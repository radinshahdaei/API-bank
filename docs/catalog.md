# Free Text-Generation API Catalog — Ranked by Throughput

> **Goal:** Maximum text output volume for dataset generation. Model quality is secondary.
> **Strategy:** Hit as many providers as possible in parallel with the same prompts.

---

## S-Tier — Massive Throughput (1M+ tokens/day potential)

### 1. Mistral AI (La Plateforme) 🇫🇷
| Field | Detail |
|---|---|
| **Base URL** | `https://api.mistral.ai/v1` |
| **Auth** | Free "Experiment" plan, no credit card |
| **Rate Limit** | ~1 RPS, 500K TPM (**~720M tokens/day theoretical**) |
| **Catch** | Data used for training, phone verification |
| **Models (text)** | Mistral Medium 3.5 (128B), Mistral Small 4, Mistral Large 3, Ministral 8B/3B/14B, Codestral |
| **OpenAI SDK?** | ✅ Yes |

### 2. Google AI Studio 🇺🇸
| Field | Detail |
|---|---|
| **Base URL** | `https://generativelanguage.googleapis.com/v1beta` |
| **Auth** | API key (free in AI Studio) |
| **Rate Limit** | 15-30 RPM, **1,500 RPD per model**, 250K tokens/min |
| **Catch** | Not available in EU/UK/CH; data used for training |
| **Models (text)** | Gemini 3.6 Flash, 3.5 Flash, 3.5 Flash-Lite, 3.1 Flash-Lite, 2.5 Flash, 2.5 Flash-Lite, 2.5 Pro |
| **OpenAI SDK?** | ❌ Gemini API format (separate SDK or REST) |

### 3. Groq 🇺🇸
| Field | Detail |
|---|---|
| **Base URL** | `https://api.groq.com/openai/v1` |
| **Auth** | Free API key, no credit card |
| **Rate Limit** | 30 RPM; **Llama 3.1 8B: 14,400 RPD**; most others: 1,000 RPD |
| **Catch** | Ultra-fast LPU — great for high throughput |
| **Models (text)** | llama-3.3-70b-versatile, llama-3.1-8b-instant, gpt-oss-120b, gpt-oss-20b, groq/compound, groq/compound-mini, qwen3.6-27b |
| **OpenAI SDK?** | ✅ Yes |

### 4. NVIDIA NIM 🇺🇸
| Field | Detail |
|---|---|
| **Base URL** | `https://integrate.api.nvidia.com/v1` |
| **Auth** | Free NVIDIA Developer account |
| **Rate Limit** | **~40 RPM, NO daily token cap** |
| **Catch** | Phone verification; models may have context window limits |
| **Models (text)** | deepseek-v4-flash (1M ctx), nemotron-3-ultra-550b, nemotron-3-super-120b, mistral-medium-3.5-128b, gpt-oss-120b/20b, llama-3.1-nemotron-ultra-253b, gemma-4-31b, minimax-m3, deepseek-v4-pro + 100+ more |
| **OpenAI SDK?** | ✅ Yes |

### 5. AINative Studio
| Field | Detail |
|---|---|
| **Base URL** | Check docs (OpenAI-compatible) |
| **Auth** | No credit card |
| **Rate Limit** | **10M tokens/month, 60 RPM, 84+ models** |
| **Models (text)** | Llama, DeepSeek, Mistral, Qwen + more |
| **OpenAI SDK?** | ✅ Yes |

---

## A-Tier — Strong Throughput (100K-1M tokens/day)

### 6. Cerebras 🇺🇸
| Field | Detail |
|---|---|
| **Base URL** | `https://api.cerebras.ai/v1` |
| **Auth** | Free tier, payment method required |
| **Rate Limit** | 5 RPM, 30K TPM, **1M tokens/day** |
| **Models (text)** | gpt-oss-120b, zai-glm-4.7, gemma-4-31b |
| **OpenAI SDK?** | ✅ Yes |

