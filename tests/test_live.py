"""Tests for live quotes: encoding, the hub, the reader and a browser connection."""

import asyncio
from typing import Any

import pytest
from tradingmachine.ubi_client import exceptions

from instruments_explorer.market import live_connection
from instruments_explorer.market import live_quote_hub
from instruments_explorer.market import live_quote_reader
from instruments_explorer.market import quote_encoder
from instruments_explorer.unified_broker_interface import live_quote_gateway
from tests import fakes


class QuoteMaker:
    """Writes UBI unified quote documents."""

    def quote(
        self,
        instrument_id: str,
        last_price: float,
        received_at: float,
    ) -> dict[str, Any]:
        """Writes one quote.

        Args:
            instrument_id (str): The instrument id.
            last_price (float): The last traded price.
            received_at (float): When UBI received the tick, in epoch seconds.

        Returns:
            dict[str, Any]: The quote document.
        """
        return {
            'instrument_id': instrument_id,
            'last_price': last_price,
            'previous_close': 100.0,
            'change_percent': None,
            'ohlc': {
                'open': 99.0,
                'high': 112.0,
                'low': 98.5,
            },
            'volume': 1200,
            'depth': {
                'buy': [
                    {
                        'price': last_price - 0.05,
                        'quantity': 10,
                        'orders': 2,
                    },
                ],
                'sell': [],
            },
            'received_at': received_at,
            'stale': False,
        }


class TestQuoteEncoder:
    """Tests for QuoteEncoder."""

    def test_encode_works_out_the_change(self) -> None:
        """Checks the change, the lifted day range and the depth."""
        message = quote_encoder.QuoteEncoder().encode(
            QuoteMaker().quote('id-a', 110.0, 5.0),
            'live',
        )
        assert message['change'] == 10.0
        assert message['change_percent'] == 10.0
        assert message['open'] == 99.0
        assert message['high'] == 112.0
        assert message['depth']['buy'][0]['quantity'] == 10
        assert message['depth']['sell'] == []
        assert message['source'] == 'live'

    def test_encode_survives_an_empty_document(self) -> None:
        """Checks that missing fields become None rather than failing."""
        message = quote_encoder.QuoteEncoder().encode({}, 'cache')
        assert message['last_price'] is None
        assert message['change'] is None
        assert message['depth'] == {
            'buy': [],
            'sell': [],
        }


class TestLiveQuoteHub:
    """Tests for LiveQuoteHub."""

    def test_deliver_reaches_only_watchers(self) -> None:
        """Checks that a quote is queued only on connections watching it."""
        hub = live_quote_hub.LiveQuoteHub()
        watching = live_connection.LiveConnection(
            'watching',
            fakes.RecordingSocket(),
            fakes.FixedClock(0.0),
        )
        idle = live_connection.LiveConnection(
            'idle',
            fakes.RecordingSocket(),
            fakes.FixedClock(0.0),
        )
        hub.add_connection(watching)
        hub.add_connection(idle)
        hub.subscribe('watching', ['id-a'])
        hub.deliver(QuoteMaker().quote('id-a', 101.0, 1.0), 'live')
        assert watching.pending_count() == 1
        assert idle.pending_count() == 0

    def test_subscribe_sends_the_latest_known_quote(self) -> None:
        """Checks that a new watcher gets the quote another watcher already has."""
        hub = live_quote_hub.LiveQuoteHub()
        first = live_connection.LiveConnection(
            'first',
            fakes.RecordingSocket(),
            fakes.FixedClock(0.0),
        )
        second = live_connection.LiveConnection(
            'second',
            fakes.RecordingSocket(),
            fakes.FixedClock(0.0),
        )
        hub.add_connection(first)
        hub.add_connection(second)
        hub.subscribe('first', ['id-a'])
        hub.deliver(QuoteMaker().quote('id-a', 101.0, 1.0), 'live')
        hub.subscribe('second', ['id-a'])
        assert second.pending_count() == 1

    def test_unwatched_quotes_are_forgotten(self) -> None:
        """Checks that the latest quote is dropped once nobody watches."""
        hub = live_quote_hub.LiveQuoteHub()
        connection = live_connection.LiveConnection(
            'only',
            fakes.RecordingSocket(),
            fakes.FixedClock(0.0),
        )
        hub.add_connection(connection)
        hub.subscribe('only', ['id-a'])
        hub.deliver(QuoteMaker().quote('id-a', 101.0, 1.0), 'live')
        hub.remove_connection('only')
        assert hub.watched_ids() == set()
        assert hub.latest_received_at('id-a') is None

    def test_subscription_limit(self) -> None:
        """Checks that one connection cannot watch too many instruments."""
        hub = live_quote_hub.LiveQuoteHub()
        hub.add_connection(
            live_connection.LiveConnection(
                'greedy',
                fakes.RecordingSocket(),
                fakes.FixedClock(0.0),
            )
        )
        too_many = []
        for number in range(
            live_quote_hub.MAXIMUM_SUBSCRIPTIONS_PER_CONNECTION + 1
        ):
            too_many.append(f'id-{number}')
        with pytest.raises(ValueError, match='at most'):
            hub.subscribe('greedy', too_many)


