# Owner: Agnes (Phase 3 - centralized error handling)
"""
App-wide exception handlers.

These exist so that unexpected/DB-level failures are turned into clean,
consistent JSON responses instead of leaking tracebacks or raw driver
errors to the client. This does NOT replace or duplicate the per-route
validation/404 checks already in the routers - it only catches the
failure modes those checks can't cover (e.g. a race condition between
a "does this email already exist?" check and the actual commit).
"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("app.errors")


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """
    Raised when a commit violates a database constraint (e.g. a UNIQUE
    column). We log the real driver error server-side and never send
    it to the client.
    """
    logger.warning(
        "IntegrityError on %s %s: %s", request.method, request.url.path, exc.orig
    )
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "This request conflicts with existing data."},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Last-resort safety net for genuinely unexpected errors (bugs, DB being
    down, etc). Logs the full exception server-side; the client only ever
    sees a generic message - never a stack trace or exception details.
    """
    logger.exception("Unhandled error on %s %s",
                     request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
