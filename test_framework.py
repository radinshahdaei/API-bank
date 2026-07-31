"""
Test framework for free text-generation APIs.
Tests each provider with a simple prompt, measures latency, and reports status.
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from providers import PROVIDERS, get_noauth_providers

TEST_PROMPT = "Say 'hello world' in exactly 3 words. Output nothing else."
TIMEOUT_SECONDS = 30
MAX_OUTPUT_TOKENS = 50


# ─── Result Helpers ──────────────────────────────────────────────────────────

def make_result(provider, status, latency_ms=None, response_text=None,
                error=None, tokens=None):
    return {
        "provider": provider["name"],
        "tier": provider["tier"],
        "model": provider["model"],
        "base_url": provider["base_url"],
        "status": status,          # "ok" | "auth_required" | "error" | "timeout"
        "latency_ms": round(latency_ms, 1) if latency_ms else None,
        "response_text": response_text[:200] if response_text else None,
        "error": str(error)[:300] if error else None,
        "tokens": tokens,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── OpenAI-Compatible Tester ─────────────────────────────────────────────────

def test_openai_compatible(provider: dict, api_key: Optional[str]) -> dict:
    """Test an OpenAI-compatible /v1/chat/completions endpoint."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Some providers require specific headers
    name = provider["name"]
    if name == "OpenRouter":
        headers["HTTP-Referer"] = "https://github.com/API-bank"
        headers["X-Title"] = "API-bank tester"
    if name == "Kilo Gateway":
        # Kilo uses x-api-key or no auth
        if api_key:
            headers["x-api-key"] = api_key
        # Remove Bearer for Kilo when no key
        if not api_key:
            headers.pop("Authorization", None)

    payload = {
        "model": provider["model"],
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "max_tokens": MAX_OUTPUT_TOKENS,
        "temperature": 0.0,
    }

    start = time.time()
    try:
        resp = requests.post(
            f"{provider['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=TIMEOUT_SECONDS,
        )
        latency_ms = (time.time() - start) * 1000

        if resp.status_code == 200:
            data = resp.json()
            choice = data.get("choices", [{}])[0]
            text = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})
            return make_result(provider, "ok", latency_ms, text, tokens=usage)
        elif resp.status_code == 401:
            return make_result(provider, "auth_required", latency_ms,
                               error=f"401: {resp.text[:200]}")
        elif resp.status_code == 429:
            return make_result(provider, "rate_limited", latency_ms,
                               error=f"429: {resp.text[:200]}")
        else:
            return make_result(provider, "error", latency_ms,
                               error=f"HTTP {resp.status_code}: {resp.text[:200]}")
    except requests.Timeout:
        latency_ms = (time.time() - start) * 1000
        return make_result(provider, "timeout", latency_ms, error="Request timed out")
    except requests.ConnectionError as e:
        latency_ms = (time.time() - start) * 1000
        return make_result(provider, "error", latency_ms, error=f"Connection error: {e}")
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        return make_result(provider, "error", latency_ms, error=f"Exception: {e}")


# ─── Gemini API Tester ────────────────────────────────────────────────────────

