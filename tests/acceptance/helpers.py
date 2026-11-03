"""Fictional fixtures shared by the acceptance tests. No network, no real Hermes, no real profile."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FAKE = Path(__file__).with_name("fake_hermes.py")
AUTHOR = {"GIT_AUTHOR_NAME": "Fixture Author", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
          "GIT_COMMITTER_NAME": "Fixture Author", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
FIXES = {"calc.py": ["return a - b", "return a + b"], "strings.py": ["s.lower()", "s.upper()"]}
REPOS = {
    "alpha-calc": {"calc.py": "def add(a, b):\n    return a - b\n",
                   "test_calc.py": "import unittest\nfrom calc import add\n\n\nclass T(unittest.TestCase):\n"
                                   "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n"},
    "beta-strings": {"strings.py": "def shout(s):\n    return s.lower()\n",
                     "test_strings.py": "import unittest\nfrom strings import shout\n\n\nclass T(unittest.TestCase):\n"
                                        "    def test_shout(self):\n        self.assertEqual(shout('hi'), 'HI')\n"},
}


def git(repo: Path, *args: str) -> str:
    env = {**os.environ, **AUTHOR}
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True, env=env).stdout.strip()


def make_repo(path: Path, files: dict[str, str]) -> str:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    for name, body in files.items():
        (path / name).write_text(body)
    (path / "AGENTS.md").write_text("Fictional fixture repo. Fix code, never tests.\n")
    (path / ".gitignore").write_text("__pycache__/\n*.pyc\n")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "fixture: failing test")
    return git(path, "rev-parse", "HEAD")


def iso(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


class Home:
    """A fresh factory home with two fictional repos and the fake harness as the builder."""

    def __init__(self, lane_state: str = "available", admission_age: float = 0, extra_harness: bool = True):
        self.tmp = tempfile.TemporaryDirectory(prefix="vol-factory-")
        self.home = Path(self.tmp.name) / "home"
        self.log = Path(self.tmp.name) / "fake-invocations.jsonl"
        self.log.touch()
        src = Path(self.tmp.name) / "src"
        src.mkdir()
        repos = []
        for rid, files in REPOS.items():
            make_repo(self.home / "repos" / rid, files)
            repos.append({"id": rid, "path": f"repos/{rid}", "test_cmd": ["python3", "-m", "unittest", "-q"],
                          "test_markers": ["unittest"], "allowed_paths": [next(iter(files))]})
        harnesses = {"hermes-builder": {"kind": "hermes", "bin": [sys.executable, str(FAKE)], "profile": "factory-builder",
                                        "provider": "example-free", "model": "example/free-model", "lane": "example-free",
                                        "max_turns": 5, "isolation": "process-group"}}
        if extra_harness:  # an alternative lane that must never be used as a substitute
            harnesses["hermes-paid"] = {**harnesses["hermes-builder"], "provider": "example-paid", "lane": "example-paid"}
        self.config = {"schema": "vol.factory-config/v0", "state_dir": "state", "work_dir": "work",
                       "admission_file": "admission.json", "harnesses": harnesses,
                       "roster": {"builder": {"harness": "hermes-builder", "principal": "builder@factory.example"},
                                  "verifier": {"kind": "local-exec", "principal": "verifier@factory.example"}},
                       "repos": repos}
        cfg_path = src / "factory.json"
        cfg_path.write_text(json.dumps(self.config))
        from runtime import factory
        self.changes = factory.apply(self.home, cfg_path)
        self.cfg_path = cfg_path
        self.write_admission(lane_state, admission_age)

    def write_admission(self, lane_state: str, age: float = 0) -> None:
        doc = {"observed_at": iso(time.time() - age), "max_age_s": 900,
               "lanes": {"example-free": {"state": lane_state, "resume_trigger": "fictional pool resets at 00:00Z"},
                         "example-paid": {"state": "available"}}}
        (self.home / "admission.json").write_text(json.dumps(doc))

    def env(self, mode: str = "fix", **extra: str) -> dict:
        return {"FAKE_HERMES_LOG": str(self.log), "FAKE_HERMES_MODE": mode, "FAKE_HERMES_FIXES": json.dumps(FIXES), **extra}

    def invocations(self) -> list[dict]:
        return [json.loads(x) for x in self.log.read_text().splitlines() if x.strip()]

    def ledger(self):
        from runtime.ledger import Ledger
        return Ledger(self.home / "state" / "ledger.sqlite")

    def close(self) -> None:
        self.tmp.cleanup()


class EnvPatch:
    def __init__(self, values: dict):
        self.values, self.saved = values, {}

    def __enter__(self):
        for k, v in self.values.items():
            self.saved[k] = os.environ.get(k)
            os.environ[k] = v

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