### 7. Cloudflare Workers AI 🇺🇸
| Field | Detail |
|---|---|
| **Base URL** | `https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run` |
| **Auth** | Cloudflare account + API token |
| **Rate Limit** | **10,000 neurons/day** (shared across models) |
| **Models (text)** | llama-3.3-70b, gpt-oss-120b, kimi-k2.7-code (262K ctx), gemma-4-26b, glm-4.7-flash, mistral-small-3.1-24b, deepseek-r1-distill-qwen-32b + 50+ more |
| **OpenAI SDK?** | ❌ Custom API, but straightforward REST |

### 8. GitHub Models 🇺🇸 — ⚠️ RETIRED (2026-07-30)
| Field | Detail |
|---|---|
| **Base URL** | `https://models.github.ai/inference` |
| **Auth** | GitHub account (free for all users) |
| **Rate Limit** | 10-15 RPM, 50-150 RPD per model; **45+ models** |
| **Catch** | **RETIRED 2026-07-30** — service discontinued per official docs/changelog. Do not use. |
| **Models (text)** | gpt-5, gpt-4.1/mini, gpt-4o, o4-mini, Llama-4-Scout/Maverick, Llama-3.3-70B, DeepSeek-R1, Mistral-Small-3.1 + 35+ more |
| **OpenAI SDK?** | ✅ Yes |

### 9. Hugging Face Inference Providers 🇺🇸
| Field | Detail |
|---|---|
| **Base URL** | `https://router.huggingface.co/v1` |
| **Auth** | Hugging Face token |
| **Rate Limit** | **100K credits/month** (~$0.10 worth), thousands of models |
| **Catch** | Credit-based, not request-based; small models cost less |
| **Models (text)** | Meta-Llama-3.1-8B, gemma-3-4b, phi-4, Qwen2.5-Coder-7B, Qwen2.5-7B + thousands of community models |
| **OpenAI SDK?** | ✅ Yes |

### 10. Cohere 🇨🇦
| Field | Detail |
|---|---|
| **Base URL** | `https://api.cohere.com/v2` |
| **Auth** | Free trial API key, no credit card |
| **Rate Limit** | 20 RPM, **1,000 API calls/month** |
| **Catch** | Non-commercial use only |
| **Models (text)** | Command A+ (218B, 436K ctx), Command A (111B), Command R+, Command R, Command R7B, Command A Reasoning, Command R7B Arabic, Aya Expanse 32B |
| **OpenAI SDK?** | ❌ Cohere SDK (or REST) |

---

## B-Tier — Moderate Throughput (10K-100K tokens/day)

### 11. OpenRouter 🇺🇸
| Field | Detail |
|---|---|
| **Base URL** | `https://openrouter.ai/api/v1` |
| **Auth** | API key (free) |
| **Rate Limit** | 20 RPM, **50 RPD** (1,000 RPD with $10 lifetime top-up) |
| **Models (text)** | 22+ free models: nemotron-3-super-120b, gpt-oss-20b, north-mini-code, gemma-4-26b/31b, ling-3.0-flash, laguna-s/xs + more |
| **OpenAI SDK?** | ✅ Yes |

### 12. SambaNova Cloud 🇺🇸
| Field | Detail |
|---|---|
| **Base URL** | `https://api.sambanova.ai/v1` |
| **Auth** | Free tier, no credit card; $5 credits (30 days) |
| **Rate Limit** | 20 RPM, 20 RPD, **200K TPD** per model |
| **Models (text)** | DeepSeek-V3.1, DeepSeek-V3.2, Llama-3.3-70B, gpt-oss-120b, MiniMax-M2.7, gemma-4-31B |
| **OpenAI SDK?** | ✅ Yes |

### 13. SiliconFlow 🇨🇳
| Field | Detail |
|---|---|
| **Base URL** | `https://api.siliconflow.cn/v1` |
| **Auth** | Free, no credit card |
| **Rate Limit** | **30 RPM, 60K TPM** |
| **Models (text)** | Qwen3-8B (131K ctx), DeepSeek-R1-Distill-Qwen-7B |
| **OpenAI SDK?** | ✅ Yes |

