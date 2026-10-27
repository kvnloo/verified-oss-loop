#!/usr/bin/env python3
"""Lint bot-authored commit trailers in a git range or a message file (stdlib only)."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Pattern, Sequence
from urllib.parse import urlsplit

REQUIRED = ("Agent-Harness", "Agent-Model")
ALLOWED = {"agent-harness", "agent-model", "agent-work-item", "agent-run"}
COAUTHOR = "co-authored-by"
DEFAULT_BOT_NOREPLY_PATTERNS = (
    "noreply@anthropic.com",
    "*[bot]@users.noreply.github.com",
    "codex@openai.com",
)
TRAILER = re.compile(r"^([A-Za-z][A-Za-z0-9-]*):[ \t]*(.*)$")
COAUTHOR_VALUE = re.compile(r"^[^<> \t][^<>]*\s+<([^<>\s@]+@[^<>\s@]+)>$")
EMAIL = re.compile(r"(?<![\w.-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
ABSOLUTE_PATH = re.compile(r"^(?:/|~/|[A-Za-z]:|\\\\)")
MACHINE = re.compile(
    r"(?:\b(?:host|hostname|machine|device)\s*[:=]|"
    r"\b(?:[A-Za-z0-9-]+\.)+(?:local|lan|internal|ts\.net)\b)",
    re.I,
)
IPV4 = re.compile(r"(?<![\w.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![\w.])")


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    trailer: str | None = None


def parse_trailers(message: str) -> list[tuple[str, str]]:
    """Parse RFC-822-style fields in the final paragraph only.

    A continuation is preserved with a newline so that validation can reject
    multi-line values without accidentally treating them as single-line.
    """
    lines = message.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return []
    text = "\n".join(lines)
    paragraph = re.split(r"\n[ \t]*\n+", text)[-1]
    result: list[tuple[str, str]] = []
    for line in paragraph.split("\n"):
        match = TRAILER.fullmatch(line)
        if match:
            result.append((match.group(1), match.group(2)))
        elif line.startswith((" ", "\t")) and result:
            key, value = result[-1]
            result[-1] = (key, value + "\n" + line.lstrip(" \t"))
        else:
            return []
    return result


def _bot_noreply(email: str, patterns: Sequence[str]) -> bool:
    """Match case-insensitive globs with '*' wildcards and literal '[bot]'."""
    for glob in patterns:
        pattern = "^" + re.escape(glob).replace(r"\*", ".*") + "$"
        if re.fullmatch(pattern, email, flags=re.I):
            return True
    return False


def _ip_literal(value: str) -> bool:
    for match in IPV4.finditer(value):
        try:
            ipaddress.IPv4Address(match.group())
        except ipaddress.AddressValueError:
            continue
        return True
    return False


def _value_findings(key: str, value: str) -> list[Finding]:
    findings: list[Finding] = []

    def bad(reason: str) -> None:
        findings.append(Finding("malformed-value", reason, key))

    if not value.strip():
        bad("empty or whitespace-only value")
    if len(value) > 120:
        bad("value exceeds 120 characters")
    if "\n" in value:
        bad("multi-line value (continuations are parsed but not allowed)")
    if value != value.strip():
        bad("leading or trailing whitespace")
    if ABSOLUTE_PATH.match(value):
        bad("absolute filesystem path")
    if MACHINE.search(value) or _ip_literal(value):
        bad("machine name or IP address")

    kind = key.casefold()
    if kind == COAUTHOR:
        if not COAUTHOR_VALUE.fullmatch(value):
            bad("Co-Authored-By must be Name <email>")
    else:
        if EMAIL.search(value):
            bad("email address outside Co-Authored-By")
        if kind == "agent-harness" and not (
            value in {"claude-code", "codex", "hermes", "chatgpt", "omp"}
            or re.fullmatch(r"other:[A-Za-z0-9][A-Za-z0-9._-]*", value)
        ):
            bad("unrecognized Agent-Harness")
        if kind == "agent-work-item" and value.strip():
            try:
                url = urlsplit(value)
                if url.scheme not in {"http", "https"} or not url.hostname or not url.path.strip("/"):
                    bad("Agent-Work-Item must be an issue/PR URL")
            except ValueError:
                bad("Agent-Work-Item must be an issue/PR URL")
        if kind == "agent-run" and ("/" in value or "\\" in value or "://" in value):
            bad("Agent-Run must be an opaque identifier, not a path or URL")
    return findings


def check_message(
    message: str,
    author_email: str,
    bot_authors: Sequence[str | Pattern[str]],
    *,
    bot_noreply_patterns: Sequence[str] = DEFAULT_BOT_NOREPLY_PATTERNS,
) -> list[Finding]:
    """Check a commit. Bot-author regexes are matched against the author email."""
    trailers = parse_trailers(message)
    found: list[Finding] = []
    seen: set[str] = set()
    names: set[str] = set()
    has_agent = False
    has_bot_coauthor = False

    for key, value in trailers:
        kind = key.casefold()
        if kind.startswith("agent-"):
            has_agent = True
            if kind not in ALLOWED:
                found.append(Finding("unknown-agent-trailer", "unknown Agent-* key", key))
            if kind in seen:
                found.append(Finding("duplicate-trailer", "duplicate Agent-* key", key))
            seen.add(kind)
            names.add(kind)
            found.extend(_value_findings(key, value))
        elif kind == COAUTHOR:
            found.extend(_value_findings(key, value))
            match = COAUTHOR_VALUE.fullmatch(value)
            if match and _bot_noreply(match.group(1), bot_noreply_patterns):
                has_bot_coauthor = True

    author_is_bot = any(
        re.search(regex, author_email) if isinstance(regex, str)
        else regex.search(author_email)
        for regex in bot_authors
    )
    if has_agent or has_bot_coauthor or author_is_bot:
        for key in REQUIRED:
            if key.casefold() not in names:
                found.append(Finding("missing-trailer", "required for bot-authored commit", key))
    return found


def _parse_git_log(output: str) -> list[tuple[str, str, str]]:
    records: list[tuple[str, str, str]] = []
    for chunk in output.split("\x1e"):
        chunk = chunk.lstrip("\r\n")
        if not chunk.strip():
            continue
        fields = chunk.split("\x00", 2)
        if len(fields) != 3 or not re.fullmatch(r"[0-9a-f]{40,64}", fields[0]):
            raise ValueError("unrecognized git log record")
        records.append((fields[0], fields[1], fields[2]))
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check bot-authored work trailers")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--range", dest="commit_range", metavar="A..B", help="git commit range")
    mode.add_argument("--message-file", metavar="F", help="commit message file")
    parser.add_argument("--bot-author", action="append", default=[], metavar="REGEX",
                        help="regex for bot author email (repeatable)")
    parser.add_argument("--bot-noreply", action="append", metavar="GLOB",
                        help="replace default bot Co-Authored-By email globs (repeatable)")
    parser.add_argument("--json", action="store_true", help="machine-readable findings")
    args = parser.parse_args(argv)

    try:
        bot_authors = [re.compile(pattern) for pattern in args.bot_author]
    except re.error as exc:
        parser.error(f"invalid --bot-author regex: {exc}")

    if args.commit_range is not None:
        parts = args.commit_range.split("..")
        if (len(parts) != 2 or any(
            not part or part.startswith("-") or re.search(r"\s|[\x00-\x1f]", part)
            for part in parts
        )):
            parser.error("--range must be a single A..B revision range")
        try:
            process = subprocess.run(
                ["git", "log", "--format=%H%x00%ae%x00%B%x1e", args.commit_range],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                check=False,
            )
        except OSError as exc:
            print(f"git error: {exc}", file=sys.stderr)
            return 2
        if process.returncode:
            print(f"git error: {process.stderr.strip()}", file=sys.stderr)
            return 2
        try:
            commits = _parse_git_log(process.stdout)
        except ValueError as exc:
            print(f"git error: {exc}", file=sys.stderr)
            return 2
    else:
        try:
            message = Path(args.message_file).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(f"message file error: {exc}", file=sys.stderr)
            return 2
        commits = [("", "", message)]

    report = []
    for sha, email, message in commits:
        findings = check_message(
            message, email, bot_authors,
            bot_noreply_patterns=args.bot_noreply
            if args.bot_noreply is not None else DEFAULT_BOT_NOREPLY_PATTERNS,
        )
        report.append({
            "sha": sha or None,
            "author_email": email or None,
            "findings": [asdict(item) for item in findings],
        })
    if args.json:
        print(json.dumps({"commits": report, "ok": all(not c["findings"] for c in report)}, indent=2))
    else:
        for item in report:
            for finding in item["findings"]:
                print(f'{item["sha"] or "message-file"}: {finding["code"]}: '
                      f'{finding["trailer"] or "(value)"}: {finding["message"]}')
        if all(not c["findings"] for c in report):
            print("ok: bot trailers")
    return 1 if any(item["findings"] for item in report) else 0


if __name__ == "__main__":
    sys.exit(main())
