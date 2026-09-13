#!/usr/bin/env python3
"""Classify a local complaint against the SPEC §10 intake ladder.

Never scrapes a tracker. Never opens GitHub issues or PRs.
origin_write_permitted means the *protocol* would allow a later publisher —
this script does not perform the write.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ACTIONS = frozenset({"ingest", "promote_issue", "open_pr"})
POLICIES = frozenset({"allowed", "forbidden", "unknown"})

DISPOSITIONS = frozenset(
    {
        "local_draft",
        "local_duplicate",
        "stop_covered",
        "needs_discussion",
        "origin_write_blocked",
        "origin_issue_allowed",
        "origin_pr_blocked",
        "origin_pr_allowed",
    }
)


def _bool(report: dict, key: str, default: bool = False) -> bool:
    if key not in report:
        return default
    val = report[key]
    if not isinstance(val, bool):
        raise SystemExit(f"{key} must be a boolean")
    return val


def decide(report: dict) -> dict:
    """Fail-closed intake. Default capture is a local draft, not a public issue."""
    if not isinstance(report, dict):
        raise SystemExit("report must be a JSON object")
    action = report.get("action", "ingest")
    if action not in ACTIONS:
        raise SystemExit(f"unknown action {action!r}")
    policy = report.get("origin_policy", "unknown")
    if policy not in POLICIES:
        raise SystemExit(f"unknown origin_policy {policy!r}")

    competing = _bool(report, "competing_pr")
    duplicate = report.get("duplicate_of")
    has_dup = isinstance(duplicate, str) and bool(duplicate.strip())
    reproduced = _bool(report, "reproduced")
    in_scope = _bool(report, "in_scope")
    github_writes = _bool(report, "github_writes")
    claimed = _bool(report, "claimed")
    has_receipt = _bool(report, "has_receipt")
    human = _bool(report, "human_or_policy_allow")

    def result(disposition: str, origin_write_permitted: bool, *reasons: str) -> dict:
        if disposition not in DISPOSITIONS:
            raise SystemExit(f"internal: bad disposition {disposition}")
        return {
            "disposition": disposition,
            "origin_write_permitted": origin_write_permitted,
            "reasons": list(reasons),
        }

    if competing:
        return result(
            "stop_covered",
            False,
            "competing PR or maintainer branch covers the scope",
        )
    if has_dup:
        return result("local_duplicate", False, "one canonical issue per problem")

    # Capture is never an origin write — even when later promote gates would pass.
    if action == "ingest":
        return result("local_draft", False, "ingest is local-only")

    if policy != "allowed":
        return result("origin_write_blocked", False, f"origin_policy={policy} fails closed")
    if not github_writes:
        return result("origin_write_blocked", False, "github_writes=0 until authorized")

    missing = []
    if not reproduced:
        missing.append("not reproduced")
    if not in_scope:
        missing.append("not in_scope")
    if not human:
        missing.append("no human_or_policy_allow")
    if missing:
        return result("needs_discussion", False, *missing)

    if action == "promote_issue":
        return result("origin_issue_allowed", True, "issue promote gates passed")

    pr_missing = []
    if not claimed:
        pr_missing.append("not claimed")
    if not has_receipt:
        pr_missing.append("no exact-head receipt")
    if pr_missing:
        return result("origin_pr_blocked", False, *pr_missing)
    return result("origin_pr_allowed", True, "pr gates passed")


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must be a JSON object")
    return data


def self_test(fixture_dir: Path) -> int:
    files = sorted(fixture_dir.glob("*.json"))
    if not files:
        print(f"no fixtures in {fixture_dir}", file=sys.stderr)
        return 2
    failed = 0
    for path in files:
        payload = load_json(path)
        report = payload.get("report", payload)
        want = payload.get("want")
        got = decide(report)
        if want is None:
            print(f"FAIL {path.name}: fixture needs a want object", file=sys.stderr)
            failed += 1
            continue
        for key in ("disposition", "origin_write_permitted"):
            if key not in want:
                print(f"FAIL {path.name}: want missing {key}", file=sys.stderr)
                failed += 1
                break
            if got[key] != want[key]:
                print(
                    f"FAIL {path.name}: {key} got {got[key]!r} want {want[key]!r} reasons={got['reasons']}",
                    file=sys.stderr,
                )
                failed += 1
                break
        else:
            print(f"ok {path.name}")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="SPEC §10 intake ladder (local fixtures only)")
    p.add_argument("path", nargs="?", type=Path, help="report JSON or fixture with report+want")
    p.add_argument("--self-test", type=Path, metavar="DIR", help="run fixtures in DIR")
    p.add_argument("--json", action="store_true", help="print classify result as JSON")
    args = p.parse_args(argv)
    if args.self_test is not None:
        return self_test(args.self_test)
    if args.path is None:
        p.print_help()
        return 2
    payload = load_json(args.path)
    report = payload["report"] if "report" in payload else payload
    got = decide(report)
    json.dump(got, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
