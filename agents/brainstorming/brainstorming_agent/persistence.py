from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from .models import AnalysisRecord, JiraEpic, OrchestratedOutput, utc_now


class LearningStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS analyses (
              analysis_id TEXT PRIMARY KEY, jira_key TEXT NOT NULL,
              source_hash TEXT NOT NULL, status TEXT NOT NULL,
              created_at TEXT NOT NULL, completed_at TEXT,
              output_json TEXT, error TEXT
            );
            CREATE TABLE IF NOT EXISTS snapshots (
              analysis_id TEXT PRIMARY KEY, jira_key TEXT NOT NULL,
              snapshot_json TEXT NOT NULL, snapshot_hash TEXT NOT NULL,
              captured_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS jira_posts (
              analysis_id TEXT PRIMARY KEY, jira_key TEXT NOT NULL,
              comment_id TEXT NOT NULL, posted_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    @staticmethod
    def source_hash(epic: JiraEpic) -> str:
        raw = json.dumps(epic.model_dump(mode="json"), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def save_snapshot(self, analysis_id: str, epic: JiraEpic) -> str:
        snapshot = json.dumps(epic.model_dump(mode="json"), sort_keys=True, default=str)
        digest = hashlib.sha256(snapshot.encode()).hexdigest()
        self.connection.execute(
            "INSERT INTO snapshots VALUES (?, ?, ?, ?, ?)",
            (analysis_id, epic.epic_key, snapshot, digest, utc_now().isoformat()),
        )
        self.connection.commit()
        return digest

    def begin(self, analysis_id: str, jira_key: str, source_hash: str) -> None:
        self.connection.execute(
            "INSERT INTO analyses VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (analysis_id, jira_key, source_hash, "running", utc_now().isoformat(), None, None, None),
        )
        self.connection.commit()

    def complete(self, analysis_id: str, output: OrchestratedOutput) -> None:
        self.connection.execute(
            "UPDATE analyses SET status='completed', completed_at=?, output_json=? WHERE analysis_id=?",
            (utc_now().isoformat(), output.model_dump_json(), analysis_id),
        )
        self.connection.commit()

    def fail(self, analysis_id: str, error: str) -> None:
        self.connection.execute(
            "UPDATE analyses SET status='failed', completed_at=?, error=? WHERE analysis_id=?",
            (utc_now().isoformat(), error, analysis_id),
        )
        self.connection.commit()

    def latest(self, jira_key: str) -> AnalysisRecord | None:
        row = self.connection.execute(
            "SELECT * FROM analyses WHERE jira_key=? AND status IN ('completed','approved','posted') "
            "ORDER BY created_at DESC LIMIT 1", (jira_key,),
        ).fetchone()
        if row is None:
            return None
        return AnalysisRecord(
            analysis_id=row["analysis_id"], jira_key=row["jira_key"],
            source_hash=row["source_hash"], status=row["status"],
            created_at=row["created_at"], completed_at=row["completed_at"],
            output=OrchestratedOutput.model_validate_json(row["output_json"]),
        )

    def mark_approved(self, analysis_id: str) -> None:
        self.connection.execute("UPDATE analyses SET status='approved' WHERE analysis_id=?", (analysis_id,))
        self.connection.commit()

    def mark_posted(self, analysis_id: str, jira_key: str, comment_id: str) -> None:
        self.connection.execute("UPDATE analyses SET status='posted' WHERE analysis_id=?", (analysis_id,))
        self.connection.execute(
            "INSERT INTO jira_posts VALUES (?, ?, ?, ?)",
            (analysis_id, jira_key, comment_id, utc_now().isoformat()),
        )
        self.connection.commit()

    def was_posted(self, analysis_id: str) -> bool:
        return self.connection.execute(
            "SELECT 1 FROM jira_posts WHERE analysis_id=?", (analysis_id,)
        ).fetchone() is not None

    def supersede(self, jira_key: str) -> None:
        self.connection.execute(
            "UPDATE analyses SET status='superseded' WHERE jira_key=? AND status IN ('completed','approved')",
            (jira_key,),
        )
        self.connection.commit()
