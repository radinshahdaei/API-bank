# Discovery-first architecture

API Bank treats discovery, documentation evidence, live operation, and dataset generation as
separate concerns. This prevents an old catalog entry or a successful HTTP request from being
mistaken for proof that an API is currently free.

## Lifecycle

```text
source adapters / AI research
            |
            v
  canonical candidates  ---->  agent research queue
            |                         |
            |<--- structured findings-+
            v
 deterministic probes
            |
            v
 immutable probe history
            |
            v
 recent verified export  ---->  dataset generator
```

The local SQLite database is operational state. It holds canonical candidates and every probe
result. Tracked JSON exports are snapshots for downstream tools and review.

## Two independent evidence axes

Each candidate has two kinds of evidence:

- **Commercial/access evidence:** unknown, claimed, documented, or directly observed no-auth
  access. An AI agent can research and cite this, but cannot prove it with prose alone.
- **Operational evidence:** the latest deterministic probe status. Only a structurally valid
  chat-completion response becomes `verified`.

Consumers should inspect both axes. `verified` means operationally working at probe time; it
does not silently promise that a provider's pricing or terms will remain unchanged.

## Agent boundary

Agents are best used for the semantic work that ordinary code handles poorly:

- finding new provider documentation and changes;
- comparing conflicting model IDs or endpoint formats;
- extracting free-tier and rate-limit claims with provenance;
- investigating failed or ambiguous probes;
- proposing new protocol adapters.

Code remains responsible for URL validation, credentials, network requests, response parsing,
timestamps, state transitions, and exports. Research output must conform to
`schemas/agent-findings.schema.json` before ingestion.

The repository uses `AGENTS.md` for durable project rules. For unattended operation, Codex can
be invoked non-interactively with a JSON output schema; scheduled automation should retain the
same least-privilege and domain-restriction policy. See the official Codex documentation for
[AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md.md) and
[non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode.md).

## Security policy

- HTTPS is required by default.
- Local, private, link-local, and reserved IP targets are rejected.
- Redirects are disabled so a candidate cannot redirect a probe to a different host.
- No-auth probes never read or send environment credentials.
- Authenticated probes require an explicit flag and a configured environment-variable name.
- Probe prompts contain no repository data or secrets, and response previews are truncated.
- Web research is treated as untrusted input due to prompt-injection risk.

## Roadmap

1. **Foundation (complete):** canonical schema, legacy ingestion, SQLite history, agent queue,
   no-auth OpenAI-compatible probe, and verified export.
2. **Discovery adapters (current):** OpenAI-compatible model-list expansion and official-source
   change detection based on content hashes; selected provider feeds can build on this layer.
3. **Protocol coverage (complete):** Gemini, Cohere, Cloudflare, and Ollama adapters normalize
   native requests and responses behind the same credential-safe probe interface.
4. **Verification policy (next):** expiry windows, repeated probes, rate-limit characterization,
   response-quality checks, and explicit confidence scoring.
5. **Automation:** scheduled research/probe runs, reviewable diffs, and notifications for newly
   verified or newly failing endpoints.
6. **Generator migration:** make `pipeline.py` consume the recent verified export and fix its
   resume and scheduling behavior.
