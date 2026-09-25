"""Tests for the settings class."""

import pytest

from instruments_explorer.configuration import settings


class TestSettings:
    """Tests for Settings."""

    def _settings(self, **values: object) -> settings.Settings:
        """Builds settings that ignore the real environment and .env.

        Args:
            **values (object): Settings to set.

        Returns:
            settings.Settings: The settings.
        """
        return settings.Settings(_env_file=None, **values)

    def test_mongodb_uri_quotes_the_password(self) -> None:
        """Checks that special characters in the password are escaped."""
        explorer_settings = self._settings(
            mongodb_username='explorer',
            mongodb_password='p@ss/word',
            mongodb_port=3003,
        )
        assert explorer_settings.mongodb_uri() == (
            'mongodb://explorer:p%40ss%2Fword@127.0.0.1:3003/?authSource=admin'
        )

    def test_chromadb_url(self) -> None:
        """Checks the ChromaDB base address."""
        explorer_settings = self._settings(chromadb_port=3004)
        assert explorer_settings.chromadb_url() == 'http://127.0.0.1:3004'

    def test_assistant_configured_follows_the_key(self) -> None:
        """Checks that the assistant counts as configured only with a key."""
        assert not self._settings().assistant_configured()
        assert self._settings(
            anthropic_api_key='key',
        ).assistant_configured()

    def test_default_model_is_opus_five_point_five(self) -> None:
        """Checks the chat assistant's default model."""
        assert self._settings().claude_model == 'claude-opus-5-5'

    def test_require_security_values_refuses_an_empty_hash(self) -> None:
        """Checks that a missing password hash stops the start-up."""
        with pytest.raises(ValueError, match='PASSWORD_HASH'):
            self._settings(session_secret='secret').require_security_values()

    def test_require_security_values_refuses_an_empty_secret(self) -> None:
        """Checks that a missing session secret stops the start-up."""
        with pytest.raises(ValueError, match='SESSION_SECRET'):
            self._settings(password_hash='hash').require_security_values()
