"""Config, idempotent apply, and the one-task pipeline (builder → independent verifier). Stdlib only."""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import admission
from .ledger import Lease, Ledger
from .verify import verify_exact_head

CONFIG_SCHEMA = "vol.factory-config/v0"


def load_config(path: str | Path) -> dict:
    cfg = json.loads(Path(path).read_text())
    if cfg.get("schema") != CONFIG_SCHEMA:
        raise ValueError(f"config schema must be {CONFIG_SCHEMA}")
    roster = cfg.get("roster", {})
    if set(roster) != {"builder", "verifier"}:
        raise ValueError("roster must define exactly the shared builder and verifier roles")
    if roster["builder"]["principal"] == roster["verifier"]["principal"]:
        raise ValueError("builder and verifier must be different principals")
    ids = [r["id"] for r in cfg.get("repos", [])]
    if len(ids) != len(set(ids)):
        raise ValueError("repo ids must be unique")
    return cfg


def resolve(home: Path, value: str) -> Path:
    p = Path(value).expanduser()
    return p if p.is_absolute() else home / p


def apply(home: str | Path, config: str | Path) -> list[str]:
    """Install a factory home from a config. Returns the changes made; [] means no-op."""
    home = Path(home).expanduser()
    cfg = load_config(config)
    changes: list[str] = []
    for d in (home, resolve(home, cfg.get("state_dir", "state")), resolve(home, cfg.get("work_dir", "work"))):
        if not d.exists():
            d.mkdir(parents=True)
            changes.append(f"mkdir {d}")
    target = home / "factory.json"
    rendered = json.dumps(cfg, indent=2, sort_keys=True) + "\n"
    if not target.exists() or target.read_text() != rendered:
        target.write_text(rendered)
        changes.append(f"write {target}")
    db = resolve(home, cfg.get("state_dir", "state")) / "ledger.sqlite"
    if not db.exists():
        Ledger(db)
        changes.append(f"init {db}")
    return changes


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def make_adapter(cfg: dict, ledger: Ledger, home: Path):
    harness = cfg["harnesses"][cfg["roster"]["builder"]["harness"]]
    if harness.get("kind") != "hermes":
        raise ValueError("only the hermes builder harness is implemented")
    from adapters.hermes.adapter import HermesAdapter
    return HermesAdapter(harness, ledger, resolve(home, cfg.get("state_dir", "state")))


@dataclass
class Prepared:
    cfg: dict
    repo_cfg: dict
    repo: Path
    work: Path
    ledger: Ledger
    task_id: str
    base: str
    goal: dict
    lease: Lease
    worktree: Path
    prompt: str


def prepare_builder(home: Path, repo_id: str, issue: str, objective: str, lease_ttl: float = 900,
                    ledger: Ledger | None = None) -> Prepared:
    """Freeze the task, take the shared builder role's lease and create its isolated worktree."""
    cfg = load_config(home / "factory.json")
    repo_cfg = next(r for r in cfg["repos"] if r["id"] == repo_id)
    repo = resolve(home, repo_cfg["path"])
    work = resolve(home, cfg.get("work_dir", "work"))
    ledger = ledger or Ledger(resolve(home, cfg.get("state_dir", "state")) / "ledger.sqlite")
    base = git(repo, "rev-parse", repo_cfg.get("base_ref", "HEAD"))
    task_id = f"{repo_id}#{issue}@{base[:12]}"
    goal = {"objective": objective, "allowed_paths": repo_cfg.get("allowed_paths", []),
            "test_cmd": repo_cfg["test_cmd"], "policy": repo_cfg.get("policy", "AGENTS.md")}
    ledger.register_task({"task_id": task_id, "repo": repo_id, "issue": issue, "base_revision": base, "goal_lock": goal})
    lease = ledger.acquire(task_id, "builder", cfg["roster"]["builder"]["principal"], lease_ttl)
    wt = work / f"{repo_id}-{issue}-b{lease.fence}"
    if wt.exists():
        shutil.rmtree(wt)
        git(repo, "worktree", "prune")
    git(repo, "worktree", "add", "-q", "-B", f"factory/{repo_id}-{issue}-f{lease.fence}", str(wt), base)
    prompt = (f"Repository task ({repo_id} issue {issue}): {objective}\n\n"
              f"Work only in this directory. Allowed paths: {', '.join(goal['allowed_paths']) or 'any'}. "
              f"Do not edit tests. Run `{' '.join(goal['test_cmd'])}` to check your fix, then stop. "
              "Do not push, open PRs or contact any remote.")
    return Prepared(cfg, repo_cfg, repo, work, ledger, task_id, base, goal, lease, wt, prompt)


def verify_builder(p: Prepared, home: Path, builder_attempt: str, head: str, lease_ttl: float = 900) -> dict:
    """The shared verifier role: its own lease, its own attempt, exact-head re-run."""
    principal = p.cfg["roster"]["verifier"]["principal"]
    vlease = p.ledger.acquire(p.task_id, "verifier", principal, lease_ttl)
    v_attempt, _ = p.ledger.begin_submit(vlease, {"harness": "local-exec", "principal": principal},
                                         verifies_attempt=builder_attempt)
    verdict = verify_exact_head(repo=p.repo, issue=p.task_id.split("#")[1].split("@")[0], base=p.base, head=head,
                                test_cmd=p.repo_cfg["test_cmd"], work_root=p.work,
                                allowed_paths=p.goal["allowed_paths"] or None)
    builder = p.ledger.record_verification(builder_attempt, v_attempt, vlease, verdict)
    p.ledger.release(vlease)
    return {"builder": builder, "verifier": {"attempt_id": v_attempt, **verdict}}


def run_task(home: str | Path, repo_id: str, issue: str, objective: str, *, lease_ttl: float = 900,
             wall_budget: float = 900, ledger: Ledger | None = None) -> dict:
    """Register → builder lease → admitted native submit → wait → candidate → verifier lease →
    exact-head independent verification. Never pushes, posts or merges."""
    home = Path(home).expanduser()
    p = prepare_builder(home, repo_id, issue, objective, lease_ttl, ledger)
    adapter = make_adapter(p.cfg, p.ledger, home)
    doc = admission.load(resolve(home, p.cfg.get("admission_file", "admission.json")))
    sub = adapter.submit(p.lease, p.worktree, p.prompt, doc)
    if sub["state"] == "held":
        return {"task_id": p.task_id, "builder": {"state": "held", **sub}, "verifier": None}
    attempt_id = sub["attempt_id"]
    obs = adapter.wait(attempt_id, wall_budget)
    lease = p.ledger.renew(p.lease, lease_ttl)
    markers = p.repo_cfg.get("test_markers") or [p.repo_cfg["test_cmd"][-1]]
    builder = adapter.collect(attempt_id, lease, p.worktree, p.base, obs, markers)
    p.ledger.release(lease)
    out = {"task_id": p.task_id, "builder": builder, "observation": obs, "verifier": None}
    if builder["head_revision"]:
        out.update(verify_builder(p, home, attempt_id, builder["head_revision"], lease_ttl))
    return out
