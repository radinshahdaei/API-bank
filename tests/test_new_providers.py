"""
Shotgun test of newly discovered free text-generation providers.
Short prompt = "Say hello" to minimize tokens and maximize discovery speed.
"""
import time
import requests
import json

PROMPT = "Say hello"
MAX_TOKENS = 20
TIMEOUT = 30

PROVIDERS = [
    # ── Chutes.ai — no CC, OpenAI compatible ──
    {
        "name": "Chutes.ai",
        "url": "https://api.chutes.ai/v1/chat/completions",
        "model": "deepseek-r1",
        "headers": {},
    },
    {
        "name": "Chutes.ai (Llama 3.1 70B)",
        "url": "https://api.chutes.ai/v1/chat/completions",
        "model": "llama-3.1-70b",
        "headers": {},
    },
    {
        "name": "Chutes.ai (Qwen 2.5 72B)",
        "url": "https://api.chutes.ai/v1/chat/completions",
        "model": "qwen-2.5-72b",
        "headers": {},
    },
    # ── BazaarLink — no CC, auto:free routing ──
    {
        "name": "BazaarLink",
        "url": "https://api.bazaarlink.ai/v1/chat/completions",
        "model": "auto:free",
        "headers": {},
    },
    # ── ZeroLimitAI — no CC, auto routing ──
    {
        "name": "ZeroLimitAI",
        "url": "https://api.zerolimitai.com/v1/chat/completions",
        "model": "auto",
        "headers": {},
    },
    # ── Free.ai — no CC, 30K tokens/day ──
    {
        "name": "Free.ai",
        "url": "https://api.free.ai/v1/chat/completions",
        "model": "auto",
        "headers": {},
    },
    # ── AnyAPI — no CC, 100K tokens/day ──
    {
        "name": "AnyAPI",
        "url": "https://api.anyapi.ai/v1/chat/completions",
        "model": "gpt-4o-mini",
        "headers": {},
    },
    # ── OpenCode Zen — no CC, 7 free models ──
    {
        "name": "OpenCode Zen (DeepSeek V4 Flash Free)",
        "url": "https://zen.opencode.ai/v1/chat/completions",
        "model": "deepseek-v4-flash-free",
        "headers": {},
    },
    {
        "name": "OpenCode Zen (Nemotron 3 Ultra Free)",
        "url": "https://zen.opencode.ai/v1/chat/completions",
        "model": "nemotron-3-ultra-free",
        "headers": {},
    },
    # ── Aion Labs — no CC, permanent free, 15 RPM ──
    {
        "name": "Aion Labs",
        "url": "https://api.aionlabs.ai/v1/chat/completions",
        "model": "aion-3.0-mini",
        "headers": {},
    },
    # ── AINative Studio — no CC, 10M tokens/month ──
    {
        "name": "AINative Studio",
        "url": "https://api.ainative.studio/v1/chat/completions",
        "model": "deepseek-chat",
        "headers": {},
    },
    # ── DeepInfra — free tier ──
    {
        "name": "DeepInfra",
        "url": "https://api.deepinfra.com/v1/openai/chat/completions",
        "model": "meta-llama/Llama-3.1-8B-Instruct",
        "headers": {},
    },
    # ── Requesty — no CC, 200 req/day ──
    {
        "name": "Requesty",
        "url": "https://api.requesty.ai/v1/chat/completions",
        "model": "gpt-4o-mini",
        "headers": {},
    },
    # ── Chat Oripe — 2M tokens/month ──
    {
        "name": "Chat Oripe",
        "url": "https://api.oriper.com/v1/chat/completions",
        "model": "gpt-4o-mini",
        "headers": {},
    },
    # ── Coze (ByteDance) — free GPT-4o/Gemini ──
    {
        "name": "Coze",
        "url": "https://api.coze.com/v1/chat/completions",
        "model": "gpt-4o-mini",
        "headers": {},
    },
    # ── Hyperbolic — free credits ──
    {
        "name": "Hyperbolic",
        "url": "https://api.hyperbolic.xyz/v1/chat/completions",
        "model": "deepseek-ai/DeepSeek-V3-0324",
        "headers": {},
    },
    # ── Novita AI — free credits ──
    {
        "name": "Novita AI",
        "url": "https://api.novita.ai/v3/openai/chat/completions",
        "model": "meta-llama/llama-3.1-8b-instruct",
        "headers": {},
    },
    # ── SambaNova Cloud — no CC, $5 credits ──
    {
        "name": "SambaNova",
        "url": "https://api.sambanova.ai/v1/chat/completions",
        "model": "Meta-Llama-3.3-70B-Instruct",
        "headers": {},
    },
    # ── Cerebras — no CC (needs payment method) ──
    {
        "name": "Cerebras",
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "gpt-oss-120b",
        "headers": {},
    },
    # ── CloudCode.ONE — free coding agents ──
    {
        "name": "CloudCode.ONE",
        "url": "https://api.cloudcode.one/v1/chat/completions",
        "model": "glm-4.7-flash",
        "headers": {},
    },
]


