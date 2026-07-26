from datetime import datetime
from sqlmodel import SQLModel, Field
from typing import Optional


class DownloadedFile(SQLModel, table=True):
    __tablename__ = "downloaded_files"

    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str = Field(unique=True, index=True)
    file_path: str
    downloaded_at: datetime = Field(default_factory=datetime.now)