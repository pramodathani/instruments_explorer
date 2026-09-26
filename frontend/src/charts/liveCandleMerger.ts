import type { CandleRow, Quote } from '../api/types';

const INDIA_OFFSET_MILLISECONDS = 5.5 * 60 * 60 * 1000;
const DAY_MILLISECONDS = 24 * 60 * 60 * 1000;

/** Adds today's candle, built from the live quote, to daily candles whose stored history stops before today. */
export class LiveCandleMerger {
  /**
   * Returns the candles with today's candle added or updated from the quote.
   * @param candles The stored daily candles, oldest first.
   * @param quote The latest quote, or undefined.
   * @returns The candles, unchanged when the quote is missing, has no trade time or open, or belongs to a day already stored.
   */
  merge(candles: CandleRow[], quote: Quote | undefined): CandleRow[] {
    if (quote === undefined || quote.last_price === null || quote.last_trade_time === null || quote.open === null) {
      return candles;
    }
    const dayStart = this.indiaDayStart(quote.last_trade_time * 1000);
    const last = candles[candles.length - 1];
    if (last !== undefined && last[0] > dayStart) {
      return candles;
    }
    const today: CandleRow = [
      dayStart,
      quote.open,
      quote.high ?? quote.last_price,
      quote.low ?? quote.last_price,
      quote.last_price,
      quote.volume,
      quote.oi,
    ];
    if (last !== undefined && last[0] === dayStart) {
      return [...candles.slice(0, -1), today];
    }
    return [...candles, today];
  }

  /**
   * Finds midnight in India of the day an instant falls on.
   * @param epochMilliseconds The instant.
   * @returns Midnight India time of that day, in epoch milliseconds.
   */
  private indiaDayStart(epochMilliseconds: number): number {
    const shifted = epochMilliseconds + INDIA_OFFSET_MILLISECONDS;
    return shifted - (shifted % DAY_MILLISECONDS) - INDIA_OFFSET_MILLISECONDS;
  }
}

export const liveCandleMerger = new LiveCandleMerger();
