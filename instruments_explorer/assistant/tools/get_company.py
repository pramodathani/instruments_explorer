"""The get_company tool: what is stored about the company behind an instrument.

Typical usage example:

  outcome = await GetCompanyTool(services).run({'instrument_id': instrument_id})
"""

from typing import Any, ClassVar

from instruments_explorer.assistant.tools import base

DOCUMENTS_LISTED = 15


class GetCompanyTool(base.BaseTool):
    """Reads the company panel of the instrument page."""

    NAME = 'get_company'
    DESCRIPTION = 'Reads what is stored about the company behind an instrument (a share or a derivative on one): its profile, sector, ratios and fundamentals from Screener.in and Yahoo Finance, strengths and weaknesses, headquarters address, key people (executives such as the CEO and CFO, and the board of directors from the company registry, with appointment dates), and the titles of its stored documents such as NSE announcements and news. Says when nothing has been fetched yet. Indices, commodities, currencies and bonds have no company.'
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
        """Reads the company.

        Args:
            arguments (dict[str, Any]): The checked input.

        Returns:
            base.ToolOutcome: The company's identity, profile and latest document titles.

        Raises:
            base.ToolError: The instrument is unknown.
        """
        answer = await self.call_route(
            self.services.knowledge.instrument_company(
                arguments['instrument_id']
            )
        )
        if answer.get('company') is None:
            return base.ToolOutcome(
                {
                    'company': None,
                    'reason': answer.get('reason'),
                },
                'Not a company',
            )
        documents = []
        for document in answer.get('documents', [])[:DOCUMENTS_LISTED]:
            documents.append(
                {
                    'title': document.get('title'),
                    'source': document.get('source'),
                    'published_at': document.get('published_at'),
                    'url': document.get('url'),
                }
            )
        profile = answer.get('profile')
        if profile is not None:
            profile = dict(profile)
            profile.pop('key_people', None)
        if profile is None:
            note = 'Nothing has been fetched for this company yet; request_knowledge_fetch can ask the user to fetch it.'
        else:
            note = None
        return base.ToolOutcome(
            {
                'company': answer['company'],
                'profile': profile,
                'key_people': answer.get('key_people'),
                'headquarters': answer.get('headquarters'),
                'documents_total': len(answer.get('documents', [])),
                'latest_documents': documents,
                'note': note,
            },
            answer['company'].get('name') or 'Company',
        )