def test_provider(p):
    """Test one provider. Returns result dict."""
    payload = {
        "model": p["model"],
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0.0,
    }
    headers = {"Content-Type": "application/json", **p["headers"]}

    start = time.time()
    try:
        resp = requests.post(p["url"], headers=headers, json=payload, timeout=TIMEOUT)
        lat = (time.time() - start) * 1000

        if resp.status_code == 200:
            data = resp.json()
            text = ""
            try:
                text = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                text = json.dumps(data)[:200]
            return {
                "name": p["name"], "status": "ok", "latency_ms": round(lat),
                "response": text.strip(), "model_used": data.get("model", ""),
            }
        elif resp.status_code == 401 or resp.status_code == 403:
            return {"name": p["name"], "status": "auth_required",
                    "latency_ms": round(lat), "body": resp.text[:200]}
        elif resp.status_code == 429:
            return {"name": p["name"], "status": "rate_limited",
                    "latency_ms": round(lat), "body": resp.text[:200]}
        elif resp.status_code == 404:
            return {"name": p["name"], "status": "not_found",
                    "latency_ms": round(lat), "body": resp.text[:200]}
        else:
            return {"name": p["name"], "status": "error",
                    "latency_ms": round(lat),
                    "body": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except requests.ConnectionError as e:
        return {"name": p["name"], "status": "connection_error",
                "latency_ms": round((time.time() - start) * 1000),
                "body": str(e)[:200]}
    except requests.Timeout:
        return {"name": p["name"], "status": "timeout",
                "latency_ms": round((time.time() - start) * 1000)}
    except Exception as e:
        return {"name": p["name"], "status": "error",
                "latency_ms": round((time.time() - start) * 1000),
                "body": str(e)[:200]}


if __name__ == "__main__":
    print(f"Testing {len(PROVIDERS)} new providers with prompt: '{PROMPT}'\n")

    results = []
    for i, p in enumerate(PROVIDERS):
        r = test_provider(p)
        results.append(r)
        icon = {
            "ok": "✅", "auth_required": "🔑", "rate_limited": "🚦",
            "not_found": "🔍", "timeout": "⏱️", "connection_error": "🔌",
            "error": "❌",
        }.get(r["status"], "❓")
        resp = r.get("response", "") or r.get("body", "") or ""
        print(f"  {icon} {r['name']:40s} [{r['status']:16s}] {r.get('latency_ms', 0):.0f}ms"
              f" — \"{resp[:80]}\"")
        time.sleep(0.3)  # be polite

    # Summary
    ok = [r for r in results if r["status"] == "ok"]
    auth = [r for r in results if r["status"] == "auth_required"]
    nf = [r for r in results if r["status"] == "not_found"]
    conn = [r for r in results if r["status"] == "connection_error"]
    other = [r for r in results if r["status"] not in ("ok", "auth_required", "not_found", "connection_error")]

    print(f"\n{'='*60}")
    print(f"RESULTS: {len(ok)} working, {len(auth)} auth, {len(nf)} not found, "
          f"{len(conn)} connection errors, {len(other)} other")
    if ok:
        print(f"\n✅ WORKING:")
        for r in ok:
            print(f"   {r['name']:40s} {r['latency_ms']:.0f}ms — \"{r.get('response', '')[:100]}\"")
    print(f"{'='*60}")

    with open("new_providers_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\n📁 Saved to new_providers_results.json")
