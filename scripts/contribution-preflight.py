#!/usr/bin/env python3
"""Offline repository-aware contribution preflight.

This tool never scrapes a live tracker and never posts public content. It consumes
local repository policy plus bounded JSON exports supplied by a caller, then
classifies repository archetypes, policy, collision risk, and the safest next
mode. Optional --record persists collision fingerprints so later runs do not
rediscover/repost the same breadcrumb.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

MAX_TRACKER_ITEMS = 128
MAX_POLICY_FILES = 32
MAX_POLICY_BYTES = 128 * 1024
TOKEN = re.compile(r"[a-z0-9]+")
STOP = {
    "a", "an", "the", "and", "or", "to", "of", "for", "in", "on", "with",
    "after", "when", "plus", "own", "this", "that", "from", "into", "by",
}

POLICY_PATHS = [
    "AGENTS.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/pull_request_template.md",
]

ARCHETYPE_PATTERNS: dict[str, tuple[str, ...]] = {
    "maintainer-debt": (
        "triage", "stale", "duplicate", "backlog", "maintenance", "review queue",
    ),
    "strict-invariant": (
        "regression", "invariant", "deterministic", "compatibility", "conformance",
        "negative control", "abi", "api compatibility",
    ),
    "performance": (
        "benchmark", "performance", "latency", "throughput", "frame time", "fps",
        "allocation", "gpu", "cpu", "memory",
    ),
    "staged-multi-repo": (
        "multi-repo", "cross-repo", "cross repo", "workspace", "landing order",
        "version skew",
    ),
}

PROHIBITED_PATTERNS = (
    "ai-generated contributions are not accepted",
    "ai generated contributions are not accepted",
    "no ai-generated",
    "no ai generated",
    "ai contributions are prohibited",
    "llm-generated contributions are not accepted",
)
ALLOWED_PATTERNS = (
    "ai-assisted contributions are allowed",
    "ai assisted contributions are allowed",
    "ai-generated contributions are allowed",
    "ai generated contributions are allowed",
    "ai contributions are allowed",
    "ai assistance is allowed",
)
RESTRICTED_PATTERNS = (
    "generated-by",
    "assisted-by",
    "disclose ai",
    "ai disclosure",
    "ai-assisted contributions must",
    "ai assisted contributions must",
)


def words(value: str) -> frozenset[str]:
    return frozenset(
        token
        for token in TOKEN.findall(value.lower())
        if len(token) > 1 and token not in STOP
    )


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def read_text(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_POLICY_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return ""


def policy_documents(root: Path) -> list[tuple[str, str]]:
    docs: list[tuple[str, str]] = []
    seen: set[Path] = set()
    candidates = [root / rel for rel in POLICY_PATHS]
    template_dir = root / ".github" / "ISSUE_TEMPLATE"
    if template_dir.is_dir():
        candidates.extend(sorted(template_dir.glob("*"))[:MAX_POLICY_FILES])

    for path in candidates:
        if len(docs) >= MAX_POLICY_FILES or path in seen or not path.is_file():
            continue
        seen.add(path)
        text = read_text(path)
        if text:
            try:
                rel = str(path.relative_to(root))
            except ValueError:
                rel = str(path)
            docs.append((rel, text))
    return docs


def classify_policy(root: Path, docs: list[tuple[str, str]]) -> dict[str, Any]:
    joined = "\n".join(text.lower() for _, text in docs)
    if any(pattern in joined for pattern in PROHIBITED_PATTERNS):
        ai = "prohibited"
    elif any(pattern in joined for pattern in RESTRICTED_PATTERNS):
        ai = "explicit_restricted"
    elif any(pattern in joined for pattern in ALLOWED_PATTERNS):
        ai = "explicit_allowed"
    else:
        # AGENTS.md makes the repo agent-native, but its mere existence does
        # not prove AI-generated public contributions are allowed.
        ai = "unclear"

    disclosure_required = any(
        token in joined for token in ("assisted-by", "generated-by", "ai disclosure", "disclose ai")
    )
    trailer = (
        "Assisted-by"
        if "assisted-by" in joined
        else "Generated-by"
        if "generated-by" in joined
        else "unknown"
    )

    return {
        "ai_contribution": ai,
        "disclosure_required": disclosure_required if ai != "unclear" else "unknown",
        "required_trailer": trailer,
        "cla_dco_gpg": [],
        "contribution_surface": "github",
        "special_rules": [path for path, _ in docs],
    }


def classify_archetypes(root: Path, docs: list[tuple[str, str]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    lowered = [(path, text.lower()) for path, text in docs]

    if (root / "AGENTS.md").is_file():
        scored.append({"name": "agent-native", "score": 100, "evidence": ["AGENTS.md"]})

    for name, patterns in ARCHETYPE_PATTERNS.items():
        evidence: list[str] = []
        score = 0
        for path, text in lowered:
            hits = [pattern for pattern in patterns if pattern in text]
            if hits:
                score += len(hits)
                evidence.append(f"{path}: {', '.join(hits[:4])}")
        if name == "strict-invariant" and (root / "tests").is_dir():
            score += 1
            evidence.append("tests/: present")
        if score:
            scored.append({"name": name, "score": score, "evidence": evidence[:8]})

    if policy["ai_contribution"] == "prohibited":
        scored.append({"name": "ai-restricted", "score": 100, "evidence": ["policy: prohibited"]})
    elif policy["ai_contribution"] == "unclear":
        scored.append({"name": "conventional-ai-policy-unclear", "score": 1, "evidence": ["no explicit AI policy found"]})

    scored.sort(key=lambda row: (-int(row["score"]), str(row["name"])))
    return scored


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read {path}: {exc}") from exc


def normalize_tracker_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict) or "title" not in item:
        raise SystemExit("each tracker item must be an object with title")
    return {
        "number": item.get("number"),
        "title": str(item["title"]),
        "type": str(item.get("type", "issue")),
        "state": str(item.get("state", "open")),
        "url": item.get("url"),
        "merged": bool(item.get("merged", False)),
        "resolved": bool(item.get("resolved", False)),
        "thread_already_links_work": bool(item.get("thread_already_links_work", False)),
    }


def collision_fingerprint(candidate: dict[str, Any], match: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "candidate": {"issue": candidate.get("issue"), "title": candidate.get("title")},
            "match": {"number": match.get("number"), "title": match.get("title"), "url": match.get("url")},
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def collision_report(candidate: dict[str, Any], tracker: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    title = str(candidate.get("title", "")).strip()
    if not title:
        raise SystemExit("candidate needs a non-empty title")
    title_tokens = words(title)
    matches: list[dict[str, Any]] = []

    for raw in tracker:
        item = normalize_tracker_item(raw)
        similarity = jaccard(title_tokens, words(item["title"]))
        exact = re.sub(r"\W+", " ", title.lower()).strip() == re.sub(
            r"\W+", " ", item["title"].lower()
        ).strip()
        if not exact and similarity < threshold:
            continue
        relationship = "direct_fix" if exact or similarity >= 0.75 else "overlapping_scope"
        ctype = (
            "resolved_but_open"
            if item["state"] == "open" and (item["merged"] or item["resolved"])
            else "hard"
            if item["state"] == "open" and relationship == "direct_fix"
            else "partial"
            if item["state"] == "open"
            else "resolved_but_open"
            if item["merged"] or item["resolved"]
            else "ambiguous"
        )
        matches.append(
            {
                **item,
                "similarity": round(similarity, 3),
                "collision_type": ctype,
                "relationship": relationship,
                "confidence": "verified" if exact or similarity >= 0.75 else "likely",
            }
        )

    rank = {"hard": 5, "partial": 4, "resolved_but_open": 3, "superseded": 2, "ambiguous": 1}
    matches.sort(key=lambda row: (-rank.get(str(row["collision_type"]), 0), -float(row["similarity"])))
    top = matches[0] if matches else None
    return {
        "type": top["collision_type"] if top else "none",
        "related_work": matches,
        "relationship": top["relationship"] if top else "unknown",
        "confidence": top["confidence"] if top else "verified",
        "thread_already_links_work": bool(top and top["thread_already_links_work"]),
    }


def load_state(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"collision_fingerprints": []}
    raw = load_json(path)
    if not isinstance(raw, dict):
        raise SystemExit("state must be a JSON object")
    values = raw.get("collision_fingerprints", [])
    return {"collision_fingerprints": [str(v) for v in values if isinstance(v, str)]}


def choose_mode(candidate: dict[str, Any], policy: dict[str, Any], collision: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if policy["ai_contribution"] == "prohibited":
        return "drop", ["ai_policy_prohibited"]
    if policy["ai_contribution"] == "unclear":
        return "watch", ["ai_policy_unclear"]

    evidence = candidate.get("evidence") if isinstance(candidate.get("evidence"), dict) else {}
    if str(candidate.get("kind", "")).lower() == "performance" and not bool(evidence.get("benchmark")):
        return "drop", ["performance_evidence_missing"]

    if collision["type"] in {"hard", "resolved_but_open"}:
        if collision["thread_already_links_work"]:
            return "watch", ["collision_already_linked"]
        return "collision_memo", ["verified_collision"]
    if collision["type"] == "partial":
        return "watch", ["partial_collision_requires_human_scope_check"]

    return "claim_issue", reasons


def render_text(report: dict[str, Any]) -> str:
    lines = [
        f"policy.ai_contribution={report['policy']['ai_contribution']}",
        "archetypes=" + ",".join(row["name"] for row in report["archetypes"]),
        f"collision.type={report['collision']['type']}",
        f"mode={report['mode']}",
    ]
    if report["reasons"]:
        lines.append("reasons=" + ",".join(report["reasons"]))
    memo = report.get("collision_memo")
    if memo:
        lines.append(f"collision_memo.should_comment={str(memo['should_comment']).lower()}")
        lines.append(f"collision_memo.status={memo['status']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline repository-aware contribution preflight")
    parser.add_argument("root", type=Path)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--tracker", type=Path, required=True)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--record", action="store_true", help="persist the top verified collision fingerprint")
    parser.add_argument("--threshold", type=float, default=0.45)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    candidate = load_json(args.candidate)
    tracker_raw = load_json(args.tracker)
    if not isinstance(candidate, dict):
        raise SystemExit("candidate must be a JSON object")
    if not isinstance(tracker_raw, list):
        raise SystemExit("tracker must be a JSON array")
    if len(tracker_raw) > MAX_TRACKER_ITEMS:
        raise SystemExit(f"tracker has {len(tracker_raw)} items; cap is {MAX_TRACKER_ITEMS}")

    docs = policy_documents(root)
    policy = classify_policy(root, docs)
    archetypes = classify_archetypes(root, docs, policy)
    collision = collision_report(candidate, tracker_raw, args.threshold)
    state = load_state(args.state)

    memo = None
    top = collision["related_work"][0] if collision["related_work"] else None
    if top and collision["type"] in {"hard", "resolved_but_open"}:
        fingerprint = collision_fingerprint(candidate, top)
        already = fingerprint in state["collision_fingerprints"]
        should_comment = (
            not already
            and not collision["thread_already_links_work"]
            and collision["confidence"] == "verified"
            and policy["ai_contribution"] not in {"prohibited", "unclear"}
        )
        memo = {
            "fingerprint": fingerprint,
            "should_comment": should_comment,
            "status": "already_recorded" if already else "new",
            "target": top.get("url") or top.get("number"),
        }
        if args.record and args.state and not already:
            values = sorted(set(state["collision_fingerprints"] + [fingerprint]))
            args.state.parent.mkdir(parents=True, exist_ok=True)
            args.state.write_text(
                json.dumps({"collision_fingerprints": values}, indent=2) + "\n",
                encoding="utf-8",
            )

    mode, reasons = choose_mode(candidate, policy, collision)
    report = {
        "policy": policy,
        "archetypes": archetypes,
        "collision": collision,
        "collision_memo": memo,
        "mode": mode,
        "reasons": reasons,
        "public_action_allowed": mode not in {"drop", "watch"},
    }

    if args.json:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
