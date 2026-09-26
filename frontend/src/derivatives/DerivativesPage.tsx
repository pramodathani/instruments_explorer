import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router';

import { ApiError, apiClient } from '../api/apiClient';
import type { ChainRow, ExpiryDescription, OptionChain, Underlying, VolatilitySurface } from '../api/types';
import { AnimatedNumber } from '../components/AnimatedNumber';
import { TiltCard } from '../components/TiltCard';
import { formatter } from '../utilities/formatter';
import { ChainCharts } from './ChainCharts';
import { ExpiryStrip } from './ExpiryStrip';
import { OptionChainTable } from './OptionChainTable';
import { UnderlyingList } from './UnderlyingList';
import { VolatilitySurface3D } from './VolatilitySurface3D';

const REFRESH_MILLISECONDS = 5000;
const NEAR_STRIKES_EACH_SIDE = 15;

const FORWARD_SOURCES: Record<string, string> = {
  future: 'from the same-expiry future',
  spot: 'spot carried forward',
  nearest_future: 'from the nearest future',
};

type Tab = 'chain' | 'charts' | 'surface';

/**
 * The derivatives page: pick an underlying and an expiry, then read its option chain, charts and 3D volatility surface.
 * @returns The page.
 */
export function DerivativesPage() {
  const [query, setQuery] = useSearchParams();
  const exchange = query.get('exchange') ?? '';
  const underlying = query.get('underlying') ?? '';
  const expiry = query.get('expiry') ?? '';
  const tab = (query.get('tab') ?? 'chain') as Tab;
  const showAll = query.get('strikes') === 'all';
  const [description, setDescription] = useState<ExpiryDescription | null>(null);
  const [chain, setChain] = useState<OptionChain | null>(null);
  const [surface, setSurface] = useState<VolatilitySurface | null>(null);
  const [error, setError] = useState('');

  const update = useCallback(
    (changes: Record<string, string | null>) => {
      const next = new URLSearchParams(query);
      for (const [name, value] of Object.entries(changes)) {
        if (value === null) {
          next.delete(name);
        } else {
          next.set(name, value);
        }
      }
      setQuery(next, {
        replace: true,
      });
    },
    [query, setQuery],
  );

  const selectUnderlying = useCallback(
    (chosen: Underlying) => {
      update({
        exchange: chosen.exchange,
        underlying: chosen.underlying_symbol,
        expiry: null,
      });
    },
    [update],
  );

  const handleLoaded = useCallback(
    (underlyings: Underlying[]) => {
      if (underlying === '' && underlyings.length > 0) {
        selectUnderlying(underlyings[0]);
      }
    },
    [underlying, selectUnderlying],
  );

  useEffect(() => {
    if (exchange === '' || underlying === '') {
      return;
    }
    let cancelled = false;
    setDescription(null);
    setChain(null);
    setSurface(null);
    apiClient
      .fetchExpiries(exchange, underlying)
      .then((loaded) => {
        if (cancelled) {
          return;
        }
        setDescription(loaded);
        setError('');
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : 'The expiries could not be loaded.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [exchange, underlying]);

  useEffect(() => {
    if (description === null || description.option_expiries.length === 0) {
      return;
    }
    const known = description.option_expiries.some((entry) => entry.expiry_date === expiry);
    if (!known) {
      const upcoming = description.option_expiries.find((entry) => entry.days > 0) ?? description.option_expiries[0];
      update({
        expiry: upcoming.expiry_date,
      });
    }
  }, [description, expiry, update]);

  useEffect(() => {
    if (exchange === '' || underlying === '' || expiry === '' || description === null) {
      return undefined;
    }
    let controller = new AbortController();
    const load = () => {
      controller.abort();
      controller = new AbortController();
      const signal = controller.signal;
      apiClient
        .fetchChain(exchange, underlying, expiry, signal)
        .then((loaded) => {
          setChain(loaded);
          setError('');
        })
        .catch((caught: unknown) => {
          if (!signal.aborted) {
            setError(caught instanceof ApiError ? caught.message : 'The option chain could not be loaded.');
          }
        });
    };
    load();
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        load();
      }
    }, REFRESH_MILLISECONDS);
    return () => {
      window.clearInterval(timer);
      controller.abort();
    };
  }, [exchange, underlying, expiry, description]);

  useEffect(() => {
    if (tab !== 'surface' || exchange === '' || underlying === '') {
      return undefined;
    }
    const controller = new AbortController();
    apiClient
      .fetchSurface(exchange, underlying, controller.signal)
      .then(setSurface)
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setError(caught instanceof ApiError ? caught.message : 'The volatility surface could not be loaded.');
        }
      });
    return () => controller.abort();
  }, [tab, exchange, underlying]);

  const rows = useMemo((): ChainRow[] => {
    if (chain === null) {
      return [];
    }
    if (showAll || chain.atm_strike === null) {
      return chain.rows;
    }
    const centre = chain.rows.findIndex((row) => row.strike === chain.atm_strike);
    const start = Math.max(0, centre - NEAR_STRIKES_EACH_SIDE);
    return chain.rows.slice(start, centre + NEAR_STRIKES_EACH_SIDE + 1);
  }, [chain, showAll]);

  const atmRow = chain?.rows.find((row) => row.strike === chain.atm_strike);
  const atmIv = useMemo(() => {
    const values: number[] = [];
    if (atmRow?.call?.iv) {
      values.push(atmRow.call.iv);
    }
    if (atmRow?.put?.iv) {
      values.push(atmRow.put.iv);
    }
    if (values.length === 0) {
      return null;
    }
    return values.reduce((total, value) => total + value, 0) / values.length;
  }, [atmRow]);

  return (
    <>
      <h1 className="page-title">Derivatives</h1>
      <p className="page-subtitle">
        Pick an underlying and an expiry to read its option chain, open interest, volatility smile and volatility surface. Implied volatility and the Greeks use Black’s model on the forward price.
      </p>
      <div className="derivatives-layout">
        <UnderlyingList selectedExchange={exchange} selectedUnderlying={underlying} onSelect={selectUnderlying} onLoaded={handleLoaded} />
        <section className="derivatives-main">
          {error !== '' ? <p className="error-text">{error}</p> : null}
          {description !== null ? (
            <>
              <div className="derivatives-heading">
                <h2 className="underlying-title">
                  {description.underlying_symbol}
                  <span className={`exchange-tag exchange-${description.exchange}`}>{description.exchange.toUpperCase()}</span>
                </h2>
                <div className="future-chips">
                  {description.spot !== null ? (
                    <Link className="chip" to={`/instrument/${description.spot.instrument_id}`}>
                      Spot {formatter.price(description.spot.last_price)}
                    </Link>
                  ) : null}
                  {description.futures.map((future) => (
                    <Link key={future.instrument_id} className="chip" to={`/instrument/${future.instrument_id}`}>
                      {formatter.date(future.expiry_date)} fut {formatter.price(future.last_price)}
                    </Link>
                  ))}
                </div>
              </div>
              <ExpiryStrip expiries={description.option_expiries} selected={expiry} onSelect={(chosen) => update({ expiry: chosen })} />
            </>
          ) : null}
          {chain !== null ? (
            <div className="grid grid-tiles derivative-stats">
              <TiltCard className="stat-tile">
                <div className="tilt-lift">
                  <div className="stat-label">Forward</div>
                  <div className="stat-value">{chain.forward === null ? '–' : <AnimatedNumber value={chain.forward} decimals={2} />}</div>
                  <div className="stat-detail">{chain.forward_source === null ? 'no price available' : FORWARD_SOURCES[chain.forward_source]}</div>
                </div>
              </TiltCard>
              <TiltCard className="stat-tile">
                <div className="tilt-lift">
                  <div className="stat-label">At the money</div>
                  <div className="stat-value">{formatter.strike(chain.atm_strike) || '–'}</div>
                  <div className="stat-detail">IV {formatter.volatility(atmIv)}</div>
                </div>
              </TiltCard>
              <TiltCard className="stat-tile">
                <div className="tilt-lift">
                  <div className="stat-label">Max pain</div>
                  <div className="stat-value">{formatter.strike(chain.max_pain) || '–'}</div>
                  <div className="stat-detail">where option buyers would collect least</div>
                </div>
              </TiltCard>
              <TiltCard className="stat-tile">
                <div className="tilt-lift">
                  <div className="stat-label">Put–call ratio</div>
                  <div className="stat-value">{chain.put_call_ratio === null ? '–' : chain.put_call_ratio.toFixed(2)}</div>
                  <div className="stat-detail">
                    {formatter.count(chain.total_put_oi)} puts / {formatter.count(chain.total_call_oi)} calls OI
                  </div>
                </div>
              </TiltCard>
              <TiltCard className="stat-tile">
                <div className="tilt-lift">
                  <div className="stat-label">Time left</div>
                  <div className="stat-value">
                    <AnimatedNumber value={Math.max(chain.days, 0)} decimals={1} /> <span className="muted">days</span>
                  </div>
                  <div className="stat-detail">to 15:30 on {formatter.date(chain.expiry_date)}</div>
                </div>
              </TiltCard>
            </div>
          ) : null}
          {description !== null ? (
            <div className="card derivatives-panel">
              <div className="derivatives-tabs">
                <div className="segmented" role="tablist">
                  <button type="button" className={tab === 'chain' ? 'segmented-active' : ''} onClick={() => update({ tab: null })}>
                    Option chain
                  </button>
                  <button type="button" className={tab === 'charts' ? 'segmented-active' : ''} onClick={() => update({ tab: 'charts' })}>
                    OI and smile
                  </button>
                  <button type="button" className={tab === 'surface' ? 'segmented-active' : ''} onClick={() => update({ tab: 'surface' })}>
                    3D volatility surface
                  </button>
                </div>
                {tab !== 'surface' ? (
                  <label className="toggle">
                    <input type="checkbox" checked={showAll} onChange={(event) => update({ strikes: event.target.checked ? 'all' : null })} />
                    All {chain?.rows.length ?? ''} strikes
                  </label>
                ) : null}
              </div>
              {chain === null && tab !== 'surface' ? <p className="muted">Loading the option chain…</p> : null}
              {chain !== null && tab === 'chain' ? <OptionChainTable chain={chain} rows={rows} /> : null}
              {chain !== null && tab === 'charts' ? <ChainCharts chain={chain} rows={rows} /> : null}
              {tab === 'surface' && surface === null ? <p className="muted">Working out implied volatility across the expiries…</p> : null}
              {tab === 'surface' && surface !== null && surface.expiries.length === 0 ? (
                <p className="empty-state">Too few option prices to draw a surface for this underlying.</p>
              ) : null}
              {tab === 'surface' && surface !== null && surface.expiries.length > 0 ? <VolatilitySurface3D surface={surface} /> : null}
            </div>
          ) : null}
        </section>
      </div>
    </>
  );
}
