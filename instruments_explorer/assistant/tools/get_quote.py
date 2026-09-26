"""The get_quote tool: an instrument's latest quote with market depth.

Typical usage example:

  outcome = await GetQuoteTool(services).run({'instrument_id': instrument_id})
"""

from typing import Any, ClassVar

from instruments_explorer.assistant.tools import base


class GetQuoteTool(base.BaseTool):
    """Reads the full quote the instrument page shows."""

    NAME = 'get_quote'
    DESCRIPTION = "Reads an instrument's latest quote from ubi: last price, change, open, high, low, previous close, volume, open interest and five levels of bids and offers. Outside market hours this is the last traded state. Needs an instrument_id."
    INPUT_SCHEMA: ClassVar[dict[str, Any]] = {
        'type': 'object',
        'properties': {
            'instrument_id': {
                'type': 'string',
            },
        },
        'required': [
            'instrument_id',
        ],
        'additionalProperties': False,
    }

    async def run(self, arguments: dict[str, Any]) -> base.ToolOutcome:
        """Reads the quote.

        Args:
            arguments (dict[str, Any]): The checked input.

        Returns:
            base.ToolOutcome: The quote.

        Raises:
            base.ToolError: ubi could not give a quote.
        """
        quote = await self.call_route(
            self.services.instruments.quote(arguments['instrument_id'])
        )
        price = quote.get('last_price')
        return base.ToolOutcome(quote, f'Last price {price}')
