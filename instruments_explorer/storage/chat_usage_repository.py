"""The chat_usage collection: how many tokens the assistant has used on each day, for the daily limit.

Typical usage example:

  usage = ChatUsageRepository(connection.database())
  await usage.add('2026-09-26', {'input_tokens': 1200, 'output_tokens': 300})
  totals = await usage.day('2026-09-26')
"""

from collections.abc import Mapping
from typing import Any

_COLLECTION = 'chat_usage'

USAGE_FIELDS = [
    'input_tokens',
    'output_tokens',
    'cache_read_input_tokens',
    'cache_creation_input_tokens',
]


class ChatUsageRepository:
    """Adds up the assistant's token use per day in the project's own MongoDB."""

    def __init__(self, database: Any):
        """Wraps the project's database.

        Args:
            database (Any): A pymongo AsyncDatabase, or a stand-in with the same collection methods.
        """
        self._collection = database[_COLLECTION]

    async def add(self, day: str, usage: Mapping[str, int]) -> None:
        """Adds one response's tokens to a day's totals.

        Args:
            day (str): The day as "YYYY-MM-DD" in India time.
            usage (Mapping[str, int]): The response's token counts, by the names in USAGE_FIELDS.
        """
        increments = {
            'responses': 1,
        }
        for field in USAGE_FIELDS:
            increments[field] = int(usage.get(field, 0) or 0)
        await self._collection.update_one(
            {
                '_id': day,
            },
            {
                '$set': {
                    'day': day,
                },
                '$inc': increments,
            },
            upsert=True,
        )

    async def day(self, day: str) -> dict[str, int]:
        """Reads a day's totals.

        Args:
            day (str): The day as "YYYY-MM-DD" in India time.

        Returns:
            dict[str, int]: "responses" and every field in USAGE_FIELDS, zero when nothing was used.
        """
        document = await self._collection.find_one(
            {
                '_id': day,
            }
        )
        totals = {
            'responses': 0,
        }
        for field in USAGE_FIELDS:
            totals[field] = 0
        if document is not None:
            for name in totals:
                totals[name] = int(document.get(name, 0) or 0)
        return totals
