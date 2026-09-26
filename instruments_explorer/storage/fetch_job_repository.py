"""The fetch_jobs collection: each run of the knowledge fetchers for a company, with its steps.

Typical usage example:

  jobs = FetchJobRepository(connection.database())
  await jobs.save(job)
  recent = await jobs.recent(20)
"""

from collections.abc import Mapping
from typing import Any

_COLLECTION = 'fetch_jobs'


class FetchJobRepository:
    """Reads and writes fetch jobs in the project's own MongoDB."""

    def __init__(self, database: Any):
        """Wraps the project's database.

        Args:
            database (Any): A pymongo AsyncDatabase, or a stand-in with the same collection methods.
        """
        self._collection = database[_COLLECTION]

    async def save(self, job: Mapping[str, Any]) -> None:
        """Stores a job, replacing its earlier state.

        Args:
            job (Mapping[str, Any]): The job, with "job_id".
        """
        stored = dict(job)
        stored['_id'] = job['job_id']
        await self._collection.replace_one(
            {
                '_id': job['job_id'],
            },
            stored,
            upsert=True,
        )

    async def recent(self, limit: int) -> list[dict[str, Any]]:
        """Lists the latest jobs, newest first.

        Args:
            limit (int): The largest number of jobs.

        Returns:
            list[dict[str, Any]]: The jobs without their _id.
        """
        cursor = self._collection.find({}).sort('created_at', -1).limit(limit)
        jobs = []
        async for document in cursor:
            cleaned = dict(document)
            cleaned.pop('_id', None)
            jobs.append(cleaned)
        return jobs
