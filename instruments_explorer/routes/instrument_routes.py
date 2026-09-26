"""The routes that search the instrument index and read one instrument from UBI.

Typical usage example:

  web_application.include_router(
      InstrumentRoutes(maintainer, client, guard).router
  )
"""

import asyncio
import sqlite3
from typing import Annotated, Any

import fastapi
from tradingmachine.ubi_client import exceptions

from instruments_explorer.instruments import instrument_index
from instruments_explorer.instruments import instrument_index_maintainer
from instruments_explorer.market import quote_encoder
from instruments_explorer.security import session_guard
from instruments_explorer.unified_broker_interface import catalogue_gateway

_STATUS_BY_ERROR = [
    (
        exceptions.NotFoundError,
        404,
    ),
    (
        exceptions.BadRequestError,
        400,
    ),
    (
        exceptions.UnreachableError,
        503,
    ),
    (
        exceptions.ServiceUnavailableError,
        503,
    ),
    (
        exceptions.AuthenticationError,
        503,
    ),
]

FilterValues = Annotated[list[str] | None, fastapi.Query()]


class InstrumentRoutes:
    """The /api/instruments routes.

    Attributes:
        maintainer: Holds the current instrument index.
        client: Reads instruments and quotes from UBI.
        router: The FastAPI router holding the routes.
    """

    def __init__(
        self,
        maintainer: instrument_index_maintainer.InstrumentIndexMaintainer,
        client: catalogue_gateway.CatalogueGateway,
        guard: session_guard.SessionGuard,
    ):
        """Creates the routes.

        Args:
            maintainer (instrument_index_maintainer.InstrumentIndexMaintainer): Holds the current instrument index.
            client (catalogue_gateway.CatalogueGateway): Reads instruments and quotes from UBI.
            guard (session_guard.SessionGuard): Requires a logged-in session.
        """
        self.maintainer = maintainer
        self.client = client
        self._encoder = quote_encoder.QuoteEncoder()
        self.router = fastapi.APIRouter(
            dependencies=[
                fastapi.Depends(guard.require_session),
            ],
        )
        self.router.add_api_route(
            '/api/instruments/index-status',
            self.index_status,
            methods=[
                'GET',
            ],
        )
        self.router.add_api_route(
            '/api/instruments/search',
            self.search,
            methods=[
                'GET',
            ],
        )
        self.router.add_api_route(
            '/api/instruments/{instrument_id}',
            self.instrument,
            methods=[
                'GET',
            ],
        )
        self.router.add_api_route(
            '/api/instruments/{instrument_id}/quote',
            self.quote,
            methods=[
                'GET',
            ],
        )

    def index_status(self) -> dict[str, Any]:
        """Describes the instrument index.

        Returns:
            dict[str, Any]: The maintainer's status.
        """
        return self.maintainer.status()

    async def search(
        self,
        q: str = '',
        exchange: FilterValues = None,
        asset_class: FilterValues = None,
        shape: FilterValues = None,
        segment: FilterValues = None,
        option_type: FilterValues = None,
        expiry_month: FilterValues = None,
        sector: FilterValues = None,
        strike_minimum: float | None = None,
        strike_maximum: float | None = None,
        sort: str = 'relevance',
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Searches and filters the instrument index.

        Every filter may be given several times, and an instrument matches when it has any of the given values.

        Args:
            q (str): The typed text.
            exchange (FilterValues): Exchanges to keep.
            asset_class (FilterValues): Asset classes to keep.
            shape (FilterValues): Shapes to keep.
            segment (FilterValues): Segments to keep.
            option_type (FilterValues): Option types to keep.
            expiry_month (FilterValues): Expiry months to keep, as "YYYY-MM".
            sector (FilterValues): Company sectors to keep.
            strike_minimum (float | None): The lowest strike to keep.
            strike_maximum (float | None): The highest strike to keep.
            sort (str): "relevance", "name", "expiry" or "strike".
            limit (int): How many results to return, from 1 to 200.
            offset (int): How many results to skip.

        Returns:
            dict[str, Any]: "mapping_date", "results", "total" and "facets".

        Raises:
            fastapi.HTTPException: 400 for an invalid request, 503 while the index is not ready.
        """
        index = self._current_index()
        filters = {
            'exchange': exchange or [],
            'asset_class': asset_class or [],
            'shape': shape or [],
            'segment': segment or [],
            'option_type': option_type or [],
            'expiry_month': expiry_month or [],
            'sector': sector or [],
        }
        try:
            request = instrument_index.SearchRequest(
                text=q,
                filters=filters,
                strike_minimum=strike_minimum,
                strike_maximum=strike_maximum,
                sort=sort,
                limit=limit,
                offset=offset,
            )
        except ValueError as error:
            raise fastapi.HTTPException(
                status_code=400,
                detail=str(error),
            ) from error
        try:
            page = await asyncio.to_thread(index.search, request)
        except sqlite3.Error as error:
            raise fastapi.HTTPException(
                status_code=503,
                detail=f'The instrument index could not be read: {error}',
            ) from error
        page['mapping_date'] = index.mapping_date
        return page

    async def instrument(self, instrument_id: str) -> dict[str, Any]:
        """Reads one instrument from the index and its details and attributes from UBI.

        When UBI cannot be reached, the index's own record is still returned, with the reason in "ubi_error".

        Args:
            instrument_id (str): UBI's instrument id.

        Returns:
            dict[str, Any]: "instrument" (the index record or None), "details", "attributes" (the first value each attribute has across brokers) and "ubi_error".

        Raises:
            fastapi.HTTPException: 404 when neither the index nor UBI knows the instrument.
        """
        record = None
        index = self.maintainer.current_index
        if index is not None:
            record = await asyncio.to_thread(index.instrument, instrument_id)
        details = None
        attributes = {}
        ubi_error = None
        try:
            details, additional = await asyncio.gather(
                self.client.instrument_details(instrument_id),
                self.client.additional_details(instrument_id),
            )
            attributes = self._merge_attributes(additional)
        except exceptions.NotFoundError as error:
            if record is None:
                raise fastapi.HTTPException(
                    status_code=404,
                    detail=error.message,
                ) from error
            ubi_error = error.message
        except exceptions.UnifiedBrokerInterfaceError as error:
            ubi_error = error.message
        if record is None and details is None:
            raise fastapi.HTTPException(
                status_code=404,
                detail=f'No instrument {instrument_id} is known.',
            )
        return {
            'instrument': record,
            'details': details,
            'attributes': attributes,
            'ubi_error': ubi_error,
        }

    async def quote(self, instrument_id: str) -> dict[str, Any]:
        """Reads an instrument's full quote from UBI.

        Args:
            instrument_id (str): UBI's instrument id.

        Returns:
            dict[str, Any]: The encoded quote, whose "source" is UBI's "cache" or "broker".

        Raises:
            fastapi.HTTPException: 404, 400 or 503 following UBI's answer, or 502 for any other failure.
        """
        try:
            document = await self.client.quote(instrument_id)
        except exceptions.UnifiedBrokerInterfaceError as error:
            raise fastapi.HTTPException(
                status_code=self._status_for(error),
                detail=error.message,
            ) from error
        source = 'cache'
        if isinstance(document, dict):
            source = str(document.get('source') or 'cache')
        else:
            document = {}
        return self._encoder.encode(document, source)

    def _current_index(self) -> instrument_index.InstrumentIndex:
        """Finds the index searches use.

        Returns:
            instrument_index.InstrumentIndex: The current index.

        Raises:
            fastapi.HTTPException: 503 while no index is ready.
        """
        index = self.maintainer.current_index
        if index is None:
            status = self.maintainer.status()
            raise fastapi.HTTPException(
                status_code=503,
                detail=f'The instrument index is not ready yet ({status["state"]}).',
            )
        return index

    def _merge_attributes(self, additional: Any) -> dict[str, Any]:
        """Takes the first value each shared attribute has across the brokers that publish it.

        Args:
            additional (Any): UBI's additional details document.

        Returns:
            dict[str, Any]: One value per attribute name that some broker publishes.
        """
        merged = {}
        if not isinstance(additional, dict):
            return merged
        names = additional.get('attribute_names') or []
        for entry in additional.get('carried_by') or []:
            for name in names:
                value = entry.get(name)
                if value is not None and name not in merged:
                    merged[name] = value
        return merged

    def _status_for(self, error: exceptions.UnifiedBrokerInterfaceError) -> int:
        """Chooses the status code to answer a UBI failure with.

        Args:
            error (exceptions.UnifiedBrokerInterfaceError): The failure.

        Returns:
            int: The HTTP status code.
        """
        for error_class, status_code in _STATUS_BY_ERROR:
            if isinstance(error, error_class):
                return status_code
        return 502
