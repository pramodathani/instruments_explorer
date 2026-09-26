import type { Quote } from '../api/types';

type Listener = () => void;

/** Holds the latest quote of each instrument and tells the components showing it when it changes. */
export class QuoteStore {
  private quotes = new Map<string, Quote>();
  private listeners = new Map<string, Set<Listener>>();

  /**
   * Starts listening for changes to one instrument's quote.
   * @param instrumentId The instrument.
   * @param listener Called after the quote changes.
   * @returns A function that stops listening.
   */
  subscribe(instrumentId: string, listener: Listener): () => void {
    let set = this.listeners.get(instrumentId);
    if (set === undefined) {
      set = new Set();
      this.listeners.set(instrumentId, set);
    }
    set.add(listener);
    return () => {
      const current = this.listeners.get(instrumentId);
      if (current === undefined) {
        return;
      }
      current.delete(listener);
      if (current.size === 0) {
        this.listeners.delete(instrumentId);
        this.quotes.delete(instrumentId);
      }
    };
  }

  /**
   * Reads an instrument's latest quote.
   * @param instrumentId The instrument.
   * @returns The quote, or undefined before one arrives.
   */
  get(instrumentId: string): Quote | undefined {
    return this.quotes.get(instrumentId);
  }

  /**
   * Stores quotes and notifies each changed instrument's listeners, ignoring a quote older than the one held.
   * @param quotes The quotes.
   */
  update(quotes: Quote[]): void {
    for (const quote of quotes) {
      const held = this.quotes.get(quote.instrument_id);
      if (held !== undefined && held.received_at !== null && quote.received_at !== null && quote.received_at < held.received_at) {
        continue;
      }
      this.quotes.set(quote.instrument_id, quote);
      const set = this.listeners.get(quote.instrument_id);
      if (set !== undefined) {
        for (const listener of set) {
          listener();
        }
      }
    }
  }
}
