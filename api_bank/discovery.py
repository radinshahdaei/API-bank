"""Discovery adapters turn heterogeneous findings into canonical candidates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import Candidate


LEGACY_PLACEHOLDERS = {
    "AINative Studio",
    "AnyAPI",
    "FreeTheAi",
    "Requesty",
    "LongCat AI",
    "Chat Oripe",
    "BazaarLink",
    "ZeroLimitAI",
    "Free.ai",
    "Chutes.ai",
}

LEGACY_PROTOCOLS = {
    "Google Gemini": "gemini",
    "Cloudflare Workers AI": "cloudflare-workers-ai",
    "Cohere": "cohere-chat",
    "Ollama Cloud": "ollama-chat",
}

SUPPORTED_PROBE_PROTOCOLS = {
    "openai-chat",
    "gemini",
    "cloudflare-workers-ai",
    "cohere-chat",
    "ollama-chat",
}


def legacy_candidates() -> Iterable[Candidate]:
    """Import the existing catalog and six runtime endpoints as initial seeds."""
    from pipeline import ENDPOINTS
    from providers import PROVIDERS

    runtime_ids = {(endpoint.base_url.rstrip("/"), endpoint.model) for endpoint in ENDPOINTS}
    for provider in PROVIDERS:
        notes = provider.get("notes", "")
        is_placeholder = (
            provider["name"] in LEGACY_PLACEHOLDERS
            or "placeholder" in notes.lower()
            or "verify" in notes.lower()
        )
        protocol = (
            "openai-chat"
            if provider.get("openai_compatible")
            else LEGACY_PROTOCOLS.get(provider["name"], "unknown")
        )
        yield Candidate(
            provider=provider["name"],
            base_url=provider["base_url"],
            model=provider.get("model"),
            protocol=protocol,
            auth_mode="api_key" if provider.get("auth_required") else "none",
            api_key_env=provider.get("api_key_env"),
            account_id_env=provider.get("account_id_env"),
            free_tier="claimed",
            source_kind="legacy_catalog",
            source_url="docs/catalog.md",
            evidence_summary=notes or None,
            notes="Requires protocol adapter" if not provider.get("openai_compatible") else None,
            status=(
                "needs_research"
                if is_placeholder
                else "needs_adapter"
                if protocol not in SUPPORTED_PROBE_PROTOCOLS
                else "discovered"
            ),
        )

    # Runtime models are more specific than the single-model provider catalog.
    for endpoint in ENDPOINTS:
        if (endpoint.base_url.rstrip("/"), endpoint.model) in runtime_ids:
            yield Candidate(
                provider=endpoint.name.split("-", 1)[0],
                base_url=endpoint.base_url,
                model=endpoint.model,
                auth_mode="none",
                free_tier="observed_no_auth",
                source_kind="legacy_verified",
                source_url="docs/verified_endpoints.json",
                evidence_summary="Previously verified by the legacy API Bank test scripts.",
            )


def candidates_from_file(path: str | Path) -> list[Candidate]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    findings = value.get("findings") if isinstance(value, dict) else value
    if not isinstance(findings, list):
        raise ValueError("Discovery input must be a list or an object containing a findings list")
    candidates = []
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError("Every finding must be a JSON object")
        finding = dict(finding)
        finding.setdefault("source_kind", "agent_research")
        finding.setdefault("status", "discovered")
        candidates.append(Candidate.from_dict(finding))
    return candidates
