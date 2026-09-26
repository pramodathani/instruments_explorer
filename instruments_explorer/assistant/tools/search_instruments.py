"""The search_instruments tool: full-text search with filters over every instrument ubi knows.

Typical usage example:

  outcome = await SearchInstrumentsTool(services).run({'query': 'reliance'})
"""

from typing import Any, ClassVar

from instruments_explorer.assistant.tools import base

_KEPT_FIELDS = [
    'instrument_id',
    'display_name',
    'exchange',
    'segment',
    'shape',
    'symbol',
    'underlying_symbol',
    'company_name',
    'sector',
    'expiry_date',
    'strike_price',
    'option_type',
]


class SearchInstrumentsTool(base.BaseTool):
    """Searches the instrument index the Explore page uses."""

    NAME = 'search_instruments'
    DESCRIPTION = 'Searches every instrument ubi knows (about 236,000 across NSE, BSE, MCX and NCDEX: shares, indices, futures, options, bonds, currencies and commodities) by name, symbol or company name, with optional filters. Use it to find the instrument_id that every other tool needs. The query understands words such as "nifty 24000 ce", "reliance fut" or "gold". Returns matching instruments and the total count.'
    INPUT_SCHEMA: ClassVar[dict[str, Any]] = {
        'type': 'object',
        'properties': {
            'query': {
                'type': 'string',
                'description': 'Words to search for, such as a symbol, company name, strike or expiry month.',
            },
            'exchange': {
                'type': 'string',
                'enum': [
                    'nse',
                    'bse',
                    'mcx',
                    'ncdex',
                ],
            },
            'asset_class': {
                'type': 'string',
                'enum': [
                    'equity',
                    'funds',
                    'fixed_income',
                    'currency',
                    'commodity',
                    'other',
                ],
            },
            'shape': {
                'type': 'string',
                'enum': [
                    'security',
                    'future',
                    'option',
                ],
                'description': 'security means the cash instrument, such as a share or an index.',
            },
            'option_type': {
                'type': 'string',
                'enum': [
                    'CE',
                    'PE',
                ],
            },
            'expiry_month': {
                'type': 'string',
                'description': 'An expiry month as "YYYY-MM".',
            },
            'sector': {
                'type': 'string',
                'description': 'An NSE industry, such as "Information Technology" or "Healthcare".',
            },
            'limit': {
                'type': 'integer',
                'description': 'How many instruments to return, 1 to 50. Defaults to 15.',
            },
        },
        'required': [
            'query',
        ],
        'additionalProperties': False,
    }

    async def run(self, arguments: dict[str, Any]) -> base.ToolOutcome:
        """Runs the search.

        Args:
            arguments (dict[str, Any]): The checked input.

        Returns:
            base.ToolOutcome: The total and the matching instruments.

        Raises:
            base.ToolError: The index is not ready or a filter is invalid.
        """
        limit = min(max(arguments.get('limit', 15), 1), 50)
        filters = {}
        for name in [
            'exchange',
            'asset_class',
            'shape',
            'option_type',
            'expiry_month',
            'sector',
        ]:
            if name in arguments:
                filters[name] = [
                    arguments[name],
                ]
        answer = await self.call_route(
            self.services.instruments.search(
                q=arguments['query'],
                limit=limit,
                **filters,
            )
        )
        instruments = []
        for result in answer['results']:
            kept = {}
            for field in _KEPT_FIELDS:
                if result.get(field) is not None:
                    kept[field] = result[field]
            instruments.append(kept)
        return base.ToolOutcome(
            {
                'total': answer['total'],
                'instruments': instruments,
            },
            f'{answer["total"]} found for “{arguments["query"]}”',
        )
