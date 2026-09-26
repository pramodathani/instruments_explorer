"""Runs screens over the stored figures and groups the matches by sector for the heatmap.

A screen asks for each condition as text: the condition's key followed by its parameters, separated by colons, such as "rsi:0:30" or "return:21:10". Parameters left out take their defaults.

Typical usage example:

  service = ScreenerService(universe, repository, ConditionCatalogue())
  answer = await service.run('total_market', ['rsi:0:30'], [], 'rsi_14', False, 100)
"""

from collections.abc import Sequence
from typing import Any

from instruments_explorer.screener import screener_universe
from instruments_explorer.screener.conditions import condition_catalogue
from instruments_explorer.storage import screener_repository

SORTABLE_FIGURES = [
    'symbol',
    'sector',
    'close',
    'change_1d',
    'change_5d',
    'change_21d',
    'change_63d',
    'change_252d',
    'from_high',
    'from_low',
    'rsi_14',
    'adx_14',
    'natr_14',
    'volume_ratio',
    'traded_value',
    'percent_b',
]
MAXIMUM_CONDITIONS = 10
MAXIMUM_ROWS = 1000


class ScreenerService:
    """Filters, sorts and groups a universe's stored figures."""

    def __init__(
        self,
        universe: screener_universe.ScreenerUniverse,
        repository: screener_repository.ScreenerRepository,
        catalogue: condition_catalogue.ConditionCatalogue,
    ):
        """Creates the service.

        Args:
            universe (screener_universe.ScreenerUniverse): Lists the stocks.
            repository (screener_repository.ScreenerRepository): Reads the stored figures.
            catalogue (condition_catalogue.ConditionCatalogue): Finds conditions by key.
        """
        self._universe = universe
        self._repository = repository
        self._catalogue = catalogue

    async def run(
        self,
        universe: str,
        requests: Sequence[str],
        sectors: Sequence[str],
        sort: str,
        descending: bool,
        limit: int,
    ) -> dict[str, Any]:
        """Runs a screen.

        Args:
            universe (str): The universe key.
            requests (Sequence[str]): Condition requests such as "rsi:0:30"; a stock must meet all of them.
            sectors (Sequence[str]): Sectors to keep, or empty for every sector.
            sort (str): One of SORTABLE_FIGURES.
            descending (bool): Whether to sort largest first.
            limit (int): The largest number of rows, from 1 to MAXIMUM_ROWS.

        Returns:
            dict[str, Any]: "universe", "members" (stocks in the universe), "with_figures" (stocks that have stored figures), "matched", "rows", "sectors" (every matching stock grouped by sector, for the heatmap, with the sector's count and average one-day change), "sector_names" (every sector in the universe) and "last_run".

        Raises:
            ValueError: A condition, the sort or the limit is invalid, or there are too many conditions.
            LookupError: The instrument index is not ready.
        """
        if sort not in SORTABLE_FIGURES:
            raise ValueError(f'Unknown sort figure: {sort!r}')
        if limit < 1 or limit > MAXIMUM_ROWS:
            raise ValueError(
                f'The limit must be between 1 and {MAXIMUM_ROWS}: {limit=}'
            )
        if len(requests) > MAXIMUM_CONDITIONS:
            raise ValueError(
                f'At most {MAXIMUM_CONDITIONS} conditions can be combined.'
            )
        conditions = []
        for request in requests:
            pieces = request.strip().lower().split(':')
            condition = self._catalogue.find(pieces[0])
            conditions.append(
                (
                    condition,
                    condition.resolve(pieces[1:]),
                )
            )
        members = await self._universe.members(universe)
        ids = []
        for member in members:
            ids.append(member['instrument_id'])
        rows = await self._repository.for_instruments(ids)
        wanted_sectors = set(sectors)
        sector_names = set()
        matched = []
        for row in rows:
            sector_names.add(row.get('sector') or 'Unclassified')
            if wanted_sectors and row.get('sector') not in wanted_sectors:
                continue
            keep = True
            for condition, parameters in conditions:
                if not condition.matches(row, parameters):
                    keep = False
                    break
            if keep:
                matched.append(row)
        matched.sort(
            key=lambda row: self._sort_key(row, sort), reverse=descending
        )
        if descending:
            present = [row for row in matched if row.get(sort) is not None]
            absent = [row for row in matched if row.get(sort) is None]
            matched = present + absent
        return {
            'universe': universe,
            'members': len(members),
            'with_figures': len(rows),
            'matched': len(matched),
            'rows': matched[:limit],
            'sectors': self._group(matched),
            'sector_names': sorted(sector_names),
            'last_run': await self._repository.latest_run(
                universe, finished_only=True
            ),
        }

    def _sort_key(self, row: dict[str, Any], sort: str) -> tuple[int, Any]:
        """Builds a sort key that puts missing values last.

        Args:
            row (dict[str, Any]): A stock's figures.
            sort (str): The figure to sort by.

        Returns:
            tuple[int, Any]: A tuple (1 when the value is missing, otherwise 0, and the value).
        """
        value = row.get(sort)
        if value is None:
            return (1, 0)
        return (0, value)

    def _group(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Groups matching stocks by sector for the heatmap.

        Args:
            rows (list[dict[str, Any]]): The matching stocks.

        Returns:
            list[dict[str, Any]]: One {"sector", "count", "average_change", "stocks"} per sector, largest first; each stock has "instrument_id", "symbol", "name", "change_1d" and "traded_value".
        """
        groups = {}
        for row in rows:
            sector = row.get('sector') or 'Unclassified'
            groups.setdefault(sector, []).append(
                {
                    'instrument_id': row['instrument_id'],
                    'symbol': row['symbol'],
                    'name': row.get('name'),
                    'change_1d': row.get('change_1d'),
                    'traded_value': row.get('traded_value'),
                }
            )
        grouped = []
        for sector, stocks in groups.items():
            changes = [
                stock['change_1d']
                for stock in stocks
                if stock['change_1d'] is not None
            ]
            average = round(sum(changes) / len(changes), 4) if changes else None
            grouped.append(
                {
                    'sector': sector,
                    'count': len(stocks),
                    'average_change': average,
                    'stocks': stocks,
                }
            )
        grouped.sort(key=lambda group: -group['count'])
        return grouped
