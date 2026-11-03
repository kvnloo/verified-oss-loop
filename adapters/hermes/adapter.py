"""Hermes harness adapter: submit, observe, reconcile, cancel and collect one bounded attempt.

Execution truth is the native Hermes session. The adapter only:

1. refuses to start unless the configured lane is admitted (no provider substitution);
2. writes the submit intent to the ledger before launching ``hermes chat``;
3. launches ``hermes -p <profile> chat --query-file F --format stream-json --max-turns N
   --in <worktree> --provider P -m M --source tool`` inside an owned process scope with stdout/stderr
   redirected to durable files, so a crashed adapter loses nothing and reconcile can read them;
4. binds the native session id it reads back from the stream;
5. cancels through Hermes' native interrupt (when configured) and then the owned scope, and reads
   back that the process is gone;
6. turns the worktree into an immutable candidate commit and stores the parsed native evidence.

``--run-budget`` is not accepted by the gateway-backed ``hermes chat``; the run budget is the
profile's ``agent.run_budget_seconds`` plus this adapter's own wall-clock ceiling. ``--yolo`` and
other approval bypasses are refused.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

from runtime import admission
from runtime.ledger import Lease, Ledger

FORBIDDEN_ARGS = {"--yolo", "--accept-hooks", "-z", "--oneshot", "--safe-mode", "--api-key", "--worktree", "-w"}
SESSION_RE = re.compile(r"^(?:Session|session_id):\s*(\S+)\s*$", re.M)
CANDIDATE_AUTHOR = ("vol-factory builder", "builder@example.invalid")


def _crash_point(name: str) -> None:
    """Test hook: die abruptly at a named point, like a killed adapter process."""
    if os.environ.get("VOL_FACTORY_CRASH_AT") == name:
        os._exit(137)


def _write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _pid_alive(pid: int) -> bool:
    try:
        with open(f"/proc/{pid}/stat") as fh:
            return fh.read().rsplit(")", 1)[1].split()[0] not in ("Z", "X")
    except (FileNotFoundError, IndexError, ProcessLookupError):
        return False


class HermesAdapter:
    def __init__(self, cfg: dict, ledger: Ledger, state_dir: str | Path):
        self.cfg = cfg
        self.ledger = ledger
        self.state_dir = Path(state_dir)
        self._procs: dict[str, subprocess.Popen] = {}
        for key in ("profile", "provider", "model"):
            if not cfg.get(key):
                raise ValueError(f"hermes harness needs an explicit {key}")

    # -- launch -----------------------------------------------------------------------------

    def build_argv(self, query_file: Path, workdir: Path) -> list[str]:
        c = self.cfg
        binary = c.get("bin", ["hermes"])
        argv = [*([binary] if isinstance(binary, str) else binary), "-p", c["profile"], "chat",
                "--query-file", str(query_file), "--format", "stream-json",
                "--max-turns", str(int(c.get("max_turns", 30))), "--in", str(workdir),
                "--provider", c["provider"], "-m", c["model"], "--source", c.get("source", "tool"),
                *c.get("extra_args", [])]
        bad = FORBIDDEN_ARGS.intersection(argv)
        if bad:
            raise ValueError(f"refusing approval/credential bypass arguments: {sorted(bad)}")
        return argv

    def _isolation(self) -> str:
        mode = self.cfg.get("isolation", "auto")
        if mode != "auto":
            return mode
        if shutil.which("systemd-run") and subprocess.run(["systemctl", "--user", "is-system-running"],
                                                           capture_output=True).returncode in (0, 1):
            return "systemd-scope"
        return "process-group"

    def _adir(self, attempt_id: str) -> Path:
        return self.state_dir / "attempts" / attempt_id

    def submit(self, lease: Lease, workdir: str | Path, prompt: str, admission_doc: dict | None,
               session_wait_s: float = 60) -> dict:
        """Admission → durable intent → launch → bind native session. Returns attempt state."""
        lane = self.cfg.get("lane", self.cfg["provider"])
        decision = admission.decide(admission_doc, lane)
        # GUARD:no-substitution -- a held lane blocks; nothing else is tried.
        if decision["decision"] != "allow":
            self.ledger.hold(lease.task_id, lease.role, decision["reason"], decision["resume_trigger"])
            return {"state": "held", **decision}
        native = {"harness": "hermes", "profile": self.cfg["profile"], "provider": self.cfg["provider"],
                  "model": self.cfg["model"], "lane": lane}
        attempt_id, intent = self.ledger.begin_submit(lease, native)
        adir = self._adir(attempt_id)
        adir.mkdir(parents=True, exist_ok=True)
        qf = adir / "query.md"
        qf.write_text(f"<!-- factory-intent: {intent} -->\n{prompt}\n")
        workdir = Path(workdir).resolve()
        argv = self.build_argv(qf, workdir)
        mode = self._isolation()
        unit = f"vol-attempt-{attempt_id}"
        launch_argv = argv
        if mode == "systemd-scope":
            props = [x for p in self.cfg.get("scope_properties", []) for x in ("-p", p)]
            launch_argv = ["systemd-run", "--user", "--scope", "--quiet", "--collect", "--unit", unit, *props, "--", *argv]
        out = open(adir / "stream.jsonl", "ab")
        err = open(adir / "stderr.txt", "ab")
        proc = subprocess.Popen(launch_argv, stdin=subprocess.DEVNULL, stdout=out, stderr=err, cwd=workdir,
                                start_new_session=True)
        out.close()
        err.close()
        self._procs[attempt_id] = proc
        _write_json(adir / "launch.json", {"pid": proc.pid, "pgid": proc.pid, "isolation": mode,
                                           "unit": unit if mode == "systemd-scope" else None,
                                           "argv": argv, "intent": intent, "workdir": str(workdir),
                                           "started_at": time.time()})
        _crash_point("after_launch")
        deadline = time.time() + session_wait_s
        while time.time() < deadline:
            obs = self.observe(attempt_id)
            if obs["session_id"]:
                self.ledger.bind_native(attempt_id, obs["session_id"], {"unit": unit if mode == "systemd-scope" else None})
                break
            if not obs["alive"]:
                break
            time.sleep(0.2)
        else:
            self.ledger.mark_reconciling(attempt_id, "no native session id within wait")
        return {"state": self.ledger.attempt(attempt_id)["state"], "attempt_id": attempt_id}

    # -- observe ----------------------------------------------------------------------------

    def observe(self, attempt_id: str) -> dict:
        adir = self._adir(attempt_id)
        launch = json.loads((adir / "launch.json").read_text()) if (adir / "launch.json").exists() else {}
        events = []
        stream = adir / "stream.jsonl"
        if stream.exists():
            for line in stream.read_text(errors="replace").splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        stderr = (adir / "stderr.txt").read_text(errors="replace") if (adir / "stderr.txt").exists() else ""
        result = next((e for e in reversed(events) if e.get("type") == "result"), None)
        sid = (result or {}).get("session_id") or next(
            (e.get("session_id") for e in events if e.get("type") == "system" and e.get("session_id")), None)
        if not sid:
            m = SESSION_RE.search(stderr)
            sid = m.group(1) if m else None
        uses: dict[str, dict] = {}
        runs = []
        for e in events:
            if e.get("type") == "tool_use":
                uses[e.get("tool_call_id") or e.get("name")] = e
            elif e.get("type") == "tool_result":
                use = uses.pop(e.get("tool_call_id") or e.get("name"), {})
                code = None
                try:
                    parsed = json.loads(e.get("output") or "")
                    if isinstance(parsed, dict) and isinstance(parsed.get("exit_code"), int):
                        code = parsed["exit_code"]
                except json.JSONDecodeError:
                    pass
                runs.append({"tool": e.get("name"), "command": (use.get("input") or {}).get("command"),
                             "exit_code": code, "is_error": bool(e.get("is_error"))})
        proc = self._procs.get(attempt_id)
        if proc is not None:
            alive = proc.poll() is None
            returncode = proc.returncode
        else:
            alive = bool(launch.get("pid")) and _pid_alive(int(launch["pid"]))
            returncode = None
        return {"session_id": sid, "terminal": result is not None,
                "exit_code": (result or {}).get("exit_code"), "error": (result or {}).get("error"),
                "text": (result or {}).get("text"), "tokens": (result or {}).get("tokens"),
                "duration_ms": (result or {}).get("duration_ms"), "model": next(
                    (e.get("model") for e in events if e.get("type") == "system"), None),
                "tool_runs": runs, "alive": alive, "process_returncode": returncode,
                "launched": bool(launch), "unit": launch.get("unit"), "pid": launch.get("pid")}

    def wait(self, attempt_id: str, timeout: float) -> dict:
        """Wait for the native terminal result. On the adapter's wall-clock ceiling, cancel."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            obs = self.observe(attempt_id)
            if not obs["alive"]:
                obs["terminal_cause"] = "result" if obs["terminal"] else "exited_without_result"
                return obs
            time.sleep(0.5)
        readback = self.cancel(attempt_id, reason="adapter_wall_budget")
        obs = self.observe(attempt_id)
        obs["terminal_cause"] = "cancelled_budget"
        obs["cancel"] = readback
        return obs

    # -- recovery ---------------------------------------------------------------------------

    def reconcile(self, attempt_id: str) -> dict:
        """Recover an attempt whose submit outcome is unknown from durable native evidence.

        Never re-sends. A found session is bound; an unknown outcome stays ``reconciling``."""
        a = self.ledger.attempt(attempt_id)
        obs = self.observe(attempt_id)
        if obs["session_id"] and not a["session_id"]:
            self.ledger.bind_native(attempt_id, obs["session_id"], {"recovered_by": "reconcile"})
        elif not obs["session_id"] and a["state"] in ("authorized", "submitted"):
            self.ledger.mark_reconciling(attempt_id, "unknown_outcome" if not obs["launched"] else "launched_no_session")
        return {"attempt": self.ledger.attempt(attempt_id), "observation": obs}

    def cancel(self, attempt_id: str, reason: str) -> dict:
        """Native interrupt (if configured), then stop the owned scope/process group; read back."""
        obs = self.observe(attempt_id)
        out: dict = {"reason": reason, "native_interrupt": "not_configured"}
        icmd = self.cfg.get("interrupt_cmd")
        if icmd and obs["session_id"]:
            argv = [x.format(session_id=obs["session_id"], profile=self.cfg["profile"]) for x in icmd]
            r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
            out["native_interrupt"] = {"exit_code": r.returncode, "output": (r.stdout + r.stderr)[-2000:]}
            for _ in range(40):  # give the attached stream a chance to report the interrupted turn
                if not self.observe(attempt_id)["alive"]:
                    break
                time.sleep(0.25)
        unit, pid = obs.get("unit"), obs.get("pid")
        if unit:
            subprocess.run(["systemctl", "--user", "stop", f"{unit}.scope"], capture_output=True, timeout=60)
        elif pid and _pid_alive(int(pid)):
            try:
                os.killpg(int(pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
        for _ in range(40):
            proc = self._procs.get(attempt_id)
            if proc is not None:
                proc.poll()
            if not self.observe(attempt_id)["alive"]:
                break
            time.sleep(0.25)
        else:
            if pid:
                try:
                    os.killpg(int(pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
                time.sleep(0.5)
                if attempt_id in self._procs:
                    self._procs[attempt_id].poll()
        final = self.observe(attempt_id)
        scope_state = None
        if unit:
            scope_state = subprocess.run(["systemctl", "--user", "show", "-p", "ActiveState", "--value", f"{unit}.scope"],
                                         capture_output=True, text=True).stdout.strip()
        out.update(stopped=not final["alive"] and scope_state in (None, "", "inactive", "failed"),
                   pid=pid, pid_alive=final["alive"], unit=unit, scope_active_state=scope_state,
                   stream_terminal=final["terminal"], stream_error=final["error"])
        a = self.ledger.attempt(attempt_id)
        if out["stopped"] and a["state"] in ("authorized", "submitted", "reconciling"):
            self.ledger.revoke(attempt_id, out)
        return out

    # -- collect ----------------------------------------------------------------------------

    def collect(self, attempt_id: str, lease: Lease, workdir: str | Path, base: str, obs: dict,
                test_markers: list[str]) -> dict:
        """Freeze the worktree into a candidate commit and store the native evidence."""
        from runtime.verify import assess_builder
        wd = Path(workdir)
        git = ["git", "-C", str(wd)]
        if subprocess.run([*git, "status", "--porcelain"], capture_output=True, text=True).stdout.strip():
            env = {**os.environ, "GIT_AUTHOR_NAME": CANDIDATE_AUTHOR[0], "GIT_AUTHOR_EMAIL": CANDIDATE_AUTHOR[1],
                   "GIT_COMMITTER_NAME": CANDIDATE_AUTHOR[0], "GIT_COMMITTER_EMAIL": CANDIDATE_AUTHOR[1]}
            subprocess.run([*git, "add", "-A"], check=True, env=env)
            subprocess.run([*git, "commit", "-q", "-m", f"candidate: {lease.task_id} ({attempt_id})"], check=True, env=env)
        head = subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        claims = assess_builder(obs, test_markers)
        result = {"head_revision": head if head != base else None, "base_revision": base,
                  "terminal_cause": obs.get("terminal_cause"), "exit_code": obs.get("exit_code"),
                  "error": obs.get("error"), "tool_runs": obs.get("tool_runs", []), "builder_claim_problems": claims,
                  "tokens": obs.get("tokens"), "model_reported": obs.get("model"),
                  "logs": {"stream": str(self._adir(attempt_id) / "stream.jsonl"),
                           "stderr": str(self._adir(attempt_id) / "stderr.txt")}}
        return self.ledger.complete(attempt_id, lease, result)
