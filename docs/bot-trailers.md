# Bot-authored commit trailers

This is a provenance convention for the existing Verified OSS Loop, not a new
approval or merge process. A commit is **bot-authored** if an agent wrote any
part of its diff, even when a human committed or reviewed it. Bot-authored
commits must identify the harness and model in their commit message.

## Trailer block

Put trailers in the **final paragraph** of the commit message, after a blank
line. Use one `Key: value` per line. The checker parses RFC-822-style
continuation lines but rejects them: convention values must be single-line.

```text
Explain the implementation

Agent-Harness: chatgpt
Agent-Model: gpt-6
Agent-Work-Item: https://github.com/kvnloo/verified-oss-loop/issues/26
Agent-Run: run-20261027-01
Co-Authored-By: Contributor <contributor[bot]@users.noreply.github.com>
```

| Trailer | Requirement |
| --- | --- |
| `Agent-Harness` | Required: `claude-code`, `codex`, `hermes`, `chatgpt`, `omp`, or `other:<name>`. |
| `Agent-Model` | Required: actual model identifier used for the diff. |
| `Agent-Work-Item` | Optional: issue or PR URL, including its path. |
| `Agent-Run` | Optional: opaque run ID, **not** a host, device, URL, or local path. |
| `Co-Authored-By` | Optional standard Git trailer (`Name <email>`); bot noreply emails aid detection. Multiple co-authors are allowed. |

The following rules apply to each `Agent-*` value and to
`Co-Authored-By` where applicable:

- Nonempty, one line, at most 120 characters; no leading or trailing spaces.
- No email addresses in `Agent-*` values. Emails are allowed only inside
  `Co-Authored-By`.
- No absolute filesystem paths (leading `/`, `~/`, UNC prefix, or Windows
  drive prefix such as `C:`), IP addresses, or machine names.
- No duplicate `Agent-*` key (case-insensitive) or unknown `Agent-*` key.
- The checker catches recognizable machine-address forms; opaque-looking host
  identifiers cannot be proven safe mechanically. Review messages before
  publishing to ensure no private host, network, device, or other personal data.

Human-only commits need no `Agent-*` trailers. Ordinary human co-authorship
may still use Git's `Co-Authored-By` trailer.

## Identification

The checker treats a commit as bot-authored if **any** of these applies:

1. An `Agent-*` trailer appears in its final paragraph.
2. A `Co-Authored-By` address matches a bot noreply glob. Defaults:
   `noreply@anthropic.com`, `*[bot]@users.noreply.github.com`, and
   `codex@openai.com`. The brackets in `[bot]` are literal.
3. The commit's author email matches one of the repeatable
   `--bot-author REGEX` expressions.

If none applies, a message without provenance appears human-only. **The
checker cannot infer agent involvement without a detection signal**: teams
should configure bot author patterns and require the trailers during review.

Only the final paragraph is inspected; apparent trailers in earlier prose do
not count. See [git-interpret-trailers](https://git-scm.com/docs/git-interpret-trailers)
for Git's trailer conventions.

## Run the checker

From a checkout of the repository being audited:

```bash
python3 scripts/check-bot-trailers.py --range main..HEAD
python3 scripts/check-bot-trailers.py --range main..HEAD --bot-author '.*@bots\.example\.invalid' --json
python3 scripts/check-bot-trailers.py --message-file /path/to/commit-message.txt
python3 tests/check_bot_trailers.py
```

The optional `--bot-noreply GLOB` flag is repeatable. When provided it
**replaces** the default bot co-author list; supply all desired globs. It
interprets `*` as a wildcard, with all other characters (including square
brackets) literal. The `--bot-author` expressions are Python regular
expressions and apply to the **git commit author email**, not to the message
file (which has no author metadata).

`--range A..B` calls `git log --format=%H%x00%ae%x00%B%x1e` without a shell.
`--message-file F` checks the file without Git. Human-friendly mode prints
each finding with its commit SHA; `--json` emits
`{"commits":[{"sha": ..., "author_email": ..., "findings": [...]}],"ok": ...}`.

| Exit | Meaning |
| --- | --- |
| 0 | All inspected messages clean (including empty ranges). |
| 1 | One or more findings: missing or duplicate required trailers, unknown keys, or invalid values. |
| 2 | Argument, message-file, or Git error. |

This lint is a contribution-quality check, **not a replacement for independent
review, evidence receipts, or authorized human merge** (`SPEC.md`).
No dependency installation, network call, or CI wiring is required to invoke
it manually.
