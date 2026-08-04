"""Command-line interface for the discovery-first API Bank workflow."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .discovery import candidates_from_file, legacy_candidates
from .models import Candidate, WatchedSource
from .probe import Prober
from .sources import SourceWatcher
from .store import DEFAULT_DB, Store
from .verification import VerificationPolicy


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
        for repetition in range(args.repeat):
            mode = "with auth" if args.with_auth else "without auth"
            run = f", run {repetition + 1}/{args.repeat}" if args.repeat > 1 else ""
            print(f"Probing {candidate.provider} / {candidate.model} ({mode}{run})...")
            result = prober.probe_chat(candidate, with_auth=args.with_auth)
            store.add_probe(result)
            suffix = f" HTTP {result.http_status}" if result.http_status else ""
            print(f"  {result.status}{suffix} ({result.latency_ms or 0:.0f} ms)")
            if repetition + 1 < args.repeat and args.interval:
                time.sleep(args.interval)


def discover_models(args, store: Store) -> None:
    candidate = store.get_candidate(args.id)
    if not candidate:
        raise SystemExit(f"Unknown candidate: {args.id}")
    prober = Prober(timeout=args.timeout)
    mode = "with auth" if args.with_auth else "without auth"
    print(f"Enumerating models from {candidate.base_url} ({mode})...")
    result = prober.probe_models(candidate, with_auth=args.with_auth)
    store.add_probe(result)
    if result.status != "working":
        suffix = f" HTTP {result.http_status}" if result.http_status else ""
        print(f"  {result.status}{suffix}: {result.error or ''}")
        return
    model_ids = result.metadata.get("models", [])[: args.limit]
    created = 0
    for model_id in model_ids:
        discovered = Candidate(
            provider=candidate.provider,
            base_url=candidate.base_url,
            model=model_id,
            protocol=candidate.protocol,
            auth_mode=candidate.auth_mode,
            api_key_env=candidate.api_key_env,
            account_id_env=candidate.account_id_env,
            free_tier=candidate.free_tier,
            source_kind=candidate.source_kind,
            source_url=candidate.source_url,
            evidence_summary=candidate.evidence_summary,
            notes=f"Discovered from {candidate.base_url}/models",
        )
        created += int(store.upsert_candidate(discovered))
    print(
        f"  Found {result.metadata.get('model_count', len(model_ids))} models; "
        f"ingested {len(model_ids)} ({created} new)."
    )


def source_sync(_args, store: Store) -> None:
    added = skipped = 0
    for candidate in store.list_candidates():
        if not candidate.source_url or urlsplit(candidate.source_url).scheme != "https":
            skipped += 1
            continue
        try:
            source = WatchedSource(
                provider=candidate.provider,
                url=candidate.source_url,
                kind="candidate_evidence",
            )
        except ValueError:
            skipped += 1
            continue
        added += int(store.upsert_source(source))
    print(f"Synchronized sources ({added} new, {skipped} candidates without watchable HTTPS evidence).")


def source_list(args, store: Store) -> None:
    sources = store.list_sources(args.status)
    if args.json:
        _json_dump([source.as_dict() for source in sources])
        return
    if not sources:
        print("No watched sources found.")
        return
    for source in sources:
        print(f"{source.id}  {source.status:14s}  {source.provider:24.24s}  {source.url}")


def source_check(args, store: Store) -> None:
    if args.id:
        source = store.get_source(args.id)
        if not source:
            raise SystemExit(f"Unknown source: {args.id}")
        sources = [source]
    else:
        sources = store.list_sources()[: args.limit]
    watcher = SourceWatcher(timeout=args.timeout, max_bytes=args.max_bytes)
    for source in sources:
        print(f"Checking {source.provider}: {source.url}")
        check = watcher.check(source)
        store.add_source_check(check)
        changed = " changed" if check.changed else ""
        suffix = f" HTTP {check.http_status}" if check.http_status else ""
        print(f"  {check.status}{changed}{suffix} ({check.latency_ms or 0:.0f} ms)")


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
        elif datetime.fromisoformat(latest["tested_at"]) < datetime.now(timezone.utc) - timedelta(
            days=args.stale_days
        ):
            missing.append("fresh live probe")
        if missing:
            tasks.append(
                {
                    "candidate": candidate.as_dict(),
                    "latest_probe": latest,
                    "research_needed": sorted(set(missing)),
                }
            )
    source_tasks = [
        {
            "source": source.as_dict(),
            "research_needed": "Review the source change and refresh affected API claims.",
        }
        for source in store.list_sources()
        if source.status in {"changed", "http_error", "network_error", "too_large"}
    ]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_tasks": tasks,
        "source_tasks": source_tasks,
        "scouting_task": {
            "goal": "Find newly available free text-generation APIs not already present.",
            "requirements": [
                "Prefer current official provider documentation.",
                "Record exact endpoint, model, authentication, and free-tier evidence.",
                "Do not send credentials or generation requests during research.",
            ],
        },
    }
    _json_dump(payload, args.output)


def export_verified(args, store: Store) -> None:
    policy = VerificationPolicy(
        max_age_days=args.max_age_days,
        min_successes=args.min_successes,
        require_free_evidence=not args.allow_unverified_free,
    )
    endpoints = []
    excluded = []
    for candidate in store.list_candidates():
        evaluation = policy.evaluate(candidate, store.probe_history(candidate.id))
        if evaluation["eligible"]:
            item = candidate.as_dict()
            item["verification"] = evaluation
            endpoints.append(item)
        elif args.include_excluded:
            excluded.append(
                {
                    "id": candidate.id,
                    "provider": candidate.provider,
                    "model": candidate.model,
                    "reasons": evaluation["reasons"],
                }
            )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": {
            "max_probe_age_days": args.max_age_days,
            "min_recent_successes": args.min_successes,
            "require_free_evidence": not args.allow_unverified_free,
            "meaning": "The latest probe worked and all configured evidence gates passed.",
        },
        "endpoints": endpoints,
    }
    if args.include_excluded:
        payload["excluded"] = excluded
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
    policy = VerificationPolicy()
    eligible = sum(
        policy.evaluate(candidate, store.probe_history(candidate.id))["eligible"]
        for candidate in candidates
    )
    print(f"Eligible for default export: {eligible}")


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
    command.add_argument("--repeat", type=int, default=1, choices=range(1, 11))
    command.add_argument("--interval", type=float, default=0, help="Seconds between repeats (max 60)")
    command.set_defaults(handler=probe)

    command = commands.add_parser("models", help="Enumerate and ingest models from one candidate")
    command.add_argument("--id", required=True, help="Candidate whose base URL should be queried")
    command.add_argument("--limit", type=int, default=100, help="Maximum model IDs to ingest")
    command.add_argument("--timeout", type=float, default=20)
    command.add_argument("--with-auth", action="store_true")
    command.set_defaults(handler=discover_models)

    command = commands.add_parser("source-sync", help="Watch candidate evidence URLs")
    command.set_defaults(handler=source_sync)

    command = commands.add_parser("source-list", help="List watched evidence sources")
    command.add_argument("--status")
    command.add_argument("--json", action="store_true")
    command.set_defaults(handler=source_list)

    command = commands.add_parser("source-check", help="Check watched sources for content changes")
    command.add_argument("--id")
    command.add_argument("--limit", type=int, default=20)
    command.add_argument("--timeout", type=float, default=20)
    command.add_argument("--max-bytes", type=int, default=1_000_000)
    command.set_defaults(handler=source_check)

    command = commands.add_parser("agent-queue", help="Build the structured research queue")
    command.add_argument("--output")
    command.add_argument("--stale-days", type=int, default=7)
    command.set_defaults(handler=agent_queue)

    command = commands.add_parser("export", help="Export recently verified endpoints")
    command.add_argument("--output", default="docs/verified_endpoints.v2.json")
    command.add_argument("--max-age-days", type=int, default=7)
    command.add_argument("--min-successes", type=int, default=1)
    command.add_argument("--allow-unverified-free", action="store_true")
    command.add_argument("--include-excluded", action="store_true")
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
    if args.command == "probe" and not 0 <= args.interval <= 60:
        parser.error("--interval must be between 0 and 60 seconds")
    with Store(args.db) as store:
        args.handler(args, store)
