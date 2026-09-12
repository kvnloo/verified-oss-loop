#!/usr/bin/env bash
# Fixture checks for detect-stack.sh and init-oss-repo.sh. No mutator install.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
DET="$HERE/scripts/detect-stack.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }

expect() {
  local dir="$1" key="$2" want="$3"
  local got
  got="$("$DET" "$dir" | awk -F= -v k="$key" '$1==k{print substr($0,index($0,"=")+1)}')"
  [[ "$got" == "$want" ]] || fail "$dir $key: got '$got' want '$want'"
}

mkdir -p "$TMP/empty"
expect "$TMP/empty" primary unknown
expect "$TMP/empty" mutator none

mkdir -p "$TMP/py"
printf '[project]\nname="x"\n' >"$TMP/py/pyproject.toml"
echo 'KEEP-LICENSE' >"$TMP/py/LICENSE"
expect "$TMP/py" primary python
expect "$TMP/py" unit_cmd "python -m pytest"
expect "$TMP/py" mutator mutmut

mkdir -p "$TMP/spec/tests"
echo 'print("ok")' >"$TMP/spec/tests/validate.py"
expect "$TMP/spec" primary python
expect "$TMP/spec" unit_cmd "python3 tests/validate.py"
expect "$TMP/spec" mutator mutmut

mkdir -p "$TMP/rs"
printf '[package]\nname="x"\nversion="0.0.0"\n' >"$TMP/rs/Cargo.toml"
expect "$TMP/rs" primary rust
expect "$TMP/rs" unit_cmd "cargo test"
expect "$TMP/rs" mutator cargo-mutants

mkdir -p "$TMP/go"
echo 'module example.com/x' >"$TMP/go/go.mod"
expect "$TMP/go" primary go
expect "$TMP/go" unit_cmd "go test ./..."
expect "$TMP/go" mutator none

mkdir -p "$TMP/bun"
echo '{}' >"$TMP/bun/package.json"
touch "$TMP/bun/bun.lock"
expect "$TMP/bun" primary js
expect "$TMP/bun" pkg_manager bun
expect "$TMP/bun" mutator stryker

"$HERE/scripts/init-oss-repo.sh" --target "$TMP/py" --name PyKit --owner kvnloo >/dev/null
grep -q 'PyKit' "$TMP/py/AGENTS.md" || fail "name not substituted"
grep -q 'python -m pytest' "$TMP/py/AGENTS.md" || fail "unit cmd not substituted"
if grep -q '{{UNIT_CMD}}' "$TMP/py/AGENTS.md"; then fail "placeholder left in AGENTS.md"; fi
[[ -f "$TMP/py/skills/tdd/SKILL.md" ]] || fail "skills not copied"
[[ -f "$TMP/py/skills/orient/SKILL.md" ]] || fail "orient skill not copied"
[[ -f "$TMP/py/skills/anti-slop/SKILL.md" ]] || fail "anti-slop skill not copied"
[[ -f "$TMP/py/skills/pstack/SKILL.md" ]] || fail "pstack skill not copied"
[[ -f "$TMP/py/skills/dr-eggbot/SKILL.md" ]] || fail "dr-eggbot skill not copied"
grep -q 'smallest complete change' "$TMP/py/skills/anti-slop/SKILL.md" || fail "anti-slop patterns missing"
grep -q 'gitnexus analyze' "$TMP/py/skills/orient/SKILL.md" || fail "orient missing gitnexus guard"
grep -q 'skills/orient/SKILL.md' "$TMP/py/AGENTS.md" || fail "AGENTS.md missing orient pointer"
grep -q 'skills/anti-slop/SKILL.md' "$TMP/py/AGENTS.md" || fail "AGENTS.md missing anti-slop pointer"
if grep -q 'gitnexus/src' "$TMP/py/skills/orient/SKILL.md"; then
  fail "orient skill looks like vendored GitNexus"
