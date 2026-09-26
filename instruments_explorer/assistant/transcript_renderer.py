"""Turns a stored conversation into the items the chat panel draws.

Stored messages hold Claude's content blocks exactly as they are sent back to the API. The panel needs something simpler: the user's words without the page context block, text and thinking summaries, and tool calls with their results and page instructions.

Typical usage example:

  items = TranscriptRenderer().render(await conversations.messages(conversation_id))
"""

from collections.abc import Mapping, Sequence
from typing import Any

from instruments_explorer.assistant import chat_session


class TranscriptRenderer:
    """Converts stored messages into chat panel items."""

    def render(
        self, messages: Sequence[Mapping[str, Any]]
    ) -> list[dict[str, Any]]:
        """Converts a conversation's messages in order.

        Args:
            messages (Sequence[Mapping[str, Any]]): The stored messages.

        Returns:
            list[dict[str, Any]]: Items with a "kind" of "user", "text", "thinking", "tool_call" or "tool_result".
        """
        items = []
        for message in messages:
            if message['role'] == 'user':
                items.extend(self._user_items(message))
            else:
                items.extend(self._assistant_items(message))
        return items

    def _user_items(self, message: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Converts a user message: the user's own words, or tool results.

        Args:
            message (Mapping[str, Any]): The stored message.

        Returns:
            list[dict[str, Any]]: The items.
        """
        items = []
        results = (message.get('display') or {}).get('results', {})
        words = []
        for block in message['content']:
            if block.get('type') == 'text':
                if not block['text'].startswith(chat_session.CONTEXT_OPENING):
                    words.append(block['text'])
            elif block.get('type') == 'tool_result':
                shown = results.get(block['tool_use_id'], {})
                items.append(
                    {
                        'kind': 'tool_result',
                        'id': block['tool_use_id'],
                        'summary': shown.get('summary', ''),
                        'is_error': bool(block.get('is_error')),
                        'ui_action': shown.get('ui_action'),
                    }
                )
        if words:
            items.insert(
                0,
                {
                    'kind': 'user',
                    'text': '\n\n'.join(words),
                    'created_at': message.get('created_at'),
                },
            )
        return items

    def _assistant_items(
        self, message: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        """Converts an answer's text, thinking and tool blocks.

        Args:
            message (Mapping[str, Any]): The stored message.

        Returns:
            list[dict[str, Any]]: The items.
        """
        items = []
        for block in message['content']:
            kind = block.get('type')
            if kind == 'text' and block.get('text'):
                items.append(
                    {
                        'kind': 'text',
                        'text': block['text'],
                    }
                )
            elif kind == 'thinking' and block.get('thinking'):
                items.append(
                    {
                        'kind': 'thinking',
                        'text': block['thinking'],
                    }
                )
            elif kind in ('tool_use', 'server_tool_use'):
                items.append(
                    {
                        'kind': 'tool_call',
                        'id': block['id'],
                        'name': block['name'],
                        'input': block.get('input'),
                    }
                )
            elif kind == 'web_search_tool_result':
                content = block.get('content')
                count = len(content) if isinstance(content, list) else 0
                items.append(
                    {
                        'kind': 'tool_result',
                        'id': block['tool_use_id'],
                        'summary': '1 web page'
                        if count == 1
                        else f'{count} web pages',
                        'is_error': not isinstance(content, list),
                        'ui_action': None,
                    }
                )
        return items
