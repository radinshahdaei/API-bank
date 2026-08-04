# API Bank — Discover and Verify Free LLM APIs

API Bank is an evidence-first toolkit for finding, researching, and continuously testing free
text-generation APIs. It combines deterministic HTTP probes with structured research from an
AI agent. Large-scale dataset generation remains available as a secondary workflow.

## Finder quick start

```bash
pip install requests

# Import the existing catalog and known runtime endpoints as initial candidates
python -m api_bank discover --source legacy

# Inspect candidates and create work for an AI research agent
python -m api_bank list
python -m api_bank agent-queue --output agent-queue.json

# Ask a compatible endpoint which models it currently exposes
python -m api_bank models --id CANDIDATE_ID

# Probe one candidate without sending credentials
python -m api_bank probe --id CANDIDATE_ID

# Require three recent successes before promotion
python -m api_bank probe --id CANDIDATE_ID --repeat 3 --interval 2
python -m api_bank export --min-successes 3

# Watch cited documentation and pricing pages for changes
python -m api_bank source-sync
python -m api_bank source-check

# Summarize state and export endpoints with a successful probe from the last 7 days
python -m api_bank report
python -m api_bank export --output docs/verified_endpoints.v2.json
```

Runtime state is stored in `.api-bank/state.db` and is intentionally gitignored. Probe history
is retained so the project can distinguish a one-off failure from a provider that has gone
stale.

## Agent-assisted discovery

The repository includes a research prompt, durable agent rules, and a strict output schema:

```bash
python -m api_bank agent-queue --output agent-queue.json

codex exec --sandbox workspace-write \
  "Read agent/research_prompt.md and agent-queue.json, then complete the research task." \
  --output-schema schemas/agent-findings.schema.json \
  -o .api-bank/agent-findings.json

python -m api_bank discover --source file --input .api-bank/agent-findings.json
```

The same research-only cycle is available as `scripts/run_agent_research.sh`. It creates and
ingests structured findings but deliberately leaves network probing as a separate reviewed step.

The agent proposes documentation-backed facts. Only the deterministic probe engine can mark an
endpoint operationally verified. Credentials are never sent unless `probe --with-auth` is
explicitly selected.

Probe adapters currently cover OpenAI-compatible chat, Google Gemini, Cohere v2 chat, Ollama
native chat, and Cloudflare Workers AI. Model enumeration currently targets OpenAI-compatible
`/models` endpoints.

See [the finder architecture](docs/finder-architecture.md) for the lifecycle, trust boundary,
security model, and roadmap.

## Dataset generation (secondary)

The legacy generator still targets six previously verified no-auth endpoints:

```bash
# 6,000 samples from 10 fact prompts
python pipeline.py --prompts prompts.txt --max-tokens 100 --temperature 0.9 \
  --max-per-endpoint 100 --output dataset.jsonl

# Template mode: 3 styles × 4 topics
python pipeline.py \
  --template "Tell me an interesting fact about {topic} in one sentence." \
  --vars topic="science,history,animals,space" \
  --output dataset.jsonl
```

The next migration will make this generator consume the new recent verified export instead of
maintaining its own hard-coded endpoint list. That migration is available with `--registry`:

```bash
python -m api_bank export --output docs/verified_endpoints.v2.json
python pipeline.py --registry docs/verified_endpoints.v2.json \
  --prompts prompts.txt --output dataset.jsonl
```

Registry mode defaults to no-auth OpenAI-compatible endpoints. Authenticated registry entries
require `--registry-with-auth` and their configured environment variable.

## Project structure

```text
api_bank/                  Discovery, persistence, probe, and CLI package
agent/research_prompt.md   Agent research contract
schemas/                   Machine-readable agent output schema
pipeline.py                Legacy dataset generation engine
providers.py               Legacy 30-provider seed catalog
test_framework.py          Legacy multi-protocol live test harness
docs/                      Architecture, catalog, and verified snapshots
tests/                     Offline unit tests plus legacy live investigation scripts
```

## Development checks

```bash
python -m unittest discover -s tests -p 'test_unit_*.py'
python -m py_compile api_bank/*.py pipeline.py providers.py
```

Live endpoint probes are deliberately not part of the offline unit-test suite.

## License

MIT
