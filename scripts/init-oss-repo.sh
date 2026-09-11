#!/usr/bin/env bash
# Copy community-health + loop templates into a repo.
# Detects stack; does not dump bun scripts into a Python/Rust/Go repo.
# Usage:
#   init-oss-repo.sh --target DIR [--name NAME] [--owner LOGIN] [--repo REPO]
#   init-oss-repo.sh --new DIR [--name NAME] [--owner LOGIN] [--git]
#   Flags: --with-automation  --labels  --force  --status  --scheme rolling|staged|stable
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATES="$HERE/templates"

TARGET=""
NEW=0
GIT_INIT=0
FORCE=0
STATUS=0
AUTOMATION=0
LABELS=0
NAME=""
OWNER=""
REPO=""
REPO_URL=""
UNIT_CMD="unknown"
MUTATOR_CMD="n/a"
RUNTIME_CMD="n/a — project-specific"
SCHEME="rolling"

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
    --status) STATUS=1; shift ;;
    --scheme)
      SCHEME="$2"
      case "$SCHEME" in
        rolling|staged|stable) ;;
        *) echo "scheme must be rolling, staged, or stable" >&2; exit 2 ;;
      esac
      shift 2
      ;;
    -h|--help) usage 0 ;;
    *) echo "unknown arg: $1" >&2; usage 2 ;;
  esac
done

[[ -n "$TARGET" ]] || usage 2
if [[ "$STATUS" -eq 1 ]]; then
  TARGET="$(cd "$TARGET" && pwd)"
  python3 "$HERE/scripts/kit-inventory.py" show --root "$TARGET"
  exit $?
fi
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
# Public clone URL only. Never copy origin (it may contain a token).
REPO_URL="https://github.com/${OWNER}/${REPO}"

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
  local project owner repo unit mut runtime url scheme
  project="$(sed_escape "$NAME")"
  owner="$(sed_escape "$OWNER")"
  repo="$(sed_escape "$REPO")"
  unit="$(sed_escape "$UNIT_CMD")"
  mut="$(sed_escape "$MUTATOR_CMD")"
  runtime="$(sed_escape "$RUNTIME_CMD")"
  url="$(sed_escape "$REPO_URL")"
  scheme="$(sed_escape "$SCHEME")"
  sed -e "s|{{PROJECT}}|$project|g" \
      -e "s|{{OWNER}}|$owner|g" \
      -e "s|{{REPO}}|$repo|g" \
      -e "s|{{REPO_URL}}|$url|g" \
      -e "s|{{SCHEME}}|$scheme|g" \
      -e "s|{{UNIT_CMD}}|$unit|g" \
      -e "s|{{MUTATOR_CMD}}|$mut|g" \
      -e "s|{{MUTATION_CMD}}|$mut|g" \
      -e "s|{{RUNTIME_CMD}}|$runtime|g" \
      "$src" >"$dest"
}

INVPY="$HERE/scripts/kit-inventory.py"
SESSION="$(mktemp)"
KIT_PATHS="$(mktemp)"
cleanup_session() { rm -f "$SESSION" "$KIT_PATHS"; }
trap cleanup_session EXIT

KIT_REV="unknown"
if git -C "$HERE" rev-parse HEAD >/dev/null 2>&1; then
  KIT_REV="$(git -C "$HERE" rev-parse HEAD)"
fi
KIT_URL="https://github.com/kvnloo/verified-oss-loop"

APPLY_FORCE=()
if [[ "$FORCE" -eq 1 ]]; then
  APPLY_FORCE=(--force)
fi

note_kit_path() {
  printf '%s\n' "$1" >>"$KIT_PATHS"
}

apply_incoming() {
  local rel="$1" incoming="$2"
  local chmod_args=()
  if [[ "${3:-}" != "" ]]; then
    chmod_args=(--chmod "$3")
  fi
  note_kit_path "$rel"
  python3 "$INVPY" apply --root "$TARGET" --path "$rel" --incoming "$incoming" \
    --session "$SESSION" "${APPLY_FORCE[@]}" "${chmod_args[@]}"
}

