import logging

from fastapi import FastAPI

from app.database import Base, engine
from app.exceptions import register_exception_handlers
from app.routers.applications import router as applications_router
from app.routers.auth import router as auth_router

logging.basicConfig(level=logging.INFO)

# Creates any tables from models.py that don't exist yet in the database.
# Safe to run every startup — it never touches tables that already exist.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Internship Applications API")

app.include_router(auth_router)
app.include_router(applications_router)

register_exception_handlers(app)
