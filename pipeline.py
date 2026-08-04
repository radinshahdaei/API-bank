"""
Dataset Generation Pipeline
===========================
Distributes prompts across verified free LLM endpoints with shared rate limiting,
parallel execution, retry with backoff, incremental saves, and resume capability.

Usage:
    # From a prompt file (one prompt per line)
    python pipeline.py --prompts prompts.txt --output dataset.jsonl

    # From a template with variables
    python pipeline.py --template "Write a {genre} story about {topic}" \\
        --vars genre=horror,comedy topic=space,ocean --output dataset.jsonl

    # Limit generations per endpoint
    python pipeline.py --prompts prompts.txt --max-per-endpoint 100

    # Dry run (see what would happen)
    python pipeline.py --prompts prompts.txt --dry-run

    # Resume from previous run (skips completed prompts)
    python pipeline.py --prompts prompts.txt --output dataset.jsonl --resume
"""

import os
import sys
import json
import time
import signal
import argparse
import threading
import itertools
import random
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

import requests

from api_bank.probe import validate_probe_target


# ═══════════════════════════════════════════════════════════════════════════════
# Rate Limiter — shared per provider, thread-safe
# ═══════════════════════════════════════════════════════════════════════════════

class RateLimiter:
    """Token bucket rate limiter. One instance per provider (shared across models)."""

    def __init__(self, rpm: float, rph: Optional[float] = None):
        self.rpm = rpm
        self.rph = rph
        self._min_interval = 60.0 / rpm if rpm > 0 else 0
        self._lock = threading.Lock()
        self._last_request = 0.0
        self._hour_requests: list[float] = []

    @staticmethod
    def _wait(seconds: float, cancel_event: Optional[threading.Event]) -> bool:
        if seconds <= 0:
            return True
        if cancel_event is None:
            time.sleep(seconds)
            return True
        return not cancel_event.wait(seconds)

    def acquire(self, cancel_event: Optional[threading.Event] = None) -> bool:
        """Block until a request slot is available, or return False when cancelled."""
        with self._lock:
            now = time.time()
            wait = self._min_interval - (now - self._last_request)
            if wait > 0 and not self._wait(wait, cancel_event):
                return False
            if wait > 0:
                now = time.time()
            if self.rph:
                self._hour_requests = [t for t in self._hour_requests if now - t < 3600]
                if len(self._hour_requests) >= self.rph:
                    oldest = self._hour_requests[0]
                    wait_hour = 3600 - (now - oldest) + 1
                    if wait_hour > 0 and not self._wait(wait_hour, cancel_event):
                        return False
                    if wait_hour > 0:
                        now = time.time()
                        self._hour_requests = [t for t in self._hour_requests if now - t < 3600]
            self._last_request = now
            self._hour_requests.append(now)
            return True


