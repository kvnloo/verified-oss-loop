#!/usr/bin/env python3
"""Hermetic unit tests for kit-inventory decisions and CLI commands.

Run with: python3 tests/kit_inventory_decide.py -v
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import stat
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "kit-inventory.py"
SPEC = importlib.util.spec_from_file_location("kit_inventory", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
kit_inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(kit_inventory)


class KitInventoryDecideTests(unittest.TestCase):
    REL = "skills/x/SKILL.md"

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.sandbox = Path(temporary.name)
        self.root = self.sandbox / "repo"
        self.root.mkdir()
        self.incoming = self.sandbox / "incoming.txt"
        self.incoming.write_text("new kit\n", encoding="utf-8")
        self.dest = self.root / self.REL

    def _dest(self, content: str) -> None:
        self.dest.parent.mkdir(parents=True, exist_ok=True)
        self.dest.write_text(content, encoding="utf-8")

    def _inventory(self, source: str, sha256: str = "") -> None:
        data = kit_inventory.load_inventory(self.root)
        data["files"][self.REL] = {
            "path": self.REL,
            "source": source,
            "sha256": sha256,
            "kit_sha256": "",
        }
        kit_inventory.save_inventory(self.root, data)

    def _decide(self, *, force: bool = False, rel: str | None = None) -> tuple[bool, str, str]:
        return kit_inventory.decide(self.root, rel or self.REL, self.incoming, self.dest, force)

    def test_decide_local_never_written(self) -> None:
        self._inventory("local")
        self.assertEqual(self._decide(force=True), (False, "skip", "local"))
        self._dest("developer version\n")
        self.assertEqual(self._decide(force=True), (False, "skip", "local"))

    def test_decide_new_unchanged_force(self) -> None:
        self.assertEqual(self._decide(), (True, "write", "new"))
        self._dest("new kit\n")
        self.assertEqual(self._decide(), (False, "unchanged", "already current"))
        self._dest("developer version\n")
        self.assertEqual(self._decide(force=True), (True, "force", "force"))

    def test_decide_first_inventory_does_not_clobber(self) -> None:
        self._dest("developer version\n")
        self.assertEqual(self._decide(), (False, "skip", "modified"))

    def test_decide_kit_unmodified_updates(self) -> None:
        self._dest("previous kit\n")
        self._inventory("kit", sha256=kit_inventory.sha256_file(self.dest))
        self.assertEqual(
            self._decide(),
            (True, "update", "kit file unmodified since last sync"),
        )
        self._dest("local edit since sync\n")
        self.assertEqual(self._decide(), (False, "skip", "modified"))

    def test_decide_modified_reclaims_matching_kit(self) -> None:
        self._dest("new kit\n")
        self._inventory("modified", sha256="0" * 64)
        self.assertEqual(
            self._decide(),
            (True, "update", "matches new kit; reclaim"),
        )

    def test_decide_normalises_rel(self) -> None:
        self._inventory("local")
        self.assertEqual(
            self._decide(rel="./skills/x/SKILL.md"),
            (False, "skip", "local"),
        )

    def test_main_apply_writes_and_logs_session(self) -> None:
        session = self.sandbox / "session.jsonl"
        dest = self.root / "a" / "b.txt"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = kit_inventory.main([
                "apply", "--root", str(self.root), "--path", "a/b.txt",
                "--incoming", str(self.incoming), "--session", str(session),
                "--chmod", "755",
            ])
        self.assertEqual(rc, 0)
        self.assertEqual(output.getvalue(), "write: a/b.txt\n")
        self.assertEqual(dest.read_bytes(), self.incoming.read_bytes())
        self.assertEqual(stat.S_IMODE(dest.stat().st_mode) & 0o111, 0o111)
        rows = [json.loads(line) for line in session.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(rows, [{
            "action": "write",
            "incoming_sha256": kit_inventory.sha256_file(self.incoming),
            "path": "a/b.txt",
            "reason": "new",
        }])

    def test_main_apply_missing_incoming_returns_two(self) -> None:
        session = self.sandbox / "missing-session.jsonl"
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            rc = kit_inventory.main([
                "apply", "--root", str(self.root), "--path", "a/b.txt",
                "--incoming", str(self.sandbox / "does-not-exist"),
                "--session", str(session),
            ])
        self.assertEqual(rc, 2)
        self.assertIn("incoming missing:", errors.getvalue())
        self.assertFalse((self.root / "a" / "b.txt").exists())
        self.assertFalse(session.exists())

    def test_main_mark_and_source(self) -> None:
        self._dest("developer version\n")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = kit_inventory.main([
                "mark", "--root", str(self.root), "--path", f"./{self.REL}",
                "--source", "local",
            ])
        self.assertEqual(rc, 0)
        self.assertEqual(output.getvalue(), f"marked {self.REL} source=local\n")
        entry = kit_inventory.load_inventory(self.root)["files"][self.REL]
        self.assertEqual(entry["source"], "local")
        self.assertEqual(entry["sha256"], kit_inventory.sha256_file(self.dest))

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = kit_inventory.main([
                "source", "--root", str(self.root), "--path", self.REL,
            ])
        self.assertEqual(rc, 0)
        self.assertEqual(output.getvalue(), "local\n")

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = kit_inventory.main([
                "source", "--root", str(self.root), "--path", "missing.txt",
            ])
        self.assertEqual(rc, 0)
        self.assertEqual(output.getvalue(), "missing\n")

        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            rc = kit_inventory.main([
                "mark", "--root", str(self.root), "--path", "missing.txt",
                "--source", "local",
            ])
        self.assertEqual(rc, 1)
        self.assertIn("missing file: missing.txt", errors.getvalue())

    def test_main_apply_keeps_marked_local_when_forced(self) -> None:
        self._dest("developer version\n")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(kit_inventory.main([
                "mark", "--root", str(self.root), "--path", self.REL,
                "--source", "local",
            ]), 0)
        session = self.sandbox / "local-session.jsonl"
        with contextlib.redirect_stdout(io.StringIO()):
            rc = kit_inventory.main([
                "apply", "--root", str(self.root), "--path", self.REL,
                "--incoming", str(self.incoming), "--session", str(session),
                "--force",
            ])
        self.assertEqual(rc, 0)
        self.assertEqual(self.dest.read_text(encoding="utf-8"), "developer version\n")
        rows = [json.loads(line) for line in session.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["action"], "skip")
        self.assertEqual(rows[0]["reason"], "local")


if __name__ == "__main__":
    unittest.main()
