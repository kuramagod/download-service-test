from pydantic import BaseModel, Field
from app.enums import DownloadStatusEnum
from datetime import datetime


class DownloadStatusResponse(BaseModel):
    status: DownloadStatusEnum = DownloadStatusEnum.IDLE
    started_at: datetime | None = None
    downloaded_count: int = 0
    batch_total: int = 0
    batch_downloaded: int = 0
    current_batch: list[str] = Field(default_factory=list)
    blocked_until: datetime | None = None
    message: str | None = "Скачивание не начало"