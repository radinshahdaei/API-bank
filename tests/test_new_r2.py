"""
Round 2: Fix URLs/models for endpoints that responded but errored.
"""
import time, requests, json

PROMPT = "Say hello"
MAX_TOKENS = 20
TIMEOUT = 20

TESTS = [
    # Free.ai — endpoint works, wrong model name. Try common free models.
    ("Free.ai (gpt-4o-mini)", "https://api.free.ai/v1/chat/completions", "gpt-4o-mini"),
    ("Free.ai (gpt-3.5-turbo)", "https://api.free.ai/v1/chat/completions", "gpt-3.5-turbo"),
    ("Free.ai (llama-3.1-8b)", "https://api.free.ai/v1/chat/completions", "llama-3.1-8b"),
    ("Free.ai (free)", "https://api.free.ai/v1/chat/completions", "free"),

    # OpenCode Zen — try alternative URLs
    ("OpenCode Zen (api.opencode)", "https://api.opencode.ai/v1/chat/completions", "deepseek-v4-flash-free"),
    ("OpenCode Zen (opencode.ai/zen)", "https://opencode.ai/zen/v1/chat/completions", "deepseek-v4-flash-free"),

    # ZeroLimitAI — try alternative
    ("ZeroLimitAI (.com/api)", "https://www.zerolimitai.com/api/v1/chat/completions", "auto"),
    ("ZeroLimitAI (api/v1)", "https://api.zerolimitai.com/v1/chat/completions", "auto"),

    # AnyAPI — try free model names
    ("AnyAPI (llama)", "https://api.anyapi.ai/v1/chat/completions", "meta-llama/Llama-3.1-8B-Instruct"),
    ("AnyAPI (free tier)", "https://api.anyapi.ai/v1/chat/completions", "free"),

    # BazaarLink — endpoint works, needs key. Try common patterns.
    ("BazaarLink (no model)", "https://api.bazaarlink.ai/v1/chat/completions", "gpt-4o-mini"),
]

for name, url, model in TESTS:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0.0,
    }
    start = time.time()
    try:
        resp = requests.post(url, headers={"Content-Type": "application/json"},
                            json=payload, timeout=TIMEOUT)
        lat = (time.time() - start) * 1000
        body = resp.text[:250]

        if resp.status_code == 200:
            try:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                print(f"✅ {name:45s} {lat:.0f}ms — \"{text.strip()}\"")
            except:
                print(f"⚠️  {name:45s} {lat:.0f}ms — 200 but parse fail: {body[:100]}")
        elif resp.status_code == 401 or resp.status_code == 403:
            print(f"🔑 {name:45s} {lat:.0f}ms — AUTH: {body[:100]}")
        elif resp.status_code == 429:
            print(f"🚦 {name:45s} {lat:.0f}ms — RATE LIMITED")
        elif resp.status_code == 404:
            print(f"🔍 {name:45s} {lat:.0f}ms — 404: {body[:100]}")
        else:
            print(f"❌ {name:45s} {lat:.0f}ms — HTTP {resp.status_code}: {body[:100]}")
    except requests.ConnectionError:
        lat = (time.time() - start) * 1000
        print(f"🔌 {name:45s} {lat:.0f}ms — Connection error")
    except Exception as e:
        lat = (time.time() - start) * 1000
        print(f"💥 {name:45s} {lat:.0f}ms — {str(e)[:100]}")
    time.sleep(0.5)

# Also: try the /v1/models endpoint on the working APIs to discover models
print("\n─── Model Discovery ───")
for label, base in [
    ("Free.ai", "https://api.free.ai/v1/models"),
    ("BazaarLink", "https://api.bazaarlink.ai/v1/models"),
    ("AnyAPI", "https://api.anyapi.ai/v1/models"),
    ("Aion Labs", "https://api.aionlabs.ai/v1/models"),
    ("AINative", "https://api.ainative.studio/v1/models"),
    ("Chutes.ai", "https://api.chutes.ai/v1/models"),
]:
    try:
        resp = requests.get(base, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            models = [m.get("id", str(m)) for m in data.get("data", [])][:10]
            print(f"  {label}: {models}")
        else:
            print(f"  {label}: HTTP {resp.status_code}")
    except Exception as e:
        print(f"  {label}: {str(e)[:80]}")
