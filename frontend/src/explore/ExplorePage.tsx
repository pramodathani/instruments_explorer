import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';

import { ApiError, apiClient } from '../api/apiClient';
import type { FacetColumn, IndexStatus, SearchParameters, SearchResponse } from '../api/types';
import { AnimatedNumber } from '../components/AnimatedNumber';
import { Icon } from '../components/Icon';
import { TiltCard } from '../components/TiltCard';
import { formatter } from '../utilities/formatter';
import { FacetGroup } from './FacetGroup';
import { ResultsTable } from './ResultsTable';
import { FACET_COLUMNS, FACET_TITLES, PAGE_SIZE, searchState } from './searchState';

const TYPING_PAUSE_MILLISECONDS = 250;
const BUILD_POLL_MILLISECONDS = 2000;

/**
 * The Explore page: full-text search over every instrument, narrowed by filters with live counts.
 * @returns The page.
 */
export function ExplorePage() {
  const [query, setQuery] = useSearchParams();
  const parameters = useMemo(() => searchState.read(query), [query]);
  const [typed, setTyped] = useState(parameters.text);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [indexStatus, setIndexStatus] = useState<IndexStatus | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const controllerReference = useRef<AbortController | null>(null);

  const replaceSearch = useCallback(
    (next: SearchParameters) => {
      setQuery(searchState.write(next), {
        replace: true,
      });
    },
    [setQuery],
  );

  useEffect(() => {
    if (typed === parameters.text) {
      return undefined;
    }
    const timer = window.setTimeout(() => {
      replaceSearch({
        ...parameters,
        text: typed,
      });
    }, TYPING_PAUSE_MILLISECONDS);
    return () => window.clearTimeout(timer);
  }, [typed, parameters, replaceSearch]);

  useEffect(() => {
    controllerReference.current?.abort();
    const controller = new AbortController();
    controllerReference.current = controller;
    setLoading(true);
    apiClient
      .searchInstruments(parameters, controller.signal)
      .then((loaded) => {
        setResponse(loaded);
        setError('');
        setIndexStatus(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        if (caught instanceof ApiError && caught.statusCode === 503) {
          apiClient
            .fetchIndexStatus()
            .then(setIndexStatus)
            .catch(() => undefined);
        }
        setError(caught instanceof ApiError ? caught.message : 'The search could not reach the server.');
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [parameters, retryKey]);

  useEffect(() => {
    if (indexStatus === null || indexStatus.state === 'ready') {
      return undefined;
    }
    const timer = window.setTimeout(() => setRetryKey((key) => key + 1), BUILD_POLL_MILLISECONDS);
    return () => window.clearTimeout(timer);
  }, [indexStatus]);

  const loadMore = useCallback(() => {
    if (response === null || loadingMore || response.results.length >= response.total) {
      return;
    }
    setLoadingMore(true);
    const controller = new AbortController();
    apiClient
      .searchInstruments(
        {
          ...parameters,
          offset: response.results.length,
          limit: PAGE_SIZE,
        },
        controller.signal,
      )
      .then((page) => {
        setResponse((current) => {
          if (current === null) {
            return page;
          }
          return {
            ...current,
            results: [...current.results, ...page.results],
          };
        });
      })
      .catch(() => undefined)
      .finally(() => setLoadingMore(false));
  }, [response, loadingMore, parameters]);

  const toggleFilter = (column: FacetColumn, value: string) => {
    replaceSearch(searchState.toggle(parameters, column, value));
  };

  const setStrike = (bound: 'strikeMinimum' | 'strikeMaximum', text: string) => {
    const value = text.trim() === '' ? null : Number(text);
    replaceSearch({
      ...parameters,
      [bound]: value !== null && Number.isFinite(value) ? value : null,
    });
  };

  const clearFilters = () => {
    setTyped('');
    replaceSearch(searchState.read(new URLSearchParams()));
  };

  const activeFilters = searchState.activeFilterCount(parameters);

  return (
    <>
      <div className="explore-heading">
        <div>
          <h1 className="page-title">Explore</h1>
          <p className="page-subtitle">
            Search every instrument the brokers carry, then narrow it down. Each count shows what choosing that value would give.
          </p>
        </div>
        <TiltCard className="explore-total">
          <div className="tilt-lift">
            <div className="stat-label">Matching instruments</div>
            <div className="stat-value">{response === null ? '…' : <AnimatedNumber value={response.total} />}</div>
            <div className="stat-detail">{response === null ? '' : `Catalogue of ${formatter.date(response.mapping_date)}`}</div>
          </div>
        </TiltCard>
      </div>
      <div className="search-bar card">
        <Icon name="explore" size={20} />
        <input
          className="search-input"
          type="search"
          placeholder="Try “reliance”, “nifty sep 25000 ce” or “gold fut”"
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
          aria-label="Search instruments"
          autoFocus
        />
        <select
          className="input sort-select"
          value={parameters.sort}
          onChange={(event) =>
            replaceSearch({
              ...parameters,
              sort: event.target.value as SearchParameters['sort'],
            })
          }
          aria-label="Sort order"
        >
          <option value="relevance">Best match</option>
          <option value="name">Name</option>
          <option value="expiry">Expiry</option>
          <option value="strike">Strike</option>
        </select>
      </div>
      <div className="explore-layout">
        <aside className="facets card">
          <div className="card-title">
            <h2>Filters</h2>
            {activeFilters > 0 ? (
              <button type="button" className="button button-quiet" onClick={clearFilters}>
                Clear {activeFilters}
              </button>
            ) : null}
          </div>
          {FACET_COLUMNS.map((column) => (
            <FacetGroup
              key={column}
              column={column}
              title={FACET_TITLES[column]}
              values={response?.facets[column] ?? []}
              chosen={parameters.filters[column] ?? []}
              onToggle={toggleFilter}
            />
          ))}
          <fieldset className="facet-group">
            <legend>Strike range</legend>
            <div className="strike-range">
              <input
                className="input"
                type="number"
                placeholder="From"
                defaultValue={parameters.strikeMinimum ?? ''}
                key={`minimum-${parameters.strikeMinimum}`}
                onBlur={(event) => setStrike('strikeMinimum', event.target.value)}
                aria-label="Lowest strike"
              />
              <span className="muted">to</span>
              <input
                className="input"
                type="number"
                placeholder="To"
                defaultValue={parameters.strikeMaximum ?? ''}
                key={`maximum-${parameters.strikeMaximum}`}
                onBlur={(event) => setStrike('strikeMaximum', event.target.value)}
                aria-label="Highest strike"
              />
            </div>
          </fieldset>
        </aside>
        <section className={`results-panel card ${loading ? 'results-loading' : ''}`}>
          {indexStatus !== null && indexStatus.state !== 'ready' ? (
            <div className="index-building">
              <div className="index-building-orbit" aria-hidden="true" />
              <h2>Building the instrument index</h2>
              <p className="muted">
                {indexStatus.building_count !== null
                  ? `${formatter.count(indexStatus.building_count)} instruments stored so far. `
                  : ''}
                The whole catalogue is downloaded from ubi once per day; this takes about ten seconds.
              </p>
              {indexStatus.last_error !== null ? <p className="error-text">{indexStatus.last_error}</p> : null}
            </div>
          ) : null}
          {error !== '' && (indexStatus === null || indexStatus.state === 'ready') ? <p className="error-text">{error}</p> : null}
          {response !== null && response.results.length === 0 && !loading ? (
            <p className="empty-state">Nothing matches. Try fewer words or clear a filter.</p>
          ) : null}
          {response !== null && response.results.length > 0 ? (
            <ResultsTable
              results={response.results}
              hasMore={response.results.length < response.total}
              loadingMore={loadingMore}
              onLoadMore={loadMore}
            />
          ) : null}
        </section>
      </div>
    </>
  );
}
