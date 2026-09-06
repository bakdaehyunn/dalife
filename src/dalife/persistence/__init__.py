"""SQLite persistence implementation and focused repository components."""

from dalife.persistence.database import SqliteDatabase
from dalife.persistence.repositories import (
    ArchiveRepository,
    CaptureRepository,
    InsightRepository,
    ProcessingRepository,
    PromptRepository,
    SearchRepository,
)

__all__ = [
    "ArchiveRepository",
    "CaptureRepository",
    "InsightRepository",
    "ProcessingRepository",
    "PromptRepository",
    "SearchRepository",
    "SqliteDatabase",
]
