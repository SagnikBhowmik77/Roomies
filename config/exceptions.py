"""
API errors carry a stable machine-readable `code` alongside the human
message, so clients can branch on `insufficient_balance` instead of
string-matching English text.
"""

from rest_framework.views import exception_handler as drf_exception_handler


class APIError(Exception):
    """Domain error with a typed code. Subclass, don't raise directly."""

    status_code = 400
    code = "error"
    message = "Request failed."

    def __init__(self, message=None):
        super().__init__(message or self.message)
        self.message = message or self.message


def exception_handler(exc, context):
    if isinstance(exc, APIError):
        from rest_framework.response import Response

        return Response(
            {"code": exc.code, "detail": exc.message}, status=exc.status_code
        )

    response = drf_exception_handler(exc, context)
    if response is not None and isinstance(response.data, dict):
        response.data.setdefault("code", getattr(exc, "default_code", "error"))
    return response
