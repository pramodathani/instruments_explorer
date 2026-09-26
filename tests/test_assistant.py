"""Tests for the chat assistant: its routes, conversation loop, tools and transcript."""

import asyncio
import json
from pathlib import Path
from typing import Any

import anthropic
import httpx

from instruments_explorer.assistant import transcript_renderer
from instruments_explorer.assistant.tools import show_in_ui
from tests import fakes
from tests import test_routes

_HEADERS = {
    'X-Requested-With': 'instruments-explorer',
}


class ChatClient:
    """Drives the chat routes of a RouteParts application.

    Attributes:
        parts: The application under test.
    """

    def __init__(self, parts: test_routes.RouteParts):
        """Logs in.

        Args:
            parts (test_routes.RouteParts): The application under test.
        """
        self.parts = parts
        parts.log_in()

    def new_conversation(self) -> str:
        """Creates a conversation.

        Returns:
            str: Its id.
        """
        response = self.parts.client.post(
            '/api/chat/conversations',
            headers=_HEADERS,
        )
        assert response.status_code == 200
        return response.json()['conversation_id']

    def send(self, conversation_id: str, text: str) -> list[dict[str, Any]]:
        """Sends a message and reads the whole event stream.

        Args:
            conversation_id (str): The conversation.
            text (str): The message.

        Returns:
            list[dict[str, Any]]: The events in order.
        """
        response = self.parts.client.post(
            f'/api/chat/conversations/{conversation_id}/messages',
            json={
                'text': text,
                'page': {
                    'path': '/overview',
                    'title': 'Overview',
                },
            },
            headers=_HEADERS,
        )
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('text/event-stream')
        events = []
        for chunk in response.text.split('\n\n'):
            for line in chunk.splitlines():
                if line.startswith('data: '):
                    events.append(json.loads(line[len('data: ') :]))
        return events

    def items(self, conversation_id: str) -> list[dict[str, Any]]:
        """Reads the conversation as the chat panel draws it.

        Args:
            conversation_id (str): The conversation.

        Returns:
            list[dict[str, Any]]: The items.
        """
        return self.parts.client.get(
            f'/api/chat/conversations/{conversation_id}'
        ).json()['items']


def _text(text: str) -> dict[str, Any]:
    """Makes a text block.

    Args:
        text (str): The text.

    Returns:
        dict[str, Any]: The block.
    """
    return {
        'type': 'text',
        'text': text,
        'citations': None,
    }