def test_gemini(provider: dict, api_key: Optional[str]) -> dict:
    """Test Google Gemini API (non-OpenAI format)."""
    if not api_key:
        return make_result(provider, "auth_required", error="GOOGLE_API_KEY not set")

    url = (f"{provider['base_url']}/models/{provider['model']}:generateContent"
           f"?key={api_key}")
    payload = {
        "contents": [{"parts": [{"text": TEST_PROMPT}]}],
        "generationConfig": {
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
            "temperature": 0.0,
        },
    }

    start = time.time()
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT_SECONDS)
        latency_ms = (time.time() - start) * 1000

        if resp.status_code == 200:
            data = resp.json()
            text = (data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", ""))
            usage = data.get("usageMetadata", {})
            return make_result(provider, "ok", latency_ms, text, tokens=usage)
        elif resp.status_code in (401, 403):
            return make_result(provider, "auth_required", latency_ms,
                               error=f"{resp.status_code}: {resp.text[:200]}")
        else:
            return make_result(provider, "error", latency_ms,
                               error=f"HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        return make_result(provider, "error", latency_ms, error=str(e))


# ─── Cloudflare Workers AI Tester ─────────────────────────────────────────────

def test_cloudflare(provider: dict, api_key: Optional[str]) -> dict:
    """Test Cloudflare Workers AI (custom endpoint format)."""
    if not api_key:
        return make_result(provider, "auth_required", error="CLOUDFLARE_API_TOKEN not set")

    account_id = os.environ.get(provider.get("account_id_env", ""))
    if not account_id:
        return make_result(provider, "auth_required",
                           error="CLOUDFLARE_ACCOUNT_ID not set")

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{provider['model']}"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "max_tokens": MAX_OUTPUT_TOKENS,
    }

    start = time.time()
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_SECONDS)
        latency_ms = (time.time() - start) * 1000
        if resp.status_code == 200:
            data = resp.json()
            text = data.get("result", {}).get("response", "")
            return make_result(provider, "ok", latency_ms, text)
        else:
            return make_result(provider, "error", latency_ms,
                               error=f"HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        return make_result(provider, "error", latency_ms, error=str(e))


# ─── Cohere API Tester ────────────────────────────────────────────────────────

def test_cohere(provider: dict, api_key: Optional[str]) -> dict:
    """Test Cohere API (non-OpenAI format, uses /v2/chat)."""
    if not api_key:
        return make_result(provider, "auth_required", error="COHERE_API_KEY not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": provider["model"],
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "max_tokens": MAX_OUTPUT_TOKENS,
    }

    start = time.time()
    try:
        resp = requests.post(
            f"{provider['base_url']}/chat",
            headers=headers,
            json=payload,
            timeout=TIMEOUT_SECONDS,
        )
        latency_ms = (time.time() - start) * 1000
        if resp.status_code == 200:
            data = resp.json()
            text = data.get("message", {}).get("content", [{}])[0].get("text", "")
            usage = data.get("usage", {})
            return make_result(provider, "ok", latency_ms, text, tokens=usage)
        else:
            return make_result(provider, "error", latency_ms,
                               error=f"HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        return make_result(provider, "error", latency_ms, error=str(e))


# ─── Ollama Cloud Tester ──────────────────────────────────────────────────────

def test_ollama(provider: dict, api_key: Optional[str]) -> dict:
    """Test Ollama Cloud API (Ollama-native format)."""
    if not api_key:
        return make_result(provider, "auth_required", error="OLLAMA_API_KEY not set")

    url = f"{provider['base_url']}/api/chat"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": provider["model"],
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "stream": False,
    }

    start = time.time()
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_SECONDS)
        latency_ms = (time.time() - start) * 1000
        if resp.status_code == 200:
            data = resp.json()
            text = data.get("message", {}).get("content", "")
            return make_result(provider, "ok", latency_ms, text)
        else:
            return make_result(provider, "error", latency_ms,
                               error=f"HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        return make_result(provider, "error", latency_ms, error=str(e))


# ─── Dispatcher ───────────────────────────────────────────────────────────────

DISPATCH = {
    "Google Gemini": test_gemini,
    "Cloudflare Workers AI": test_cloudflare,
    "Cohere": test_cohere,
    "Ollama Cloud": test_ollama,
}


def test_provider(provider: dict) -> dict:
    """Run a single provider test. Returns result dict."""
    name = provider["name"]

    # Get API key from environment
    api_key = None
    if provider.get("api_key_env"):
        api_key = os.environ.get(provider["api_key_env"])
        if not api_key:
            return make_result(provider, "auth_required",
                               error=f"Env var {provider['api_key_env']} not set")

    # Route to correct tester
    tester = DISPATCH.get(name)
    if tester:
        return tester(provider, api_key)

    if provider["openai_compatible"]:
        return test_openai_compatible(provider, api_key)

    return make_result(provider, "error", error=f"No tester for {name}")


def test_all(providers=None, max_workers=10):
    """Test all providers in parallel. Returns list of result dicts."""
    if providers is None:
        providers = PROVIDERS

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(test_provider, p): p for p in providers}
        for future in as_completed(future_map):
            try:
                result = future.result()
                results.append(result)
                # Print as we go
                icon = {"ok": "✅", "auth_required": "🔑", "error": "❌",
                        "timeout": "⏱️", "rate_limited": "🚦"}.get(result["status"], "❓")
                lat = f" ({result['latency_ms']:.0f}ms)" if result["latency_ms"] else ""
                print(f"{icon} {result['provider']:25s} [{result['status']}]{lat}")
                if result.get("response_text"):
                    print(f"   ↳ {result['response_text'][:100]}")
            except Exception as e:
                p = future_map[future]
                results.append(make_result(p, "error", error=f"Test harness error: {e}"))
                print(f"💥 {p['name']:25s} [harness_error] {e}")

    return results