fi
grep -q 'KEEP-LICENSE' "$TMP/py/LICENSE" || fail "LICENSE was overwritten"
[[ -f "$TMP/py/prompt.md" ]] || fail "prompt.md not copied"
grep -q 'https://github.com/kvnloo/PyKit' "$TMP/py/prompt.md" || fail "prompt.md must link to the onboarded repo"
if grep -q '{{REPO_URL}}' "$TMP/py/prompt.md"; then fail "placeholder left in prompt.md"; fi
if grep -q 'x-access-token:' "$TMP/py/prompt.md"; then fail "prompt.md leaked a token"; fi
grep -q 'triage' "$TMP/py/prompt.md" || fail "onboarded prompt.md missing triage branch"
grep -q 'needs-discussion' "$TMP/py/prompt.md" || fail "onboarded prompt.md missing needs-discussion"
grep -q 'triage' "$TMP/py/skills/autodevelop/SKILL.md" || fail "onboarded autodevelop skill missing triage branch"
grep -q 'needs-discussion' "$TMP/py/skills/autodevelop/SKILL.md" || fail "onboarded autodevelop skill missing needs-discussion"
if grep -q 'If nothing is claimable: stop' "$TMP/py/prompt.md"; then fail "empty claimable queue must not be stop-only"; fi
if grep -q 'If nothing is claimable: stop' "$TMP/py/skills/autodevelop/SKILL.md"; then fail "empty claimable queue must not be stop-only in autodevelop"; fi

mkdir -p "$TMP/new"
"$HERE/scripts/init-oss-repo.sh" --new "$TMP/new" --name Smoke --owner kvnloo >/dev/null
[[ -f "$TMP/new/AGENTS.md" ]] || fail "init did not write AGENTS.md"
grep -q 'https://github.com/kvnloo/Smoke' "$TMP/new/prompt.md" || fail "downstream prompt.md must link to itself"
grep -q 'Smoke' "$TMP/new/AGENTS.md" || fail "name not substituted"
[[ ! -f "$TMP/new/.github/workflows/stale.yml" ]] || fail "automation copied without --with-automation"
"$HERE/scripts/init-oss-repo.sh" --target "$TMP/new" --name Smoke --owner kvnloo >/dev/null
grep -q 'Smoke' "$TMP/new/AGENTS.md" || fail "second init clobbered or lost name"

"$HERE/bin/oss-onboard" "$TMP/new" --name Smoke --owner kvnloo >/dev/null || fail "oss-onboard failed"

[[ -f "$TMP/new/.verified-oss-loop/rollout.yml" ]] || fail "rollout.yml missing after onboard"
grep -q 'scheme: rolling' "$TMP/new/.verified-oss-loop/rollout.yml" || fail "default scheme is not rolling"
if grep -q '{{SCHEME}}' "$TMP/new/.verified-oss-loop/rollout.yml"; then fail "placeholder left in rollout.yml"; fi
[[ -f "$TMP/new/.verified-oss-loop/rollout.py" ]] || fail "rollout.py not copied to .verified-oss-loop"
[[ -f "$TMP/new/scripts/rollout.py" ]] || fail "rollout.py not copied to scripts/"
[[ -x "$TMP/new/scripts/ensure-rollout-branches.sh" ]] || fail "ensure-rollout-branches.sh not executable"
[[ "$(python3 "$TMP/new/.verified-oss-loop/rollout.py" --root "$TMP/new" get worker_base)" == nightly ]] \
  || fail "rolling worker_base should be nightly"
python3 "$TMP/new/.verified-oss-loop/rollout.py" --root "$TMP/new" allow-automerge preview \
  || fail "rolling should allow preview automerge"
python3 "$TMP/new/.verified-oss-loop/rollout.py" --root "$TMP/new" allow-automerge nightly \
  || fail "rolling should allow nightly automerge"

mkdir -p "$TMP/stable"
"$HERE/scripts/init-oss-repo.sh" --new "$TMP/stable" --name Stable --owner kvnloo --scheme stable >/dev/null
grep -q 'scheme: stable' "$TMP/stable/.verified-oss-loop/rollout.yml" || fail "stable scheme not written"
[[ "$(python3 "$HERE/scripts/rollout.py" --root "$TMP/stable" get worker_base)" == main ]] \
  || fail "stable worker_base should be main"
if python3 "$HERE/scripts/rollout.py" --root "$TMP/stable" allow-automerge preview; then
  fail "stable must not allow preview automerge"
fi
if python3 "$HERE/scripts/rollout.py" --root "$TMP/stable" allow-promote preview-to-nightly; then
  fail "stable must not allow preview-to-nightly promote"
fi

mkdir -p "$TMP/staged"
"$HERE/scripts/init-oss-repo.sh" --new "$TMP/staged" --name Staged --owner kvnloo --scheme staged >/dev/null
python3 "$HERE/scripts/rollout.py" --root "$TMP/staged" allow-automerge preview \
  || fail "staged should allow preview automerge"
