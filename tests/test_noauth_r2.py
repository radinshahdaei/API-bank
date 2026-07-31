"""
Round 2: Fix issues from first deep test.
- OVHcloud: test sequentially (2 RPM limit per model)
- LLM7.io: find actually available free models
- Kilo: re-test models with real prompt
"""
import time
import requests
import json

TEST_PROMPT = "Say 'ready' and nothing else."
TIMEOUT = 45


def test_ovhcloud_sequential():
    """Test OVHcloud models one at a time with 2s delay (2 RPM = 30s between, but 2s works across models)."""
    models = [
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

    print("🌐 OVHcloud — sequential testing (2s delay between)...\n")
    results = []

    for model in models:
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
                choice = data.get("choices", [{}])[0]
                msg = choice.get("message", {})
                text = msg.get("content", "") if msg else ""
                results.append({"model": model, "status": "ok", "latency_ms": round(lat), "response": text.strip()})
                print(f"  ✅ {model:40s} {lat:.0f}ms — \"{text.strip()}\"")
            elif resp.status_code == 429:
                results.append({"model": model, "status": "rate_limited", "latency_ms": round(lat)})
                print(f"  🚦 {model:40s} {lat:.0f}ms — RATE LIMITED (2 RPM per model)")
            else:
                body = resp.text[:200]
                results.append({"model": model, "status": "error", "latency_ms": round(lat), "error": body})
                print(f"  ❌ {model:40s} {lat:.0f}ms — HTTP {resp.status_code}: {body[:100]}")
        except Exception as e:
            lat = (time.time() - start) * 1000
            results.append({"model": model, "status": "error", "latency_ms": round(lat), "error": str(e)[:150]})
            print(f"  💥 {model:40s} {lat:.0f}ms — {e}")

        # Respect rate limit: 2 RPM per model, but across models we can go faster
        # 2 sec between requests should keep us under 30 RPM total
        time.sleep(2)

    ok = [r for r in results if r["status"] == "ok"]
    rl = [r for r in results if r["status"] == "rate_limited"]
    print(f"\n  OVHcloud: {len(ok)} working, {len(rl)} rate limited, {len(results) - len(ok) - len(rl)} errors")
    return results


def test_llm7_models():
    """Try LLM7.io with models from their actual /v1/models list."""
    print("\n🔍 LLM7.io — trying models from their API...\n")

    # First, fetch the actual model list
    try:
        resp = requests.get("https://api.llm7.io/v1/models", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            models = [m["id"] for m in data.get("data", [])]
            print(f"  Available models ({len(models)}):")
            for m in models:
                print(f"    - {m}")
        else:
            print(f"  Failed to get model list: {resp.status_code}")
            return []
    except Exception as e:
        print(f"  Error getting models: {e}")
        return []

    # Try a few free-tier models
    results = []
    test_models = [m for m in models if m not in ("claude-fable-5", "gpt-5", "gpt-4o")][:8]

    for model in test_models:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": TEST_PROMPT}],
            "max_tokens": 20,
            "temperature": 0.0,
        }
        start = time.time()
        try:
            resp = requests.post(
                "https://api.llm7.io/v1/chat/completions",
                headers={"Content-Type": "application/json"},
                json=payload, timeout=TIMEOUT,
            )
            lat = (time.time() - start) * 1000
            body = resp.text[:250]
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                results.append({"model": model, "status": "ok", "latency_ms": round(lat), "response": text.strip()})
                print(f"  ✅ {model:40s} {lat:.0f}ms — \"{text.strip()}\"")
            elif resp.status_code == 401 or resp.status_code == 402:
                results.append({"model": model, "status": "auth_required", "latency_ms": round(lat)})
                print(f"  🔑 {model:40s} {lat:.0f}ms — AUTH REQUIRED: {body[:100]}")
            else:
                results.append({"model": model, "status": "error", "latency_ms": round(lat), "error": body})
                print(f"  ❌ {model:40s} {lat:.0f}ms — HTTP {resp.status_code}: {body[:100]}")
            time.sleep(1)
        except Exception as e:
            lat = (time.time() - start) * 1000
            results.append({"model": model, "status": "error", "latency_ms": round(lat), "error": str(e)[:150]})
            print(f"  💥 {model:40s} — {e}")

    ok = [r for r in results if r["status"] == "ok"]
    print(f"\n  LLM7.io: {len(ok)}/{len(test_models)} working without auth")
    return results


def test_kilo_with_prompt():
    """Test Kilo with a more interesting prompt to verify quality."""
    print("\n🌐 Kilo Gateway — testing with real prompt...\n")

    models = [
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "stepfun/step-3.7-flash:free",
        "inclusionai/ling-3.0-flash:free",
        "cohere/north-mini-code:free",
        "poolside/laguna-s-2.1:free",
        "poolside/laguna-xs-2.1:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
    ]

    prompt = "Explain what 2+2 equals in exactly one sentence."
    results = []

    for model in models:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 80,
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
                actual = data.get("model", "?")
                results.append({"model": model, "status": "ok", "latency_ms": round(lat),
                                "response": text.strip(), "routed_to": actual})
                print(f"  ✅ {model:55s} {lat:.0f}ms")
                print(f"     → {actual}")
                print(f"     \"{text.strip()[:120]}\"")
            else:
                results.append({"model": model, "status": "error", "latency_ms": round(lat),
                                "error": resp.text[:150]})
                print(f"  ❌ {model:55s} HTTP {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            lat = (time.time() - start) * 1000
            results.append({"model": model, "status": "error", "latency_ms": round(lat), "error": str(e)[:150]})
            print(f"  💥 {model:55s} {e}")
        time.sleep(0.5)

    ok = [r for r in results if r["status"] == "ok"]
    print(f"\n  Kilo: {len(ok)}/{len(models)} models working")
    return results


if __name__ == "__main__":
    print("=" * 65)
    print("ROUND 2: DEEP NO-AUTH TEST (FIXED)")
    print("=" * 65)

    ovh = test_ovhcloud_sequential()
    llm7 = test_llm7_models()
    kilo = test_kilo_with_prompt()

    # ── Final Summary ──
    ovh_ok = [r for r in ovh if r["status"] == "ok"]
    ovh_rl = [r for r in ovh if r["status"] == "rate_limited"]
    llm7_ok = [r for r in llm7 if r["status"] == "ok"]
    kilo_ok = [r for r in kilo if r["status"] == "ok"]

    print("\n" + "=" * 65)
    print("FINAL TALLY")
    print("=" * 65)
    print(f"  OVHcloud:   {len(ovh_ok)} working + {len(ovh_rl)} rate-limited → likely {len(ovh_ok) + len(ovh_rl)} usable")
    print(f"  Kilo:       {len(kilo_ok)} working")
    print(f"  LLM7.io:    {len(llm7_ok)} working without auth")
    print(f"  ─────────────────────")
    print(f"  TOTAL:      {len(ovh_ok) + len(kilo_ok) + len(llm7_ok)} endpoints confirmed working")
    print("=" * 65)

    with open("noauth_results_r2.json", "w") as f:
        json.dump({"ovhcloud": ovh, "llm7": llm7, "kilo": kilo}, f, indent=2)
    print("\n📁 Saved to noauth_results_r2.json")
