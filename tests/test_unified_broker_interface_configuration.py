"""Tests for reading UBI's connection details from its .env file."""

from pathlib import Path

import pytest

from instruments_explorer.configuration import (
    unified_broker_interface_configuration,
)

_COMPLETE_FILE = '\n'.join(
    [
        'UNIFIED_BROKER_INTERFACE_REDIS_HOST=127.0.0.1',
        'UNIFIED_BROKER_INTERFACE_REDIS_PORT=1002',
        'UNIFIED_BROKER_INTERFACE_REDIS_DB=0',
        'UNIFIED_BROKER_INTERFACE_REDIS_USERNAME=',
        'UNIFIED_BROKER_INTERFACE_REDIS_PASSWORD=redis-secret',
        'UNIFIED_BROKER_INTERFACE_MONGODB_HOST=127.0.0.1',
        'UNIFIED_BROKER_INTERFACE_MONGODB_PORT=1003',
        'UNIFIED_BROKER_INTERFACE_MONGODB_DB=ubi',
        'UNIFIED_BROKER_INTERFACE_MONGODB_USERNAME=admin',
        'UNIFIED_BROKER_INTERFACE_MONGODB_PASSWORD=mongo-secret',
    ]
)


class TestUnifiedBrokerInterfaceConfiguration:
    """Tests for UnifiedBrokerInterfaceConfiguration."""

    def _write(self, directory: Path, text: str) -> None:
        """Writes a .env file into a directory.

        Args:
            directory (Path): The directory.
            text (str): The file's contents.
        """
        (directory / '.env').write_text(text)

    def _load(
        self,
        directory: Path,
    ) -> unified_broker_interface_configuration.UnifiedBrokerInterfaceConfiguration:
        """Loads the configuration from a directory's .env file.

        Args:
            directory (Path): The directory.

        Returns:
            UnifiedBrokerInterfaceConfiguration: The configuration.

        Raises:
            FileNotFoundError: The directory has no .env file.
            ValueError: A required variable is missing or invalid.
        """
        configuration_class = unified_broker_interface_configuration.UnifiedBrokerInterfaceConfiguration
        return configuration_class.load(directory)

    def test_reads_stores_and_default_api_address(self, tmp_path: Path) -> None:
        """Checks that store details are read and the API address defaults to 127.0.0.1:8080.

        Args:
            tmp_path (Path): pytest's temporary directory.
        """
        self._write(tmp_path, _COMPLETE_FILE)
        configuration = self._load(tmp_path)
        assert configuration.redis_port == 1002
        assert configuration.redis_username is None
        assert configuration.redis_password == 'redis-secret'
        assert configuration.mongodb_database == 'ubi'
        assert configuration.rest_api_base_url == 'http://127.0.0.1:8080'

    def test_reads_api_address_when_set(self, tmp_path: Path) -> None:
        """Checks that UBI's own API host and port are used when set.

        Args:
            tmp_path (Path): pytest's temporary directory.
        """
        extra_lines = '\n'.join(
            [
                'UNIFIED_BROKER_INTERFACE_API_HOST=10.0.0.5',
                'UNIFIED_BROKER_INTERFACE_API_PORT=9000',
            ]
        )
        self._write(tmp_path, _COMPLETE_FILE + '\n' + extra_lines)
        configuration = self._load(tmp_path)
        assert configuration.rest_api_base_url == 'http://10.0.0.5:9000'

    def test_missing_file_is_reported(self, tmp_path: Path) -> None:
        """Checks that a missing .env file raises FileNotFoundError.

        Args:
            tmp_path (Path): pytest's temporary directory.

        Raises:
            AssertionError: No error was raised.
        """
        with pytest.raises(FileNotFoundError):
            self._load(tmp_path)

    def test_missing_variable_is_reported(self, tmp_path: Path) -> None:
        """Checks that a missing required variable names the variable.

        Args:
            tmp_path (Path): pytest's temporary directory.

        Raises:
            AssertionError: No error was raised.
        """
        text = _COMPLETE_FILE.replace(
            'UNIFIED_BROKER_INTERFACE_MONGODB_DB=ubi',
            '',
        )
        self._write(tmp_path, text)
        with pytest.raises(ValueError, match='MONGODB_DB'):
            self._load(tmp_path)

    def test_port_must_be_a_number(self, tmp_path: Path) -> None:
        """Checks that a port that is not a number is refused.

        Args:
            tmp_path (Path): pytest's temporary directory.

        Raises:
            AssertionError: No error was raised.
        """
        text = _COMPLETE_FILE.replace('REDIS_PORT=1002', 'REDIS_PORT=abc')
        self._write(tmp_path, text)
        with pytest.raises(ValueError, match='REDIS_PORT'):
            self._load(tmp_path)
