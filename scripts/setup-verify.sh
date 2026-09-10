#!/usr/bin/env bash
# Print (and optionally install) a TDD/mutation recipe for a detected stack.
# Never copies another project's mutator. Never installs unless --install.
# Usage: setup-verify.sh [--root DIR] [--install]
set -euo pipefail

ROOT="."
INSTALL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --install) INSTALL=1; shift ;;
    -h|--help)
      echo "Usage: $0 [--root DIR] [--install]"
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

HERE="$(cd "$(dirname "$0")" && pwd)"

root=""
stacks=""
primary=""
pkg_manager=""
unit_cmd=""
test_cmd=""
mutator=""
mutator_cmd=""
mixed=""

while IFS= read -r line; do
  key="${line%%=*}"
  val="${line#*=}"
  case "$key" in
    root|stacks|primary|pkg_manager|unit_cmd|test_cmd|mutator|mutator_cmd|mixed)
      printf -v "$key" '%s' "$val"
      ;;
  esac
done < <("$HERE/detect-stack.sh" "$ROOT")

echo "# verify recipe for $root"
echo "primary=$primary stacks=$stacks pkg_manager=$pkg_manager"
echo
echo "## unit (TDD: red, then green)"
echo "$unit_cmd"
echo
echo "## sabotage (optional: break one assertion, expect fail)"
echo "# edit one test, rerun: $unit_cmd"
echo
echo "## mutation"
echo "$mutator_cmd"
if [[ "$mutator" == "none" ]]; then
  echo "# Honest skip. Do not invent a score."
fi
echo
echo "## receipt fields"
cat <<EOF
head_revision: git rev-parse HEAD
tests.red: $unit_cmd
tests.green: $unit_cmd
mutation: $mutator_cmd
EOF

install_js() {
  case "$pkg_manager" in
    bun)
      command -v bun >/dev/null || { echo "install bun first: https://bun.sh" >&2; return 1; }
      bun add -d @stryker-mutator/core
      ;;
    pnpm) pnpm add -D @stryker-mutator/core ;;
    yarn) yarn add -D @stryker-mutator/core ;;
    npm) npm install -D @stryker-mutator/core ;;
    *) echo "unknown js package manager" >&2; return 1 ;;
  esac
}

if [[ "$INSTALL" -eq 1 ]]; then
  echo
  echo "## --install"
  case "$primary" in
    js) install_js ;;
    python)
      echo "python3 -m pip install --user pytest mutmut"
      python3 -m pip install --user pytest mutmut
      ;;
    rust)
      if command -v cargo >/dev/null; then
        cargo install cargo-mutants --locked
      else
        echo "install rustup first" >&2
        exit 1
      fi
      ;;
    go)
      echo "no mutator to install; use go test ./..."
      ;;
    *)
      echo "unknown stack; refusing to guess a mutator" >&2
      exit 1
      ;;
  esac
fi
