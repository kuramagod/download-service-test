from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    downloaded_at: datetime


class FileListItem(BaseModel):
    filename: str
    downloaded_at: datetime


class FileListResponse(BaseModel):
    items: list[FileListItem]
    total: int
    page: int
    size: int


class CalculateRequest(BaseModel):
    file_ids: list[int]


class AllFileNamesResponse(BaseModel):
    filenames: list[str]