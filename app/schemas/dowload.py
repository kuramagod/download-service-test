from pydantic import BaseModel


class DownloadResponse(BaseModel):
    message: str