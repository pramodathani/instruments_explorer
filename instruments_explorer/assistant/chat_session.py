"""Runs one turn of a conversation with Claude: streams the answer, runs tools, and stores every message.

The loop is written out by hand rather than using the SDK's tool runner, because every piece of the answer (thinking summaries, text, tool calls, tool results and page instructions) is forwarded to the browser the moment it arrives.

Typical usage example:

  session = ChatSession(client, tool_box, conversations, usage, explorer_settings, clock)
  async for event in session.respond(conversation_id, 'Chart TCS with RSI', {'path': '/overview'}):
      send(event)
"""

import asyncio
import datetime
import logging
import zoneinfo
from collections.abc import AsyncIterator, Mapping
from pathlib import Path
from typing import Any

import anthropic

from instruments_explorer.assistant import tool_box
from instruments_explorer.configuration import settings
from instruments_explorer.storage import chat_usage_repository
from instruments_explorer.storage import conversation_repository
from instruments_explorer.utilities import clock

MAX_TOKENS = 64000
MAXIMUM_ROUNDS = 16
MAXIMUM_JSON_RETRIES = 2
FALLBACK_BETA = 'server-side-fallback-2026-07-01'
INDIA = zoneinfo.ZoneInfo('Asia/Kolkata')
SYSTEM_PROMPT = (Path(__file__).parent / 'system_prompt.md').read_text(
    encoding='utf-8'
)
CONTEXT_OPENING = '<page_context>'
DEFAULT_TITLE = 'New chat'

_LOGGER = logging.getLogger(__name__)


