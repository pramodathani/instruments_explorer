"""The get_price_history tool: candles and TA-Lib indicators, summarised so a long history stays small.

Typical usage example:

  outcome = await GetPriceHistoryTool(services).run({'instrument_id': instrument_id, 'indicators': ['rsi:14']})
"""

from typing import Any, ClassVar

from instruments_explorer.assistant.tools import base

RECENT_CANDLES = 20


class GetPriceHistoryTool(base.BaseTool):
    """Reads what the chart draws and gives Claude a summary with the latest values."""

    NAME = 'get_price_history'
    DESCRIPTION = "Reads an instrument's candles from ubi and computes technical indicators over them with TA-Lib. Returns a summary of the whole period (first and last close, change, highest and lowest price, average volume) plus the last 20 candles and each indicator's last 20 values, not the full series. Daily candles are reliable; intraday candles exist only for a few instruments. Use show_in_ui to draw the chart for the user."
    INPUT_SCHEMA: ClassVar[dict[str, Any]] = {
        'type': 'object',
        'properties': {
            'instrument_id': {
                'type': 'string',
            },
            'interval': {
                'type': 'string',
                'enum': [
                    'day',
                    'week',
                    'month',
                    '60minute',
                    '30minute',
                    '15minute',
                    '5minute',
                    'minute',
                ],
                'description': 'The candle length. Defaults to day.',
            },
            'days': {
                'type': 'integer',
                'description': 'How many calendar days back from today. Defaults to 365.',
            },
            'indicators': {
                'type': 'array',
                'items': {
                    'type': 'string',
                },
                'description': 'Indicator requests such as "rsi:14" or "sma:200"; see list_indicators.',
            },
        },
        'required': [
            'instrument_id',
        ],
        'additionalProperties': False,
    }

    async def run(self, arguments: dict[str, Any]) -> base.ToolOutcome:
        """Reads the candles and indicators and summarises them.

        Args:
            arguments (dict[str, Any]): The checked input.

        Returns:
            base.ToolOutcome: The summary, recent candles and recent indicator values.

        Raises:
            base.ToolError: The interval or range is invalid, or ubi could not give candles.
        """
        answer = await self.call_route(
            self.services.charts.chart(
                arguments['instrument_id'],
                interval=arguments.get('interval', 'day'),
                days=arguments.get('days', 365),
                indicator=arguments.get('indicators', []),
            )
        )
        candles = answer['candles']
        if not candles:
            return base.ToolOutcome(
                {
                    'candles': 0,
                    'note': 'ubi has no candles for this instrument, interval and period.',
                },
                'No candles',
            )
        return base.ToolOutcome(
            {
                'interval': answer['interval'],
                'price_basis': answer.get('price_basis'),
                'summary': self._summary(candles),
                'recent_candles': self._recent(candles),
                'indicators': self._indicators(answer.get('indicators', [])),
                'errors': answer.get('errors', []),
            },
            f'{len(candles)} candles',
        )

    def _summary(self, candles: list[list[Any]]) -> dict[str, Any]:
        """Describes the whole period.

        Args:
            candles (list[list[Any]]): Rows of [time, open, high, low, close, volume, oi].

        Returns:
            dict[str, Any]: The period's first and last dates and closes, change, range and average volume.
        """
        highest = candles[0][2]
        lowest = candles[0][3]
        volume_total = 0
        for candle in candles:
            highest = max(highest, candle[2])
            lowest = min(lowest, candle[3])
            volume_total += candle[5] or 0
        first_close = candles[0][4]
        last_close = candles[-1][4]
        change = None
        if first_close:
            change = round((last_close / first_close - 1) * 100, 2)
        return {
            'candles': len(candles),
            'first_time': candles[0][0],
            'last_time': candles[-1][0],
            'first_close': first_close,
            'last_close': last_close,
            'change_percent': change,
            'highest': highest,
            'lowest': lowest,
            'average_volume': round(volume_total / len(candles)),
        }

    def _recent(self, candles: list[list[Any]]) -> list[dict[str, Any]]:
        """Gives the latest candles with named fields.

        Args:
            candles (list[list[Any]]): Rows of [time, open, high, low, close, volume, oi].

        Returns:
            list[dict[str, Any]]: The last RECENT_CANDLES candles.
        """
        recent = []
        for candle in candles[-RECENT_CANDLES:]:
            recent.append(
                {
                    'time': candle[0],
                    'open': candle[1],
                    'high': candle[2],
                    'low': candle[3],
                    'close': candle[4],
                    'volume': candle[5],
                }
            )
        return recent

    def _indicators(
        self, indicators: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Keeps each indicator line's latest values and its latest markers.

        Args:
            indicators (list[dict[str, Any]]): The indicators from the chart route.

        Returns:
            list[dict[str, Any]]: Each indicator's id and title, each line's last values as [time, value] pairs, and its last markers for candle patterns.
        """
        summaries = []
        for indicator in indicators:
            lines = []
            for output in indicator.get('outputs', []):
                lines.append(
                    {
                        'label': output.get('label'),
                        'recent': output.get('points', [])[-RECENT_CANDLES:],
                    }
                )
            summaries.append(
                {
                    'id': indicator.get('id'),
                    'title': indicator.get('title'),
                    'lines': lines,
                    'recent_markers': indicator.get('markers', [])[
                        -RECENT_CANDLES:
                    ],
                }
            )
        return summaries