def _tool_use(
    tool_id: str, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Makes a tool_use block.

    Args:
        tool_id (str): The call's id.
        name (str): The tool's name.
        arguments (dict[str, Any]): The input.

    Returns:
        dict[str, Any]: The block.
    """
    return {
        'type': 'tool_use',
        'id': tool_id,
        'name': name,
        'input': arguments,
    }


def _types(events: list[dict[str, Any]]) -> list[str]:
    """Lists the events' types.

    Args:
        events (list[dict[str, Any]]): The events.

    Returns:
        list[str]: Their types in order.
    """
    found = []
    for event in events:
        found.append(event['type'])
    return found


class TestChatRoutes:
    """Tests for the /api/chat routes and the conversation loop."""

    def test_without_a_key_messages_are_refused(self, tmp_path: Path) -> None:
        """Checks that conversations work but messages answer 503 while no key is set.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = test_routes.RouteParts(tmp_path / 'dist', tmp_path / 'index')
        chat = ChatClient(parts)
        conversation_id = chat.new_conversation()
        response = parts.client.post(
            f'/api/chat/conversations/{conversation_id}/messages',
            json={
                'text': 'hello',
            },
            headers=_HEADERS,
        )
        assert response.status_code == 503

    def test_a_plain_answer(self, tmp_path: Path) -> None:
        """Checks the events, the stored transcript and the request sent to Claude for a text answer.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = test_routes.RouteParts(
            tmp_path / 'dist',
            tmp_path / 'index',
            api_key='test key',
            claude_turns=[
                fakes.FakeTurn(
                    [
                        {
                            'type': 'thinking',
                            'thinking': 'The user greets me.',
                            'signature': 'signature-1',
                        },
                        _text('Hello! Ask me about any instrument.'),
                    ],
                    'end_turn',
                ),
            ],
        )
        chat = ChatClient(parts)
        conversation_id = chat.new_conversation()
        events = chat.send(conversation_id, 'Hello there')
        assert _types(events) == [
            'title',
            'thinking_start',
            'thinking',
            'text_start',
            'text',
            'usage',
            'done',
        ]
        assert events[0]['title'] == 'Hello there'
        request = parts.claude.messages.requests[0]
        assert request['model'] == 'claude-opus-5-5'
        assert request['thinking'] == {
            'type': 'adaptive',
            'display': 'summarized',
        }
        assert request['output_config'] == {
            'effort': 'high',
        }
        assert request['fallbacks'] == 'default'
        assert request['betas'] == [
            'server-side-fallback-2026-07-01',
        ]
        assert request['system'][0]['cache_control'] == {
            'type': 'ephemeral',
        }
        assert 'tool_choice' not in request
        first_block = request['messages'][0]['content'][0]['text']
        assert first_block.startswith('<page_context>')
        assert 'Page: /overview' in first_block
        items = chat.items(conversation_id)
        kinds = []
        for item in items:
            kinds.append(item['kind'])
        assert kinds == [
            'user',
            'thinking',
            'text',
        ]
        assert items[0]['text'] == 'Hello there'

    def test_history_is_sent_back_unchanged(self, tmp_path: Path) -> None:
        """Checks that the second request replays the first answer's blocks exactly, thinking signature included.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        first_answer = [
            {
                'type': 'thinking',
                'thinking': 'Short.',
                'signature': 'signature-1',
            },
            _text('First answer.'),
        ]
        parts = test_routes.RouteParts(
            tmp_path / 'dist',
            tmp_path / 'index',
            api_key='test key',
            claude_turns=[
                fakes.FakeTurn(first_answer, 'end_turn'),
                fakes.FakeTurn(
                    [
                        _text('Second answer.'),
                    ],
                    'end_turn',
                ),
            ],
        )
        chat = ChatClient(parts)
        conversation_id = chat.new_conversation()
        chat.send(conversation_id, 'One')
        chat.send(conversation_id, 'Two')
        second = parts.claude.messages.requests[1]
        assert second['messages'][1] == {
            'role': 'assistant',
            'content': first_answer,
        }
        assert (
            second['messages'][0]
            == parts.claude.messages.requests[0]['messages'][0]
        )
        assert len(second['messages']) == 3

    def test_tools_run_and_move_the_page(self, tmp_path: Path) -> None:
        """Checks a round of two parallel tool calls, their results sent back, and the page instruction.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = test_routes.RouteParts(
            tmp_path / 'dist',
            tmp_path / 'index',
            api_key='test key',
            claude_turns=[
                fakes.FakeTurn(
                    [
                        _tool_use(
                            'call-1',
                            'search_instruments',
                            {
                                'query': 'reliance',
                                'shape': 'security',
                            },
                        ),
                        _tool_use(
                            'call-2',
                            'show_in_ui',
                            {
                                'page': 'instrument',
                                'instrument_id': fakes.RELIANCE_NSE_ID,
                                'indicators': [
                                    'rsi:14',
                                    'sma:50',
                                ],
                            },
                        ),
                    ],
                    'tool_use',
                ),
                fakes.FakeTurn(
                    [
                        _text('Here is Reliance with RSI.'),
                    ],
                    'end_turn',
                ),
            ],
        )
        chat = ChatClient(parts)
        conversation_id = chat.new_conversation()
        events = chat.send(conversation_id, 'Chart Reliance with RSI')
        actions = []
        results = []
        for event in events:
            if event['type'] == 'ui_action':
                actions.append(event['action'])
            if event['type'] == 'tool_result':
                results.append(event)
        assert actions == [
            {
                'kind': 'navigate',
                'path': f'/instrument/{fakes.RELIANCE_NSE_ID}?indicator=rsi%3A14&indicator=sma%3A50',
                'label': 'Instrument',
            },
        ]
        assert len(results) == 2
        assert not results[0]['is_error']
        second = parts.claude.messages.requests[1]
        tool_results = second['messages'][2]['content']
        assert tool_results[0]['tool_use_id'] == 'call-1'
        assert 'RELIANCE' in tool_results[0]['content']
        assert tool_results[1]['tool_use_id'] == 'call-2'
        items = chat.items(conversation_id)
        shown = []
        for item in items:
            if item['kind'] == 'tool_result' and item['ui_action'] is not None:
                shown.append(item['ui_action']['kind'])
        assert shown == [
            'navigate',
        ]

    def test_an_invalid_tool_input_is_reported_to_claude(
        self, tmp_path: Path
    ) -> None:
        """Checks that an input that breaks the schema returns an error result instead of running.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = test_routes.RouteParts(
            tmp_path / 'dist',
            tmp_path / 'index',
            api_key='test key',
            claude_turns=[
                fakes.FakeTurn(
                    [
                        _tool_use(
                            'call-1',
                            'search_instruments',
                            {
                                'query': 42,
                                'colour': 'red',
                            },
                        ),
                    ],
                    'tool_use',
                ),
                fakes.FakeTurn(
                    [
                        _text('Sorry.'),
                    ],
                    'end_turn',
                ),
            ],
        )
        chat = ChatClient(parts)
        chat.send(chat.new_conversation(), 'Search')
        result = parts.claude.messages.requests[1]['messages'][2]['content'][0]
        assert result['is_error'] is True
        assert "Field 'query' must be of type string." in result['content']
        assert "Unknown field 'colour'." in result['content']

    def test_a_refusal_is_not_stored(self, tmp_path: Path) -> None:
        """Checks that a declined answer is reported and left out of the history.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = test_routes.RouteParts(
            tmp_path / 'dist',
            tmp_path / 'index',
            api_key='test key',
            claude_turns=[
                fakes.FakeTurn(
                    [],
                    'refusal',
                ),
            ],
        )
        chat = ChatClient(parts)
        conversation_id = chat.new_conversation()
        events = chat.send(conversation_id, 'Something declined')
        assert 'refusal' in _types(events)
        kinds = []
        for item in chat.items(conversation_id):
            kinds.append(item['kind'])
        assert kinds == [
            'user',
        ]

    def test_an_api_error_is_reported(self, tmp_path: Path) -> None:
        """Checks that a rate limit ends the turn with a readable error.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        request = httpx.Request('POST', 'https://api.anthropic.com/v1/messages')
        response = httpx.Response(429, request=request)
        error = anthropic.RateLimitError(
            'rate limited', response=response, body=None
        )
        parts = test_routes.RouteParts(
            tmp_path / 'dist',
            tmp_path / 'index',
            api_key='test key',
            claude_turns=[
                fakes.FakeTurn(
                    [],
                    'end_turn',
                    fails_with=error,
                ),
            ],
        )
        chat = ChatClient(parts)
        events = chat.send(chat.new_conversation(), 'Hello')
        assert events[-2]['type'] == 'error'
        assert 'rate limiting' in events[-2]['text']
        assert events[-1]['type'] == 'done'

    def test_the_daily_limit_stops_new_turns(self, tmp_path: Path) -> None:
        """Checks that no request is made once today's tokens reach the limit.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = test_routes.RouteParts(
            tmp_path / 'dist',
            tmp_path / 'index',
            api_key='test key',
        )
        asyncio.run(
            parts.chat_usage.add(
                '2026-09-26',
                {
                    'input_tokens': 2000000,
                },
            )
        )
        chat = ChatClient(parts)
        events = chat.send(chat.new_conversation(), 'Hello')
        assert events[0]['type'] == 'error'
        assert 'limit' in events[0]['text']
        assert parts.claude.messages.requests == []

    def test_rename_delete_and_the_header(self, tmp_path: Path) -> None:
        """Checks renaming, deleting, listing and the application header on changes.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = test_routes.RouteParts(tmp_path / 'dist', tmp_path / 'index')
        chat = ChatClient(parts)
        conversation_id = chat.new_conversation()
        assert parts.client.post('/api/chat/conversations').status_code == 403
        renamed = parts.client.patch(
            f'/api/chat/conversations/{conversation_id}',
            json={
                'title': 'Options research',
            },
            headers=_HEADERS,
        ).json()
        assert renamed['title'] == 'Options research'
        listed = parts.client.get('/api/chat/conversations').json()
        assert listed[0]['conversation_id'] == conversation_id
        deleted = parts.client.delete(
            f'/api/chat/conversations/{conversation_id}',
            headers=_HEADERS,
        )
        assert deleted.status_code == 200
        missing = parts.client.get(f'/api/chat/conversations/{conversation_id}')
        assert missing.status_code == 404

    def test_usage(self, tmp_path: Path) -> None:
        """Checks the usage route counts input, output and cache writes but not cache reads.

        Args:
            tmp_path (Path): A temporary directory from pytest.
        """
        parts = test_routes.RouteParts(tmp_path / 'dist', tmp_path / 'index')
        asyncio.run(
            parts.chat_usage.add(
                '2026-09-26',
                {
                    'input_tokens': 10,
                    'output_tokens': 5,
                    'cache_read_input_tokens': 1000,
                    'cache_creation_input_tokens': 20,
                },
            )
        )
        ChatClient(parts)
        body = parts.client.get('/api/chat/usage').json()
        assert body['billable'] == 35
        assert body['cache_read_input_tokens'] == 1000
        assert body['model'] == 'claude-opus-5-5'


