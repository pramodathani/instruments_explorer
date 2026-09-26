"""The shared mechanism of every assistant tool: its definition for Claude, input checking, and error handling.

Typical usage example:

  class GetQuoteTool(BaseTool):
      NAME = 'get_quote'
      ...
      async def run(self, arguments):
          quote = await self.call_route(self.services.instruments.quote(arguments['instrument_id']))
          return ToolOutcome(quote, 'Quote read')
"""

import json
from collections.abc import Awaitable, Mapping
from typing import Any, ClassVar

import fastapi

from instruments_explorer.assistant import assistant_services

MAXIMUM_RESULT_CHARACTERS = 24000

_JSON_TYPES = {
    'string': (str,),
    'integer': (int,),
    'number': (
        int,
        float,
    ),
    'boolean': (bool,),
    'array': (list,),
    'object': (dict,),
}


class ToolError(Exception):
    """A tool could not do what it was asked, for a reason Claude should read."""


class ToolOutcome:
    """What one tool call produced.

    Attributes:
        content: The result for Claude, serialised to JSON when it is not already text.
        summary: A short line for the chat panel's tool card.
        ui_action: An instruction for the page, such as navigating, or None.
        is_error: Whether the call failed.
    """

    def __init__(
        self,
        content: Any,
        summary: str,
        ui_action: dict[str, Any] | None = None,
        is_error: bool = False,
    ):
        """Creates the outcome.

        Args:
            content (Any): The result for Claude.
            summary (str): A short line for the chat panel's tool card.
            ui_action (dict[str, Any] | None): An instruction for the page, or None.
            is_error (bool): Whether the call failed.
        """
        self.content = content
        self.summary = summary
        self.ui_action = ui_action
        self.is_error = is_error

    def text(self) -> str:
        """Gives the result as the text sent back to Claude, cut short when very long.

        Returns:
            str: The text.
        """
        if isinstance(self.content, str):
            text = self.content
        else:
            text = json.dumps(self.content, ensure_ascii=False, default=str)
        if len(text) > MAXIMUM_RESULT_CHARACTERS:
            text = (
                text[:MAXIMUM_RESULT_CHARACTERS]
                + ' [cut short: ask for a narrower result]'
            )
        return text


class BaseTool:
    """A tool Claude can call, described by a name, a description and a JSON schema for its input.

    Subclasses set NAME, DESCRIPTION and INPUT_SCHEMA and implement run().

    Attributes:
        services: The route groups the tool calls.
    """

    NAME = ''
    DESCRIPTION = ''
    INPUT_SCHEMA: ClassVar[dict[str, Any]] = {}

    def __init__(self, services: assistant_services.AssistantServices):
        """Keeps the route groups.

        Args:
            services (assistant_services.AssistantServices): The route groups the tool calls.
        """
        self.services = services

    def definition(self) -> dict[str, Any]:
        """Describes the tool for Claude's tools list.

        Returns:
            dict[str, Any]: The tool definition, with eager input streaming so inputs arrive as they are written.
        """
        return {
            'name': self.NAME,
            'description': self.DESCRIPTION,
            'input_schema': self.INPUT_SCHEMA,
            'eager_input_streaming': True,
        }

    def problems(self, arguments: Any) -> list[str]:
        """Checks an input against the schema's properties, required fields, types and allowed values.

        With eager input streaming the server no longer validates inputs, so every input is checked here before the tool runs.

        Args:
            arguments (Any): The input Claude wrote.

        Returns:
            list[str]: What is wrong, empty when the input is acceptable.
        """
        if not isinstance(arguments, dict):
            return [
                'The input must be a JSON object.',
            ]
        properties = self.INPUT_SCHEMA.get('properties', {})
        found = []
        for name in self.INPUT_SCHEMA.get('required', []):
            if name not in arguments:
                found.append(f'Missing required field {name!r}.')
        for name, value in arguments.items():
            schema = properties.get(name)
            if schema is None:
                found.append(f'Unknown field {name!r}.')
                continue
            found.extend(self._value_problems(name, value, schema))
        return found

    async def run(self, arguments: dict[str, Any]) -> ToolOutcome:
        """Does the tool's work.

        Args:
            arguments (dict[str, Any]): The checked input.

        Returns:
            ToolOutcome: The result.

        Raises:
            ToolError: The work could not be done.
        """
        raise NotImplementedError

    async def call_route(self, call: Awaitable[Any]) -> Any:
        """Awaits a route handler, turning its HTTP error into a ToolError with the same message.

        Args:
            call (Awaitable[Any]): The handler's coroutine.

        Returns:
            Any: What the handler returned.

        Raises:
            ToolError: The handler raised an HTTP error.
        """
        try:
            return await call
        except fastapi.HTTPException as error:
            raise ToolError(str(error.detail)) from error

    def _value_problems(
        self,
        name: str,
        value: Any,
        schema: Mapping[str, Any],
    ) -> list[str]:
        """Checks one value against its property schema.

        Args:
            name (str): The field's name, for messages.
            value (Any): The value.
            schema (Mapping[str, Any]): The property's schema.

        Returns:
            list[str]: What is wrong with the value.
        """
        expected = _JSON_TYPES.get(schema.get('type', ''), (object,))
        is_boolean = isinstance(value, bool)
        if not isinstance(value, expected) or (
            is_boolean and schema.get('type') != 'boolean'
        ):
            return [
                f'Field {name!r} must be of type {schema.get("type")}.',
            ]
        if 'enum' in schema and value not in schema['enum']:
            return [
                f'Field {name!r} must be one of {schema["enum"]}.',
            ]
        if schema.get('type') == 'array' and 'items' in schema:
            found = []
            for position, item in enumerate(value):
                found.extend(
                    self._value_problems(
                        f'{name}[{position}]',
                        item,
                        schema['items'],
                    )
                )
            return found
        return []
