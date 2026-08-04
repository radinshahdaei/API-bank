import io
import json
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from pipeline import Endpoint, Pipeline, RateLimiter, load_registry_endpoints


class RegistryTests(unittest.TestCase):
    def test_registry_loader_filters_protocol_auth_and_unsafe_targets(self):
        registry = {
            "endpoints": [
                {
                    "id": "one",
                    "provider": "NoAuth",
                    "base_url": "https://api.example.com/v1",
                    "model": "small",
                    "protocol": "openai-chat",
                    "auth_mode": "none",
                },
                {
                    "id": "two",
                    "provider": "Gemini",
                    "base_url": "https://example.com/v1beta",
                    "model": "flash",
                    "protocol": "gemini",
                    "auth_mode": "none",
                },
                {
                    "id": "three",
                    "provider": "Private",
                    "base_url": "https://127.0.0.1/v1",
                    "model": "private",
                    "protocol": "openai-chat",
                    "auth_mode": "none",
                },
                {
                    "id": "four",
                    "provider": "Keyed",
                    "base_url": "https://keyed.example.com/v1",
                    "model": "keyed",
                    "protocol": "openai-chat",
                    "auth_mode": "api_key",
                    "api_key_env": "PIPELINE_TEST_KEY",
                },
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "registry.json")
            path.write_text(json.dumps(registry), encoding="utf-8")
            default = load_registry_endpoints(str(path))
            with patch.dict("os.environ", {"PIPELINE_TEST_KEY": "secret"}):
                with_auth = load_registry_endpoints(str(path), include_auth=True)

        self.assertEqual([endpoint.model for endpoint in default], ["small"])
        self.assertEqual([endpoint.model for endpoint in with_auth], ["small", "keyed"])


class PipelineResumeTests(unittest.TestCase):
    def test_prompt_hash_is_stable_sha256(self):
        self.assertEqual(Pipeline._prompt_hash("hello"), "2cf24dba5fb0a30e26e8")

    def test_resume_uses_persisted_repeat_key_and_retries_errors(self):
        endpoint = Endpoint("Example", "https://api.example.com/v1", "small")
        prompt = "hello"
        prompt_hash = Pipeline._prompt_hash(prompt)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory, "dataset.jsonl")
            records = [
                {
                    "endpoint": endpoint.name,
                    "prompt_hash": prompt_hash,
                    "dedup_key": f"{prompt_hash}__rep0",
                    "status": "ok",
                },
                {
                    "endpoint": endpoint.name,
                    "prompt_hash": prompt_hash,
                    "dedup_key": f"{prompt_hash}__rep1",
                    "status": "error",
                },
            ]
            output.write_text("\n".join(json.dumps(item) for item in records), encoding="utf-8")
            pipeline = Pipeline([endpoint], [prompt], str(output), repeat=2, resume=True)
            pipeline._load_completed()
            jobs = pipeline._build_jobs()

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0][2], f"{prompt_hash}__rep1")

    def test_endpoint_cap_selects_before_resume_filtering(self):
        endpoint = Endpoint("Example", "https://api.example.com/v1", "small")
        pipeline = Pipeline(
            [endpoint],
            ["first", "second"],
            "unused.jsonl",
            max_per_endpoint=1,
        )
        key = f"{Pipeline._prompt_hash('first')}__rep0"
        pipeline._completed.add((endpoint.name, key))
        self.assertEqual(pipeline._build_jobs(), [])


class PipelineSchedulingTests(unittest.TestCase):
    def test_jobs_are_round_robin_by_endpoint(self):
        endpoints = [
            Endpoint("Alpha", "https://alpha.example.com/v1", "a"),
            Endpoint("Beta", "https://beta.example.com/v1", "b"),
        ]
        pipeline = Pipeline(endpoints, ["one", "two"], "unused.jsonl")
        jobs = pipeline._build_jobs()
        self.assertEqual([job[0].name for job in jobs], ["Alpha", "Beta", "Alpha", "Beta"])

    def test_rate_limit_wait_can_be_cancelled(self):
        limiter = RateLimiter(rpm=1)
        limiter._last_request = time.time()
        cancelled = threading.Event()
        cancelled.set()
        started = time.monotonic()
        acquired = limiter.acquire(cancelled)
        self.assertFalse(acquired)
        self.assertLess(time.monotonic() - started, 0.1)

    def test_dry_run_counts_every_planned_job(self):
        endpoints = [
            Endpoint("Alpha", "https://alpha.example.com/v1", "a"),
            Endpoint("Beta", "https://beta.example.com/v1", "b"),
        ]
        pipeline = Pipeline(endpoints, ["one", "two"], "unused.jsonl", dry_run=True)
        output = io.StringIO()
        with redirect_stdout(output):
            pipeline.run()
        rendered = output.getvalue()
        self.assertIn("[4/4]", rendered)
        self.assertIn("Dry-run jobs:  4", rendered)


if __name__ == "__main__":
    unittest.main()
