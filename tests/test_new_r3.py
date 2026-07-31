"""Test OpenCode Zen thoroughly + quick shotgun of agent-found providers."""
import time, requests, json

PROMPT = "Say hello"
MAX_TOKENS = 20
TIMEOUT = 20

# ── OpenCode Zen — CONFIRMED WORKING ──
ZEN_MODELS = [
    "deepseek-v4-flash-free",
    "mimo-v2.5-free",
    "nemotron-3-ultra-free",
    "big-pickle-free",
    "qwen-3.6-plus-free",
    "minimax-m3-free",
    "north-mini-code-free",
]

print("🌐 OpenCode Zen — testing all 7 models\n")
zen_ok = []
for model in ZEN_MODELS:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": MAX_TOKENS, "temperature": 0.0,
    }
    start = time.time()
    try:
        resp = requests.post(
            "https://opencode.ai/zen/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json=payload, timeout=TIMEOUT)
        lat = (time.time()-start)*1000
        if resp.status_code == 200:
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            actual = data.get("model", "")
            zen_ok.append((model, round(lat), text.strip(), actual))
            print(f"  ✅ {model:35s} {lat:.0f}ms → {actual} — \"{text.strip()}\"")
        elif resp.status_code == 429:
            print(f"  🚦 {model:35s} {lat:.0f}ms — RATE LIMITED")
        else:
            print(f"  ❌ {model:35s} {lat:.0f}ms — HTTP {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"  💥 {model:35s} — {str(e)[:80]}")
    time.sleep(1)

# ── Agent-found providers ──
NEW_TESTS = [
    ("Kluster AI", "https://api.kluster.ai/v1/chat/completions", "deepseek-r1"),
    ("Kluster AI (Llama 4)", "https://api.kluster.ai/v1/chat/completions", "llama-4-maverick"),
    ("Kluster AI (Qwen3)", "https://api.kluster.ai/v1/chat/completions", "qwen3-235b"),
    ("DeepInfra (no captcha)", "https://api.deepinfra.com/v1/openai/chat/completions", "meta-llama/Llama-3.1-8B-Instruct"),
    ("Together AI", "https://api.together.xyz/v1/chat/completions", "meta-llama/Llama-3.1-8B-Instruct"),
    ("Fireworks AI", "https://api.fireworks.ai/inference/v1/chat/completions", "accounts/fireworks/models/llama-v3p1-8b-instruct"),
    ("Hyperbolic", "https://api.hyperbolic.xyz/v1/chat/completions", "deepseek-ai/DeepSeek-V3-0324"),
    ("Novita AI v3", "https://api.novita.ai/v3/openai/chat/completions", "meta-llama/llama-3.1-8b-instruct"),
    ("Scaleway", "https://api.scaleway.ai/v1/chat/completions", "llama-3.3-70b"),
    ("CloudCode.ONE", "https://api.cloudcode.one/v1/chat/completions", "glm-4.7-flash"),
]

print("\n🔍 Agent-found providers\n")
new_ok = []
for name, url, model in NEW_TESTS:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": MAX_TOKENS, "temperature": 0.0,
    }
    start = time.time()
    try:
        resp = requests.post(url, headers={"Content-Type": "application/json"},
                            json=payload, timeout=TIMEOUT)
        lat = (time.time()-start)*1000
        body = resp.text[:200]
        if resp.status_code == 200:
            try:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                new_ok.append((name, url, model, round(lat), text.strip()))
                print(f"  ✅ {name:35s} {lat:.0f}ms — \"{text.strip()}\"")
            except:
                print(f"  ⚠️  {name:35s} {lat:.0f}ms — PARSE FAIL: {body[:80]}")
        elif resp.status_code in (401, 403):
            print(f"  🔑 {name:35s} {lat:.0f}ms — AUTH: {body[:80]}")
        elif resp.status_code == 429:
            print(f"  🚦 {name:35s} {lat:.0f}ms — RATE LIMITED")
        elif resp.status_code == 404:
            print(f"  🔍 {name:35s} {lat:.0f}ms — 404")
        else:
            print(f"  ❌ {name:35s} {lat:.0f}ms — HTTP {resp.status_code}: {body[:80]}")
    except requests.ConnectionError:
        print(f"  🔌 {name:35s} — Connection refused")
    except Exception as e:
        print(f"  💥 {name:35s} — {str(e)[:80]}")
    time.sleep(0.5)

# Summary
print(f"\n{'='*60}")
print(f"OpenCode Zen: {len(zen_ok)}/7 working")
print(f"New providers: {len(new_ok)} working")
print(f"{'='*60}")
if zen_ok:
    print("\n✅ OpenCode Zen working models:")
    for m, lat, txt, actual in zen_ok:
        print(f"   {m:35s} {lat:.0f}ms → {actual}")
if new_ok:
    print("\n✅ New working providers:")
    for name, url, model, lat, txt in new_ok:
        print(f"   {name:35s} {lat:.0f}ms — {model}")

with open("new_providers_r2.json", "w") as f:
    json.dump({"zen": [{"model": m, "latency_ms": l, "text": t, "actual": a}
                       for m,l,t,a in zen_ok],
               "new": [{"name": n, "url": u, "model": m, "latency_ms": l, "text": t}
                       for n,u,m,l,t in new_ok]}, f, indent=2)
print("\n📁 Saved to new_providers_r2.json")
