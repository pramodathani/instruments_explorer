"""Searches and filters a built instrument index.

Typical usage example:

  index = InstrumentIndex.open(path)
  request = SearchRequest(text='nifty sep', filters={'shape': ['option']})
  page = index.search(request)
"""

import collections
import sqlite3
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Self

from instruments_explorer.instruments import search_query_parser

FACET_COLUMNS = [
    'exchange',
    'asset_class',
    'shape',
    'segment',
    'option_type',
    'expiry_month',
]
SORT_ORDERS = [
    'relevance',
    'name',
    'expiry',
    'strike',
]
MAXIMUM_LIMIT = 200
_FACET_CACHE_SIZE = 256
_RESULT_COLUMNS = [
    'instrument_id',
    'exchange',
    'segment',
    'bare_segment',
    'asset_class',
    'shape',
    'is_index',
    'symbol',
    'underlying_symbol',
    'display_name',
    'expiry_date',
    'strike_price',
    'option_type',
]
_ORDER_BY = {
    'name': 'root_key, exchange_rank, shape_rank, expiry_date, strike_price, option_type',
    'expiry': 'expiry_date IS NULL, expiry_date, root_key, strike_price, option_type',
    'strike': 'strike_price IS NULL, strike_price, root_key, expiry_date, option_type',
}
_RELEVANCE_ORDER = """
    CASE
        WHEN root_key = :first_word THEN 0
        WHEN substr(root_key, 1, length(:first_word)) = :first_word THEN 1
        ELSE 2
    END,
    shape_rank,
    is_index DESC,
    exchange_rank,
    length(root_key),
    root_key,
    expiry_date,
    strike_price,
    option_type
"""
_BROWSE_ORDER = 'shape_rank, is_index DESC, exchange_rank, root_key, expiry_date, strike_price, option_type'


class SearchRequest:
    """What a person asked for: typed text, filters, a strike range, an order and a page.

    Attributes:
        text: The typed text, possibly empty.
        filters: Chosen values per facet column; a column that is absent or empty is not filtered.
        strike_minimum: The lowest strike to include, or None.
        strike_maximum: The highest strike to include, or None.
        sort: One of SORT_ORDERS.
        limit: How many results to return.
        offset: How many results to skip, for the next page.
    """

    def __init__(
        self,
        text: str = '',
        filters: Mapping[str, Sequence[str]] | None = None,
        strike_minimum: float | None = None,
        strike_maximum: float | None = None,
        sort: str = 'relevance',
        limit: int = 100,
        offset: int = 0,
    ):
        """Creates the request, checking its values.

        Args:
            text (str): The typed text, possibly empty.
            filters (Mapping[str, Sequence[str]] | None): Chosen values per facet column, or None for no filters.
            strike_minimum (float | None): The lowest strike to include, or None.
            strike_maximum (float | None): The highest strike to include, or None.
            sort (str): One of SORT_ORDERS.
            limit (int): How many results to return, from 1 to MAXIMUM_LIMIT.
            offset (int): How many results to skip, zero or more.

        Raises:
            ValueError: A filter names an unknown column, or the sort, limit or offset is out of range.
        """
        cleaned_filters = {}
        if filters is not None:
            for column, values in filters.items():
                if column not in FACET_COLUMNS:
                    raise ValueError(f'Unknown filter: {column!r}')
                chosen = []
                for value in values:
                    if value:
                        chosen.append(str(value))
                if chosen:
                    cleaned_filters[column] = sorted(set(chosen))
        if sort not in SORT_ORDERS:
            raise ValueError(f'Unknown sort order: {sort!r}')
        if limit < 1 or limit > MAXIMUM_LIMIT:
            raise ValueError(
                f'The limit must be between 1 and {MAXIMUM_LIMIT}: {limit=}'
            )
        if offset < 0:
            raise ValueError(f'The offset cannot be negative: {offset=}')
        self.text = text
        self.filters = cleaned_filters
        self.strike_minimum = strike_minimum
        self.strike_maximum = strike_maximum
        self.sort = sort
        self.limit = limit
        self.offset = offset

    def facet_key(self) -> tuple[Any, ...]:
        """Builds a key that is equal for requests whose filter counts are equal.

        Returns:
            tuple[Any, ...]: The text, filters and strike range, without the order and page.
        """
        filter_items = []
        for column in sorted(self.filters):
            filter_items.append(
                (
                    column,
                    tuple(self.filters[column]),
                )
            )
        return (
            self.text.strip().lower(),
            tuple(filter_items),
            self.strike_minimum,
            self.strike_maximum,
        )