### 14. LLM7.io 🇬🇧
| Field | Detail |
|---|---|
| **Base URL** | `https://api.llm7.io/v1` |
| **Auth** | **No registration needed** (120 RPM with token) |
| **Rate Limit** | **30 RPM** (anonymous) |
| **Models (text)** | deepseek-r1-0528, deepseek-v3-0324, gemini-2.5-flash-lite, gpt-4o-mini, mistral-small-3.1-24b, qwen2.5-coder-32b + 24 more |
| **OpenAI SDK?** | ✅ Yes |

### 15. Kilo Gateway 🇺🇸
| Field | Detail |
|---|---|
| **Base URL** | `https://api.kilo.ai/api/gateway` |
| **Auth** | **No account needed** |
| **Rate Limit** | **200 req/hr per IP** |
| **Catch** | Free models may use prompts for training |
| **Models (text)** | nemotron-3-ultra-550b (1M ctx), step-3.7-flash, nemotron-3-super-120b, nemotron-3-nano-omni-30b (reasoning), ling-3.0-flash, laguna-s-2.1/xs-2.1 (code), north-mini-code + openrouter/free |
| **OpenAI SDK?** | ✅ Yes |

### 16. DeepSeek Platform 🇨🇳
| Field | Detail |
|---|---|
| **Base URL** | `https://api.deepseek.com` |
| **Auth** | API key, phone verification |
| **Rate Limit** | No official free tier (paid; small new-user grant) |
| **Models (text)** | deepseek-v4-flash, deepseek-v4-pro (`deepseek-chat` deprecated) |
| **OpenAI SDK?** | ✅ Yes |

### 17. ModelScope 🇨🇳
| Field | Detail |
|---|---|
| **Base URL** | `https://api-inference.modelscope.cn/v1` |
| **Auth** | Alibaba Cloud + real-name verification |
| **Rate Limit** | **2,000 RPD** total, ≤500 RPD per model |
| **Models (text)** | Qwen3.5-35B-A3B, Qwen3.5-27B + more |
| **OpenAI SDK?** | ✅ Yes |

---

## C-Tier — Useful Supplement (lower limits but many providers)

### 18. OVHcloud AI Endpoints 🇫🇷
| Field | Detail |
|---|---|
| **Base URL** | `https://oai.endpoints.kepler.ai.cloud.ovh.net/v1` |
| **Auth** | **NO API key, NO signup** |
| **Rate Limit** | 2 RPM per IP per model |
| **Models (text)** | Qwen3.5-397B-A17B, gpt-oss-120b/20b, Llama-3.3-70B, Qwen3.6-27B, Qwen3.5-9B, Qwen3-32B, Qwen3-Coder-30B, Mistral-Small-3.2-24B, Mistral-Nemo, Mistral-7B |
| **OpenAI SDK?** | ✅ Yes |

### 19. AnyAPI
| Field | Detail |
|---|---|
| **Base URL** | Check docs (OpenAI-compatible) |
| **Auth** | No credit card |
| **Rate Limit** | **100K tokens/day**, 400+ models |
| **OpenAI SDK?** | ✅ Yes |

### 20. FreeTheAi (da-jb)
| Field | Detail |
|---|---|
| **Base URL** | Check docs (OpenAI-compatible) |
| **Auth** | Discord signup |
| **Rate Limit** | **30 RPM, NO daily cap** |
| **OpenAI SDK?** | ✅ Yes |

### 21. Requesty
| Field | Detail |
|---|---|
| **Base URL** | Check docs (OpenAI-compatible) |
| **Auth** | No credit card |
| **Rate Limit** | **200 requests/day** |
| **OpenAI SDK?** | ✅ Yes |

### 22. LongCat AI
| Field | Detail |
|---|---|
| **Base URL** | Check docs (OpenAI-compatible) |
| **Auth** | Signup + KYC |
| **Rate Limit** | **10M token one-time grant** |
| **OpenAI SDK?** | ✅ Yes |

