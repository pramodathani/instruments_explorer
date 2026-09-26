import { useEffect, useState } from 'react';

import { ApiError, apiClient } from '../api/apiClient';
import type { Underlying } from '../api/types';
import { formatter } from '../utilities/formatter';

const TYPING_PAUSE_MILLISECONDS = 200;

/** Props for UnderlyingList. */
interface UnderlyingListProps {
  selectedExchange: string;
  selectedUnderlying: string;
  onSelect: (underlying: Underlying) => void;
  onLoaded: (underlyings: Underlying[]) => void;
}

/**
 * A searchable list of underlyings with derivatives, index options first.
 * @param props The selected underlying, what choosing one does, and what to do with the first list loaded.
 * @returns The list.
 */
export function UnderlyingList(props: UnderlyingListProps) {
  const { selectedExchange, selectedUnderlying, onSelect, onLoaded } = props;
  const [typed, setTyped] = useState('');
  const [underlyings, setUnderlyings] = useState<Underlying[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      apiClient
        .fetchUnderlyings(typed, controller.signal)
        .then((loaded) => {
          setUnderlyings(loaded);
          setError('');
          if (typed === '') {
            onLoaded(loaded);
          }
        })
        .catch((caught: unknown) => {
          if (!controller.signal.aborted) {
            setError(caught instanceof ApiError ? caught.message : 'The underlyings could not be loaded.');
          }
        });
    }, TYPING_PAUSE_MILLISECONDS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [typed, onLoaded]);

  return (
    <aside className="underlying-list card">
      <input
        className="input"
        type="search"
        placeholder="Find an underlying"
        value={typed}
        onChange={(event) => setTyped(event.target.value)}
        aria-label="Find an underlying"
      />
      {error !== '' ? <p className="error-text">{error}</p> : null}
      <ul>
        {underlyings.map((underlying) => {
          const selected = underlying.exchange === selectedExchange && underlying.underlying_symbol === selectedUnderlying;
          return (
            <li key={`${underlying.exchange}-${underlying.underlying_symbol}`}>
              <button type="button" className={`underlying-option ${selected ? 'underlying-selected' : ''}`} onClick={() => onSelect(underlying)}>
                <span className="underlying-name">{underlying.underlying_symbol}</span>
                <span className={`exchange-tag exchange-${underlying.exchange}`}>{underlying.exchange.toUpperCase()}</span>
                <span className="underlying-detail muted">
                  {formatter.count(underlying.options)} options · {underlying.expiries} expiries
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
