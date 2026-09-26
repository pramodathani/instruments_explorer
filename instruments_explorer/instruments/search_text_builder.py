"""Lists the words an instrument can be found by in the full-text index.

Typical usage example:

  builder = SearchTextBuilder()
  builder.build(record)  # 'nifty nse option options opt 29 sep 2026 29sep sep26 25000 ce call'
"""

from typing import Any

from instruments_explorer.instruments import instrument_namer

_OPTION_WORDS = {
    'CE': 'call',
    'PE': 'put',
}


class SearchTextBuilder:
    """Builds the lower-case search text of one instrument."""

    def __init__(self):
        """Creates the builder."""
        self._namer = instrument_namer.InstrumentNamer()

    def build(self, record: dict[str, Any]) -> str:
        """Collects the words for one instrument.

        The words cover its names, exchange, kind, expiry written several ways, strike and option type, so "nifty sep 25000 ce", "reliance fut" and "gold oct" all find what a person means.

        Args:
            record (dict[str, Any]): The instrument's identity fields.

        Returns:
            str: The words, lower case, separated by spaces.
        """
        words = []
        for field in [
            'symbol',
            'underlying_symbol',
        ]:
            value = record.get(field)
            if value:
                words.append(str(value))
        words.append(record['exchange'])
        shape = record['shape']
        if shape == 'future':
            words.append('fut future futures')
        elif shape == 'option':
            words.append('opt option options')
        expiry_date = record.get('expiry_date')
        if expiry_date:
            label = self._namer.expiry_label(expiry_date)
            month = self._namer.month_name(expiry_date).lower()
            day = expiry_date[8:10]
            year = expiry_date[:4]
            words.append(label)
            if month:
                words.append(f'{day}{month} {month}{year[2:]}')
        strike_price = record.get('strike_price')
        if strike_price is not None:
            words.append(self._namer.strike_label(strike_price))
        option_type = record.get('option_type')
        if option_type:
            words.append(option_type)
            words.append(_OPTION_WORDS.get(option_type, ''))
        return ' '.join(words).lower()
