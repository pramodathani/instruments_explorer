"""Connection details for the unified broker interface, read from its own .env file.

instruments_explorer never keeps a second copy of UBI's passwords. It reads the addresses and credentials of UBI's Redis and MongoDB, and the address of UBI's REST API, from the `.env` file in UBI's project directory.

Typical usage example:

  configuration = UnifiedBrokerInterfaceConfiguration.load(directory)
  print(configuration.rest_api_base_url)
"""

from pathlib import Path
from typing import Self

import dotenv

_PREFIX = 'UNIFIED_BROKER_INTERFACE_'


class UnifiedBrokerInterfaceConfiguration:
    """The addresses and credentials of UBI's Redis, MongoDB and REST API.

    Attributes:
        project_directory: The unified_broker_interface project directory.
        redis_host: The Redis host.
        redis_port: The Redis port.
        redis_database: The Redis database number.
        redis_username: The Redis user name, or None.
        redis_password: The Redis password, or None.
        mongodb_host: The MongoDB host.
        mongodb_port: The MongoDB port.
        mongodb_database: The MongoDB database name.
        mongodb_username: The MongoDB user name, or None.
        mongodb_password: The MongoDB password, or None.
        rest_api_base_url: The REST API's address without a path, such as "http://127.0.0.1:8080".
    """

    def __init__(
        self,
        project_directory: Path,
        values: dict[str, str | None],
    ):
        """Builds the configuration from the values of a .env file.

        Args:
            project_directory (Path): The unified_broker_interface project directory.
            values (dict[str, str | None]): The variables read from the project's .env file.

        Raises:
            ValueError: A required variable is missing or a port is not a whole number.
        """
        self.project_directory = project_directory
        self._values = values
        self.redis_host = self._required('REDIS_HOST')
        self.redis_port = self._required_number('REDIS_PORT')
        self.redis_database = self._required_number('REDIS_DB')
        self.redis_username = self._optional('REDIS_USERNAME')
        self.redis_password = self._optional('REDIS_PASSWORD')
        self.mongodb_host = self._required('MONGODB_HOST')
        self.mongodb_port = self._required_number('MONGODB_PORT')
        self.mongodb_database = self._required('MONGODB_DB')
        self.mongodb_username = self._optional('MONGODB_USERNAME')
        self.mongodb_password = self._optional('MONGODB_PASSWORD')
        api_host = self._optional('API_HOST')
        if api_host is None:
            api_host = '127.0.0.1'
        api_port = self._optional('API_PORT')
        if api_port is None:
            api_port = '8080'
        self.rest_api_base_url = f'http://{api_host}:{api_port}'

    @classmethod
    def load(cls, project_directory: Path) -> Self:
        """Reads the configuration from the project's .env file.

        Args:
            project_directory (Path): The unified_broker_interface project directory.

        Returns:
            Self: The configuration read from the file.

        Raises:
            FileNotFoundError: The project has no .env file.
            ValueError: A required variable is missing or a port is not a whole number.
        """
        environment_file = project_directory / '.env'
        if not environment_file.is_file():
            raise FileNotFoundError(
                f'No .env file in the unified_broker_interface directory: {environment_file}'
            )
        return cls(project_directory, dotenv.dotenv_values(environment_file))

    def _optional(self, name: str) -> str | None:
        """Reads a variable that may be absent or empty.

        Args:
            name (str): The variable name without the UNIFIED_BROKER_INTERFACE_ prefix.

        Returns:
            str | None: The value, or None when it is absent or empty.
        """
        value = self._values.get(_PREFIX + name)
        if not value:
            return None
        return value

    def _required(self, name: str) -> str:
        """Reads a variable that must be present.

        Args:
            name (str): The variable name without the UNIFIED_BROKER_INTERFACE_ prefix.

        Returns:
            str: The value.

        Raises:
            ValueError: The variable is absent or empty.
        """
        value = self._optional(name)
        if value is None:
            raise ValueError(
                f'Missing variable in the unified_broker_interface .env file: {_PREFIX + name}'
            )
        return value

    def _required_number(self, name: str) -> int:
        """Reads a variable that must hold a whole number.

        Args:
            name (str): The variable name without the UNIFIED_BROKER_INTERFACE_ prefix.

        Returns:
            int: The value as a number.

        Raises:
            ValueError: The variable is absent, empty or not a whole number.
        """
        text = self._required(name)
        try:
            return int(text)
        except ValueError as error:
            raise ValueError(
                f'Not a whole number in the unified_broker_interface .env file: {_PREFIX + name}={text!r}'
            ) from error
