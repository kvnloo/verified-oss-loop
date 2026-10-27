#!/usr/bin/env python3
"""Offline, dependency-free tests for the bot trailer convention and CLI."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check-bot-trailers.py"
SPEC = importlib.util.spec_from_file_location("check_bot_trailers", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot import bot trailer checker")
checker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)

VALID = (
    "Implement provenance checks\n\n"
    "Agent-Harness: chatgpt\n"
    "Agent-Model: gpt-6\n"
    "Agent-Work-Item: https://github.com/kvnloo/verified-oss-loop/issues/26\n"
    "Agent-Run: run-20261027-01\n"
)
COAUTHORED_BOT = (
    "Update helper\n\n"
    "Co-Authored-By: Claude <noreply@anthropic.com>\n"
)


def codes(message: str, author: str = "", patterns=()) -> list[str]:
    return [finding.code for finding in checker.check_message(message, author, patterns)]


def missing_keys(message: str, author: str = "", patterns=()) -> set[str]:
    return {
        finding.trailer
        for finding in checker.check_message(message, author, patterns)
        if finding.code == "missing-trailer"
    }


class TrailerUnitTests(unittest.TestCase):
    def test_human_commit_without_trailers_is_clean(self) -> None:
        self.assertEqual(codes("Human change\n\nNo agent involved."), [])

    def test_human_coauthor_does_not_imply_bot(self) -> None:
        self.assertEqual(
            codes("Joint work\n\nCo-Authored-By: Teammate <human@example.invalid>"),
            [],
        )

    def test_anthropic_noreply_requires_both_fields(self) -> None:
        self.assertEqual(
            missing_keys(COAUTHORED_BOT),
            {"Agent-Harness", "Agent-Model"},
        )
        self.assertEqual(codes(COAUTHORED_BOT).count("missing-trailer"), 2)

    def test_github_bot_noreply_brackets_are_literal(self) -> None:
        message = "Bot help\n\nCo-Authored-By: Helper <helper[bot]@users.noreply.github.com>"
        self.assertEqual(
            missing_keys(message),
            {"Agent-Harness", "Agent-Model"},
        )
        human = "Joint work\n\nCo-Authored-By: Helper <helperb@users.noreply.github.com>"
        self.assertEqual(codes(human), [])

    def test_codex_noreply_detected(self) -> None:
        message = "Change\n\nCo-Authored-By: Codex <codex@openai.com>"
        self.assertEqual(missing_keys(message), {"Agent-Harness", "Agent-Model"})

    def test_full_valid_set_clean_and_parsed(self) -> None:
        self.assertEqual(codes(VALID), [])
        self.assertEqual(
            checker.parse_trailers(VALID),
            [
                ("Agent-Harness", "chatgpt"),
                ("Agent-Model", "gpt-6"),
                ("Agent-Work-Item", "https://github.com/kvnloo/verified-oss-loop/issues/26"),
                ("Agent-Run", "run-20261027-01"),
            ],
        )

    def test_other_harness_is_allowed(self) -> None:
        self.assertEqual(
            codes("New bot\n\nAgent-Harness: other:my-runner\nAgent-Model: model-v1"),
            [],
        )

    def test_unknown_harness_is_malformed(self) -> None:
        self.assertIn(
            "malformed-value",
            codes("Bot\n\nAgent-Harness: unknown\nAgent-Model: model-1"),
        )

    def test_duplicate_model_is_reported_case_insensitively(self) -> None:
        message = VALID + "agent-model: second-model\n"
        findings = checker.check_message(message, "", [])
        self.assertTrue(
            any(f.code == "duplicate-trailer" and f.trailer == "agent-model" for f in findings)
        )

    def test_absolute_run_path_is_reported(self) -> None:
        for value in ("/srv/x", "~/work", "C:\\work", "\\\\server\\share"):
            with self.subTest(value=value):
                message = VALID + f"Agent-Run: {value}\n"
                self.assertIn("malformed-value", codes(message))
                self.assertTrue(
                    any("path" in f.message for f in checker.check_message(message, "", []))
                )

    def test_unknown_agent_key_reported(self) -> None:
        self.assertIn(
            "unknown-agent-trailer",
            codes(VALID + "Agent-Foo: unexpected\n"),
        )

    def test_agent_key_in_earlier_paragraph_is_ignored(self) -> None:
        message = (
            "A human change\n\n"
            "Agent-Harness: codex\nAgent-Model: model-in-description\n\n"
            "This is the actual final paragraph, not trailers."
        )
        self.assertEqual(checker.parse_trailers(message), [])
        self.assertEqual(codes(message), [])

    def test_bot_author_regex_triggers_missing_fields(self) -> None:
        self.assertEqual(
            missing_keys("Automated commit", "worker@bots.example.invalid",
                         [re.compile(r"@bots\.example\.invalid$")]),
            {"Agent-Harness", "Agent-Model"},
        )
        self.assertEqual(
            missing_keys("Automated commit", "worker@bots.example.invalid",
                         [r"@bots\.example\.invalid$"]),
            {"Agent-Harness", "Agent-Model"},
        )

    def test_custom_bot_noreply_list_replaces_defaults(self) -> None:
        custom = "Change\n\nCo-Authored-By: Runner <ci@bots.example.invalid>"
        self.assertEqual(codes(custom), [])
        self.assertEqual(
            {
                f.trailer for f in checker.check_message(
                    custom, "", [], bot_noreply_patterns=["ci@bots.example.invalid"]
                ) if f.code == "missing-trailer"
            },
            {"Agent-Harness", "Agent-Model"},
        )
        self.assertEqual(
            checker.check_message(COAUTHORED_BOT, "", [],
                                  bot_noreply_patterns=["ci@bots.example.invalid"]),
            [],
        )

    def test_multiline_continuation_parses_but_is_rejected(self) -> None:
        message = "Bot\n\nAgent-Harness: chatgpt\nAgent-Model: gpt-6\n extra"
        self.assertEqual(
            checker.parse_trailers(message)[-1],
            ("Agent-Model", "gpt-6\nextra"),
        )
        self.assertIn("malformed-value", codes(message))

    def test_empty_overlong_and_email_values_are_invalid(self) -> None:
        for value in ("   ", "x" * 121, "person@example.invalid", "  model "):
            with self.subTest(value=value):
                message = f"Bot\n\nAgent-Harness: chatgpt\nAgent-Model: {value}\n"
                self.assertIn("malformed-value", codes(message))

    def test_run_machine_identifier_rejected(self) -> None:
        self.assertIn("malformed-value", codes(VALID + "Agent-Run: hostname=box\n"))

    def test_work_item_requires_url(self) -> None:
        self.assertIn("malformed-value", codes(VALID + "Agent-Work-Item: issue-26\n"))

    def test_malformed_coauthor_value_is_reported(self) -> None:
        message = "Human change\n\nCo-Authored-By: no-address"
        self.assertIn("malformed-value", codes(message))


class TrailerCLITests(unittest.TestCase):
    def run_checker(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=cwd, capture_output=True, text=True, check=False,
        )

    def test_message_file_valid_and_failing_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            message_file = Path(tmp) / "message.txt"
            message_file.write_text(VALID, encoding="utf-8")
            clean = self.run_checker("--message-file", str(message_file), "--json")
            self.assertEqual(clean.returncode, 0, clean.stderr)
            self.assertTrue(json.loads(clean.stdout)["ok"])
            message_file.write_text(COAUTHORED_BOT, encoding="utf-8")
            bad = self.run_checker("--message-file", str(message_file), "--json")
            self.assertEqual(bad.returncode, 1, bad.stderr)
            report = json.loads(bad.stdout)
            self.assertIsNone(report["commits"][0]["sha"])
            self.assertEqual(
                {f["trailer"] for f in report["commits"][0]["findings"]},
                {"Agent-Harness", "Agent-Model"},
            )

    def test_invalid_regex_and_bad_range_are_usage_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            msg = Path(tmp) / "message.txt"
            msg.write_text(VALID, encoding="utf-8")
            bad_re = self.run_checker("--message-file", str(msg), "--bot-author", "[")
            self.assertEqual(bad_re.returncode, 2)
            self.assertIn("invalid --bot-author regex", bad_re.stderr)
            bad_range = self.run_checker("--range", "--not-a-revision")
            self.assertEqual(bad_range.returncode, 2)

    def test_missing_message_file_is_error_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = self.run_checker("--message-file", str(Path(tmp) / "missing"))
            self.assertEqual(missing.returncode, 2)
            self.assertIn("message file error", missing.stderr)

    def test_range_reports_bad_commit_sha_in_temporary_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()

            def git(*args: str) -> str:
                command = [
                    "git", "-C", str(repo),
                    "-c", "user.name=Test Contributor",
                    "-c", "user.email=test@example.invalid",
                    "-c", "commit.gpgsign=false",
                    *args,
                ]
                proc = subprocess.run(
                    command, capture_output=True, text=True, check=True,
                )
                return proc.stdout.strip()

            git("init", "-q")
            tracked = repo / "file.txt"
            tracked.write_text("first\n", encoding="utf-8")
            git("add", "file.txt")
            git("commit", "-q", "-m", "Human first commit")
            tracked.write_text("second\n", encoding="utf-8")
            git("add", "file.txt")
            git("commit", "-q", "-m", COAUTHORED_BOT)
            bad_sha = git("rev-parse", "HEAD")

            proc = self.run_checker("--range", "HEAD~1..HEAD", "--json", cwd=repo)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            report = json.loads(proc.stdout)
            self.assertFalse(report["ok"])
            self.assertEqual(len(report["commits"]), 1)
            self.assertEqual(report["commits"][0]["sha"], bad_sha)
            self.assertEqual(
                {f["trailer"] for f in report["commits"][0]["findings"]},
                {"Agent-Harness", "Agent-Model"},
            )

            empty = self.run_checker("--range", "HEAD..HEAD", "--json", cwd=repo)
            self.assertEqual(empty.returncode, 0, empty.stderr)
            self.assertEqual(json.loads(empty.stdout), {"commits": [], "ok": True})

            not_a_ref = self.run_checker("--range", "unknown-ref..HEAD", cwd=repo)
            self.assertEqual(not_a_ref.returncode, 2)
            self.assertIn("git error", not_a_ref.stderr)


if __name__ == "__main__":
    unittest.main()
