# API Bank — Free LLM Dataset Generation Pipeline

Generate large text datasets using **15 verified free LLM endpoints** — no API keys, no credit cards, no signup required.

## Quick Start

```bash
# Install
pip install requests

# Generate 150 samples from example prompts
python pipeline.py --prompts prompts.example.txt --max-per-endpoint 10 --output my_dataset.jsonl
```

```bash
# Template mode — 3 styles × 3 topics = 9 prompts × 13 endpoints
python pipeline.py \
  --template "Write a {style} about {topic}." \
  --vars style="a haiku,an essay,a tweet" topic="AI,cats,the ocean" \
  --output my_dataset.jsonl
```

## Verified Endpoints (13 stable, no auth)

| Provider | Endpoints | Rate Limit | Auth |
|---|---|---|---|
| **OVHcloud** | 7 models (Qwen, Mistral, Llama, GPT-OSS) | 2 RPM/model | None |
| **Kilo Gateway** | 4 models (Nemotron Ultra/Super/Nano, Ling) | 200 req/hr | None |
| **LLM7.io** | 2 models (Codestral, Gemini Flash) | 30 RPM | None |

**Sustained throughput:** ~18 req/min → **~1,000 generations/hour → ~25,000/day**

## Pipeline Features

- **Two input modes:** Prompt file or template × variables (cartesian product)
- **Shared rate limiters:** One per provider — no more 429 errors
- **Retry with backoff:** Auto-retries on rate limits
- **JSONL output:** One JSON record per generation, append-only, easy to parse
- **Resume:** `--resume` skips completed prompt×endpoint pairs
- **Graceful shutdown:** Ctrl+C saves progress
- **Dry run:** `--dry-run` shows job plan without API calls

```bash
# List all configured endpoints
python pipeline.py --list-endpoints

# Filter to specific providers
python pipeline.py --prompts prompts.txt --endpoint OVH Kilo

# Include flaky endpoints (gpt-oss-20b, Qwen3.6-27B)
python pipeline.py --prompts prompts.txt --include-flaky

# Resume interrupted run
python pipeline.py --prompts prompts.txt --output dataset.jsonl --resume
```

## Project Structure

```
API-bank/
├── pipeline.py              # Main dataset generation engine
├── providers.py             # 30 provider configurations (all tiers)
├── test_framework.py        # API testing & verification harness
├── catalog.md               # Full ranked catalog of 30 free APIs
├── verified_endpoints.json  # Machine-readable verified results
├── prompts.example.txt      # 10 example prompts
├── init.md                  # Original research brief
├── scripts/
│   └── update_references.sh # Clone/pull reference API repos
├── tests/
│   ├── test_noauth_deep.py  # Deep no-auth endpoint testing
│   └── test_noauth_r2.py    # Sequential rate-limit-safe tests
└── references/              # Mirrors of source repos (gitignored)
    ├── free-llm-api-resources/
    ├── awesome-free-llm-apis/
    ├── awesome-free-models/
    └── public-apis/
```

## Updating Reference Data

```bash
bash scripts/update_references.sh
```

This clones or pulls the 4 source repositories from `init.md` into `references/`.

## Adding Auth-Required APIs

The `providers.py` file contains configs for all 30 APIs including S-Tier providers
(Mistral, Groq, Google Gemini, NVIDIA NIM) that need API keys. Set the corresponding
environment variables and uncomment them in `pipeline.py` to 5-10x your throughput.

See `catalog.md` for the full ranked list with signup instructions.

## Output Format (JSONL)

```json
{
  "endpoint": "OVH-Mistral-Nemo",
  "model": "Mistral-Nemo-Instruct-2407",
  "prompt": "Write a short story about a robot learning to paint.",
  "prompt_hash": "2635215065744076406",
  "timestamp": "2026-07-31T07:41:51Z",
  "status": "ok",
  "generation": "In the quiet hum of the art restoration lab...",
  "latency_ms": 11192.7,
  "usage": {"prompt_tokens": 14, "completion_tokens": 512, "total_tokens": 526},
  "error": null
}
```

## Sources

Built from research across:
- [cheahjs/free-llm-api-resources](https://github.com/cheahjs/free-llm-api-resources)
- [mnfst/awesome-free-llm-apis](https://github.com/mnfst/awesome-free-llm-apis)
- [12britz/awesome-free-models](https://github.com/12britz/awesome-free-models)
- [public-apis/public-apis](https://github.com/public-apis/public-apis)

## License

MIT — use this for whatever you want.
