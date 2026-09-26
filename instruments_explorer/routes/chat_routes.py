"""The chat assistant's routes: conversations, their messages, and the streamed answer.

The answer is streamed as Server-Sent Events from a POST, because the request carries the user's message. Each event is one line "event: <type>" and one line "data: <json>".

Typical usage example:

  web_application.include_router(ChatRoutes(parts, tools, guard, clock).router)
"""

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import anthropic
import fastapi
import fastapi.responses
import pydantic

from instruments_explorer.assistant import chat_session
from instruments_explorer.assistant import tool_box
from instruments_explorer.assistant import transcript_renderer
from instruments_explorer.configuration import settings
from instruments_explorer.security import session_guard
from instruments_explorer.storage import chat_usage_repository
from instruments_explorer.storage import conversation_repository
from instruments_explorer.utilities import clock

CONVERSATIONS_LISTED = 60
MAXIMUM_MESSAGE_CHARACTERS = 20000


class PageContext(pydantic.BaseModel):
    """The page the user is on when they send a message.

    Attributes:
        path: The page's address, such as "/instrument/<id>?indicator=rsi:14".
        title: The page's heading, when it has one.
    """

    path: str = pydantic.Field(default='/', max_length=2000)
    title: str = pydantic.Field(default='', max_length=300)


class MessageRequest(pydantic.BaseModel):
    """A message the user sends.

    Attributes:
        text: What the user wrote.
        page: The page they are on.
    """

    text: str = pydantic.Field(
        min_length=1, max_length=MAXIMUM_MESSAGE_CHARACTERS
    )
    page: PageContext = pydantic.Field(default_factory=PageContext)


class RenameRequest(pydantic.BaseModel):
    """A new title for a conversation.

    Attributes:
        title: The title.
    """

    title: str = pydantic.Field(min_length=1, max_length=120)


class ChatParts:
    """The chat assistant's components.

    Attributes:
        client: The Claude API client, or None while no API key is set.
        conversations: Stores conversations and messages.
        usage: Adds up tokens per day.
        explorer_settings: Supplies the model, effort and daily limit.
    """

    def __init__(
        self,
        client: anthropic.AsyncAnthropic | None,
        conversations: conversation_repository.ConversationRepository,
        usage: chat_usage_repository.ChatUsageRepository,
        explorer_settings: settings.Settings,
    ):
        """Keeps the components.

        Args:
            client (anthropic.AsyncAnthropic | None): The Claude API client, or None while no API key is set.
            conversations (conversation_repository.ConversationRepository): Stores conversations and messages.
            usage (chat_usage_repository.ChatUsageRepository): Adds up tokens per day.
            explorer_settings (settings.Settings): Supplies the model, effort and daily limit.
        """
        self.client = client
        self.conversations = conversations
        self.usage = usage
        self.explorer_settings = explorer_settings


