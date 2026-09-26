import { useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router';

import type { InstrumentRecord } from '../api/types';
import { formatter } from '../utilities/formatter';

/** Props for ResultsTable. */
interface ResultsTableProps {
  results: InstrumentRecord[];
  hasMore: boolean;
  loadingMore: boolean;
  onLoadMore: () => void;
}

/**
 * The search results, one instrument per row, loading the next page when the last row scrolls into view.
 * @param props The rows, whether more exist, whether they are loading, and what loads them.
 * @returns The table.
 */
export function ResultsTable(props: ResultsTableProps) {
  const { results, hasMore, loadingMore, onLoadMore } = props;
  const navigate = useNavigate();
  const sentinelReference = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const sentinel = sentinelReference.current;
    if (sentinel === null || !hasMore) {
      return undefined;
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries[0]?.isIntersecting && !loadingMore) {
        onLoadMore();
      }
    });
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loadingMore, onLoadMore]);

  return (
    <div className="results">
      <table className="data-table">
        <thead>
          <tr>
            <th>Instrument</th>
            <th>Exchange</th>
            <th>Segment</th>
            <th>Kind</th>
            <th>Expiry</th>
            <th className="numeric">Strike</th>
          </tr>
        </thead>
        <tbody>
          {results.map((result, position) => (
            <tr
              key={result.instrument_id}
              className="result-row"
              style={{ animationDelay: `${Math.min(position % 100, 24) * 18}ms` }}
              onClick={() => navigate(`/instrument/${result.instrument_id}`)}
            >
              <td>
                <Link to={`/instrument/${result.instrument_id}`} className="result-name" onClick={(event) => event.stopPropagation()}>
                  {result.display_name}
                </Link>
                {result.is_index && result.shape === 'security' ? <span className="chip chip-small">Index</span> : null}
                {result.company_name !== null ? <div className="result-company muted">{result.company_name}</div> : null}
              </td>
              <td>
                <span className={`exchange-tag exchange-${result.exchange}`}>{result.exchange.toUpperCase()}</span>
              </td>
              <td className="muted">{formatter.segment(result.bare_segment)}</td>
              <td>{formatter.shape(result.shape)}</td>
              <td className="mono">{formatter.date(result.expiry_date)}</td>
              <td className="numeric mono">
                {formatter.strike(result.strike_price)}
                {result.option_type !== null ? <span className={`option-type option-${result.option_type}`}>{result.option_type}</span> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div ref={sentinelReference} className="results-sentinel">
        {loadingMore ? 'Loading more…' : null}
      </div>
    </div>
  );
}
