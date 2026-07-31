# API Bank — Free LLM Dataset Generation Pipeline

Generate large text datasets using **6 verified free LLM endpoints** — no API keys, no credit cards, no signup required.

## Quick Start

```bash
pip install requests

# 6,000 samples from 10 fact prompts
python pipeline.py --prompts prompts.txt --max-tokens 100 --temperature 0.9 \
  --max-per-endpoint 100 --output dataset.jsonl
```

```bash
# Template mode — 3 styles × 4 topics = 12 prompts
python pipeline.py \
  --template "Tell me an interesting fact about {topic} in one sentence." \
  --vars topic="science,history,animals,space" \
  --output dataset.jsonl
```

## Verified Endpoints (6, no auth)

| Provider | Models | Rate Limit |
|---|---|---|
| **Kilo Gateway** | Nemotron-Nano, Ling-3-Flash | 200 req/hr |
| **LLM7.io** | Codestral, Gemini-Flash-Lite | 30 RPM |
| **OpenCode Zen** | DeepSeek-V4-Flash, Nemotron-3-Ultra | ~30 RPM |

**Sustained throughput:** ~17 req/min → ~1,000/hour → ~24,000/day

## Pipeline Features

- **Prompt file** or **template × variables** (cartesian product)
- **Shared rate limiters** per provider — proper serialization
- **`reasoning_effort: "none"`** with graceful 400 fallback — saves 50-70% tokens
- **Retry with backoff** on rate limits and transient errors
- **JSONL output** — append-only, machine-readable
- **Resume** — `--resume` skips completed prompt×endpoint pairs
- **Graceful Ctrl+C shutdown** — saves progress

```bash
python pipeline.py --list-endpoints    # See all endpoints
python pipeline.py --endpoint Kilo Zen # Filter to specific providers
python pipeline.py --resume            # Resume interrupted run
python pipeline.py --dry-run           # Preview without API calls
```

## Project Structure

```
├── pipeline.py              # Dataset generation engine
├── providers.py             # 30 provider configs (all tiers)
├── test_framework.py        # API testing harness
├── prompts.txt              # 10 fact prompts
├── docs/
│   ├── catalog.md           # Full ranked catalog of 30 free APIs
│   └── verified_endpoints.json
├── scripts/
│   └── update_references.sh # Clone/pull reference API repos
├── tests/
│   ├── test_noauth_deep.py  # Deep endpoint testing
│   └── test_all_models.py   # Exhaustive model discovery
└── references/              # Source repo mirrors (gitignored)
```

## Output Format (JSONL)

```json
{
  "endpoint": "Zen-DeepSeek-V4-Flash",
  "model": "deepseek-v4-flash-free",
  "prompt": "Tell me an interesting fact about science in one sentence.",
  "status": "ok",
  "generation": "The speed of light is so fundamentally tied to...",
  "latency_ms": 731.2,
  "usage": {"prompt_tokens": 12, "completion_tokens": 25, "total_tokens": 37}
}
```

## Scaling Up

`providers.py` has configs for 30+ APIs. Set the environment variables for S-Tier providers
(Mistral, Groq, Google Gemini, NVIDIA NIM) and add them to `pipeline.py` to 5-10x throughput.

## Sources

- [cheahjs/free-llm-api-resources](https://github.com/cheahjs/free-llm-api-resources)
- [mnfst/awesome-free-llm-apis](https://github.com/mnfst/awesome-free-llm-apis)
- [12britz/awesome-free-models](https://github.com/12britz/awesome-free-models)
- [public-apis/public-apis](https://github.com/public-apis/public-apis)

## License

MIT
