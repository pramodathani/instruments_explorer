import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router';

import { ApiError, apiClient } from '../api/apiClient';
import type { ScreenerAnswer, ScreenerRow, ScreenerRun, ScreenerSetup } from '../api/types';
import { AnimatedNumber } from '../components/AnimatedNumber';
import { TiltCard } from '../components/TiltCard';
import { liveSocket } from '../live/liveServices';
import { formatter } from '../utilities/formatter';
import { ConditionPicker } from './ConditionPicker';
import { SectorHeatmap } from './SectorHeatmap';

/** A ready-made screen. */
interface Preset {
  label: string;
  conditions: string[];
  sort: string;
  descending: boolean;
}

const PRESETS: Preset[] = [
  {
    label: 'Oversold',
    conditions: ['rsi:0:30'],
    sort: 'rsi_14',
    descending: false,
  },
  {
    label: 'Overbought',
    conditions: ['rsi:70:100'],
    sort: 'rsi_14',
    descending: true,
  },
  {
    label: 'Golden cross',
    conditions: ['golden_cross:10'],
    sort: 'change_21d',
    descending: true,
  },
  {
    label: 'Near 52-week high',
    conditions: ['near_high:3'],
    sort: 'from_high',
    descending: true,
  },
  {
    label: 'Volume spike',
    conditions: ['volume_spike:2.5'],
    sort: 'volume_ratio',
    descending: true,
  },
  {
    label: 'Strong uptrend',
    conditions: ['above_average:200', 'above_average:50', 'strong_trend:25'],
    sort: 'change_63d',
    descending: true,
  },
  {
    label: 'Momentum turning up',
    conditions: ['macd_turn:5', 'above_average:200'],
    sort: 'change_5d',
    descending: true,
  },
];

/** One column of the results table. */
interface Column {
  key: keyof ScreenerRow;
  label: string;
  kind: 'price' | 'percent' | 'number' | 'ratio';
}

const COLUMNS: Column[] = [
  {
    key: 'close',
    label: 'Close',
    kind: 'price',
  },
  {
    key: 'change_1d',
    label: '1D',
    kind: 'percent',
  },
  {
    key: 'change_21d',
    label: '1M',
    kind: 'percent',
  },
  {
    key: 'change_252d',
    label: '1Y',
    kind: 'percent',
  },
  {
    key: 'from_high',
    label: 'From 52W high',
    kind: 'percent',
  },
  {
    key: 'rsi_14',
    label: 'RSI',
    kind: 'number',
  },
  {
    key: 'adx_14',
    label: 'ADX',
    kind: 'number',
  },
  {
    key: 'volume_ratio',
    label: 'Volume ×',
    kind: 'ratio',
  },
];

/**
 * The screener page: pick conditions and sectors over a universe of stocks, then read the matches as a sector heatmap and a sortable table.
 * @returns The page.
 */
