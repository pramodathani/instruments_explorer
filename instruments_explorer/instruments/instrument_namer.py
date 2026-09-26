"""Writes a readable name for an instrument from its identity fields.

Typical usage example:

  namer = InstrumentNamer()
  namer.name('option', None, 'NIFTY', '2026-09-29', 25000.0, 'CE')
  # 'NIFTY 29 SEP 2026 25000 CE'
"""

_MONTHS = [
    'JAN',
    'FEB',
    'MAR',
    'APR',
    'MAY',
    'JUN',
    'JUL',
    'AUG',
    'SEP',
    'OCT',
    'NOV',
    'DEC',
]


class InstrumentNamer:
    """Formats names, expiries and strikes the way a person reads them."""

    def name(
        self,
        shape: str,
        symbol: str | None,
        underlying_symbol: str | None,
        expiry_date: str | None,
        strike_price: float | None,
        option_type: str | None,
    ) -> str:
        """Writes an instrument's name.

        Args:
            shape (str): "security", "future" or "option".
            symbol (str | None): The symbol, for a security.
            underlying_symbol (str | None): The underlying, for a derivative.
            expiry_date (str | None): The expiry as "YYYY-MM-DD", for a derivative.
            strike_price (float | None): The strike, for an option.
            option_type (str | None): "CE" or "PE", for an option.

        Returns:
            str: The symbol for a security, "ROOT DD MON YYYY FUT" for a future, and "ROOT DD MON YYYY STRIKE CE" for an option.
        """
        if shape == 'security':
            return symbol or underlying_symbol or ''
        parts = [
            underlying_symbol or symbol or '',
        ]
        if expiry_date is not None:
            parts.append(self.expiry_label(expiry_date))
        if shape == 'future':
            parts.append('FUT')
            return ' '.join(parts)
        if strike_price is not None:
            parts.append(self.strike_label(strike_price))
        if option_type is not None:
            parts.append(option_type)
        return ' '.join(parts)

    def expiry_label(self, expiry_date: str) -> str:
        """Writes an expiry as "DD MON YYYY".

        Args:
            expiry_date (str): The expiry as "YYYY-MM-DD".

        Returns:
            str: The expiry such as "29 SEP 2026", or the text unchanged when it is not a date.
        """
        pieces = expiry_date.split('-')
        if len(pieces) != 3 or not pieces[1].isdigit():
            return expiry_date
        month_number = int(pieces[1])
        if month_number < 1 or month_number > 12:
            return expiry_date
        return f'{pieces[2]} {_MONTHS[month_number - 1]} {pieces[0]}'

    def month_name(self, expiry_date: str) -> str:
        """Finds the three-letter month of an expiry.

        Args:
            expiry_date (str): The expiry as "YYYY-MM-DD".

        Returns:
            str: The month such as "SEP", or an empty string when the text is not a date.
        """
        pieces = expiry_date.split('-')
        if len(pieces) != 3 or not pieces[1].isdigit():
            return ''
        month_number = int(pieces[1])
        if month_number < 1 or month_number > 12:
            return ''
        return _MONTHS[month_number - 1]

    def strike_label(self, strike_price: float) -> str:
        """Writes a strike without a trailing ".0".

        Args:
            strike_price (float): The strike.

        Returns:
            str: "25000" for a whole strike, or up to four decimal places such as "82.25".
        """
        if strike_price == int(strike_price):
            return str(int(strike_price))
        return f'{strike_price:.4f}'.rstrip('0').rstrip('.')
