import type { ExpiryDescription } from '../api/types';
import { formatter } from '../utilities/formatter';

/** Props for ExpiryStrip. */
interface ExpiryStripProps {
  expiries: ExpiryDescription['option_expiries'];
  selected: string;
  onSelect: (expiry: string) => void;
}

/**
 * The option expiries as a scrolling row of buttons, each with its days left and contract count.
 * @param props The expiries, the selected one, and what choosing one does.
 * @returns The strip.
 */
export function ExpiryStrip(props: ExpiryStripProps) {
  const { expiries, selected, onSelect } = props;
  return (
    <div className="expiry-strip" role="tablist" aria-label="Expiries">
      {expiries.map((expiry) => (
        <button
          key={expiry.expiry_date}
          type="button"
          role="tab"
          aria-selected={expiry.expiry_date === selected}
          className={`expiry-button ${expiry.expiry_date === selected ? 'expiry-selected' : ''}`}
          onClick={() => onSelect(expiry.expiry_date)}
        >
          <span className="expiry-date">{formatter.date(expiry.expiry_date)}</span>
          <span className="expiry-detail">
            {expiry.days < 1 ? 'today' : `${Math.round(expiry.days)}d`} · {expiry.strikes} strikes
          </span>
        </button>
      ))}
    </div>
  );
}
