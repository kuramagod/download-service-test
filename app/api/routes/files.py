from fastapi import APIRouter, HTTPException, Query

from sqlmodel import select, func 
from app.db.database import SessionDep
from app.enums import SortDirectionEnum
from app.models.downloaded_file import DownloadedFile
from app.schemas.file import FileListResponse, FileListItem, AllFileNamesResponse
from app.schemas.statistics import StatisticsResponse, StatisticsRequest
from app.services.statistics_service import CalculateFileStatistic
from typing import Annotated


router = APIRouter(prefix='/api', tags=["Files"])


@router.get("/files", response_model=FileListResponse)
async def list_files(
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 20,
    sort: SortDirectionEnum = SortDirectionEnum.DESC
) -> FileListResponse:
    order_column = DownloadedFile.downloaded_at
    order_clause = order_column.desc() if sort == SortDirectionEnum.DESC else order_column.asc()

    total_result = await session.execute(select(func.count()).select_from(DownloadedFile))
    total = total_result.scalar()

    rows_result = await session.execute(select(DownloadedFile).order_by(order_clause).offset((page - 1) * size).limit(size))
    rows = rows_result.scalars().all()
    
    items = [FileListItem(filename=row.filename, downloaded_at=row.downloaded_at) for row in rows]
    return FileListResponse(items=items, page=page, size=size, total=total or 0)


@router.get("/files/all", response_model=AllFileNamesResponse)
async def list_all_file_names(session: SessionDep) -> AllFileNamesResponse:
    names = await session.execute(select(DownloadedFile.filename))
    return AllFileNamesResponse(filenames=list(names.scalars()))


@router.post("/files/statistics", response_model=StatisticsResponse)
async def compute_statistics(session: SessionDep, payload: StatisticsRequest) -> StatisticsResponse:
    if not payload.filenames:
        raise HTTPException(status_code=422, detail="filenames must not be empty")

    rows = await session.execute(select(DownloadedFile).where(DownloadedFile.filename.in_(payload.filenames)))
    files = list(rows.scalars())

    missing = set(payload.filenames) - {f.filename for f in files}
    if missing:
        raise HTTPException(status_code=404, detail=f"Unknown files: {sorted(missing)}")

    statistics = CalculateFileStatistic(files=files)

    return StatisticsResponse(total_statistic=statistics.get_total_statistics(), file_statistic=statistics.get_file_statistic())
    
