import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine
from app.exceptions import register_exception_handlers
from app.routers.applications import router as applications_router
from app.routers.auth import router as auth_router
from app.routers.students import router as students_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Internship Applications API", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(applications_router)
app.include_router(students_router)

register_exception_handlers(app)
