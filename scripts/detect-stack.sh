#!/usr/bin/env bash
# Detect language/package-manager/test/mutator for a repo root.
# Prints KEY=value lines. Does not install anything.
# Usage: detect-stack.sh [DIR]
set -euo pipefail

ROOT="${1:-.}"
ROOT="$(cd "$ROOT" && pwd)"

has() { [[ -e "$ROOT/$1" ]]; }
file_has() {
  local f="$1" pat="$2"
  [[ -f "$ROOT/$f" ]] && grep -Eq "$pat" "$ROOT/$f"
}

STACKS=()
PKG_MANAGER="none"
TEST_CMD="unknown"
MUTATOR="none"
MUTATOR_CMD="n/a — no mutator for this stack"
UNIT_CMD="unknown"

if has bun.lock || has bun.lockb; then
  STACKS+=(js)
  PKG_MANAGER="bun"
elif has package.json; then
  STACKS+=(js)
  if has pnpm-lock.yaml; then PKG_MANAGER="pnpm"
  elif has yarn.lock; then PKG_MANAGER="yarn"
  elif has package-lock.json; then PKG_MANAGER="npm"
  else PKG_MANAGER="npm"
  fi
fi

if has Cargo.toml; then STACKS+=(rust); fi
if has go.mod; then STACKS+=(go); fi
if has pyproject.toml || has pytest.ini || has setup.cfg || has setup.py || has requirements.txt; then
  STACKS+=(python)
elif has tests/validate.py || compgen -G "$ROOT/tests/*.py" >/dev/null; then
  STACKS+=(python)
fi

if [[ ${#STACKS[@]} -eq 0 ]]; then
  STACKS+=(unknown)
fi

# Prefer an explicit test script, then language defaults.
if has package.json; then
  if file_has package.json '"test"[[:space:]]*:'; then
    case "$PKG_MANAGER" in
      bun) UNIT_CMD="bun test" ;;
      pnpm) UNIT_CMD="pnpm test" ;;
      yarn) UNIT_CMD="yarn test" ;;
      *) UNIT_CMD="npm test" ;;
    esac
    # bun projects often use `bun test` even if npm script exists
    if [[ "$PKG_MANAGER" == "bun" ]]; then
      UNIT_CMD="bun test"
    fi
  elif [[ "$PKG_MANAGER" == "bun" ]]; then
    UNIT_CMD="bun test"
  fi
fi

if printf '%s\n' "${STACKS[@]}" | grep -qx python; then
  if [[ "$UNIT_CMD" == "unknown" ]]; then
    if has tests/validate.py; then
      UNIT_CMD="python3 tests/validate.py"
    else
      UNIT_CMD="python -m pytest"
    fi
  fi
fi

if printf '%s\n' "${STACKS[@]}" | grep -qx rust && [[ "$UNIT_CMD" == "unknown" ]]; then
  UNIT_CMD="cargo test"
fi
if printf '%s\n' "${STACKS[@]}" | grep -qx go && [[ "$UNIT_CMD" == "unknown" ]]; then
  UNIT_CMD="go test ./..."
fi

# Mutator follows the *primary* stack. Mixed repos must pick per-crate.
PRIMARY="${STACKS[0]}"
case "$PRIMARY" in
  js)
    MUTATOR="stryker"
    if [[ "$PKG_MANAGER" == "bun" ]]; then
      MUTATOR_CMD="bunx stryker run"
    else
      MUTATOR_CMD="npx stryker run"
    fi
    ;;
  python)
    MUTATOR="mutmut"
    MUTATOR_CMD="mutmut run"
    ;;
  rust)
    MUTATOR="cargo-mutants"
    MUTATOR_CMD="cargo mutants"
    ;;
  go)
    MUTATOR="none"
    MUTATOR_CMD="n/a — no default Go mutator; use go test / fuzz"
    ;;
esac

TEST_CMD="$UNIT_CMD"

IFS=,
echo "root=$ROOT"
echo "stacks=${STACKS[*]}"
echo "primary=$PRIMARY"
echo "pkg_manager=$PKG_MANAGER"
echo "unit_cmd=$UNIT_CMD"
echo "test_cmd=$TEST_CMD"
echo "mutator=$MUTATOR"
echo "mutator_cmd=$MUTATOR_CMD"
echo "mixed=$([[ ${#STACKS[@]} -gt 1 ]] && echo true || echo false)"
