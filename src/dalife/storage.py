from __future__ import annotations

from pathlib import Path
from typing import Any

from dalife.models import CaptureRecord
from dalife.persistence.database import SqliteDatabase
from dalife.persistence.repositories import (
    ArchiveRepository,
    CaptureRepository,
    InsightRepository,
    PersonalContextRepository,
    ProcessingRepository,
    PromptRepository,
    SearchRepository,
)


class ArchiveStore:
    """Thin compatibility facade over cohesive persistence repositories."""

    def __init__(self, state_dir: Path) -> None:
        self.database = SqliteDatabase(state_dir)
        self.captures = CaptureRepository(self.database)
        self.archives = ArchiveRepository(self.database)
        self.processing = ProcessingRepository(self.database)
        self.search = SearchRepository(self.database)
        self.prompts = PromptRepository(self.database)
        self.insights = InsightRepository(self.database)
        self.personal_context = PersonalContextRepository(self.database)
        self._repositories = (
            self.captures,
            self.archives,
            self.processing,
            self.search,
            self.prompts,
            self.insights,
            self.personal_context,
        )

    @property
    def path(self) -> Path:
        return self.database.path

    def connect(self) -> Any:
        """Compatibility escape hatch for administration and legacy tests only."""
        return self.database.connect()

    def init_db(self) -> None:
        self.database.init_db()

    def __getattr__(self, name: str) -> Any:
        for repository in self._repositories:
            try:
                return object.__getattribute__(repository, name)
            except AttributeError:
                continue
        raise AttributeError(f"{type(self).__name__} does not provide {name}")


__all__ = ["ArchiveStore", "CaptureRecord"]
