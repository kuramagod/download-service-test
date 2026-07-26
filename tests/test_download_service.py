from unittest.mock import AsyncMock

import pytest

from app.api.routes import download as download_route
from app.enums import DownloadStatusEnum
from app.services import download_service as download_module


class DummySettings:
    pass


@pytest.mark.asyncio
async def test_download_all_marks_stopped_on_exception(monkeypatch):
    class DummyStatusService:
        async def set(self, payload):
            return None

    monkeypatch.setattr(download_module, "DownloadStatusService", lambda *_args, **_kwargs: DummyStatusService())

    service = download_module.DownloadService(settings=DummySettings(), session=AsyncMock())
    service._download_all_once = AsyncMock(side_effect=RuntimeError("boom"))
    service._persist_progress = AsyncMock()

    with pytest.raises(RuntimeError):
        await service.download_all()

    assert service._progress.status == DownloadStatusEnum.STOPPED


@pytest.mark.asyncio
async def test_download_all_marks_stopped_on_shutdown_signal(monkeypatch):
    class DummyStatusService:
        async def set(self, payload):
            return None

    monkeypatch.setattr(download_module, "DownloadStatusService", lambda *_args, **_kwargs: DummyStatusService())

    service = download_module.DownloadService(settings=DummySettings(), session=AsyncMock())
    service._download_all_once = AsyncMock(side_effect=KeyboardInterrupt())
    service._persist_progress = AsyncMock()

    with pytest.raises(KeyboardInterrupt):
        await service.download_all()

    assert service._progress.status == DownloadStatusEnum.STOPPED


@pytest.mark.asyncio
async def test_stop_download_requests_stop_and_updates_status(monkeypatch):
    saved_payload = {}
    requested = {}

    def fake_request_download_stop():
        requested["value"] = True

    class DummyStatusService:
        async def get(self):
            return {"status": "running", "message": "working"}

        async def set(self, payload):
            saved_payload["value"] = payload

    monkeypatch.setattr(download_route, "request_download_stop", fake_request_download_stop)
    monkeypatch.setattr(download_route, "DownloadStatusService", lambda *_args, **_kwargs: DummyStatusService())

    result = await download_route.stop_download()

    assert requested["value"] is True
    assert saved_payload["value"]["status"] == DownloadStatusEnum.STOPPED.value
    assert saved_payload["value"]["message"] == "Скачивание остановлено пользователем"
    assert result.message == "Скачивание остановлено"
