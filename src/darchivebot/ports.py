from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from darchivebot.models import (
    ArchiveItemRecord,
    BotPromptRecord,
    CaptureFileRecord,
    CaptureRecord,
    CaptureSummaryRecord,
    InsightEvidenceRecord,
    InsightNoteRecord,
    ProcessingRunRecord,
)


class DatabasePort(Protocol):
    path: Path

    def init_db(self) -> None: ...


class CaptureRepositoryPort(Protocol):
    def add_capture(self, **values: Any) -> str: ...
    def add_file(self, **values: Any) -> str: ...
    def pending_captures(self, limit: int) -> list[CaptureRecord]: ...
    def files_for_capture(self, capture_id: str) -> list[CaptureFileRecord]: ...
    def list_captures(self, limit: int) -> list[CaptureRecord]: ...
    def list_capture_summaries(self, limit: int, interest: str = "") -> list[CaptureSummaryRecord]: ...
    def get_capture(self, capture_id: str) -> CaptureRecord | None: ...
    def mark_capture_status(self, capture_id: str, status: str) -> None: ...
    def mark_capture_processed(self, capture_id: str) -> None: ...
    def mark_capture_failed(self, capture_id: str, *, error: str) -> CaptureRecord: ...


class ArchiveRepositoryPort(Protocol):
    def get_archive_item(self, capture_id: str) -> ArchiveItemRecord | None: ...
    def list_archive_items_for_graph(self, limit: int | None = None) -> list[ArchiveItemRecord]: ...
    def upsert_extracted_text(self, *, capture_id: str, source: str, text: str, metadata: Any = None) -> None: ...
    def upsert_archive_item(self, capture_id: str, item: dict[str, Any], **metadata: Any) -> None: ...
    def archive_interpretations_for_capture(self, capture_id: str) -> list[ArchiveItemRecord]: ...


class ProcessingRepositoryPort(Protocol):
    def processing_runs_for_capture_ids(self, capture_ids: list[str]) -> dict[str, list[ProcessingRunRecord]]: ...
    def start_processing_run(self, *, capture_id: str, processor: str, input_path: str = "") -> str: ...
    def finish_processing_run(self, *, run_id: str, status: str, output_path: str = "", error: str = "") -> None: ...


class SearchRepositoryPort(Protocol):
    def rebuild_search_index(self) -> dict[str, Any]: ...
    def search_archive(self, query: str, *, limit: int = 20) -> list[ArchiveItemRecord]: ...
    def review_archive_items(
        self,
        *,
        limit: int = 20,
        needs_review_only: bool = False,
        revisit_only: bool = False,
    ) -> list[ArchiveItemRecord]: ...


class PromptRepositoryPort(Protocol):
    def create_bot_prompt(self, **values: Any) -> BotPromptRecord: ...
    def get_bot_prompt(self, prompt_id: str) -> BotPromptRecord | None: ...
    def mark_bot_prompt_sent(self, prompt_id: str, *, telegram_message_id: str = "") -> None: ...
    def record_bot_prompt_choice(self, prompt_id: str, **values: Any) -> BotPromptRecord | None: ...


class InsightRepositoryPort(Protocol):
    def create_insight_note(self, note: dict[str, Any]) -> str: ...
    def list_insight_notes(self, limit: int = 20) -> list[InsightNoteRecord]: ...
    def get_insight_note(self, note_id: str) -> InsightNoteRecord | None: ...
    def insight_note_items(self, note_id: str) -> list[InsightEvidenceRecord]: ...


class ProcessingStore(CaptureRepositoryPort, ArchiveRepositoryPort, ProcessingRepositoryPort, Protocol):
    pass


class AnalysisStore(ArchiveRepositoryPort, ProcessingRepositoryPort, Protocol):
    pass


class RetrievalStore(CaptureRepositoryPort, ArchiveRepositoryPort, SearchRepositoryPort, Protocol):
    pass


class PromptStore(CaptureRepositoryPort, ArchiveRepositoryPort, SearchRepositoryPort, PromptRepositoryPort, InsightRepositoryPort, Protocol):
    pass


class InsightSynthesisStore(ArchiveRepositoryPort, InsightRepositoryPort, Protocol):
    pass


class TelegramStore(CaptureRepositoryPort, PromptRepositoryPort, Protocol):
    pass


class WebStore(RetrievalStore, InsightRepositoryPort, Protocol):
    pass
