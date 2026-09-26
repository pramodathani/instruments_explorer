"""The assistant's tools in a fixed order, and the one place that runs a tool call safely.

The tools list is sent with every request, so its order and wording never change between requests; that keeps it inside Claude's prompt cache.

Typical usage example:

  tool_box = ToolBox(services)
  definitions = tool_box.definitions()
  outcome = await tool_box.call('get_quote', {'instrument_id': instrument_id})
"""

import logging
from typing import Any

from instruments_explorer.assistant import assistant_services
from instruments_explorer.assistant.tools import base
from instruments_explorer.assistant.tools import describe_screener
from instruments_explorer.assistant.tools import get_company
from instruments_explorer.assistant.tools import get_instrument
from instruments_explorer.assistant.tools import get_option_chain
from instruments_explorer.assistant.tools import get_price_history
from instruments_explorer.assistant.tools import get_quote
from instruments_explorer.assistant.tools import list_indicators
from instruments_explorer.assistant.tools import request_knowledge_fetch
from instruments_explorer.assistant.tools import run_screen
from instruments_explorer.assistant.tools import search_instruments
from instruments_explorer.assistant.tools import search_knowledge
from instruments_explorer.assistant.tools import show_in_ui

WEB_SEARCH_TOOL = {
    'type': 'web_search_20260209',
    'name': 'web_search',
    'max_uses': 5,
}

_LOGGER = logging.getLogger(__name__)


class ToolBox:
    """Holds every tool and runs calls to them.

    Attributes:
        tools: The client tools, in the order they are sent to Claude.
    """

    def __init__(
        self,
        services: assistant_services.AssistantServices,
        web_search: bool = True,
    ):
        """Creates every tool.

        Args:
            services (assistant_services.AssistantServices): The route groups the tools call.
            web_search (bool): Whether to offer Claude's server-side web search as well.
        """
        self.tools = [
            search_instruments.SearchInstrumentsTool(services),
            get_instrument.GetInstrumentTool(services),
            get_quote.GetQuoteTool(services),
            list_indicators.ListIndicatorsTool(services),
            get_price_history.GetPriceHistoryTool(services),
            get_option_chain.GetOptionChainTool(services),
            describe_screener.DescribeScreenerTool(services),
            run_screen.RunScreenTool(services),
            get_company.GetCompanyTool(services),
            search_knowledge.SearchKnowledgeTool(services),
            request_knowledge_fetch.RequestKnowledgeFetchTool(services),
            show_in_ui.ShowInUiTool(services),
        ]
        self._web_search = web_search
        self._by_name = {}
        for tool in self.tools:
            self._by_name[tool.NAME] = tool

    def definitions(self) -> list[dict[str, Any]]:
        """Describes every tool for the request.

        Returns:
            list[dict[str, Any]]: The client tool definitions, then web search when offered.
        """
        definitions = []
        for tool in self.tools:
            definitions.append(tool.definition())
        if self._web_search:
            definitions.append(dict(WEB_SEARCH_TOOL))
        return definitions

    async def call(self, name: str, arguments: Any) -> base.ToolOutcome:
        """Runs one tool call, turning every failure into an error result Claude can read.

        This is an isolation point: a tool that crashes must not end the conversation, so unexpected errors are logged and reported to Claude as a failed call.

        Args:
            name (str): The tool's name.
            arguments (Any): The input Claude wrote.

        Returns:
            base.ToolOutcome: The tool's result, or an error result.
        """
        tool = self._by_name.get(name)
        if tool is None:
            return base.ToolOutcome(
                f'There is no tool named {name!r}.',
                'Unknown tool',
                is_error=True,
            )
        problems = tool.problems(arguments)
        if problems:
            return base.ToolOutcome(
                'The input was not valid: ' + ' '.join(problems),
                'Invalid input',
                is_error=True,
            )
        try:
            return await tool.run(arguments)
        except base.ToolError as error:
            return base.ToolOutcome(str(error), str(error), is_error=True)
        except Exception:  # pylint: disable=broad-exception-caught
            _LOGGER.exception('Tool %s failed', name)
            return base.ToolOutcome(
                f'The {name} tool failed unexpectedly.',
                'Failed',
                is_error=True,
            )