if python3 "$HERE/scripts/rollout.py" --root "$TMP/staged" allow-automerge nightly; then
  fail "staged must not allow nightly automerge"
fi
python3 "$HERE/scripts/rollout.py" --root "$TMP/staged" allow-promote preview-to-nightly \
  || fail "staged should allow operator promote"

if "$HERE/scripts/init-oss-repo.sh" --target "$TMP/bad-scheme" --scheme nope >/dev/null 2>&1; then
  fail "invalid --scheme must fail"
fi

grep -q 'rollout.py' "$TMP/new/AGENTS.md" || fail "onboarded AGENTS.md missing rollout.py"
grep -q 'rollout.py' "$TMP/new/prompt.md" || fail "onboarded prompt.md missing rollout.py"
grep -q 'Never merge `main` or `dev`' "$TMP/new/AGENTS.md" || fail "onboarded AGENTS.md missing main/dev merge guard"

mkdir -p "$TMP/auto"
"$HERE/scripts/init-oss-repo.sh" --new "$TMP/auto" --name Auto --owner kvnloo --with-automation >/dev/null
[[ -f "$TMP/auto/.github/workflows/stale.yml" ]] || fail "automation did not copy stale.yml"
grep -q 'path: .github/workflows/stale.yml' "$TMP/auto/.verified-oss-loop/inventory.yml" \
  || fail "inventory lost leading dot on .github paths"
[[ -f "$TMP/auto/.github/workflows/receipt.yml" ]] || fail "automation did not copy receipt.yml"
[[ -f "$TMP/auto/.github/workflows/claim-expiry.yml" ]] || fail "automation did not copy claim-expiry.yml"
[[ -f "$TMP/auto/.github/workflows/scorecard.yml" ]] || fail "automation did not copy scorecard.yml"
[[ -f "$TMP/auto/.github/dependabot.yml" ]] || fail "automation did not copy dependabot.yml"
[[ -f "$TMP/auto/.github/scripts/create-labels.sh" ]] || fail "create-labels.sh missing"
[[ -f "$TMP/auto/.github/scripts/check-receipt.py" ]] || fail "check-receipt.py missing"
[[ -f "$TMP/auto/.github/scripts/expire-claims.sh" ]] || fail "expire-claims.sh missing"
[[ -x "$TMP/auto/.github/scripts/expire-claims.sh" ]] || fail "expire-claims.sh not executable"
[[ -f "$TMP/auto/.github/workflows/automerge-preview.yml" ]] || fail "automation did not copy automerge-preview.yml"
[[ -f "$TMP/auto/.github/workflows/automerge-nightly.yml" ]] || fail "automation did not copy automerge-nightly.yml"
[[ -f "$TMP/auto/.github/workflows/promote-preview.yml" ]] || fail "automation did not copy promote-preview.yml"
grep -q 'scripts/rollout.py' "$TMP/auto/.github/workflows/automerge-preview.yml" \
  || fail "automerge-preview must call scripts/rollout.py"
[[ ! -f "$TMP/auto/.github/workflows/hitl-publish-origin.yml" ]] \
  || fail "origin-publish workflow must not be dumped onto onboarded repos"
[[ ! -f "$TMP/auto/scripts/publish-origin-from-hitl.py" ]] \
  || fail "origin-publish script must not be dumped onto onboarded repos"
grep -q 'github.event.pull_request.base.ref' "$TMP/auto/.github/workflows/automerge-preview.yml" \
  || fail "automerge must read scheme from the base branch"
if grep -q 'package-ecosystem: npm' "$TMP/auto/.github/dependabot.yml"; then
  fail "dependabot baked a language ecosystem"
fi
grep -q 'Verified OSS Loop' "$HERE/docs/factory.md" || fail "factory adapter missing"
[[ -f "$HERE/HITL.md" ]] || fail "HITL.md missing from kit"
grep -q 'docs/factory.md' "$HERE/HITL.md" || fail "HITL.md must point at docs/factory.md"
grep -q 'github_writes=0' "$HERE/HITL.md" || fail "HITL.md missing github_writes=0 until Todo"
grep -q 'Workers never merge' "$HERE/HITL.md" || fail "HITL.md missing workers-never-merge"
grep -q 'does not set claim priority' "$HERE/HITL.md" || fail "HITL.md must say traction does not set claim priority"
for col in Triage Backlog Todo 'In Progress' 'Ready to Review' 'Maintainer Review' Done Canceled; do
  grep -q "$col" "$HERE/HITL.md" || fail "HITL.md missing Linear column $col"
