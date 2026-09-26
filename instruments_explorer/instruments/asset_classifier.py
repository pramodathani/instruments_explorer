"""Sorts UBI's segments into a few broad asset classes.

UBI has over fifty segments, such as `nse_equity_index_options` and `mcx_commodity_futures`. The explorer groups them into six asset classes so a person can narrow the catalogue in one click before choosing a segment.

Typical usage example:

  classifier = AssetClassifier()
  classifier.asset_class('equity_index_options')  # 'equity'
"""

ASSET_CLASSES = [
    'equity',
    'funds',
    'fixed_income',
    'currency',
    'commodity',
    'other',
]
_KEYWORDS = [
    (
        'fixed_income',
        'fixed_income',
    ),
    (
        'currenc',
        'currency',
    ),
    (
        'commodit',
        'commodity',
    ),
    (
        'equit',
        'equity',
    ),
    (
        'fund',
        'funds',
    ),
    (
        'trust',
        'funds',
    ),
]
_EXCHANGE_RANKS = {
    'nse': 0,
    'bse': 1,
    'mcx': 2,
    'ncdex': 3,
}
_SHAPE_RANKS = {
    'security': 0,
    'future': 1,
    'option': 2,
}


class AssetClassifier:
    """Names the asset class of a segment and ranks exchanges and shapes for sorting."""

    def asset_class(self, bare_segment: str) -> str:
        """Finds the asset class of a segment.

        Args:
            bare_segment (str): The segment without its exchange, such as "equity_index_options".

        Returns:
            str: One of ASSET_CLASSES; "other" for uncategorised segments.
        """
        for keyword, asset_class in _KEYWORDS:
            if keyword in bare_segment:
                return asset_class
        return 'other'

    def is_index(self, bare_segment: str) -> bool:
        """Says whether a segment is about an index rather than a single company or commodity.

        Args:
            bare_segment (str): The segment without its exchange.

        Returns:
            bool: True for index segments and index derivatives.
        """
        return 'indices' in bare_segment or '_index_' in bare_segment

    def exchange_rank(self, exchange: str) -> int:
        """Ranks an exchange so NSE comes first, then BSE, MCX and NCDEX.

        Args:
            exchange (str): The exchange code.

        Returns:
            int: The rank, lowest first.
        """
        return _EXCHANGE_RANKS.get(exchange, len(_EXCHANGE_RANKS))

    def shape_rank(self, shape: str) -> int:
        """Ranks a shape so securities come before futures and futures before options.

        Args:
            shape (str): "security", "future" or "option".

        Returns:
            int: The rank, lowest first.
        """
        return _SHAPE_RANKS.get(shape, len(_SHAPE_RANKS))

    def bare_segment(self, exchange: str, segment: str) -> str:
        """Removes the exchange prefix from a segment name.

        Args:
            exchange (str): The exchange code, such as "nse".
            segment (str): The prefixed segment, such as "nse_equities".

        Returns:
            str: The segment without the prefix, such as "equities".
        """
        prefix = f'{exchange}_'
        if segment.startswith(prefix):
            return segment[len(prefix) :]
        return segment
