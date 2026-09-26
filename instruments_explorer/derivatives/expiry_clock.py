"""Measures the time left until an option expires.

Indian exchange-traded options expire at the close of trading, 15:30 India time, on their expiry date.

Typical usage example:

  years = ExpiryClock(clock).years_until('2026-09-29')
"""

import datetime

from instruments_explorer.utilities import clock

_INDIA = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
_CLOSING_HOUR = 15
_CLOSING_MINUTE = 30
_SECONDS_PER_YEAR = 365.0 * 24 * 60 * 60


class ExpiryClock:
    """Turns an expiry date into the years left from now."""

    def __init__(self, time_source: clock.SystemClock):
        """Creates the clock.

        Args:
            time_source (clock.SystemClock): The source of the current time.
        """
        self._time_source = time_source

    def expiry_moment(self, expiry_date: str) -> float:
        """Finds the moment an expiry date's contracts stop trading.

        Args:
            expiry_date (str): The expiry as "YYYY-MM-DD".

        Returns:
            float: 15:30 India time on that date, in epoch seconds.

        Raises:
            ValueError: The text is not a date.
        """
        day = datetime.date.fromisoformat(expiry_date)
        moment = datetime.datetime(
            day.year,
            day.month,
            day.day,
            _CLOSING_HOUR,
            _CLOSING_MINUTE,
            tzinfo=_INDIA,
        )
        return moment.timestamp()

    def years_until(self, expiry_date: str) -> float:
        """Measures the time left until an expiry.

        Args:
            expiry_date (str): The expiry as "YYYY-MM-DD".

        Returns:
            float: The years left, zero or less once the contracts have stopped trading.

        Raises:
            ValueError: The text is not a date.
        """
        seconds = self.expiry_moment(expiry_date) - self._time_source.now()
        return seconds / _SECONDS_PER_YEAR

    def days_until(self, expiry_date: str) -> float:
        """Measures the time left until an expiry, in days.

        Args:
            expiry_date (str): The expiry as "YYYY-MM-DD".

        Returns:
            float: The calendar days left, with a fraction for the part of today.

        Raises:
            ValueError: The text is not a date.
        """
        return self.years_until(expiry_date) * 365.0
