"""The routes that serve an instrument's candles with its TA-Lib indicators.

Typical usage example:

  web_application.include_router(
      ChartRoutes(client, catalogue, guard).router
  )
"""

import asyncio
import datetime
from typing import Annotated, Any

import fastapi
from tradingmachine.ubi_client import exceptions

from instruments_explorer.indicators import indicator_calculator
from instruments_explorer.indicators import indicator_catalogue
from instruments_explorer.market import candle_series
from instruments_explorer.security import session_guard
from instruments_explorer.unified_broker_interface import catalogue_gateway

INTERVALS = [
    'day',
    '1minute',
    '2minute',
    '3minute',
    '4minute',
    '5minute',
    '10minute',
    '15minute',
    '20minute',
    '25minute',
    '30minute',
    '45minute',
    '60minute',
    '120minute',
    '180minute',
    '240minute',
]
MAXIMUM_DAYS = 36500
MAXIMUM_INTRADAY_DAYS = 366
_CALENDAR_DAYS_PER_TRADING_DAY = 1.6
_INTRADAY_WARM_UP_DAYS = 7
_INDIA = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

IndicatorRequests = Annotated[list[str] | None, fastapi.Query()]


class ChartRoutes:
    """The chart and indicator catalogue routes.

    Attributes:
        client: Reads candles from UBI.
        catalogue: Lists the indicators.
        router: The FastAPI router holding the routes.
    """

    def __init__(
        self,
        client: catalogue_gateway.CatalogueGateway,
        catalogue: indicator_catalogue.IndicatorCatalogue,
        guard: session_guard.SessionGuard,
    ):
        """Creates the routes.

        Args:
            client (catalogue_gateway.CatalogueGateway): Reads candles from UBI.
            catalogue (indicator_catalogue.IndicatorCatalogue): Lists the indicators.
            guard (session_guard.SessionGuard): Requires a logged-in session.
        """
        self.client = client
        self.catalogue = catalogue
        self._calculator = indicator_calculator.IndicatorCalculator(catalogue)
        self.router = fastapi.APIRouter(
            dependencies=[
                fastapi.Depends(guard.require_session),
            ],
        )
        self.router.add_api_route(
            '/api/indicators',
            self.indicators,
            methods=[
                'GET',
            ],
        )
        self.router.add_api_route(
            '/api/instruments/{instrument_id}/chart',
            self.chart,
            methods=[
                'GET',
            ],
        )

    def indicators(self) -> list[dict[str, Any]]:
        """Lists every indicator the chart can show.

        Returns:
            list[dict[str, Any]]: One description per indicator.
        """
        return self.catalogue.describe()

    async def chart(
        self,
        instrument_id: str,
        interval: str = 'day',
        days: int = 730,
        adjusted: bool = True,
        indicator: IndicatorRequests = None,
    ) -> dict[str, Any]:
        """Reads an instrument's candles from UBI and computes the requested indicators over them.

        Args:
            instrument_id (str): UBI's instrument id.
            interval (str): One of INTERVALS.
            days (int): How many days back from today to read.
            adjusted (bool): Whether to correct an adjustable instrument for splits and bonuses.
            indicator (IndicatorRequests): Indicator requests such as "rsi:14", given once per indicator.

        Returns:
            dict[str, Any]: The instrument id, interval, days, "price_basis", "adjustable", "source", "has_volume", "candles" as [time, open, high, low, close, volume, oi] rows, "indicators" and "errors".

        Raises:
            fastapi.HTTPException: 400 for an invalid interval or range, 404 for an unknown instrument, 503 when UBI cannot be reached, or 502 for another UBI failure.
        """
        if interval not in INTERVALS:
            raise fastapi.HTTPException(
                status_code=400,
                detail=f'Unknown interval: {interval!r}',
            )
        maximum = MAXIMUM_DAYS if interval == 'day' else MAXIMUM_INTRADAY_DAYS
        if days < 1 or days > maximum:
            raise fastapi.HTTPException(
                status_code=400,
                detail=f'For {interval} candles, days must be between 1 and {maximum}: {days=}',
            )
        requests = list(indicator or [])
        extra_days = self._warm_up_days(interval, days, maximum, requests)
        try:
            document = await self.client.prices(
                instrument_id,
                interval,
                days + extra_days,
                adjusted,
            )
        except exceptions.NotFoundError as error:
            raise fastapi.HTTPException(
                status_code=404,
                detail=error.message,
            ) from error
        except (
            exceptions.UnreachableError,
            exceptions.AuthenticationError,
        ) as error:
            raise fastapi.HTTPException(
                status_code=503,
                detail=error.message,
            ) from error
        except exceptions.UnifiedBrokerInterfaceError as error:
            raise fastapi.HTTPException(
                status_code=502,
                detail=error.message,
            ) from error
        if not isinstance(document, dict):
            document = {}
        return await asyncio.to_thread(
            self._build_answer,
            instrument_id,
            interval,
            days,
            document,
            requests,
        )

    def _warm_up_days(
        self,
        interval: str,
        days: int,
        maximum: int,
        requests: list[str],
    ) -> int:
        """Works out how many extra days to read so the indicators have values from the chart's first candle.

        Args:
            interval (str): The candle interval.
            days (int): The days the chart shows.
            maximum (int): The most days UBI allows for the interval.
            requests (list[str]): The indicator requests.

        Returns:
            int: The extra days, never taking the total past the maximum.
        """
        candles = self._calculator.warm_up_candles(requests)
        if candles == 0:
            return 0
        if interval == 'day':
            extra = int(candles * _CALENDAR_DAYS_PER_TRADING_DAY) + 10
        else:
            extra = _INTRADAY_WARM_UP_DAYS
        return max(0, min(extra, maximum - days))

    def _first_time(self, document: dict[str, Any], days: int) -> int:
        """Finds the start of the chart's first day, midnight in India, from the end of the range UBI read.

        Args:
            document (dict[str, Any]): UBI's prices answer, whose "to" is the last day read.
            days (int): The days the chart shows.

        Returns:
            int: The first day's start in epoch milliseconds, or 0 to keep everything when UBI gave no end date.
        """
        to_text = document.get('to')
        if not to_text:
            return 0
        last_day = datetime.date.fromisoformat(str(to_text))
        first_day = last_day - datetime.timedelta(days=days)
        start = datetime.datetime(
            first_day.year,
            first_day.month,
            first_day.day,
            tzinfo=_INDIA,
        )
        return int(start.timestamp() * 1000)

    def _trim(self, result: dict[str, Any], first_time: int) -> None:
        """Drops the warm-up part of an indicator's lines and markers.

        Args:
            result (dict[str, Any]): One computed indicator, changed in place.
            first_time (int): The chart's first moment, in epoch milliseconds.
        """
        for output in result['outputs']:
            kept = []
            for point in output['points']:
                if point[0] >= first_time:
                    kept.append(point)
            output['points'] = kept
        markers = []
        for marker in result['markers']:
            if marker['time'] >= first_time:
                markers.append(marker)
        result['markers'] = markers

    def _build_answer(
        self,
        instrument_id: str,
        interval: str,
        days: int,
        document: dict[str, Any],
        requests: list[str],
    ) -> dict[str, Any]:
        """Turns UBI's candles into the chart's answer, computing the indicators.

        Args:
            instrument_id (str): UBI's instrument id.
            interval (str): The candle interval.
            days (int): The number of days read.
            document (dict[str, Any]): UBI's prices answer.
            requests (list[str]): The indicator requests.

        Returns:
            dict[str, Any]: The chart's answer, as described in chart().
        """
        history = candle_series.CandleSeries.from_prices_document(document)
        first_time = self._first_time(document, days)
        series = history.since(first_time)
        results = []
        errors = []
        if len(history) > 0:
            results, errors = self._calculator.compute(history, requests)
            for result in results:
                self._trim(result, first_time)
        return {
            'instrument_id': instrument_id,
            'interval': interval,
            'days': days,
            'price_basis': document.get('price_basis'),
            'adjustable': bool(document.get('adjustable')),
            'source': document.get('source'),
            'has_volume': series.has_volume(),
            'candles': series.rows(),
            'indicators': results,
            'errors': errors,
        }