done
grep -q 'HITL.md' "$HERE/README.md" || fail "README missing HITL.md pointer"
grep -q 'HITL.md' "$HERE/docs/factory.md" || fail "factory adapter must point at kit HITL.md"
if grep -q 'oss-factory/blob/main/factory/HITL.md' "$HERE/docs/factory.md"; then
  fail "factory.md must not send workers to a third-process HITL path"
fi
grep -q 'workers never merge' "$HERE/docs/quality-bots.md" || fail "quality-bots catalog missing protocol rule"
grep -q 'linux-next' "$HERE/docs/quality-at-scale.md" || fail "quality-at-scale missing linux-next mapping"
grep -q 'compute replaces attempts' "$HERE/docs/quality-at-scale.md" || fail "quality-at-scale missing compute principle"
grep -q 'Agent Shin' "$HERE/docs/quality-at-scale.md" || fail "quality-at-scale missing LiteLLM Agent Shin skip"
grep -q 'PolyForm Noncommercial' "$HERE/docs/agent-onboarding.md" || fail "agent-onboarding catalog missing GitNexus license"
grep -q 'oraios/serena' "$HERE/docs/agent-onboarding.md" || fail "agent-onboarding catalog missing Serena"
grep -q 'pstack' "$HERE/docs/agent-onboarding.md" || fail "agent-onboarding catalog missing pstack"
grep -q 'dr-eggbot' "$HERE/docs/agent-onboarding.md" || fail "agent-onboarding catalog missing dr-eggbot"
grep -q -- '--source local' "$HERE/docs/kit-inventory.md" || fail "kit-inventory doc missing local rule"
if grep -q 'x-access-token:' "$HERE/scripts/init-oss-repo.sh"; then
  fail "init must not write credentialed remotes into inventory"
fi
grep -q 'query' "$HERE/docs/agent-onboarding.md" || fail "agent-onboarding catalog missing GitNexus query"
if [[ -d "$HERE/gitnexus" ]] || [[ -d "$HERE/GitNexus" ]]; then
  fail "GitNexus source must not be vendored into this kit"
fi
grep -q 'https://github.com/kvnloo/verified-oss-loop' "$HERE/prompt.md" || fail "kit prompt.md must link to this repo"
grep -q '{{REPO_URL}}' "$HERE/templates/prompt.md" || fail "template prompt.md missing REPO_URL"

python3 "$HERE/scripts/check-receipt.py" --file "$HERE/tests/fixtures/receipt-good.md" \
  --head 1234567890abcdef1234567890abcdef12345678 >/dev/null \
  || fail "good receipt should pass"
if python3 "$HERE/scripts/check-receipt.py" --file "$HERE/tests/fixtures/receipt-good.md" --head deadbeef >/dev/null; then
  fail "good receipt must fail exact-head mismatch"
fi
if python3 "$HERE/scripts/check-receipt.py" --file "$HERE/tests/fixtures/receipt-bad.md" >/dev/null; then
  fail "bad receipt should fail"
fi

for s in "$HERE/scripts/"*.sh "$HERE/bin/oss-onboard" "$HERE/tests/smoke.sh"; do
  bash -n "$s" || fail "bash -n $s"
done
python3 -m json.tool "$HERE/harnesses/stacks.json" >/dev/null || fail "stacks.json"
python3 -m py_compile "$HERE/scripts/check-receipt.py" || fail "check-receipt.py"
python3 -m py_compile "$HERE/scripts/kit-inventory.py" || fail "kit-inventory.py"
python3 -m py_compile "$HERE/scripts/rollout.py" || fail "rollout.py"
python3 -m py_compile "$HERE/scripts/publish-origin-from-hitl.py" || fail "publish-origin-from-hitl.py"
python3 "$HERE/scripts/publish-origin-from-hitl.py" --self-test || fail "publish-origin-from-hitl --self-test"
set +e
python3 "$HERE/scripts/publish-origin-from-hitl.py" --merge >/tmp/hitl-merge.out 2>/tmp/hitl-merge.err
merge_rc=$?
set -e
[[ "$merge_rc" == 2 ]] || fail "--merge must exit 2 (never merge), got $merge_rc"
[[ -f "$HERE/.github/workflows/hitl-publish-origin.yml" ]] || fail "hitl-publish-origin.yml missing"
grep -q 'hitl-maintainer-review' "$HERE/.github/workflows/hitl-publish-origin.yml" \
  || fail "workflow missing event_type hitl-maintainer-review"
