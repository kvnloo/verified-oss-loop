#!/usr/bin/env bash
# Copy community-health + loop templates into a repo.
# Detects stack; does not dump bun scripts into a Python/Rust/Go repo.
# Usage:
#   init-oss-repo.sh --target DIR [--name NAME] [--owner LOGIN] [--repo REPO]
#   init-oss-repo.sh --new DIR [--name NAME] [--owner LOGIN] [--git]
#   Flags: --with-automation  --with-pages  --labels  --force  --status
#          --scheme rolling|staged|stable  --layout greenfield|mature
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
PAGES=0
NAME=""
OWNER=""
REPO=""
REPO_URL=""
UNIT_CMD="unknown"
MUTATOR_CMD="n/a"
RUNTIME_CMD="n/a — project-specific"
SCHEME="rolling"
LAYOUT="greenfield"

usage() {
  sed -n '3,9p' "$0" | sed 's/^# //'
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
    --with-pages) PAGES=1; shift ;;
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
    --layout)
      LAYOUT="$2"
      case "$LAYOUT" in
        greenfield|mature) ;;
        *) echo "layout must be greenfield or mature" >&2; exit 2 ;;
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

copy_file_as() {
  local dest_rel="$1" src_rel="$2"
  local src="$TEMPLATES/$src_rel"
  local tmp
  tmp="$(mktemp)"
  subst "$src" "$tmp"
  apply_incoming "$dest_rel" "$tmp"
  rm -f "$tmp"
}

copy_raw() {
  local rel="$1" src="$2"
  apply_incoming "$rel" "$src" "${3:-}"
}

load_stack

KIT_SKILLS=(
  skills/autodevelop/SKILL.md
  skills/orient/SKILL.md
  skills/tdd/SKILL.md
  skills/anti-slop/SKILL.md
  skills/pstack/SKILL.md
  skills/dr-eggbot/SKILL.md
  skills/verify/SKILL.md
)

copy_raw .verified-oss-loop/kit-inventory.py "$HERE/scripts/kit-inventory.py"
copy_raw .verified-oss-loop/rollout.py "$HERE/scripts/rollout.py"
copy_file .verified-oss-loop/README.md
copy_file .verified-oss-loop/rollout.yml

if [[ "$LAYOUT" == "mature" ]]; then
  # Kit stays under .verified-oss-loop/. Do not replace a mature AGENTS.md
  # or dump kit skills over existing source:local skills/.
  copy_file docs/verified-oss-loop.md
  for f in "${KIT_SKILLS[@]}"; do
    copy_file_as ".verified-oss-loop/$f" "$f"
  done
  copy_raw .verified-oss-loop/scripts/cluster-similar-issues.py "$HERE/scripts/cluster-similar-issues.py"
else
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
  )
  for f in "${HEALTH[@]}"; do
    copy_file "$f"
  done
  copy_raw scripts/rollout.py "$HERE/scripts/rollout.py"
  copy_raw scripts/ensure-rollout-branches.sh "$HERE/scripts/ensure-rollout-branches.sh" 755
  copy_raw scripts/cluster-similar-issues.py "$HERE/scripts/cluster-similar-issues.py"
fi

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

if [[ "$PAGES" -eq 1 ]]; then
  copy_raw .verified-oss-loop/pages-url-map.py "$HERE/scripts/pages-url-map.py"
  copy_file .verified-oss-loop/pages-url-map.yml
  if [[ "$LAYOUT" == "mature" ]]; then
    copy_raw .verified-oss-loop/scripts/pages-url-map.py "$HERE/scripts/pages-url-map.py"
    copy_file_as .verified-oss-loop/pages-channels.md .github/workflows/pages-channels.md
  else
    copy_raw scripts/pages-url-map.py "$HERE/scripts/pages-url-map.py"
    copy_file .github/workflows/pages-channels.md
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

PAGES_DETECTED=0
if [[ -f "$TARGET/.github/workflows/pages.yml" || -f "$TARGET/.github/workflows/pages.yaml" ]]; then
  PAGES_DETECTED=1
fi
if [[ -f "$TARGET/scripts/build-pages.py" ]]; then
  PAGES_DETECTED=1
fi
if [[ -f "$TARGET/CNAME" ]]; then
  PAGES_DETECTED=1
fi
if [[ -d "$TARGET/.github/workflows" ]]; then
  while IFS= read -r -d '' wf; do
    bn="$(basename "$wf")"
    case "$bn" in
      automerge-preview.yml|automerge-nightly.yml|promote-preview.yml) continue ;;
    esac
    PAGES_DETECTED=1
  done < <(find "$TARGET/.github/workflows" -maxdepth 1 \( -name '*pages*.yml' -o -name '*pages*.yaml' \) -print0 2>/dev/null || true)
fi

PAGES_CHECK_FAIL=0
if [[ "$PAGES" -eq 1 || "$PAGES_DETECTED" -eq 1 ]]; then
  echo "git channels: preview, nightly, dev, main"
  echo "pages map:    main→{base}  nightly→{base}nightly/  preview→{base}next/  features→{base}wip/<slug>/"
  echo "              {base} is / or /${REPO}/ for a project Pages site. preview git ≠ /preview/"
  if [[ "$LAYOUT" == "mature" ]]; then
    echo "check:        python3 .verified-oss-loop/pages-url-map.py check --root ."
  else
    echo "check:        python3 scripts/pages-url-map.py check --root ."
  fi
  echo "branches:     bash scripts/ensure-rollout-branches.sh --root . --push"
fi
if [[ "$PAGES_DETECTED" -eq 1 ]]; then
  echo "warning: this repo looks like it publishes GitHub Pages."
  echo "  Git channel names are not URL paths. Offer: ./bin/oss-onboard DIR --with-pages"
  echo "  docs: https://github.com/kvnloo/verified-oss-loop/blob/main/docs/rollout.md"
fi
if [[ "$PAGES" -eq 1 || "$PAGES_DETECTED" -eq 1 ]]; then
  if ! python3 "$HERE/scripts/pages-url-map.py" check --root "$TARGET"; then
    echo "FAIL: Pages URL map nests a git channel under /preview/ or /nightly/"
    echo "  forbidden: {base}preview/nightly/  {base}preview/preview/"
    echo "  fix: hoist channels (main→{base}, nightly→{base}nightly/, preview→{base}next/, features→{base}wip/<slug>/)"
    if [[ "$PAGES" -eq 1 ]]; then
      PAGES_CHECK_FAIL=1
    fi
  fi
fi

echo "next:"
echo "  1. Edit AGENTS.md ownership if this repo has split surfaces"
echo "  2. gh auth + .github/scripts/create-labels.sh  (or rerun with --labels)"
echo "  3. Fill SECURITY.md with a real private contact"
echo "  4. Protect main and dev (PR + receipt/unit). preview/nightly stay loose. docs/rollout.md"
echo "  5. bash scripts/ensure-rollout-branches.sh --root . --push   (preview, nightly, dev)"
echo "  6. Commit .verified-oss-loop/inventory.yml (kit vs local provenance)"
echo "  7. Workers never merge main or dev"
echo "  8. Pages: git channels are not URL paths. --with-pages copies pages-url-map.py (preview git ≠ /preview/)"
echo "  9. automation yml is inert until a human lands it on origin/main; do not expect promote-preview to run from a feature branch"

if [[ "$PAGES_CHECK_FAIL" -eq 1 ]]; then
  exit 1
fi
