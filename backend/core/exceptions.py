"""Uniform API error envelope.

Every non-2xx API response produced by DRF is normalised to::

    {
      "success": false,
      "error": {
        "code": "validation_error",
        "message": "Human readable summary",
        "details": {"field": ["reason", ...]}
      }
    }

so the React client only ever has to parse one shape.
"""

import logging

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("opsportal.api")


class BusinessRuleError(exceptions.APIException):
    """Raised when a request is well-formed but violates a business rule.

    Example: confirming a challan whose lines exceed the available stock.
    """

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This action violates a business rule."
    default_code = "business_rule_error"

    def __init__(self, message=None, details=None, code=None):
        self.details = details or {}
        super().__init__(message or self.default_detail, code or self.default_code)


class InsufficientStockError(BusinessRuleError):
    default_detail = "Insufficient stock for one or more products."
    default_code = "insufficient_stock"


_CODE_BY_STATUS = {
    400: "bad_request",
    401: "authentication_failed",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    415: "unsupported_media_type",
    429: "throttled",
    500: "server_error",
}


def _summarise(detail):
    """Pull a single human-readable sentence out of a DRF error detail."""
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        return _summarise(detail[0]) if detail else "Invalid request."
    if isinstance(detail, dict):
        for key, value in detail.items():
            message = _summarise(value)
            if key in ("non_field_errors", "detail"):
                return message
            return f"{key}: {message}"
    return str(detail)


def api_exception_handler(exc, context):
    """DRF ``EXCEPTION_HANDLER``."""

    # Translate framework/database exceptions into DRF ones first.
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()
    elif isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(getattr(exc, "message_dict", None) or list(exc.messages))
    elif isinstance(exc, IntegrityError):
        logger.warning("Database integrity error: %s", exc)
        exc = exceptions.ValidationError(
            {"non_field_errors": ["This operation conflicts with existing data."]}
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        # Unhandled exception -> let Django's 500 handling (and the logs) take
        # over rather than swallowing a real bug behind a pretty envelope.
        logger.exception("Unhandled API exception", exc_info=exc)
        return None

    detail = response.data
    status_code = response.status_code

    if isinstance(exc, exceptions.ValidationError):
        code = "validation_error"
        details = detail if isinstance(detail, dict) else {"non_field_errors": detail}
        message = _summarise(detail)
    elif isinstance(exc, BusinessRuleError):
        codes = exc.get_codes()
        code = codes if isinstance(codes, str) else exc.default_code
        details = getattr(exc, "details", {}) or {}
        message = _summarise(detail)
    else:
        codes = exc.get_codes() if hasattr(exc, "get_codes") else None
        code = codes if isinstance(codes, str) else _CODE_BY_STATUS.get(status_code, "error")
        details = detail if isinstance(detail, dict) and len(detail) > 1 else {}
        message = _summarise(detail)

    response.data = {
        "success": False,
        "error": {"code": code, "message": message, "details": details},
    }
    return response


def error_response(message, *, code="error", details=None, status_code=status.HTTP_400_BAD_REQUEST):
    """Build the same envelope manually (used by a few non-DRF views)."""
    return Response(
        {"success": False, "error": {"code": code, "message": message, "details": details or {}}},
        status=status_code,
    )
