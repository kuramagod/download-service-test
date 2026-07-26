from fastapi import APIRouter, BackgroundTasks

from app.core.config import settings
from app.db.database import async_session_factory
from app.services.download_service import DownloadService
from app.services.download_status import DownloadStatusService
from app.schemas.dowload import DownloadResponse
from app.schemas.status import DownloadStatusResponse
from app.core.redis import redis_client
from app.enums import DownloadStatusEnum


router = APIRouter(prefix='/api/download', tags=["Download"])


async def _run_download():
    async with async_session_factory() as session:
        service = DownloadService(settings=settings, session=session)
        await service.download_all()


@router.post("/start", response_model=DownloadResponse)
async def download(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_download)
    return DownloadResponse(message="Скачавание началось...")


@router.get("/status", response_model=DownloadStatusResponse)
async def download_status():
    status_service = DownloadStatusService(redis_client)
    status = await status_service.get()
    return DownloadStatusResponse(**status)


@router.post("/stop", response_model=DownloadResponse)
async def stop_download():
    await redis_client.publish(DownloadService.STOP_CHANNEL, "stop")
    await redis_client.setex(DownloadService.STOP_FLAG_KEY, 3600, "true")

    status_service = DownloadStatusService(redis_client)
    current = await status_service.get()

    current["status"] = DownloadStatusEnum.STOPPED.value
    current["message"] = "Скачивание остановлено пользователем"

    await status_service.set(current)

    return DownloadResponse(message="Скачивание остановлено")