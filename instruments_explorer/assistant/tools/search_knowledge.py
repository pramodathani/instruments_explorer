"""The search_knowledge tool: semantic search over stored company documents in ChromaDB.

Typical usage example:

  outcome = await SearchKnowledgeTool(services).run({'question': 'dividend policy', 'instrument_id': instrument_id})
"""

from typing import Any, ClassVar

from instruments_explorer.assistant.tools import base


class SearchKnowledgeTool(base.BaseTool):
    """Searches the stored passages the knowledge page and company panel search."""

    NAME = 'search_knowledge'
    DESCRIPTION = "Finds the stored passages closest in meaning to a question, across NSE announcements, company profiles, news, Wikipedia and the user's uploaded documents. Give an instrument_id to search only that instrument's company. Cite each passage's title, source and date when you use it."
    INPUT_SCHEMA: ClassVar[dict[str, Any]] = {
        'type': 'object',
        'properties': {
            'question': {
                'type': 'string',
            },
            'instrument_id': {
                'type': 'string',
                'description': "Search only this instrument's company.",
            },
            'limit': {
                'type': 'integer',
                'description': 'How many passages, 1 to 12. Defaults to 8.',
            },
        },
        'required': [
            'question',
        ],
        'additionalProperties': False,
    }

    async def run(self, arguments: dict[str, Any]) -> base.ToolOutcome:
        """Runs the search.

        Args:
            arguments (dict[str, Any]): The checked input.

        Returns:
            base.ToolOutcome: The passages, best first.

        Raises:
            base.ToolError: The instrument is not a company, or ChromaDB cannot be reached.
        """
        company_key = None
        if 'instrument_id' in arguments:
            company = await self.call_route(
                self.services.knowledge.instrument_company(
                    arguments['instrument_id']
                )
            )
            if company.get('company') is None:
                raise base.ToolError(
                    company.get('reason') or 'This instrument has no company.'
                )
            company_key = company['company']['company_key']
        limit = min(max(arguments.get('limit', 8), 1), 12)
        passages = await self.call_route(
            self.services.knowledge.search(
                arguments['question'],
                company_key=company_key,
                limit=limit,
            )
        )
        return base.ToolOutcome(passages, f'{len(passages)} passages')
