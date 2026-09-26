"""Turns UBI's unified quote into the message the browser shows.

Typical usage example:

  message = QuoteEncoder().encode(quote, 'live')
"""

from collections.abc import Mapping
from typing import Any

_COPIED_FIELDS = [
    'instrument_id',
    'lot_size',
    'last_price',
    'previous_close',
    'average_price',
    'volume',
    'last_quantity',
    'last_trade_time',
    'exchange_time',
    'buy_quantity',
    'sell_quantity',
    'oi',
    'oi_day_high',
    'oi_day_low',
    'received_at',
]


class QuoteEncoder:
    """Picks the fields a quote header and market depth need, and works out the change."""

    def encode(self, quote: Mapping[str, Any], source: str) -> dict[str, Any]:
        """Encodes one quote.

        Args:
            quote (Mapping[str, Any]): UBI's unified quote.
            source (str): "live" when it came from UBI's live quote hash, or UBI's own "cache" or "broker" when it came from the quote route.

        Returns:
            dict[str, Any]: The message, with the day's open, high and low lifted out of "ohlc", the change worked out from the last price and previous close, and the five-level depth.
        """
        message = {}
        for field in _COPIED_FIELDS:
            message[field] = quote.get(field)
        ohlc = quote.get('ohlc') or {}
        message['open'] = ohlc.get('open')
        message['high'] = ohlc.get('high')
        message['low'] = ohlc.get('low')
        last_price = quote.get('last_price')
        previous_close = quote.get('previous_close')
        change = None
        if last_price is not None and previous_close is not None:
            change = round(last_price - previous_close, 4)
        change_percent = quote.get('change_percent')
        if change_percent is None and change is not None and previous_close:
            change_percent = round(change / previous_close * 100, 4)
        message['change'] = change
        message['change_percent'] = change_percent
        depth = quote.get('depth') or {}
        message['depth'] = {
            'buy': list(depth.get('buy') or []),
            'sell': list(depth.get('sell') or []),
        }
        message['stale'] = bool(quote.get('stale'))
        message['source'] = source
        return message
