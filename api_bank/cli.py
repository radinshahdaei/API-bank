"""Command-line interface for the discovery-first API Bank workflow."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .discovery import candidates_from_file, legacy_candidates
from .probe import Prober
from .store import DEFAULT_DB, Store


def _json_dump(value, output: str | None = None) -> None:
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
        print(f"Wrote {path}")
    else:
        print(rendered, end="")


def discover(args, store: Store) -> None:
    candidates = list(legacy_candidates()) if args.source == "legacy" else candidates_from_file(args.input)
    created = sum(store.upsert_candidate(candidate) for candidate in candidates)
    print(f"Discovered {len(candidates)} candidates ({created} new, {len(candidates) - created} updated).")


def list_candidates(args, store: Store) -> None:
    candidates = store.list_candidates(args.status)
    if args.json:
        _json_dump([candidate.as_dict() for candidate in candidates])
        return
    if not candidates:
        print("No candidates found.")
        return
    for candidate in candidates:
        model = candidate.model or "<model discovery needed>"
        print(f"{candidate.id}  {candidate.status:16s}  {candidate.provider:24.24s}  {model}")


def probe(args, store: Store) -> None:
    if args.id:
        candidate = store.get_candidate(args.id)
        if not candidate:
            raise SystemExit(f"Unknown candidate: {args.id}")
        candidates = [candidate]
    else:
        candidates = store.list_candidates()
        if not args.with_auth:
            candidates = [candidate for candidate in candidates if candidate.auth_mode in {"none", "unknown"}]
        candidates = [
            candidate
            for candidate in candidates
            if candidate.model and candidate.protocol == "openai-chat"
        ]
        candidates = candidates[: args.limit]

    if not candidates:
        print("No probeable candidates selected.")
        return
    prober = Prober(timeout=args.timeout, allow_http=args.allow_http)
    for candidate in candidates:
        mode = "with auth" if args.with_auth else "without auth"
        print(f"Probing {candidate.provider} / {candidate.model} ({mode})...")
        result = prober.probe_chat(candidate, with_auth=args.with_auth)
        store.add_probe(result)
        suffix = f" HTTP {result.http_status}" if result.http_status else ""
        print(f"  {result.status}{suffix} ({result.latency_ms or 0:.0f} ms)")


def agent_queue(args, store: Store) -> None:
    tasks = []
    for candidate in store.list_candidates():
        latest = store.latest_probe(candidate.id)
        missing = []
        if not candidate.source_url:
            missing.append("official source URL")
        if candidate.free_tier in {"unknown", "claimed"}:
            missing.append("official free-tier evidence")
        if not candidate.model:
            missing.append("current text model ID")
        if candidate.status in {
            "needs_research",
            "invalid_endpoint",
            "invalid_response",
            "rate_limited",
            "unreachable",
            "server_error",
            "rejected",
        }:
            missing.append("correct endpoint/protocol details")
        if candidate.status == "needs_adapter":
            missing.append(f"a deterministic {candidate.protocol} protocol adapter")
        if latest is None:
            missing.append("live probe")
        if missing:
            tasks.append(
                {
                    "candidate": candidate.as_dict(),
                    "latest_probe": latest,
                    "research_needed": sorted(set(missing)),
                }
            )
    _json_dump({"generated_at": datetime.now(timezone.utc).isoformat(), "tasks": tasks}, args.output)


def export_verified(args, store: Store) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.max_age_days)
    endpoints = []
    for row in store.verification_rows():
        item = dict(row)
        tested_at = datetime.fromisoformat(item["tested_at"])
        if tested_at < cutoff:
            continue
        item["auth_used"] = bool(item["auth_used"])
        endpoints.append(item)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": {
            "max_probe_age_days": args.max_age_days,
            "meaning": "A recent chat-completion probe returned a structurally valid response.",
            "free_tier_is_separate_evidence": True,
        },
        "endpoints": endpoints,
    }
    _json_dump(payload, args.output)


def report(_args, store: Store) -> None:
    candidates = store.list_candidates()
    counts: dict[str, int] = {}
    for candidate in candidates:
        counts[candidate.status] = counts.get(candidate.status, 0) + 1
    print(f"Candidates: {len(candidates)}")
    for status, count in sorted(counts.items()):
        print(f"  {status:18s} {count}")
    probed = sum(store.latest_probe(candidate.id) is not None for candidate in candidates)
    print(f"Probed at least once: {probed}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Discover, research, and verify free text-generation APIs")
    parser.add_argument("--db", default=str(DEFAULT_DB), help=f"State database (default: {DEFAULT_DB})")
    commands = parser.add_subparsers(dest="command", required=True)

    command = commands.add_parser("discover", help="Ingest candidates from a source")
    command.add_argument("--source", choices=["legacy", "file"], default="legacy")
    command.add_argument("--input", help="Agent finding JSON (required for --source file)")
    command.set_defaults(handler=discover)

    command = commands.add_parser("list", help="List canonical candidates")
    command.add_argument("--status")
    command.add_argument("--json", action="store_true")
    command.set_defaults(handler=list_candidates)

    command = commands.add_parser("probe", help="Run tiny deterministic chat probes")
    command.add_argument("--id", help="Probe one candidate ID")
    command.add_argument("--limit", type=int, default=10)
    command.add_argument("--timeout", type=float, default=20)
    command.add_argument("--with-auth", action="store_true", help="Explicitly allow configured API credentials")
    command.add_argument("--allow-http", action="store_true", help="Allow cleartext HTTP targets")
    command.set_defaults(handler=probe)

    command = commands.add_parser("agent-queue", help="Build the structured research queue")
    command.add_argument("--output")
    command.set_defaults(handler=agent_queue)

    command = commands.add_parser("export", help="Export recently verified endpoints")
    command.add_argument("--output", default="docs/verified_endpoints.v2.json")
    command.add_argument("--max-age-days", type=int, default=7)
    command.set_defaults(handler=export_verified)

    command = commands.add_parser("report", help="Summarize finder state")
    command.set_defaults(handler=report)
    return parser


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "discover" and args.source == "file" and not args.input:
        parser.error("--input is required with --source file")
    if args.command == "probe" and args.with_auth and not args.id:
        parser.error("--with-auth requires --id so credentials are scoped to one reviewed target")
    with Store(args.db) as store:
        args.handler(args, store)
