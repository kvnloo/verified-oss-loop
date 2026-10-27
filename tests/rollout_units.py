#!/usr/bin/env python3
"""Offline unit contracts for scripts/rollout.py."""

from __future__ import annotations

import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


ROLLOUT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "rollout.py"
spec = importlib.util.spec_from_file_location("rollout_under_test", ROLLOUT_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {ROLLOUT_PATH}")
rollout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rollout)


class RolloutUnits(unittest.TestCase):
    def setUp(self) -> None:
        temporary_root = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_root.cleanup)
        self.root = Path(temporary_root.name)
        self.config = self.root / ".verified-oss-loop" / "rollout.yml"

    def _write_config(self, content: str) -> None:
        self.config.parent.mkdir(parents=True, exist_ok=True)
        self.config.write_text(content, encoding="utf-8")

    def _cli(self, *args: str) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = rollout.main(["--root", str(self.root), *args])
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def test_load_scheme_default_and_quotes(self) -> None:
        self.assertFalse(self.config.exists())
        self.assertEqual(rollout.load_scheme(self.root), "rolling")

        cases = (
            ("double quotes", 'scheme: "staged"\n', "staged"),
            ("single quotes and inline comment", "scheme: 'stable'  # pinned\n", "stable"),
            ("commented-out scheme", "# scheme: stable\nscheme: staged\n", "staged"),
            ("first scheme wins", "scheme: stable\nscheme: staged\n", "stable"),
        )
        for label, content, expected in cases:
            with self.subTest(case=label):
                self._write_config(content)
                self.assertEqual(rollout.load_scheme(self.root), expected)

    def test_unknown_scheme_exits(self) -> None:
        self._write_config("scheme: beta\n")
        with self.assertRaises(SystemExit) as raised:
            rollout.load_scheme(self.root)
        self.assertEqual(str(raised.exception), "unknown rollout scheme: beta")

    def test_policy_table(self) -> None:
        expected = {
            "stable": {
                "scheme": "stable",
                "worker_base": "main",
                "feature_target": "main",
                "overnight_target": "main",
                "automerge_preview": False,
                "automerge_nightly": False,
                "promote_preview_to_nightly": False,
            },
            "staged": {
                "scheme": "staged",
                "worker_base": "nightly",
                "feature_target": "preview",
                "overnight_target": "nightly",
                "automerge_preview": True,
                "automerge_nightly": False,
                "promote_preview_to_nightly": True,
            },
            "rolling": {
                "scheme": "rolling",
                "worker_base": "nightly",
                "feature_target": "preview",
                "overnight_target": "nightly",
                "automerge_preview": True,
                "automerge_nightly": True,
                "promote_preview_to_nightly": True,
            },
        }
        for scheme, values in expected.items():
            with self.subTest(scheme=scheme):
                self.assertEqual(rollout.policy(scheme), values)

    def test_cli_show_lowercases_bools(self) -> None:
        expected_lines = {
            "stable": [
                "scheme=stable",
                "worker_base=main",
                "feature_target=main",
                "overnight_target=main",
                "automerge_preview=false",
                "automerge_nightly=false",
                "promote_preview_to_nightly=false",
            ],
            "staged": [
                "scheme=staged",
                "worker_base=nightly",
                "feature_target=preview",
                "overnight_target=nightly",
                "automerge_preview=true",
                "automerge_nightly=false",
                "promote_preview_to_nightly=true",
            ],
            "rolling": [
                "scheme=rolling",
                "worker_base=nightly",
                "feature_target=preview",
                "overnight_target=nightly",
                "automerge_preview=true",
                "automerge_nightly=true",
                "promote_preview_to_nightly=true",
            ],
        }
        for scheme, lines in expected_lines.items():
            with self.subTest(scheme=scheme):
                self._write_config(f"scheme: {scheme}\n")
                exit_code, stdout, stderr = self._cli("show")
                self.assertEqual(exit_code, 0)
                self.assertEqual(stdout.splitlines(), lines)
                self.assertEqual(stderr, "")

    def test_cli_get_unknown_key(self) -> None:
        exit_code, stdout, stderr = self._cli("get", "nope")
        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "unknown key: nope\n")

        exit_code, stdout, stderr = self._cli("get", "automerge_preview")
        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout, "true\n")
        self.assertEqual(stderr, "")

    def test_cli_allow_matrix(self) -> None:
        commands = (
            ("allow-automerge", "preview"),
            ("allow-automerge", "nightly"),
            ("allow-promote", "preview-to-nightly"),
        )
        exit_codes = {
            "rolling": (0, 0, 0),
            "staged": (0, 1, 0),
            "stable": (1, 1, 1),
        }
        for scheme, expected_codes in exit_codes.items():
            self._write_config(f"scheme: {scheme}\n")
            for command, expected in zip(commands, expected_codes):
                with self.subTest(scheme=scheme, command=command):
                    exit_code, stdout, stderr = self._cli(*command)
                    self.assertEqual(exit_code, expected)
                    self.assertEqual(stdout, "")
                    self.assertEqual(stderr, "")

        with self.assertRaises(SystemExit) as invalid_channel:
            self._cli("allow-automerge", "beta")
        self.assertEqual(invalid_channel.exception.code, 2)

        with self.assertRaises(SystemExit) as invalid_promotion:
            self._cli("allow-promote", "nightly-to-main")
        self.assertEqual(invalid_promotion.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
