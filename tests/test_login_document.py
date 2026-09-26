"""Tests for reading UBI's stored login document."""

import datetime

from instruments_explorer.unified_broker_interface import login_document

_NOW = datetime.datetime(2026, 9, 16, 10, 0, 0).timestamp()  # noqa: DTZ001


class TestLoginDocument:
    """Tests for LoginDocument."""

    def test_stored_document_is_read(self) -> None:
        """Checks that the token and a local-time expiry with microseconds are read."""
        login = login_document.LoginDocument.from_document(
            {
                'broker_name': 'unified_broker_interface',
                'access_token': 'abc',
                'last_login': '2026-09-15 16:24:15.239134',
                'expires_at': '2026-09-16 16:24:15.239134',
            }
        )
        expected_expiry = datetime.datetime(  # noqa: DTZ001
            2026,
            9,
            16,
            16,
            24,
            15,
            239134,
        ).timestamp()
        assert login.access_token == 'abc'
        assert login.expires_at_epoch == expected_expiry

    def test_connect_answer_is_read(self) -> None:
        """Checks that the connect answer's hyphenated token key is read."""
        login = login_document.LoginDocument.from_document(
            {
                'access-token': 'xyz',
                'expires_at': '2026-09-16 11:00:00.000000',
            }
        )
        assert login.access_token == 'xyz'
        assert login.is_usable(_NOW, 30.0)

    def test_token_close_to_expiry_is_not_usable(self) -> None:
        """Checks that a token expiring within the margin is not used."""
        login = login_document.LoginDocument(
            'abc',
            '2026-09-16 10:00:20.000000',
        )
        assert not login.is_usable(_NOW, 30.0)
        assert login.is_usable(_NOW, 10.0)

    def test_disconnected_session_is_not_usable(self) -> None:
        """Checks that UBI's disconnected document, with no token, is not used."""
        login = login_document.LoginDocument.from_document(
            {
                'access_token': None,
                'expires_at': None,
            }
        )
        assert not login.is_usable(_NOW, 30.0)

    def test_unreadable_expiry_is_not_usable(self) -> None:
        """Checks that a token with an expiry in an unknown format is not used."""
        login = login_document.LoginDocument('abc', 'tomorrow')
        assert login.expires_at_epoch is None
        assert not login.is_usable(_NOW, 30.0)

    def test_description_hides_the_token(self) -> None:
        """Checks that printing a login never shows the token."""
        login = login_document.LoginDocument(
            'secret-token-value',
            '2026-09-16 16:24:15.239134',
        )
        assert 'secret-token-value' not in repr(login)
        assert 'has_token=True' in repr(login)