class ChatRoutes:
    """The /api/chat routes.

    Attributes:
        parts: The assistant's components.
        router: The FastAPI router holding the routes.
    """

    def __init__(
        self,
        parts: ChatParts,
        tools: tool_box.ToolBox,
        guard: session_guard.SessionGuard,
        time_source: clock.SystemClock,
    ):
        """Creates the routes.

        Args:
            parts (ChatParts): The assistant's components.
            tools (tool_box.ToolBox): The tools Claude may call.
            guard (session_guard.SessionGuard): Requires a logged-in session, and the application header on changes.
            time_source (clock.SystemClock): The source of the current time.
        """
        self.parts = parts
        self._tools = tools
        self._time_source = time_source
        self._renderer = transcript_renderer.TranscriptRenderer()
        self.router = fastapi.APIRouter(
            prefix='/api/chat',
            dependencies=[
                fastapi.Depends(guard.require_session),
            ],
        )
        changes = [
            fastapi.Depends(guard.require_app_header),
        ]
        self.router.add_api_route(
            '/conversations',
            self.list_conversations,
            methods=[
                'GET',
            ],
        )
        self.router.add_api_route(
            '/conversations',
            self.create_conversation,
            methods=[
                'POST',
            ],
            dependencies=changes,
        )
        self.router.add_api_route(
            '/conversations/{conversation_id}',
            self.conversation,
            methods=[
                'GET',
            ],
        )
        self.router.add_api_route(
            '/conversations/{conversation_id}',
            self.rename_conversation,
            methods=[
                'PATCH',
            ],
            dependencies=changes,
        )
        self.router.add_api_route(
            '/conversations/{conversation_id}',
            self.delete_conversation,
            methods=[
                'DELETE',
            ],
            dependencies=changes,
        )
        self.router.add_api_route(
            '/conversations/{conversation_id}/messages',
            self.send_message,
            methods=[
                'POST',
            ],
            dependencies=changes,
        )
        self.router.add_api_route(
            '/usage',
            self.usage,
            methods=[
                'GET',
            ],
        )

    async def list_conversations(self) -> list[dict[str, Any]]:
        """Lists the latest conversations.

        Returns:
            list[dict[str, Any]]: The conversations, most recently used first.
        """
        return await self.parts.conversations.recent(CONVERSATIONS_LISTED)

    async def create_conversation(self) -> dict[str, Any]:
        """Starts an empty conversation.

        Returns:
            dict[str, Any]: The conversation.
        """
        return await self.parts.conversations.create(
            uuid.uuid4().hex,
            chat_session.DEFAULT_TITLE,
            self._time_source.now(),
        )

    async def conversation(self, conversation_id: str) -> dict[str, Any]:
        """Reads a conversation with the items the chat panel draws.

        Args:
            conversation_id (str): The conversation's id.

        Returns:
            dict[str, Any]: "conversation" and "items".

        Raises:
            fastapi.HTTPException: 404 for an unknown conversation.
        """
        conversation = await self._find(conversation_id)
        messages = await self.parts.conversations.messages(conversation_id)
        return {
            'conversation': conversation,
            'items': self._renderer.render(messages),
        }

    async def rename_conversation(
        self,
        conversation_id: str,
        body: RenameRequest,
    ) -> dict[str, Any]:
        """Renames a conversation.

        Args:
            conversation_id (str): The conversation's id.
            body (RenameRequest): The new title.

        Returns:
            dict[str, Any]: The renamed conversation.

        Raises:
            fastapi.HTTPException: 404 for an unknown conversation.
        """
        await self._find(conversation_id)
        await self.parts.conversations.rename(
            conversation_id, body.title.strip()
        )
        return await self._find(conversation_id)

    async def delete_conversation(self, conversation_id: str) -> dict[str, Any]:
        """Deletes a conversation and its messages.

        Args:
            conversation_id (str): The conversation's id.

        Returns:
            dict[str, Any]: {"deleted": the id}.

        Raises:
            fastapi.HTTPException: 404 for an unknown conversation.
        """
        await self._find(conversation_id)
        await self.parts.conversations.delete(conversation_id)
        return {
            'deleted': conversation_id,
        }

    async def send_message(
        self,
        conversation_id: str,
        body: MessageRequest,
    ) -> fastapi.responses.StreamingResponse:
        """Answers a message, streaming the answer as Server-Sent Events.

        Args:
            conversation_id (str): The conversation's id.
            body (MessageRequest): The message and the page the user is on.

        Returns:
            fastapi.responses.StreamingResponse: The event stream.

        Raises:
            fastapi.HTTPException: 503 while no API key is set, 404 for an unknown conversation.
        """
        if self.parts.client is None:
            raise fastapi.HTTPException(
                status_code=503,
                detail='The assistant has no API key. Set INSTRUMENTS_EXPLORER_ANTHROPIC_API_KEY in .env and restart.',
            )
        await self._find(conversation_id)
        session = chat_session.ChatSession(
            self.parts.client,
            self._tools,
            self.parts.conversations,
            self.parts.usage,
            self.parts.explorer_settings,
            self._time_source,
        )
        events = session.respond(
            conversation_id,
            body.text,
            body.page.model_dump(),
        )
        return fastapi.responses.StreamingResponse(
            self._encode(events),
            media_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
            },
        )

    async def usage(self) -> dict[str, Any]:
        """Describes today's token use against the daily limit.

        Returns:
            dict[str, Any]: Today's totals, the billable count, the limit, the model and the effort.
        """
        session = chat_session.ChatSession(
            self.parts.client,
            self._tools,
            self.parts.conversations,
            self.parts.usage,
            self.parts.explorer_settings,
            self._time_source,
        )
        return await session.usage_today()

    async def _find(self, conversation_id: str) -> dict[str, Any]:
        """Reads a conversation or answers 404.

        Args:
            conversation_id (str): The conversation's id.

        Returns:
            dict[str, Any]: The conversation.

        Raises:
            fastapi.HTTPException: 404 for an unknown conversation.
        """
        conversation = await self.parts.conversations.find(conversation_id)
        if conversation is None:
            raise fastapi.HTTPException(
                status_code=404,
                detail=f'No such conversation: {conversation_id!r}',
            )
        return conversation

    async def _encode(
        self,
        events: AsyncIterator[dict[str, Any]],
    ) -> AsyncIterator[str]:
        """Writes events in the Server-Sent Events format.

        Args:
            events (AsyncIterator[dict[str, Any]]): The session's events.

        Yields:
            str: One encoded event.
        """
        async for event in events:
            data = json.dumps(event, ensure_ascii=False, default=str)
            yield f'event: {event["type"]}\ndata: {data}\n\n'
