"""The describe_screener tool: the screener's universes, conditions, sortable figures and when figures were last computed.

Typical usage example:

  outcome = await DescribeScreenerTool(services).run({})
"""

from typing import Any, ClassVar

from instruments_explorer.assistant.tools import base


class DescribeScreenerTool(base.BaseTool):
    """Reads the screener's setup, which the screener page's condition picker shows."""

    NAME = 'describe_screener'
    DESCRIPTION = 'Describes the stock screener before run_screen: its universes, every condition with its key and parameters, the figures results can be sorted by, and when each universe\'s figures were last computed. Conditions are requested as the key followed by colon-separated parameters, such as "rsi:0:30" or "near_high:3".'
    INPUT_SCHEMA: ClassVar[dict[str, Any]] = {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    }

    async def run(self, arguments: dict[str, Any]) -> base.ToolOutcome:
        """Reads the setup.

        Args:
            arguments (dict[str, Any]): The empty input.

        Returns:
            base.ToolOutcome: The setup without the live run's progress.
        """
        del arguments
        setup = await self.call_route(self.services.screener.setup())
        setup = dict(setup)
        setup.pop('job', None)
        return base.ToolOutcome(setup, f'{len(setup["conditions"])} conditions')