### 23. Chat Oripe
| Field | Detail |
|---|---|
| **Base URL** | Check docs (OpenAI-compatible) |
| **Auth** | No credit card |
| **Rate Limit** | **2M tokens/month**, GPT-4 + Claude access |
| **OpenAI SDK?** | ✅ Yes |

### 24. BazaarLink
| Field | Detail |
|---|---|
| **Base URL** | Check docs (OpenAI-compatible) |
| **Auth** | No credit card, no expiry |
| **Rate Limit** | 10 RPM, **130 req/day**; auto:free routing |
| **OpenAI SDK?** | ✅ Yes |

### 25. ZeroLimitAI
| Field | Detail |
|---|---|
| **Base URL** | Check docs (OpenAI-compatible) |
| **Auth** | No credit card, no expiry |
| **Rate Limit** | Lifetime free, `model: "auto"` routing |
| **OpenAI SDK?** | ✅ Yes |

### 26. Free.ai
| Field | Detail |
|---|---|
| **Base URL** | Check docs (OpenAI-compatible) |
| **Auth** | No credit card |
| **Rate Limit** | **30K tokens/day**, 400+ tools |
| **OpenAI SDK?** | ✅ Yes |

### 27. Ollama Cloud
| Field | Detail |
|---|---|
| **Base URL** | `https://ollama.com` |
| **Auth** | API key from Ollama settings |
| **Rate Limit** | Session limits (every 5 hrs) + weekly limits |
| **Models (text)** | deepseek-v4-pro, deepseek-v4-flash, minimax-m3, kimi-k3, gpt-oss:120b/20b, nemotron-3-ultra, mistral-large-3:675b, qwen3.5:397b + 400+ more |
| **OpenAI SDK?** | ❌ Ollama API format |

### 28. Z AI (Zhipu AI) 🇨🇳
| Field | Detail |
|---|---|
| **Base URL** | `https://api.z.ai/api/paas/v4` |
| **Auth** | Free, no credit card |
| **Rate Limit** | 1 concurrent request |
| **Models (text)** | GLM-4.7-Flash (200K ctx, 128K output), GLM-4.5-Flash |
| **OpenAI SDK?** | ✅ Yes |

### 29. Aion Labs 🇮🇱
| Field | Detail |
|---|---|
| **Base URL** | `https://api.aionlabs.ai/v1` |
| **Auth** | Free, no credit card |
| **Rate Limit** | 15 RPM, 20K tokens/day |
| **Models (text)** | Aion 3.0, 3.0 Mini, 2.5, 2.0 (128K ctx, roleplay/storytelling) |
| **OpenAI SDK?** | ✅ Yes |

### 30. Chutes.ai
| Field | Detail |
|---|---|
| **Base URL** | Check docs (OpenAI-compatible) |
| **Auth** | No credit card |
| **Rate Limit** | Community-powered GPU, variable |
| **Models (text)** | DeepSeek-R1, Llama 3.1 70B, Qwen 2.5 72B |
| **OpenAI SDK?** | ✅ Yes |

---

## Summary: Estimated Daily Throughput

