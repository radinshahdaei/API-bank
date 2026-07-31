"""
Deep test of no-auth APIs: try all models, measure latency distribution.
"""
import time
import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

TEST_PROMPT = "Say 'ready' and nothing else."
TIMEOUT = 30

# ─── OVHcloud: all text models ────────────────────────────────────────────────

OVHCLOUD_MODELS = [
    "Qwen3.5-397B-A17B",
    "gpt-oss-120b",
    "gpt-oss-20b",
    "Meta-Llama-3_3-70B-Instruct",
    "Qwen3.6-27B",
    "Qwen3.5-9B",
    "Qwen3-32B",
    "Qwen3-Coder-30B-A3B-Instruct",
    "Mistral-Small-3.2-24B-Instruct",
    "Mistral-Nemo-Instruct-2407",
    "Mistral-7B-Instruct-v0.3",
]

# ─── Kilo Gateway: try different model routes ─────────────────────────────────

KILO_MODELS = [
    "kilo-auto/free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "stepfun/step-3.7-flash:free",
]


def test_ovhcloud_model(model):
    """Test a single OVHcloud model."""
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "max_tokens": 20,
        "temperature": 0.0,
    }
    start = time.time()
    try:
        resp = requests.post(
            "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions",
            headers=headers, json=payload, timeout=TIMEOUT,
        )
        lat = (time.time() - start) * 1000
        if resp.status_code == 200:
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            return {"model": model, "status": "ok", "latency_ms": round(lat),
                    "response": text.strip()}
        else:
            return {"model": model, "status": "error",
                    "latency_ms": round(lat),
                    "error": f"HTTP {resp.status_code}: {resp.text[:150]}"}
    except Exception as e:
        return {"model": model, "status": "error",
                "latency_ms": round((time.time() - start) * 1000),
                "error": str(e)[:150]}


