import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router';

import { ApiError, apiClient } from '../api/apiClient';
import type { ChartResponse, IndicatorDescription, Quote } from '../api/types';
import { TiltCard } from '../components/TiltCard';
import { CandleView3D } from './CandleView3D';
import { indicatorCatalogueStore } from './indicatorCatalogueStore';
import { IndicatorPicker } from './IndicatorPicker';
import { liveCandleMerger } from './liveCandleMerger';
import { PriceChart } from './PriceChart';

/** One choice of how far back the chart reads. */
interface Period {
  label: string;
  days: number;
}

const DAILY_PERIODS: Period[] = [
  {
    label: '1M',
    days: 31,
  },
  {
    label: '3M',
    days: 92,
  },
  {
    label: '6M',
    days: 183,
  },
  {
    label: '1Y',
    days: 365,
  },
  {
    label: '2Y',
    days: 730,
  },
  {
    label: '5Y',
    days: 1826,
  },
  {
    label: 'Max',
    days: 36500,
  },
];

const INTRADAY_PERIODS: Period[] = [
  {
    label: '1D',
    days: 1,
  },
  {
    label: '5D',
    days: 5,
  },
  {
    label: '1M',
    days: 31,
  },
  {
    label: '3M',
    days: 92,
  },
  {
    label: '1Y',
    days: 366,
  },
];

const INTERVALS: [string, string][] = [
  ['day', 'Daily'],
  ['60minute', '1 hour'],
  ['30minute', '30 minutes'],
  ['15minute', '15 minutes'],
  ['5minute', '5 minutes'],
  ['1minute', '1 minute'],
];

const DEFAULT_INDICATORS = ['sma:20', 'rsi:14'];

/** Props for ChartPanel. */
interface ChartPanelProps {
  instrumentId: string;
  quote: Quote | undefined;
}

/**
 * The chart card: interval, period, adjustment and 2D/3D controls, the indicator picker, and the chart itself.
 * @param props The instrument and its latest quote, used to add today's candle.
 * @returns The card.
 */
export function ChartPanel(props: ChartPanelProps) {
  const { instrumentId, quote } = props;
  const [query, setQuery] = useSearchParams();
  const interval = query.get('interval') ?? 'day';
  const intraday = interval !== 'day';
  const periods = intraday ? INTRADAY_PERIODS : DAILY_PERIODS;
  const days = Number(query.get('days') ?? (intraday ? 5 : 730));
  const adjusted = query.get('adjusted') !== 'false';
  const view = query.get('view') === '3d' ? '3d' : '2d';
  const indicators = useMemo(() => (query.has('indicator') ? query.getAll('indicator').filter((value) => value !== '') : DEFAULT_INDICATORS), [query]);
  const [catalogue, setCatalogue] = useState<IndicatorDescription[]>([]);
  const [chart, setChart] = useState<ChartResponse | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const update = useCallback(
    (changes: Record<string, string | string[] | null>) => {
      const next = new URLSearchParams(query);
      for (const [name, value] of Object.entries(changes)) {
        next.delete(name);
        if (Array.isArray(value)) {
          if (value.length === 0) {
            next.append(name, '');
          }
          for (const item of value) {
            next.append(name, item);
          }
        } else if (value !== null) {
          next.set(name, value);
        }
      }
      setQuery(next, {
        replace: true,
      });
    },
    [query, setQuery],
  );

  useEffect(() => {
    indicatorCatalogueStore
      .load()
      .then(setCatalogue)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    apiClient
      .fetchChart(instrumentId, interval, days, adjusted, indicators, controller.signal)
      .then((loaded) => {
        setChart(loaded);
        setError('');
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setError(caught instanceof ApiError ? caught.message : 'The chart could not be loaded.');
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [instrumentId, interval, days, adjusted, indicators]);

  const candles = useMemo(() => {
    if (chart === null) {
      return [];
    }
    if (intraday) {
      return chart.candles;
    }
    return liveCandleMerger.merge(chart.candles, quote);
  }, [chart, quote, intraday]);

  const chooseInterval = (next: string) => {
    const nextIsIntraday = next !== 'day';
    const changes: Record<string, string | null> = {
      interval: next === 'day' ? null : next,
    };
    if (nextIsIntraday !== intraday) {
      changes.days = null;
    }
    update(changes);
  };

  return (
    <TiltCard className="chart-card">
      <div className="chart-toolbar">
        <h2>Chart</h2>
        <select className="input chart-select" value={interval} onChange={(event) => chooseInterval(event.target.value)} aria-label="Candle interval">
          {INTERVALS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <div className="segmented" role="group" aria-label="Period">
          {periods.map((period) => (
            <button
              key={period.label}
              type="button"
              className={period.days === days ? 'segmented-active' : ''}
              onClick={() => update({ days: String(period.days) })}
            >
              {period.label}
            </button>
          ))}
        </div>
        {chart?.adjustable ? (
          <label className="toggle">
            <input type="checkbox" checked={adjusted} onChange={(event) => update({ adjusted: event.target.checked ? null : 'false' })} />
            Adjusted for splits
          </label>
        ) : null}
        <div className="segmented chart-view-switch" role="group" aria-label="View">
          <button type="button" className={view === '2d' ? 'segmented-active' : ''} onClick={() => update({ view: null })}>
            2D
          </button>
          <button type="button" className={view === '3d' ? 'segmented-active' : ''} onClick={() => update({ view: '3d' })}>
            3D
          </button>
        </div>
      </div>
      {view === '2d' ? (
        <IndicatorPicker catalogue={catalogue} chosen={indicators} hasVolume={chart?.has_volume ?? true} onChange={(chosen) => update({ indicator: chosen })} />
      ) : null}
      {chart !== null && chart.errors.length > 0 ? (
        <div className="notice">
          {chart.errors.map((message) => (
            <div key={message}>{message}</div>
          ))}
        </div>
      ) : null}
      {error !== '' ? <p className="error-text">{error}</p> : null}
      <div className={`chart-area ${loading ? 'chart-loading' : ''}`}>
        {chart !== null && candles.length === 0 ? (
          <p className="empty-state">
            {intraday
              ? 'No intraday candles are stored for this instrument. ubi loads intraday history only when someone asks it to, so try the daily chart.'
              : 'No candles are stored for this period.'}
          </p>
        ) : null}
        {candles.length > 0 && view === '2d' ? (
          <PriceChart candles={candles} indicators={chart?.indicators ?? []} hasVolume={chart?.has_volume ?? false} intraday={intraday} />
        ) : null}
        {candles.length > 0 && view === '3d' ? <CandleView3D candles={candles} /> : null}
      </div>
      {chart !== null ? (
        <p className="chart-footnote muted">
          {candles.length.toLocaleString('en-IN')} candles · {chart.price_basis === 'adjusted' ? 'adjusted for corporate actions' : chart.price_basis === 'unadjusted' ? 'not adjusted' : 'prices as traded'}
          {candles.length > chart.candles.length ? ' · today’s candle from the live quote' : ''}
        </p>
      ) : null}
    </TiltCard>
  );
}