| Tier | Provider | Est. Daily Throughput | Auth Difficulty |
|---|---|---|---|
| **S** | Mistral | ~33M tokens/day | ⭐⭐ Phone verify |
| **S** | Google AI Studio | ~10M+ tokens/day | ⭐ API key |
| **S** | Groq | 14,400 req/day (8B model) | ⭐ API key |
| **S** | NVIDIA NIM | No cap (~57K req/day at 40 RPM) | ⭐⭐ Dev account |
| **S** | AINative Studio | 10M tokens/month, 60 RPM | ⭐ No CC |
| **A** | Cerebras | 1M tokens/day | ⭐⭐⭐ Payment method |
| **A** | Cloudflare Workers AI | 10K neurons/day | ⭐⭐ Account |
| **A** | GitHub Models ⚠️ retired | — | ⭐ GitHub account |
| **A** | Hugging Face | Credit-metered | ⭐ Token |
| **A** | Cohere | 1,000 req/month | ⭐ API key |
| **B** | OpenRouter | 50-1,000 RPD | ⭐ API key |
| **B** | SambaNova | 200K TPD | ⭐ No CC |
| **B** | SiliconFlow | 30 RPM, 60K TPM | ⭐ No CC |
| **B** | LLM7.io | 30 RPM, no registration | 🆓 No auth |
| **B** | Kilo Gateway | 200 req/hr, no account | 🆓 No auth |
| **B** | DeepSeek | Paid (no free tier) | ⭐⭐ Phone verify |
| **B** | ModelScope | 2,000 RPD | ⭐⭐⭐ Real-name verify |
| **C** | OVHcloud | 2 RPM/model, no auth | 🆓 No auth |
| **C** | FreeTheAi | 30 RPM, no daily cap | ⭐ Discord |
| **C** | LongCat AI | 10M tokens (one-time) | ⭐⭐ KYC |
| **C** | Chat Oripe | 2M tokens/month | ⭐ No CC |
| **C** | 6+ more C-tier | ~100-200 req/day each | 🆓-⭐ |

---

## Verified research notes (2026-08-12)

The key-gated (API-key) providers below were re-researched from current official
documentation on 2026-08-12. Full findings — including the cited source URL and evidence
summary for every provider — are archived in
[`docs/research/2026-08-12-major-providers.json`](research/2026-08-12-major-providers.json).
`free_tier: documented` means the official docs explicitly state free access; `claimed`
means credible non-official claims only.

| Provider | Model | Free-tier evidence |
|---|---|---|
| Google Gemini | gemini-2.5-flash | documented |
| Mistral | mistral-small-latest | documented (Free mode) |
| NVIDIA NIM | nvidia/nemotron-3-nano-30b-a3b | documented (prototyping) |
| Cohere | command-r7b-12-2024 | documented (Trial key) |
| OpenRouter | openai/gpt-oss-20b:free | documented (:free suffix) |
| SambaNova | Meta-Llama-3.3-70B-Instruct | documented (no payment method) |
| SiliconFlow | Qwen/Qwen3-8B | documented (.cn small models) |
| Z AI (Zhipu) | glm-4.7-flash | documented ($0) |
| Cerebras | gpt-oss-120b | documented ($5 trial credit, 30-day expiry) |
| Hugging Face | meta-llama/Llama-3.1-8B-Instruct | documented (free tier) |
| Cloudflare Workers AI | @cf/meta/llama-3.1-8b-instruct | documented (10K neurons/day) |
| Groq | llama-3.1-8b-instant | claimed |
| DeepSeek | deepseek-v4-flash | claimed |
| Ollama Cloud | gpt-oss:120b | claimed |

### Corrections applied

- **GitHub Models** — reported retired 2026-07-30 per official docs/changelog. Excluded from findings; left in the seed catalog with a retirement flag.
- **DeepSeek** — base URL `https://api.deepseek.com` (the `/v1` is a documented alias); `deepseek-chat` deprecated → `deepseek-v4-flash`.
- **Z AI (Zhipu)** — international endpoint `https://api.z.ai/api/paas/v4`; `glm-4-flash` → `glm-4.7-flash` (free).
- **Ollama Cloud** — host is `https://ollama.com` (not `api.ollama.com`); model `llama3.1:8b` unconfirmed → `gpt-oss:120b`.

---

## Quick-Start Strategy

For maximum dataset generation throughput:

1. **Sign up for all S-Tier + A-Tier today** (Mistral, Google, Groq, NVIDIA, AINative, Cerebras, Cloudflare, GitHub, HuggingFace, Cohere)
2. **Add all B-Tier as volume multipliers** (OpenRouter, SambaNova, SiliconFlow, LLM7, Kilo, DeepSeek)
3. **Use C-Tier as bonus capacity** — especially the no-auth ones (OVHcloud, LLM7, Kilo)
4. **Parallelize aggressively** — hit all providers simultaneously with the same prompt template
5. **Use OpenAI SDK compatibility** — 25/30 providers are OpenAI-compatible; same code, different `base_url` + `api_key`