def test_kilo_model(model):
    """Test a single Kilo Gateway model."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "max_tokens": 20,
        "temperature": 0.0,
    }
    start = time.time()
    try:
        resp = requests.post(
            "https://api.kilo.ai/api/gateway/chat/completions",
            headers={"Content-Type": "application/json"},
            json=payload, timeout=TIMEOUT,
        )
        lat = (time.time() - start) * 1000
        if resp.status_code == 200:
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            actual_model = data.get("model", "unknown")
            return {"model": model, "actual_model": actual_model,
                    "status": "ok", "latency_ms": round(lat),
                    "response": text.strip()}
        else:
            return {"model": model, "status": "error",
                    "latency_ms": round(lat),
                    "error": f"HTTP {resp.status_code}: {resp.text[:150]}"}
    except Exception as e:
        return {"model": model, "status": "error",
                "latency_ms": round((time.time() - start) * 1000),
                "error": str(e)[:150]}


def test_llm7_noauth():
    """Try various LLM7.io approaches to find no-auth access."""
    results = []

    # Try 1: /v1/chat/completions with no auth
    start = time.time()
    try:
        resp = requests.post(
            "https://api.llm7.io/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json={
                "model": "mistral-small-3.1-24b",
                "messages": [{"role": "user", "content": TEST_PROMPT}],
                "max_tokens": 20,
            },
            timeout=TIMEOUT,
        )
        lat = (time.time() - start) * 1000
        results.append({
            "method": "POST /v1/chat/completions (no auth)",
            "status": resp.status_code,
            "latency_ms": round(lat),
            "body": resp.text[:300],
        })
    except Exception as e:
        results.append({"method": "no auth", "status": "error", "error": str(e)[:150]})

    # Try 2: with empty API key
    start = time.time()
    try:
        resp = requests.post(
            "https://api.llm7.io/v1/chat/completions",
            headers={"Content-Type": "application/json", "Authorization": "Bearer "},
            json={
                "model": "mistral-small-3.1-24b",
                "messages": [{"role": "user", "content": TEST_PROMPT}],
                "max_tokens": 20,
            },
            timeout=TIMEOUT,
        )
        lat = (time.time() - start) * 1000
        results.append({
            "method": "POST /v1/chat/completions (empty Bearer)",
            "status": resp.status_code,
            "latency_ms": round(lat),
            "body": resp.text[:300],
        })
    except Exception as e:
        results.append({"method": "empty Bearer", "status": "error", "error": str(e)[:150]})

    # Try 3: GET the base to see if there's docs
    try:
        resp = requests.get("https://api.llm7.io/v1/models", timeout=10)
        results.append({
            "method": "GET /v1/models (no auth)",
            "status": resp.status_code,
            "body": resp.text[:300],
        })
    except Exception as e:
        results.append({"method": "GET /v1/models", "status": "error", "error": str(e)[:150]})

    # Try 4: GET their website for docs
    try:
        resp = requests.get("https://llm7.io", timeout=10)
        results.append({
            "method": "GET https://llm7.io",
            "status": resp.status_code,
            "body": resp.text[:500],
        })
    except Exception as e:
        results.append({"method": "GET llm7.io", "status": "error", "error": str(e)[:150]})

    return results


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 65)
    print("DEEP NO-AUTH API TEST")
    print("=" * 65)

    # ── OVHcloud ──
    print(f"\n🌐 OVHcloud — testing {len(OVHCLOUD_MODELS)} models...\n")
    ovh_results = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        fmap = {ex.submit(test_ovhcloud_model, m): m for m in OVHCLOUD_MODELS}
        for f in as_completed(fmap):
            r = f.result()
            ovh_results.append(r)
            icon = "✅" if r["status"] == "ok" else "❌"
            print(f"  {icon} {r['model']:40s} {r['latency_ms']:.0f}ms"
                  f" — \"{r.get('response', r.get('error', ''))[:60]}\"")

    ok = [r for r in ovh_results if r["status"] == "ok"]
    print(f"\n  OVHcloud: {len(ok)}/{len(OVHCLOUD_MODELS)} models working")

    # ── Kilo ──
    print(f"\n🌐 Kilo Gateway — testing {len(KILO_MODELS)} model routes...\n")
    kilo_results = []
    for m in KILO_MODELS:
        r = test_kilo_model(m)
        kilo_results.append(r)
        icon = "✅" if r["status"] == "ok" else "❌"
        am = f" → {r.get('actual_model', '')}" if r.get("actual_model") else ""
        print(f"  {icon} {m:55s} {r['latency_ms']:.0f}ms"
              f" — \"{r.get('response', r.get('error', ''))[:60]}\"{am}")

    ok = [r for r in kilo_results if r["status"] == "ok"]
    print(f"\n  Kilo Gateway: {len(ok)}/{len(KILO_MODELS)} routes working")

    # ── LLM7.io investigation ──
    print(f"\n🔍 LLM7.io — investigating no-auth access...\n")
    llm7_results = test_llm7_noauth()
    for r in llm7_results:
        print(f"  [{r['status']}] {r['method']}")
        print(f"         {r.get('body', r.get('error', ''))[:200]}\n")

    # ── Summary ──
    all_ovh = [r for r in ovh_results if r["status"] == "ok"]
    all_kilo = [r for r in kilo_results if r["status"] == "ok"]
    print("=" * 65)
    print(f"TOTAL NO-AUTH WORKING: {len(all_ovh)} OVHcloud + {len(all_kilo)} Kilo")
    if all_ovh:
        lats = [r["latency_ms"] for r in all_ovh]
        print(f"  OVHcloud latency: {min(lats):.0f}–{max(lats):.0f}ms (avg {sum(lats)/len(lats):.0f}ms)")
    if all_kilo:
        lats = [r["latency_ms"] for r in all_kilo]
        print(f"  Kilo latency:     {min(lats):.0f}–{max(lats):.0f}ms (avg {sum(lats)/len(lats):.0f}ms)")
    print("=" * 65)

    # Save
    with open("noauth_results.json", "w") as f:
        json.dump({
            "ovhcloud": ovh_results,
            "kilo": kilo_results,
            "llm7_investigation": llm7_results,
        }, f, indent=2)
    print("\n📁 Saved to noauth_results.json")
