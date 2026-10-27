#!/usr/bin/env python3
"""Unit tests for kit-inventory finalize and show. Stdlib and temporary files only."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "kit-inventory.py"
SPEC = importlib.util.spec_from_file_location("kit_inventory", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SOURCE}")
kit_inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(kit_inventory)


class KitInventoryFinalizeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write_file(self, relative: str, content: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_session(self, *rows: dict[str, str]) -> Path:
        return self.write_file(
            "session.jsonl",
            "".join(json.dumps(row) + "\n" for row in rows),
        )

    def write_kit_paths(self, *paths: str) -> Path:
        return self.write_file("kit-paths.txt", "".join(p + "\n" for p in paths))

    def invoke(self, command: str, *args: str) -> tuple[int, str]:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            result = kit_inventory.main([command, "--root", str(self.root), *args])
        return result, stdout.getvalue()

    def inventory(self) -> dict:
        return kit_inventory.load_inventory(self.root)

    def test_finalize_classifies_rows(self) -> None:
        a = self.write_file("a.txt", "kit content\n")
        b = self.write_file("b.txt", "locally modified\n")
        c = self.write_file("c.txt", "developer owned\n")
        incoming_a = hashlib.sha256(a.read_bytes()).hexdigest()
        incoming_b = hashlib.sha256(b"original b").hexdigest()
        incoming_c = hashlib.sha256(b"original c").hexdigest()
        session = self.write_session(
            {"path": "a.txt", "action": "write", "reason": "new", "incoming_sha256": incoming_a},
            {"path": "b.txt", "action": "skip", "reason": "modified", "incoming_sha256": incoming_b},
            {"path": "c.txt", "action": "skip", "reason": "local", "incoming_sha256": incoming_c},
        )

        code, _ = self.invoke("finalize", "--session", str(session))
        self.assertEqual(code, 0)
        files = self.inventory()["files"]
        self.assertEqual(
            {name: files[name]["source"] for name in ("a.txt", "b.txt", "c.txt")},
            {"a.txt": "kit", "b.txt": "modified", "c.txt": "local"},
        )
        self.assertEqual(files["a.txt"]["kit_sha256"], incoming_a)
        self.assertEqual(files["b.txt"]["kit_sha256"], incoming_b)
        for name, path in (("a.txt", a), ("b.txt", b), ("c.txt", c)):
            with self.subTest(path=name):
                self.assertEqual(files[name]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_finalize_drops_missing_kit_files(self) -> None:
        file = self.write_file("gone.txt", "kit file\n")
        paths = self.write_kit_paths("gone.txt")
        code, _ = self.invoke("finalize", "--kit-paths", str(paths))
        self.assertEqual(code, 0)
        self.assertIn("gone.txt", self.inventory()["files"])

        file.unlink()
        code, _ = self.invoke("finalize", "--kit-paths", str(paths))
        self.assertEqual(code, 0)
        self.assertNotIn("gone.txt", self.inventory()["files"])

    def test_finalize_adds_untracked_local_skills(self) -> None:
        kit_path = self.write_file("tracked.txt", "kit file\n")
        paths = self.write_kit_paths(kit_path.relative_to(self.root).as_posix())
        skills = (
            self.write_file("skills/mine/SKILL.md", "mine\n"),
            self.write_file(".claude/skills/x/SKILL.md", "custom\n"),
        )

        code, _ = self.invoke("finalize", "--kit-paths", str(paths))
        self.assertEqual(code, 0)
        files = self.inventory()["files"]
        self.assertEqual(files["tracked.txt"]["source"], "kit")
        for path in skills:
            rel = path.relative_to(self.root).as_posix()
            with self.subTest(path=rel):
                self.assertEqual(files[rel]["source"], "local")
                self.assertEqual(files[rel]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_finalize_keeps_previous_local(self) -> None:
        notes = self.write_file("notes.md", "first revision\n")
        code, _ = self.invoke("mark", "--path", "notes.md", "--source", "local")
        self.assertEqual(code, 0)
        self.assertEqual(self.inventory()["files"]["notes.md"]["source"], "local")

        notes.write_text("second revision\n", encoding="utf-8")
        empty_session = self.write_session()
        code, _ = self.invoke("finalize", "--session", str(empty_session))
        self.assertEqual(code, 0)
        entry = self.inventory()["files"]["notes.md"]
        self.assertEqual(entry["source"], "local")
        self.assertEqual(entry["sha256"], hashlib.sha256(notes.read_bytes()).hexdigest())

        notes.unlink()
        code, _ = self.invoke("finalize", "--session", str(empty_session))
        self.assertEqual(code, 0)
        self.assertNotIn("notes.md", self.inventory()["files"])

    def test_finalize_metadata(self) -> None:
        code, stdout = self.invoke("finalize", "--kit-revision", "r2")
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "wrote .verified-oss-loop/inventory.yml\n")
        inventory = self.inventory()
        self.assertEqual(inventory["kit_revision"], "r2")
        self.assertRegex(inventory["synced_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

    def test_show_json_and_text(self) -> None:
        code, stdout = self.invoke("show")
        self.assertEqual(code, 1)
        self.assertIn("no inventory", stdout)

        self.write_file("tracked.txt", "kit file\n")
        self.write_file("skills/mine/SKILL.md", "local skill\n")
        kit_paths = self.write_kit_paths("tracked.txt")
        code, _ = self.invoke("finalize", "--kit-paths", str(kit_paths), "--kit-revision", "r2")
        self.assertEqual(code, 0)

        code, stdout = self.invoke("show", "--json")
        self.assertEqual(code, 0)
        shown = json.loads(stdout)
        self.assertEqual(set(shown), {"kit", "kit_revision", "synced_at", "files"})
        self.assertEqual(shown["kit_revision"], "r2")
        self.assertEqual(shown["files"]["tracked.txt"]["source"], "kit")
        self.assertEqual(shown["files"]["skills/mine/SKILL.md"]["source"], "local")

        code, text = self.invoke("show")
        self.assertEqual(code, 0)
        self.assertIn("kit:", text)
        self.assertIn("\nkit:\n  tracked.txt", text)
        self.assertIn("\nmodified:\n  (none)", text)
        self.assertIn("\nlocal:\n  skills/mine/SKILL.md", text)


if __name__ == "__main__":
    unittest.main()