class InstrumentIndex:
    """A read-only connection to one instrument index file.

    Attributes:
        path: The index file.
        mapping_date: The catalogue mapping date the index was built from.
        instrument_count: How many instruments the index holds.
    """

    def __init__(self, path: Path, connection: sqlite3.Connection):
        """Wraps an open connection to an index file.

        Args:
            path (Path): The index file.
            connection (sqlite3.Connection): A read-only connection to it.

        Raises:
            sqlite3.Error: The index details could not be read.
            KeyError: The index details are incomplete.
        """
        self.path = path
        self._connection = connection
        self._lock = threading.Lock()
        self._parser = search_query_parser.SearchQueryParser()
        self._facet_cache = collections.OrderedDict()
        details = dict(
            connection.execute('SELECT name, value FROM index_details')
        )
        self.mapping_date = details['mapping_date']
        self.instrument_count = int(details['instrument_count'])

    @classmethod
    def open(cls, path: Path) -> Self:
        """Opens an index file read-only.

        Args:
            path (Path): The index file.

        Returns:
            Self: The index.

        Raises:
            sqlite3.Error: The file is missing or is not a complete index.
        """
        connection = sqlite3.connect(
            f'file:{path}?mode=ro',
            uri=True,
            check_same_thread=False,
        )
        try:
            return cls(path, connection)
        except (sqlite3.Error, KeyError) as error:
            connection.close()
            raise sqlite3.DatabaseError(
                f'Not a complete instrument index: {path}'
            ) from error

    def search(self, request: SearchRequest) -> dict[str, Any]:
        """Finds one page of matching instruments, their total, and the count for every filter value.

        Args:
            request (SearchRequest): What to search for.

        Returns:
            dict[str, Any]: "results" (one dictionary per instrument), "total" (how many match in all) and "facets" (a list of {"value", "count"} per facet column).

        Raises:
            sqlite3.Error: The index could not be read.
        """
        query = self._parser.parse(request.text)
        where_sql, parameters = self._where(request, query, None)
        parameters['limit'] = request.limit
        parameters['offset'] = request.offset
        order_sql = self._order_by(request, query)
        if query is not None:
            parameters['first_word'] = query.first_word
        columns = ', '.join(_RESULT_COLUMNS)
        results_sql = f'SELECT {columns} FROM instruments {where_sql} ORDER BY {order_sql} LIMIT :limit OFFSET :offset'
        count_sql = f'SELECT COUNT(*) FROM instruments {where_sql}'
        with self._lock:
            rows = self._connection.execute(results_sql, parameters).fetchall()
            total = self._connection.execute(count_sql, parameters).fetchone()[
                0
            ]
        results = []
        for row in rows:
            result = dict(zip(_RESULT_COLUMNS, row, strict=True))
            result['is_index'] = bool(result['is_index'])
            results.append(result)
        return {
            'results': results,
            'total': total,
            'facets': self.facets(request),
        }

    def facets(self, request: SearchRequest) -> dict[str, list[dict[str, Any]]]:
        """Counts the matches for every value of every facet column.

        Each column is counted with every filter applied except its own, so the counts say what choosing another value of that column would give. Results are cached, because the counts for the whole catalogue are asked for often and do not change.

        Args:
            request (SearchRequest): What to search for.

        Returns:
            dict[str, list[dict[str, Any]]]: For each facet column, a list of {"value", "count"}, largest count first, except expiry months, which are in date order.

        Raises:
            sqlite3.Error: The index could not be read.
        """
        key = request.facet_key()
        with self._lock:
            cached = self._facet_cache.get(key)
            if cached is not None:
                self._facet_cache.move_to_end(key)
                return cached
        query = self._parser.parse(request.text)
        counted = {}
        for column in FACET_COLUMNS:
            where_sql, parameters = self._where(request, query, column)
            order_sql = 'COUNT(*) DESC'
            if column == 'expiry_month':
                order_sql = 'value'
            null_condition = f'{column} IS NOT NULL'
            if where_sql:
                where_sql = f'{where_sql} AND {null_condition}'
            else:
                where_sql = f'WHERE {null_condition}'
            sql = f'SELECT {column} AS value, COUNT(*) FROM instruments {where_sql} GROUP BY {column} ORDER BY {order_sql}'
            with self._lock:
                rows = self._connection.execute(sql, parameters).fetchall()
            values = []
            for value, count in rows:
                values.append(
                    {
                        'value': value,
                        'count': count,
                    }
                )
            counted[column] = values
        with self._lock:
            self._facet_cache[key] = counted
            while len(self._facet_cache) > _FACET_CACHE_SIZE:
                self._facet_cache.popitem(last=False)
        return counted

    def instrument(self, instrument_id: str) -> dict[str, Any] | None:
        """Looks up one instrument by id.

        Args:
            instrument_id (str): UBI's instrument id.

        Returns:
            dict[str, Any] | None: The instrument keyed by the result column names, or None when the index does not have it.

        Raises:
            sqlite3.Error: The index could not be read.
        """
        columns = ', '.join(_RESULT_COLUMNS)
        with self._lock:
            row = self._connection.execute(
                f'SELECT {columns} FROM instruments WHERE instrument_id = ?',
                (instrument_id,),
            ).fetchone()
        if row is None:
            return None
        result = dict(zip(_RESULT_COLUMNS, row, strict=True))
        result['is_index'] = bool(result['is_index'])
        return result

    def derivative_underlyings(
        self,
        text: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Lists the underlyings that have futures or options, by exchange.

        Args:
            text (str): Typed text; underlyings whose name starts with it come first, and an empty text lists the busiest underlyings.
            limit (int): The largest number of underlyings to return.

        Returns:
            list[dict[str, Any]]: One dictionary per exchange and underlying with "exchange", "underlying_symbol", "asset_class", "is_index", "futures", "options", "expiries" and "next_expiry": exact matches first, then equity indices, other equities and everything else, each by option count.
        """
        key = ''.join(text.lower().split())
        sql = """
            SELECT
                exchange,
                underlying_symbol,
                MAX(asset_class),
                MAX(is_index),
                SUM(shape = 'future'),
                SUM(shape = 'option'),
                COUNT(DISTINCT expiry_date),
                MIN(expiry_date)
            FROM instruments
            WHERE shape IN ('future', 'option')
                AND underlying_symbol IS NOT NULL
                AND (:key = '' OR substr(root_key, 1, length(:key)) = :key)
            GROUP BY exchange, underlying_symbol
            ORDER BY
                root_key = :key DESC,
                MAX(asset_class = 'equity') DESC,
                MAX(is_index) DESC,
                SUM(shape = 'option') DESC,
                exchange_rank,
                underlying_symbol
            LIMIT :limit
        """
        parameters = {
            'key': key,
            'limit': limit,
        }
        with self._lock:
            rows = self._connection.execute(sql, parameters).fetchall()
        underlyings = []
        for row in rows:
            underlyings.append(
                {
                    'exchange': row[0],
                    'underlying_symbol': row[1],
                    'asset_class': row[2],
                    'is_index': bool(row[3]),
                    'futures': row[4],
                    'options': row[5],
                    'expiries': row[6],
                    'next_expiry': row[7],
                }
            )
        return underlyings

    def derivative_contracts(
        self,
        exchange: str,
        underlying_symbol: str,
    ) -> list[dict[str, Any]]:
        """Lists every future and option of one underlying on one exchange.

        Args:
            exchange (str): The exchange, such as "nse".
            underlying_symbol (str): The underlying, such as "NIFTY".

        Returns:
            list[dict[str, Any]]: The contracts keyed by the result column names, by expiry, then futures before options, then strike and option type.
        """
        columns = ', '.join(_RESULT_COLUMNS)
        sql = f"""
            SELECT {columns}
            FROM instruments
            WHERE exchange = ?
                AND underlying_symbol = ?
                AND shape IN ('future', 'option')
            ORDER BY expiry_date, shape_rank, strike_price, option_type
        """
        with self._lock:
            rows = self._connection.execute(
                sql,
                (
                    exchange,
                    underlying_symbol,
                ),
            ).fetchall()
        contracts = []
        for row in rows:
            contract = dict(zip(_RESULT_COLUMNS, row, strict=True))
            contract['is_index'] = bool(contract['is_index'])
            contracts.append(contract)
        return contracts

    def underlying_security(
        self,
        exchange: str,
        underlying_symbol: str,
    ) -> dict[str, Any] | None:
        """Finds the cash instrument an underlying's derivatives are written on, such as the NIFTY index or the RELIANCE share.

        Args:
            exchange (str): The exchange of the derivatives.
            underlying_symbol (str): The underlying's symbol.

        Returns:
            dict[str, Any] | None: The security keyed by the result column names, preferring equities and indices over other cash segments, or None when the exchange lists none.
        """
        columns = ', '.join(_RESULT_COLUMNS)
        sql = f"""
            SELECT {columns}
            FROM instruments
            WHERE exchange = ?
                AND symbol = ?
                AND shape = 'security'
                AND bare_segment != 'uncategorised'
            ORDER BY
                bare_segment IN ('equities', 'equity_indices') DESC,
                bare_segment
            LIMIT 1
        """
        with self._lock:
            row = self._connection.execute(
                sql,
                (
                    exchange,
                    underlying_symbol,
                ),
            ).fetchone()
        if row is None:
            return None
        security = dict(zip(_RESULT_COLUMNS, row, strict=True))
        security['is_index'] = bool(security['is_index'])
        return security

    def close(self) -> None:
        """Closes the connection."""
        with self._lock:
            self._connection.close()

    def _where(
        self,
        request: SearchRequest,
        query: search_query_parser.SearchQuery | None,
        skipped_column: str | None,
    ) -> tuple[str, dict[str, Any]]:
        """Builds the WHERE clause for a request.

        Column names come only from FACET_COLUMNS, and every value is a bound parameter, so nothing typed can change the SQL.

        Args:
            request (SearchRequest): What to search for.
            query (search_query_parser.SearchQuery | None): The parsed text, or None when no words were typed.
            skipped_column (str | None): A facet column whose own filter is left out, or None.

        Returns:
            tuple[str, dict[str, Any]]: A tuple (the clause starting with "WHERE", or an empty string, and its named parameters).
        """
        conditions = []
        parameters = {}
        if query is not None:
            conditions.append(
                'row_number IN (SELECT rowid FROM instrument_search WHERE instrument_search MATCH :expression)'
            )
            parameters['expression'] = query.expression
        for column in FACET_COLUMNS:
            if column == skipped_column:
                continue
            values = request.filters.get(column)
            if not values:
                continue
            names = []
            for position, value in enumerate(values):
                name = f'{column}_{position}'
                parameters[name] = value
                names.append(f':{name}')
            conditions.append(f'{column} IN ({", ".join(names)})')
        if request.strike_minimum is not None:
            conditions.append('strike_price >= :strike_minimum')
            parameters['strike_minimum'] = request.strike_minimum
        if request.strike_maximum is not None:
            conditions.append('strike_price <= :strike_maximum')
            parameters['strike_maximum'] = request.strike_maximum
        if not conditions:
            return '', parameters
        return 'WHERE ' + ' AND '.join(conditions), parameters

    def _order_by(
        self,
        request: SearchRequest,
        query: search_query_parser.SearchQuery | None,
    ) -> str:
        """Chooses the ORDER BY clause for a request.

        Args:
            request (SearchRequest): What to search for.
            query (search_query_parser.SearchQuery | None): The parsed text, or None when no words were typed.

        Returns:
            str: The clause without the words ORDER BY.
        """
        if request.sort != 'relevance':
            return _ORDER_BY[request.sort]
        if query is None:
            return _BROWSE_ORDER
        return _RELEVANCE_ORDER
