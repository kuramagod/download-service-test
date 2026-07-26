from pydantic import BaseModel


class FileStatistic(BaseModel):
    filename: str
    digits: dict[str, int]


class StatisticsResponse(BaseModel):
    total_statistic: dict[str, int]
    file_statistic: list[FileStatistic]

class StatisticsRequest(BaseModel):
    filenames: list[str]