import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router';

import { ApiError, apiClient } from '../api/apiClient';
import type { InstrumentDocument } from '../api/types';
import { StatusBadge } from '../components/StatusBadge';
import { TiltCard } from '../components/TiltCard';
import { useLiveQuote } from '../live/useLiveQuote';
import { formatter } from '../utilities/formatter';
import { DepthTable } from './DepthTable';
import { QuotePanel } from './QuotePanel';

const ATTRIBUTE_LABELS: Record<string, string> = {
  isin: 'ISIN',
  display_name: 'Name',
  instrument_type: 'Instrument type',
  series: 'Series',
  freeze_quantity: 'Freeze quantity',
  price_band_high: 'Upper price band',
  price_band_low: 'Lower price band',
  multiplier: 'Multiplier',
  underlying_token: 'Underlying token',
  surveillance_category: 'Surveillance category',
  permitted_to_trade: 'Permitted to trade',
  buy_allowed: 'Buy allowed',
  sell_allowed: 'Sell allowed',
  intraday_leverage: 'Intraday leverage',
  margin_trading_leverage: 'Margin trading leverage',
  pledge_eligible: 'Pledge eligible',
};

/**
 * One instrument's page: its live quote, depth, contract details and broker attributes.
 * @returns The page.
 */
export function InstrumentPage() {
  const { instrumentId = '' } = useParams();
  const [document, setDocument] = useState<InstrumentDocument | null>(null);
  const [error, setError] = useState('');
  const { quote, error: quoteError } = useLiveQuote(instrumentId);

  useEffect(() => {
    let cancelled = false;
    setDocument(null);
    setError('');
    apiClient
      .fetchInstrument(instrumentId)
      .then((loaded) => {
        if (!cancelled) {
          setDocument(loaded);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : 'The instrument could not be loaded.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [instrumentId]);

  if (error !== '') {
    return (
      <>
        <h1 className="page-title">Instrument not found</h1>
        <p className="page-subtitle">
          {error} Go back to <Link to="/explore">Explore</Link>.
        </p>
      </>
    );
  }
  const record = document?.instrument ?? null;
  const details = document?.details ?? null;
  const title = record?.display_name ?? (document === null ? 'Loading…' : instrumentId);
  const attributes = Object.entries(document?.attributes ?? {});

  return (
    <>
      <div className="instrument-heading">
        <h1 className="page-title">{title}</h1>
        {record !== null ? (
          <div className="instrument-chips">
            <span className={`exchange-tag exchange-${record.exchange}`}>{record.exchange.toUpperCase()}</span>
            <span className="chip">{formatter.segment(record.bare_segment)}</span>
            <span className="chip">{formatter.shape(record.shape)}</span>
            {record.is_index ? <span className="chip">Index</span> : null}
            {document?.attributes.display_name !== undefined ? <span className="muted">{document.attributes.display_name}</span> : null}
          </div>
        ) : null}
      </div>
      {document?.ubi_error ? (
        <div className="notice">
          <StatusBadge kind="warning" label="ubi" /> {document.ubi_error}
        </div>
      ) : null}
      <div className="instrument-grid">
        <QuotePanel quote={quote} error={quoteError} isDerivative={record !== null && record.shape !== 'security'} />
        <DepthTable quote={quote} />
        <TiltCard className="chart-placeholder">
          <div className="tilt-lift">
            <h2>Chart and indicators</h2>
            <p className="muted">The Highcharts Stock chart with TA-Lib indicators and a 3D candle view arrives in phase 3.</p>
          </div>
        </TiltCard>
        <TiltCard>
          <div className="tilt-lift">
            <h2>Contract</h2>
            <dl className="figures figures-two">
              <div>
                <dt>Lot size</dt>
                <dd className="mono">{formatter.count(details?.lot_size)}</dd>
              </div>
              <div>
                <dt>Tick size</dt>
                <dd className="mono">{details?.tick_size ?? '–'}</dd>
              </div>
              <div>
                <dt>Expiry</dt>
                <dd className="mono">{formatter.date(record?.expiry_date ?? null) || '–'}</dd>
              </div>
              <div>
                <dt>Strike</dt>
                <dd className="mono">{formatter.strike(record?.strike_price ?? null) || '–'}</dd>
              </div>
              <div>
                <dt>First seen</dt>
                <dd className="mono">{formatter.date(details?.first_seen_date ?? null) || '–'}</dd>
              </div>
              <div>
                <dt>Last seen</dt>
                <dd className="mono">{formatter.date(details?.last_seen_date ?? null) || '–'}</dd>
              </div>
            </dl>
            <h3 className="section-heading">Listed by {details?.carried_by.length ?? 0} brokers</h3>
            <div className="broker-list">
              {(details?.carried_by ?? []).map((handle) => (
                <span key={handle.broker} className="chip" title={`${handle.order_symbol} · token ${handle.broker_token}`}>
                  {handle.broker}
                </span>
              ))}
            </div>
            <p className="muted mono instrument-id">{instrumentId}</p>
          </div>
        </TiltCard>
        <TiltCard>
          <div className="tilt-lift">
            <h2>Broker attributes</h2>
            {attributes.length === 0 ? <p className="muted">No broker publishes extra attributes for this instrument.</p> : null}
            <dl className="figures figures-two">
              {attributes.map(([name, value]) => (
                <div key={name}>
                  <dt>{ATTRIBUTE_LABELS[name] ?? name}</dt>
                  <dd className="mono">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </TiltCard>
      </div>
    </>
  );
}
