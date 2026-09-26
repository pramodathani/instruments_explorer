"""UBI's stored login: its access token and when the token expires.

UBI stores one login document for its whole REST API, in the Redis hash `last_login` under the field `unified_broker_interface` and in MongoDB. The expiry is written in the local time of the machine UBI runs on, as "2026-09-16 16:24:15.239134".

Typical usage example:

  login = LoginDocument.from_document(document)
  if login.is_usable(clock.now(), margin_seconds=30):
      token = login.access_token
"""

import datetime
from collections.abc import Mapping
from typing import Any, Self

_TIME_FORMATS = [
    '%Y-%m-%d %H:%M:%S.%f',
    '%Y-%m-%d %H:%M:%S',
]


class LoginDocument:
    """UBI's access token and its expiry.

    Attributes:
        access_token: The token, or None after UBI's session was disconnected.
        expires_at_text: The expiry exactly as UBI wrote it, or None.
        expires_at_epoch: The expiry in epoch seconds, or None when it is missing or unreadable.
    """

    def __init__(
        self,
        access_token: str | None,
        expires_at_text: str | None,
    ):
        """Creates the login from its token and expiry text.

        Args:
            access_token (str | None): The token, or None.
            expires_at_text (str | None): The expiry as UBI writes it, or None.
        """
        self.access_token = access_token
        self.expires_at_text = expires_at_text
        self.expires_at_epoch = self._parse_expiry(expires_at_text)

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Self:
        """Creates the login from a stored document or a connect answer.

        Args:
            document (Mapping[str, Any]): A document with "access_token" (stored) or "access-token" (connect answer), and "expires_at".

        Returns:
            Self: The login.
        """
        access_token = document.get('access_token')
        if access_token is None:
            access_token = document.get('access-token')
        if access_token is not None:
            access_token = str(access_token)
        expires_at = document.get('expires_at')
        if expires_at is not None:
            expires_at = str(expires_at)
        return cls(access_token, expires_at)

    def is_usable(self, now: float, margin_seconds: float) -> bool:
        """Checks whether the token exists and stays valid for a while longer.

        Args:
            now (float): The current time in epoch seconds.
            margin_seconds (float): How long the token must still be valid for, in seconds.

        Returns:
            bool: True when there is a token that expires more than the margin from now.
        """
        if not self.access_token or self.expires_at_epoch is None:
            return False
        return self.expires_at_epoch - now > margin_seconds

    def __repr__(self) -> str:
        """Describes the login without revealing the token.

        Returns:
            str: A description with the expiry and whether a token is present.
        """
        has_token = bool(self.access_token)
        return (
            f'LoginDocument(has_token={has_token}, '
            f'expires_at={self.expires_at_text!r})'
        )

    def _parse_expiry(self, text: str | None) -> float | None:
        """Reads an expiry written in local time.

        Args:
            text (str | None): The expiry text, or None.

        Returns:
            float | None: Epoch seconds, or None when the text is missing or in no known format.
        """
        if text is None:
            return None
        for time_format in _TIME_FORMATS:
            try:
                moment = datetime.datetime.strptime(text, time_format)  # noqa: DTZ007
            except ValueError:
                continue
            return moment.timestamp()
        return None
