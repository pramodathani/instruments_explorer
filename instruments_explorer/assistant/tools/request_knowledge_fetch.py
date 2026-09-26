"""The request_knowledge_fetch tool: asks the user to confirm fetching a company's knowledge from the internet.

The tool never fetches anything itself. Fetching makes requests to outside websites, so it only puts a confirmation button in the chat, and the fetch starts when the user presses it.

Typical usage example:

  outcome = await RequestKnowledgeFetchTool(services).run({'instrument_id': instrument_id})
"""

from typing import Any, ClassVar

from instruments_explorer.assistant.tools import base


class RequestKnowledgeFetchTool(base.BaseTool):
    """Offers the user a button that starts a knowledge fetch for a company."""

    NAME = 'request_knowledge_fetch'
    DESCRIPTION = "Asks the user to confirm fetching a company's knowledge from the internet (NSE announcements, Yahoo Finance, Screener.in and news), which takes about twenty seconds. It does not fetch anything by itself: the user sees a button and decides. Use it when get_company shows nothing or old data and the question needs fresh company information. Tell the user you have asked, and do not wait for the result in this turn."
    INPUT_SCHEMA: ClassVar[dict[str, Any]] = {
        'type': 'object',
        'properties': {
            'instrument_id': {
                'type': 'string',
            },
            'reason': {
                'type': 'string',
                'description': 'One sentence the user sees next to the button.',
            },
        },
        'required': [
            'instrument_id',
        ],
        'additionalProperties': False,
    }

    async def run(self, arguments: dict[str, Any]) -> base.ToolOutcome:
        """Checks that the instrument has a company and asks the page to show the button.

        Args:
            arguments (dict[str, Any]): The checked input.

        Returns:
            base.ToolOutcome: A note that the user was asked, with the page instruction.

        Raises:
            base.ToolError: The instrument is not a company.
        """
        answer = await self.call_route(
            self.services.knowledge.instrument_company(
                arguments['instrument_id']
            )
        )
        company = answer.get('company')
        if company is None:
            raise base.ToolError(
                answer.get('reason') or 'This instrument has no company.'
            )
        return base.ToolOutcome(
            {
                'asked': True,
                'note': 'The user now sees a button to start the fetch. Nothing has been fetched yet.',
            },
            f'Asked to fetch {company.get("symbol")}',
            ui_action={
                'kind': 'confirm_fetch',
                'instrument_id': arguments['instrument_id'],
                'company_name': company.get('name'),
                'symbol': company.get('symbol'),
                'reason': arguments.get('reason', ''),
            },
        )
