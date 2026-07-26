from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.routes.download import router as download_router
from app.api.routes.files import router as files_router
from app.api.routes.pages import router as pages_router
import app.core.logging


app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")


app.include_router(pages_router)
app.include_router(download_router)
app.include_router(files_router)