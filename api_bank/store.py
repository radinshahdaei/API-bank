"""SQLite persistence for candidates and immutable probe history."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from .models import Candidate, ProbeResult, SourceCheck, WatchedSource, utc_now


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
    "empty_response",
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
                account_id_env TEXT,
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
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_checked TEXT,
                last_changed TEXT,
                content_hash TEXT,
                etag TEXT,
                last_modified TEXT,
                error TEXT
            );
            CREATE TABLE IF NOT EXISTS source_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL REFERENCES sources(id),
                status TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                http_status INTEGER,
                latency_ms REAL,
                content_hash TEXT,
                changed INTEGER NOT NULL DEFAULT 0,
                etag TEXT,
                last_modified TEXT,
                content_type TEXT,
                error TEXT
            );
            CREATE INDEX IF NOT EXISTS source_checks_source_checked
                ON source_checks(source_id, checked_at DESC);
            """
        )
        candidate_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(candidates)")
        }
        if "account_id_env" not in candidate_columns:
            self.connection.execute("ALTER TABLE candidates ADD COLUMN account_id_env TEXT")
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
                candidate.account_id_env = previous.account_id_env
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
                "empty_response": "empty_response",
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
            if result.status == "working" and not result.auth_used:
                self.connection.execute(
                    """
                    UPDATE candidates
                    SET auth_mode = 'none',
                        free_tier = CASE
                            WHEN free_tier = 'documented' THEN free_tier
                            ELSE 'observed_no_auth'
                        END
                    WHERE id = ?
                    """,
                    (result.candidate_id,),
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

    def probe_history(
        self, candidate_id: str, request_kind: str = "chat", limit: int = 100
    ) -> list[dict]:
        rows = self.connection.execute(
            "SELECT * FROM probes WHERE candidate_id = ? AND request_kind = ? "
            "ORDER BY tested_at DESC, id DESC LIMIT ?",
            (candidate_id, request_kind, limit),
        )
        history = []
        for row in rows:
            item = dict(row)
            item["auth_used"] = bool(item["auth_used"])
            item["metadata"] = json.loads(item.pop("metadata_json"))
            history.append(item)
        return history

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

    def upsert_source(self, source: WatchedSource) -> bool:
        existing = self.connection.execute(
            "SELECT * FROM sources WHERE id = ?", (source.id,)
        ).fetchone()
        if existing:
            previous = WatchedSource.from_dict(dict(existing))
            source.first_seen = previous.first_seen
            source.status = previous.status
            source.last_checked = previous.last_checked
            source.last_changed = previous.last_changed
            source.content_hash = previous.content_hash
            source.etag = previous.etag
            source.last_modified = previous.last_modified
            source.error = previous.error
        value = source.as_dict()
        columns = list(value)
        assignments = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "id")
        self.connection.execute(
            f"INSERT INTO sources ({', '.join(columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)}) "
            f"ON CONFLICT(id) DO UPDATE SET {assignments}",
            [value[column] for column in columns],
        )
        self.connection.commit()
        return existing is None

    def get_source(self, source_id: str) -> Optional[WatchedSource]:
        row = self.connection.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        return WatchedSource.from_dict(dict(row)) if row else None

    def list_sources(self, status: Optional[str] = None) -> list[WatchedSource]:
        sql = "SELECT * FROM sources"
        params: tuple[str, ...] = ()
        if status:
            sql += " WHERE status = ?"
            params = (status,)
        sql += " ORDER BY provider COLLATE NOCASE, url"
        return [WatchedSource.from_dict(dict(row)) for row in self.connection.execute(sql, params)]

    def add_source_check(self, check: SourceCheck) -> None:
        value = check.as_dict()
        value["changed"] = int(value["changed"])
        columns = list(value)
        self.connection.execute(
            f"INSERT INTO source_checks ({', '.join(columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)})",
            [value[column] for column in columns],
        )
        status = "changed" if check.changed else check.status
        changed_at = check.checked_at if check.changed else None
        self.connection.execute(
            """
            UPDATE sources
            SET status = ?, last_checked = ?,
                last_changed = COALESCE(?, last_changed),
                content_hash = COALESCE(?, content_hash),
                etag = COALESCE(?, etag),
                last_modified = COALESCE(?, last_modified),
                error = ?
            WHERE id = ?
            """,
            (
                status,
                check.checked_at,
                changed_at,
                check.content_hash,
                check.etag,
                check.last_modified,
                check.error,
                check.source_id,
            ),
        )
        self.connection.commit()
