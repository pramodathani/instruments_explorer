"""Tests for Black's model, implied volatility, the expiry clock and the option chain builder."""

import asyncio
import datetime
import math
from pathlib import Path
from typing import Any

import pytest

from instruments_explorer.derivatives import black_model
from instruments_explorer.derivatives import expiry_clock
from instruments_explorer.derivatives import option_chain_builder
from instruments_explorer.instruments import instrument_index_builder
from instruments_explorer.instruments import instrument_index_maintainer
from tests import fakes

_RATE = 0.065


class TestBlackModel:
    """Tests for BlackModel and ImpliedVolatilitySolver."""

    def test_put_call_parity(self) -> None:
        """Checks that call minus put equals the discounted forward minus strike."""
        model = black_model.BlackModel()
        call = model.price(23200.0, 23000.0, 0.05, 0.14, _RATE, 'CE')
        put = model.price(23200.0, 23000.0, 0.05, 0.14, _RATE, 'PE')
        expected = math.exp(-_RATE * 0.05) * (23200.0 - 23000.0)
        assert call - put == pytest.approx(expected)

    def test_at_the_money_price(self) -> None:
        """Checks the textbook approximation 0.4 * F * sigma * sqrt(T) at the money."""
        model = black_model.BlackModel()
        price = model.price(100.0, 100.0, 1.0, 0.2, 0.0, 'CE')
        assert price == pytest.approx(0.4 * 100.0 * 0.2, rel=0.01)

    @pytest.mark.parametrize(
        'volatility',
        [
            0.05,
            0.14,
            0.6,
            2.0,
        ],
    )
    def test_solver_recovers_the_volatility(self, volatility: float) -> None:
        """Checks that pricing and then solving gives the volatility back.

        Args:
            volatility (float): The volatility used to price.
        """
        model = black_model.BlackModel()
        solver = black_model.ImpliedVolatilitySolver(model)
        for option_type in [
            'CE',
            'PE',
        ]:
            price = model.price(
                23200.0,
                22800.0,
                0.1,
                volatility,
                _RATE,
                option_type,
            )
            solved = solver.solve(
                price,
                23200.0,
                22800.0,
                0.1,
                _RATE,
                option_type,
            )
            assert solved == pytest.approx(volatility, abs=1e-4)

    def test_solver_refuses_a_price_below_intrinsic_value(self) -> None:
        """Checks that a price no volatility can give has no answer."""
        solver = black_model.ImpliedVolatilitySolver(black_model.BlackModel())
        assert solver.solve(50.0, 23200.0, 23000.0, 0.05, _RATE, 'CE') is None
        assert solver.solve(10.0, 23200.0, 23000.0, 0.0, _RATE, 'CE') is None

    def test_greeks(self) -> None:
        """Checks the call and put deltas differ by the discount factor and share gamma and vega."""
        model = black_model.BlackModel()
        call = model.greeks(23200.0, 23000.0, 0.05, 0.14, _RATE, 'CE')
        put = model.greeks(23200.0, 23000.0, 0.05, 0.14, _RATE, 'PE')
        assert call['delta'] - put['delta'] == pytest.approx(
            math.exp(-_RATE * 0.05)
        )
        assert call['gamma'] == pytest.approx(put['gamma'])
        assert call['vega'] == pytest.approx(put['vega'])
        assert call['theta'] < 0


class TestExpiryClock:
    """Tests for ExpiryClock."""

    def test_years_until_the_close(self) -> None:
        """Checks that an expiry counts to 15:30 India time."""
        india = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        now = datetime.datetime(2026, 9, 28, 15, 30, tzinfo=india)
        clock = expiry_clock.ExpiryClock(fakes.FixedClock(now.timestamp()))
        assert clock.days_until('2026-09-29') == pytest.approx(1.0)
        assert clock.years_until('2026-09-28') == pytest.approx(0.0)


class ChainMaker:
    """Builds an option chain builder over the made-up catalogue with prepared quotes."""

    def quote(
        self,
        last_price: float,
        oi: int = 0,
        volume: int = 0,
        bid: float | None = None,
        offer: float | None = None,
    ) -> dict[str, Any]:
        """Writes one unified quote.

        Args:
            last_price (float): The last traded price.
            oi (int): The open interest.
            volume (int): The day's volume.
            bid (float | None): The best bid, or None.
            offer (float | None): The best offer, or None.

        Returns:
            dict[str, Any]: The quote.
        """
        buy = []
        sell = []
        if bid is not None:
            buy.append(
                {
                    'price': bid,
                    'quantity': 50,
                    'orders': 1,
                }
            )
        if offer is not None:
            sell.append(
                {
                    'price': offer,
                    'quantity': 50,
                    'orders': 1,
                }
            )
        return {
            'last_price': last_price,
            'oi': oi,
            'volume': volume,
            'depth': {
                'buy': buy,
                'sell': sell,
            },
            'received_at': 1.0,
        }

    def builder(
        self,
        directory: Path,
        quotes: dict[str, Any],
    ) -> option_chain_builder.OptionChainBuilder:
        """Builds the index and a chain builder over it.

        Args:
            directory (Path): Where to build the index.
            quotes (dict[str, Any]): Quotes by instrument id.

        Returns:
            option_chain_builder.OptionChainBuilder: The builder.
        """
        client = fakes.FakeCatalogueClient(fakes.CatalogueMaker().catalogue())
        time_source = fakes.FixedClock(fakes.TODAY_EPOCH)
        maintainer = instrument_index_maintainer.InstrumentIndexMaintainer(
            client,
            instrument_index_builder.InstrumentIndexBuilder(
                client,
                directory,
                time_source,
            ),
            time_source,
        )
        asyncio.run(maintainer.refresh())
        return option_chain_builder.OptionChainBuilder(
            maintainer,
            fakes.FakeSnapshotReader(quotes),
            time_source,
            _RATE,
        )


