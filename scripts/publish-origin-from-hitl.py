#!/usr/bin/env python3
"""Open a GitHub parent PR from a Linear Maintainer Review fork PR.

Never merges. Non-fork and plugin repos fail closed. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any

GITHUB_PR_RE = re.compile(
    r"https://github\.com/([^/\s]+)/([^/\s]+)/pull/(\d+)",
    re.I,
)
PLUGIN_NAME_RE = re.compile(
    r"(^|/)(cursor-plugin|pstack-plugin|marketplace-plugin|claude-plugin)s?(/|$)",
    re.I,
)
PLUGIN_TOPICS = frozenset(
    {
        "cursor-plugin",
        "claude-plugin",
        "claude-code-plugin",
        "codex-plugin",
        "opencode-plugin",
    }
)
TEAM_NUMBER_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]*)-(\d+)$")
MAINTAINER_REVIEW = "maintainer review"
EXIT_NEVER_MERGE = 2
SCAN_FIRST = 50
DISPATCH_ID_KEYS = ("linear_issue", "identifier", "issue", "issueId", "issue_id")

LINEAR_ISSUE_QUERY = """
query ($id: String!) {
  issue(id: $id) {
    id
    identifier
    title
    url
    description
    state { name }
    attachments { nodes { url title } }
  }
}
"""

LINEAR_IDENTIFIER_QUERY = """
query ($team: String!, $number: Float!) {
  issues(filter: { team: { key: { eq: $team } }, number: { eq: $number } }, first: 1) {
    nodes { id identifier title url description state { name } attachments { nodes { url title } } }
  }
}
"""

LINEAR_SCAN_QUERY = """
query ($first: Int!) {
  issues(filter: { state: { name: { eq: "Maintainer Review" } } }, first: $first) {
    nodes { id identifier title url description state { name } attachments { nodes { url title } } }
  }
}
"""


class FailClosed(SystemExit):
    """Refuse origin publish. Exit 1 so CI/automation stops."""


def never_merge(reason: str = "workers never merge main/dev; this script never merges") -> None:
    print(f"refuse --merge: {reason}", file=sys.stderr)
    raise SystemExit(EXIT_NEVER_MERGE)


def looks_like_uuid(ident: str) -> bool:
    s = (ident or "").strip()
    return "-" in s and len(s) >= 32


def parse_linear_identifier(ident: str) -> tuple[str, int] | None:
    """TEAM-NUMBER (PER-1) → (PER, 1). UUID / other strings → None."""
    m = TEAM_NUMBER_RE.fullmatch((ident or "").strip())
    if not m:
        return None
    return m.group(1).upper(), int(m.group(2))


def maintainer_review_scan_query() -> str:
    return LINEAR_SCAN_QUERY


def looks_like_plugin(full_name: str, topics: list[str] | None = None) -> bool:
    name = (full_name or "").strip().lower()
    if PLUGIN_NAME_RE.search(name):
        return True
    if "/cursor-plugins/" in name or name.endswith("-cursor-plugin"):
        return True
    for topic in topics or []:
        if str(topic).strip().lower() in PLUGIN_TOPICS:
            return True
    return False


def require_fork_parent(repo: dict[str, Any]) -> str:
    """Return parent full_name or fail closed."""
    full_name = str(repo.get("full_name") or repo.get("nameWithOwner") or "")
    topics = repo.get("topics") if isinstance(repo.get("topics"), list) else []
    if looks_like_plugin(full_name, topics):
        raise FailClosed(f"plugin repo fail closed: {full_name or 'unknown'}")
    if not repo.get("fork"):
        raise FailClosed(f"non-fork repo fail closed: {full_name or 'unknown'}")
    parent = repo.get("parent") if isinstance(repo.get("parent"), dict) else {}
    parent_name = str(parent.get("full_name") or "").strip()
    if not parent_name:
        raise FailClosed(f"fork missing parent: {full_name or 'unknown'}")
    if looks_like_plugin(parent_name, parent.get("topics") if isinstance(parent.get("topics"), list) else []):
        raise FailClosed(f"plugin parent fail closed: {parent_name}")
    return parent_name


def parse_github_pr_url(url: str) -> tuple[str, str, int] | None:
    m = GITHUB_PR_RE.search(url or "")
    if not m:
        return None
    owner, repo, num = m.group(1), m.group(2), int(m.group(3))
    repo = repo.removesuffix(".git")
    return owner, repo, num


def collect_pr_urls(*texts: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for text in texts:
        if not text:
            continue
        for m in GITHUB_PR_RE.finditer(text):
            url = f"https://github.com/{m.group(1)}/{m.group(2)}/pull/{m.group(3)}"
            key = url.lower()
            if key not in seen:
                seen.add(key)
                found.append(url)
    return found


def issue_is_maintainer_review(issue: dict[str, Any]) -> bool:
    state = issue.get("state") if isinstance(issue.get("state"), dict) else {}
    name = str(state.get("name") or issue.get("state") or "").strip().lower()
    return name == MAINTAINER_REVIEW


def attachment_urls(issue: dict[str, Any]) -> list[str]:
    attachments = issue.get("attachments") or {}
    nodes: list[Any]
    if isinstance(attachments, dict):
        nodes = attachments.get("nodes") or attachments.get("edges") or []
    elif isinstance(attachments, list):
        nodes = attachments
    else:
        nodes = []
    urls: list[str] = []
    for node in nodes:
        if isinstance(node, dict) and "node" in node and isinstance(node["node"], dict):
            node = node["node"]
        if not isinstance(node, dict):
            continue
        url = str(node.get("url") or "")
        if url:
            urls.append(url)
    return urls


def pr_repo_number(pr: dict[str, Any]) -> tuple[str, str, int]:
    parsed = parse_github_pr_url(str(pr.get("html_url") or pr.get("url") or ""))
    if parsed:
        return parsed
    base = pr.get("base") if isinstance(pr.get("base"), dict) else {}
    repo = base.get("repo") if isinstance(base.get("repo"), dict) else {}
    full = str(repo.get("full_name") or "")
    number = pr.get("number")
    if "/" in full and number is not None:
        owner, name = full.split("/", 1)
        return owner, name, int(number)
    raise FailClosed("cannot locate pull request owner/repo/number")


def plan_origin_pr(pr: dict[str, Any], head_repo: dict[str, Any]) -> dict[str, Any]:
    parent = require_fork_parent(head_repo)
    head_owner = ""
    owner = head_repo.get("owner")
    if isinstance(owner, dict):
        head_owner = str(owner.get("login") or "")
    if not head_owner:
        head_owner = str(head_repo.get("full_name") or "").split("/", 1)[0]
    head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
    head_ref = str(head.get("ref") or pr.get("head_ref") or "")
    if not head_owner or not head_ref:
        raise FailClosed("fork PR missing head owner/ref")
    base_repo = pr.get("base") if isinstance(pr.get("base"), dict) else {}
    base_full = ""
    if isinstance(base_repo.get("repo"), dict):
        base_full = str(base_repo["repo"].get("full_name") or "")
    elif pr.get("base_repo"):
        base_full = str(pr.get("base_repo") or "")
    already = base_full.lower() == parent.lower()
    parent_owner, parent_repo = parent.split("/", 1)
    pr_owner, pr_name, pr_number = pr_repo_number(pr)
    return {
        "origin_repo": parent,
        "origin_owner": parent_owner,
        "origin_name": parent_repo,
        "head": f"{head_owner}:{head_ref}",
        "title": str(pr.get("title") or "").strip() or "origin PR from HITL fork",
        "body": str(pr.get("body") or ""),
        "draft": False,
        "fork_draft": bool(pr.get("draft")),
        "already_on_origin": already,
        "html_url": str(pr.get("html_url") or ""),
        "number": pr.get("number"),
        "pr_owner": pr_owner,
        "pr_name": pr_name,
        "pr_number": pr_number,
    }


def _scalar_id(val: Any) -> str | None:
    if isinstance(val, str) and val.strip():
        return val.strip()
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return str(int(val)) if float(val).is_integer() else str(val)
    return None


def _id_from_mapping(obj: dict[str, Any]) -> str | None:
    for key in DISPATCH_ID_KEYS:
        found = _scalar_id(obj.get(key))
        if found:
            return found
    data = obj.get("data") if isinstance(obj.get("data"), dict) else {}
    for key in ("linear_issue", "identifier", "id"):
        found = _scalar_id(data.get(key))
        if found:
            return found
    issue = obj.get("issue") if isinstance(obj.get("issue"), dict) else {}
    for key in ("linear_issue", "identifier", "id"):
        found = _scalar_id(issue.get(key))
        if found:
            return found
    return None


def issue_id_from_dispatch(event: dict[str, Any]) -> str:
    payload: dict[str, Any]
    if isinstance(event.get("client_payload"), dict):
        payload = event["client_payload"]
    elif isinstance(event.get("clientPayload"), dict):
        payload = event["clientPayload"]
    else:
        payload = event
    for obj in (payload, event):
        if not isinstance(obj, dict):
            continue
        found = _id_from_mapping(obj)
        if found:
            return found
    raise FailClosed("dispatch payload missing Linear issue id")


def _http_json(
    url: str,
    *,
    token: str | None,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    github: bool = False,
) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "Accept": "application/vnd.github+json" if github else "application/json",
        "User-Agent": "verified-oss-loop-hitl-origin-publish",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise FailClosed(f"http {exc.code} {url.split('?', 1)[0]}: {detail}") from exc


def github_json(path: str, token: str, *, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    return _http_json(f"https://api.github.com{path}", token=token, method=method, body=body, github=True)


def linear_graphql(api_key: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    data = _http_json(
        "https://api.linear.app/graphql",
        token=api_key,
        method="POST",
        body={"query": query, "variables": variables},
    )
    if not isinstance(data, dict):
        raise FailClosed("linear graphql returned non-object")
    if data.get("errors"):
        raise FailClosed(f"linear graphql error: {data['errors']}")
    inner = data.get("data")
    if not isinstance(inner, dict):
        raise FailClosed("linear graphql missing data")
    return inner


def linear_issue(issue_id: str, api_key: str) -> dict[str, Any]:
    ident = issue_id.strip()
    parsed = parse_linear_identifier(ident)
    if parsed is not None and not looks_like_uuid(ident):
        team, number = parsed
        inner = linear_graphql(
            api_key,
            LINEAR_IDENTIFIER_QUERY,
            {"team": team, "number": float(number)},
        )
        issues = inner.get("issues") if isinstance(inner.get("issues"), dict) else {}
        nodes = issues.get("nodes") if isinstance(issues, dict) else []
        if not isinstance(nodes, list) or not nodes or not isinstance(nodes[0], dict):
            raise FailClosed(f"linear issue not found: {ident}")
        return nodes[0]
    inner = linear_graphql(api_key, LINEAR_ISSUE_QUERY, {"id": ident})
    issue = inner.get("issue")
    if not isinstance(issue, dict):
        raise FailClosed(f"linear issue not found: {ident}")
    return issue


def list_maintainer_review_issues(api_key: str, first: int = SCAN_FIRST) -> list[dict[str, Any]]:
    inner = linear_graphql(api_key, maintainer_review_scan_query(), {"first": first})
    issues = inner.get("issues") if isinstance(inner.get("issues"), dict) else {}
    nodes = issues.get("nodes") if isinstance(issues, dict) else []
    if not isinstance(nodes, list):
        raise FailClosed("linear Maintainer Review scan returned no nodes")
    out: list[dict[str, Any]] = []
    for node in nodes:
        if isinstance(node, dict):
            out.append(node)
    return out


def existing_origin_pr(token: str, origin_repo: str, head: str) -> dict[str, Any] | None:
    owner, name = origin_repo.split("/", 1)
    pulls = github_json(
        f"/repos/{owner}/{name}/pulls?state=open&head={head}",
        token,
    )
    if isinstance(pulls, list):
        for pr in pulls:
            if isinstance(pr, dict) and pr.get("html_url"):
                return pr
    return None


def undraft_pr(token: str, owner: str, name: str, number: int) -> None:
    github_json(
        f"/repos/{owner}/{name}/pulls/{number}",
        token,
        method="PATCH",
        body={"draft": False},
    )


def create_origin_pr(plan: dict[str, Any], token: str) -> str:
    if plan.get("fork_draft"):
        undraft_pr(token, str(plan["pr_owner"]), str(plan["pr_name"]), int(plan["pr_number"]))
    if plan.get("already_on_origin") and plan.get("html_url"):
        print(f"already on origin: {plan['html_url']}")
        return str(plan["html_url"])
    existing = existing_origin_pr(token, str(plan["origin_repo"]), str(plan["head"]))
    if existing:
        if existing.get("draft"):
            owner, name, number = pr_repo_number(existing)
            undraft_pr(token, owner, name, number)
        url = str(existing["html_url"])
        print(f"origin PR already open: {url}")
        return url
    parent = github_json(f"/repos/{plan['origin_owner']}/{plan['origin_name']}", token)
    base = "main"
    if isinstance(parent, dict) and parent.get("default_branch"):
        base = str(parent["default_branch"])
    body = github_json(
        f"/repos/{plan['origin_owner']}/{plan['origin_name']}/pulls",
        token,
        method="POST",
        body={
            "title": plan["title"],
            "head": plan["head"],
            "base": base,
            "body": plan["body"],
            "draft": False,
            "maintainer_can_modify": True,
        },
    )
    url = str(body.get("html_url") or "")
    if not url:
        raise FailClosed(f"origin PR create returned no html_url: {body}")
    if body.get("draft"):
        owner, name, number = pr_repo_number(body)
        undraft_pr(token, owner, name, number)
    print(url)
    return url


def publish_loaded_issue(issue: dict[str, Any], github_token: str) -> str:
    ident = str(issue.get("identifier") or issue.get("id") or "unknown")
    if not issue_is_maintainer_review(issue):
        state = issue.get("state") if isinstance(issue.get("state"), dict) else {}
        raise FailClosed(
            f"{ident} is not Maintainer Review (state={state.get('name') or 'unknown'})"
        )
    urls = collect_pr_urls(*attachment_urls(issue), str(issue.get("description") or ""))
    if not urls:
        raise FailClosed(f"{ident} has no attached GitHub PR")
    last_err: Exception | None = None
    for url in urls:
        parsed = parse_github_pr_url(url)
        if parsed is None:
            continue
        owner, repo, number = parsed
        try:
            pr = github_json(f"/repos/{owner}/{repo}/pulls/{number}", github_token)
            head_repo = pr.get("head", {}).get("repo") if isinstance(pr.get("head"), dict) else None
            if not isinstance(head_repo, dict):
                head_repo = github_json(f"/repos/{owner}/{repo}", github_token)
            plan = plan_origin_pr(pr, head_repo)
            return create_origin_pr(plan, github_token)
        except FailClosed as exc:
            last_err = exc
            continue
    if last_err:
        raise last_err
    raise FailClosed(f"{ident} attached PRs failed closed")


def publish_issue(issue_id: str, *, github_token: str, linear_key: str) -> str:
    issue = linear_issue(issue_id, linear_key)
    return publish_loaded_issue(issue, github_token)


def scan_maintainer_review(*, github_token: str, linear_key: str) -> int:
    issues = list_maintainer_review_issues(linear_key, SCAN_FIRST)
    failed = 0
    for issue in issues:
        ident = str(issue.get("identifier") or issue.get("id") or "?")
        try:
            url = publish_loaded_issue(issue, github_token)
            print(f"{ident}: {url}")
        except FailClosed as exc:
            print(f"fail closed {ident}: {exc}", file=sys.stderr)
            failed += 1
    if failed:
        print(f"scan: {failed}/{len(issues)} failed", file=sys.stderr)
        return 1
    print(f"scan: {len(issues)} ok")
    return 0


def self_test() -> None:
    fork_repo = {
        "full_name": "kvnloo/hermes-agent",
        "fork": True,
        "owner": {"login": "kvnloo"},
        "parent": {"full_name": "NousResearch/hermes-agent"},
        "topics": [],
    }
    pr = {
        "title": "fix: example",
        "body": "receipt",
        "draft": False,
        "html_url": "https://github.com/kvnloo/hermes-agent/pull/99",
        "number": 99,
        "head": {"ref": "cursor/example", "repo": fork_repo},
        "base": {"repo": {"full_name": "kvnloo/hermes-agent"}},
    }
    plan = plan_origin_pr(pr, fork_repo)
    assert plan["origin_repo"] == "NousResearch/hermes-agent"
    assert plan["head"] == "kvnloo:cursor/example"
    assert plan["already_on_origin"] is False
    assert plan["draft"] is False

    draft_pr = dict(pr)
    draft_pr["draft"] = True
    draft_plan = plan_origin_pr(draft_pr, fork_repo)
    assert draft_plan["fork_draft"] is True
    assert draft_plan["draft"] is False

    origin_pr = {
        "title": "already published",
        "body": "",
        "draft": False,
        "html_url": "https://github.com/NousResearch/hermes-agent/pull/12",
        "number": 12,
        "head": {"ref": "cursor/example", "repo": fork_repo},
        "base": {"repo": {"full_name": "NousResearch/hermes-agent"}},
    }
    origin_plan = plan_origin_pr(origin_pr, fork_repo)
    assert origin_plan["already_on_origin"] is True
    assert origin_plan["draft"] is False

    plugin = {
        "full_name": "kvnloo/pstack-plugin",
        "fork": False,
        "topics": ["cursor-plugin"],
    }
    try:
        require_fork_parent(plugin)
        raise AssertionError("plugin repo must fail closed")
    except FailClosed:
        pass

    non_fork = {"full_name": "kvnloo/verified-oss-loop", "fork": False, "topics": []}
    try:
        require_fork_parent(non_fork)
        raise AssertionError("non-fork repo must fail closed")
    except FailClosed:
        pass

    marketplace = {
        "full_name": "some-org/cursor-plugin-demo",
        "fork": True,
        "parent": {"full_name": "cursor/cursor-plugin-demo"},
        "topics": ["cursor-plugin"],
        "owner": {"login": "some-org"},
    }
    try:
        require_fork_parent(marketplace)
        raise AssertionError("plugin-topic fork must fail closed")
    except FailClosed:
        pass

    issue = {
        "identifier": "PER-1",
        "state": {"name": "Maintainer Review"},
        "attachments": {
            "nodes": [{"url": "https://github.com/kvnloo/hermes-agent/pull/99", "title": "PR"}]
        },
        "description": "",
    }
    assert issue_is_maintainer_review(issue)
    assert not issue_is_maintainer_review({"state": {"name": "Ready to Review"}})
    urls = collect_pr_urls(*attachment_urls(issue))
    assert urls == ["https://github.com/kvnloo/hermes-agent/pull/99"]

    event = {"client_payload": {"identifier": "PER-1358"}}
    assert issue_id_from_dispatch(event) == "PER-1358"
    nested = {"client_payload": {"data": {"identifier": "PER-2"}}}
    assert issue_id_from_dispatch(nested) == "PER-2"
    assert issue_id_from_dispatch({"client_payload": {"linear_issue": "PER-1358"}}) == "PER-1358"
    assert issue_id_from_dispatch({"linear_issue": "PER-3"}) == "PER-3"
    assert issue_id_from_dispatch({"client_payload": {}, "linear_issue": "PER-4"}) == "PER-4"
    try:
        issue_id_from_dispatch({"client_payload": {}})
        raise AssertionError("empty dispatch must fail closed")
    except FailClosed:
        pass

    assert parse_linear_identifier("PER-1") == ("PER", 1)
    assert parse_linear_identifier("PER-1358") == ("PER", 1358)
    assert parse_linear_identifier("dcc5f96a-5f02-4385-92c7-c4abfe8d27cf") is None
    assert looks_like_uuid("dcc5f96a-5f02-4385-92c7-c4abfe8d27cf")
    assert not looks_like_uuid("PER-1")

    scan_q = maintainer_review_scan_query()
    assert "Maintainer Review" in scan_q
    assert "first" in scan_q

    parsed = parse_github_pr_url("see https://github.com/kvnloo/hermes-agent/pull/10 extra")
    assert parsed == ("kvnloo", "hermes-agent", 10)

    print("self-test ok")


def require_secrets() -> tuple[str, str]:
    github_token = os.environ.get("HITL_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    linear_key = os.environ.get("LINEAR_API_KEY") or ""
    if not github_token:
        raise FailClosed("HITL_GITHUB_TOKEN is required")
    if not linear_key:
        raise FailClosed("LINEAR_API_KEY is required")
    return github_token, linear_key


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Open origin GitHub PRs from Linear Maintainer Review. Never merges."
    )
    parser.add_argument("--self-test", action="store_true", help="run fail-closed fixtures")
    parser.add_argument(
        "--merge",
        action="store_true",
        help="forbidden: this publisher never merges (always exit 2)",
    )
    parser.add_argument("--issue", help="Linear issue id (PER-123 or UUID)")
    parser.add_argument(
        "--dispatch",
        action="store_true",
        help="read GITHUB_EVENT_PATH / --payload for repository_dispatch",
    )
    parser.add_argument("--payload", help="path to GitHub event JSON")
    parser.add_argument(
        "--scan-maintainer-review",
        action="store_true",
        help="publish each Linear issue in Maintainer Review (first 50)",
    )
    args = parser.parse_args(argv)

    if args.merge:
        never_merge()

    if args.self_test:
        self_test()
        return 0

    github_token, linear_key = require_secrets()

    if args.scan_maintainer_review:
        return scan_maintainer_review(github_token=github_token, linear_key=linear_key)

    issue_id = args.issue

    if args.dispatch or args.payload or (not issue_id and os.environ.get("GITHUB_EVENT_PATH")):
        path = args.payload or os.environ.get("GITHUB_EVENT_PATH")
        if not path:
            raise FailClosed("dispatch mode needs GITHUB_EVENT_PATH or --payload")
        event = json.loads(open(path, encoding="utf-8").read())
        if not isinstance(event, dict):
            raise FailClosed("event payload must be a JSON object")
        issue_id = issue_id_from_dispatch(event)

    if not issue_id:
        parser.error("need --self-test, --issue, --dispatch, or --scan-maintainer-review")

    publish_issue(issue_id, github_token=github_token, linear_key=linear_key)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FailClosed as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
