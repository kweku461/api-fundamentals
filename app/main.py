from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import Base, SessionLocal, engine
from app.models import Role, User
from app.routers.applications import router as applications_router
from app.routers.auth import router as auth_router
from app.routers.students import router as students_router
from app.security import hash_password


def create_admin_if_configured() -> None:
	"""Creates the first admin from the ADMIN_EMAIL / ADMIN_PASSWORD settings, if set."""
	email = os.getenv("ADMIN_EMAIL")
	password = os.getenv("ADMIN_PASSWORD")
	if not email or not password:
		return
	with SessionLocal() as db:
		if db.scalar(select(User).where(User.email == email.lower())) is None:
			db.add(User(email=email.lower(), hashed_password=hash_password(password), role=Role.admin))
			db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
	Base.metadata.create_all(bind=engine)
	create_admin_if_configured()
	yield


app = FastAPI(title="Internship Applications API", lifespan=lifespan)


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(request: Request, exc: StarletteHTTPException):
	return JSONResponse(
		status_code=exc.status_code,
		headers=exc.headers,
		content={"detail": exc.detail, "errors": []},
	)


@app.exception_handler(RequestValidationError)
async def handle_validation_exception(request: Request, exc: RequestValidationError):
	errors = [
		{"location": error["loc"], "message": error["msg"], "type": error["type"]}
		for error in exc.errors()
	]
	return JSONResponse(
		status_code=422,
		content={"detail": "Request validation failed", "errors": errors},
	)


@app.exception_handler(IntegrityError)
async def handle_integrity_exception(request: Request, exc: IntegrityError):
	return JSONResponse(
		status_code=409,
		content={
			"detail": "The request conflicts with existing data.",
			"errors": [],
		},
	)


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception):
	logging.getLogger(__name__).error(
		"Unhandled application exception",
		exc_info=(type(exc), exc, exc.__traceback__),
	)
	return JSONResponse(
		status_code=500,
		content={"detail": "Internal server error", "errors": []},
	)


app.include_router(auth_router)
app.include_router(applications_router)
app.include_router(students_router)


@app.get("/", tags=["health"], summary="Health check")
def health():
	"""Render pings this to confirm the API is running."""
	return {"status": "ok", "docs": "/docs"}
