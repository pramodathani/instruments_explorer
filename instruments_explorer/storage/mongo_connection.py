"""The connection to the project's own MongoDB.

Typical usage example:

  connection = MongoConnection(explorer_settings)
  report = await connection.check()
  await connection.close()
"""

from typing import Any

import pymongo
import pymongo.errors

from instruments_explorer.configuration import settings


class MongoConnection:
    """Holds one asynchronous MongoDB client for the whole process.

    Attributes:
        database_name: The database that holds the project's collections.
    """

    def __init__(self, explorer_settings: settings.Settings):
        """Creates the client without connecting yet.

        Args:
            explorer_settings (settings.Settings): Supplies the address, credentials, database and timeout.
        """
        self.database_name = explorer_settings.mongodb_database
        timeout_milliseconds = int(
            explorer_settings.store_timeout_seconds * 1000
        )
        self._client = pymongo.AsyncMongoClient(
            explorer_settings.mongodb_uri(),
            serverSelectionTimeoutMS=timeout_milliseconds,
            connectTimeoutMS=timeout_milliseconds,
        )

    def database(self) -> Any:
        """Gives the project's database.

        Returns:
            Any: The pymongo AsyncDatabase for the project's collections.
        """
        return self._client[self.database_name]

    async def check(self) -> dict[str, Any]:
        """Pings MongoDB.

        Returns:
            dict[str, Any]: {"name", "reachable", "detail"}, where detail is the server version or the reason it could not be reached.
        """
        try:
            information = await self._client.server_info()
        except pymongo.errors.PyMongoError as error:
            return {
                'name': 'MongoDB',
                'reachable': False,
                'detail': str(error).split(',')[0],
            }
        return {
            'name': 'MongoDB',
            'reachable': True,
            'detail': f'version {information["version"]}',
        }

    async def close(self) -> None:
        """Closes the client."""
        await self._client.close()
