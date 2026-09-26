"""The Earth page's routes: every company with a known headquarters, placed on the globe, and the sweep that locates them.

Typical usage example:

  web_application.include_router(EarthRoutes(knowledge_parts, knowledge, maintainer, guard).router)
"""

from typing import Any

import fastapi

from instruments_explorer.instruments import instrument_index_maintainer
from instruments_explorer.knowledge import postcode_geocoder
from instruments_explorer.routes import knowledge_routes
from instruments_explorer.security import session_guard


class EarthRoutes:
    """The /api/earth routes.

    Attributes:
        parts: The knowledge components, which hold the companies, the geocoder and the sweep.
        router: The FastAPI router holding the routes.
    """

    def __init__(
        self,
        parts: knowledge_routes.KnowledgeParts,
        knowledge: knowledge_routes.KnowledgeRoutes,
        maintainer: instrument_index_maintainer.InstrumentIndexMaintainer,
        guard: session_guard.SessionGuard,
    ):
        """Creates the routes.

        Args:
            parts (knowledge_routes.KnowledgeParts): The knowledge components.
            knowledge (knowledge_routes.KnowledgeRoutes): Places a headquarters address on the map.
            maintainer (instrument_index_maintainer.InstrumentIndexMaintainer): Holds the instrument index, for each company's share.
            guard (session_guard.SessionGuard): Requires a logged-in session, and the application header on POST routes.
        """
        self.parts = parts
        self._knowledge = knowledge
        self._maintainer = maintainer
        self.router = fastapi.APIRouter(
            prefix='/api/earth',
            dependencies=[
                fastapi.Depends(guard.require_session),
            ],
        )
        self.router.add_api_route(
            '/companies',
            self.companies,
            methods=[
                'GET',
            ],
        )
        self.router.add_api_route(
            '/locate',
            self.locate_all,
            methods=[
                'POST',
            ],
            dependencies=[
                fastapi.Depends(guard.require_app_header),
            ],
        )

    async def companies(self) -> dict[str, Any]:
        """Lists every company whose headquarters can be placed on the map.

        Returns:
            dict[str, Any]: "companies" (each with "company_key", "name", "symbol", "sector", "city", "address", "latitude", "longitude", "precision" and "instrument_id"), "with_address" (companies with an address), "unplaced" (addresses that could not be placed), "geocoder_ready", "download_url", "index_companies" and "sweep".
        """
        stored = await self.parts.companies.with_headquarters()
        share_ids = {}
        index = self._maintainer.current_index
        if index is not None:
            share_ids = index.share_ids_by_symbol('nse')
        placed = []
        unplaced = 0
        for company in stored:
            headquarters = self._knowledge.locate(company.get('headquarters'))
            if headquarters is None or headquarters['location'] is None:
                unplaced += 1
                continue
            location = headquarters['location']
            placed.append(
                {
                    'company_key': company.get('company_key'),
                    'name': company.get('name'),
                    'symbol': company.get('symbol'),
                    'sector': self.parts.companies.sector(company),
                    'city': headquarters.get('city'),
                    'address': ', '.join(
                        headquarters.get('address_lines') or []
                    ),
                    'latitude': location['latitude'],
                    'longitude': location['longitude'],
                    'precision': location['precision'],
                    'instrument_id': share_ids.get(company.get('symbol') or ''),
                }
            )
        geocoder = self.parts.geocoder
        index_companies = len(await self.parts.companies.screener_members(True))
        return {
            'companies': placed,
            'with_address': len(stored),
            'unplaced': unplaced,
            'geocoder_ready': geocoder is not None and geocoder.available(),
            'download_url': postcode_geocoder.DOWNLOAD_URL,
            'index_companies': index_companies,
            'sweep': self.parts.sweep.state
            if self.parts.sweep is not None
            else None,
        }

    async def locate_all(self) -> dict[str, Any]:
        """Starts fetching the headquarters of every Nifty Total Market company not yet located.

        Returns:
            dict[str, Any]: The sweep's state.

        Raises:
            fastapi.HTTPException: 503 when the sweep is not set up.
        """
        if self.parts.sweep is None:
            raise fastapi.HTTPException(
                status_code=503,
                detail='Locating companies is not set up.',
            )
        return await self.parts.sweep.start()
