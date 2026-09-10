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
grep -q 'KEEP-LICENSE' "$TMP/py/LICENSE" || fail "LICENSE was overwritten"

mkdir -p "$TMP/new"
"$HERE/scripts/init-oss-repo.sh" --new "$TMP/new" --name Smoke --owner kvnloo >/dev/null
[[ -f "$TMP/new/AGENTS.md" ]] || fail "init did not write AGENTS.md"
grep -q 'Smoke' "$TMP/new/AGENTS.md" || fail "name not substituted"
[[ ! -f "$TMP/new/.github/workflows/stale.yml" ]] || fail "automation copied without --with-automation"
"$HERE/scripts/init-oss-repo.sh" --target "$TMP/new" --name Smoke --owner kvnloo >/dev/null
grep -q 'Smoke' "$TMP/new/AGENTS.md" || fail "second init clobbered or lost name"

"$HERE/bin/oss-onboard" "$TMP/new" --name Smoke --owner kvnloo >/dev/null || fail "oss-onboard failed"

mkdir -p "$TMP/auto"
"$HERE/scripts/init-oss-repo.sh" --new "$TMP/auto" --name Auto --owner kvnloo --with-automation >/dev/null
[[ -f "$TMP/auto/.github/workflows/stale.yml" ]] || fail "automation did not copy stale.yml"
[[ -f "$TMP/auto/.github/scripts/create-labels.sh" ]] || fail "create-labels.sh missing"

for s in "$HERE/scripts/"*.sh "$HERE/bin/oss-onboard" "$HERE/tests/smoke.sh"; do
  bash -n "$s" || fail "bash -n $s"
done
python3 -m json.tool "$HERE/harnesses/stacks.json" >/dev/null || fail "stacks.json"

echo "ok"
