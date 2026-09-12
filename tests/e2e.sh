#!/usr/bin/env bash
# Isolated e2e for the onboarding kit. No GitHub writes. No mutator --install.
# Complements tests/smoke.sh (fixtures). This spins temp git repos and runs
# oss-onboard the way a harness would.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() { echo "E2E FAIL: $*" >&2; exit 1; }

onboard() {
  "$HERE/bin/oss-onboard" "$@"
}

# --- YAML: every workflow must parse and must not push main/dev ---
python3 - "$HERE" <<'PY' || fail "workflow yaml / merge-risk check"
import sys, pathlib, re
root = pathlib.Path(sys.argv[1])
try:
    import yaml  # type: ignore
except ImportError:
    yaml = None

bad = []
files = list((root / ".github/workflows").glob("*.yml"))
files += list((root / "templates/.github/workflows").glob("*.yml"))
for p in files:
    text = p.read_text(encoding="utf-8")
    if yaml:
        yaml.safe_load(text)
    if not re.search(r"^name:", text, re.M):
        bad.append(f"{p}: missing name")
    if not re.search(r"^on:", text, re.M):
        bad.append(f"{p}: missing on")
    if not re.search(r"^jobs:", text, re.M):
        bad.append(f"{p}: missing jobs")
    # allow comments; forbid git push of production
    for line in text.splitlines():
        s = line.split("#", 1)[0]
        if re.search(r"git push\s+origin\s+(main|dev)\b", s):
            bad.append(f"{p}: pushes {s.strip()}")
        if re.search(r"gh pr merge.*\b(main|dev)\b", s):
            bad.append(f"{p}: merges into main/dev {s.strip()}")
if bad:
    print("\n".join(bad), file=sys.stderr)
    sys.exit(1)
print("ok: workflow yaml")
PY

# --- receipt unit on kit + copied copy ---
python3 "$HERE/scripts/check-receipt.py" --file "$HERE/tests/fixtures/receipt-good.md" \
  --head 1234567890abcdef1234567890abcdef12345678 >/dev/null \
  || fail "good receipt"
if python3 "$HERE/scripts/check-receipt.py" --file "$HERE/tests/fixtures/receipt-bad.md" >/dev/null; then
  fail "bad receipt should fail"
fi

# --- stacks: detect then onboard ---
mkdir -p "$TMP/py" "$TMP/rs" "$TMP/go" "$TMP/bun" "$TMP/npm" "$TMP/empty"
printf '[project]\nname="e2e"\n' >"$TMP/py/pyproject.toml"
echo 'KEEP' >"$TMP/py/LICENSE"
printf '[package]\nname="x"\nversion="0.0.0"\n' >"$TMP/rs/Cargo.toml"
echo 'module example.com/e2e' >"$TMP/go/go.mod"
echo '{}' >"$TMP/bun/package.json"
touch "$TMP/bun/bun.lock"
echo '{"scripts":{"test":"true"}}' >"$TMP/npm/package.json"
touch "$TMP/npm/package-lock.json"

expect_unit() {
  local dir="$1" want="$2"
  local got
  got="$("$HERE/scripts/detect-stack.sh" "$dir" | awk -F= -v k=unit_cmd '$1==k{print substr($0,index($0,"=")+1)}')"
  [[ "$got" == "$want" ]] || fail "$dir unit_cmd got $got want $want"
}
expect_unit "$TMP/py" "python -m pytest"
expect_unit "$TMP/rs" "cargo test"
expect_unit "$TMP/go" "go test ./..."
expect_unit "$TMP/bun" "bun test"
expect_unit "$TMP/npm" "npm test"

