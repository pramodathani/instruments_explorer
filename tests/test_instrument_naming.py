"""Tests for instrument names, asset classes and search words."""

from instruments_explorer.instruments import asset_classifier
from instruments_explorer.instruments import instrument_namer
from instruments_explorer.instruments import search_text_builder
from tests import fakes


class TestInstrumentNamer:
    """Tests for InstrumentNamer."""

    def test_security_is_its_symbol(self) -> None:
        """Checks a security's name."""
        namer = instrument_namer.InstrumentNamer()
        assert namer.name('security', 'INFY', None, None, None, None) == 'INFY'

    def test_future_name(self) -> None:
        """Checks a future's name."""
        namer = instrument_namer.InstrumentNamer()
        name = namer.name(
            'future',
            None,
            'CRUDEOIL',
            '2026-10-19',
            None,
            None,
        )
        assert name == 'CRUDEOIL 19 OCT 2026 FUT'

    def test_option_name_keeps_decimal_strikes(self) -> None:
        """Checks an option's name with a fractional strike."""
        namer = instrument_namer.InstrumentNamer()
        name = namer.name(
            'option',
            None,
            'USDINR',
            '2026-10-28',
            82.25,
            'PE',
        )
        assert name == 'USDINR 28 OCT 2026 82.25 PE'

    def test_expiry_label_leaves_bad_text_alone(self) -> None:
        """Checks that text that is not a date is returned unchanged."""
        namer = instrument_namer.InstrumentNamer()
        assert namer.expiry_label('someday') == 'someday'
        assert namer.expiry_label('2026-13-01') == '2026-13-01'


class TestAssetClassifier:
    """Tests for AssetClassifier."""

    def test_asset_classes(self) -> None:
        """Checks each family of segments."""
        classifier = asset_classifier.AssetClassifier()
        expected = {
            'equity_index_options': 'equity',
            'equities': 'equity',
            'exchange_traded_funds': 'funds',
            'investment_trusts': 'funds',
            'fixed_income_index_futures': 'fixed_income',
            'currency_options': 'currency',
            'commodity_futures': 'commodity',
            'uncategorised': 'other',
        }
        for bare_segment, asset_class in expected.items():
            assert classifier.asset_class(bare_segment) == asset_class

    def test_is_index(self) -> None:
        """Checks which segments are about indices."""
        classifier = asset_classifier.AssetClassifier()
        assert classifier.is_index('equity_indices')
        assert classifier.is_index('equity_index_options')
        assert not classifier.is_index('equities')
        assert not classifier.is_index('equity_options')

    def test_bare_segment(self) -> None:
        """Checks that only the exchange prefix is removed."""
        classifier = asset_classifier.AssetClassifier()
        assert classifier.bare_segment('nse', 'nse_equities') == 'equities'
        assert (
            classifier.bare_segment('unknown', 'uncategorised')
            == 'uncategorised'
        )


class TestSearchTextBuilder:
    """Tests for SearchTextBuilder."""

    def test_option_words(self) -> None:
        """Checks the words an option can be found by."""
        record = fakes.CatalogueMaker().identity(
            'id',
            'nse',
            'nse_equity_index_options',
            'option',
            underlying_symbol='NIFTY',
            expiry_date='2026-09-29',
            strike_price=25000.0,
            option_type='CE',
        )
        words = search_text_builder.SearchTextBuilder().build(record).split()
        for word in [
            'nifty',
            'nse',
            'option',
            '29',
            'sep',
            '2026',
            '29sep',
            'sep26',
            '25000',
            'ce',
            'call',
        ]:
            assert word in words
