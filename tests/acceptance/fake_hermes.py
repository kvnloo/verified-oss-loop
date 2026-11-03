#!/usr/bin/env python3
"""Offline stand-in for ``hermes chat --format stream-json`` used by the acceptance tests.

Accepts the adapter's real argv shape, emits the same JSONL event types Hermes emits
(``system/init``, ``tool_use``, ``tool_result``, ``result``) and the ``Session: <id>`` stderr line,
and records each invocation to $FAKE_HERMES_LOG so tests can count submissions.

FAKE_HERMES_MODE: fix (default) | fabricate | cheat | hang | slow
FAKE_HERMES_FIXES: JSON {"file": ["old", "new"], ...}; the first file present in --in is edited.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path


def emit(obj: dict) -> None:
    sys.stdout.write(json.dumps({**obj, "timestamp": int(time.time() * 1000)}) + "\n")
    sys.stdout.flush()


def arg(argv: list[str], flag: str) -> str | None:
    return argv[argv.index(flag) + 1] if flag in argv else None


def main() -> int:
    argv = sys.argv[1:]
    if "--yolo" in argv or "chat" not in argv:
        print("fake hermes: refused argv", file=sys.stderr)
        return 2
    workdir = Path(arg(argv, "--in") or ".")
    query = Path(arg(argv, "--query-file")).read_text()
    intent = (re.search(r"factory-intent: (\S+)", query) or [None, None])[1]
    mode = os.environ.get("FAKE_HERMES_MODE", "fix")
    sid = "local-fake-" + uuid.uuid4().hex
    with open(os.environ["FAKE_HERMES_LOG"], "a") as fh:
        fh.write(json.dumps({"session_id": sid, "intent": intent, "in": str(workdir), "pid": os.getpid(),
                             "profile": arg(argv, "-p"), "provider": arg(argv, "--provider"),
                             "model": arg(argv, "-m"), "mode": mode}) + "\n")
    emit({"type": "system", "subtype": "init", "model": arg(argv, "-m"), "session_id": ""})
    print(f"Session: {sid}", file=sys.stderr, flush=True)
    if mode == "hang":
        time.sleep(float(os.environ.get("FAKE_HERMES_SLEEP", "300")))
    if mode == "slow":
        time.sleep(float(os.environ.get("FAKE_HERMES_SLEEP", "1")))
    fixes = json.loads(os.environ.get("FAKE_HERMES_FIXES", "{}"))
    target = next((f for f in fixes if (workdir / f).exists()), None)
    if target:
        path = workdir / target
        old, new = fixes[target]
        if mode == "fabricate":
            path.write_text(path.read_text() + "\n# looked at this\n")
        elif mode == "cheat":
            test = next(workdir.glob("test_*.py"))
            test.write_text(re.sub(r"self\.assert\w+\(.*\)", "self.assertTrue(True)", test.read_text()))
        else:
            path.write_text(path.read_text().replace(old, new))
    cmd = "python3 -m unittest -q"
    emit({"type": "tool_use", "name": "terminal", "tool_call_id": "call-1", "input": {"command": cmd}})
    proc = subprocess.run(cmd.split(), cwd=workdir, capture_output=True, text=True)
    emit({"type": "tool_result", "name": "terminal", "tool_call_id": "call-1", "duration_ms": 10,
          "output": json.dumps({"output": (proc.stdout + proc.stderr)[-2000:], "exit_code": proc.returncode}),
          "is_error": proc.returncode != 0})
    emit({"type": "result", "session_id": sid, "exit_code": 0, "text": "Fixed; all tests pass.",
          "tokens": {"input": 10, "output": 5, "total": 15, "cache_read": 0, "cache_write": 0}, "duration_ms": 5})
    print(f"\nsession_id: {sid}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
