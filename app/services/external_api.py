import asyncio
import httpx
from app.core.logging import logging
from datetime import UTC, datetime, timedelta

from app.core.config import Settings


DEFAULT_RETRY_SECONDS = 5.0
MIN_REQUEST_INTERVAL = 1.0
MAX_REQUEST_INTERVAL = 15.0
BACKOFF_MULTIPLIER = 2.0
DECAY_MULTIPLIER = 0.9   
BLOCK_SAFETY_MARGIN = 5.0


logger = logging.getLogger(__name__)


class ClientBlockedError(Exception): 
    def __init__(self, unblock_at: datetime):
        self.unblock_at = unblock_at
        super().__init__(f"Заблокированы до {unblock_at.isoformat()}")

class ExternalApi:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(base_url=settings.external_api_base_url, timeout=30.0, headers=self._build_headers())
        self._request_lock = asyncio.Lock()
        self._last_request_at: float = 0.0
        self._current_interval = MIN_REQUEST_INTERVAL

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._settings.candidate_id:
            headers['x-candidate-id'] = self._settings.candidate_id
        return headers

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> float:
        raw = response.headers.get("Retry-After")
        if raw is None:
            return DEFAULT_RETRY_SECONDS
        try:
            return max(float(raw), 0.0)
        except ValueError:
            return DEFAULT_RETRY_SECONDS

    async def _throttle(self) -> None:
        async with self._request_lock:
            now = asyncio.get_event_loop().time()
            wait = self._last_request_at + self._current_interval - now
            if wait > 0:
                logger.debug(f"Ожидание {wait:.2f} сек.")
                await asyncio.sleep(wait)
            self._last_request_at = asyncio.get_event_loop().time()

    def _increase_interval(self) -> None:
        old = self._current_interval
        self._current_interval = min(self._current_interval * BACKOFF_MULTIPLIER, MAX_REQUEST_INTERVAL)
        if self._current_interval != old:
            logger.info(f"Увеличиваю паузу между запросами до {self._current_interval:.1f} сек.")

    def _decrease_interval(self) -> None:
        self._current_interval = max(self._current_interval * DECAY_MULTIPLIER, MIN_REQUEST_INTERVAL)

    async def _request(self, method: str, path: str, *, json: object | None = None, headers: dict[str, str] | None = None) -> httpx.Response:
        retry_count = 0
        while True:
            await self._throttle()

            response = await self._client.request(method, path, json=json, headers=headers)

            if response.status_code == 429:
                retry_after = self._parse_retry_after(response)
                self._increase_interval()
                wait_time = retry_after if retry_after > 0 else DEFAULT_RETRY_SECONDS
                logger.warning(f"429. Ждём {wait_time:.1f} сек. Попытка #{retry_count + 1}")

                self._current_interval = max(self._current_interval, wait_time)
                await asyncio.sleep(wait_time)
                retry_count += 1
                continue

            if response.status_code == 403:
                delay = self._parse_retry_after(response) + BLOCK_SAFETY_MARGIN
                unblock_at = datetime.now(UTC) + timedelta(seconds=delay)
                logger.error(f"403. Заблокированы, продолжим не раньше {unblock_at.isoformat()}.")
                raise ClientBlockedError(unblock_at)

            response.raise_for_status()
            self._decrease_interval()
            retry_count = 0
            return response

    async def get_names(self) -> list[str]:
        response = await self._request('GET', '/api/files/names')
        return response.json()["file_names"]

    async def download(self, file_names: list[str]) -> bytes:
        response = await self._request('POST', '/api/files/download', json={"file_names": file_names})
        return response.content

    async def mark_downloaded(self, file_names: list[str]):
        response = await self._request('POST', '/api/files/downloaded', json={"file_names": file_names})
        return response.json()

    async def close(self):
        await self._client.aclose()