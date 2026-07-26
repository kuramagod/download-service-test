from enum import StrEnum


class DownloadStatusEnum(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    BLOCKED = "blocked"
    DONE = "done"
    ERROR = "error"


class SortDirectionEnum(StrEnum):
    ASC = "asc"
    DESC = "desc"