class TestOptionChainBuilder:
    """Tests for OptionChainBuilder."""

    def test_expiries(self, tmp_path: Path) -> None:
        """Checks the spot, futures and option expiries.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        maker = ChainMaker()
        builder = maker.builder(
            tmp_path,
            {
                fakes.NIFTY_ID: maker.quote(25010.0),
                'id-nifty-future': maker.quote(25060.0),
            },
        )
        description = asyncio.run(builder.expiries('nse', 'NIFTY'))
        assert description['spot']['last_price'] == 25010.0
        assert description['futures'][0]['last_price'] == 25060.0
        first = description['option_expiries'][0]
        assert first['expiry_date'] == '2026-09-29'
        assert first['contracts'] == 2
        assert first['strikes'] == 1
        assert first['days'] > 3

    def test_chain_uses_the_same_expiry_future(self, tmp_path: Path) -> None:
        """Checks the forward, the at-the-money strike, the ratio and implied volatility.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        maker = ChainMaker()
        builder = maker.builder(
            tmp_path,
            {
                fakes.NIFTY_ID: maker.quote(25010.0),
                'id-nifty-future': maker.quote(25060.0),
                'id-nifty-25000-ce': maker.quote(
                    160.0,
                    oi=1000,
                    volume=50,
                ),
                'id-nifty-25000-pe': maker.quote(
                    95.0,
                    oi=1500,
                    bid=94.0,
                    offer=96.0,
                ),
            },
        )
        chain = asyncio.run(builder.chain('nse', 'NIFTY', '2026-09-29'))
        assert chain['forward'] == 25060.0
        assert chain['forward_source'] == 'future'
        assert chain['atm_strike'] == 25000.0
        assert chain['put_call_ratio'] == 1.5
        row = chain['rows'][0]
        assert row['call']['iv'] is not None
        assert row['put']['iv'] is not None
        assert 0 < row['call']['delta'] < 1
        assert -1 < row['put']['delta'] < 0

    def test_untraded_contract_gets_no_volatility(self, tmp_path: Path) -> None:
        """Checks that an old last price with a wide spread is not trusted.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        maker = ChainMaker()
        builder = maker.builder(
            tmp_path,
            {
                'id-nifty-future': maker.quote(25060.0),
                'id-nifty-25000-ce': maker.quote(
                    400.0,
                    volume=0,
                    bid=50.0,
                    offer=300.0,
                ),
            },
        )
        chain = asyncio.run(builder.chain('nse', 'NIFTY', '2026-09-29'))
        call = chain['rows'][0]['call']
        assert call['last_price'] == 400.0
        assert call['iv'] is None

    def test_forward_from_spot_without_a_future(self, tmp_path: Path) -> None:
        """Checks that the spot is carried forward when the same-expiry future has no price.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        maker = ChainMaker()
        builder = maker.builder(
            tmp_path,
            {
                fakes.NIFTY_ID: maker.quote(25000.0),
            },
        )
        chain = asyncio.run(builder.chain('nse', 'NIFTY', '2026-10-27'))
        assert chain['forward_source'] == 'spot'
        assert chain['forward'] > 25000.0

    def test_max_pain(self, tmp_path: Path) -> None:
        """Checks the strike where option holders collect least.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        rows = [
            {
                'strike': 100.0,
                'call': {
                    'oi': 10,
                },
                'put': {
                    'oi': 500,
                },
            },
            {
                'strike': 110.0,
                'call': {
                    'oi': 300,
                },
                'put': {
                    'oi': 300,
                },
            },
            {
                'strike': 120.0,
                'call': {
                    'oi': 500,
                },
                'put': {
                    'oi': 10,
                },
            },
        ]
        builder = ChainMaker().builder(tmp_path, {})
        assert builder._max_pain(rows) == 110.0

    def test_interpolation_never_extrapolates(self, tmp_path: Path) -> None:
        """Checks straight-line interpolation inside the priced range only.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        builder = ChainMaker().builder(tmp_path, {})
        known = [
            (
                100.0,
                20.0,
            ),
            (
                120.0,
                10.0,
            ),
        ]
        assert builder._interpolate(known, 110.0) == 15.0
        assert builder._interpolate(known, 90.0) is None
        assert builder._interpolate(known, 130.0) is None

    def test_spikes_are_dropped(self, tmp_path: Path) -> None:
        """Checks that a lone outlier among smooth neighbours is removed.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        builder = ChainMaker().builder(tmp_path, {})
        known = []
        for position, value in enumerate(
            [
                12.0,
                11.5,
                11.0,
                30.0,
                11.2,
                11.6,
            ]
        ):
            known.append(
                (
                    100.0 + position,
                    value,
                )
            )
        strikes = []
        for strike, _ in builder._without_spikes(known):
            strikes.append(strike)
        assert 103.0 not in strikes
        assert len(strikes) == 5

    def test_unknown_underlying(self, tmp_path: Path) -> None:
        """Checks the error for an underlying without derivatives.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        builder = ChainMaker().builder(tmp_path, {})
        with pytest.raises(option_chain_builder.UnknownUnderlyingError):
            asyncio.run(builder.expiries('nse', 'NOBODY'))