onboard "$TMP/py" --name PyE2E --owner kvnloo --with-automation --with-pages >/dev/null
grep -q 'python -m pytest' "$TMP/py/AGENTS.md" || fail "py unit not pinned"
grep -q 'KEEP' "$TMP/py/LICENSE" || fail "LICENSE overwritten"
[[ -f "$TMP/py/.github/workflows/receipt.yml" ]] || fail "automation missing receipt.yml"
[[ -f "$TMP/py/.github/workflows/automerge-preview.yml" ]] || fail "automerge-preview missing"
[[ -f "$TMP/py/scripts/pages-url-map.py" ]] || fail "--with-pages missing map"
grep -q 'package-ecosystem: github-actions' "$TMP/py/.github/dependabot.yml" || fail "dependabot missing actions"
if grep -q 'package-ecosystem: npm' "$TMP/py/.github/dependabot.yml"; then fail "dependabot baked npm"; fi
grep -q 'https://github.com/kvnloo/PyE2E' "$TMP/py/prompt.md" || fail "prompt URL"
if grep -q 'If nothing is claimable: stop' "$TMP/py/prompt.md"; then fail "onboarded prompt stop-only"; fi
python3 "$TMP/py/.github/scripts/check-receipt.py" --file "$HERE/tests/fixtures/receipt-good.md" \
  --head 1234567890abcdef1234567890abcdef12345678 >/dev/null \
  || fail "copied check-receipt diverged"
grep -q 'allow-automerge preview' "$TMP/py/.github/workflows/automerge-preview.yml" || fail "automerge preview gate"
grep -q 'branches: \[preview\]' "$TMP/py/.github/workflows/automerge-preview.yml" || fail "automerge not limited to preview"
grep -q 'workflow_dispatch' "$TMP/py/.github/workflows/promote-preview.yml" || fail "promote not dispatch"
if grep -q 'git push origin main' "$TMP/py/.github/workflows/promote-preview.yml"; then
  fail "promote pushes main"
fi
"$HERE/scripts/setup-verify.sh" --root "$TMP/py" >/dev/null || fail "setup-verify py"

onboard "$TMP/go" --name GoE2E --owner kvnloo >/dev/null
grep -q 'n/a' "$TMP/go/AGENTS.md" || fail "go mutation should be n/a-ish"
[[ ! -f "$TMP/go/.github/workflows/stale.yml" ]] || fail "automation without flag"

onboard "$TMP/bun" --name BunE2E --owner kvnloo >/dev/null
grep -q 'bun test' "$TMP/bun/AGENTS.md" || fail "bun unit"
if [[ -f "$TMP/bun/Cargo.toml" ]]; then fail "dumped cargo into bun tree"; fi

onboard "$TMP/empty" --name EmptyE2E --owner kvnloo >/dev/null
grep -q 'unknown' "$TMP/empty/AGENTS.md" || fail "empty stack should pin unknown unit"

# --- git channels in a real repo ---
git init -q "$TMP/roll"
git -C "$TMP/roll" checkout -b main
git -C "$TMP/roll" config user.email e2e@example.test
git -C "$TMP/roll" config user.name e2e
echo x >"$TMP/roll/README"
git -C "$TMP/roll" add README
git -C "$TMP/roll" commit -q -m init
git -C "$TMP/roll" remote add origin "$TMP/roll.git"
git init -q --bare "$TMP/roll.git"
git -C "$TMP/roll" push -q origin main
git -C "$TMP/roll" fetch -q origin
onboard "$TMP/roll" --name RollE2E --owner kvnloo --scheme rolling >/dev/null
bash "$TMP/roll/scripts/ensure-rollout-branches.sh" --root "$TMP/roll"
git -C "$TMP/roll" rev-parse --verify preview >/dev/null || fail "rolling missing preview"
git -C "$TMP/roll" rev-parse --verify nightly >/dev/null || fail "rolling missing nightly"
git -C "$TMP/roll" rev-parse --verify dev >/dev/null || fail "rolling missing dev"
[[ "$(git -C "$TMP/roll" rev-parse preview)" == "$(git -C "$TMP/roll" rev-parse origin/main)" ]] \
  || fail "preview not from origin/main"

mkdir -p "$TMP/stable.git" "$TMP/stable"
git init -q --bare "$TMP/stable.git"
git init -q "$TMP/stable"
git -C "$TMP/stable" checkout -b main
git -C "$TMP/stable" config user.email e2e@example.test
git -C "$TMP/stable" config user.name e2e
echo x >"$TMP/stable/README"
git -C "$TMP/stable" add README
git -C "$TMP/stable" commit -q -m init
git -C "$TMP/stable" remote add origin "$TMP/stable.git"
git -C "$TMP/stable" push -q origin main
git -C "$TMP/stable" fetch -q origin
onboard "$TMP/stable" --name StE2E --owner kvnloo --scheme stable >/dev/null
if python3 "$HERE/scripts/rollout.py" --root "$TMP/stable" allow-automerge preview; then
  fail "stable automerge"
