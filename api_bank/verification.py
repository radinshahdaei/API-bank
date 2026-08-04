"""Explicit policy for promoting operational probes into verified exports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .models import Candidate


FREE_EVIDENCE = {"documented", "observed_no_auth"}


@dataclass(frozen=True)
class VerificationPolicy:
    max_age_days: int = 7
    min_successes: int = 1
    require_free_evidence: bool = True

    def evaluate(
        self,
        candidate: Candidate,
        history: list[dict[str, Any]],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=self.max_age_days)
        recent = [item for item in history if datetime.fromisoformat(item["tested_at"]) >= cutoff]
        successes = [item for item in recent if item["status"] == "working"]
        latest = history[0] if history else None
        reasons = []
        if latest is None:
            reasons.append("never_probed")
        elif latest["status"] != "working":
            reasons.append(f"latest_probe_{latest['status']}")
        elif datetime.fromisoformat(latest["tested_at"]) < cutoff:
            reasons.append("latest_probe_stale")
        if len(successes) < self.min_successes:
            reasons.append("insufficient_recent_successes")
        if self.require_free_evidence and candidate.free_tier not in FREE_EVIDENCE:
            reasons.append("free_access_not_documented_or_observed")
        return {
            "eligible": not reasons,
            "reasons": reasons,
            "recent_successes": len(successes),
            "recent_probes": len(recent),
            "latest_probe": latest,
            "free_evidence": candidate.free_tier,
        }
