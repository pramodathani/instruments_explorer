"""Test doubles shared by the test modules."""

from typing import Any


class FixedClock:
    """A clock that stays at a set moment until moved.

    Attributes:
        epoch: The moment the clock shows, in epoch seconds.
    """

    def __init__(self, epoch: float):
        """Creates the clock.

        Args:
            epoch (float): The moment the clock shows, in epoch seconds.
        """
        self.epoch = epoch

    def now(self) -> float:
        """Reads the set moment.

        Returns:
            float: The moment in epoch seconds.
        """
        return self.epoch

    def advance(self, seconds: float) -> None:
        """Moves the clock forward.

        Args:
            seconds (float): How far to move, in seconds.
        """
        self.epoch += seconds


class FakeStoreChecker:
    """A stand-in store checker that returns a prepared report.

    Attributes:
        name: The store's name.
        reachable: Whether the report says the store is reachable.
    """

    def __init__(self, name: str, reachable: bool):
        """Creates the stand-in.

        Args:
            name (str): The store's name.
            reachable (bool): Whether the report says the store is reachable.
        """
        self.name = name
        self.reachable = reachable

    async def check(self) -> dict[str, Any]:
        """Returns the prepared report.

        Returns:
            dict[str, Any]: {"name", "reachable", "detail"}.
        """
        return {
            'name': self.name,
            'reachable': self.reachable,
            'detail': 'prepared by the test',
        }
