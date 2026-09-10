#!/usr/bin/env bash
# Copy community-health + loop templates into a repo.
# Detects stack; does not dump bun scripts into a Python/Rust/Go repo.
# Usage:
#   init-oss-repo.sh --target DIR [--name NAME] [--owner LOGIN] [--repo REPO]
#   init-oss-repo.sh --new DIR [--name NAME] [--owner LOGIN] [--git]
#   Flags: --with-automation  --labels  --force
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATES="$HERE/templates"

TARGET=""
NEW=0
GIT_INIT=0
FORCE=0
AUTOMATION=0
LABELS=0
NAME=""
OWNER=""
REPO=""
UNIT_CMD="unknown"
MUTATOR_CMD="n/a"
RUNTIME_CMD="n/a — project-specific"

usage() {
  sed -n '3,8p' "$0" | sed 's/^# //'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --new) TARGET="$2"; NEW=1; shift 2 ;;
    --name) NAME="$2"; shift 2 ;;
    --owner) OWNER="$2"; shift 2 ;;
    --repo) REPO="$2"; shift 2 ;;
    --git) GIT_INIT=1; shift ;;
    --with-automation) AUTOMATION=1; shift ;;
    --labels) LABELS=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage 0 ;;
    *) echo "unknown arg: $1" >&2; usage 2 ;;
  esac
done

[[ -n "$TARGET" ]] || usage 2
mkdir -p "$TARGET"
TARGET="$(cd "$TARGET" && pwd)"

if [[ "$NEW" -eq 1 && "$GIT_INIT" -eq 1 && ! -d "$TARGET/.git" ]]; then
  git init -q "$TARGET"
fi

if [[ -z "$NAME" ]]; then
  NAME="$(basename "$TARGET")"
fi
if [[ -z "$OWNER" ]]; then
  OWNER="${GITHUB_USER:-}"
  if [[ -z "$OWNER" ]] && git -C "$TARGET" remote get-url origin >/dev/null 2>&1; then
    OWNER="$(git -C "$TARGET" remote get-url origin | sed -E 's#.*[:/]([^/]+)/[^/]+(\.git)?$#\1#')"
  fi
  OWNER="${OWNER:-YOUR_GITHUB_LOGIN}"
fi
if [[ -z "$REPO" ]]; then
  REPO="$NAME"
  if git -C "$TARGET" remote get-url origin >/dev/null 2>&1; then
    REPO="$(git -C "$TARGET" remote get-url origin | sed -E 's#.*[:/][^/]+/([^/]+)(\.git)?$#\1#' | sed 's/\.git$//')"
  fi
fi

sed_escape() {
  printf '%s' "$1" | sed -e 's/[|&\\]/\\&/g'
}

load_stack() {
  local key val
  while IFS= read -r line; do
    key="${line%%=*}"
    val="${line#*=}"
    case "$key" in
      unit_cmd) UNIT_CMD="$val" ;;
      mutator_cmd) MUTATOR_CMD="$val" ;;
    esac
  done < <("$HERE/scripts/detect-stack.sh" "$TARGET")
  if [[ -z "$UNIT_CMD" ]]; then UNIT_CMD="unknown"; fi
  if [[ -z "$MUTATOR_CMD" ]]; then MUTATOR_CMD="n/a"; fi
}

subst() {
  local src="$1" dest="$2"
  local project owner repo unit mut runtime
  project="$(sed_escape "$NAME")"
  owner="$(sed_escape "$OWNER")"
  repo="$(sed_escape "$REPO")"
  unit="$(sed_escape "$UNIT_CMD")"
  mut="$(sed_escape "$MUTATOR_CMD")"
  runtime="$(sed_escape "$RUNTIME_CMD")"
  sed -e "s|{{PROJECT}}|$project|g" \
      -e "s|{{OWNER}}|$owner|g" \
      -e "s|{{REPO}}|$repo|g" \
      -e "s|{{UNIT_CMD}}|$unit|g" \
      -e "s|{{MUTATOR_CMD}}|$mut|g" \
      -e "s|{{MUTATION_CMD}}|$mut|g" \
      -e "s|{{RUNTIME_CMD}}|$runtime|g" \
      "$src" >"$dest"
}

copy_file() {
  local rel="$1"
  local src="$TEMPLATES/$rel"
  local dest="$TARGET/$rel"
  mkdir -p "$(dirname "$dest")"
  if [[ -e "$dest" && "$FORCE" -eq 0 ]]; then
    echo "skip existing: $rel"
    return 0
  fi
  subst "$src" "$dest"
  echo "wrote $rel"
}

load_stack

HEALTH=(
  AGENTS.md
  CONTRIBUTING.md
  SECURITY.md
  roadmap.example.yml
  skills/autodevelop/SKILL.md
  skills/tdd/SKILL.md
  skills/verify/SKILL.md
  .github/PULL_REQUEST_TEMPLATE.md
  .github/ISSUE_TEMPLATE/config.yml
  .github/ISSUE_TEMPLATE/bug.yml
  .github/ISSUE_TEMPLATE/feature.yml
  .github/ISSUE_TEMPLATE/claim.yml
  .github/labels.md
)

for f in "${HEALTH[@]}"; do
  copy_file "$f"
done

if [[ -e "$TARGET/LICENSE" ]]; then
  echo "keep existing: LICENSE"
fi

if [[ "$AUTOMATION" -eq 1 ]]; then
  copy_file .github/labeler.yml
  copy_file .github/workflows/labeler.yml
  copy_file .github/workflows/stale.yml
  copy_file .github/CODEOWNERS
  mkdir -p "$TARGET/.github/scripts"
  if [[ -e "$TARGET/.github/scripts/create-labels.sh" && "$FORCE" -eq 0 ]]; then
    echo "skip existing: .github/scripts/create-labels.sh"
  else
    subst "$TEMPLATES/.github/scripts/create-labels.sh" "$TARGET/.github/scripts/create-labels.sh"
    chmod +x "$TARGET/.github/scripts/create-labels.sh"
    echo "wrote .github/scripts/create-labels.sh"
  fi
fi

if [[ "$LABELS" -eq 1 ]]; then
  if [[ "$AUTOMATION" -eq 0 ]]; then
    mkdir -p "$TARGET/.github/scripts"
    if [[ -e "$TARGET/.github/scripts/create-labels.sh" && "$FORCE" -eq 0 ]]; then
      echo "skip existing: .github/scripts/create-labels.sh"
    else
      subst "$TEMPLATES/.github/scripts/create-labels.sh" "$TARGET/.github/scripts/create-labels.sh"
      chmod +x "$TARGET/.github/scripts/create-labels.sh"
      echo "wrote .github/scripts/create-labels.sh"
    fi
  fi
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    (cd "$TARGET" && bash .github/scripts/create-labels.sh)
  else
    echo "skip labels: gh not authenticated"
  fi
fi

echo
"$HERE/scripts/setup-verify.sh" --root "$TARGET"
echo
echo "next:"
echo "  1. Edit AGENTS.md ownership if this repo has split surfaces"
echo "  2. gh auth + .github/scripts/create-labels.sh  (or rerun with --labels)"
echo "  3. Fill SECURITY.md with a real private contact"
echo "  4. Workers never merge main"
