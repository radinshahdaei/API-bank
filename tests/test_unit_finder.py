import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from api_bank.discovery import candidates_from_file
from api_bank.models import Candidate, ProbeResult
from api_bank.probe import Prober, validate_probe_target
from api_bank.store import Store


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


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


if __name__ == "__main__":
    unittest.main()
