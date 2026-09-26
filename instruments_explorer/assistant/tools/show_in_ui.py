"""The show_in_ui tool: moves the user's page to a view, such as a chart with indicators or an option chain.

Typical usage example:

  outcome = await ShowInUiTool(services).run({'page': 'instrument', 'instrument_id': instrument_id, 'indicators': ['rsi:14']})
"""

import urllib.parse
from typing import Any, ClassVar

from instruments_explorer.assistant.tools import base


class ShowInUiTool(base.BaseTool):
    """Builds a page address from structured choices and tells the page to open it."""

    NAME = 'show_in_ui'
    DESCRIPTION = """Opens a view on the user's page next to the chat, so they can see what you are describing. Pages and the fields each one uses:
- instrument: instrument_id, with optional indicators (such as "rsi:14", "sma:50"), interval, days and view ("2d" or "3d") for its chart.
- explore: query and filters (exchange, asset_class, shape, option_type, expiry_month, sector).
- derivatives: exchange and underlying, with optional expiry and tab ("chain", "charts" or "surface").
- screener: conditions and sectors, with optional sort and descending.
- universe: optional instrument_id to fly to, and include_options.
- knowledge and overview: no fields.
Call it once, after you have the ids you need, when showing would help more than describing."""
    INPUT_SCHEMA: ClassVar[dict[str, Any]] = {
        'type': 'object',
        'properties': {
            'page': {
                'type': 'string',
                'enum': [
                    'instrument',
                    'explore',
                    'derivatives',
                    'screener',
                    'universe',
                    'knowledge',
                    'overview',
                ],
            },
            'instrument_id': {
                'type': 'string',
            },
            'indicators': {
                'type': 'array',
                'items': {
                    'type': 'string',
                },
            },
            'interval': {
                'type': 'string',
            },
            'days': {
                'type': 'integer',
            },
            'view': {
                'type': 'string',
                'enum': [
                    '2d',
                    '3d',
                ],
            },
            'query': {
                'type': 'string',
            },
            'exchange': {
                'type': 'string',
            },
            'asset_class': {
                'type': 'string',
            },
            'shape': {
                'type': 'string',
            },
            'option_type': {
                'type': 'string',
            },
            'expiry_month': {
                'type': 'string',
            },
            'sector': {
                'type': 'string',
            },
            'underlying': {
                'type': 'string',
            },
            'expiry': {
                'type': 'string',
            },
            'tab': {
                'type': 'string',
                'enum': [
                    'chain',
                    'charts',
                    'surface',
                ],
            },
            'conditions': {
                'type': 'array',
                'items': {
                    'type': 'string',
                },
            },
            'sectors': {
                'type': 'array',
                'items': {
                    'type': 'string',
                },
            },
            'sort': {
                'type': 'string',
            },
            'descending': {
                'type': 'boolean',
            },
            'include_options': {
                'type': 'boolean',
            },
            'label': {
                'type': 'string',
                'description': 'A few words naming the view, shown on the link in the chat.',
            },
        },
        'required': [
            'page',
        ],
        'additionalProperties': False,
    }

    async def run(self, arguments: dict[str, Any]) -> base.ToolOutcome:
        """Builds the address and asks the page to open it.

        Args:
            arguments (dict[str, Any]): The checked input.

        Returns:
            base.ToolOutcome: The address, with the navigation instruction for the page.

        Raises:
            base.ToolError: A field the page needs is missing.
        """
        page = arguments['page']
        if page == 'instrument':
            path = self._instrument(arguments)
        elif page == 'explore':
            path = self._with_query('/explore', self._explore_query(arguments))
        elif page == 'derivatives':
            path = self._derivatives(arguments)
        elif page == 'screener':
            path = self._with_query(
                '/screener', self._screener_query(arguments)
            )
        elif page == 'universe':
            path = self._with_query(
                '/universe', self._universe_query(arguments)
            )
        else:
            path = f'/{page}'
        label = arguments.get('label') or page.title()
        return base.ToolOutcome(
            {
                'shown': path,
            },
            f'Showing {label}',
            ui_action={
                'kind': 'navigate',
                'path': path,
                'label': label,
            },
        )

    def _instrument(self, arguments: dict[str, Any]) -> str:
        """Builds an instrument page address with its chart settings.

        Args:
            arguments (dict[str, Any]): The checked input.

        Returns:
            str: The address.

        Raises:
            base.ToolError: The instrument id is missing.
        """
        if 'instrument_id' not in arguments:
            raise base.ToolError('The instrument page needs instrument_id.')
        query = []
        for indicator in arguments.get('indicators', []):
            query.append(('indicator', indicator))
        for name in [
            'interval',
            'days',
            'view',
        ]:
            if name in arguments:
                query.append((name, str(arguments[name])))
        instrument_id = urllib.parse.quote(arguments['instrument_id'], safe='')
        return self._with_query(f'/instrument/{instrument_id}', query)

    def _explore_query(
        self, arguments: dict[str, Any]
    ) -> list[tuple[str, str]]:
        """Builds the Explore page's search and filters.

        Args:
            arguments (dict[str, Any]): The checked input.

        Returns:
            list[tuple[str, str]]: The query pairs.
        """
        query = []
        if 'query' in arguments:
            query.append(('q', arguments['query']))
        for name in [
            'exchange',
            'asset_class',
            'shape',
            'option_type',
            'expiry_month',
            'sector',
        ]:
            if name in arguments:
                query.append((name, arguments[name]))
        return query

    def _derivatives(self, arguments: dict[str, Any]) -> str:
        """Builds a derivatives page address.

        Args:
            arguments (dict[str, Any]): The checked input.

        Returns:
            str: The address.

        Raises:
            base.ToolError: The exchange or underlying is missing.
        """
        if 'exchange' not in arguments or 'underlying' not in arguments:
            raise base.ToolError(
                'The derivatives page needs exchange and underlying.'
            )
        query = [
            ('exchange', arguments['exchange']),
            ('underlying', arguments['underlying'].upper()),
        ]
        for name in [
            'expiry',
            'tab',
        ]:
            if name in arguments:
                query.append((name, arguments[name]))
        return self._with_query('/derivatives', query)

    def _screener_query(
        self, arguments: dict[str, Any]
    ) -> list[tuple[str, str]]:
        """Builds the screener page's conditions, sectors and order.

        Args:
            arguments (dict[str, Any]): The checked input.

        Returns:
            list[tuple[str, str]]: The query pairs.
        """
        query = []
        for condition in arguments.get('conditions', []):
            query.append(('condition', condition))
        for sector in arguments.get('sectors', []):
            query.append(('sector', sector))
        if 'sort' in arguments:
            query.append(('sort', arguments['sort']))
        if arguments.get('descending'):
            query.append(('descending', 'true'))
        return query

    def _universe_query(
        self, arguments: dict[str, Any]
    ) -> list[tuple[str, str]]:
        """Builds the universe page's options switch and instrument to fly to.

        Args:
            arguments (dict[str, Any]): The checked input.

        Returns:
            list[tuple[str, str]]: The query pairs.
        """
        query = []
        if arguments.get('include_options'):
            query.append(('options', 'true'))
        if 'instrument_id' in arguments:
            query.append(('focus', arguments['instrument_id']))
        return query

    def _with_query(self, path: str, query: list[tuple[str, str]]) -> str:
        """Joins a path and its query pairs.

        Args:
            path (str): The page path.
            query (list[tuple[str, str]]): The query pairs, which may repeat a name.

        Returns:
            str: The address.
        """
        if not query:
            return path
        return f'{path}?{urllib.parse.urlencode(query)}'
