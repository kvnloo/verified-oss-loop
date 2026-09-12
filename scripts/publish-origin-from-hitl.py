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
MAINTAINER_REVIEW = "maintainer review"
EXIT_NEVER_MERGE = 2

LINEAR_ISSUE_QUERY = """
query($id: String!) {
  issue(id: $id) {
    id
    identifier
    title
    url
    state { name }
    attachments {
      nodes { url title }
    }
    description
  }
}
"""


class FailClosed(SystemExit):
    """Refuse origin publish. Exit 1 so CI/automation stops."""


def never_merge(reason: str = "workers never merge main/dev; this script never merges") -> None:
    print(f"refuse --merge: {reason}", file=sys.stderr)
    raise SystemExit(EXIT_NEVER_MERGE)


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


def plan_origin_pr(pr: dict[str, Any], head_repo: dict[str, Any]) -> dict[str, Any]:
    parent = require_fork_parent(head_repo)
    head_owner = ""
    owner = head_repo.get("owner")
    if isinstance(owner, dict):
        head_owner = str(owner.get("login") or "")
    if not head_owner:
        head_owner = str(head_repo.get("full_name") or "").split("/", 1)[0]
    head_ref = ""
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
    return {
        "origin_repo": parent,
        "origin_owner": parent_owner,
        "origin_name": parent_repo,
        "head": f"{head_owner}:{head_ref}",
        "title": str(pr.get("title") or "").strip() or "origin PR from HITL fork",
        "body": str(pr.get("body") or ""),
        "draft": bool(pr.get("draft")),
        "already_on_origin": already,
        "html_url": str(pr.get("html_url") or ""),
        "number": pr.get("number"),
    }


def issue_id_from_dispatch(event: dict[str, Any]) -> str:
    payload = event.get("client_payload") if isinstance(event.get("client_payload"), dict) else {}
    if not payload and isinstance(event.get("clientPayload"), dict):
        payload = event["clientPayload"]
    for key in ("identifier", "issue", "issueId", "issue_id"):
        val = payload.get(key)
        if val:
            return str(val)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    if not data and isinstance(payload.get("issue"), dict):
        data = payload["issue"]
    for key in ("identifier", "id"):
        val = data.get(key)
        if val:
            return str(val)
    nested = event.get("issue") if isinstance(event.get("issue"), dict) else {}
    for key in ("identifier", "id"):
        val = nested.get(key)
        if val:
            return str(val)
    raise FailClosed("dispatch payload missing Linear issue id")


def _http_json(url: str, *, token: str | None, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "Accept": "application/json",
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
    return _http_json(f"https://api.github.com{path}", token=token, method=method, body=body)


def linear_issue(issue_id: str, api_key: str) -> dict[str, Any]:
    ident = issue_id.strip()
    payload = {"query": LINEAR_ISSUE_QUERY, "variables": {"id": ident}}
    data = _http_json("https://api.linear.app/graphql", token=api_key, method="POST", body=payload)
    if not isinstance(data, dict):
        raise FailClosed("linear graphql returned non-object")
    if data.get("errors"):
        raise FailClosed(f"linear graphql error: {data['errors']}")
    issue = (data.get("data") or {}).get("issue")
    if not isinstance(issue, dict):
        raise FailClosed(f"linear issue not found: {ident}")
    return issue


def existing_origin_pr(token: str, origin_repo: str, head: str) -> str | None:
    owner, name = origin_repo.split("/", 1)
    pulls = github_json(
        f"/repos/{owner}/{name}/pulls?state=open&head={head}",
        token,
    )
    if isinstance(pulls, list):
        for pr in pulls:
            if isinstance(pr, dict) and pr.get("html_url"):
                return str(pr["html_url"])
    return None


def create_origin_pr(plan: dict[str, Any], token: str) -> str:
    if plan.get("already_on_origin") and plan.get("html_url"):
        print(f"already on origin: {plan['html_url']}")
        return str(plan["html_url"])
    existing = existing_origin_pr(token, str(plan["origin_repo"]), str(plan["head"]))
    if existing:
        print(f"origin PR already open: {existing}")
        return existing
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
            "draft": bool(plan.get("draft")),
            "maintainer_can_modify": True,
        },
    )
    url = str(body.get("html_url") or "")
    if not url:
        raise FailClosed(f"origin PR create returned no html_url: {body}")
    print(url)
    return url


def publish_issue(issue_id: str, *, github_token: str, linear_key: str) -> str:
    issue = linear_issue(issue_id, linear_key)
    if not issue_is_maintainer_review(issue):
        state = issue.get("state") if isinstance(issue.get("state"), dict) else {}
        raise FailClosed(
            f"{issue.get('identifier') or issue_id} is not Maintainer Review "
            f"(state={state.get('name') or 'unknown'})"
        )
    urls = collect_pr_urls(*attachment_urls(issue), str(issue.get("description") or ""))
    if not urls:
        raise FailClosed(f"{issue.get('identifier') or issue_id} has no attached GitHub PR")
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
    raise FailClosed(f"{issue.get('identifier') or issue_id} attached PRs failed closed")


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
    try:
        issue_id_from_dispatch({"client_payload": {}})
        raise AssertionError("empty dispatch must fail closed")
    except FailClosed:
        pass

    parsed = parse_github_pr_url("see https://github.com/kvnloo/hermes-agent/pull/10 extra")
    assert parsed == ("kvnloo", "hermes-agent", 10)

    print("self-test ok")


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
    parser.add_argument("--issue", help="Linear issue id (PER-123)")
    parser.add_argument(
        "--dispatch",
        action="store_true",
        help="read GITHUB_EVENT_PATH / --payload for repository_dispatch",
    )
    parser.add_argument("--payload", help="path to GitHub event JSON")
    args = parser.parse_args(argv)

    if args.merge:
        never_merge()

    if args.self_test:
        self_test()
        return 0

    github_token = os.environ.get("HITL_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    linear_key = os.environ.get("LINEAR_API_KEY") or ""
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
        parser.error("need --self-test, --issue, or --dispatch")

    if not github_token:
        raise FailClosed("HITL_GITHUB_TOKEN is required")
    if not linear_key:
        raise FailClosed("LINEAR_API_KEY is required")

    publish_issue(issue_id, github_token=github_token, linear_key=linear_key)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FailClosed as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
