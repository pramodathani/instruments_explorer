"""Turns an HTTP answer from the unified broker interface into data or an error.

Typical usage example:

  body = ResponseReader().read(response)
"""

import json
from typing import Any

import httpx

from instruments_explorer.unified_broker_interface import exceptions

_EXCEPTION_BY_STATUS = {
    400: exceptions.BadRequestError,
    401: exceptions.AuthenticationError,
    404: exceptions.NotFoundError,
    409: exceptions.ConflictError,
    422: exceptions.OrderRejectedError,
    429: exceptions.RateLimitError,
    502: exceptions.BrokerError,
    503: exceptions.ServiceUnavailableError,
    504: exceptions.OrderOutcomeUnknownError,
}


class ResponseReader:
    """Reads UBI's JSON answers and raises one error class per failure status."""

    def read(self, response: httpx.Response) -> Any:
        """Reads an answer's JSON body, raising for a failure status.

        Args:
            response (httpx.Response): The answer.

        Returns:
            Any: The parsed JSON body, or None when the body is empty or not JSON.

        Raises:
            UnifiedBrokerInterfaceError: A subclass chosen by the status code when the status is not successful.
        """
        body = self._parse_body(response)
        if response.is_success:
            return body
        message = f'UBI answered HTTP {response.status_code}'
        if isinstance(body, dict) and isinstance(body.get('error'), str):
            message = body['error']
        exception_class = _EXCEPTION_BY_STATUS.get(
            response.status_code,
            exceptions.ServerError,
        )
        raise exception_class(
            message,
            status_code=response.status_code,
            detail=body,
        )

    def _parse_body(self, response: httpx.Response) -> Any:
        """Parses a body as JSON.

        Args:
            response (httpx.Response): The answer.

        Returns:
            Any: The parsed body, or None when it is empty or not JSON, such as Flask's HTML error pages.
        """
        if not response.content:
            return None
        try:
            return response.json()
        except json.JSONDecodeError:
            return None
