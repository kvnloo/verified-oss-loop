"""Independent exact-head verification and builder-claim assessment. Stdlib only.

A builder's exit code and prose are claims. Verification here means: a different principal checks
out the exact full candidate SHA in its own worktree, runs the project's test command itself, runs
the same command at the base as a failing control, checks the change stays inside the goal lock's
allowed paths, and passes the existing Verified OSS Loop receipt format gate
(``scripts/check-receipt.py``). Receipt-format success alone is never treated as verification.
"""
from __future__ import annotations

import fnmatch
import importlib.util
import json
import subprocess
import uuid
from pathlib import Path

from .ledger import FULL_SHA

ROOT = Path(__file__).resolve().parents[1]


def _git(repo: str | Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=check)


def _receipt_checker():
    spec = importlib.util.spec_from_file_location("vol_check_receipt", ROOT / "scripts" / "check-receipt.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("scripts/check-receipt.py not found")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def assess_builder(observation: dict, test_markers: list[str]) -> list[str]:
    """Flag builder claims the builder's own native evidence contradicts.

    ``observation`` is the adapter's parsed stream: ``exit_code`` and ``tool_runs`` (each with
    ``command``/``exit_code``/``is_error``). A zero exit whose last test run failed is a fabricated
    success, whatever the final prose says."""
    problems = []
    runs = [r for r in observation.get("tool_runs", [])
            if any(m in str(r.get("command") or "") for m in test_markers)]
    if observation.get("exit_code") == 0 and runs:
        last = runs[-1]
        if last.get("exit_code") not in (0, None) or last.get("is_error"):
            problems.append("claimed_success_with_failing_tests")
    if observation.get("exit_code") == 0 and not observation.get("terminal"):
        problems.append("no_terminal_result")
    return problems


def _run_tests(cwd: Path, test_cmd: list[str], timeout: float, log: Path) -> int:
    try:
        proc = subprocess.run(test_cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        code, out = proc.returncode, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as exc:
        code, out = 124, f"timeout after {timeout}s\n{exc.stdout or ''}{exc.stderr or ''}"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(f"$ {' '.join(test_cmd)}\n# cwd={cwd.name} exit={code}\n{out}")
    return code


def _allowed(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, p) or path == p for p in patterns)


def verify_exact_head(*, repo: str | Path, issue: str, base: str, head: str, test_cmd: list[str],
                      work_root: str | Path, allowed_paths: list[str] | None = None,
                      require_red: bool = True, timeout: float = 300) -> dict:
    """Run the verifier role at the exact candidate head. Returns a SPEC section 5 verdict record."""
    work_root = Path(work_root)
    reasons: list[str] = []
    verdict = {"verdict": "CHANGES_REQUIRED", "head_revision": str(head).lower(), "base_revision": base,
               "reasons": reasons, "tests": {}, "changed_files": []}
    head = str(head).lower()
    # GUARD:verifier-full-sha -- tests at a prefix or another revision are not evidence for this head.
    if not FULL_SHA.match(head):
        reasons.append("head_not_full_sha")
        return verdict
    if _git(repo, "cat-file", "-e", f"{head}^{{commit}}", check=False).returncode != 0:
        reasons.append("head_not_found")
        return verdict
    tag = uuid.uuid4().hex[:8]
    green_dir, red_dir = work_root / f"verify-head-{tag}", work_root / f"verify-base-{tag}"
    try:
        _git(repo, "worktree", "add", "--detach", str(green_dir), head)
        checked_out = _git(green_dir, "rev-parse", "HEAD").stdout.strip()
        verdict["checked_out"] = checked_out
        if checked_out != head:
            reasons.append("checkout_mismatch")
            return verdict
        changed = [p for p in _git(repo, "diff", "--name-only", base, head).stdout.splitlines() if p]
        verdict["changed_files"] = changed
        if not changed:
            reasons.append("no_change")
        if allowed_paths:
            outside = [p for p in changed if not _allowed(p, allowed_paths)]
            if outside:
                reasons.append("out_of_scope_change:" + ",".join(outside))
        logs = work_root / f"logs-{tag}"
        # GUARD:verifier-reruns -- the verdict comes from this run, never from the builder's exit code.
        green = _run_tests(green_dir, test_cmd, timeout, logs / "green.log")
        verdict["tests"]["green"] = {"command": " ".join(test_cmd), "exit_code": green, "log": str(logs / "green.log")}
        if green != 0:
            reasons.append("tests_fail_at_head")
        if require_red:
            _git(repo, "worktree", "add", "--detach", str(red_dir), base)
            red = _run_tests(red_dir, test_cmd, timeout, logs / "red.log")
            verdict["tests"]["red"] = {"command": " ".join(test_cmd), "exit_code": red, "log": str(logs / "red.log")}
            if red == 0:
                reasons.append("red_control_passed_at_base")
        receipt = render_receipt(issue=issue, base=base, head=head, changed=changed, tests=verdict["tests"])
        verdict["receipt_errors"] = _receipt_checker().check(receipt, expected_head=head)
        if verdict["receipt_errors"]:
            reasons.append("receipt_format")
        if not reasons:
            verdict["verdict"] = "APPROVE_EXACT_HEAD"
        return verdict
    finally:
        for d in (green_dir, red_dir):
            if d.exists():
                _git(repo, "worktree", "remove", "--force", str(d), check=False)


def render_receipt(*, issue: str, base: str, head: str, changed: list[str], tests: dict) -> str:
    """A SPEC section 4 receipt carrying the verifier's own commands and exits."""
    red = tests.get("red") or {}
    green = tests.get("green") or {}
    return "\n".join([
        "```yaml",
        f"issue: {issue}",
        f"base_revision: {base}",
        f"head_revision: {head}",
        f"changed_files: {json.dumps(changed)}",
        "tests:",
        f"  red: {red.get('command', '')} # exit {red.get('exit_code', 'not run')} at base",
        f"  green: {green.get('command', '')} # exit {green.get('exit_code', 'not run')} at head",
        "runtime_evidence: []",
        "limitations: [verifier-local execution; not CI]",
        "ai_assistance: factory-runtime",
        "```",
    ])
