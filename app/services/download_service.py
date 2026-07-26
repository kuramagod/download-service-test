import asyncio
import io
from app.core.logging import logging
import zipfile
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import datetime, UTC
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.redis import redis_client
from app.repositories.dowload_file_repository import DownloadedFileRepository
from app.services.external_api import ExternalApi, ClientBlockedError
from app.services.download_status import DownloadStatusService
from app.enums import DownloadStatusEnum


NSK = ZoneInfo("Asia/Novosibirsk")
logger = logging.getLogger(__name__)


@dataclass
class DownloadProgress:
    status: DownloadStatusEnum = DownloadStatusEnum.IDLE
    started_at: datetime | None = None
    downloaded_count: int = 0
    batch_total: int = 0
    batch_downloaded: int = 0
    current_batch: list[str] = field(default_factory=list)
    blocked_until: datetime | None = None
    message: str | None = None

    @classmethod
    def from_dict(cls, data: dict | None) -> "DownloadProgress":
        if not data:
            return cls()

        return cls(
            status=DownloadStatusEnum(data.get("status", DownloadStatusEnum.IDLE.value)),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            downloaded_count=data.get("downloaded_count", 0),
            batch_total=data.get("batch_total", 0),
            batch_downloaded=data.get("batch_downloaded", 0),
            current_batch=data.get("current_batch", []) or [],
            blocked_until=datetime.fromisoformat(data["blocked_until"]) if data.get("blocked_until") else None,
            message=data.get("message"),
        )

    def to_dict(self) -> dict:
        return {
            "status": self.status.value if isinstance(self.status, DownloadStatusEnum) else self.status,
            "started_at": self.started_at.astimezone(NSK).isoformat() if self.started_at else None,
            "downloaded_count": self.downloaded_count,
            "batch_total": self.batch_total,
            "batch_downloaded": self.batch_downloaded,
            "current_batch": self.current_batch,
            "blocked_until": self.blocked_until.astimezone(NSK).isoformat() if self.blocked_until else None,
            "message": self.message,
        }


class DownloadService:
    STOP_CHANNEL = "download:stop"
    STOP_FLAG_KEY = "download:stop_flag"

    def __init__(self, settings: Settings, session: AsyncSession):
        self._settings = settings
        self._repository = DownloadedFileRepository(session)
        self._status = DownloadStatusService(redis_client)
        self._progress = DownloadProgress()
        self._stop_requested = False
        self._pubsub = None

    async def _load_progress(self) -> None:
        data = await self._status.get()
        self._progress = DownloadProgress.from_dict(data)

    async def _init_pubsub(self):
        if self._pubsub is None:
            self._pubsub = redis_client.pubsub()
            await self._pubsub.subscribe(self.STOP_CHANNEL)
            logger.info(f"Подписка на канал остановки {self.STOP_CHANNEL}")

    async def _check_stop_signal(self):
        stop_flag = await redis_client.get(self.STOP_FLAG_KEY)
        if stop_flag in ("true", b"true"):
            self._stop_requested = True
            await redis_client.delete(self.STOP_FLAG_KEY)
            return

        if self._pubsub:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=0.001,
                )
                if message and message["data"] in ("stop", b"stop"):
                    self._stop_requested = True
                    logger.info("Получен сигнал остановки через PubSub")
            except Exception as e:
                logger.error(f"Ошибка при проверке PubSub: {e}")

    async def reset_stop_flag(self):
        self._stop_requested = False
        await redis_client.delete(self.STOP_FLAG_KEY)

    async def _should_stop(self) -> bool:
        await self._check_stop_signal()

        if not self._stop_requested:
            return False

        self._progress.status = DownloadStatusEnum.STOPPED
        self._progress.message = "Скачивание остановлено пользователем"
        await self._persist_progress()
        logger.info("Процесс остановлен: Скачивание остановлено пользователем")
        return True

    async def download_all(self):
        await self._load_progress()
        await self._init_pubsub()
        await self.reset_stop_flag()

        self._progress.status = DownloadStatusEnum.RUNNING
        if self._progress.started_at is None:
            self._progress.started_at = datetime.now(UTC)

        await self._persist_progress()

        try:
            while True:
                if await self._should_stop():
                    return

                await self._download_all_once()
                break
        finally:
            if self._pubsub:
                try:
                    await self._pubsub.unsubscribe(self.STOP_CHANNEL)
                    await self._pubsub.close()
                except Exception as e:
                    logger.error(f"Ошибка при закрытии PubSub: {e}")

    async def _download_all_once(self):
        external_api = ExternalApi(settings=self._settings)
        try:
            while True:
                if await self._should_stop():
                    return

                file_names = await external_api.get_names()

                if not file_names:
                    self._progress.status = DownloadStatusEnum.DONE
                    self._progress.message = "Скачивание завершено"
                    await self._persist_progress()
                    return

                self._progress.current_batch = file_names
                self._progress.batch_total = len(file_names)
                self._progress.batch_downloaded = 0
                self._progress.message = (f"Скачано {self._progress.downloaded_count}")
                await self._persist_progress()

                batches = [file_names[i : i + 3] for i in range(0, len(file_names), 3)]

                for batch in batches:
                    if await self._should_stop():
                        return

                    files = await external_api.download(batch)
                    saved_files = self.save_files(files)

                    for filename, file_path in saved_files:
                        await self._repository.create(filename, file_path)
                    await self._repository.commit()

                    await external_api.mark_downloaded(batch)

                    self._progress.downloaded_count += len(batch)
                    self._progress.batch_downloaded += len(batch)
                    self._progress.message = (f"Скачано {self._progress.downloaded_count}")
                    await self._persist_progress()

                self._progress.current_batch = []
                self._progress.batch_total = 0
                self._progress.batch_downloaded = 0

        except ClientBlockedError as exc:
            self._progress.status = DownloadStatusEnum.BLOCKED
            self._progress.blocked_until = exc.unblock_at
            self._progress.message = f"Сервис заблокирован до {exc.unblock_at.isoformat()}"
            await self._persist_progress()
        finally:
            await external_api.close()

    async def _persist_progress(self) -> None:
        await self._status.set(self._progress.to_dict())

    def save_files(self, zip_data):
        output_dir = Path(__file__).parent.parent / "files"
        output_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_file:
            saved_files = []
            for file_name in zip_file.namelist():
                zip_file.extract(file_name, output_dir)
                file_path = output_dir / file_name
                logger.info(f"Распакован файл {file_path}.")
                saved_files.append((file_name, str(file_path)))

            return saved_files