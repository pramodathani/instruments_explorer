"""Reads the key people out of an uploaded document, such as an annual report, with Claude.

An annual report runs to hundreds of pages, so only the passages that mention directors, officers or the board are sent, up to MAXIMUM_CHARACTERS. Claude answers with a list in a fixed JSON shape. The tokens used count toward the chat assistant's daily limit.

Typical usage example:

  extractor = KeyPeopleExtractor(client, usage, explorer_settings, clock)
  people = await extractor.extract('Reliance Industries Limited', document_text)
"""

import datetime
import json
import re
import zoneinfo

import anthropic

from instruments_explorer.configuration import settings
from instruments_explorer.storage import chat_usage_repository
from instruments_explorer.utilities import clock

MAXIMUM_CHARACTERS = 40000
PASSAGE_CHARACTERS = 1500
MAX_TOKENS = 16000
INDIA = zoneinfo.ZoneInfo('Asia/Kolkata')
KEYWORDS = re.compile(
    r'board of directors|director|chairman|chairperson|chief executive|chief financial|chief operating|\bceo\b|\bcfo\b|\bcoo\b|\bcto\b|company secretary|key managerial|\bdin\b',
    re.IGNORECASE,
)
PEOPLE_SCHEMA = {
    'type': 'object',
    'properties': {
        'people': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                    },
                    'role': {
                        'type': 'string',
                    },
                },
                'required': [
                    'name',
                    'role',
                ],
                'additionalProperties': False,
            },
        },
    },
    'required': [
        'people',
    ],
    'additionalProperties': False,
}
INSTRUCTIONS = """These are passages from a document about {company}, such as its annual report. List the company's current key people: the chairperson, the managing director or chief executive, the chief financial officer, other chief officers (such as COO, CTO, CHRO), the company secretary, and every member of the board of directors, marking each director's kind (for example "Independent Director", "Non-Executive Director", "Whole-time Director").

Use each person's full name as written, without honorifics such as Mr. or Dr. Give each person once, with all their roles in one role string separated by semicolons. Leave out people who have resigned or retired, auditors, and people from other companies. If the passages name nobody, return an empty list.

<passages>
{passages}
</passages>"""


class ExtractionError(Exception):
    """Claude could not read key people from the document."""


class KeyPeopleExtractor:
    """Asks Claude to list the key people named in a document."""

    def __init__(
        self,
        client: anthropic.AsyncAnthropic,
        usage: chat_usage_repository.ChatUsageRepository,
        explorer_settings: settings.Settings,
        time_source: clock.SystemClock,
    ):
        """Keeps the client, the usage ledger and the settings.

        Args:
            client (anthropic.AsyncAnthropic): The Claude API client.
            usage (chat_usage_repository.ChatUsageRepository): Adds up tokens per day, shared with the chat assistant.
            explorer_settings (settings.Settings): Supplies the model and the daily limit.
            time_source (clock.SystemClock): The source of the current time.
        """
        self._client = client
        self._usage = usage
        self._settings = explorer_settings
        self._time_source = time_source

    async def extract(
        self, company_name: str, text: str
    ) -> list[dict[str, str]]:
        """Lists the key people a document names.

        Args:
            company_name (str): The company the document is about.
            text (str): The document's text.

        Returns:
            list[dict[str, str]]: One {"name", "role"} per person.

        Raises:
            ExtractionError: The document mentions no directors or officers, today's token limit is used up, Claude declined, or its answer could not be read.
            anthropic.APIError: The request failed.
        """
        passages = self.select_passages(text)
        if not passages:
            raise ExtractionError(
                'The document does not mention any directors or officers.'
            )
        today = (
            datetime.datetime.fromtimestamp(self._time_source.now(), INDIA)
            .date()
            .isoformat()
        )
        totals = await self._usage.day(today)
        used = (
            totals['input_tokens']
            + totals['output_tokens']
            + totals['cache_creation_input_tokens']
        )
        if used >= self._settings.claude_daily_token_limit:
            raise ExtractionError("Today's Claude token limit is used up.")
        response = await self._client.messages.create(
            model=self._settings.claude_model,
            max_tokens=MAX_TOKENS,
            thinking={
                'type': 'adaptive',
            },
            output_config={
                'effort': 'low',
                'format': {
                    'type': 'json_schema',
                    'schema': PEOPLE_SCHEMA,
                },
            },
            messages=[
                {
                    'role': 'user',
                    'content': INSTRUCTIONS.format(
                        company=company_name,
                        passages=passages,
                    ),
                },
            ],
        )
        tokens = {}
        for field in chat_usage_repository.USAGE_FIELDS:
            tokens[field] = int(getattr(response.usage, field, 0) or 0)
        await self._usage.add(today, tokens)
        if response.stop_reason == 'refusal':
            raise ExtractionError('Claude declined to read this document.')
        answer = ''
        for block in response.content:
            if block.type == 'text':
                answer += block.text
        try:
            people = json.loads(answer)['people']
        except (ValueError, KeyError, TypeError) as error:
            raise ExtractionError(
                "Claude's answer could not be read."
            ) from error
        cleaned = []
        for person in people:
            name = str(person.get('name', '')).strip()
            if name:
                cleaned.append(
                    {
                        'name': name,
                        'role': str(person.get('role', '')).strip(),
                    }
                )
        return cleaned

    def select_passages(self, text: str) -> str:
        """Picks the parts of a long document that mention directors, officers or the board.

        Args:
            text (str): The document's text.

        Returns:
            str: The passages around each mention, merged where they overlap, at most MAXIMUM_CHARACTERS long, or an empty string when nothing is mentioned.
        """
        windows = []
        for match in KEYWORDS.finditer(text):
            start = max(match.start() - PASSAGE_CHARACTERS // 3, 0)
            end = min(match.start() + PASSAGE_CHARACTERS, len(text))
            if windows and start <= windows[-1][1]:
                windows[-1][1] = max(windows[-1][1], end)
            else:
                windows.append([start, end])
        pieces = []
        total = 0
        for start, end in windows:
            piece = text[start:end]
            if total + len(piece) > MAXIMUM_CHARACTERS:
                piece = piece[: MAXIMUM_CHARACTERS - total]
            pieces.append(piece)
            total += len(piece)
            if total >= MAXIMUM_CHARACTERS:
                break
        return '\n[…]\n'.join(pieces)
