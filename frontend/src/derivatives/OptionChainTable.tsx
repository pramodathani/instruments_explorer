import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';

import type { ChainRow, ChainSide, OptionChain } from '../api/types';
import { formatter } from '../utilities/formatter';

/** Props for OptionChainTable. */
interface OptionChainTableProps {
  chain: OptionChain;
  rows: ChainRow[];
}

/**
 * The option chain: calls on the left, strikes in the middle, puts on the right, with open interest bars and in-the-money shading.
 * @param props The chain and the rows to show.
 * @returns The table.
 */
export function OptionChainTable(props: OptionChainTableProps) {
  const { chain, rows } = props;
  const navigate = useNavigate();
  const atmReference = useRef<HTMLTableRowElement>(null);
  let largestOi = 1;
  for (const row of rows) {
    largestOi = Math.max(largestOi, row.call?.oi ?? 0, row.put?.oi ?? 0);
  }

  useEffect(() => {
    atmReference.current?.scrollIntoView({
      block: 'center',
      behavior: 'smooth',
    });
  }, [chain.underlying_symbol, chain.expiry_date]);

  const open = (side: ChainSide | null) => {
    if (side !== null) {
      navigate(`/instrument/${side.instrument_id}`);
    }
  };

  const forward = chain.forward;

  return (
    <div className="chain-scroller">
      <table className="chain-table">
        <thead>
          <tr>
            <th colSpan={6} className="chain-side-title">
              Calls
            </th>
            <th />
            <th colSpan={6} className="chain-side-title">
              Puts
            </th>
          </tr>
          <tr>
            <th className="numeric">OI</th>
            <th className="numeric">Volume</th>
            <th className="numeric">IV</th>
            <th className="numeric">Delta</th>
            <th className="numeric">Chg %</th>
            <th className="numeric">LTP</th>
            <th className="chain-strike-heading">Strike</th>
            <th className="numeric">LTP</th>
            <th className="numeric">Chg %</th>
            <th className="numeric">Delta</th>
            <th className="numeric">IV</th>
            <th className="numeric">Volume</th>
            <th className="numeric">OI</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const atm = row.strike === chain.atm_strike;
            const callInMoney = forward !== null && row.strike < forward;
            const putInMoney = forward !== null && row.strike > forward;
            return (
              <tr key={row.strike} ref={atm ? atmReference : undefined} className={atm ? 'chain-atm' : ''}>
                <td className={`numeric chain-oi ${callInMoney ? 'chain-itm' : ''}`}>
                  <span className="chain-oi-bar chain-oi-call" style={{ width: `${((row.call?.oi ?? 0) / largestOi) * 100}%` }} />
                  {formatter.count(row.call?.oi)}
                </td>
                <td className={`numeric muted ${callInMoney ? 'chain-itm' : ''}`}>{formatter.count(row.call?.volume)}</td>
                <td className={`numeric ${callInMoney ? 'chain-itm' : ''}`}>{formatter.volatility(row.call?.iv)}</td>
                <td className={`numeric muted ${callInMoney ? 'chain-itm' : ''}`}>{row.call?.delta?.toFixed(2) ?? '–'}</td>
                <td className={`numeric ${formatter.changeClass(row.call?.change_percent)} ${callInMoney ? 'chain-itm' : ''}`}>{formatter.signedPercent(row.call?.change_percent)}</td>
                <td className={`numeric chain-price ${callInMoney ? 'chain-itm' : ''}`} onClick={() => open(row.call)}>
                  {formatter.price(row.call?.last_price)}
                </td>
                <td className="chain-strike">{formatter.strike(row.strike)}</td>
                <td className={`numeric chain-price ${putInMoney ? 'chain-itm' : ''}`} onClick={() => open(row.put)}>
                  {formatter.price(row.put?.last_price)}
                </td>
                <td className={`numeric ${formatter.changeClass(row.put?.change_percent)} ${putInMoney ? 'chain-itm' : ''}`}>{formatter.signedPercent(row.put?.change_percent)}</td>
                <td className={`numeric muted ${putInMoney ? 'chain-itm' : ''}`}>{row.put?.delta?.toFixed(2) ?? '–'}</td>
                <td className={`numeric ${putInMoney ? 'chain-itm' : ''}`}>{formatter.volatility(row.put?.iv)}</td>
                <td className={`numeric muted ${putInMoney ? 'chain-itm' : ''}`}>{formatter.count(row.put?.volume)}</td>
                <td className={`numeric chain-oi ${putInMoney ? 'chain-itm' : ''}`}>
                  <span className="chain-oi-bar chain-oi-put" style={{ width: `${((row.put?.oi ?? 0) / largestOi) * 100}%` }} />
                  {formatter.count(row.put?.oi)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