grep -q 'HITL_GITHUB_TOKEN' "$HERE/.github/workflows/hitl-publish-origin.yml" \
  || fail "workflow missing HITL_GITHUB_TOKEN"
grep -q 'LINEAR_API_KEY' "$HERE/.github/workflows/hitl-publish-origin.yml" \
  || fail "workflow missing LINEAR_API_KEY"
grep -q 'publish-origin-from-hitl.py' "$HERE/.github/workflows/hitl-publish-origin.yml" \
  || fail "workflow must call publish-origin-from-hitl.py"
if ! grep -q 'scan-maintainer-review' "$HERE/.github/workflows/hitl-publish-origin.yml" && \
   ! grep -q 'schedule:' "$HERE/.github/workflows/hitl-publish-origin.yml"; then
  fail "workflow missing scan-maintainer-review or schedule"
fi
grep -q 'scan-maintainer-review' "$HERE/.github/workflows/hitl-publish-origin.yml" \
  || fail "workflow missing scan-maintainer-review"
grep -q 'schedule:' "$HERE/.github/workflows/hitl-publish-origin.yml" \
  || fail "workflow missing schedule"
if grep -q -- '--issue "${{ inputs.issue }}"' "$HERE/.github/workflows/hitl-publish-origin.yml"; then
  fail "workflow must not interpolate inputs.issue into the run script"
fi
grep -q 'LINEAR_ISSUE_INPUT' "$HERE/.github/workflows/hitl-publish-origin.yml" \
  || fail "workflow must pass issue via LINEAR_ISSUE_INPUT env"
grep -q 'publish-origin-from-hitl.py' "$HERE/HITL.md" || fail "HITL.md missing origin-publish script"
grep -q 'hitl-maintainer-review' "$HERE/HITL.md" || fail "HITL.md missing hitl-maintainer-review"
grep -q 'HITL_GITHUB_TOKEN' "$HERE/HITL.md" || fail "HITL.md missing HITL_GITHUB_TOKEN"
grep -q 'fail closed' "$HERE/HITL.md" || fail "HITL.md missing fail closed"
grep -q 'publish-origin-from-hitl.py' "$HERE/README.md" || fail "README missing origin-publish pointer"
grep -q 'hitl-maintainer-review' "$HERE/docs/factory.md" || fail "factory.md missing hitl-maintainer-review"
grep -q 'publish-origin-from-hitl.py' "$HERE/skills/factory/SKILL.md" \
  || fail "factory skill missing origin-publish pointer"

# Inventory: new kit skills appear; local skills survive; --force does not clobber local
INV="$TMP/new/.verified-oss-loop/inventory.yml"
[[ -f "$INV" ]] || fail "inventory.yml missing after onboard"
[[ "$(python3 "$HERE/scripts/kit-inventory.py" source --root "$TMP/new" --path skills/tdd/SKILL.md)" == kit ]] \
  || fail "tdd should be source=kit"
[[ -f "$TMP/new/skills/pstack/SKILL.md" ]] || fail "pstack pointer skill not copied"
[[ -f "$TMP/new/skills/dr-eggbot/SKILL.md" ]] || fail "dr-eggbot skill not copied"
grep -q 'Workers never merge' "$TMP/new/skills/pstack/SKILL.md" || fail "pstack missing merge guard"
grep -q 'One job' "$TMP/new/skills/dr-eggbot/SKILL.md" || fail "dr-eggbot missing one-job bar"
if grep -q 'subagent_type: "poteto-agent"' "$TMP/new/skills/pstack/SKILL.md"; then
  fail "pstack pointer must not vendor plugin internals"
fi
mkdir -p "$TMP/new/skills/local-bot"
echo 'LOCAL-SKILL' >"$TMP/new/skills/local-bot/SKILL.md"
echo 'KEEP-TDD' >>"$TMP/new/skills/tdd/SKILL.md"
"$HERE/scripts/init-oss-repo.sh" --target "$TMP/new" --name Smoke --owner kvnloo >/dev/null
grep -q 'LOCAL-SKILL' "$TMP/new/skills/local-bot/SKILL.md" || fail "local skill was overwritten"
grep -q 'KEEP-TDD' "$TMP/new/skills/tdd/SKILL.md" || fail "modified kit skill was overwritten without --force"
[[ "$(python3 "$HERE/scripts/kit-inventory.py" source --root "$TMP/new" --path skills/local-bot/SKILL.md)" == local ]] \
  || fail "local-bot should be source=local"
