"""The get_instrument tool: one instrument's details from the index and from ubi.

Typical usage example:

  outcome = await GetInstrumentTool(services).run({'instrument_id': instrument_id})
"""

from typing import Any, ClassVar

from instruments_explorer.assistant.tools import base


class GetInstrumentTool(base.BaseTool):
    """Reads what the instrument page shows at the top: the record, lot size, tick size and other details."""

    NAME = 'get_instrument'
    DESCRIPTION = "Reads one instrument's full details: its names, exchange and segment, expiry, strike, lot size, tick size, trading symbol and ubi's additional attributes. Needs an instrument_id from search_instruments."
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
        """Reads the instrument.

        Args:
            arguments (dict[str, Any]): The checked input.

        Returns:
            base.ToolOutcome: The instrument's details.

        Raises:
            base.ToolError: The instrument is unknown.
        """
        answer = await self.call_route(
            self.services.instruments.instrument(arguments['instrument_id'])
        )
        name = answer.get('record', {}).get(
            'display_name', arguments['instrument_id']
        )
        return base.ToolOutcome(answer, f'Details of {name}')