class ChatSession:
    """Answers the user's messages with Claude and the application's tools."""

    def __init__(
        self,
        client: anthropic.AsyncAnthropic | None,
        tools: tool_box.ToolBox,
        conversations: conversation_repository.ConversationRepository,
        usage: chat_usage_repository.ChatUsageRepository,
        explorer_settings: settings.Settings,
        time_source: clock.SystemClock,
    ):
        """Keeps the client, tools and stores.

        Args:
            client (anthropic.AsyncAnthropic | None): The Claude API client, or None when only usage is read.
            tools (tool_box.ToolBox): The tools Claude may call.
            conversations (conversation_repository.ConversationRepository): Stores conversations and messages.
            usage (chat_usage_repository.ChatUsageRepository): Adds up tokens per day.
            explorer_settings (settings.Settings): Supplies the model, effort and daily limit.
            time_source (clock.SystemClock): The source of the current time.
        """
        self._client = client
        self._tools = tools
        self._conversations = conversations
        self._usage = usage
        self._settings = explorer_settings
        self._time_source = time_source

    async def respond(
        self,
        conversation_id: str,
        text: str,
        page: Mapping[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        """Answers one user message, yielding events for the browser as they happen.

        Events have a "type": "text_start", "text", "thinking_start", "thinking", "tool_call", "tool_result", "ui_action", "title", "usage", "refusal", "error" and finally "done".

        Args:
            conversation_id (str): The conversation's id.
            text (str): What the user wrote.
            page (Mapping[str, Any]): The page the user is on, with "path" and optionally "title".

        Yields:
            dict[str, Any]: One event for the browser.
        """
        conversation = await self._conversations.find(conversation_id)
        if conversation is None:
            yield self._error('This conversation no longer exists.')
            return
        limit_message = await self._limit_message()
        if limit_message is not None:
            yield self._error(limit_message)
            return
        history = []
        for message in await self._conversations.messages(conversation_id):
            history.append(
                {
                    'role': message['role'],
                    'content': message['content'],
                }
            )
        user_content = [
            {
                'type': 'text',
                'text': self._context_text(page),
            },
            {
                'type': 'text',
                'text': text,
            },
        ]
        await self._conversations.append(
            conversation_id,
            'user',
            user_content,
            self._time_source.now(),
            None,
        )
        history.append(
            {
                'role': 'user',
                'content': user_content,
            }
        )
        if (
            conversation['message_count'] == 0
            and conversation['title'] == DEFAULT_TITLE
        ):
            title = self._title_from(text)
            await self._conversations.rename(conversation_id, title)
            yield {
                'type': 'title',
                'title': title,
            }
        async for event in self._run_rounds(conversation_id, history):
            yield event
        yield {
            'type': 'done',
        }

    async def _run_rounds(
        self,
        conversation_id: str,
        history: list[dict[str, Any]],
    ) -> AsyncIterator[dict[str, Any]]:
        """Asks Claude, runs any tools it calls, and asks again until it answers without tools.

        Args:
            conversation_id (str): The conversation's id.
            history (list[dict[str, Any]]): Every message so far, extended in place.

        Yields:
            dict[str, Any]: One event for the browser.
        """
        json_retries = 0
        rounds = 0
        while rounds < MAXIMUM_ROUNDS:
            holder = {}
            try:
                async for event in self._stream_round(history, holder):
                    yield event
            except ValueError:
                json_retries += 1
                if json_retries > MAXIMUM_JSON_RETRIES:
                    yield self._error(
                        'Claude wrote a tool input that could not be read, several times in a row.'
                    )
                    return
                continue
            except anthropic.RateLimitError:
                yield self._error(
                    'The Claude API is rate limiting requests. Wait a minute and try again.'
                )
                return
            except anthropic.AuthenticationError:
                yield self._error(
                    'The Claude API rejected the API key. Check INSTRUMENTS_EXPLORER_ANTHROPIC_API_KEY.'
                )
                return
            except anthropic.APIStatusError as error:
                yield self._error(
                    f'The Claude API answered with an error ({error.status_code}): {error.message}'
                )
                return
            except anthropic.APIConnectionError:
                yield self._error(
                    'The Claude API could not be reached. Check the internet connection.'
                )
                return
            json_retries = 0
            rounds += 1
            message = holder['message']
            usage = await self._record_usage(message)
            yield usage
            if message.stop_reason == 'refusal':
                yield self._refusal(message)
                return
            content = self._content_dicts(message)
            tool_uses = []
            for block in message.content:
                if block.type == 'tool_use':
                    tool_uses.append(block)
            if message.stop_reason == 'max_tokens' and tool_uses:
                yield self._error(
                    'The answer ran out of room while writing a tool call.'
                )
                return
            await self._store(
                conversation_id, history, 'assistant', content, usage
            )
            if message.stop_reason == 'pause_turn':
                continue
            if not tool_uses:
                return
            async for event in self._run_tools(
                conversation_id, history, tool_uses
            ):
                yield event
        yield self._error(
            f'Stopped after {MAXIMUM_ROUNDS} rounds of tool calls.'
        )

    async def _stream_round(
        self,
        history: list[dict[str, Any]],
        holder: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        """Streams one request to Claude, forwarding its pieces and keeping the finished message in holder.

        Args:
            history (list[dict[str, Any]]): Every message so far.
            holder (dict[str, Any]): Receives the finished message under "message".

        Yields:
            dict[str, Any]: One event for the browser.

        Raises:
            ValueError: A tool input could not be parsed at all.
            anthropic.APIError: The request failed.
        """
        async with self._client.beta.messages.stream(
            model=self._settings.claude_model,
            max_tokens=MAX_TOKENS,
            system=[
                {
                    'type': 'text',
                    'text': SYSTEM_PROMPT,
                    'cache_control': {
                        'type': 'ephemeral',
                    },
                },
            ],
            tools=self._tools.definitions(),
            messages=history,
            thinking={
                'type': 'adaptive',
                'display': 'summarized',
            },
            output_config={
                'effort': self._settings.claude_effort,
            },
            cache_control={
                'type': 'ephemeral',
            },
            fallbacks='default',
            betas=[
                FALLBACK_BETA,
            ],
        ) as stream:
            async for event in stream:
                forwarded = self._forward(event)
                if forwarded is not None:
                    yield forwarded
            holder['message'] = await stream.get_final_message()

    def _forward(self, event: Any) -> dict[str, Any] | None:
        """Turns one stream event into a browser event, when the browser needs it.

        Args:
            event (Any): The SDK's stream event.

        Returns:
            dict[str, Any] | None: The browser event, or None.
        """
        if event.type == 'text':
            return {
                'type': 'text',
                'text': event.text,
            }
        if event.type == 'thinking':
            return {
                'type': 'thinking',
                'text': event.thinking,
            }
        if event.type != 'content_block_start':
            return None
        block = event.content_block
        if block.type == 'text':
            return {
                'type': 'text_start',
            }
        if block.type == 'thinking':
            return {
                'type': 'thinking_start',
            }
        if block.type in ('tool_use', 'server_tool_use'):
            return {
                'type': 'tool_call',
                'id': block.id,
                'name': block.name,
            }
        if block.type == 'web_search_tool_result':
            return {
                'type': 'tool_result',
                'id': block.tool_use_id,
                'summary': self._web_search_summary(block.to_dict(mode='json')),
                'is_error': False,
            }
        return None

    async def _run_tools(
        self,
        conversation_id: str,
        history: list[dict[str, Any]],
        tool_uses: list[Any],
    ) -> AsyncIterator[dict[str, Any]]:
        """Runs every tool call of one answer at the same time and stores their results as one message.

        Args:
            conversation_id (str): The conversation's id.
            history (list[dict[str, Any]]): Every message so far, extended in place.
            tool_uses (list[Any]): The answer's tool_use blocks.

        Yields:
            dict[str, Any]: The tool calls' inputs, results and page instructions.
        """
        for block in tool_uses:
            yield {
                'type': 'tool_call',
                'id': block.id,
                'name': block.name,
                'input': block.input,
            }
        calls = []
        for block in tool_uses:
            calls.append(self._tools.call(block.name, block.input))
        outcomes = await asyncio.gather(*calls)
        results = []
        display = {}
        for block, outcome in zip(tool_uses, outcomes, strict=True):
            result = {
                'type': 'tool_result',
                'tool_use_id': block.id,
                'content': outcome.text(),
            }
            if outcome.is_error:
                result['is_error'] = True
            results.append(result)
            display[block.id] = {
                'summary': outcome.summary,
                'is_error': outcome.is_error,
                'ui_action': outcome.ui_action,
            }
            yield {
                'type': 'tool_result',
                'id': block.id,
                'summary': outcome.summary,
                'is_error': outcome.is_error,
            }
            if outcome.ui_action is not None:
                yield {
                    'type': 'ui_action',
                    'id': block.id,
                    'action': outcome.ui_action,
                }
        await self._conversations.append(
            conversation_id,
            'user',
            results,
            self._time_source.now(),
            None,
            display={
                'results': display,
            },
        )
        history.append(
            {
                'role': 'user',
                'content': results,
            }
        )

    async def _store(
        self,
        conversation_id: str,
        history: list[dict[str, Any]],
        role: str,
        content: list[dict[str, Any]],
        usage: Mapping[str, Any],
    ) -> None:
        """Appends a message to the stored conversation and to the history sent next.

        Args:
            conversation_id (str): The conversation's id.
            history (list[dict[str, Any]]): Every message so far, extended in place.
            role (str): The message's role.
            content (list[dict[str, Any]]): Its content blocks.
            usage (Mapping[str, Any]): The usage event of the answer.
        """
        tokens = {}
        for field in chat_usage_repository.USAGE_FIELDS:
            tokens[field] = usage.get(field, 0)
        await self._conversations.append(
            conversation_id,
            role,
            content,
            self._time_source.now(),
            tokens,
        )
        history.append(
            {
                'role': role,
                'content': content,
            }
        )

    def _content_dicts(self, message: Any) -> list[dict[str, Any]]:
        """Serialises an answer's content blocks exactly as the API sent them, so they can be sent back unchanged.

        Args:
            message (Any): The finished message.

        Returns:
            list[dict[str, Any]]: The content blocks.
        """
        content = []
        for block in message.content:
            content.append(block.to_dict(mode='json'))
        return content

    async def _record_usage(self, message: Any) -> dict[str, Any]:
        """Adds an answer's tokens to today's totals and describes them for the browser.

        Args:
            message (Any): The finished message.

        Returns:
            dict[str, Any]: A "usage" event with this answer's tokens, today's billable total and the daily limit.
        """
        tokens = {}
        for field in chat_usage_repository.USAGE_FIELDS:
            tokens[field] = int(getattr(message.usage, field, 0) or 0)
        _LOGGER.info(
            'Claude answer: model %s, stop %s, input %d, output %d, cache read %d, cache write %d',
            message.model,
            message.stop_reason,
            tokens['input_tokens'],
            tokens['output_tokens'],
            tokens['cache_read_input_tokens'],
            tokens['cache_creation_input_tokens'],
        )
        today = self._today()
        await self._usage.add(today, tokens)
        totals = await self._usage.day(today)
        event = {
            'type': 'usage',
            'model': message.model,
            'today': self._billable(totals),
            'limit': self._settings.claude_daily_token_limit,
        }
        event.update(tokens)
        return event

    async def usage_today(self) -> dict[str, Any]:
        """Describes today's token use against the daily limit.

        Returns:
            dict[str, Any]: Today's totals, "billable" (what the limit counts), "limit", "model" and "effort".
        """
        totals = await self._usage.day(self._today())
        answer = dict(totals)
        answer['day'] = self._today()
        answer['billable'] = self._billable(totals)
        answer['limit'] = self._settings.claude_daily_token_limit
        answer['model'] = self._settings.claude_model
        answer['effort'] = self._settings.claude_effort
        return answer

    async def _limit_message(self) -> str | None:
        """Checks today's tokens against the daily limit.

        Returns:
            str | None: Why no new turn may start, or None when one may.
        """
        totals = await self._usage.day(self._today())
        used = self._billable(totals)
        limit = self._settings.claude_daily_token_limit
        if used >= limit:
            return f"Today's limit of {limit:,} tokens is used up ({used:,} used). It resets at midnight India time, or raise INSTRUMENTS_EXPLORER_CLAUDE_DAILY_TOKEN_LIMIT."
        return None

    def _billable(self, totals: Mapping[str, int]) -> int:
        """Counts the tokens the daily limit applies to: input, output and cache writes, but not cache reads, which cost a twentieth as much.

        Args:
            totals (Mapping[str, int]): A day's totals.

        Returns:
            int: The count.
        """
        return (
            totals.get('input_tokens', 0)
            + totals.get('output_tokens', 0)
            + totals.get('cache_creation_input_tokens', 0)
        )

    def _context_text(self, page: Mapping[str, Any]) -> str:
        """Writes the context block that starts every user message.

        Args:
            page (Mapping[str, Any]): The page the user is on, with "path" and optionally "title".

        Returns:
            str: The block.
        """
        moment = datetime.datetime.fromtimestamp(self._time_source.now(), INDIA)
        lines = [
            CONTEXT_OPENING,
            f'Now: {moment:%A %d %B %Y, %H:%M} India time',
            f'Page: {page.get("path") or "/"}',
        ]
        if page.get('title'):
            lines.append(f'Page title: {page["title"]}')
        lines.append('</page_context>')
        return '\n'.join(lines)

    def _today(self) -> str:
        """Gives today's date in India.

        Returns:
            str: The date as "YYYY-MM-DD".
        """
        moment = datetime.datetime.fromtimestamp(self._time_source.now(), INDIA)
        return moment.date().isoformat()

    def _title_from(self, text: str) -> str:
        """Makes a conversation title from its first message.

        Args:
            text (str): The first message.

        Returns:
            str: The first line, cut to 60 characters.
        """
        first_line = (
            text.strip().splitlines()[0] if text.strip() else DEFAULT_TITLE
        )
        if len(first_line) > 60:
            return first_line[:59].rstrip() + '…'
        return first_line

    def _web_search_summary(self, block: Mapping[str, Any]) -> str:
        """Describes a web search result block in a few words.

        Args:
            block (Mapping[str, Any]): The web_search_tool_result block.

        Returns:
            str: How many pages were found, or the error code.
        """
        content = block.get('content')
        if isinstance(content, list):
            return (
                '1 web page'
                if len(content) == 1
                else f'{len(content)} web pages'
            )
        if isinstance(content, dict):
            return f'Web search failed: {content.get("error_code")}'
        return 'Web search'

    def _refusal(self, message: Any) -> dict[str, Any]:
        """Describes a declined answer.

        Args:
            message (Any): The finished message whose stop reason is "refusal".

        Returns:
            dict[str, Any]: A "refusal" event.
        """
        details = getattr(message, 'stop_details', None)
        explanation = getattr(details, 'explanation', None) if details else None
        return {
            'type': 'refusal',
            'text': explanation or 'Claude declined to answer this request.',
        }

    def _error(self, text: str) -> dict[str, Any]:
        """Makes an error event.

        Args:
            text (str): What went wrong.

        Returns:
            dict[str, Any]: An "error" event.
        """
        return {
            'type': 'error',
            'text': text,
        }
