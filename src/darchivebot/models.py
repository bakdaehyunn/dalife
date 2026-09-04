from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any, TypeVar


RecordT = TypeVar("RecordT", bound="Record")


@dataclass(frozen=True)
class Record(Mapping[str, Any]):
    """Immutable typed boundary object for a persisted or joined database record.

    Mapping compatibility is intentional: it preserves the project's existing public
    Python behavior while preventing sqlite3.Row from escaping persistence.
    """

    _values: Mapping[str, Any]

    @classmethod
    def from_mapping(cls: type[RecordT], values: Mapping[str, Any]) -> RecordT:
        return cls(dict(values))

    def __getitem__(self, key: str) -> Any:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def to_dict(self) -> dict[str, Any]:
        return dict(self._values)


@dataclass(frozen=True)
class CaptureRecord(Record):
    pass


@dataclass(frozen=True)
class CaptureFileRecord(Record):
    pass


@dataclass(frozen=True)
class CaptureSummaryRecord(Record):
    pass


@dataclass(frozen=True)
class ArchiveItemRecord(Record):
    pass


@dataclass(frozen=True)
class BotPromptRecord(Record):
    pass


@dataclass(frozen=True)
class ProcessingRunRecord(Record):
    pass


@dataclass(frozen=True)
class InsightNoteRecord(Record):
    pass


@dataclass(frozen=True)
class InsightEvidenceRecord(Record):
    pass


@dataclass(frozen=True)
class AreaRecord(Record):
    pass


@dataclass(frozen=True)
class PlaceRecord(Record):
    pass


@dataclass(frozen=True)
class EvidenceItemRecord(Record):
    pass


@dataclass(frozen=True)
class PlaceEvidenceRecord(Record):
    pass


@dataclass(frozen=True)
class QueryLedgerRecord(Record):
    pass


@dataclass(frozen=True)
class RoutineRecord(Record):
    pass


@dataclass(frozen=True)
class ReminderRecord(Record):
    pass


@dataclass(frozen=True)
class ReminderEventRecord(Record):
    pass


@dataclass(frozen=True)
class CoursePlanRecord(Record):
    pass


@dataclass(frozen=True)
class CoursePlanStopRecord(Record):
    pass


@dataclass(frozen=True)
class UserFeedbackRecord(Record):
    pass


@dataclass(frozen=True)
class RecommendationSessionRecord(Record):
    pass


@dataclass(frozen=True)
class RecommendationCandidateRecord(Record):
    pass
