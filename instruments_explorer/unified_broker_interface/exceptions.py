"""Errors raised when a request to the unified broker interface fails.

Every failed answer from UBI becomes one of the classes below, chosen by its HTTP status code, so callers can catch the base class or one specific failure.

Typical usage example:

  try:
      await client.quote(instrument)
  except exceptions.NotFoundError as error:
      print(error.message, error.detail)
"""

from typing import Any


class UnifiedBrokerInterfaceError(Exception):
    """A failure reported by, or on the way to, the unified broker interface.

    Attributes:
        message: What went wrong, taken from the answer's "error" field when it has one.
        status_code: The HTTP status code of the answer, or None when no answer arrived.
        detail: The parsed JSON body of the answer, or an empty dictionary when there was none.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        detail: Any = None,
    ):
        """Creates the error.

        Args:
            message (str): What went wrong.
            status_code (int | None): The HTTP status code, or None when no answer arrived.
            detail (Any): The parsed JSON body, or None when there was none.
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        if detail is None:
            detail = {}
        self.detail = detail


class BadRequestError(UnifiedBrokerInterfaceError):
    """A request field was missing or invalid (HTTP 400)."""


class AuthenticationError(UnifiedBrokerInterfaceError):
    """The access token or the API key and secret were refused, or no token could be obtained (HTTP 401)."""


class NotFoundError(UnifiedBrokerInterfaceError):
    """The instrument, order or document does not exist (HTTP 404)."""


class ConflictError(UnifiedBrokerInterfaceError):
    """The order has already finished, or two brokers hold the same order id (HTTP 409)."""


class OrderRejectedError(UnifiedBrokerInterfaceError):
    """The broker refused the order (HTTP 422)."""


class RateLimitError(UnifiedBrokerInterfaceError):
    """The broker is at its request limit (HTTP 429)."""


class BrokerError(UnifiedBrokerInterfaceError):
    """No broker's data could be read for the request (HTTP 502)."""


class ServiceUnavailableError(UnifiedBrokerInterfaceError):
    """The data is stale or missing, or no broker can take the order (HTTP 503)."""


class OrderOutcomeUnknownError(UnifiedBrokerInterfaceError):
    """An order request may have reached the broker, but its outcome is unknown (HTTP 504, or a lost answer)."""


class ServerError(UnifiedBrokerInterfaceError):
    """A failure status with no more specific class, such as HTTP 500."""


class UnreachableError(UnifiedBrokerInterfaceError):
    """UBI or its stores could not be reached, so nothing was sent."""
