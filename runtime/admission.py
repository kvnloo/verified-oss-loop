"""Consume an admission decision; never make one. Stdlib only.

The factory enforces an approved constraint: a lane runs only when an external owner (a quota
probe, router or human) says it is available *now*. Missing, stale, unknown, exhausted or
throttled all hold the lane with a reason and a resume trigger. There is no fallback provider:
a held lane stays held.
"""
from __future__ import annotations

import calendar
import json
import time
from pathlib import Path


def _parse_ts(value: str) -> float | None:
    try:
        return float(calendar.timegm(time.strptime(value.replace("+00:00", "Z"), "%Y-%m-%dT%H:%M:%SZ")))
    except (ValueError, AttributeError):
        return None


def decide(doc: dict | None, lane: str, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    if not doc:
        return {"decision": "hold", "reason": "admission_missing", "resume_trigger": "fresh admission record for " + lane}
    observed = _parse_ts(str(doc.get("observed_at", "")))
    max_age = float(doc.get("max_age_s", 900))
    if observed is None or now - observed > max_age:
        return {"decision": "hold", "reason": "admission_stale",
                "resume_trigger": f"admission record newer than {int(max_age)}s for {lane}"}
    entry = (doc.get("lanes") or {}).get(lane)
    if not entry:
        return {"decision": "hold", "reason": "admission_unknown_lane", "resume_trigger": f"admission entry for {lane}"}
    state = entry.get("state")
    if state == "available":
        return {"decision": "allow", "reason": entry.get("evidence", "available"), "resume_trigger": ""}
    return {"decision": "hold", "reason": f"lane_{state or 'unknown'}",
            "resume_trigger": entry.get("resume_trigger") or f"{lane} reports available"}


def load(path: str | Path | None) -> dict | None:
    if not path or not Path(path).exists():
        return None
    return json.loads(Path(path).read_text())