# ═══════════════════════════════════════════════════════════════════════════════
# Endpoint
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Endpoint:
    name: str
    base_url: str
    model: str
    timeout: int = 120
    completion_path: str = "/chat/completions"
    extra_headers: dict = field(default_factory=dict)
    api_key_env: Optional[str] = None

    def generate(self, prompt: str, max_tokens: int = 512,
                 temperature: float = 0.8, retries: int = 2) -> dict:
        """Send a generation request with retry on rate limit."""
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key_env:
            api_key = os.environ.get(self.api_key_env)
            if not api_key:
                return {
                    "status": "error",
                    "error": f"Environment variable {self.api_key_env} is not set",
                    "latency_ms": None,
                }
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        last_error = None
        tried_reasoning_off = False
        for attempt in range(retries + 2):  # +2 for possible reasoning retry
            # Try with reasoning disabled on first attempt (saves 50-70% tokens)
            if not tried_reasoning_off:
                payload["reasoning_effort"] = "none"
            else:
                payload.pop("reasoning_effort", None)

            start = time.time()
            try:
                resp = requests.post(
                    f"{self.base_url}{self.completion_path}",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                latency_ms = (time.time() - start) * 1000

                # If reasoning_effort causes a 400, retry without it
                if resp.status_code == 400 and not tried_reasoning_off:
                    tried_reasoning_off = True
                    continue

                if resp.status_code == 200:
                    data = resp.json()
                    choice = data.get("choices", [{}])[0]
                    text = (choice.get("message", {}) or {}).get("content", "") or ""
                    return {
                        "status": "ok",
                        "text": text,
                        "model_used": data.get("model", self.model),
                        "latency_ms": round(latency_ms, 1),
                        "usage": data.get("usage", {}),
                        "attempts": attempt + 1,
                    }
                elif resp.status_code == 429:
                    last_error = f"429: {resp.text[:200]}"
                    if attempt < retries:
                        backoff = (2 ** attempt) * 5 + random.uniform(0, 3)
                        time.sleep(backoff)
                    continue
                else:
                    return {
                        "status": "error",
                        "error": f"HTTP {resp.status_code}: {resp.text[:300]}",
                        "latency_ms": round(latency_ms, 1),
                    }
            except requests.Timeout:
                last_error = "Request timed out"
                if attempt < retries:
                    time.sleep(3)
                continue
            except Exception as e:
                return {"status": "error", "error": str(e)[:300],
                        "latency_ms": round((time.time() - start) * 1000, 1)}

        return {"status": "rate_limited", "error": last_error or "Max retries",
                "latency_ms": None}


# ═══════════════════════════════════════════════════════════════════════════════
# Provider Groups — shared rate limiters per provider (same IP = same pool)
# ═══════════════════════════════════════════════════════════════════════════════

# Kilo Gateway: 200 req/hr per IP
_kilo_limiter = RateLimiter(rpm=3, rph=200)

# LLM7.io: 30 RPM for anonymous
_llm7_limiter = RateLimiter(rpm=30)

# OpenCode Zen: no auth, curated gateway
_zen_limiter = RateLimiter(rpm=30)


ENDPOINTS = [
    # ═══ Kilo Gateway — no auth, 200 req/hr shared ═══
    Endpoint(name="Kilo-Nemotron-Nano",
             base_url="https://api.kilo.ai/api/gateway",
             model="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
             timeout=120),
    Endpoint(name="Kilo-Ling-3-Flash",
             base_url="https://api.kilo.ai/api/gateway",
             model="inclusionai/ling-3.0-flash:free",
             timeout=180),

    # ═══ LLM7.io — no auth for basic ═══
    Endpoint(name="LLM7-Codestral",
             base_url="https://api.llm7.io/v1",
             model="codestral-latest",
             timeout=120),
    Endpoint(name="LLM7-Gemini-Flash",
             base_url="https://api.llm7.io/v1",
             model="gemini-3.1-flash-lite",
             timeout=120),
    # ═══ OpenCode Zen — no auth, curated gateway ═══
    Endpoint(name="Zen-DeepSeek-V4-Flash",
             base_url="https://opencode.ai/zen/v1",
             model="deepseek-v4-flash-free",
             timeout=120),
    Endpoint(name="Zen-Nemotron-3-Ultra",
             base_url="https://opencode.ai/zen/v1",
             model="nemotron-3-ultra-free",
             timeout=120),
]

# Map endpoints to their shared rate limiter (by provider prefix)
_LIMITERS = {
    "Kilo": _kilo_limiter,
    "LLM7": _llm7_limiter,
    "Zen": _zen_limiter,
}

_DYNAMIC_LIMITERS: dict[str, RateLimiter] = {}

FLAKY_ENDPOINTS = []


def get_limiter_for(endpoint: Endpoint) -> RateLimiter:
    """Get the shared rate limiter for an endpoint based on provider prefix."""
    for prefix, limiter in _LIMITERS.items():
        if endpoint.name.startswith(prefix):
            return limiter
    # Fallback: conservative limiter shared by every model on the same base URL.
    if endpoint.base_url not in _DYNAMIC_LIMITERS:
        _DYNAMIC_LIMITERS[endpoint.base_url] = RateLimiter(rpm=2)
    return _DYNAMIC_LIMITERS[endpoint.base_url]


def load_registry_endpoints(filepath: str, include_auth: bool = False) -> list[Endpoint]:
    """Load generation-compatible endpoints from a finder verified export."""
    with open(filepath) as file:
        registry = json.load(file)
    endpoints = []
    for item in registry.get("endpoints", []):
        if item.get("protocol") != "openai-chat" or not item.get("model"):
            continue
        try:
            validate_probe_target(item["base_url"])
        except (KeyError, ValueError):
            continue
        auth_mode = item.get("auth_mode", "unknown")
        if auth_mode != "none" and not include_auth:
            continue
        api_key_env = item.get("api_key_env") if auth_mode != "none" else None
        if api_key_env and not os.environ.get(api_key_env):
            continue
        provider = item.get("provider", "Registry")
        suffix = item.get("id", "")[:8]
        endpoints.append(
            Endpoint(
                name=f"{provider}-{item['model']}-{suffix}".strip("-"),
                base_url=item["base_url"],
                model=item["model"],
                api_key_env=api_key_env,
            )
        )
    return endpoints


# ═══════════════════════════════════════════════════════════════════════════════
# Prompt Loader
# ═══════════════════════════════════════════════════════════════════════════════

def load_prompts(filepath: str) -> list[str]:
    """Load prompts from a text file (one per line, skip blanks and comments)."""
    prompts = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                prompts.append(line)
    return prompts


def generate_from_template(template: str, vars_dict: dict[str, list[str]]) -> list[str]:
    """Generate prompts from a template and variable lists (cartesian product)."""
    keys = list(vars_dict.keys())
    values = [vars_dict[k] for k in keys]
    prompts = []
    for combo in itertools.product(*values):
        ctx = dict(zip(keys, combo))
        prompts.append(template.format(**ctx))
    return prompts


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

class Pipeline:
    def __init__(
        self,
        endpoints: list[Endpoint],
        prompts: list[str],
        output_path: str,
        max_tokens: int = 512,
        temperature: float = 0.8,
        max_per_endpoint: Optional[int] = None,
        repeat: int = 1,
        resume: bool = False,
        dry_run: bool = False,
    ):
        self.endpoints = endpoints
        self.prompts = prompts
        self.output_path = output_path
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_per_endpoint = max_per_endpoint
        self.repeat = repeat
        self.dry_run = dry_run
        self.resume = resume

        self._lock = threading.Lock()
        self._completed: set[tuple[str, str]] = set()
        self._start_time: Optional[float] = None
        self._shutdown = threading.Event()

    @staticmethod
    def _prompt_hash(prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:20]

    def _load_completed(self):
        if not os.path.exists(self.output_path):
            return
        count = 0
        with open(self.output_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("status") != "ok":
                        continue
                    dedup_key = rec.get("dedup_key")
                    if not dedup_key:
                        dedup_key = f"{rec['prompt_hash']}__rep0"
                    self._completed.add((rec["endpoint"], dedup_key))
                    count += 1
                except (json.JSONDecodeError, KeyError):
                    pass
        if count:
            print(f"📂 Resumed: {count} successful generations found")

    def _save_result(self, record: dict, dedup_key: str):
        with self._lock:
            Path(self.output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.output_path, "a") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._completed.add((record["endpoint"], dedup_key))

    def _generate_one(self, endpoint: Endpoint, prompt: str, dedup_key: str,
                      limiter: RateLimiter) -> dict:
        """Generate one sample: acquire shared limiter, call endpoint, build record."""
        ph = self._prompt_hash(prompt)

        record = {
            "endpoint": endpoint.name,
            "model": endpoint.model,
            "prompt": prompt,
            "prompt_hash": ph,
            "dedup_key": dedup_key,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": None,
            "generation": None,
            "latency_ms": None,
            "usage": None,
            "error": None,
        }

        if self.dry_run:
            record["status"] = "dry_run"
            return record, dedup_key

        # Shared rate limiter ensures we don't exceed per-IP limits
        if not limiter.acquire(self._shutdown):
            record["status"] = "cancelled"
            record["error"] = "Pipeline shutdown requested"
            return record, dedup_key

        result = endpoint.generate(prompt, self.max_tokens, self.temperature)
        record.update({
            "status": result["status"],
            "generation": result.get("text"),
            "latency_ms": result.get("latency_ms"),
            "usage": result.get("usage"),
            "error": result.get("error"),
        })
        return record, dedup_key

    def _should_generate(self, endpoint: Endpoint, prompt: str, dedup_key: str) -> bool:
        key = (endpoint.name, dedup_key)
        return key not in self._completed and not self._shutdown.is_set()

    def _build_jobs(self) -> list[tuple[Endpoint, str, str, RateLimiter]]:
        """Build (endpoint, prompt, dedup_key, limiter) tuples, filtering completed."""
        endpoint_jobs = []
        for ep in self.endpoints:
            jobs = []
            limiter = get_limiter_for(ep)
            limit = (
                self.max_per_endpoint
                if self.max_per_endpoint is not None
                else len(self.prompts) * self.repeat
            )
            selected = 0
            for rep in range(self.repeat):
                for prompt in self.prompts:
                    if selected >= limit:
                        break
                    selected += 1
                    dedup_key = f"{self._prompt_hash(prompt)}__rep{rep}"
                    key = (ep.name, dedup_key)
                    if key not in self._completed and not self._shutdown.is_set():
                        jobs.append((ep, prompt, dedup_key, limiter))
                if selected >= limit:
                    break
            endpoint_jobs.append(jobs)

        # Round-robin prevents a slow first provider from occupying every worker.
        jobs = []
        longest = max((len(items) for items in endpoint_jobs), default=0)
        for index in range(longest):
            for items in endpoint_jobs:
                if index < len(items):
                    jobs.append(items[index])
        return jobs

    def run(self):
        if self.dry_run:
            print("🔍 DRY RUN — no API calls will be made\n")

        if self.resume:
            self._load_completed()

        jobs = self._build_jobs()

        if not jobs:
            print("✅ Nothing to generate (all prompts already completed).")
            return

        total_jobs = len(jobs)
        print(f"🚀 Pipeline starting: {total_jobs} generations "
              f"({len(self.prompts)} prompts × {len(self.endpoints)} endpoints)")
        print(f"   Max tokens: {self.max_tokens} | Temperature: {self.temperature}")
        print(f"   Output: {self.output_path}\n")

        self._start_time = time.time()

        def _on_sigint(sig, frame):
            print("\n\n⏸️  Shutting down... (Ctrl+C again to force)")
            self._shutdown.set()
        signal.signal(signal.SIGINT, _on_sigint)

        completed = errors = rate_limited = dry_runs = cancelled = 0
        max_workers = min(len(self.endpoints), 15)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self._generate_one, ep, prompt, dk, limiter): (ep, prompt, dk)
                for ep, prompt, dk, limiter in jobs
            }

            for future in as_completed(future_map):
                if self._shutdown.is_set():
                    for f in future_map:
                        f.cancel()
                    break

                ep, prompt, dk = future_map[future]
                try:
                    record, dedup_key = future.result()
                except Exception as e:
                    record = {
                        "endpoint": ep.name, "prompt": prompt,
                        "prompt_hash": self._prompt_hash(prompt),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "status": "error", "error": f"Pipeline: {e}",
                    }
                    dedup_key = dk

                if record["status"] == "ok":
                    completed += 1
                elif record["status"] == "rate_limited":
                    rate_limited += 1
                elif record["status"] == "dry_run":
                    dry_runs += 1
                elif record["status"] == "cancelled":
                    cancelled += 1
                else:
                    errors += 1

                if not self.dry_run and record["status"] not in ("dry_run",):
                    self._save_result(record, dedup_key)

                total_done = completed + errors + rate_limited + dry_runs + cancelled
                pct = total_done / total_jobs * 100
                elapsed = time.time() - self._start_time
                rate = total_done / elapsed * 60 if elapsed > 0 else 0
                eta = ((total_jobs - total_done) / rate * 60) if rate > 0 else 0
                icon = {"ok": "✅", "rate_limited": "🚦", "error": "❌", "timeout": "⏱️",
                        "dry_run": "🔍", "cancelled": "⏸️"}.get(
                    record["status"], "❓")
                preview = (record.get("generation") or "")[:60].replace("\n", " ")
                print(f"\r  {icon} [{total_done}/{total_jobs}] {pct:5.1f}% | "
                      f"{rate:5.1f} gen/min | ETA {eta:4.0f}s | "
                      f"{ep.name}: \"{preview}\"", end="")
                sys.stdout.flush()

        print("\n")
        elapsed = time.time() - self._start_time
        print("=" * 60)
        print("PIPELINE COMPLETE")
        print("=" * 60)
        print(f"  ✅ Succeeded:     {completed}")
        print(f"  🚦 Rate limited:  {rate_limited}")
        print(f"  ❌ Errors:        {errors}")
        if dry_runs:
            print(f"  🔍 Dry-run jobs:  {dry_runs}")
        if cancelled:
            print(f"  ⏸️  Cancelled:     {cancelled}")
        print(f"  ⏱️  Time:          {elapsed:.0f}s ({elapsed/60:.1f} min)")
        if completed > 0:
            print(f"  📊 Throughput:    {completed / elapsed * 60:.1f} gen/min")
        print(f"  📁 Output:        {self.output_path}")
        print("=" * 60)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def parse_vars(var_strings: list[str]) -> dict[str, list[str]]:
    """Parse --vars key=val1,val2 into dict."""
    result = {}
    for s in var_strings:
        if "=" not in s:
            raise ValueError(f"Invalid var format: {s}. Use key=val1,val2")
        key, vals = s.split("=", 1)
        result[key.strip()] = [v.strip() for v in vals.split(",")]
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Generate datasets in parallel across free LLM endpoints",
        epilog="Repo: https://github.com/API-bank",
    )
    g = parser.add_argument_group("Prompt Input")
    g.add_argument("--prompts", type=str, help="File with one prompt per line")
    g.add_argument("--template", type=str,
                   help="Template: 'Write a {style} story about {topic}'")
    g.add_argument("--vars", type=str, nargs="*",
                   help="Template vars: key=val1,val2 key=val3,val4")

    g = parser.add_argument_group("Output")
    g.add_argument("--output", type=str, default="dataset.jsonl",
                   help="Output JSONL file (default: dataset.jsonl)")
    g.add_argument("--max-tokens", type=int, default=512,
                   help="Max tokens per generation (default: 512)")
    g.add_argument("--temperature", type=float, default=0.8,
                   help="Temperature (default: 0.8)")

    g = parser.add_argument_group("Limits")
    g.add_argument("--max-per-endpoint", type=int,
                   help="Cap generations per endpoint")
    g.add_argument("--repeat", type=int, default=1,
                   help="Repeat each prompt N times per endpoint (default: 1)")
    g.add_argument("--endpoint", type=str, nargs="*",
                   help="Filter endpoints (prefix match)")
    g.add_argument("--include-flaky", action="store_true",
                   help="Include flaky endpoints")
    g.add_argument("--registry", type=str,
                   help="Finder verified export to use instead of hard-coded endpoints")
    g.add_argument("--registry-with-auth", action="store_true",
                   help="Allow registry endpoints that use configured API keys")

    g = parser.add_argument_group("Runtime")
    g.add_argument("--resume", action="store_true",
                   help="Resume from existing output")
    g.add_argument("--dry-run", action="store_true",
                   help="Show plan without calling APIs")
    g.add_argument("--list-endpoints", action="store_true",
                   help="List endpoints and exit")

    args = parser.parse_args()

    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    if args.max_per_endpoint is not None and args.max_per_endpoint < 0:
        parser.error("--max-per-endpoint cannot be negative")

    configured_endpoints = (
        load_registry_endpoints(args.registry, args.registry_with_auth)
        if args.registry
        else list(ENDPOINTS)
    )

    if args.list_endpoints:
        print("Configured endpoints:\n")
        for ep in configured_endpoints:
            lim = get_limiter_for(ep)
            print(f"  {ep.name:30s} {ep.model:45s} (shared RPM={lim.rpm})")
        if FLAKY_ENDPOINTS:
            print(f"\n  Flaky endpoints (use --include-flaky):")
            for ep in FLAKY_ENDPOINTS:
                print(f"  {ep.name:30s} {ep.model}")
        print(f"\n  Total: {len(configured_endpoints)} configured + {len(FLAKY_ENDPOINTS)} flaky")
        return

    # Load prompts
    if args.prompts:
        prompts = load_prompts(args.prompts)
        print(f"📄 Loaded {len(prompts)} prompts from {args.prompts}")
    elif args.template and args.vars:
        vars_dict = parse_vars(args.vars)
        prompts = generate_from_template(args.template, vars_dict)
        print(f"🎲 Generated {len(prompts)} prompts from template")
        print(f"   Template: {args.template}")
        for k, v in vars_dict.items():
            print(f"   {k}: {v}")
        if len(prompts) <= 20:
            for i, p in enumerate(prompts):
                print(f"     [{i}] {p}")
    else:
        parser.error("Specify --prompts FILE or --template + --vars")

    if not prompts:
        print("❌ No prompts loaded.")
        sys.exit(1)

    # Select endpoints
    endpoints = configured_endpoints
    if args.include_flaky:
        endpoints += FLAKY_ENDPOINTS
    if args.endpoint:
        endpoints = [ep for ep in endpoints
                     if any(ep.name.lower().startswith(e.lower())
                            for e in args.endpoint)]
        if not endpoints:
            print(f"❌ No endpoints match: {args.endpoint}")
            sys.exit(1)
        print(f"🎯 {len(endpoints)} endpoints: {[e.name for e in endpoints]}")

    if not endpoints:
        print("❌ No generation-compatible endpoints are available.")
        sys.exit(1)

    # Run
    Pipeline(
        endpoints=endpoints,
        prompts=prompts,
        output_path=args.output,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        max_per_endpoint=args.max_per_endpoint,
        repeat=args.repeat,
        resume=args.resume,
        dry_run=args.dry_run,
    ).run()


if __name__ == "__main__":
    main()
