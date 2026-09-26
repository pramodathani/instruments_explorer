"""The only way the knowledge fetchers reach the internet: it obeys robots.txt and spaces out requests to each site.

Typical usage example:

  client = PoliteHttpClient(http_client, 'instruments_explorer', 2.0)
  response = await client.get('https://www.screener.in/company/RELIANCE/')
"""

import asyncio
import time
import urllib.parse
import urllib.robotparser
from collections.abc import Mapping
from typing import Any

import httpx

ROBOTS_CACHE_SECONDS = 24 * 60 * 60


class RobotsDisallowedError(Exception):
    """A site's robots.txt does not allow the address to be fetched."""


class PoliteHttpClient:
    """Fetches addresses only where robots.txt allows, never faster than one request per site every interval.

    Attributes:
        robots_agent: The name robots.txt rules are checked against.
        host_interval_seconds: The shortest wait between two requests to the same site, in seconds.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        robots_agent: str,
        host_interval_seconds: float,
    ):
        """Creates the client.

        Args:
            http_client (httpx.AsyncClient): The underlying client, which carries the default headers.
            robots_agent (str): The name robots.txt rules are checked against.
            host_interval_seconds (float): The shortest wait between two requests to the same site, in seconds.
        """
        self.robots_agent = robots_agent
        self.host_interval_seconds = host_interval_seconds
        self._http_client = http_client
        self._robots = {}
        self._host_locks = {}
        self._last_request_at = {}

    async def get(
        self,
        url: str,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        """Fetches an address after checking robots.txt and waiting for the site's turn.

        Args:
            url (str): The address.
            params (Mapping[str, Any] | None): Query string parameters, or None.
            headers (Mapping[str, str] | None): Extra headers, or None.

        Returns:
            httpx.Response: The answer, whatever its status.

        Raises:
            RobotsDisallowedError: The site's robots.txt does not allow the address.
            httpx.HTTPError: The request failed.
        """
        full_url = url
        if params:
            full_url = f'{url}?{urllib.parse.urlencode(params)}'
        if not await self.allowed(full_url):
            raise RobotsDisallowedError(
                f'robots.txt does not allow fetching {full_url}'
            )
        host = urllib.parse.urlsplit(url).netloc
        lock = self._host_locks.setdefault(host, asyncio.Lock())
        async with lock:
            last = self._last_request_at.get(host)
            if last is not None:
                wait = self.host_interval_seconds - (time.monotonic() - last)
                if wait > 0:
                    await asyncio.sleep(wait)
            try:
                return await self._http_client.get(
                    url,
                    params=params,
                    headers=headers,
                )
            finally:
                self._last_request_at[host] = time.monotonic()

    async def allowed(self, url: str) -> bool:
        """Checks an address against its site's robots.txt, reading the file at most once a day.

        A robots.txt that is missing or cannot be read allows everything, as the robots.txt convention says.

        Args:
            url (str): The address.

        Returns:
            bool: True when the address may be fetched.
        """
        parts = urllib.parse.urlsplit(url)
        origin = f'{parts.scheme}://{parts.netloc}'
        cached = self._robots.get(origin)
        if (
            cached is None
            or time.monotonic() - cached[0] > ROBOTS_CACHE_SECONDS
        ):
            parser = urllib.robotparser.RobotFileParser()
            try:
                response = await self._http_client.get(f'{origin}/robots.txt')
            except httpx.HTTPError:
                parser.allow_all = True
            else:
                if response.status_code >= 400:
                    parser.allow_all = True
                else:
                    parser.parse(response.text.splitlines())
            cached = (
                time.monotonic(),
                parser,
            )
            self._robots[origin] = cached
        return cached[1].can_fetch(self.robots_agent, url)
