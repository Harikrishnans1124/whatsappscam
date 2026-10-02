"""RFC 9457 Problem Details error handling for FastAPI."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def create_problem_response(
    status_code: int,
    title: str,
    detail: str,
    instance: str | None = None,
    problem_type: str = "about:blank",
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "type": problem_type,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if instance:
        content["instance"] = instance
    if extra:
        content.update(extra)

    return JSONResponse(
        status_code=status_code,
        content=content,
        headers={"Content-Type": "application/problem+json"},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Extract readable detail messages
    error_messages = []
    for err in exc.errors():
        msg = err.get("msg", "Validation error")
        loc = err.get("loc", [])
        field = loc[-1] if loc else "body"
        # If msg starts with "Value error, ", clean it up
        clean_msg = msg.replace("Value error, ", "").strip()
        error_messages.append(f"{field}: {clean_msg}" if field != "body" else clean_msg)

    detail = "; ".join(error_messages) or "Invalid request body."
    return create_problem_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        title="Invalid request body",
        detail=detail,
        instance=request.url.path,
        problem_type="https://trustshop.example/problems/validation-error",
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    title_map = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        429: "Too Many Requests",
        500: "Internal Server Error",
        503: "Service Unavailable",
    }
    title = title_map.get(exc.status_code, "HTTP Error")
    return create_problem_response(
        status_code=exc.status_code,
        title=title,
        detail=str(exc.detail),
        instance=request.url.path,
        problem_type=f"https://trustshop.example/problems/{exc.status_code}",
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return create_problem_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        title="Internal Server Error",
        detail="An unexpected server error occurred.",
        instance=request.url.path,
        problem_type="https://trustshop.example/problems/internal-error",
    )


def setup_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
