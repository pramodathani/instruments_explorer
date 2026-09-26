"""Tests for building, searching and maintaining the instrument index."""

import asyncio
from pathlib import Path

import pytest

from instruments_explorer.instruments import instrument_index
from instruments_explorer.instruments import instrument_index_builder
from instruments_explorer.instruments import instrument_index_maintainer
from tests import fakes


class IndexMaker:
    """Builds a real index file from the made-up catalogue."""

    def build(
        self,
        directory: Path,
    ) -> tuple[instrument_index.InstrumentIndex, fakes.FakeCatalogueClient]:
        """Builds and opens an index.

        Args:
            directory (Path): Where to write the index file.

        Returns:
            tuple[instrument_index.InstrumentIndex, fakes.FakeCatalogueClient]: A tuple (the opened index, the client it was built from).
        """
        client = fakes.FakeCatalogueClient(fakes.CatalogueMaker().catalogue())
        builder = instrument_index_builder.InstrumentIndexBuilder(
            client,
            directory,
            fakes.FixedClock(fakes.TODAY_EPOCH),
        )
        path, _ = asyncio.run(builder.build())
        return instrument_index.InstrumentIndex.open(path), client


class TestInstrumentIndexBuilder:
    """Tests for InstrumentIndexBuilder."""

    def test_build_leaves_out_expired_instruments(self, tmp_path: Path) -> None:
        """Checks the count and that the expired option is not stored.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        index, _ = IndexMaker().build(tmp_path)
        assert index.instrument_count == 10
        assert index.mapping_date == '2026-09-25'
        assert index.instrument('id-nifty-expired') is None

    def test_build_names_and_classifies(self, tmp_path: Path) -> None:
        """Checks the stored name, asset class and index flag.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        index, _ = IndexMaker().build(tmp_path)
        option = index.instrument('id-nifty-25000-ce')
        assert option['display_name'] == 'NIFTY 29 SEP 2026 25000 CE'
        assert option['asset_class'] == 'equity'
        assert option['is_index'] is True
        assert option['bare_segment'] == 'equity_index_options'
        gold = index.instrument('id-gold-future')
        assert gold['display_name'] == 'GOLD 05 OCT 2026 FUT'
        assert gold['asset_class'] == 'commodity'
        assert index.instrument('id-niftybees')['asset_class'] == 'funds'

    def test_build_renames_the_file_into_place(self, tmp_path: Path) -> None:
        """Checks that only the finished file is left.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        IndexMaker().build(tmp_path)
        names = []
        for path in tmp_path.iterdir():
            names.append(path.name)
        assert names == [
            'instruments-2026-09-25.sqlite',
        ]


class TestInstrumentIndex:
    """Tests for InstrumentIndex searches."""

    def _names(self, page: dict) -> list[str]:
        """Lists the display names of a page of results.

        Args:
            page (dict): The search answer.

        Returns:
            list[str]: The names, in result order.
        """
        names = []
        for result in page['results']:
            names.append(result['display_name'])
        return names

    def test_exact_name_comes_first(self, tmp_path: Path) -> None:
        """Checks that the index itself comes before its derivatives and similar names.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        index, _ = IndexMaker().build(tmp_path)
        page = index.search(instrument_index.SearchRequest(text='nifty'))
        names = self._names(page)
        assert names[0] == 'NIFTY'
        assert names.index('NIFTY 29 SEP 2026 FUT') < names.index(
            'NIFTY 29 SEP 2026 25000 CE'
        )
        assert names.index('NIFTY 29 SEP 2026 25000 CE') < names.index(
            'NIFTYBEES'
        )
        assert page['total'] == 6

    def test_words_find_one_contract(self, tmp_path: Path) -> None:
        """Checks that expiry, strike and option words narrow to one contract.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        index, _ = IndexMaker().build(tmp_path)
        page = index.search(
            instrument_index.SearchRequest(text='nifty sep 25000 call')
        )
        assert self._names(page) == [
            'NIFTY 29 SEP 2026 25000 CE',
        ]

    def test_filters_combine(self, tmp_path: Path) -> None:
        """Checks that values of one filter widen and different filters narrow.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        index, _ = IndexMaker().build(tmp_path)
        request = instrument_index.SearchRequest(
            filters={
                'shape': [
                    'future',
                ],
                'exchange': [
                    'nse',
                    'mcx',
                ],
            },
            sort='name',
        )
        assert self._names(index.search(request)) == [
            'GOLD 05 OCT 2026 FUT',
            'NIFTY 29 SEP 2026 FUT',
            'RELIANCE 27 OCT 2026 FUT',
        ]

    def test_facet_ignores_its_own_filter(self, tmp_path: Path) -> None:
        """Checks that a facet's counts are taken without its own filter but with the others.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        index, _ = IndexMaker().build(tmp_path)
        request = instrument_index.SearchRequest(
            filters={
                'shape': [
                    'future',
                ],
                'exchange': [
                    'mcx',
                ],
            },
        )
        facets = index.search(request)['facets']
        shape_counts = {}
        for entry in facets['shape']:
            shape_counts[entry['value']] = entry['count']
        assert shape_counts == {
            'future': 1,
        }
        exchange_counts = {}
        for entry in facets['exchange']:
            exchange_counts[entry['value']] = entry['count']
        assert exchange_counts == {
            'nse': 2,
            'mcx': 1,
        }

    def test_expiry_months_are_in_date_order(self, tmp_path: Path) -> None:
        """Checks the expiry month facet's order.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        index, _ = IndexMaker().build(tmp_path)
        facets = index.facets(instrument_index.SearchRequest())
        months = []
        for entry in facets['expiry_month']:
            months.append(entry['value'])
        assert months == [
            '2026-09',
            '2026-10',
        ]

    def test_strike_range(self, tmp_path: Path) -> None:
        """Checks that the strike range keeps only options within it.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        index, _ = IndexMaker().build(tmp_path)
        request = instrument_index.SearchRequest(
            strike_minimum=25500,
            strike_maximum=30000,
        )
        assert self._names(index.search(request)) == [
            'NIFTY 27 OCT 2026 26000 CE',
        ]

    def test_paging(self, tmp_path: Path) -> None:
        """Checks that limit and offset page through the results.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        index, _ = IndexMaker().build(tmp_path)
        first = index.search(
            instrument_index.SearchRequest(sort='name', limit=4)
        )
        second = index.search(
            instrument_index.SearchRequest(sort='name', limit=4, offset=4)
        )
        assert first['total'] == 10
        assert len(first['results']) == 4
        assert set(self._names(first)).isdisjoint(self._names(second))

    def test_punctuation_cannot_break_the_search(self, tmp_path: Path) -> None:
        """Checks that quotes and operators are ignored.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        index, _ = IndexMaker().build(tmp_path)
        page = index.search(instrument_index.SearchRequest(text='"gold" (*'))
        assert 'GOLD 05 OCT 2026 FUT' in self._names(page)

    def test_request_refuses_an_unknown_filter(self) -> None:
        """Checks that a filter column outside the facet list is refused."""
        with pytest.raises(ValueError, match='Unknown filter'):
            instrument_index.SearchRequest(
                filters={
                    'instrument_id; DROP TABLE instruments': [
                        'x',
                    ],
                },
            )

    def test_request_refuses_a_large_limit(self) -> None:
        """Checks the limit bound."""
        with pytest.raises(ValueError, match='limit'):
            instrument_index.SearchRequest(limit=1000)


class TestInstrumentIndexMaintainer:
    """Tests for InstrumentIndexMaintainer."""

    def test_refresh_builds_once_per_mapping_date(self, tmp_path: Path) -> None:
        """Checks that a second refresh with the same mapping date does not rebuild.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        client = fakes.FakeCatalogueClient(fakes.CatalogueMaker().catalogue())
        time_source = fakes.FixedClock(fakes.TODAY_EPOCH)
        builder = instrument_index_builder.InstrumentIndexBuilder(
            client,
            tmp_path,
            time_source,
        )
        maintainer = instrument_index_maintainer.InstrumentIndexMaintainer(
            client,
            builder,
            time_source,
        )
        asyncio.run(maintainer.refresh())
        asyncio.run(maintainer.refresh())
        assert client.master_downloads == 1
        status = maintainer.status()
        assert status['state'] == 'ready'
        assert status['instrument_count'] == 10
        assert status['building_count'] is None

    def test_open_newest_existing(self, tmp_path: Path) -> None:
        """Checks that an index left by an earlier run is opened without UBI.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        IndexMaker().build(tmp_path)
        client = fakes.FakeCatalogueClient([])
        time_source = fakes.FixedClock(fakes.TODAY_EPOCH)
        maintainer = instrument_index_maintainer.InstrumentIndexMaintainer(
            client,
            instrument_index_builder.InstrumentIndexBuilder(
                client,
                tmp_path,
                time_source,
            ),
            time_source,
        )
        maintainer.open_newest_existing()
        assert maintainer.current_index.mapping_date == '2026-09-25'
        assert client.master_downloads == 0
