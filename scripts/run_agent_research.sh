#!/usr/bin/env bash
# Generate a research queue, run Codex with structured output, and ingest its findings.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
QUEUE_PATH="$PROJECT_DIR/agent-queue.json"
FINDINGS_PATH="$PROJECT_DIR/.api-bank/agent-findings.json"

cd "$PROJECT_DIR"
python -m api_bank discover --source legacy
python -m api_bank source-sync
python -m api_bank agent-queue --output "$QUEUE_PATH"

codex exec --sandbox workspace-write \
  "Read agent/research_prompt.md and agent-queue.json, then complete the research task." \
  --output-schema schemas/agent-findings.schema.json \
  -o "$FINDINGS_PATH"

python -m api_bank discover --source file --input "$FINDINGS_PATH"
python -m api_bank source-sync
python -m api_bank report
