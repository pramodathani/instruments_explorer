import type { DepthLevel, Quote } from '../api/types';
import { TiltCard } from '../components/TiltCard';
import { formatter } from '../utilities/formatter';

const LEVELS = 5;

/** Props for DepthTable. */
interface DepthTableProps {
  quote: Quote | undefined;
}

/**
 * The five best bids and offers side by side, each with a bar showing its quantity.
 * @param props The quote holding the depth.
 * @returns The table.
 */
export function DepthTable(props: DepthTableProps) {
  const { quote } = props;
  const buy = quote?.depth.buy ?? [];
  const sell = quote?.depth.sell ?? [];
  let largest = 1;
  for (const level of [...buy, ...sell]) {
    largest = Math.max(largest, level.quantity);
  }
  const rows: [DepthLevel | undefined, DepthLevel | undefined][] = [];
  for (let index = 0; index < LEVELS; index += 1) {
    rows.push([buy[index], sell[index]]);
  }
  return (
    <TiltCard className="depth-card">
      <div className="tilt-lift">
        <h2>Market depth</h2>
        <table className="depth-table">
          <thead>
            <tr>
              <th>Orders</th>
              <th className="numeric">Bid qty</th>
              <th className="numeric">Bid</th>
              <th className="numeric">Offer</th>
              <th className="numeric">Offer qty</th>
              <th className="numeric">Orders</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([bid, offer], index) => (
              <tr key={index}>
                <td className="mono muted">{bid?.orders ?? ''}</td>
                <td className="numeric mono depth-bid">
                  {bid === undefined ? '' : formatter.count(bid.quantity)}
                  {bid === undefined ? null : <span className="depth-bar depth-bar-bid" style={{ width: `${(bid.quantity / largest) * 100}%` }} />}
                </td>
                <td className="numeric mono change-up">{bid === undefined ? '' : formatter.price(bid.price)}</td>
                <td className="numeric mono change-down">{offer === undefined ? '' : formatter.price(offer.price)}</td>
                <td className="numeric mono depth-offer">
                  {offer === undefined ? '' : formatter.count(offer.quantity)}
                  {offer === undefined ? null : <span className="depth-bar depth-bar-offer" style={{ width: `${(offer.quantity / largest) * 100}%` }} />}
                </td>
                <td className="numeric mono muted">{offer?.orders ?? ''}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={2} className="numeric mono">
                {formatter.count(quote?.buy_quantity)}
              </td>
              <td colSpan={2} className="numeric muted">
                Total quantity
              </td>
              <td colSpan={2} className="numeric mono">
                {formatter.count(quote?.sell_quantity)}
              </td>
            </tr>
          </tfoot>
        </table>
        {buy.length === 0 && sell.length === 0 ? <p className="muted">No depth in this quote.</p> : null}
      </div>
    </TiltCard>
  );
}
