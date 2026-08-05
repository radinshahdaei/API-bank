"""Small, deterministic, credential-safe probes with protocol adapters."""

from __future__ import annotations

import ipaddress
import os
import time
from urllib.parse import quote, urlsplit

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
        if not candidate.model:
            return ProbeResult(candidate.id, "chat", "skipped", error="No model configured")
        adapters = {
            "openai-chat": self._probe_openai,
            "gemini": self._probe_gemini,
            "cohere-chat": self._probe_cohere,
            "ollama-chat": self._probe_ollama,
            "cloudflare-workers-ai": self._probe_cloudflare,
        }
        adapter = adapters.get(candidate.protocol)
        if not adapter:
            return ProbeResult(
                candidate.id,
                "chat",
                "skipped",
                error=f"No {candidate.protocol} probe adapter is available",
            )
        return adapter(candidate, with_auth)

    def _probe_openai(self, candidate: Candidate, with_auth: bool) -> ProbeResult:
        key, auth_error = self._credential(candidate, with_auth)
        if auth_error:
            return auth_error
        headers = self._json_headers(key)
        payload = {
            "model": candidate.model,
            "messages": [{"role": "user", "content": PROBE_PROMPT}],
            "max_tokens": 32,
            "temperature": 0,
            "stream": False,
            "reasoning_effort": "none",
        }
        response, latency_or_error = self._post(
            candidate,
            f"{candidate.base_url}/chat/completions",
            headers,
            payload,
            bool(key),
        )
        if response is None:
            return latency_or_error
        latency = latency_or_error
        if response.status_code == 400:
            # Some compatible APIs reject reasoning_effort. Retry once without it.
            payload.pop("reasoning_effort")
            response, latency_or_error = self._post(
                candidate,
                f"{candidate.base_url}/chat/completions",
                headers,
                payload,
                bool(key),
            )
            if response is None:
                return latency_or_error
            latency += latency_or_error
        if response.status_code != 200:
            return self._http_failure(candidate, response, latency, bool(key))
        try:
            data = response.json()
            choice = data["choices"][0]
            text = (choice["message"].get("content") or "")[:160]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            return self._invalid(candidate, latency, bool(key), "OpenAI-compatible", exc)
        return self._working(
            candidate,
            latency,
            bool(key),
            text,
            data.get("model"),
            {"finish_reason": choice.get("finish_reason")},
        )

    def _probe_gemini(self, candidate: Candidate, with_auth: bool) -> ProbeResult:
        key, auth_error = self._credential(candidate, with_auth)
        if auth_error:
            return auth_error
        model = candidate.model.removeprefix("models/")
        url = f"{candidate.base_url}/models/{quote(model, safe='')}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": PROBE_PROMPT}]}],
            "generationConfig": {"maxOutputTokens": 8, "temperature": 0},
        }
        response, latency_or_error = self._post(
            candidate,
            url,
            self._json_headers(),
            payload,
            bool(key),
            params={"key": key} if key else None,
        )
        if response is None:
            return latency_or_error
        latency = latency_or_error
        if response.status_code != 200:
            return self._http_failure(candidate, response, latency, bool(key))
        try:
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"][:160]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            return self._invalid(candidate, latency, bool(key), "Gemini", exc)
        return self._working(candidate, latency, bool(key), text, model)

    def _probe_cohere(self, candidate: Candidate, with_auth: bool) -> ProbeResult:
        key, auth_error = self._credential(candidate, with_auth)
        if auth_error:
            return auth_error
        payload = {
            "model": candidate.model,
            "messages": [{"role": "user", "content": PROBE_PROMPT}],
            "max_tokens": 8,
            "temperature": 0,
        }
        response, latency_or_error = self._post(
            candidate,
            f"{candidate.base_url}/chat",
            self._json_headers(key),
            payload,
            bool(key),
        )
        if response is None:
            return latency_or_error
        latency = latency_or_error
        if response.status_code != 200:
            return self._http_failure(candidate, response, latency, bool(key))
        try:
            data = response.json()
            content = data["message"]["content"]
            text = next(item["text"] for item in content if item.get("type", "text") == "text")[:160]
        except (ValueError, KeyError, IndexError, TypeError, StopIteration) as exc:
            return self._invalid(candidate, latency, bool(key), "Cohere", exc)
        return self._working(candidate, latency, bool(key), text, candidate.model)

    def _probe_ollama(self, candidate: Candidate, with_auth: bool) -> ProbeResult:
        key, auth_error = self._credential(candidate, with_auth)
        if auth_error:
            return auth_error
        payload = {
            "model": candidate.model,
            "messages": [{"role": "user", "content": PROBE_PROMPT}],
            "stream": False,
            "options": {"temperature": 0, "num_predict": 8},
        }
        response, latency_or_error = self._post(
            candidate,
            f"{candidate.base_url}/api/chat",
            self._json_headers(key),
            payload,
            bool(key),
        )
        if response is None:
            return latency_or_error
        latency = latency_or_error
        if response.status_code != 200:
            return self._http_failure(candidate, response, latency, bool(key))
        try:
            data = response.json()
            text = data["message"]["content"][:160]
        except (ValueError, KeyError, TypeError) as exc:
            return self._invalid(candidate, latency, bool(key), "Ollama", exc)
        return self._working(candidate, latency, bool(key), text, data.get("model", candidate.model))

    def _probe_cloudflare(self, candidate: Candidate, with_auth: bool) -> ProbeResult:
        key, auth_error = self._credential(candidate, with_auth)
        if auth_error:
            return auth_error
        base_url = candidate.base_url
        if "{ACCOUNT_ID}" in base_url:
            if not with_auth or not candidate.account_id_env:
                return ProbeResult(
                    candidate.id,
                    "chat",
                    "skipped",
                    error="Cloudflare probing requires --with-auth and account_id_env",
                )
            account_id = os.environ.get(candidate.account_id_env)
            if not account_id:
                return ProbeResult(
                    candidate.id,
                    "chat",
                    "skipped",
                    error=f"Environment variable {candidate.account_id_env} is not set",
                )
            base_url = base_url.replace("{ACCOUNT_ID}", quote(account_id, safe=""))
        validate_probe_target(base_url, self.allow_http)
        payload = {
            "messages": [{"role": "user", "content": PROBE_PROMPT}],
            "max_tokens": 8,
        }
        response, latency_or_error = self._post(
            candidate,
            f"{base_url}/{candidate.model}",
            self._json_headers(key),
            payload,
            bool(key),
        )
        if response is None:
            return latency_or_error
        latency = latency_or_error
        if response.status_code != 200:
            return self._http_failure(candidate, response, latency, bool(key))
        try:
            data = response.json()
            text = data["result"]["response"][:160]
        except (ValueError, KeyError, TypeError) as exc:
            return self._invalid(candidate, latency, bool(key), "Cloudflare Workers AI", exc)
        return self._working(candidate, latency, bool(key), text, candidate.model)

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
        key, auth_error = self._credential(candidate, with_auth)
        if auth_error:
            auth_error.request_kind = "models"
            return auth_error
        started = time.monotonic()
        try:
            response = self.session.get(
                f"{candidate.base_url}/models",
                headers=self._json_headers(key),
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.Timeout:
            return self._error(candidate, started, "models", "timeout", "Request timed out", bool(key))
        except requests.RequestException as exc:
            return self._error(candidate, started, "models", "network_error", str(exc), bool(key))

        latency = round((time.monotonic() - started) * 1000, 1)
        if response.status_code == 200:
            try:
                data = response.json()
                models = sorted(
                    {
                        item["id"].strip()
                        for item in data["data"]
                        if isinstance(item, dict)
                        and isinstance(item.get("id"), str)
                        and item["id"].strip()
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
                    auth_used=bool(key),
                )
            return ProbeResult(
                candidate.id,
                "models",
                "working",
                http_status=200,
                latency_ms=latency,
                auth_used=bool(key),
                metadata={"models": models[:500], "model_count": len(models)},
            )
        result = self._http_failure(candidate, response, latency, bool(key))
        result.request_kind = "models"
        return result

    def _post(self, candidate, url, headers, payload, auth_used, params=None):
        started = time.monotonic()
        try:
            response = self.session.post(
                url,
                headers=headers,
                json=payload,
                params=params,
                timeout=self.timeout,
                allow_redirects=False,
            )
            return response, round((time.monotonic() - started) * 1000, 1)
        except requests.Timeout:
            return None, self._error(
                candidate, started, "chat", "timeout", "Request timed out", auth_used
            )
        except requests.RequestException as exc:
            return None, self._error(
                candidate, started, "chat", "network_error", str(exc), auth_used
            )

    @staticmethod
    def _credential(candidate: Candidate, with_auth: bool):
        if not with_auth:
            return None, None
        if not candidate.api_key_env:
            return None, ProbeResult(
                candidate.id, "chat", "skipped", error="No API key environment variable configured"
            )
        api_key = os.environ.get(candidate.api_key_env)
        if not api_key:
            return None, ProbeResult(
                candidate.id,
                "chat",
                "skipped",
                error=f"Environment variable {candidate.api_key_env} is not set",
            )
        return api_key, None

    @staticmethod
    def _json_headers(api_key=None):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    @staticmethod
    def _working(candidate, latency, auth_used, text, model, metadata=None):
        if not text or not text.strip():
            return ProbeResult(
                candidate.id,
                "chat",
                "empty_response",
                http_status=200,
                latency_ms=latency,
                model_returned=model,
                error="Provider returned a valid response envelope with empty assistant content",
                auth_used=auth_used,
                metadata=metadata or {},
            )
        return ProbeResult(
            candidate.id,
            "chat",
            "working",
            http_status=200,
            latency_ms=latency,
            model_returned=model,
            response_preview=text,
            auth_used=auth_used,
            metadata=metadata or {},
        )

    @staticmethod
    def _invalid(candidate, latency, auth_used, protocol, error):
        return ProbeResult(
            candidate.id,
            "chat",
            "invalid_response",
            http_status=200,
            latency_ms=latency,
            error=f"Invalid {protocol} response: {error}",
            auth_used=auth_used,
        )

    @staticmethod
    def _http_failure(candidate, response, latency, auth_used):
        status = response.status_code
        if status in {401, 403} or (status == 400 and candidate.auth_mode == "api_key" and not auth_used):
            mapped = "auth_required"
        else:
            mapped = {
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
            error=(getattr(response, "text", "") or "")[:300],
            auth_used=auth_used,
        )

    @staticmethod
    def _error(candidate, started, request_kind, status, error, auth_used):
        return ProbeResult(
            candidate.id,
            request_kind,
            status,
            latency_ms=round((time.monotonic() - started) * 1000, 1),
            error=error[:300],
            auth_used=auth_used,
        )
