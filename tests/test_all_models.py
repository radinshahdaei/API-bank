"""Try every model we can find from the 4 working providers."""
import time, requests, json

PROMPT = "Say hi"
MAX_TOKENS = 30
TIMEOUT = 25

def test(url, model, name):
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
        if resp.status_code == 200:
            data = resp.json()
            msg = data["choices"][0].get("message", {})
            content = msg.get("content") or ""
            # Check for reasoning in content
            has_think = "<think>" in content.lower()
            has_reasoning_field = bool(msg.get("reasoning"))
            actual_model = data.get("model", "")
            content_preview = content[:80] if content else "(empty)"
            flag = ""
            if has_think:
                flag += " [THINK_IN_CONTENT]"
            if has_reasoning_field:
                flag += " [reasoning_field]"
            return f"✅ {name:45s} {lat:5.0f}ms → {actual_model:30s} \"{content_preview}\"{flag}"
        elif resp.status_code == 429:
            return f"🚦 {name:45s} RATE LIMITED"
        elif resp.status_code == 404:
            return f"🔍 {name:45s} 404"
        elif resp.status_code in (401, 403):
            return f"🔑 {name:45s} AUTH"
        else:
            return f"❌ {name:45s} HTTP {resp.status_code}: {resp.text[:90]}"
    except requests.ConnectionError:
        return f"🔌 {name:45s} Connection refused"
    except requests.Timeout:
        return f"⏱️  {name:45s} Timeout"
    except Exception as e:
        return f"💥 {name:45s} {str(e)[:80]}"


# ─── OVHcloud: try models we haven't or that failed before ───
print("═" * 70)
print("OVHCLOUD — retesting with different prompts")
print("═" * 70)
ovh_url = "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions"
ovh_models = [
    # ones we haven't tried or failed before
    ("Qwen/Qwen2.5-72B-Instruct", "Qwen2.5-72B"),
    ("Qwen/Qwen2.5-32B-Instruct", "Qwen2.5-32B"),
    ("Qwen/Qwen2.5-14B-Instruct", "Qwen2.5-14B"),
    ("Qwen/Qwen2.5-7B-Instruct", "Qwen2.5-7B"),
    ("Qwen/Qwen2.5-Coder-32B-Instruct", "Qwen2.5-Coder-32B"),
    ("Qwen/Qwen2.5-Coder-14B-Instruct", "Qwen2.5-Coder-14B"),
    ("Qwen/Qwen2.5-Coder-7B-Instruct", "Qwen2.5-Coder-7B"),
    ("mistralai/Mistral-7B-Instruct-v0.2", "Mistral-7B-v0.2"),
    ("mistralai/Mixtral-8x7B-Instruct-v0.1", "Mixtral-8x7B"),
    ("mistralai/Mixtral-8x22B-Instruct-v0.1", "Mixtral-8x22B"),
    ("meta-llama/Llama-2-7b-chat-hf", "Llama-2-7B"),
    ("meta-llama/Llama-3.1-8B-Instruct", "Llama-3.1-8B"),
    ("google/gemma-2-9b-it", "Gemma-2-9B"),
    ("google/gemma-2-27b-it", "Gemma-2-27B"),
    ("deepseek-ai/DeepSeek-V3", "DeepSeek-V3"),
    ("01-ai/Yi-1.5-34B-Chat", "Yi-1.5-34B"),
    ("microsoft/Phi-3-mini-4k-instruct", "Phi-3-mini"),
    ("microsoft/Phi-3-medium-4k-instruct", "Phi-3-medium"),
]
for model_id, label in ovh_models:
    print("  " + test(ovh_url, model_id, f"OVH-{label}"))
    time.sleep(1.2)

# ─── Kilo: try more models ───
print("\n" + "═" * 70)
print("KILO GATEWAY — trying more models")
print("═" * 70)
kilo_url = "https://api.kilo.ai/api/gateway/chat/completions"
kilo_models = [
    ("openrouter/free", "OpenRouter-free"),
    ("google/gemma-4-26b-a4b-it:free", "Gemma-4-26B"),
    ("google/gemma-4-31b-it:free", "Gemma-4-31B"),
    ("openai/gpt-oss-20b:free", "GPT-OSS-20B"),
    ("openai/gpt-oss-120b:free", "GPT-OSS-120B"),
    ("qwen/qwen3.6-27b:free", "Qwen3.6-27B"),
    ("meta-llama/llama-3.3-70b:free", "Llama-3.3-70B"),
    ("mistralai/mistral-small-3.1-24b:free", "Mistral-Small-3.1"),
    ("deepseek/deepseek-r1:free", "DeepSeek-R1"),
    ("deepseek/deepseek-v3:free", "DeepSeek-V3"),
    ("stepfun/step-3.7-flash:free", "Step-3.7-Flash"),
]
for model_id, label in kilo_models:
    print("  " + test(kilo_url, model_id, f"Kilo-{label}"))
    time.sleep(1)

# ─── LLM7.io: try all free models ───
print("\n" + "═" * 70)
print("LLM7.io — trying all chat models")
print("═" * 70)
llm7_url = "https://api.llm7.io/v1/chat/completions"
llm7_models = [
    # from their /v1/models endpoint (only text models)
    ("gpt-oss:20b", "GPT-OSS-20B"),
    ("deepseek-v4-flash", "DeepSeek-V4-Flash"),
    ("kimi-k3", "Kimi-K3"),
    ("minimax-m2.7", "MiniMax-M2.7"),
    ("gpt-5.4-mini", "GPT-5.4-Mini"),
    ("grok-4.5", "Grok-4.5"),
]
for model_id, label in llm7_models:
    print("  " + test(llm7_url, model_id, f"LLM7-{label}"))
    time.sleep(1)

# ─── OpenCode Zen: retry the ones that errored ───
print("\n" + "═" * 70)
print("ZEN — retrying with different params")
print("═" * 70)
zen_url = "https://opencode.ai/zen/v1/chat/completions"
zen_models = [
    ("big-pickle-free", "Big-Pickle"),
    ("qwen-3.6-plus-free", "Qwen-3.6-Plus"),
    ("minimax-m3-free", "MiniMax-M3"),
    ("north-mini-code-free", "North-Mini-Code"),
]
for model_id, label in zen_models:
    # For reasoning models, give more tokens
    mt = 100 if "north" in model_id or "pickle" in model_id else MAX_TOKENS
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": mt, "temperature": 0.0,
    }
    start = time.time()
    try:
        resp = requests.post(zen_url, headers={"Content-Type": "application/json"},
                            json=payload, timeout=TIMEOUT)
        lat = (time.time()-start)*1000
        if resp.status_code == 200:
            data = resp.json()
            msg = data["choices"][0].get("message", {})
            content = msg.get("content") or ""
            has_think = "<think>" in content.lower()
            has_reasoning = bool(msg.get("reasoning"))
            flag = ""
            if has_think: flag += " [THINK]"
            if has_reasoning: flag += " [reasoning_field]"
            print(f"  ✅ Zen-{label:25s} {lat:.0f}ms — \"{content[:80] or '(empty)'}\"{flag}")
        elif resp.status_code in (401, 403):
            print(f"  🔑 Zen-{label:25s} AUTH: {resp.text[:100]}")
        elif resp.status_code == 429:
            print(f"  🚦 Zen-{label:25s} RATE LIMITED")
        else:
            print(f"  ❌ Zen-{label:25s} HTTP {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"  💥 Zen-{label:25s} {str(e)[:80]}")
    time.sleep(1)
