"""The list_indicators tool: the TA-Lib indicators the charts can draw and how to ask for them.

Typical usage example:

  outcome = await ListIndicatorsTool(services).run({})
"""

from typing import Any, ClassVar

from instruments_explorer.assistant.tools import base


class ListIndicatorsTool(base.BaseTool):
    """Lists the indicator catalogue the chart's picker shows."""

    NAME = 'list_indicators'
    DESCRIPTION = 'Lists the technical indicators available for get_price_history and for charts shown with show_in_ui, with each one\'s key and parameters. An indicator is requested as its key followed by colon-separated parameters in order, such as "rsi:14", "sma:50" or "macd:12:26:9"; parameters left out take their defaults.'
    INPUT_SCHEMA: ClassVar[dict[str, Any]] = {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    }

    async def run(self, arguments: dict[str, Any]) -> base.ToolOutcome:
        """Lists the indicators.

        Args:
            arguments (dict[str, Any]): The empty input.

        Returns:
            base.ToolOutcome: The catalogue.
        """
        del arguments
        catalogue = self.services.charts.indicators()
        return base.ToolOutcome(catalogue, f'{len(catalogue)} indicators')
