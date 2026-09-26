"""Read-only access to UBI's MongoDB: its API credentials and its stored login.

UBI keeps its REST API key and secret in the `settings` collection and its current access token in the `last_login` collection, both under `broker_name` "unified_broker_interface". The reader only ever calls `find_one`.

Typical usage example:

  reader = MongoReader.from_configuration(configuration, timeout_seconds=3)
  api_key, api_secret = reader.api_credentials()
"""

from typing import Any, Self

import pymongo
import pymongo.database

from instruments_explorer.configuration import (
    unified_broker_interface_configuration,
)

APPLICATION_NAME = 'unified_broker_interface'


class MongoReader:
    """Reads UBI's API credentials and login document without ever writing."""

    def __init__(
        self,
        client: pymongo.MongoClient,
        database: pymongo.database.Database,
    ):
        """Wraps a MongoDB client and UBI's database.

        Args:
            client (pymongo.MongoClient): The client, kept so it can be closed.
            database (pymongo.database.Database): UBI's database.
        """
        self._client = client
        self._database = database

    @classmethod
    def from_configuration(
        cls,
        configuration: (
            unified_broker_interface_configuration.UnifiedBrokerInterfaceConfiguration
        ),
        timeout_seconds: float,
    ) -> Self:
        """Creates a reader for UBI's MongoDB.

        Args:
            configuration (UnifiedBrokerInterfaceConfiguration): UBI's store addresses and credentials.
            timeout_seconds (float): How long a query may take before it fails.

        Returns:
            Self: The reader. It connects on its first query.
        """
        timeout_milliseconds = int(timeout_seconds * 1000)
        client = pymongo.MongoClient(
            host=configuration.mongodb_host,
            port=configuration.mongodb_port,
            username=configuration.mongodb_username,
            password=configuration.mongodb_password,
            serverSelectionTimeoutMS=timeout_milliseconds,
            connectTimeoutMS=timeout_milliseconds,
            socketTimeoutMS=timeout_milliseconds,
        )
        return cls(client, client[configuration.mongodb_database])

    def api_credentials(self) -> tuple[str, str]:
        """Reads UBI's REST API key and secret.

        Returns:
            tuple[str, str]: A tuple (api_key, api_secret).

        Raises:
            ValueError: The settings document is missing, or has no key or secret.
            pymongo.errors.PyMongoError: MongoDB could not be read.
        """
        document = self._find_application_document('settings')
        if document is None:
            raise ValueError(
                f'No settings document for {APPLICATION_NAME} in UBI MongoDB.'
            )
        api_key = document.get('api_key')
        api_secret = document.get('api_secret')
        if not api_key or not api_secret:
            raise ValueError(
                f'The {APPLICATION_NAME} settings document has no api_key or api_secret.'
            )
        return str(api_key), str(api_secret)

    def stored_login(self) -> dict[str, Any] | None:
        """Reads UBI's login document, which holds the current access token.

        Returns:
            dict[str, Any] | None: The document without its _id, or None when there is none.

        Raises:
            pymongo.errors.PyMongoError: MongoDB could not be read.
        """
        return self._find_application_document('last_login')

    def close(self) -> None:
        """Closes the client."""
        self._client.close()

    def _find_application_document(
        self,
        collection_name: str,
    ) -> dict[str, Any] | None:
        """Finds the document for UBI's own application in a collection.

        Args:
            collection_name (str): The collection, "settings" or "last_login".

        Returns:
            dict[str, Any] | None: The document without its _id, or None when there is none.

        Raises:
            pymongo.errors.PyMongoError: MongoDB could not be read.
        """
        collection = self._database[collection_name]
        return collection.find_one(
            {
                'broker_name': APPLICATION_NAME,
            },
            {
                '_id': 0,
            },
        )
