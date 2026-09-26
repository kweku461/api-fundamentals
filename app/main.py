from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import Base, engine
from app.routers.applications import router as applications_router
from app.routers.auth import router as auth_router
from app.routers.students import router as students_router


@asynccontextmanager
async def lifespan(app: FastAPI):
	Base.metadata.create_all(bind=engine)
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
