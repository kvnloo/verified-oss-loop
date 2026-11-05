#!/usr/bin/env python3
"""Export stored factory receipts without dispatching or writing to the ledger.

Counts cover this home only, across its full history, not a global queue or time window.
Queued means a registered task without a builder attempt, not admission eligibility.
Sent requires a Hermes builder session binding. Returned requires a stored completion.
Tested requires a separate exact-head verifier receipt, not a fresh test run by this tool.
Merged is null because the runtime ledger does not observe GitHub merge authority.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime import admission, factory


def snapshot(home: Path, requested=()) -> dict:
    home = home.expanduser().resolve()
    cfg = factory.load_config(home / "factory.json")
    path = factory.resolve(home, cfg.get("state_dir", "state")) / "ledger.sqlite"
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        tasks = [dict(r) for r in db.execute("SELECT * FROM tasks ORDER BY task_id")]
        attempts = [dict(r) for r in db.execute("SELECT * FROM attempts ORDER BY created_at, attempt_id")]
        holds = [dict(r) for r in db.execute("SELECT * FROM holds ORDER BY task_id, role")]
    for a in attempts:
        a["native"] = json.loads(a["native"])
        a["evidence"] = json.loads(a["evidence"])
    for t in tasks:
        t["goal_lock"] = json.loads(t["goal_lock"])
    registered = {r["id"] for r in cfg["repos"]}
    repos = {}
    for repo in sorted(registered | {t["repo"] for t in tasks} | set(requested)):
        tids = {t["task_id"] for t in tasks if t["repo"] == repo}
        builders = [a for a in attempts if a["task_id"] in tids and a["role"] == "builder"]
        native = [a for a in builders if a["native"].get("harness") == "hermes" and a["session_id"]]
        tested = []
        for b in native:
            for v in attempts:
                e = v["evidence"]
                tests = e.get("tests", {})
                if (b["state"] == "independently_verified" and v["role"] == "verifier"
                        and v["task_id"] == b["task_id"] and v["verifies_attempt"] == b["attempt_id"]
                        and v["lease_owner"] != b["lease_owner"] and v["state"] == "completed"
                        and b["session_id"] != v["session_id"]
                        and re.fullmatch(r"[0-9a-f]{40}", b["head_revision"] or "")
                        and v["head_revision"] == e.get("head_revision") == e.get("checked_out") == b["head_revision"]
                        and e.get("verdict") == "APPROVE_EXACT_HEAD"
                        and tests.get("green", {}).get("exit_code") == 0
                        and tests.get("red", {}).get("exit_code") not in (None, 0)):
                    tested.append(b["attempt_id"])
                    break
        repos[repo] = {"registered": repo in registered, "counts": {
            "queued": len(tids - {a["task_id"] for a in builders}),
            "sent": len(native),
            "returned": sum(bool(a["result_digest"]) for a in native),
            "tested": len(tested), "merged": None}, "tested_attempts": tested}
    harness = cfg["harnesses"][cfg["roster"]["builder"]["harness"]]
    admission_path = factory.resolve(home, cfg.get("admission_file", "admission.json"))
    return {"observed_at": datetime.now(timezone.utc).isoformat(), "home": str(home),
            "ledger": str(path), "scope": __doc__, "admission_path": str(admission_path),
            "admission": admission.decide(admission.load(admission_path), harness["lane"]),
            "repos": repos, "tasks": tasks, "attempts": attempts, "holds": holds,
            "unresolved_attempts": [a["attempt_id"] for a in attempts
                                    if a["state"] in ("authorized", "submitted", "reconciling")]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--home", required=True, type=Path)
    p.add_argument("--repo", action="append", default=[], help="Also include an unregistered repo ID")
    args = p.parse_args()
    print(json.dumps(snapshot(args.home, args.repo), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
