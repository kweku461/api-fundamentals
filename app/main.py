from fastapi import FastAPI

from app.routers.applications import router as applications_router


app = FastAPI(title="Internship Applications API")
app.include_router(applications_router)