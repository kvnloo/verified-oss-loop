# Factory runtime onboarding (Hermes first)

A fresh machine, public source, a fictional config. Nothing here needs the maintainer's accounts,
files or history.

## 1. Install

```bash
git clone https://github.com/kvnloo/verified-oss-loop
cd verified-oss-loop
python3 -m unittest discover -s tests/acceptance -v   # offline; fake harness, fictional repos
```

Python 3.10+ and git. No pip installs: the runtime is stdlib only.

## 2. Apply a factory home

```bash
bin/vol-factory apply --home ~/factory --config examples/factory.example.json
bin/vol-factory apply --home ~/factory --config examples/factory.example.json   # prints: no-op
```

`apply` creates `~/factory/{factory.json,state/ledger.sqlite,work/}` and changes nothing on a second
run. Delete the home to uninstall; your repositories and Hermes profiles are never touched.

## 3. Point it at your repos and a Hermes profile

Edit `~/factory/factory.json` (or your own copy of the example, then re-apply):

- `repos[]`: local clones, each with `test_cmd` and the `allowed_paths` a builder may change.
  Two repos share the same `roster`; there is no per-repository bot.
- `harnesses.hermes-builder`: an explicit Hermes `profile`, `provider` and `model`. The adapter runs
  `hermes -p <profile> chat --query-file … --format stream-json --max-turns N --in <worktree>
  --provider P -m M --source tool`. It refuses `--yolo` and other approval/credential bypasses.
- Create the profile with `hermes profile create factory-builder --no-skills` (no `--clone`, so no
  credentials are copied). In its `config.yaml` set the model/provider, `fallback_providers: []`
  (a held lane must not silently switch provider) and `agent.run_budget_seconds` (the gateway-backed
  `hermes chat` does not accept `--run-budget`).
- `interrupt_cmd` (optional): how to stop a running turn. Killing a `hermes chat` client only
  detaches it; the gateway keeps working. Use the bundled shim with Hermes' own Python, e.g.
  `["<hermes venv>/bin/python", "adapters/hermes/interrupt.py", "--profile", "{profile}", "{session_id}"]`.

## 4. Admission

The runtime never decides budget. It reads `~/factory/admission.json`, written by whatever owns
your quota decision:

```json
{"observed_at": "2030-01-01T00:00:00Z", "max_age_s": 900,
 "lanes": {"example-free": {"state": "available"}}}
```

Missing, stale, unknown or non-`available` lanes hold the task with a reason and resume trigger.

## 5. Run one task

```bash
bin/vol-factory run --home ~/factory --repo alpha-calc --issue 1 --objective "fix the failing test"
bin/vol-factory inspect --home ~/factory --attempt att-…   # contracts/attempt.schema.json document
```

The builder works in its own worktree; a different principal then re-runs the tests at the exact
candidate SHA (and at the base, which must fail). Only that makes an attempt
`independently_verified`. Nothing is pushed, posted or merged.
