import { useCallback, useEffect, useState, useSyncExternalStore } from 'react';

import { ApiError, apiClient } from '../api/apiClient';
import type { Quote } from '../api/types';
import { liveSocket, quoteStore } from './liveServices';

/** What useLiveQuote gives a component. */
export interface LiveQuoteState {
  quote: Quote | undefined;
  error: string;
}

/**
 * Loads an instrument's quote from ubi once, then keeps it up to date from the live feed.
 * @param instrumentId The instrument.
 * @returns The latest quote, and an explanation when the first load failed.
 */
export function useLiveQuote(instrumentId: string): LiveQuoteState {
  const [error, setError] = useState('');
  const subscribe = useCallback((listener: () => void) => quoteStore.subscribe(instrumentId, listener), [instrumentId]);
  const read = useCallback(() => quoteStore.get(instrumentId), [instrumentId]);
  const quote = useSyncExternalStore(subscribe, read);

  useEffect(() => {
    let cancelled = false;
    setError('');
    apiClient
      .fetchQuote(instrumentId)
      .then((loaded) => {
        if (!cancelled) {
          quoteStore.update([loaded]);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : 'The quote could not be loaded.');
        }
      });
    liveSocket.retain([instrumentId]);
    return () => {
      cancelled = true;
      liveSocket.release([instrumentId]);
    };
  }, [instrumentId]);

  return {
    quote,
    error,
  };
}