class TestShowInUi:
    """Tests for the page addresses show_in_ui builds."""

    def _path(self, arguments: dict[str, Any]) -> str:
        """Runs the tool and returns the address it asks the page to open.

        Args:
            arguments (dict[str, Any]): The input.

        Returns:
            str: The address.
        """
        tool = show_in_ui.ShowInUiTool(None)
        outcome = asyncio.run(tool.run(arguments))
        return outcome.ui_action['path']

    def test_derivatives(self) -> None:
        """Checks a derivatives address with an expiry and tab."""
        path = self._path(
            {
                'page': 'derivatives',
                'exchange': 'nse',
                'underlying': 'nifty',
                'expiry': '2026-09-29',
                'tab': 'surface',
            }
        )
        assert (
            path
            == '/derivatives?exchange=nse&underlying=NIFTY&expiry=2026-09-29&tab=surface'
        )

    def test_screener(self) -> None:
        """Checks a screener address with repeated conditions."""
        path = self._path(
            {
                'page': 'screener',
                'conditions': [
                    'rsi:0:30',
                    'above_average:200',
                ],
                'sectors': [
                    'Information Technology',
                ],
                'descending': True,
            }
        )
        assert (
            path
            == '/screener?condition=rsi%3A0%3A30&condition=above_average%3A200&sector=Information+Technology&descending=true'
        )

    def test_universe_focus(self) -> None:
        """Checks a universe address that flies to an instrument."""
        path = self._path(
            {
                'page': 'universe',
                'instrument_id': 'abc',
                'include_options': True,
            }
        )
        assert path == '/universe?options=true&focus=abc'


class TestTranscriptRenderer:
    """Tests for TranscriptRenderer."""

    def test_web_search_and_context_blocks(self) -> None:
        """Checks that the context block is hidden and a web search becomes a call with a result."""
        messages = [
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'text',
                        'text': '<page_context>\nPage: /\n</page_context>',
                    },
                    {
                        'type': 'text',
                        'text': 'Any news on TCS?',
                    },
                ],
            },
            {
                'role': 'assistant',
                'content': [
                    {
                        'type': 'server_tool_use',
                        'id': 'search-1',
                        'name': 'web_search',
                        'input': {
                            'query': 'TCS news',
                        },
                    },
                    {
                        'type': 'web_search_tool_result',
                        'tool_use_id': 'search-1',
                        'content': [
                            {
                                'type': 'web_search_result',
                                'url': 'https://example.com',
                                'title': 'TCS results',
                            },
                        ],
                    },
                    _text('TCS reported results.'),
                ],
            },
        ]
        items = transcript_renderer.TranscriptRenderer().render(messages)
        assert items[0]['text'] == 'Any news on TCS?'
        assert items[1]['kind'] == 'tool_call'
        assert items[2]['summary'] == '1 web page'
        assert items[3]['kind'] == 'text'
