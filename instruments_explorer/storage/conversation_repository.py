"""The chat_conversations and chat_messages collections: the assistant's conversations, kept append-only.

A message is never edited after it is stored, because Claude checks that the thinking blocks it is sent back belong to an unchanged conversation. A conversation can be renamed or deleted as a whole.

Typical usage example:

  conversations = ConversationRepository(connection.database())
  await conversations.create(conversation_id, 'New chat', now)
  await conversations.append(conversation_id, 'user', content, now, None)
"""

from collections.abc import Mapping, Sequence
from typing import Any

_CONVERSATIONS = 'chat_conversations'
_MESSAGES = 'chat_messages'


class ConversationRepository:
    """Reads and writes chat conversations and their messages in the project's own MongoDB."""

    def __init__(self, database: Any):
        """Wraps the project's database.

        Args:
            database (Any): A pymongo AsyncDatabase, or a stand-in with the same collection methods.
        """
        self._conversations = database[_CONVERSATIONS]
        self._messages = database[_MESSAGES]

    async def ensure_indexes(self) -> None:
        """Creates the indexes the conversation list and message reads use."""
        await self._conversations.create_index('updated_at')
        await self._messages.create_index('conversation_id')

    async def create(
        self,
        conversation_id: str,
        title: str,
        now: float,
    ) -> dict[str, Any]:
        """Stores a new, empty conversation.

        Args:
            conversation_id (str): The new conversation's id.
            title (str): Its title.
            now (float): The time as epoch seconds.

        Returns:
            dict[str, Any]: The conversation.
        """
        conversation = {
            '_id': conversation_id,
            'conversation_id': conversation_id,
            'title': title,
            'created_at': now,
            'updated_at': now,
            'message_count': 0,
            'input_tokens': 0,
            'output_tokens': 0,
        }
        await self._conversations.replace_one(
            {
                '_id': conversation_id,
            },
            conversation,
            upsert=True,
        )
        return self._clean(conversation)

    async def recent(self, limit: int) -> list[dict[str, Any]]:
        """Lists the latest conversations, most recently used first.

        Args:
            limit (int): The largest number of conversations.

        Returns:
            list[dict[str, Any]]: The conversations.
        """
        cursor = (
            self._conversations.find({}).sort('updated_at', -1).limit(limit)
        )
        conversations = []
        async for document in cursor:
            conversations.append(self._clean(document))
        return conversations

    async def find(self, conversation_id: str) -> dict[str, Any] | None:
        """Reads one conversation.

        Args:
            conversation_id (str): The conversation's id.

        Returns:
            dict[str, Any] | None: The conversation, or None when it does not exist.
        """
        document = await self._conversations.find_one(
            {
                '_id': conversation_id,
            }
        )
        if document is None:
            return None
        return self._clean(document)

    async def rename(self, conversation_id: str, title: str) -> None:
        """Changes a conversation's title.

        Args:
            conversation_id (str): The conversation's id.
            title (str): The new title.
        """
        await self._conversations.update_one(
            {
                '_id': conversation_id,
            },
            {
                '$set': {
                    'title': title,
                },
            },
        )

    async def delete(self, conversation_id: str) -> None:
        """Deletes a conversation and every message in it.

        Args:
            conversation_id (str): The conversation's id.
        """
        await self._messages.delete_many(
            {
                'conversation_id': conversation_id,
            }
        )
        await self._conversations.delete_one(
            {
                '_id': conversation_id,
            }
        )

    async def append(
        self,
        conversation_id: str,
        role: str,
        content: Sequence[Mapping[str, Any]],
        now: float,
        usage: Mapping[str, int] | None,
        display: Mapping[str, Any] | None = None,
    ) -> int:
        """Adds a message to the end of a conversation.

        Args:
            conversation_id (str): The conversation's id.
            role (str): "user" or "assistant".
            content (Sequence[Mapping[str, Any]]): The message's content blocks, exactly as they will be sent back to Claude.
            now (float): The time as epoch seconds.
            usage (Mapping[str, int] | None): The tokens an assistant message used, or None.
            display (Mapping[str, Any] | None): Extra facts for showing the message in the chat panel that are never sent to Claude, such as tool result summaries, or None.

        Returns:
            int: The message's position in the conversation, counting from 0.

        Raises:
            LookupError: The conversation does not exist.
        """
        conversation = await self._conversations.find_one(
            {
                '_id': conversation_id,
            }
        )
        if conversation is None:
            raise LookupError(f'No such conversation: {conversation_id!r}')
        sequence = conversation.get('message_count', 0)
        await self._messages.insert_one(
            {
                '_id': f'{conversation_id}:{sequence:06d}',
                'conversation_id': conversation_id,
                'sequence': sequence,
                'role': role,
                'content': list(content),
                'created_at': now,
                'usage': dict(usage) if usage is not None else None,
                'display': dict(display) if display is not None else None,
            }
        )
        increments = {
            'message_count': 1,
        }
        if usage is not None:
            increments['input_tokens'] = usage.get('input_tokens', 0)
            increments['output_tokens'] = usage.get('output_tokens', 0)
        await self._conversations.update_one(
            {
                '_id': conversation_id,
            },
            {
                '$set': {
                    'updated_at': now,
                },
                '$inc': increments,
            },
        )
        return sequence

    async def messages(self, conversation_id: str) -> list[dict[str, Any]]:
        """Reads every message of a conversation in order.

        Args:
            conversation_id (str): The conversation's id.

        Returns:
            list[dict[str, Any]]: The messages, each with "sequence", "role", "content", "created_at", "usage" and "display".
        """
        cursor = self._messages.find(
            {
                'conversation_id': conversation_id,
            }
        ).sort('sequence', 1)
        messages = []
        async for document in cursor:
            messages.append(self._clean(document))
        return messages

    def _clean(self, document: Mapping[str, Any]) -> dict[str, Any]:
        """Removes MongoDB's _id from a document.

        Args:
            document (Mapping[str, Any]): The stored document.

        Returns:
            dict[str, Any]: A copy without _id.
        """
        cleaned = dict(document)
        cleaned.pop('_id', None)
        return cleaned