class TestLiveQuoteReader:
    """Tests for LiveQuoteReader."""

    def test_read_once_delivers_only_changed_quotes(self) -> None:
        """Checks that an unchanged quote is not delivered twice, and a new tick is."""
        quotes = {
            'id-a': QuoteMaker().quote('id-a', 101.0, 1.0),
        }
        quote_gateway = live_quote_gateway.LiveQuoteGateway(
            fakes.FakeLiveQuoteSource(quotes)
        )
        hub = live_quote_hub.LiveQuoteHub()
        hub.add_connection(
            live_connection.LiveConnection(
                'browser',
                fakes.RecordingSocket(),
                fakes.FixedClock(0.0),
            )
        )
        hub.subscribe('browser', ['id-a'])
        reader = live_quote_reader.LiveQuoteReader(quote_gateway, hub)
        assert asyncio.run(reader.read_once()) == 1
        assert asyncio.run(reader.read_once()) == 0
        quotes['id-a'] = QuoteMaker().quote('id-a', 102.0, 2.0)
        assert asyncio.run(reader.read_once()) == 1

    def test_read_once_asks_nothing_when_nobody_watches(self) -> None:
        """Checks that Redis is not read without watchers."""
        source = fakes.FakeLiveQuoteSource()
        reader = live_quote_reader.LiveQuoteReader(
            live_quote_gateway.LiveQuoteGateway(source),
            live_quote_hub.LiveQuoteHub(),
        )
        assert asyncio.run(reader.read_once()) == 0
        assert source.reads == []

    def test_redis_failure_is_raised_for_the_retry_loop(self) -> None:
        """Checks that a Redis failure reaches run, which waits and tries again.

        Raises:
            AssertionError: No UnreachableError was raised.
        """
        source = fakes.FakeLiveQuoteSource()
        source.failing = True
        hub = live_quote_hub.LiveQuoteHub()
        hub.add_connection(
            live_connection.LiveConnection(
                'browser',
                fakes.RecordingSocket(),
                fakes.FixedClock(0.0),
            )
        )
        hub.subscribe('browser', ['id-a'])
        reader = live_quote_reader.LiveQuoteReader(
            live_quote_gateway.LiveQuoteGateway(source),
            hub,
        )
        with pytest.raises(exceptions.UnreachableError):
            asyncio.run(reader.read_once())


class TestLiveConnection:
    """Tests for LiveConnection."""

    def test_flush_sends_the_newest_quote_per_instrument(self) -> None:
        """Checks that two quotes for one instrument are merged into one message."""
        socket = fakes.RecordingSocket()
        connection = live_connection.LiveConnection(
            'browser',
            socket,
            fakes.FixedClock(7.0),
        )
        connection.queue_quote(
            {
                'instrument_id': 'id-a',
                'last_price': 1.0,
            }
        )
        connection.queue_quote(
            {
                'instrument_id': 'id-a',
                'last_price': 2.0,
            }
        )
        assert asyncio.run(connection.flush())
        assert socket.sent == [
            {
                'type': 'quotes',
                'server_time': 7.0,
                'quotes': [
                    {
                        'instrument_id': 'id-a',
                        'last_price': 2.0,
                    },
                ],
            },
        ]
