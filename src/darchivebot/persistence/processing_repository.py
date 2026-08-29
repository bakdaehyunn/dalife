from __future__ import annotations

import uuid
from typing import Any

from darchivebot.models import ProcessingRunRecord
from darchivebot.persistence.common import records, utc_now
from darchivebot.persistence.database import RepositoryBase


class ProcessingRepository(RepositoryBase):
    def processing_runs_for_capture_ids(self, capture_ids: list[str]) -> dict[str, list[ProcessingRunRecord]]:
        self.init_db()
        if not capture_ids:
            return {}
        placeholders = ",".join("?" for _ in capture_ids)
        with self.connect() as conn:
            rows = records(
                conn.execute(
                    f"""
                    SELECT * FROM processing_runs
                    WHERE capture_id IN ({placeholders})
                    ORDER BY started_at DESC
                    """,
                    tuple(capture_ids),
                ),
                ProcessingRunRecord,
            )
        grouped: dict[str, list[ProcessingRunRecord]] = {capture_id: [] for capture_id in capture_ids}
        for row in rows:
            grouped.setdefault(str(row["capture_id"]), []).append(row)
        return grouped

    def start_processing_run(
        self,
        *,
        capture_id: str,
        processor: str,
        input_path: str = "",
    ) -> str:
        self.init_db()
        run_id = str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO processing_runs(id, capture_id, processor, status, input_path, started_at)
                VALUES (?, ?, ?, 'running', ?, ?)
                """,
                (run_id, capture_id, processor, input_path, utc_now()),
            )
        return run_id

    def finish_processing_run(
        self,
        *,
        run_id: str,
        status: str,
        output_path: str = "",
        error: str = "",
    ) -> None:
        self.init_db()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE processing_runs
                SET status = ?, output_path = ?, error = ?, finished_at = ?
                WHERE id = ?
                """,
                (status, output_path, error, utc_now(), run_id),
            )
