"""The read-only client for the unified broker interface's REST API.

Every request carries UBI's access token from the token provider. A request refused with 401 is retried once with the token the provider finds after the refusal. The client only reads: it has no order, portfolio or session routes.

Typical usage example:

  client = UnifiedBrokerInterfaceClient(http_client, provider)
  segments = await client.instrument_segments()
  quote = await client.quote('11111111-1111-5111-8111-000000000003')
"""

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import httpx

from instruments_explorer.unified_broker_interface import access_token_provider
from instruments_explorer.unified_broker_interface import exceptions
from instruments_explorer.unified_broker_interface import (
    json_array_stream_parser,
)
from instruments_explorer.unified_broker_interface import response_reader


class UnifiedBrokerInterfaceClient:
    """Calls UBI's REST API with the shared access token."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        token_provider: access_token_provider.AccessTokenProvider,
    ):
        """Creates the client.

        Args:
            http_client (httpx.AsyncClient): The client whose base URL is UBI's REST API.
            token_provider (access_token_provider.AccessTokenProvider): Finds the access token.
        """
        self._http_client = http_client
        self._token_provider = token_provider
        self._response_reader = response_reader.ResponseReader()

    async def greeting(self) -> Any:
        """Calls UBI's unauthenticated greeting route, which proves the API is up.

        Returns:
            Any: UBI's welcome message document.

        Raises:
            UnreachableError: UBI could not be reached.
            UnifiedBrokerInterfaceError: UBI answered with a failure status.
        """
        response = await self._send('GET', '/api/', None, None)
        return self._response_reader.read(response)

    async def instrument_segments(self) -> Any:
        """Reads the exchanges and segments of the current instrument catalogue.

        Returns:
            Any: A document with "mapping_date", "exchanges" and "segments".

        Raises:
            UnifiedBrokerInterfaceError: The request failed.
        """
        return await self._request('GET', '/api/instruments/segments')

    async def download_master(
        self,
        handle_batch: Callable[[list[dict[str, Any]]], Awaitable[None]],
        batch_size: int = 5000,
    ) -> str:
        """Streams every instrument of the current catalogue, in batches.

        The catalogue has over half a million instruments, so it is parsed as it arrives and handed on in batches instead of being held whole.

        Args:
            handle_batch (Callable[[list[dict[str, Any]]], Awaitable[None]]): Called with each batch of identity documents, in catalogue order.
            batch_size (int): How many instruments each batch holds, except the last.

        Returns:
            str: The catalogue's mapping date, from the X-Mapping-Date header.

        Raises:
            UnifiedBrokerInterfaceError: The token could not be found, UBI could not be reached, or UBI answered with a failure status.
            ValueError: The answer is not one complete JSON array, or has no mapping date.
        """
        token = await self._token_provider.current_token()
        try:
            return await self._stream_master(token, handle_batch, batch_size)
        except exceptions.AuthenticationError:
            token = await self._token_provider.token_after_refusal(token)
            return await self._stream_master(token, handle_batch, batch_size)

    async def instrument_details(self, instrument_id: str) -> Any:
        """Reads an instrument's identity, seen dates, lot size, tick size and broker handles.

        Args:
            instrument_id (str): UBI's instrument id.

        Returns:
            Any: The instrument details document.

        Raises:
            UnifiedBrokerInterfaceError: The request failed.
        """
        return await self._request(
            'GET',
            '/api/instruments/details',
            params={
                'instrument_id': instrument_id,
            },
        )

    async def additional_details(self, instrument_id: str) -> Any:
        """Reads the extra attributes each broker publishes about an instrument, such as its ISIN.

        Args:
            instrument_id (str): UBI's instrument id.

        Returns:
            Any: A document with "attribute_names" and one "carried_by" entry per broker.

        Raises:
            UnifiedBrokerInterfaceError: The request failed.
        """
        return await self._request(
            'GET',
            '/api/instruments/additional_details',
            params={
                'instrument_id': instrument_id,
            },
        )

    async def quote(self, instrument_id: str) -> Any:
        """Reads an instrument's full quote with market depth.

        Args:
            instrument_id (str): UBI's instrument id.

        Returns:
            Any: The unified quote document with "source".

        Raises:
            UnifiedBrokerInterfaceError: The request failed.
        """
        return await self._request(
            'GET',
            '/api/instruments/quote',
            params={
                'instrument_id': instrument_id,
            },
        )

    async def _stream_master(
        self,
        token: str,
        handle_batch: Callable[[list[dict[str, Any]]], Awaitable[None]],
        batch_size: int,
    ) -> str:
        """Streams the catalogue once with one token.

        Args:
            token (str): The access token.
            handle_batch (Callable[[list[dict[str, Any]]], Awaitable[None]]): Called with each batch.
            batch_size (int): How many instruments each batch holds, except the last.

        Returns:
            str: The catalogue's mapping date.

        Raises:
            AuthenticationError: UBI refused the token, before any batch was handed on.
            UnifiedBrokerInterfaceError: UBI could not be reached or answered with another failure status.
            ValueError: The answer is not one complete JSON array, or has no mapping date.
        """
        parameters = {
            'exchange': 'all',
            'segment': 'all',
        }
        headers = {
            'access-token': token,
        }
        parser = json_array_stream_parser.JsonArrayStreamParser()
        try:
            async with self._http_client.stream(
                'GET',
                '/api/instruments/master',
                params=parameters,
                headers=headers,
            ) as response:
                if not response.is_success:
                    await response.aread()
                    self._response_reader.read(response)
                mapping_date = response.headers.get('X-Mapping-Date')
                if not mapping_date:
                    raise ValueError(
                        'UBI answered the instrument master without an X-Mapping-Date header.'
                    )
                batch = []
                async for text in response.aiter_text():
                    for item in parser.feed(text):
                        batch.append(item)
                        if len(batch) >= batch_size:
                            await handle_batch(batch)
                            batch = []
                parser.finish()
                if batch:
                    await handle_batch(batch)
        except httpx.RequestError as error:
            raise exceptions.UnreachableError(
                f'The instrument master download from UBI failed: {error}'
            ) from error
        return mapping_date

    async def _request(
        self,
        method: str,
        path: str,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        """Sends an authenticated request, retrying once after a 401.

        Args:
            method (str): The HTTP method.
            path (str): The path, starting with /api/.
            params (Mapping[str, Any] | None): Query string parameters, or None.

        Returns:
            Any: The parsed JSON body.

        Raises:
            UnifiedBrokerInterfaceError: The token could not be found, UBI could not be reached, or UBI answered with a failure status.
        """
        token = await self._token_provider.current_token()
        response = await self._send(method, path, params, token)
        if response.status_code == 401:
            token = await self._token_provider.token_after_refusal(token)
            response = await self._send(method, path, params, token)
        return self._response_reader.read(response)

    async def _send(
        self,
        method: str,
        path: str,
        params: Mapping[str, Any] | None,
        token: str | None,
    ) -> httpx.Response:
        """Sends one request.

        Args:
            method (str): The HTTP method.
            path (str): The path, starting with /api/.
            params (Mapping[str, Any] | None): Query string parameters, or None.
            token (str | None): The access token, or None for an unauthenticated route.

        Returns:
            httpx.Response: The answer, whatever its status.

        Raises:
            UnreachableError: The connection failed or no answer arrived.
        """
        headers = {}
        if token is not None:
            headers['access-token'] = token
        try:
            return await self._http_client.request(
                method,
                path,
                params=params,
                headers=headers,
            )
        except httpx.RequestError as error:
            raise exceptions.UnreachableError(
                f'No answer from UBI for {method} {path}: {error}'
            ) from error
