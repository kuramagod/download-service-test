from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates


router = APIRouter(tags=["Pages"])


templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def download_page(request: Request):
    return templates.TemplateResponse(request, "download.html")


@router.get("/files")
async def files_page(request: Request):
    return templates.TemplateResponse(request, "files.html")