fi
out="$(bash "$HERE/scripts/ensure-rollout-branches.sh" --root "$TMP/stable")"
echo "$out" | grep -q 'scheme=stable' || fail "stable ensure should no-op extra channels"
if git -C "$TMP/stable" rev-parse --verify preview >/dev/null 2>&1; then
  fail "stable should not create preview"
fi

# --- pages ---
[[ "$(python3 "$HERE/scripts/pages-url-map.py" path --branch nightly --base /aodl/)" == /aodl/nightly/ ]] \
  || fail "pages nightly"
[[ "$(python3 "$HERE/scripts/pages-url-map.py" path --branch preview --base /aodl/)" == /aodl/next/ ]] \
  || fail "pages preview"
if python3 "$HERE/scripts/pages-url-map.py" check --root "$HERE/tests/fixtures/pages-url-map/bad" >/dev/null 2>&1; then
  fail "pages catch-all should fail"
fi

# --- kit harness: root prompt must not be stop-only (same as onboarded copies) ---
if grep -q 'If nothing is claimable: stop' "$HERE/prompt.md"; then
  fail "kit prompt.md still stop-only; templates/prompt.md already triages"
fi

# --- extra stacks (parallel tester gap vs smoke) ---
mkdir -p "$TMP/rs2" "$TMP/npm2" "$TMP/mixed"
printf '[package]\nname="x"\nversion="0.0.0"\n' >"$TMP/rs2/Cargo.toml"
echo '{}' >"$TMP/npm2/package.json"
touch "$TMP/npm2/package-lock.json"
echo '{}' >"$TMP/mixed/package.json"
touch "$TMP/mixed/bun.lock"
printf '[project]\nname="m"\n' >"$TMP/mixed/pyproject.toml"
onboard "$TMP/rs2" --name RsE2E --owner kvnloo >/dev/null
grep -q 'cargo test' "$TMP/rs2/AGENTS.md" || fail "rust unit not pinned"
onboard "$TMP/npm2" --name NpmE2E --owner kvnloo >/dev/null
grep -q '| `unknown` |' "$TMP/npm2/AGENTS.md" || fail "npm without test script should pin unknown unit"
onboard "$TMP/mixed" --name MixE2E --owner kvnloo >/dev/null
grep -q 'bun test' "$TMP/mixed/AGENTS.md" || fail "mixed bun+py primary should be js/bun"
if "$HERE/bin/oss-onboard" "$TMP/bad-scheme" --scheme nope >/dev/null 2>&1; then
  fail "oss-onboard invalid --scheme must fail"
fi

# --- claim lease: piped JSON must reach python (heredoc would steal stdin) ---
if grep -q 'python3 - <<' "$HERE/scripts/expire-claims.sh"; then
  fail "expire-claims heredoc would steal stdin from piped comments"
fi
[[ -f "$TMP/py/.github/scripts/claim-lease.py" ]] || fail "automation must copy claim-lease.py next to expire-claims.sh"
export VOL_NOW_EPOCH=1700000000
export VOL_MAX_AGE_SECS=86400
expired='[{"body":"claiming for autodevelop\nexpires: 2020-01-01T00:00:00Z","createdAt":"2020-01-01T00:00:00Z"}]'
fresh='[{"body":"claiming for autodevelop\nexpires: 2099-01-01T00:00:00Z","createdAt":"2023-11-14T22:13:20Z"}]'
[[ "$(printf '%s' "$expired" | python3 "$HERE/scripts/claim-lease.py" | sed -n '1p')" == yes ]] \
  || fail "past expires must be expired"
[[ "$(printf '%s' "$fresh" | python3 "$HERE/scripts/claim-lease.py" | sed -n '1p')" == no ]] \
  || fail "future expires must not be expired"
[[ "$(printf '%s' "$expired" | python3 "$TMP/py/.github/scripts/claim-lease.py" | sed -n '1p')" == yes ]] \
  || fail "copied claim-lease.py diverged"
unset VOL_NOW_EPOCH VOL_MAX_AGE_SECS

echo "ok: e2e"
