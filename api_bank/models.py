"""Canonical records shared by discovery, probing, and export."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit


PROTOCOLS = {
    "openai-chat",
    "gemini",
    "cloudflare-workers-ai",
    "cohere-chat",
    "ollama-chat",
    "unknown",
}
AUTH_MODES = {"none", "api_key", "unknown"}
FREE_TIERS = {"unknown", "claimed", "documented", "observed_no_auth"}
SOURCE_KINDS = {"api_docs", "pricing", "models", "changelog", "candidate_evidence", "other"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError(f"Invalid HTTP(S) base URL: {value!r}")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("Base URL cannot contain credentials, a query, or a fragment")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def candidate_id(base_url: str, model: Optional[str], protocol: str) -> str:
    identity = json.dumps(
        [normalize_base_url(base_url), (model or "").strip(), protocol],
        separators=(",", ":"),
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


@dataclass
class Candidate:
    provider: str
    base_url: str
    model: Optional[str] = None
    protocol: str = "openai-chat"
    auth_mode: str = "unknown"
    api_key_env: Optional[str] = None
    account_id_env: Optional[str] = None
    free_tier: str = "unknown"
    source_kind: str = "manual"
    source_url: Optional[str] = None
    evidence_summary: Optional[str] = None
    notes: Optional[str] = None
    status: str = "discovered"
    first_seen: str = field(default_factory=utc_now)
    last_seen: str = field(default_factory=utc_now)
    id: str = ""

    def __post_init__(self) -> None:
        self.provider = self.provider.strip()
        if not self.provider:
            raise ValueError("Candidate provider is required")
        self.base_url = normalize_base_url(self.base_url)
        self.model = self.model.strip() if self.model else None
        if self.protocol not in PROTOCOLS:
            raise ValueError(f"Unsupported protocol: {self.protocol}")
        if self.auth_mode not in AUTH_MODES:
            raise ValueError(f"Unsupported auth mode: {self.auth_mode}")
        if self.free_tier not in FREE_TIERS:
            raise ValueError(f"Unsupported free-tier evidence: {self.free_tier}")
        self.id = self.id or candidate_id(self.base_url, self.model, self.protocol)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Candidate":
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: item for key, item in value.items() if key in allowed})


@dataclass
class ProbeResult:
    candidate_id: str
    request_kind: str
    status: str
    tested_at: str = field(default_factory=utc_now)
    http_status: Optional[int] = None
    latency_ms: Optional[float] = None
    model_returned: Optional[str] = None
    response_preview: Optional[str] = None
    error: Optional[str] = None
    auth_used: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WatchedSource:
    provider: str
    url: str
    kind: str = "candidate_evidence"
    status: str = "pending"
    first_seen: str = field(default_factory=utc_now)
    last_checked: Optional[str] = None
    last_changed: Optional[str] = None
    content_hash: Optional[str] = None
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    error: Optional[str] = None
    id: str = ""

    def __post_init__(self) -> None:
        self.provider = self.provider.strip()
        self.url = normalize_base_url(self.url)
        if self.kind not in SOURCE_KINDS:
            raise ValueError(f"Unsupported source kind: {self.kind}")
        if not self.id:
            self.id = hashlib.sha256(self.url.encode("utf-8")).hexdigest()[:16]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "WatchedSource":
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: item for key, item in value.items() if key in allowed})


@dataclass
class SourceCheck:
    source_id: str
    status: str
    checked_at: str = field(default_factory=utc_now)
    http_status: Optional[int] = None
    latency_ms: Optional[float] = None
    content_hash: Optional[str] = None
    changed: bool = False
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    content_type: Optional[str] = None
    error: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
