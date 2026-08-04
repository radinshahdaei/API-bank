"""Read-only change detection for documentation and pricing sources."""

from __future__ import annotations

import hashlib
import time

import requests

from .models import SourceCheck, WatchedSource
from .probe import validate_probe_target


class SourceWatcher:
    def __init__(self, timeout: float = 20, max_bytes: int = 1_000_000, session=None):
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.session = session or requests.Session()

    def check(self, source: WatchedSource) -> SourceCheck:
        validate_probe_target(source.url)
        headers = {
            "Accept": "text/html,application/json,text/plain;q=0.9,*/*;q=0.1",
            "User-Agent": "API-Bank-Source-Watcher/0.1",
        }
        if source.etag:
            headers["If-None-Match"] = source.etag
        if source.last_modified:
            headers["If-Modified-Since"] = source.last_modified
        started = time.monotonic()
        try:
            response = self.session.get(
                source.url,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=False,
                stream=True,
            )
        except requests.Timeout:
            return self._error(source, started, "timeout", "Request timed out")
        except requests.RequestException as exc:
            return self._error(source, started, "network_error", str(exc))

        latency = round((time.monotonic() - started) * 1000, 1)
        if response.status_code == 304:
            return SourceCheck(
                source.id,
                "unchanged",
                http_status=304,
                latency_ms=latency,
                content_hash=source.content_hash,
                etag=response.headers.get("ETag") or source.etag,
                last_modified=response.headers.get("Last-Modified") or source.last_modified,
            )
        if response.status_code != 200:
            return SourceCheck(
                source.id,
                "http_error",
                http_status=response.status_code,
                latency_ms=latency,
                error=(getattr(response, "text", "") or "")[:300],
            )

        declared_size = response.headers.get("Content-Length")
        try:
            declared_size_value = int(declared_size) if declared_size else None
        except ValueError:
            declared_size_value = None
        if declared_size_value is not None and declared_size_value > self.max_bytes:
            return SourceCheck(
                source.id,
                "too_large",
                http_status=200,
                latency_ms=latency,
                error=f"Content-Length {declared_size} exceeds {self.max_bytes} bytes",
            )
        digest = hashlib.sha256()
        size = 0
        try:
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                size += len(chunk)
                if size > self.max_bytes:
                    return SourceCheck(
                        source.id,
                        "too_large",
                        http_status=200,
                        latency_ms=latency,
                        error=f"Response exceeds {self.max_bytes} bytes",
                    )
                digest.update(chunk)
        finally:
            response.close()
        content_hash = digest.hexdigest()
        changed = source.content_hash is not None and source.content_hash != content_hash
        return SourceCheck(
            source.id,
            "ok",
            http_status=200,
            latency_ms=latency,
            content_hash=content_hash,
            changed=changed,
            etag=response.headers.get("ETag"),
            last_modified=response.headers.get("Last-Modified"),
            content_type=response.headers.get("Content-Type"),
        )

    @staticmethod
    def _error(source: WatchedSource, started: float, status: str, error: str) -> SourceCheck:
        return SourceCheck(
            source.id,
            status,
            latency_ms=round((time.monotonic() - started) * 1000, 1),
            error=error[:300],
        )
