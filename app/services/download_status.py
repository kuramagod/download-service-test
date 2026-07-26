import json


class DownloadStatusService:
    def __init__(self, redis_client, key: str = "download_status"):
        self.redis = redis_client
        self.key = key

    async def set(self, data: dict):
        await self.redis.set(self.key, json.dumps(data, ensure_ascii=False))

    async def get(self) -> dict:
        raw = await self.redis.get(self.key)
        return json.loads(raw) if raw else {}