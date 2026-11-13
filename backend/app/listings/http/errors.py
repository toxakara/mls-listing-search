"""One JSON body for every failed request, whatever the status: {code, message, details}."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pydantic_core import ErrorDetails
from starlette.exceptions import HTTPException

from app.listings.application.ports import ListingsUnavailableError
from app.listings.application.search import UnknownCityError

logger = logging.getLogger(__name__)

# Pydantic writes for developers ("unable to parse string as a number"). These are the errors a
# search can produce, reworded for the person who reads them under a form field. Any other type,
# such as our own "price_range", keeps its message.
_PLAIN_MESSAGES = {
    "float_parsing": "Enter a number, for example 450000.",
    "finite_number": "Enter a number, for example 450000.",
    "int_parsing": "Enter a whole number, for example 3.",
    "int_parsing_size": "Enter a smaller number.",
    # `:g` prints a float bound such as 0.0 as 0.
    "greater_than_equal": "Enter {ge:g} or more.",
    "greater_than": "Enter a number above {gt:g}.",
    "less_than_equal": "Enter {le:g} or less.",
    "string_too_long": "Use at most {max_length} characters.",
    "literal_error": "Choose {expected}.",
    "too_long": "Choose at most {max_length}.",
    "extra_forbidden": "This is not a search option.",
}


def _plain_message(error: ErrorDetails) -> str:
    template = _PLAIN_MESSAGES.get(error["type"])
    return template.format(**error.get("ctx", {})) if template else error["msg"]


class FieldErrorDTO(BaseModel):
    # Query parameter name, e.g. "maxPrice".
    field: str | None
    message: str


class ErrorDTO(BaseModel):
    # Stable and machine-readable: VALIDATION_ERROR, NOT_FOUND, METHOD_NOT_ALLOWED,
    # SERVICE_UNAVAILABLE, INTERNAL_ERROR.
    code: str
    message: str
    # One entry per invalid parameter; empty for every error except validation.
    details: list[FieldErrorDTO] = Field(default_factory=list)


def _error_response(
    status_code: int, error: ErrorDTO, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=error.model_dump(), headers=headers)


def _validation_error_response(details: list[FieldErrorDTO]) -> JSONResponse:
    # Only parameter names and messages are returned, never the rejected input.
    error = ErrorDTO(code="VALIDATION_ERROR", message="Invalid search parameters", details=details)
    return _error_response(422, error)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic locations look like ("query", "status", 0); the parameter name is the second part.
        return _validation_error_response(
            [
                FieldErrorDTO(
                    field=str(error["loc"][1]) if len(error["loc"]) > 1 else None,
                    message=_plain_message(error),
                )
                for error in exc.errors()
            ]
        )

    @app.exception_handler(UnknownCityError)
    async def handle_unknown_city(request: Request, exc: UnknownCityError) -> JSONResponse:
        message = "No listings are in a city with this name."
        if exc.suggestion:
            # A city taken from the data, not the rejected input.
            message += f" Did you mean {exc.suggestion}?"
        return _validation_error_response([FieldErrorDTO(field="city", message=message)])

    @app.exception_handler(ListingsUnavailableError)
    async def handle_listings_unavailable(request: Request, exc: ListingsUnavailableError) -> JSONResponse:
        # The cause (missing file, broken JSON, database down) goes to the log for whoever fixes it,
        # one line per request rather than a traceback; the user only needs to know to try again.
        logger.error("Listings are unavailable: %s", exc)
        message = "Listings are temporarily unavailable. Please try again in a moment."
        return _error_response(503, ErrorDTO(code="SERVICE_UNAVAILABLE", message=message))

    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, exc: HTTPException) -> JSONResponse:
        """Errors raised by the framework itself, such as an unknown path (404) or method (405)."""
        status = HTTPStatus(exc.status_code)
        # `exc.headers` carries the `Allow` header of a 405.
        return _error_response(status, ErrorDTO(code=status.name, message=status.phrase), exc.headers)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # The message is fixed so no internal detail leaks. The server still logs the traceback:
        # Starlette re-raises the exception after this response is sent.
        message = "Something went wrong on our side. Please try again."
        return _error_response(500, ErrorDTO(code="INTERNAL_ERROR", message=message))
