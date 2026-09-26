import { useEffect, useRef, useState } from 'react';

import type { Quote } from '../api/types';
import { StatusBadge } from '../components/StatusBadge';
import { TiltCard } from '../components/TiltCard';
import { formatter } from '../utilities/formatter';

/** Props for QuotePanel. */
interface QuotePanelProps {
  quote: Quote | undefined;
  error: string;
  isDerivative: boolean;
}

const SOURCE_LABELS: Record<string, string> = {
  live: 'Live feed',
  cache: 'ubi cache',
  broker: 'Fetched from a broker',
};

/**
 * The last price, the change, the day's range and the day's figures, flashing when the price moves.
 * @param props The quote, a load error, and whether to show open interest.
 * @returns The panel.
 */
export function QuotePanel(props: QuotePanelProps) {
  const { quote, error, isDerivative } = props;
  const previousPrice = useRef<number | null>(null);
  const [flash, setFlash] = useState<'up' | 'down' | null>(null);
  const lastPrice = quote?.last_price ?? null;

  useEffect(() => {
    const previous = previousPrice.current;
    previousPrice.current = lastPrice;
    if (previous === null || lastPrice === null || previous === lastPrice) {
      return undefined;
    }
    setFlash(lastPrice > previous ? 'up' : 'down');
    const timer = window.setTimeout(() => setFlash(null), 700);
    return () => window.clearTimeout(timer);
  }, [lastPrice]);

  if (quote === undefined) {
    return (
      <TiltCard className="quote-panel">
        <p className="muted">{error === '' ? 'Loading the quote…' : error}</p>
      </TiltCard>
    );
  }

  const change = quote.change ?? 0;
  const direction = change > 0 ? 'up' : change < 0 ? 'down' : 'flat';
  let rangePosition = 50;
  if (quote.low !== null && quote.high !== null && quote.last_price !== null && quote.high > quote.low) {
    rangePosition = ((quote.last_price - quote.low) / (quote.high - quote.low)) * 100;
  }
  const figures: [string, string][] = [
    ['Open', formatter.price(quote.open)],
    ['High', formatter.price(quote.high)],
    ['Low', formatter.price(quote.low)],
    ['Previous close', formatter.price(quote.previous_close)],
    ['Average price', formatter.price(quote.average_price)],
    ['Volume', formatter.count(quote.volume)],
    ['Last trade', formatter.time(quote.last_trade_time)],
    ['Received', formatter.time(quote.received_at)],
  ];
  if (isDerivative) {
    figures.push(['Open interest', formatter.count(quote.oi)]);
    figures.push(['Lot size', formatter.count(quote.lot_size)]);
  }

  return (
    <TiltCard className="quote-panel">
      <div className="tilt-lift">
        <div className="card-title">
          <span className="stat-label">Last price</span>
          <StatusBadge kind={quote.source === 'live' ? 'good' : 'neutral'} label={SOURCE_LABELS[quote.source] ?? quote.source} />
        </div>
        <div className={`last-price ${flash === null ? '' : `flash-${flash}`}`}>{formatter.price(quote.last_price)}</div>
        <div className={`price-change change-${direction}`}>
          {formatter.signedPrice(quote.change)} ({formatter.signedPercent(quote.change_percent)})
        </div>
        <div className="day-range" aria-label="The day's range">
          <span className="mono">{formatter.price(quote.low)}</span>
          <div className="day-range-track">
            <div className="day-range-marker" style={{ left: `${Math.min(Math.max(rangePosition, 0), 100)}%` }} />
          </div>
          <span className="mono">{formatter.price(quote.high)}</span>
        </div>
        <dl className="figures">
          {figures.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd className="mono">{value}</dd>
            </div>
          ))}
        </dl>
      </div>
    </TiltCard>
  );
}
