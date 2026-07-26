from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sqlalchemy.sql import exists
from app.models.downloaded_file import DownloadedFile


class DownloadedFileRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, filename, file_path):
        exists_query = select(exists().where(DownloadedFile.filename == filename))
        if await self.session.scalar(exists_query):
            return None

        self.session.add(DownloadedFile(filename=filename, file_path=file_path))

    async def commit(self):
        await self.session.commit()