copy_file() {
  local rel="$1"
  local src="$TEMPLATES/$rel"
  local tmp
  tmp="$(mktemp)"
  subst "$src" "$tmp"
  apply_incoming "$rel" "$tmp"
  rm -f "$tmp"
}

copy_raw() {
  local rel="$1" src="$2"
  apply_incoming "$rel" "$src" "${3:-}"
}

load_stack

HEALTH=(
  AGENTS.md
  CONTRIBUTING.md
  SECURITY.md
  prompt.md
  roadmap.example.yml
  skills/autodevelop/SKILL.md
  skills/orient/SKILL.md
  skills/tdd/SKILL.md
  skills/anti-slop/SKILL.md
  skills/pstack/SKILL.md
  skills/dr-eggbot/SKILL.md
  skills/verify/SKILL.md
  .github/PULL_REQUEST_TEMPLATE.md
  .github/ISSUE_TEMPLATE/config.yml
  .github/ISSUE_TEMPLATE/bug.yml
  .github/ISSUE_TEMPLATE/feature.yml
  .github/ISSUE_TEMPLATE/claim.yml
  .github/labels.md
  .verified-oss-loop/README.md
  .verified-oss-loop/rollout.yml
)

for f in "${HEALTH[@]}"; do
  copy_file "$f"
done

copy_raw .verified-oss-loop/kit-inventory.py "$HERE/scripts/kit-inventory.py"
copy_raw .verified-oss-loop/rollout.py "$HERE/scripts/rollout.py"
copy_raw scripts/rollout.py "$HERE/scripts/rollout.py"
copy_raw scripts/ensure-rollout-branches.sh "$HERE/scripts/ensure-rollout-branches.sh" 755

if [[ -e "$TARGET/LICENSE" ]]; then
  echo "keep existing: LICENSE"
fi

if [[ "$AUTOMATION" -eq 1 ]]; then
  copy_file .github/labeler.yml
  copy_file .github/workflows/labeler.yml
  copy_file .github/workflows/stale.yml
  copy_file .github/workflows/receipt.yml
  copy_file .github/workflows/claim-expiry.yml
  copy_file .github/workflows/scorecard.yml
  copy_file .github/dependabot.yml
  copy_file .github/CODEOWNERS
  copy_file .github/scripts/create-labels.sh
  copy_file .github/workflows/automerge-preview.yml
  copy_file .github/workflows/automerge-nightly.yml
  copy_file .github/workflows/promote-preview.yml
  if [[ -f "$TARGET/.github/scripts/create-labels.sh" ]]; then
    chmod +x "$TARGET/.github/scripts/create-labels.sh"
  fi
  copy_raw .github/scripts/check-receipt.py "$HERE/scripts/check-receipt.py"
  copy_raw .github/scripts/expire-claims.sh "$HERE/scripts/expire-claims.sh" 755
fi

if [[ "$LABELS" -eq 1 && "$AUTOMATION" -eq 0 ]]; then
  copy_file .github/scripts/create-labels.sh
  if [[ -f "$TARGET/.github/scripts/create-labels.sh" ]]; then
    chmod +x "$TARGET/.github/scripts/create-labels.sh"
  fi
fi

python3 "$INVPY" finalize --root "$TARGET" --session "$SESSION" --kit-paths "$KIT_PATHS" \
  --kit-revision "$KIT_REV" --kit-url "$KIT_URL"

if [[ "$LABELS" -eq 1 ]]; then
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
echo "  4. Protect main and dev (PR + receipt/unit). preview/nightly stay loose. docs/rollout.md"
echo "  5. bash scripts/ensure-rollout-branches.sh --root . --push   (preview, nightly, dev)"
echo "  6. Commit .verified-oss-loop/inventory.yml (kit vs local provenance)"
echo "  7. Workers never merge main or dev"