def print_summary(results):
    """Print a summary table of all results."""
    ok = [r for r in results if r["status"] == "ok"]
    auth = [r for r in results if r["status"] == "auth_required"]
    err = [r for r in results if r["status"] == "error"]
    to = [r for r in results if r["status"] == "timeout"]
    rl = [r for r in results if r["status"] == "rate_limited"]

    print("\n" + "=" * 70)
    print(f"RESULTS SUMMARY — {len(results)} APIs tested")
    print("=" * 70)
    print(f"  ✅ Working:      {len(ok):3d}")
    print(f"  🔑 Need API key: {len(auth):3d}")
    print(f"  ❌ Errors:       {len(err):3d}")
    print(f"  ⏱️  Timeouts:     {len(to):3d}")
    print(f"  🚦 Rate limited:  {len(rl):3d}")

    if ok:
        print(f"\n  Working APIs ({len(ok)}):")
        avg_lat = sum(r["latency_ms"] for r in ok) / len(ok)
        print(f"  Avg latency: {avg_lat:.0f}ms")
        for r in ok:
            txt = (r['response_text'] or '')[:80]
        print(f"    ✅ {r['provider']:25s} {r['latency_ms']:.0f}ms — \"{txt}\"")

    if auth:
        print(f"\n  Need API Key ({len(auth)}):")
        for r in auth:
            env_var = PROVIDERS[[p["name"] for p in PROVIDERS].index(r["provider"])].get("api_key_env", "?")
            print(f"    🔑 {r['provider']:25s} → set {env_var}")

    if err:
        print(f"\n  Errors ({len(err)}):")
        for r in err:
            print(f"    ❌ {r['provider']:25s} {r['error'][:100]}")

    if rl:
        print(f"\n  Rate Limited ({len(rl)}):")
        for r in rl:
            print(f"    🚦 {r['provider']:25s} {r['error'][:100]}")

    print("=" * 70)

    return {"ok": len(ok), "auth": len(auth), "error": len(err),
            "timeout": len(to), "rate_limited": len(rl)}


def save_results(results, filepath="results.json"):
    """Save results to JSON file."""
    with open(filepath, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n📁 Full results saved to {filepath}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test free text-generation APIs")
    parser.add_argument("--noauth", action="store_true", help="Only test no-auth APIs")
    parser.add_argument("--tier", type=str, help="Only test APIs in a specific tier (S/A/B/C)")
    parser.add_argument("--provider", type=str, help="Only test a specific provider by name")
    parser.add_argument("--workers", type=int, default=10, help="Parallel workers (default: 10)")
    parser.add_argument("--output", type=str, default="results.json", help="Results JSON path")
    args = parser.parse_args()

    providers = PROVIDERS
    if args.noauth:
        providers = get_noauth_providers()
    elif args.tier:
        from providers import get_by_tier
        providers = get_by_tier(args.tier)
    elif args.provider:
        from providers import get_provider
        p = get_provider(args.provider)
        providers = [p] if p else []

    if not providers:
        print("No providers to test.")
        sys.exit(1)

    print(f"Testing {len(providers)} provider(s) with {args.workers} workers...\n")
    results = test_all(providers, max_workers=args.workers)
    print_summary(results)
    save_results(results, args.output)
