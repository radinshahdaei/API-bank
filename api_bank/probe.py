"""Small, deterministic, and credential-safe HTTP probes."""

from __future__ import annotations

import ipaddress
import os
import time
from typing import Optional
from urllib.parse import urlsplit

import requests

from .models import Candidate, ProbeResult


PROBE_PROMPT = "Reply with exactly: API_BANK_OK"


def validate_probe_target(base_url: str, allow_http: bool = False) -> None:
    parts = urlsplit(base_url)
    if parts.scheme != "https" and not (allow_http and parts.scheme == "http"):
        raise ValueError("Probes require HTTPS unless --allow-http is explicitly set")
    hostname = (parts.hostname or "").lower()
    if hostname == "localhost" or hostname.endswith(".local"):
        raise ValueError("Local probe targets are not allowed")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return
    if not address.is_global:
        raise ValueError("Private, loopback, link-local, and reserved IP targets are not allowed")


class Prober:
    def __init__(self, timeout: float = 20, allow_http: bool = False, session=None):
        self.timeout = timeout
        self.allow_http = allow_http
        self.session = session or requests.Session()

    def probe_chat(self, candidate: Candidate, with_auth: bool = False) -> ProbeResult:
        validate_probe_target(candidate.base_url, self.allow_http)
        if candidate.protocol != "openai-chat":
            return ProbeResult(
                candidate.id,
                "chat",
                "skipped",
                error=f"No {candidate.protocol} probe adapter is available yet",
            )
        if not candidate.model:
            return ProbeResult(candidate.id, "chat", "skipped", error="No model configured")

        headers, auth_used, auth_error = self._headers(candidate, with_auth)
        if auth_error:
            return auth_error

        url = f"{candidate.base_url}/chat/completions"
        payload = {
            "model": candidate.model,
            "messages": [{"role": "user", "content": PROBE_PROMPT}],
            "max_tokens": 8,
            "temperature": 0,
            "stream": False,
        }
        started = time.monotonic()
        try:
            response = self.session.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.Timeout:
            return self._error(candidate, started, "timeout", "Request timed out", auth_used)
        except requests.RequestException as exc:
            return self._error(candidate, started, "network_error", str(exc), auth_used)

        latency = round((time.monotonic() - started) * 1000, 1)
        status = response.status_code
        if status == 200:
            try:
                data = response.json()
                message = data["choices"][0]["message"]
                text = message.get("content") or ""
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                return ProbeResult(
                    candidate.id,
                    "chat",
                    "invalid_response",
                    http_status=status,
                    latency_ms=latency,
                    error=f"Invalid OpenAI-compatible response: {exc}",
                    auth_used=auth_used,
                )
            return ProbeResult(
                candidate.id,
                "chat",
                "working",
                http_status=status,
                latency_ms=latency,
                model_returned=data.get("model"),
                response_preview=text[:160],
                auth_used=auth_used,
                metadata={"finish_reason": data["choices"][0].get("finish_reason")},
            )

        mapped = {
            401: "auth_required",
            403: "auth_required",
            404: "not_found",
            408: "timeout",
            429: "rate_limited",
        }.get(status, "server_error" if status >= 500 else "rejected")
        return ProbeResult(
            candidate.id,
            "chat",
            mapped,
            http_status=status,
            latency_ms=latency,
            error=response.text[:300],
            auth_used=auth_used,
        )

    def probe_models(self, candidate: Candidate, with_auth: bool = False) -> ProbeResult:
        """Enumerate an OpenAI-compatible model catalog without selecting a model."""
        validate_probe_target(candidate.base_url, self.allow_http)
        if candidate.protocol != "openai-chat":
            return ProbeResult(
                candidate.id,
                "models",
                "skipped",
                error=f"No {candidate.protocol} model-list adapter is available yet",
            )
        headers, auth_used, auth_error = self._headers(candidate, with_auth)
        if auth_error:
            auth_error.request_kind = "models"
            return auth_error
        started = time.monotonic()
        try:
            response = self.session.get(
                f"{candidate.base_url}/models",
                headers=headers,
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.Timeout:
            result = self._error(candidate, started, "timeout", "Request timed out", auth_used)
            result.request_kind = "models"
            return result
        except requests.RequestException as exc:
            result = self._error(candidate, started, "network_error", str(exc), auth_used)
            result.request_kind = "models"
            return result

        latency = round((time.monotonic() - started) * 1000, 1)
        if response.status_code == 200:
            try:
                data = response.json()
                raw_models = data["data"]
                models = sorted(
                    {
                        item["id"].strip()
                        for item in raw_models
                        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip()
                    }
                )
            except (ValueError, KeyError, TypeError) as exc:
                return ProbeResult(
                    candidate.id,
                    "models",
                    "invalid_response",
                    http_status=200,
                    latency_ms=latency,
                    error=f"Invalid OpenAI-compatible model list: {exc}",
                    auth_used=auth_used,
                )
            return ProbeResult(
                candidate.id,
                "models",
                "working",
                http_status=200,
                latency_ms=latency,
                auth_used=auth_used,
                metadata={"models": models[:500], "model_count": len(models)},
            )

        mapped = {
            401: "auth_required",
            403: "auth_required",
            404: "not_found",
            408: "timeout",
            429: "rate_limited",
        }.get(response.status_code, "server_error" if response.status_code >= 500 else "rejected")
        return ProbeResult(
            candidate.id,
            "models",
            mapped,
            http_status=response.status_code,
            latency_ms=latency,
            error=response.text[:300],
            auth_used=auth_used,
        )

    @staticmethod
    def _headers(candidate: Candidate, with_auth: bool):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if not with_auth:
            return headers, False, None
        if not candidate.api_key_env:
            return headers, False, ProbeResult(
                candidate.id, "chat", "skipped", error="No API key environment variable configured"
            )
        api_key = os.environ.get(candidate.api_key_env)
        if not api_key:
            return headers, False, ProbeResult(
                candidate.id,
                "chat",
                "skipped",
                error=f"Environment variable {candidate.api_key_env} is not set",
            )
        headers["Authorization"] = f"Bearer {api_key}"
        return headers, True, None

    @staticmethod
    def _error(
        candidate: Candidate,
        started: float,
        status: str,
        error: str,
        auth_used: bool,
    ) -> ProbeResult:
        return ProbeResult(
            candidate.id,
            "chat",
            status,
            latency_ms=round((time.monotonic() - started) * 1000, 1),
            error=error[:300],
            auth_used=auth_used,
        )
