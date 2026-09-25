"""The source of the current time.

Components take a clock object instead of calling `time.time()` directly, so tests can run them at any moment.

Typical usage example:

  clock = SystemClock()
  now = clock.now()
"""

import time


class SystemClock:
    """The real wall clock."""

    def now(self) -> float:
        """Reads the current time.

        Returns:
            float: Seconds since the Unix epoch.
        """
        return time.time()
