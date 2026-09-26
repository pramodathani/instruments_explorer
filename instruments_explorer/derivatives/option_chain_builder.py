"""Builds an underlying's expiry list, option chains and volatility surface from the index and live quotes.

Typical usage example:

  builder = OptionChainBuilder(maintainer, snapshot_reader, clock, 0.065)
  expiries = await builder.expiries('nse', 'NIFTY')
  chain = await builder.chain('nse', 'NIFTY', '2026-09-29')
"""

import asyncio
import math
import statistics
from typing import Any

from instruments_explorer.derivatives import black_model
from instruments_explorer.derivatives import expiry_clock
from instruments_explorer.instruments import instrument_index_maintainer
from instruments_explorer.market import quote_snapshot_reader
from instruments_explorer.utilities import clock

MAXIMUM_SURFACE_EXPIRIES = 8
MAXIMUM_SURFACE_STRIKES = 31
SURFACE_WIDTH = 0.08
MINIMUM_SURFACE_POINTS = 5
SPIKE_NEIGHBOURS = 2
SPIKE_SHARE = 0.3
SPIKE_POINTS = 3.0


class UnknownUnderlyingError(ValueError):
    """The index has no futures or options for an underlying on an exchange."""


class OptionChainBuilder:
    """Assembles expiries, chains and surfaces for one underlying at a time.

    Attributes:
        rate: The yearly risk-free rate used for discounting, such as 0.065.
    """

    def __init__(
        self,
        maintainer: instrument_index_maintainer.InstrumentIndexMaintainer,
        snapshot_reader: quote_snapshot_reader.QuoteSnapshotReader,
        time_source: clock.SystemClock,
        rate: float,
    ):
        """Creates the builder.

        Args:
            maintainer (instrument_index_maintainer.InstrumentIndexMaintainer): Holds the instrument index.
            snapshot_reader (quote_snapshot_reader.QuoteSnapshotReader): Reads many live quotes at once.
            time_source (clock.SystemClock): The source of the current time.
            rate (float): The yearly risk-free rate used for discounting.
        """
        self.rate = rate
        self._maintainer = maintainer
        self._snapshot_reader = snapshot_reader
        self._clock = expiry_clock.ExpiryClock(time_source)
        self._model = black_model.BlackModel()
        self._solver = black_model.ImpliedVolatilitySolver(self._model)

    async def underlyings(self, text: str, limit: int) -> list[dict[str, Any]]:
        """Lists underlyings that have derivatives.

        Args:
            text (str): Typed text to match the start of the name.
            limit (int): The largest number of underlyings.

        Returns:
            list[dict[str, Any]]: As InstrumentIndex.derivative_underlyings returns them.

        Raises:
            LookupError: The instrument index is not ready.
        """
        index = self._index()
        return await asyncio.to_thread(
            index.derivative_underlyings,
            text,
            limit,
        )

    async def expiries(
        self,
        exchange: str,
        underlying_symbol: str,
    ) -> dict[str, Any]:
        """Describes an underlying: its cash instrument, its futures and its option expiries.

        Args:
            exchange (str): The exchange.
            underlying_symbol (str): The underlying.

        Returns:
            dict[str, Any]: "exchange", "underlying_symbol", "spot" (the cash instrument with its last price, or None), "futures" (each with its last price) and "option_expiries" (each with its contract and strike counts and days left).

        Raises:
            LookupError: The instrument index is not ready.
            UnknownUnderlyingError: The underlying has no derivatives on the exchange.
        """
        spot, contracts = await self._load(exchange, underlying_symbol)
        futures = self._futures(contracts)
        wanted = []
        for future in futures:
            wanted.append(future['instrument_id'])
        if spot is not None:
            wanted.append(spot['instrument_id'])
        quotes = await self._snapshot_reader.read(wanted)
        future_rows = []
        for future in futures:
            future_rows.append(
                {
                    'instrument_id': future['instrument_id'],
                    'display_name': future['display_name'],
                    'expiry_date': future['expiry_date'],
                    'last_price': self._last_price(
                        quotes.get(future['instrument_id'])
                    ),
                }
            )
        counts = {}
        strikes = {}
        for contract in contracts:
            if contract['shape'] != 'option':
                continue
            expiry_date = contract['expiry_date']
            counts[expiry_date] = counts.get(expiry_date, 0) + 1
            strikes.setdefault(expiry_date, set()).add(contract['strike_price'])
        option_expiries = []
        for expiry_date in sorted(counts):
            option_expiries.append(
                {
                    'expiry_date': expiry_date,
                    'contracts': counts[expiry_date],
                    'strikes': len(strikes[expiry_date]),
                    'days': round(self._clock.days_until(expiry_date), 2),
                }
            )
        return {
            'exchange': exchange,
            'underlying_symbol': underlying_symbol,
            'spot': self._spot_row(spot, quotes),
            'futures': future_rows,
            'option_expiries': option_expiries,
        }

    async def chain(
        self,
        exchange: str,
        underlying_symbol: str,
        expiry_date: str,
    ) -> dict[str, Any]:
        """Builds one expiry's option chain with prices, open interest, implied volatility and Greeks.

        Args:
            exchange (str): The exchange.
            underlying_symbol (str): The underlying.
            expiry_date (str): The expiry as "YYYY-MM-DD".

        Returns:
            dict[str, Any]: "expiry_date", "days", "rate", "spot", "forward", "forward_source", "atm_strike", "max_pain", "put_call_ratio", "total_call_oi", "total_put_oi" and "rows", one per strike with "strike", "call" and "put".

        Raises:
            LookupError: The instrument index is not ready.
            UnknownUnderlyingError: The underlying has no options for that expiry on the exchange.
        """
        spot, contracts = await self._load(exchange, underlying_symbol)
        options = []
        for contract in contracts:
            if (
                contract['shape'] == 'option'
                and contract['expiry_date'] == expiry_date
            ):
                options.append(contract)
        if not options:
            raise UnknownUnderlyingError(
                f'No {underlying_symbol} options expire on {expiry_date} on {exchange}.'
            )
        wanted = []
        for option in options:
            wanted.append(option['instrument_id'])
        futures = self._futures(contracts)
        for future in futures:
            wanted.append(future['instrument_id'])
        if spot is not None:
            wanted.append(spot['instrument_id'])
        quotes = await self._snapshot_reader.read(wanted)
        years = self._clock.years_until(expiry_date)
        forward, forward_source = self._forward(
            spot,
            futures,
            quotes,
            expiry_date,
            years,
        )
        rows_by_strike = {}
        for option in options:
            strike = option['strike_price']
            row = rows_by_strike.setdefault(
                strike,
                {
                    'strike': strike,
                    'call': None,
                    'put': None,
                },
            )
            side = self._side(
                option,
                quotes.get(option['instrument_id']),
                forward,
                years,
            )
            if option['option_type'] == 'CE':
                row['call'] = side
            else:
                row['put'] = side
        rows = []
        for strike in sorted(rows_by_strike):
            rows.append(rows_by_strike[strike])
        total_call_oi = 0
        total_put_oi = 0
        for row in rows:
            total_call_oi += self._open_interest(row['call'])
            total_put_oi += self._open_interest(row['put'])
        put_call_ratio = None
        if total_call_oi > 0:
            put_call_ratio = round(total_put_oi / total_call_oi, 4)
        return {
            'exchange': exchange,
            'underlying_symbol': underlying_symbol,
            'expiry_date': expiry_date,
            'days': round(years * 365.0, 2),
            'rate': self.rate,
            'spot': self._spot_row(spot, quotes),
            'forward': forward,
            'forward_source': forward_source,
            'atm_strike': self._atm_strike(rows, forward),
            'max_pain': self._max_pain(rows),
            'put_call_ratio': put_call_ratio,
            'total_call_oi': total_call_oi,
            'total_put_oi': total_put_oi,
            'rows': rows,
        }

    async def surface(
        self,
        exchange: str,
        underlying_symbol: str,
    ) -> dict[str, Any]:
        """Builds the implied volatility of strikes around the money across the nearest expiries.

        Each point uses the out-of-the-money option, a put below the forward and a call above it, because those trade most and their prices are least distorted. The strikes come from the nearest expiry within SURFACE_WIDTH of its forward; an expiry that does not list a strike, or has no price there, gets a value interpolated between its nearest priced strikes, never extrapolated. Expiries with fewer than MINIMUM_SURFACE_POINTS priced strikes in range are left out.

        Args:
            exchange (str): The exchange.
            underlying_symbol (str): The underlying.

        Returns:
            dict[str, Any]: "expiries" (each with "expiry_date", "days" and "forward"), "strikes" (in ascending order) and "volatility", one row per expiry with one value per strike, in percent or None.

        Raises:
            LookupError: The instrument index is not ready.
            UnknownUnderlyingError: The underlying has no derivatives on the exchange.
        """
        description = await self.expiries(exchange, underlying_symbol)
        expiry_dates = []
        for entry in description['option_expiries']:
            if entry['days'] > 0:
                expiry_dates.append(entry['expiry_date'])
        chains = []
        for expiry_date in expiry_dates[: MAXIMUM_SURFACE_EXPIRIES * 2]:
            chains.append(
                await self.chain(exchange, underlying_symbol, expiry_date)
            )
        strikes = self._surface_strikes(chains)
        expiries = []
        volatility = []
        for chain in chains:
            if len(expiries) >= MAXIMUM_SURFACE_EXPIRIES:
                break
            known = self._known_volatility(chain, strikes)
            if len(known) < MINIMUM_SURFACE_POINTS:
                continue
            values = []
            for strike in strikes:
                values.append(self._interpolate(known, strike))
            expiries.append(
                {
                    'expiry_date': chain['expiry_date'],
                    'days': chain['days'],
                    'forward': chain['forward'],
                }
            )
            volatility.append(values)
        return {
            'exchange': exchange,
            'underlying_symbol': underlying_symbol,
            'expiries': expiries,
            'strikes': strikes,
            'volatility': volatility,
        }

    def _index(self) -> Any:
        """Finds the current instrument index.

        Returns:
            Any: The InstrumentIndex.

        Raises:
            LookupError: The index is not ready.
        """
        index = self._maintainer.current_index
        if index is None:
            raise LookupError('The instrument index is not ready yet.')
        return index

    async def _load(
        self,
        exchange: str,
        underlying_symbol: str,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """Reads an underlying's cash instrument and derivatives from the index.

        Args:
            exchange (str): The exchange.
            underlying_symbol (str): The underlying.

        Returns:
            tuple[dict[str, Any] | None, list[dict[str, Any]]]: A tuple (the cash instrument or None, every future and option).

        Raises:
            LookupError: The index is not ready.
            UnknownUnderlyingError: The underlying has no derivatives on the exchange.
        """
        index = self._index()
        contracts = await asyncio.to_thread(
            index.derivative_contracts,
            exchange,
            underlying_symbol,
        )
        if not contracts:
            raise UnknownUnderlyingError(
                f'No futures or options on {underlying_symbol} are listed on {exchange}.'
            )
        spot = await asyncio.to_thread(
            index.underlying_security,
            exchange,
            underlying_symbol,
        )
        return spot, contracts

    def _futures(self, contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Picks the futures out of an underlying's contracts.

        Args:
            contracts (list[dict[str, Any]]): Every future and option.

        Returns:
            list[dict[str, Any]]: The futures, nearest expiry first.
        """
        futures = []
        for contract in contracts:
            if contract['shape'] == 'future':
                futures.append(contract)
        return futures

    def _spot_row(
        self,
        spot: dict[str, Any] | None,
        quotes: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Describes the cash instrument with its latest price.

        Args:
            spot (dict[str, Any] | None): The cash instrument, or None.
            quotes (dict[str, Any]): Live quotes by instrument id.

        Returns:
            dict[str, Any] | None: "instrument_id", "display_name", "last_price" and "change_percent", or None without a cash instrument.
        """
        if spot is None:
            return None
        quote = quotes.get(spot['instrument_id']) or {}
        return {
            'instrument_id': spot['instrument_id'],
            'display_name': spot['display_name'],
            'last_price': self._last_price(quote),
            'change_percent': quote.get('change_percent'),
        }

    def _forward(
        self,
        spot: dict[str, Any] | None,
        futures: list[dict[str, Any]],
        quotes: dict[str, Any],
        expiry_date: str,
        years: float,
    ) -> tuple[float | None, str | None]:
        """Chooses the forward price for an expiry.

        The future of the same expiry is the market's own forward. Without one, the cash price is carried forward at the risk-free rate, and without that, the nearest priced future is used as it is.

        Args:
            spot (dict[str, Any] | None): The cash instrument, or None.
            futures (list[dict[str, Any]]): The underlying's futures.
            quotes (dict[str, Any]): Live quotes by instrument id.
            expiry_date (str): The option expiry.
            years (float): The years left until that expiry.

        Returns:
            tuple[float | None, str | None]: A tuple (the forward price, and "future", "spot" or "nearest_future"), or (None, None) when nothing is priced.
        """
        for future in futures:
            if future['expiry_date'] == expiry_date:
                price = self._last_price(quotes.get(future['instrument_id']))
                if price is not None:
                    return price, 'future'
        if spot is not None:
            price = self._last_price(quotes.get(spot['instrument_id']))
            if price is not None:
                return price * math.exp(self.rate * max(years, 0.0)), 'spot'
        for future in futures:
            price = self._last_price(quotes.get(future['instrument_id']))
            if price is not None:
                return price, 'nearest_future'
        return None, None

    def _side(
        self,
        option: dict[str, Any],
        quote: dict[str, Any] | None,
        forward: float | None,
        years: float,
    ) -> dict[str, Any]:
        """Describes one call or put of a chain row.

        Args:
            option (dict[str, Any]): The option contract.
            quote (dict[str, Any] | None): Its live quote, or None.
            forward (float | None): The forward price, or None.
            years (float): The years left until expiry.

        Returns:
            dict[str, Any]: The instrument id, prices, change, open interest, volume, best bid and offer, "iv" in percent and the Greeks, with None where unknown.
        """
        quote = quote or {}
        depth = quote.get('depth') or {}
        bids = depth.get('buy') or []
        offers = depth.get('sell') or []
        bid = bids[0].get('price') if bids else None
        offer = offers[0].get('price') if offers else None
        last_price = self._last_price(quote)
        side = {
            'instrument_id': option['instrument_id'],
            'last_price': last_price,
            'change_percent': quote.get('change_percent'),
            'oi': quote.get('oi'),
            'volume': quote.get('volume'),
            'bid': bid,
            'offer': offer,
            'received_at': quote.get('received_at'),
            'iv': None,
            'delta': None,
            'gamma': None,
            'theta': None,
            'vega': None,
        }
        price = self._fair_price(last_price, bid, offer, quote.get('volume'))
        if forward is None or price is None or years <= 0:
            return side
        volatility = self._solver.solve(
            price,
            forward,
            option['strike_price'],
            years,
            self.rate,
            option['option_type'],
        )
        if volatility is None:
            return side
        greeks = self._model.greeks(
            forward,
            option['strike_price'],
            years,
            volatility,
            self.rate,
            option['option_type'],
        )
        side['iv'] = round(volatility * 100.0, 2)
        side['delta'] = round(greeks['delta'], 4)
        side['gamma'] = round(greeks['gamma'], 6)
        side['theta'] = round(greeks['theta'], 4)
        side['vega'] = round(greeks['vega'], 4)
        return side

    def _fair_price(
        self,
        last_price: float | None,
        bid: float | None,
        offer: float | None,
        volume: int | None,
    ) -> float | None:
        """Chooses the price implied volatility is worked out from, or none when no price can be trusted.

        The middle of a tight best bid and offer reflects the market now. Otherwise the last trade is used, but only when the contract traded today: an untraded contract's "last price" is the close of the last day it traded, which can be far from today's value and would show as a false jump in volatility.

        Args:
            last_price (float | None): The last traded price.
            bid (float | None): The best bid.
            offer (float | None): The best offer.
            volume (int | None): The day's traded volume.

        Returns:
            float | None: The mid price when both sides are quoted and the offer is at most twice the bid, otherwise the last price when the contract traded today, otherwise None.
        """
        if bid and offer and offer >= bid and offer <= bid * 2:
            return (bid + offer) / 2.0
        if volume:
            return last_price
        return None

    def _last_price(self, quote: dict[str, Any] | None) -> float | None:
        """Reads a quote's last price.

        Args:
            quote (dict[str, Any] | None): The quote, or None.

        Returns:
            float | None: The last price when it is above zero, otherwise None.
        """
        if not quote:
            return None
        price = quote.get('last_price')
        if price is None or price <= 0:
            return None
        return float(price)

    def _open_interest(self, side: dict[str, Any] | None) -> int:
        """Reads one side's open interest.

        Args:
            side (dict[str, Any] | None): A call or put of a chain row, or None.

        Returns:
            int: The open interest, zero when unknown.
        """
        if side is None or side['oi'] is None:
            return 0
        return int(side['oi'])

    def _atm_strike(
        self,
        rows: list[dict[str, Any]],
        forward: float | None,
    ) -> float | None:
        """Finds the strike nearest the forward.

        Args:
            rows (list[dict[str, Any]]): The chain rows.
            forward (float | None): The forward price, or None.

        Returns:
            float | None: The at-the-money strike, or None without a forward.
        """
        if forward is None or not rows:
            return None
        nearest = rows[0]['strike']
        for row in rows:
            if abs(row['strike'] - forward) < abs(nearest - forward):
                nearest = row['strike']
        return nearest

    def _max_pain(self, rows: list[dict[str, Any]]) -> float | None:
        """Finds the expiry price at which option holders would collect the least in total.

        Args:
            rows (list[dict[str, Any]]): The chain rows.

        Returns:
            float | None: The strike with the smallest total payout to call and put holders, or None when no open interest is known.
        """
        best_strike = None
        best_payout = None
        has_open_interest = False
        for candidate in rows:
            settlement = candidate['strike']
            payout = 0.0
            for row in rows:
                call_interest = self._open_interest(row['call'])
                put_interest = self._open_interest(row['put'])
                if call_interest or put_interest:
                    has_open_interest = True
                payout += call_interest * max(0.0, settlement - row['strike'])
                payout += put_interest * max(0.0, row['strike'] - settlement)
            if best_payout is None or payout < best_payout:
                best_payout = payout
                best_strike = settlement
        if not has_open_interest:
            return None
        return best_strike

    def _surface_strikes(self, chains: list[dict[str, Any]]) -> list[float]:
        """Picks the surface's strikes from the nearest expiry that has a forward price.

        Args:
            chains (list[dict[str, Any]]): The chains, nearest expiry first.

        Returns:
            list[float]: The strikes within SURFACE_WIDTH of that expiry's forward, thinned evenly to at most MAXIMUM_SURFACE_STRIKES, ascending.
        """
        for chain in chains:
            forward = chain['forward']
            if forward is None:
                continue
            nearby = []
            for row in chain['rows']:
                if abs(row['strike'] - forward) <= forward * SURFACE_WIDTH:
                    nearby.append(row['strike'])
            if len(nearby) <= MAXIMUM_SURFACE_STRIKES:
                return nearby
            step = (len(nearby) - 1) / (MAXIMUM_SURFACE_STRIKES - 1)
            thinned = []
            for position in range(MAXIMUM_SURFACE_STRIKES):
                thinned.append(nearby[round(position * step)])
            return thinned
        return []

    def _known_volatility(
        self,
        chain: dict[str, Any],
        strikes: list[float],
    ) -> list[tuple[float, float]]:
        """Collects a chain's priced strikes that fall within the surface's strike range.

        Args:
            chain (dict[str, Any]): One expiry's chain.
            strikes (list[float]): The surface's strikes, ascending.

        Returns:
            list[tuple[float, float]]: A list of tuples (strike, implied volatility in percent), ascending by strike.
        """
        if not strikes:
            return []
        known = []
        for row in chain['rows']:
            if row['strike'] < strikes[0] or row['strike'] > strikes[-1]:
                continue
            value = self._out_of_money_volatility(row, chain['forward'])
            if value is not None:
                known.append(
                    (
                        row['strike'],
                        value,
                    )
                )
        return self._without_spikes(known)

    def _without_spikes(
        self,
        known: list[tuple[float, float]],
    ) -> list[tuple[float, float]]:
        """Drops volatilities that stand far apart from their neighbours.

        A quiet strike's last trade can be hours or days old, and its implied volatility then shows as a spike that says nothing about the market. A point is dropped when it differs from the median of its nearest 2 * SPIKE_NEIGHBOURS points by more than SPIKE_SHARE of that median or SPIKE_POINTS, whichever is larger. At the ends of the row the window slides inward rather than shrinking, so a spike next to the last strike cannot drag the last strike out with it.

        Args:
            known (list[tuple[float, float]]): Priced strikes and volatilities, ascending.

        Returns:
            list[tuple[float, float]]: The points that are not spikes, ascending.
        """
        kept = []
        for position, (strike, value) in enumerate(known):
            neighbours = []
            window = SPIKE_NEIGHBOURS * 2 + 1
            first = max(
                0, min(position - SPIKE_NEIGHBOURS, len(known) - window)
            )
            last = min(len(known), first + window)
            for other in range(first, last):
                if other != position:
                    neighbours.append(known[other][1])
            if len(neighbours) < 2:
                kept.append((strike, value))
                continue
            median = statistics.median(neighbours)
            allowed = max(median * SPIKE_SHARE, SPIKE_POINTS)
            if abs(value - median) <= allowed:
                kept.append((strike, value))
        return kept

    def _interpolate(
        self,
        known: list[tuple[float, float]],
        strike: float,
    ) -> float | None:
        """Reads a volatility at a strike, interpolating in a straight line between the nearest priced strikes.

        Args:
            known (list[tuple[float, float]]): Priced strikes and volatilities, ascending.
            strike (float): The strike wanted.

        Returns:
            float | None: The volatility in percent, or None outside the priced range.
        """
        for position, (known_strike, value) in enumerate(known):
            if known_strike == strike:
                return value
            if known_strike > strike:
                if position == 0:
                    return None
                lower_strike, lower_value = known[position - 1]
                share = (strike - lower_strike) / (known_strike - lower_strike)
                return round(lower_value + share * (value - lower_value), 2)
        return None

    def _out_of_money_volatility(
        self,
        row: dict[str, Any] | None,
        forward: float | None,
    ) -> float | None:
        """Takes a strike's implied volatility from its out-of-the-money option, falling back to the other side.

        Args:
            row (dict[str, Any] | None): The chain row at the strike, or None.
            forward (float | None): The forward price, or None.

        Returns:
            float | None: The implied volatility in percent, or None when neither side has one.
        """
        if row is None:
            return None
        call_volatility = row['call']['iv'] if row['call'] else None
        put_volatility = row['put']['iv'] if row['put'] else None
        if forward is not None and row['strike'] >= forward:
            preferred = call_volatility
            other = put_volatility
        else:
            preferred = put_volatility
            other = call_volatility
        if preferred is not None:
            return preferred
        return other
