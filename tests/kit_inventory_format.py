#!/usr/bin/env python3
"""Offline stdlib tests for the kit inventory parser and emitter."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "kit-inventory.py"
SPEC = importlib.util.spec_from_file_location("kit_inventory", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {SCRIPT}")
kit_inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(kit_inventory)


class KitInventoryFormatTests(unittest.TestCase):
    def _write_inventory(self, root: Path, text: str) -> None:
        path = kit_inventory.inventory_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_posix(self) -> None:
        cases = {
            "./a/b": "a/b",
            "././a": "a",
            "a\\b": "a/b",
            "  .github/x  ": ".github/x",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(kit_inventory.posix(raw), expected)

    def test_load_missing_returns_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                kit_inventory.load_inventory(Path(tmp)),
                {
                    "schema": kit_inventory.SCHEMA,
                    "kit": kit_inventory.DEFAULT_KIT,
                    "kit_revision": "",
                    "synced_at": "",
                    "files": {},
                },
            )

    def test_emit_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = {
                "kit_revision": "r1",
                "files": {
                    "skills/b/SKILL.md": {"source": "local", "sha256": "aa"},
                    ".github/workflows/x.yml": {
                        "source": "kit",
                        "sha256": "bb",
                        "kit_sha256": "cc",
                    },
                },
            }
            self.assertEqual(
                kit_inventory.save_inventory(root, data),
                kit_inventory.inventory_path(root),
            )
            loaded = kit_inventory.load_inventory(root)
            self.assertEqual(loaded["kit_revision"], "r1")
            self.assertEqual(
                loaded["files"],
                {
                    "skills/b/SKILL.md": {
                        "path": "skills/b/SKILL.md",
                        "source": "local",
                        "sha256": "aa",
                        "kit_sha256": "",
                    },
                    ".github/workflows/x.yml": {
                        "path": ".github/workflows/x.yml",
                        "source": "kit",
                        "sha256": "bb",
                        "kit_sha256": "cc",
                    },
                },
            )

    def test_emit_is_sorted_and_omits_empty_hashes(self) -> None:
        emitted = kit_inventory.emit_inventory(
            {
                "files": {
                    "z.md": {"sha256": "", "kit_sha256": ""},
                    "a.md": {
                        "source": "local",
                        "sha256": "aa",
                        "kit_sha256": "bb",
                    },
                }
            }
        )
        self.assertLess(
            emitted.index("  - path: a.md\n"),
            emitted.index("  - path: z.md\n"),
        )
        self.assertIn("    sha256: aa\n", emitted)
        self.assertIn("    kit_sha256: bb\n", emitted)
        last_entry = emitted.split("  - path: z.md\n", 1)[1]
        self.assertIn("    source: kit\n", last_entry)
        self.assertNotIn("    sha256:", last_entry)
        self.assertNotIn("    kit_sha256:", last_entry)

    def test_comments_and_blank_lines_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_inventory(
                root,
                "# comment\n\nfiles:\n  # comment\n"
                "  - path: skills/b/SKILL.md\n\n"
                "    # comment\n    source: local # note\n\n",
            )
            entry = kit_inventory.load_inventory(root)["files"]["skills/b/SKILL.md"]
            self.assertEqual(entry["source"], "local")

    def test_entry_default_source_is_kit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_inventory(root, "files:\n  - path: a.md\n")
            self.assertEqual(
                kit_inventory.load_inventory(root)["files"]["a.md"],
                {
                    "path": "a.md",
                    "source": "kit",
                    "sha256": "",
                    "kit_sha256": "",
                },
            )

    def test_hash_in_path_is_truncated(self) -> None:
        # Known limitation: the hand-rolled reader treats any # as a comment.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_inventory(root, "files:\n  - path: docs/a#b.md\n")
            files = kit_inventory.load_inventory(root)["files"]
            self.assertEqual(files["docs/a"]["path"], "docs/a")
            self.assertNotIn("docs/a#b.md", files)


if __name__ == "__main__":
    unittest.main()
