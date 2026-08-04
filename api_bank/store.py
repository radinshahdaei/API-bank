"""SQLite persistence for candidates and immutable probe history."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from .models import Candidate, ProbeResult, utc_now


DEFAULT_DB = Path(".api-bank/state.db")

SOURCE_PRIORITY = {
    "legacy_catalog": 0,
    "legacy_verified": 1,
    "manual": 2,
    "agent_research": 3,
}

PROBE_STATUSES = {
    "verified",
    "auth_required",
    "invalid_endpoint",
    "invalid_response",
    "rate_limited",
    "unreachable",
    "server_error",
    "rejected",
}


class Store:
    def __init__(self, path: str | Path = DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self._migrate()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def _migrate(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                base_url TEXT NOT NULL,
                model TEXT,
                protocol TEXT NOT NULL,
                auth_mode TEXT NOT NULL,
                api_key_env TEXT,
                free_tier TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                source_url TEXT,
                evidence_summary TEXT,
                notes TEXT,
                status TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS probes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id TEXT NOT NULL REFERENCES candidates(id),
                request_kind TEXT NOT NULL,
                status TEXT NOT NULL,
                tested_at TEXT NOT NULL,
                http_status INTEGER,
                latency_ms REAL,
                model_returned TEXT,
                response_preview TEXT,
                error TEXT,
                auth_used INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS probes_candidate_tested
                ON probes(candidate_id, tested_at DESC);
            """
        )
        self.connection.commit()

    def upsert_candidate(self, candidate: Candidate) -> bool:
        existing = self.connection.execute(
            "SELECT * FROM candidates WHERE id = ?", (candidate.id,)
        ).fetchone()
        if existing:
            previous = Candidate.from_dict(dict(existing))
            candidate.first_seen = previous.first_seen
            if previous.status in PROBE_STATUSES:
                candidate.status = previous.status
            if SOURCE_PRIORITY.get(candidate.source_kind, 0) < SOURCE_PRIORITY.get(previous.source_kind, 0):
                candidate.provider = previous.provider
                candidate.auth_mode = previous.auth_mode
                candidate.api_key_env = previous.api_key_env
                candidate.free_tier = previous.free_tier
                candidate.source_kind = previous.source_kind
                candidate.source_url = previous.source_url
                candidate.evidence_summary = previous.evidence_summary
                candidate.notes = previous.notes
        values = candidate.as_dict()
        columns = list(values)
        assignments = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "id")
        self.connection.execute(
            f"INSERT INTO candidates ({', '.join(columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)}) "
            f"ON CONFLICT(id) DO UPDATE SET {assignments}",
            [values[column] for column in columns],
        )
        self.connection.commit()
        return existing is None

    def get_candidate(self, candidate_id: str) -> Optional[Candidate]:
        row = self.connection.execute(
            "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
        return Candidate.from_dict(dict(row)) if row else None

    def list_candidates(self, status: Optional[str] = None) -> list[Candidate]:
        sql = "SELECT * FROM candidates"
        params: tuple[str, ...] = ()
        if status:
            sql += " WHERE status = ?"
            params = (status,)
        sql += " ORDER BY provider COLLATE NOCASE, model COLLATE NOCASE"
        return [Candidate.from_dict(dict(row)) for row in self.connection.execute(sql, params)]

    def add_probe(self, result: ProbeResult) -> None:
        value = result.as_dict()
        metadata = json.dumps(value.pop("metadata"), ensure_ascii=False, sort_keys=True)
        value["auth_used"] = int(value["auth_used"])
        columns = list(value) + ["metadata_json"]
        params = list(value.values()) + [metadata]
        self.connection.execute(
            f"INSERT INTO probes ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
            params,
        )
        if result.request_kind == "chat":
            candidate_status = {
                "working": "verified",
                "auth_required": "auth_required",
                "not_found": "invalid_endpoint",
                "invalid_response": "invalid_response",
                "rate_limited": "rate_limited",
                "timeout": "unreachable",
                "network_error": "unreachable",
                "server_error": "server_error",
                "rejected": "rejected",
            }.get(result.status)
            if candidate_status:
                self.connection.execute(
                    "UPDATE candidates SET status = ?, last_seen = ? WHERE id = ?",
                    (candidate_status, utc_now(), result.candidate_id),
                )
        self.connection.commit()

    def latest_probe(self, candidate_id: str, request_kind: str = "chat") -> Optional[dict]:
        row = self.connection.execute(
            "SELECT * FROM probes WHERE candidate_id = ? AND request_kind = ? "
            "ORDER BY tested_at DESC, id DESC LIMIT 1",
            (candidate_id, request_kind),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["auth_used"] = bool(result["auth_used"])
        result["metadata"] = json.loads(result.pop("metadata_json"))
        return result

    def verification_rows(self) -> Iterable[dict]:
        return self.connection.execute(
            """
            SELECT c.*, p.tested_at, p.http_status, p.latency_ms,
                   p.model_returned, p.auth_used
            FROM candidates c
            JOIN probes p ON p.id = (
                SELECT p2.id FROM probes p2
                WHERE p2.candidate_id = c.id AND p2.request_kind = 'chat'
                ORDER BY p2.tested_at DESC, p2.id DESC LIMIT 1
            )
            WHERE c.status = 'verified' AND p.status = 'working'
            ORDER BY c.provider COLLATE NOCASE, c.model COLLATE NOCASE
            """
        )