[[ "$(python3 "$HERE/scripts/kit-inventory.py" source --root "$TMP/new" --path skills/tdd/SKILL.md)" == modified ]] \
  || fail "edited tdd should be source=modified"
rm -f "$TMP/new/skills/anti-slop/SKILL.md"
"$HERE/scripts/init-oss-repo.sh" --target "$TMP/new" --name Smoke --owner kvnloo >/dev/null
[[ -f "$TMP/new/skills/anti-slop/SKILL.md" ]] || fail "missing kit skill was not restored"
"$HERE/scripts/init-oss-repo.sh" --target "$TMP/new" --name Smoke --owner kvnloo --force >/dev/null
if grep -q 'KEEP-TDD' "$TMP/new/skills/tdd/SKILL.md"; then
  fail "--force should refresh modified kit tdd"
fi
grep -q 'LOCAL-SKILL' "$TMP/new/skills/local-bot/SKILL.md" || fail "--force overwrote a local skill"
"$HERE/bin/oss-onboard" "$TMP/new" --status >/dev/null || fail "oss-onboard --status failed"

python3 -m py_compile "$HERE/scripts/cluster-similar-issues.py" || fail "cluster-similar-issues.py"
CLUST_JSON="$(python3 "$HERE/scripts/cluster-similar-issues.py" --json "$HERE/tests/fixtures/issues-tiny.json")"
echo "$CLUST_JSON" | python3 -c '
import json,sys
c=json.load(sys.stdin)["clusters"]
sets=[set(x) for x in c]
def has(want):
    return any(want <= s for s in sets)
if not has({101,102,107}):
    raise SystemExit("expected 101/102/107 clustered")
if not has({103,104}):
    raise SystemExit("expected 103/104 clustered")
if not any(s=={108} for s in sets):
    raise SystemExit("108 must stay a singleton")
n=sum(len(s) for s in sets)
if n!=8:
    raise SystemExit("fixture must stay at 8 issues")
'
[[ "$(python3 -c 'import json; print(len(json.load(open("'"$HERE"'/tests/fixtures/issues-tiny.json"))))')" == 8 ]] \
  || fail "issues-tiny.json must have exactly 8 issues"
if python3 "$HERE/scripts/cluster-similar-issues.py" --cap 65 "$HERE/tests/fixtures/issues-tiny.json" >/dev/null 2>&1; then
  fail "cap above 64 must fail"
fi

mkdir -p "$TMP/mature/skills/local-bot" "$TMP/mature/docs"
echo 'KEEP-AGENTS' >"$TMP/mature/AGENTS.md"
echo 'LOCAL-SKILL' >"$TMP/mature/skills/local-bot/SKILL.md"
"$HERE/bin/oss-onboard" "$TMP/mature" --layout mature --name Mature --owner kvnloo >/dev/null \
  || fail "mature onboard failed"
grep -q 'KEEP-AGENTS' "$TMP/mature/AGENTS.md" || fail "mature onboard replaced AGENTS.md"
[[ -f "$TMP/mature/docs/verified-oss-loop.md" ]] || fail "mature onboard missing docs/verified-oss-loop.md"
[[ -d "$TMP/mature/.verified-oss-loop" ]] || fail "mature kit dir missing"
[[ -f "$TMP/mature/.verified-oss-loop/skills/tdd/SKILL.md" ]] || fail "mature kit skills not under .verified-oss-loop"
[[ ! -f "$TMP/mature/skills/tdd/SKILL.md" ]] || fail "mature onboard dumped kit skills over skills/"
grep -q 'LOCAL-SKILL' "$TMP/mature/skills/local-bot/SKILL.md" || fail "mature onboard clobbered source:local skill"
[[ "$(python3 "$HERE/scripts/kit-inventory.py" source --root "$TMP/mature" --path skills/local-bot/SKILL.md)" == local ]] \
  || fail "existing skill should remain source=local"
grep -q -- '--layout mature' "$HERE/docs/verified-oss-loop.md" || fail "kit docs missing mature layout"
grep -q -- '--layout mature' "$HERE/skills/factory/SKILL.md" || fail "factory skill missing mature layout"
grep -q 'cluster-similar-issues.py' "$HERE/README.md" || fail "README missing clustering pointer"

echo "ok"
