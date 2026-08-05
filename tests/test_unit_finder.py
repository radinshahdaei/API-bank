import json
import os
import tempfile
import unittest
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import requests

from api_bank.discovery import candidates_from_file
from api_bank.models import Candidate, ProbeResult, WatchedSource
from api_bank.probe import Prober, validate_probe_target
from api_bank.sources import SourceWatcher
from api_bank.store import Store
from api_bank.verification import VerificationPolicy


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text="", headers=None, content=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = headers or {}
        self.content = content if content is not None else text.encode()
        self.closed = False

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    def iter_content(self, chunk_size=65536):
        for offset in range(0, len(self.content), chunk_size):
            yield self.content[offset : offset + chunk_size]

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class SequenceSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, copy.deepcopy(kwargs)))
        return next(self.responses)

    def post(self, url, **kwargs):
        self.calls.append((url, copy.deepcopy(kwargs)))
        return next(self.responses)


class CandidateTests(unittest.TestCase):
    def test_candidate_identity_is_stable_and_url_is_normalized(self):
        first = Candidate(provider="Example", base_url="HTTPS://API.EXAMPLE.COM/v1/", model="small")
        second = Candidate(provider="Renamed", base_url="https://api.example.com/v1", model="small")
        self.assertEqual(first.base_url, "https://api.example.com/v1")
        self.assertEqual(first.id, second.id)

    def test_rejects_embedded_url_credentials(self):
        with self.assertRaises(ValueError):
            Candidate(provider="Bad", base_url="https://user:secret@example.com/v1")

    def test_agent_finding_file_is_ingested(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "finding.json")
            path.write_text(
                json.dumps(
                    {
                        "findings": [
                            {
                                "provider": "Example",
                                "base_url": "https://api.example.com/v1",
                                "model": "example-small",
                                "auth_mode": "none",
                                "free_tier": "documented",
                                "source_url": "https://example.com/docs",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            candidates = candidates_from_file(path)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].source_kind, "agent_research")

    def test_non_openai_protocol_is_preserved(self):
        candidate = Candidate(
            provider="Gemini example",
            base_url="https://example.com/v1beta",
            model="flash",
            protocol="gemini",
        )
        self.assertEqual(candidate.protocol, "gemini")


class StoreTests(unittest.TestCase):
    def test_probe_history_updates_operational_status(self):
        with tempfile.TemporaryDirectory() as directory:
            with Store(Path(directory, "state.db")) as store:
                candidate = Candidate(
                    provider="Example",
                    base_url="https://api.example.com/v1",
                    model="small",
                    auth_mode="none",
                )
                self.assertTrue(store.upsert_candidate(candidate))
                self.assertFalse(store.upsert_candidate(candidate))
                store.add_probe(
                    ProbeResult(
                        candidate_id=candidate.id,
                        request_kind="chat",
                        status="working",
                        http_status=200,
                        response_preview="API_BANK_OK",
                    )
                )
                saved = store.get_candidate(candidate.id)
                latest = store.latest_probe(candidate.id)
                rows = list(store.verification_rows())

        self.assertEqual(saved.status, "verified")
        self.assertEqual(saved.auth_mode, "none")
        self.assertEqual(saved.free_tier, "observed_no_auth")
        self.assertEqual(latest["status"], "working")
        self.assertEqual(len(rows), 1)

    def test_discovery_refresh_does_not_erase_probe_status_or_agent_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            with Store(Path(directory, "state.db")) as store:
                researched = Candidate(
                    provider="Example",
                    base_url="https://api.example.com/v1",
                    model="small",
                    source_kind="agent_research",
                    source_url="https://example.com/official-docs",
                    free_tier="documented",
                )
                store.upsert_candidate(researched)
                store.add_probe(ProbeResult(researched.id, "chat", "working", http_status=200))
                legacy = Candidate(
                    provider="Old Example Name",
                    base_url="https://api.example.com/v1",
                    model="small",
                    source_kind="legacy_catalog",
                    free_tier="claimed",
                )
                store.upsert_candidate(legacy)
                saved = store.get_candidate(researched.id)

        self.assertEqual(saved.status, "verified")
        self.assertEqual(saved.provider, "Example")
        self.assertEqual(saved.free_tier, "documented")
        self.assertEqual(saved.source_url, "https://example.com/official-docs")

    def test_watched_source_retains_change_history(self):
        with tempfile.TemporaryDirectory() as directory:
            with Store(Path(directory, "state.db")) as store:
                source = WatchedSource(provider="Example", url="https://example.com/docs")
                self.assertTrue(store.upsert_source(source))
                first = SourceWatcher(
                    session=FakeSession(FakeResponse(content=b"version one"))
                ).check(source)
                store.add_source_check(first)
                saved = store.get_source(source.id)
                second = SourceWatcher(
                    session=FakeSession(FakeResponse(content=b"version two"))
                ).check(saved)
                store.add_source_check(second)
                changed = store.get_source(source.id)

        self.assertFalse(first.changed)
        self.assertTrue(second.changed)
        self.assertEqual(changed.status, "changed")
        self.assertIsNotNone(changed.last_changed)


class ProbeTests(unittest.TestCase):
    def test_rejects_private_targets(self):
        for url in ("https://127.0.0.1/v1", "https://169.254.169.254/latest", "https://localhost/v1"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_probe_target(url)

    def test_no_auth_probe_never_reads_or_sends_key(self):
        session = FakeSession(
            FakeResponse(
                payload={
                    "model": "small-v2",
                    "choices": [{"message": {"content": "API_BANK_OK"}, "finish_reason": "stop"}],
                }
            )
        )
        candidate = Candidate(
            provider="Example",
            base_url="https://api.example.com/v1",
            model="small",
            auth_mode="api_key",
            api_key_env="EXAMPLE_API_KEY",
        )
        with patch.dict(os.environ, {"EXAMPLE_API_KEY": "top-secret"}):
            result = Prober(session=session).probe_chat(candidate, with_auth=False)

        self.assertEqual(result.status, "working")
        _url, kwargs = session.calls[0]
        self.assertNotIn("Authorization", kwargs["headers"])
        self.assertFalse(kwargs["allow_redirects"])
        self.assertNotIn("top-secret", json.dumps(kwargs))

    def test_authenticated_probe_requires_explicit_environment_key(self):
        session = FakeSession(FakeResponse(status_code=401, text="missing key"))
        candidate = Candidate(
            provider="Example",
            base_url="https://api.example.com/v1",
            model="small",
            auth_mode="api_key",
            api_key_env="MISSING_EXAMPLE_KEY",
        )
        with patch.dict(os.environ, {}, clear=True):
            result = Prober(session=session).probe_chat(candidate, with_auth=True)
        self.assertEqual(result.status, "skipped")
        self.assertEqual(session.calls, [])

    def test_timeout_is_recorded_without_raising(self):
        session = FakeSession(requests.Timeout("slow"))
        candidate = Candidate(
            provider="Example",
            base_url="https://api.example.com/v1",
            model="small",
        )
        result = Prober(session=session).probe_chat(candidate)
        self.assertEqual(result.status, "timeout")

    def test_model_enumeration_deduplicates_and_sorts_ids(self):
        session = FakeSession(
            FakeResponse(
                payload={"data": [{"id": "model-b"}, {"id": "model-a"}, {"id": "model-a"}]}
            )
        )
        candidate = Candidate(
            provider="Example",
            base_url="https://api.example.com/v1",
            model="old-model",
        )
        result = Prober(session=session).probe_models(candidate)
        self.assertEqual(result.status, "working")
        self.assertEqual(result.metadata["models"], ["model-a", "model-b"])
        self.assertEqual(result.metadata["model_count"], 2)

    def test_openai_adapter_retries_without_reasoning_effort(self):
        session = SequenceSession(
            [
                FakeResponse(status_code=400, text="unknown field"),
                FakeResponse(
                    payload={
                        "model": "small",
                        "choices": [
                            {"message": {"content": "API_BANK_OK"}, "finish_reason": "stop"}
                        ],
                    }
                ),
            ]
        )
        candidate = Candidate(
            provider="Example",
            base_url="https://api.example.com/v1",
            model="small",
        )
        result = Prober(session=session).probe_chat(candidate)
        self.assertEqual(result.status, "working")
        self.assertIn("reasoning_effort", session.calls[0][1]["json"])
        self.assertNotIn("reasoning_effort", session.calls[1][1]["json"])

    def test_empty_assistant_content_is_not_verified(self):
        session = FakeSession(
            FakeResponse(
                payload={
                    "model": "small",
                    "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
                }
            )
        )
        candidate = Candidate(
            provider="Example",
            base_url="https://api.example.com/v1",
            model="small",
        )
        result = Prober(session=session).probe_chat(candidate)
        self.assertEqual(result.status, "empty_response")

    def test_gemini_adapter_uses_query_key_and_normalizes_response(self):
        session = FakeSession(
            FakeResponse(
                payload={
                    "candidates": [{"content": {"parts": [{"text": "API_BANK_OK"}]}}]
                }
            )
        )
        candidate = Candidate(
            provider="Gemini",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            model="gemini-test",
            protocol="gemini",
            auth_mode="api_key",
            api_key_env="GEMINI_TEST_KEY",
        )
        with patch.dict(os.environ, {"GEMINI_TEST_KEY": "query-secret"}):
            result = Prober(session=session).probe_chat(candidate, with_auth=True)
        self.assertEqual(result.status, "working")
        _url, kwargs = session.calls[0]
        self.assertEqual(kwargs["params"], {"key": "query-secret"})
        self.assertNotIn("Authorization", kwargs["headers"])

    def test_cohere_adapter_normalizes_content_blocks(self):
        session = FakeSession(
            FakeResponse(payload={"message": {"content": [{"type": "text", "text": "API_BANK_OK"}]}})
        )
        candidate = Candidate(
            provider="Cohere",
            base_url="https://api.cohere.com/v2",
            model="command-test",
            protocol="cohere-chat",
        )
        result = Prober(session=session).probe_chat(candidate)
        self.assertEqual(result.status, "working")
        self.assertEqual(result.response_preview, "API_BANK_OK")

    def test_ollama_adapter_normalizes_native_message(self):
        session = FakeSession(
            FakeResponse(payload={"model": "test:latest", "message": {"content": "API_BANK_OK"}})
        )
        candidate = Candidate(
            provider="Ollama",
            base_url="https://api.ollama.com",
            model="test:latest",
            protocol="ollama-chat",
        )
        result = Prober(session=session).probe_chat(candidate)
        self.assertEqual(result.status, "working")
        self.assertEqual(result.model_returned, "test:latest")

    def test_cloudflare_adapter_scopes_account_and_key_to_explicit_probe(self):
        session = FakeSession(FakeResponse(payload={"result": {"response": "API_BANK_OK"}}))
        candidate = Candidate(
            provider="Cloudflare",
            base_url="https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run",
            model="@cf/example/model",
            protocol="cloudflare-workers-ai",
            auth_mode="api_key",
            api_key_env="CF_TEST_KEY",
            account_id_env="CF_TEST_ACCOUNT",
        )
        with patch.dict(
            os.environ,
            {"CF_TEST_KEY": "bearer-secret", "CF_TEST_ACCOUNT": "account-123"},
        ):
            result = Prober(session=session).probe_chat(candidate, with_auth=True)
        self.assertEqual(result.status, "working")
        url, kwargs = session.calls[0]
        self.assertIn("accounts/account-123/ai/run/@cf/example/model", url)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer bearer-secret")


class SourceWatcherTests(unittest.TestCase):
    def test_unchanged_response_uses_conditional_headers(self):
        source = WatchedSource(
            provider="Example",
            url="https://example.com/docs",
            content_hash="abc",
            etag='"v1"',
        )
        session = FakeSession(FakeResponse(status_code=304, headers={"ETag": '"v1"'}))
        result = SourceWatcher(session=session).check(source)
        self.assertEqual(result.status, "unchanged")
        self.assertFalse(result.changed)
        _url, kwargs = session.calls[0]
        self.assertEqual(kwargs["headers"]["If-None-Match"], '"v1"')
        self.assertFalse(kwargs["allow_redirects"])

    def test_oversized_source_is_not_hashed(self):
        source = WatchedSource(provider="Example", url="https://example.com/docs")
        response = FakeResponse(headers={"Content-Length": "101"}, content=b"small")
        result = SourceWatcher(max_bytes=100, session=FakeSession(response)).check(source)
        self.assertEqual(result.status, "too_large")


class VerificationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 4, tzinfo=timezone.utc)
        self.candidate = Candidate(
            provider="Example",
            base_url="https://api.example.com/v1",
            model="small",
            free_tier="observed_no_auth",
        )

    def probe(self, status="working", age_days=0):
        return {
            "status": status,
            "tested_at": (self.now - timedelta(days=age_days)).isoformat(),
            "auth_used": False,
        }

    def test_requires_latest_success_and_minimum_recent_successes(self):
        policy = VerificationPolicy(max_age_days=7, min_successes=2)
        one = policy.evaluate(self.candidate, [self.probe()], now=self.now)
        two = policy.evaluate(
            self.candidate,
            [self.probe(), self.probe(age_days=1)],
            now=self.now,
        )
        failed_latest = policy.evaluate(
            self.candidate,
            [self.probe("server_error"), self.probe(age_days=1), self.probe(age_days=2)],
            now=self.now,
        )
        self.assertFalse(one["eligible"])
        self.assertTrue(two["eligible"])
        self.assertIn("latest_probe_server_error", failed_latest["reasons"])

    def test_rejects_stale_or_unsubstantiated_free_access(self):
        stale = VerificationPolicy().evaluate(
            self.candidate, [self.probe(age_days=8)], now=self.now
        )
        unsubstantiated = Candidate(
            provider="Claimed",
            base_url="https://claimed.example.com/v1",
            model="small",
            free_tier="claimed",
        )
        claimed = VerificationPolicy().evaluate(
            unsubstantiated, [self.probe()], now=self.now
        )
        self.assertIn("latest_probe_stale", stale["reasons"])
        self.assertIn("free_access_not_documented_or_observed", claimed["reasons"])


if __name__ == "__main__":
    unittest.main()