export function ScreenerPage() {
  const [query, setQuery] = useSearchParams();
  const universe = query.get('universe') ?? 'total_market';
  const conditions = useMemo(() => (query.has('condition') ? query.getAll('condition').filter((value) => value !== '') : PRESETS[0].conditions), [query]);
  const sectors = useMemo(() => query.getAll('sector'), [query]);
  const sort = query.get('sort') ?? 'rsi_14';
  const descending = query.get('descending') === 'true';
  const [setup, setSetup] = useState<ScreenerSetup | null>(null);
  const [answer, setAnswer] = useState<ScreenerAnswer | null>(null);
  const [run, setRun] = useState<ScreenerRun | null>(null);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  const update = useCallback(
    (changes: Record<string, string | string[] | null>) => {
      const next = new URLSearchParams(query);
      for (const [name, value] of Object.entries(changes)) {
        next.delete(name);
        if (Array.isArray(value)) {
          if (value.length === 0 && name === 'condition') {
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
    apiClient
      .fetchScreenerSetup()
      .then((loaded) => {
        setSetup(loaded);
        setRun(loaded.job);
      })
      .catch((caught: unknown) => setError(caught instanceof ApiError ? caught.message : 'The screener could not be loaded.'));
  }, []);

  useEffect(() => {
    return liveSocket.onScreenerJob((updated) => {
      setRun(updated);
      if (updated.status !== 'running') {
        setReloadKey((key) => key + 1);
      }
    });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    apiClient
      .runScreen(
        {
          universe,
          conditions,
          sectors,
          sort,
          descending,
        },
        controller.signal,
      )
      .then((loaded) => {
        setAnswer(loaded);
        setError('');
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setError(caught instanceof ApiError ? caught.message : 'The screen could not be run.');
        }
      });
    return () => controller.abort();
  }, [universe, conditions, sectors, sort, descending, reloadKey]);

  const refresh = () => {
    apiClient
      .refreshScreener(universe)
      .then(setRun)
      .catch((caught: unknown) => setError(caught instanceof ApiError ? caught.message : 'The refresh could not start.'));
  };

  const applyPreset = (preset: Preset) => {
    update({
      condition: preset.conditions,
      sort: preset.sort,
      descending: preset.descending ? 'true' : null,
    });
  };

  const toggleSector = (sector: string) => {
    const next = sectors.includes(sector) ? sectors.filter((value) => value !== sector) : [...sectors, sector];
    update({
      sector: next,
    });
  };

  const sortBy = (key: string) => {
    if (key === sort) {
      update({
        descending: descending ? null : 'true',
      });
    } else {
      update({
        sort: key,
        descending: key === 'symbol' || key === 'sector' ? null : 'true',
      });
    }
  };

  const running = run !== null && run.status === 'running';
  const lastRun = answer?.last_run ?? setup?.last_runs[universe] ?? null;
  const progress = running && run.total > 0 ? ((run.done + run.failed) / run.total) * 100 : 0;

  const cell = (row: ScreenerRow, column: Column) => {
    const value = row[column.key] as number | null;
    if (column.kind === 'price') {
      return formatter.price(value);
    }
    if (column.kind === 'percent') {
      return <span className={formatter.changeClass(value)}>{formatter.signedPercent(value)}</span>;
    }
    if (column.kind === 'ratio') {
      return value === null ? '–' : `${value.toFixed(2)}×`;
    }
    return value === null ? '–' : value.toFixed(1);
  };

  return (
    <>
      <h1 className="page-title">Screener</h1>
      <p className="page-subtitle">
        Find stocks that meet technical conditions computed with TA-Lib from each stock’s daily candles. Figures are computed once a day after ubi loads the day’s prices.
      </p>
      <div className="screener-status card">
        <div className="segmented" role="group" aria-label="Universe">
          {(setup?.universes ?? []).map((entry) => (
            <button key={entry.key} type="button" className={entry.key === universe ? 'segmented-active' : ''} onClick={() => update({ universe: entry.key === 'total_market' ? null : entry.key })}>
              {entry.label}
            </button>
          ))}
        </div>
        <div className="screener-run">
          {running ? (
            <>
              <span>
                Computing figures: {formatter.count(run.done + run.failed)} of {formatter.count(run.total)}
              </span>
              <div className="screener-progress">
                <span style={{ width: `${progress}%` }} />
              </div>
            </>
          ) : lastRun !== null ? (
            <span className="muted">
              Figures from {formatter.dateTime(lastRun.finished_at)} · {formatter.count(lastRun.done)} stocks
              {lastRun.failed > 0 ? ` · ${lastRun.failed} without enough history` : ''}
            </span>
          ) : (
            <span className="muted">No figures yet for this universe.</span>
          )}
          <button type="button" className="button" onClick={refresh} disabled={running}>
            {running ? 'Computing…' : lastRun === null ? 'Compute figures' : 'Recompute'}
          </button>
        </div>
      </div>
      <div className="screener-presets">
        {PRESETS.map((preset) => (
          <button key={preset.label} type="button" className="chip preset-chip" onClick={() => applyPreset(preset)}>
            {preset.label}
          </button>
        ))}
      </div>
      <div className="card screener-builder">
        <ConditionPicker catalogue={setup?.conditions ?? []} chosen={conditions} onChange={(chosen) => update({ condition: chosen })} />
        {answer !== null && answer.sector_names.length > 0 ? (
          <div className="sector-chips">
            {answer.sector_names.map((sector) => (
              <button key={sector} type="button" className={`chip sector-chip ${sectors.includes(sector) ? 'sector-chosen' : ''}`} onClick={() => toggleSector(sector)}>
                {sector}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      {error !== '' ? <p className="error-text">{error}</p> : null}
      {answer !== null ? (
        <>
          <div className="grid grid-tiles section">
            <TiltCard className="stat-tile">
              <div className="tilt-lift">
                <div className="stat-label">Matches</div>
                <div className="stat-value">
                  <AnimatedNumber value={answer.matched} />
                </div>
                <div className="stat-detail">of {formatter.count(answer.with_figures)} stocks with figures</div>
              </div>
            </TiltCard>
            <TiltCard className="stat-tile">
              <div className="tilt-lift">
                <div className="stat-label">Sectors</div>
                <div className="stat-value">
                  <AnimatedNumber value={answer.sectors.length} />
                </div>
                <div className="stat-detail">{answer.sectors[0] ? `most: ${answer.sectors[0].sector}` : 'none'}</div>
              </div>
            </TiltCard>
          </div>
          <section className="card section heatmap-card">
            <h2>Heatmap by sector</h2>
            <p className="muted">Each box is a stock, sized by its average daily traded value and coloured by today’s change. Click a sector to zoom in, and a stock to open it.</p>
            <SectorHeatmap sectors={answer.sectors} />
          </section>
          <section className="card section screener-results">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="sortable" onClick={() => sortBy('symbol')}>
                    Stock {sort === 'symbol' ? (descending ? '↓' : '↑') : ''}
                  </th>
                  <th className="sortable" onClick={() => sortBy('sector')}>
                    Sector {sort === 'sector' ? (descending ? '↓' : '↑') : ''}
                  </th>
                  {COLUMNS.map((column) => (
                    <th key={column.key} className="numeric sortable" onClick={() => sortBy(column.key)}>
                      {column.label} {sort === column.key ? (descending ? '↓' : '↑') : ''}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {answer.rows.map((row, position) => (
                  <tr key={row.instrument_id} className="result-row" style={{ animationDelay: `${Math.min(position, 24) * 18}ms` }}>
                    <td>
                      <Link to={`/instrument/${row.instrument_id}`} className="result-name">
                        {row.symbol}
                      </Link>
                      <div className="result-company muted">{row.name}</div>
                    </td>
                    <td className="muted">{row.sector}</td>
                    {COLUMNS.map((column) => (
                      <td key={column.key} className="numeric mono">
                        {cell(row, column)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {answer.matched === 0 ? <p className="empty-state">No stock meets every condition. Remove one, or loosen its numbers.</p> : null}
          </section>
        </>
      ) : null}
    </>
  );
}
