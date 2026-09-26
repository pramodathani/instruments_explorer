"""Tests for the gateways and components through which the project reaches UBI with tradingmachine."""

import asyncio
import os
from pathlib import Path
from typing import Any

import pytest
from tradingmachine.ubi_client import exceptions

from instruments_explorer.configuration import (
    unified_broker_interface_configuration,
)
from instruments_explorer.unified_broker_interface import catalogue_gateway
from instruments_explorer.unified_broker_interface import live_quote_gateway
from instruments_explorer.unified_broker_interface import (
    tradingmachine_components,
)
from tests import fakes

_ENVIRONMENT = '\n'.join(
    [
        'UNIFIED_BROKER_INTERFACE_REDIS_HOST=127.0.0.1',
        'UNIFIED_BROKER_INTERFACE_REDIS_PORT=1002',
        'UNIFIED_BROKER_INTERFACE_REDIS_DB=0',
        'UNIFIED_BROKER_INTERFACE_REDIS_PASSWORD=redis-secret',
        'UNIFIED_BROKER_INTERFACE_MONGODB_HOST=127.0.0.1',
        'UNIFIED_BROKER_INTERFACE_MONGODB_PORT=1003',
        'UNIFIED_BROKER_INTERFACE_MONGODB_DB=ubi',
        'UNIFIED_BROKER_INTERFACE_API_PORT=8080',
    ]
)


class TestCatalogueGateway:
    """Tests for CatalogueGateway."""

    def test_answers_pass_through_unchanged(self) -> None:
        """Checks that every read returns tradingmachine's answer as it came."""
        catalogue = fakes.FakeTradingmachineCatalogue()
        catalogue.documents[('details', 'a')] = {
            'instrument_id': 'a',
        }
        catalogue.documents[('additional_details', 'a')] = {
            'attribute_names': [
                'isin',
            ],
        }
        catalogue.documents[('quote', 'a')] = {
            'last_price': 12.5,
            'source': 'cache',
        }
        prices = fakes.PricesMaker().document(3)
        catalogue.prices['a'] = prices
        gateway = catalogue_gateway.CatalogueGateway(catalogue)

        async def read_everything() -> list[Any]:
            """Reads every route once.

            Returns:
                list[Any]: The answers, in route order.
            """
            return [
                await gateway.greeting(),
                await gateway.instrument_segments(),
                await gateway.instrument_details('a'),
                await gateway.additional_details('a'),
                await gateway.quote('a'),
                await gateway.prices('a', '5minute', 30, False),
            ]

        answers = asyncio.run(read_everything())
        assert answers[0]['message'].startswith('Welcome')
        assert answers[1]['mapping_date'] == '2026-09-26'
        assert answers[2] == {
            'instrument_id': 'a',
        }
        assert answers[4]['source'] == 'cache'
        assert answers[5] is prices
        assert catalogue.price_requests == [
            (
                'a',
                '5minute',
                30,
                False,
            ),
        ]

    def test_errors_pass_through(self) -> None:
        """Checks that tradingmachine's errors reach the caller unchanged.

        Raises:
            AssertionError: No NotFoundError was raised.
        """
        gateway = catalogue_gateway.CatalogueGateway(
            fakes.FakeTradingmachineCatalogue()
        )
        with pytest.raises(exceptions.NotFoundError):
            asyncio.run(gateway.instrument_details('missing'))

    def test_master_is_handed_on_in_batches(self) -> None:
        """Checks the batches, the mapping date and that the stream is closed."""
        catalogue = fakes.FakeTradingmachineCatalogue()
        identities = []
        for index in range(7):
            identities.append(
                {
                    'instrument_id': f'id-{index}',
                }
            )
        catalogue.master = fakes.FakeMasterStream(identities, '2026-09-25')
        gateway = catalogue_gateway.CatalogueGateway(catalogue)
        sizes = []

        async def store_batch(batch: list[dict[str, Any]]) -> None:
            """Records a batch's size.

            Args:
                batch (list[dict[str, Any]]): The batch.
            """
            sizes.append(len(batch))

        mapping_date = asyncio.run(gateway.download_master(store_batch, 3))
        assert mapping_date == '2026-09-25'
        assert sizes == [
            3,
            3,
            1,
        ]
        assert catalogue.master.closed

    def test_incomplete_master_raises_and_closes(self) -> None:
        """Checks that a master that stops early raises and is still closed.

        Raises:
            AssertionError: No IncompleteResponseError was raised.
        """
        catalogue = fakes.FakeTradingmachineCatalogue()
        catalogue.master = fakes.FakeMasterStream(
            [
                {
                    'instrument_id': 'a',
                },
            ],
            '2026-09-25',
        )
        catalogue.master.failure = exceptions.IncompleteResponseError(
            'ended early'
        )
        gateway = catalogue_gateway.CatalogueGateway(catalogue)

        async def ignore_batch(batch: list[dict[str, Any]]) -> None:
            """Ignores a batch.

            Args:
                batch (list[dict[str, Any]]): The batch.
            """
            del batch

        with pytest.raises(exceptions.IncompleteResponseError):
            asyncio.run(gateway.download_master(ignore_batch))
        assert catalogue.master.closed


class TestLiveQuoteGateway:
    """Tests for LiveQuoteGateway."""

    def test_quotes_and_failures(self) -> None:
        """Checks that quotes come back and a Redis failure is raised.

        Raises:
            AssertionError: The quotes or the error were wrong.
        """
        source = fakes.FakeLiveQuoteSource(
            {
                'a': {
                    'last_price': 1.0,
                },
            }
        )
        gateway = live_quote_gateway.LiveQuoteGateway(source)
        assert asyncio.run(gateway.read(('a', 'b'))) == {
            'a': {
                'last_price': 1.0,
            },
        }
        assert source.reads == [
            [
                'a',
                'b',
            ],
        ]
        source.failing = True
        with pytest.raises(exceptions.UnreachableError):
            asyncio.run(gateway.read(['a']))


class TestTradingmachineComponents:
    """Tests for TradingmachineComponents."""

    def test_components_use_ubi_settings_and_no_tradingmachine_configuration(
        self,
        tmp_path: Path,
    ) -> None:
        """Checks the wiring, and that tradingmachine's own .env is never loaded.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        (tmp_path / '.env').write_text(_ENVIRONMENT)
        configuration = unified_broker_interface_configuration.UnifiedBrokerInterfaceConfiguration.load(
            tmp_path
        )
        components = tradingmachine_components.TradingmachineComponents(
            configuration,
            5.0,
            False,
            90.0,
            fakes.FixedClock(0.0),
        )
        assert components.client.token_source is components.token_source
        assert components.token_source.may_connect is False
        assert components.token_source.connect_cooldown_seconds == 90.0
        assert (
            components.catalogue.unified_broker_interface is components.client
        )
        assert components.live_quote_reader.hash_name == 'unified:quotes:live'
        for name in os.environ:
            assert not name.startswith('TRADINGMACHINE_'), name
        components.close()
