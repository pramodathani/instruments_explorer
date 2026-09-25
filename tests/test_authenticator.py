"""Tests for the password authenticator."""

import argon2

from instruments_explorer.security import authenticator
from tests import fakes

_PASSWORD = 'correct horse battery'
_HASH = argon2.PasswordHasher(
    time_cost=1,
    memory_cost=8,
    parallelism=1,
).hash(_PASSWORD)


class TestAuthenticator:
    """Tests for Authenticator."""

    def test_verify_accepts_the_right_password(self) -> None:
        """Checks that the right password is accepted."""
        checker = authenticator.Authenticator(_HASH, fakes.FixedClock(0.0))
        assert checker.verify('10.0.0.1', _PASSWORD)

    def test_repeated_failures_lock_the_address_out(self) -> None:
        """Checks that five wrong passwords lock the address out."""
        checker = authenticator.Authenticator(_HASH, fakes.FixedClock(0.0))
        for _ in range(5):
            assert not checker.verify('10.0.0.1', 'wrong')
        assert checker.is_locked_out('10.0.0.1')
        assert not checker.is_locked_out('10.0.0.2')

    def test_lockout_ends_after_the_lockout_period(self) -> None:
        """Checks that old failures are forgotten."""
        time_source = fakes.FixedClock(0.0)
        checker = authenticator.Authenticator(_HASH, time_source)
        for _ in range(5):
            checker.verify('10.0.0.1', 'wrong')
        time_source.advance(301.0)
        assert not checker.is_locked_out('10.0.0.1')
