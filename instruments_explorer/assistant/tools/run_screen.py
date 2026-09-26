"""The run_screen tool: finds stocks meeting technical conditions over the stored daily figures.

Typical usage example:

  outcome = await RunScreenTool(services).run({'conditions': ['rsi:0:30']})
"""

from typing import Any, ClassVar

from instruments_explorer.assistant.tools import base

_KEPT_FIELDS = [
    'instrument_id',
    'symbol',
    'name',
    'sector',
    'close',
    'change_1d',
    'change_21d',
    'change_252d',
    'from_high',
    'rsi_14',
    'adx_14',
    'volume_ratio',
]


class RunScreenTool(base.BaseTool):
    """Runs a screen the way the screener page does."""

    NAME = 'run_screen'
    DESCRIPTION = 'Screens stocks by technical conditions computed once a day with TA-Lib, such as RSI ranges, moving-average crossovers, distance from the 52-week high or low, volume spikes and trend strength. Every condition must hold. Returns how many matched, the matches with their main figures, and the count per sector. Call describe_screener first to learn the condition keys, parameters and sortable figures.'
    INPUT_SCHEMA: ClassVar[dict[str, Any]] = {
        'type': 'object',
        'properties': {
            'conditions': {
                'type': 'array',
                'items': {
                    'type': 'string',
                },
                'description': 'Condition requests such as "rsi:0:30" or "above_average:200".',
            },
            'sectors': {
                'type': 'array',
                'items': {
                    'type': 'string',
                },
                'description': 'Keep only these NSE industries, such as "Information Technology".',
            },
            'universe': {
                'type': 'string',
                'description': 'A universe key from describe_screener. Defaults to total_market.',
            },
            'sort': {
                'type': 'string',
                'description': 'A sortable figure from describe_screener. Defaults to change_1d.',
            },
            'descending': {
                'type': 'boolean',
            },
            'limit': {
                'type': 'integer',
                'description': 'How many matches to return, 1 to 50. Defaults to 25.',
            },
        },
        'required': [
            'conditions',
        ],
        'additionalProperties': False,
    }

    async def run(self, arguments: dict[str, Any]) -> base.ToolOutcome:
        """Runs the screen.

        Args:
            arguments (dict[str, Any]): The checked input.

        Returns:
            base.ToolOutcome: The match count, the matches and the sectors.

        Raises:
            base.ToolError: A condition, sort or universe is invalid.
        """
        limit = min(max(arguments.get('limit', 25), 1), 50)
        answer = await self.call_route(
            self.services.screener.run(
                universe=arguments.get('universe', 'total_market'),
                condition=arguments['conditions'],
                sector=arguments.get('sectors', []),
                sort=arguments.get('sort', 'change_1d'),
                descending=arguments.get('descending', True),
                limit=limit,
            )
        )
        rows = []
        for row in answer['rows']:
            kept = {}
            for field in _KEPT_FIELDS:
                kept[field] = row.get(field)
            rows.append(kept)
        sectors = []
        for sector in answer.get('sectors', []):
            sectors.append(
                {
                    'sector': sector.get('sector'),
                    'count': sector.get('count'),
                    'average_change': sector.get('average_change'),
                }
            )
        return base.ToolOutcome(
            {
                'matched': answer['matched'],
                'with_figures': answer.get('with_figures'),
                'last_run': answer.get('last_run'),
                'rows': rows,
                'sectors': sectors,
            },
            f'{answer["matched"]} stocks matched',
        )
