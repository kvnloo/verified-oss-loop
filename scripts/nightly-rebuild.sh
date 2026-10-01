#!/usr/bin/env bash
# nightly-rebuild.sh: regenerate `nightly` linux-next style.
#
#   nightly = <default branch> + every branch in .nightly/branches, in order.
#
# It is rebuilt from scratch every run and force-pushed. Nothing is ever merged
# FROM nightly. The job only writes refs/heads/<target>, refs/tags/<target>-*
# and (with --save-rerere) refs/heads/nightly-rerere. It never touches the
# default branch or any feature branch.
#
# Usage:
#   scripts/nightly-rebuild.sh [options]
#
# Options:
#   --dry-run, --no-push   build, test and report; push nothing (DEFAULT outside CI)
#   --push                 push even outside CI (CI=true already implies push)
#   --manifest FILE        manifest to use (default: <remote>/<default>:.nightly/branches,
#                          then <remote>/nightly-manifest:.nightly/branches)
#   --remote NAME          remote (default: origin)
#   --default BRANCH       default branch (default: the remote's HEAD)
#   --target BRANCH        branch to rebuild (default: nightly)
#   --test-cmd CMD         full test command     (env NIGHTLY_TEST_CMD)
#   --smoke-cmd CMD        per-branch smoke      (env NIGHTLY_SMOKE_CMD, default = test cmd)
#   --out DIR              report dir (default: <repo>/.nightly-out)
#   --rerere               reuse recorded conflict resolutions from <remote>/nightly-rerere
#   --save-rerere          with --rerere and push: publish the rr-cache back to nightly-rerere
#   --max-rebuilds N       cap on extra test runs when the final tree is red (default 5)
#   --no-fetch             use remote-tracking refs as they are (tests / offline)
#   --keep-worktree        leave the build worktree in place for debugging
#   -h, --help
#
# Environment: DRY_RUN=true forces --dry-run. CI=true switches the default to push.
# NIGHTLY_TEST_TIMEOUT (seconds, default 1800), NIGHTLY_TAG_KEEP_DAYS (default 30).
# NIGHTLY_GH=0 disables the `gh pr list --state merged` graduation check. It
# runs when gh is installed and the remote is on github.com (or NIGHTLY_GH_REPO
# names owner/repo); any gh failure just skips it.
#
# Exit: 0 rebuilt (branches may have been dropped; see the report),
#       1 base red, push rejected, or any other failure (fail closed: nothing pushed),
#       2 usage or manifest error.
#
# Outputs: <out>/report.json, <out>/REPORT.md, <out>/logs/*.log
set -euo pipefail

log() { printf '[nightly] %s\n' "$*" >&2; }
die() { log "FATAL: $*"; exit "${2:-1}"; }
truthy() { case "${1:-}" in 1|true|TRUE|True|yes|on) return 0 ;; *) return 1 ;; esac; }
usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; exit "${1:-0}"; }

REMOTE="${NIGHTLY_REMOTE:-origin}"
DEF="${NIGHTLY_DEFAULT:-}"
TARGET="${NIGHTLY_TARGET:-nightly}"
MANIFEST="${NIGHTLY_MANIFEST:-}"
TEST_CMD="${NIGHTLY_TEST_CMD:-}"
SMOKE_CMD="${NIGHTLY_SMOKE_CMD:-}"
OUT="${NIGHTLY_OUT:-}"
RERERE=0; truthy "${NIGHTLY_RERERE:-}" && RERERE=1
SAVE_RERERE=0
MAX_REBUILDS="${NIGHTLY_MAX_REBUILDS:-5}"
TEST_TIMEOUT="${NIGHTLY_TEST_TIMEOUT:-1800}"
TAG_KEEP_DAYS="${NIGHTLY_TAG_KEEP_DAYS:-30}"
FETCH=1
KEEP_WT=0
PUSH=0
truthy "${CI:-}" && PUSH=1
FORCE_DRY=0
truthy "${DRY_RUN:-}" && FORCE_DRY=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run|--no-push) FORCE_DRY=1; shift ;;
    --push) PUSH=1; shift ;;
    --manifest) MANIFEST="$2"; shift 2 ;;
    --remote) REMOTE="$2"; shift 2 ;;
    --default) DEF="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    --test-cmd) TEST_CMD="$2"; shift 2 ;;
    --smoke-cmd) SMOKE_CMD="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --rerere) RERERE=1; shift ;;
    --save-rerere) SAVE_RERERE=1; shift ;;
    --max-rebuilds) MAX_REBUILDS="$2"; shift 2 ;;
    --no-fetch) FETCH=0; shift ;;
    --keep-worktree) KEEP_WT=1; shift ;;
    -h|--help) usage 0 ;;
    *) log "unknown arg: $1"; usage 2 ;;
  esac
done
# --dry-run always wins over CI / --push.
[[ "$FORCE_DRY" -eq 1 ]] && PUSH=0
[[ -z "$SMOKE_CMD" ]] && SMOKE_CMD="$TEST_CMD"
[[ "$MAX_REBUILDS" =~ ^[0-9]+$ ]] || die "--max-rebuilds must be a number" 2

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || die "not inside a git repository" 2
cd "$REPO_ROOT"
COMMON_DIR="$(cd "$(git rev-parse --git-common-dir)" && pwd)"
OUT="${OUT:-$REPO_ROOT/.nightly-out}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
rm -rf "$OUT/logs"; rm -f "$OUT/report.json" "$OUT/REPORT.md"
mkdir -p "$OUT/logs"
printf '*\n' >"$OUT/.gitignore"   # never committed by accident

STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
START_EPOCH="$(date -u +%s)"
STAMP="$(date -u +%Y%m%d)"
MODE_WORD="dry-run"; [[ "$PUSH" -eq 1 ]] && MODE_WORD="push"

# The runner has no identity by default ("fatal: empty ident name"). Merge
# commits are the bot's, and a fixed date per run makes rebuilds of the same
# branch list produce byte-identical commits.
export GIT_AUTHOR_NAME="${NIGHTLY_GIT_NAME:-github-actions[bot]}"
export GIT_AUTHOR_EMAIL="${NIGHTLY_GIT_EMAIL:-41898282+github-actions[bot]@users.noreply.github.com}"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME" GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"
export GIT_AUTHOR_DATE="@$START_EPOCH +0000" GIT_COMMITTER_DATE="@$START_EPOCH +0000"
export GIT_MERGE_AUTOEDIT=no

# ---------------------------------------------------------------- state
B=(); MODE=(); OWNER=(); NOTE=(); STATUS=(); SHA=(); REASON=(); FILES=(); CW=(); LOGF=()
INCLUDED=()          # indices currently merged into the build, in manifest order
BASE_SHA=""; OLD=""; BASE_TESTS="skipped"; FINAL_GATE="none"; RESULT_SHA=""; RESULT_TREE=""
PUSHED="false"; PUSH_NOTE=""; TAG=""; MANIFEST_SRC=""; OUTCOME="error"; REPORTED=0; WT=""
declare -A TCACHE=() TLOG=()
TESTN=0; LAST_LOG=""; CACHED=0

clean1() { printf '%s' "$1" | tr '\t\n\r' '   '; }

write_report() {
  [[ "$REPORTED" -eq 1 ]] && return 0
  REPORTED=1
  local tsv="$OUT/entries.tsv" i
  : >"$tsv"
  for i in "${!B[@]}"; do
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$(clean1 "${B[$i]}")" "${MODE[$i]}" "$(clean1 "${OWNER[$i]}")" "${STATUS[$i]:-PENDING}" \
      "${SHA[$i]:-}" "$(clean1 "${REASON[$i]:-}")" "$(clean1 "${FILES[$i]:-}")" \
      "$(clean1 "${CW[$i]:-}")" "${LOGF[$i]:-}" "$(clean1 "${NOTE[$i]:-}")" >>"$tsv"
  done
  local url
  url="$(git remote get-url "$REMOTE" 2>/dev/null | sed -E 's#://[^@/]*@#://#' || true)"
  NR_REPO="$url" NR_REMOTE="$REMOTE" NR_DEF="$DEF" NR_BASE="$BASE_SHA" NR_BASE_TESTS="$BASE_TESTS" \
  NR_MODE="$MODE_WORD" NR_TARGET="$TARGET" NR_OLD="$OLD" NR_RESULT="$RESULT_SHA" NR_TREE="$RESULT_TREE" \
  NR_PUSHED="$PUSHED" NR_PUSH_NOTE="$PUSH_NOTE" NR_TAG="$TAG" NR_GATE="$FINAL_GATE" \
  NR_MANIFEST="$MANIFEST_SRC" NR_TEST="$TEST_CMD" NR_SMOKE="$SMOKE_CMD" NR_OUTCOME="$OUTCOME" \
  NR_STARTED="$STARTED" NR_RERERE="$RERERE" \
  python3 - "$tsv" "$OUT" <<'PY' || log "report writer failed"
import json, os, sys, datetime
tsv, out = sys.argv[1], sys.argv[2]
E = os.environ.get
keys = ["branch", "mode", "owner", "status", "sha", "reason", "files", "conflicts_with", "log", "note"]
entries = []
for line in open(tsv, encoding="utf-8"):
    row = dict(zip(keys, line.rstrip("\n").split("\t")))
    row["files"] = row["files"].split() if row["files"] else []
    row["conflicts_with"] = row["conflicts_with"].split() if row["conflicts_with"] else []
    tail = []
    if row["log"] and os.path.isfile(row["log"]):
        with open(row["log"], encoding="utf-8", errors="replace") as fh:
            tail = fh.read().splitlines()[-40:]
        row["log"] = os.path.relpath(row["log"], out)
    row["log_tail"] = tail
    entries.append(row)
counts = {}
for e in entries:
    counts[e["status"]] = counts.get(e["status"], 0) + 1
rep = {
    "schema": "verified-oss-loop.nightly-report.v1",
    "started_at": E("NR_STARTED"),
    "finished_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "repo": E("NR_REPO"), "remote": E("NR_REMOTE"), "target": E("NR_TARGET"),
    "mode": E("NR_MODE"), "outcome": E("NR_OUTCOME"),
    "manifest": E("NR_MANIFEST"),
    "test_cmd": E("NR_TEST") or None, "smoke_cmd": E("NR_SMOKE") or None,
    "rerere": E("NR_RERERE") == "1",
    "base": {"branch": E("NR_DEF"), "sha": E("NR_BASE"), "tests": E("NR_BASE_TESTS")},
    "previous": E("NR_OLD") or None,
    "result": {"sha": E("NR_RESULT") or None, "tree": E("NR_TREE") or None,
               "final_gate": E("NR_GATE"), "pushed": E("NR_PUSHED") == "true",
               "push_note": E("NR_PUSH_NOTE") or None, "tag": E("NR_TAG") or None},
    "counts": counts,
    "entries": entries,
}
with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as fh:
    json.dump(rep, fh, indent=2)
    fh.write("\n")

s = lambda x: (x or "")[:10]
L = [f"# {rep['target']} rebuild: {rep['outcome']}", ""]
L.append(f"- base: `{rep['base']['branch']}@{s(rep['base']['sha'])}` (tests: {rep['base']['tests']})")
res = rep["result"]
if res["sha"]:
    state = "pushed" if res["pushed"] else ("not pushed: " + (res["push_note"] or rep["mode"]))
    L.append(f"- result: `{rep['target']}@{s(res['sha'])}` final gate **{res['final_gate']}**, {state}"
             + (f", tag `{res['tag']}`" if res["tag"] else ""))
L.append(f"- mode: {rep['mode']} · manifest: `{rep['manifest']}` · tests: `{rep['test_cmd'] or 'none (merge-only)'}`")
L.append("")
order = ["MERGED", "WARN", "CONTAINED", "GRADUATED", "GONE", "DROPPED", "PENDING"]
for st in order:
    group = [e for e in entries if e["status"] == st]
    if not group:
        continue
    L.append(f"## {st} ({len(group)})")
    L.append("")
    for e in group:
        line = f"- `{e['branch']}@{s(e['sha']) or '-'}` {e['owner']} ({e['mode']})"
        if e["reason"]:
            line += f": {e['reason']}"
        if e["files"]:
            line += " · files: " + ", ".join(f"`{f}`" for f in e["files"][:12])
        if e["conflicts_with"]:
            line += " · conflicts with: " + ", ".join(f"`{c}`" for c in e["conflicts_with"])
        L.append(line)
        if e["log_tail"] and st in ("DROPPED", "WARN"):
            L.append("  <details><summary>last log lines</summary>\n\n  ```")
            L.extend("  " + t for t in e["log_tail"])
            L.append("  ```\n  </details>")
    L.append("")
stale = [e["branch"] for e in entries if e["status"] in ("GRADUATED", "GONE")]
if stale:
    L.append("**Manifest hygiene:** remove " + ", ".join(f"`{b}`" for b in stale)
             + " from the manifest (already in the default branch, or gone).")
    L.append("")
with open(os.path.join(out, "REPORT.md"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(L) + "\n")
PY
  rm -f "$tsv"
}

on_exit() {
  local rc=$?
  if [[ -n "$WT" && -d "$WT" ]]; then
    if [[ "$KEEP_WT" -eq 1 ]]; then
      log "build worktree kept at $WT"
    else
      git -C "$REPO_ROOT" worktree remove --force "$WT" >/dev/null 2>&1 || rm -rf "$WT"
      git -C "$REPO_ROOT" worktree prune >/dev/null 2>&1 || true
    fi
  fi
  if [[ "$REPORTED" -eq 0 ]]; then
    [[ "$OUTCOME" == "error" ]] && PUSH_NOTE="${PUSH_NOTE:-aborted (rc=$rc); nothing pushed}"
    write_report
  fi
  [[ -f "$OUT/REPORT.md" ]] && log "report: $OUT/REPORT.md"
  exit "$rc"
}
trap on_exit EXIT

# ---------------------------------------------------------------- fetch, refs
if [[ "$FETCH" -eq 1 ]]; then
  log "fetching $REMOTE"
  git fetch --prune --quiet "$REMOTE" "+refs/heads/*:refs/remotes/$REMOTE/*"
fi
if [[ -z "$DEF" ]]; then
  DEF="$(git symbolic-ref --quiet --short "refs/remotes/$REMOTE/HEAD" 2>/dev/null || true)"
  DEF="${DEF#"$REMOTE"/}"
fi
if [[ -z "$DEF" && "$FETCH" -eq 1 ]]; then
  DEF="$(git ls-remote --symref "$REMOTE" HEAD 2>/dev/null | awk '/^ref:/{sub("refs/heads/","",$2); print $2; exit}')"
fi
[[ -n "$DEF" ]] || die "cannot determine the default branch; pass --default" 2
[[ "$DEF" != "$TARGET" ]] || die "target '$TARGET' is the default branch; refusing" 2
git check-ref-format --branch "$TARGET" >/dev/null 2>&1 || die "bad target branch name: $TARGET" 2
BASE_SHA="$(git rev-parse -q --verify "refs/remotes/$REMOTE/$DEF^{commit}")" \
  || die "refs/remotes/$REMOTE/$DEF not found" 2
OLD="$(git rev-parse -q --verify "refs/remotes/$REMOTE/$TARGET^{commit}" || true)"
log "base $DEF@${BASE_SHA:0:10}  previous $TARGET@${OLD:0:10}  mode $MODE_WORD"

# ---------------------------------------------------------------- manifest
MF="$OUT/manifest.effective"
if [[ -n "$MANIFEST" ]]; then
  [[ -f "$MANIFEST" ]] || die "manifest not found: $MANIFEST" 2
  cp "$MANIFEST" "$MF"; MANIFEST_SRC="$MANIFEST"
elif git cat-file -e "refs/remotes/$REMOTE/$DEF:.nightly/branches" 2>/dev/null; then
  git show "refs/remotes/$REMOTE/$DEF:.nightly/branches" >"$MF"; MANIFEST_SRC="$REMOTE/$DEF:.nightly/branches"
elif git cat-file -e "refs/remotes/$REMOTE/nightly-manifest:.nightly/branches" 2>/dev/null; then
  git show "refs/remotes/$REMOTE/nightly-manifest:.nightly/branches" >"$MF"
  MANIFEST_SRC="$REMOTE/nightly-manifest:.nightly/branches"
else
  die "no manifest: add .nightly/branches to $DEF (or a nightly-manifest branch), or pass --manifest" 2
fi
declare -A SEEN=()
lineno=0
while IFS= read -r line || [[ -n "$line" ]]; do
  lineno=$((lineno + 1))
  note=""
  [[ "$line" == *"#"* ]] && note="${line#*#}" && note="${note# }"
  content="${line%%#*}"
  read -r b m o extra <<<"$content" || true
  [[ -z "${b:-}" ]] && continue
  m="${m:-required}"; o="${o:-unknown}"
  [[ -z "${extra:-}" ]] || die "manifest line $lineno: too many fields (branch mode owner # note)" 2
  case "$m" in required|advisory) ;; *) die "manifest line $lineno: mode must be required|advisory, got '$m'" 2 ;; esac
  git check-ref-format --branch "$b" >/dev/null 2>&1 || die "manifest line $lineno: bad branch name '$b'" 2
  [[ "$b" != "$DEF" && "$b" != "$TARGET" ]] || die "manifest line $lineno: '$b' is the default or target branch" 2
  [[ -z "${SEEN[$b]:-}" ]] || die "manifest line $lineno: duplicate entry '$b'" 2
  SEEN[$b]=1
  B+=("$b"); MODE+=("$m"); OWNER+=("$o"); NOTE+=("$note")
done <"$MF"
log "manifest $MANIFEST_SRC: ${#B[@]} entries"

# ---------------------------------------------------------------- build worktree
WT="$(mktemp -d "${TMPDIR:-/tmp}/nightly-build.XXXXXX")"
git worktree add --quiet --detach "$WT" "$BASE_SHA"
GITC=(git -C "$WT" -c rerere.enabled=false)
if [[ "$RERERE" -eq 1 ]]; then
  GITC=(git -C "$WT" -c rerere.enabled=true -c rerere.autoupdate=true)
  RR_REF="refs/remotes/$REMOTE/nightly-rerere"
  if git cat-file -e "$RR_REF:rr-cache" 2>/dev/null; then
    git archive "$RR_REF" rr-cache | tar -x -C "$COMMON_DIR"
    log "restored rr-cache from $REMOTE/nightly-rerere"
  else
    log "rerere on; no $REMOTE/nightly-rerere cache yet"
  fi
fi

wt_clean() { git -C "$WT" reset -q --hard; git -C "$WT" clean -qffd; }

slug() { printf '%s' "$1" | tr -c 'A-Za-z0-9._-' '_' | cut -c1-60; }

# run_cmd KIND LABEL: run the smoke or test command on the worktree HEAD.
# Results are cached by (command, tree), so a tree is never tested twice.
run_cmd() {
  local kind="$1" label="$2" cmd tree key rc=0 logf
  if [[ "$kind" == smoke ]]; then cmd="$SMOKE_CMD"; else cmd="$TEST_CMD"; fi
  LAST_LOG=""; CACHED=1
  [[ -z "$cmd" ]] && return 0
  tree="$(git -C "$WT" rev-parse 'HEAD^{tree}')"
  key="$tree:$(printf '%s' "$cmd" | cksum | cut -d' ' -f1)"
  if [[ -n "${TCACHE[$key]:-}" ]]; then
    LAST_LOG="${TLOG[$key]}"; return "${TCACHE[$key]}"
  fi
  CACHED=0
  TESTN=$((TESTN + 1))
  logf="$OUT/logs/$(printf '%02d' "$TESTN")-$kind-$(slug "$label").log"
  log "$kind: $label"
  local to=()
  command -v timeout >/dev/null 2>&1 && [[ "$TEST_TIMEOUT" != 0 ]] && to=(timeout "$TEST_TIMEOUT")
  (cd "$WT" && "${to[@]}" bash -c "$cmd") >"$logf" 2>&1 </dev/null || rc=$?
  printf '[nightly] %s exited %s on tree %s: %s\n' "$kind" "$rc" "${tree:0:12}" "$cmd" >>"$logf"
  [[ "$rc" -eq 0 ]] || rc=1
  wt_clean
  TCACHE[$key]="$rc"; TLOG[$key]="$logf"; LAST_LOG="$logf"
  return "$rc"
}

# would_run KIND: true when run_cmd on the current tree needs a real run.
would_run() {
  local cmd tree key
  if [[ "$1" == smoke ]]; then cmd="$SMOKE_CMD"; else cmd="$TEST_CMD"; fi
  [[ -z "$cmd" ]] && return 1
  tree="$(git -C "$WT" rev-parse 'HEAD^{tree}')"
  key="$tree:$(printf '%s' "$cmd" | cksum | cut -d' ' -f1)"
  [[ -z "${TCACHE[$key]:-}" ]]
}

CONFLICT_FILES=""; MERGE_ERR=""; RR_USED=0
# merge_entry I: merge entry I into the worktree HEAD. 0 merged, 1 not merged.
merge_entry() {
  local i="$1" un
  CONFLICT_FILES=""; MERGE_ERR=""; RR_USED=0
  if "${GITC[@]}" merge --no-ff --no-edit -q \
       -m "nightly: merge ${B[$i]} @ ${SHA[$i]:0:12}" "${SHA[$i]}" >"$OUT/logs/.merge" 2>&1; then
    return 0
  fi
  un="$(git -C "$WT" diff --name-only --diff-filter=U || true)"
  if [[ -z "$un" ]] && git -C "$WT" rev-parse -q --verify MERGE_HEAD >/dev/null; then
    # rerere resolved every conflict (autoupdate staged it); the tests still judge it.
    if "${GITC[@]}" commit --no-edit -q >>"$OUT/logs/.merge" 2>&1; then RR_USED=1; return 0; fi
  fi
  CONFLICT_FILES="$(printf '%s\n' "$un" | sed '/^$/d' | tr '\n' ' ' | sed 's/ $//')"
  MERGE_ERR="$(grep -m1 -E 'error|fatal' "$OUT/logs/.merge" || true)"
  git -C "$WT" merge --abort >/dev/null 2>&1 || true
  wt_clean
  return 1
}

# rebuild I...: reset to base and merge the given entries. 1 if any fails to merge.
rebuild() {
  git -C "$WT" reset -q --hard "$BASE_SHA"; git -C "$WT" clean -qffd
  local i
  for i in "$@"; do merge_entry "$i" || return 1; done
}

# conflicts_with I: previous included entries (and/or the default branch) whose
# changes touch the files entry I conflicted on.
conflicts_with() {
  local i="$1" j f out=() files=" $CONFLICT_FILES " rc=0
  for j in ${INCLUDED[@]+"${INCLUDED[@]}"}; do
    while IFS= read -r f; do
      [[ -n "$f" && "$files" == *" $f "* ]] && { out+=("${B[$j]}"); break; }
    done < <(git diff --name-only "$BASE_SHA...${SHA[$j]}")
  done
  git merge-tree --write-tree --quiet "$BASE_SHA" "${SHA[$i]}" >/dev/null 2>&1 || rc=$?
  [[ "$rc" -eq 1 ]] && out+=("$DEF")
  printf '%s' "${out[*]:-}"
}

# graduated BRANCH SHA: true when the entry is already in the default branch,
# as opposed to CONTAINED (carried by an earlier manifest entry). Sets GRAD_HOW.
#   1. its tip is an ancestor of the default (merge commit / fast-forward);
#   2. merging it into the default yields the default's own tree (squash- or
#      rebase-merged, or patch-equivalent);
#   3. with gh: a merged PR from BRANCH whose head is exactly SHA (squash-merged,
#      and the default has since moved on the same files, so 2 no longer holds).
BASE_TREE=""
GH_OK=0
GH_REPO="${NIGHTLY_GH_REPO:-}"
if [[ -z "$GH_REPO" ]]; then
  GH_REPO="$(git remote get-url "$REMOTE" 2>/dev/null \
    | sed -nE 's#^(https://([^@/]*@)?github\.com/|git@github\.com:|ssh://git@github\.com/)([^/]+/[^/]+)$#\3#p' \
    | sed -E 's#\.git$##' || true)"
fi
if [[ "${NIGHTLY_GH:-auto}" != 0 && -n "$GH_REPO" ]] && command -v gh >/dev/null 2>&1; then GH_OK=1; fi
GRAD_HOW=""
graduated() {
  local b="$1" sha="$2" mt pr
  GRAD_HOW=""
  if git merge-base --is-ancestor "$sha" "$BASE_SHA"; then GRAD_HOW="ancestor of $DEF"; return 0; fi
  [[ -n "$BASE_TREE" ]] || BASE_TREE="$(git rev-parse "$BASE_SHA^{tree}")"
  if mt="$(git merge-tree --write-tree "$BASE_SHA" "$sha" 2>/dev/null | head -n1)" && [[ "$mt" == "$BASE_TREE" ]]; then
    GRAD_HOW="merging it into $DEF changes nothing: squash-merged or patch-equivalent"; return 0
  fi
  [[ "$GH_OK" -eq 1 ]] || return 1
  pr="$(gh pr list -R "$GH_REPO" --state merged --head "$b" --limit 20 --json number,headRefOid \
          --jq ".[] | select(.headRefOid == \"$sha\") | .number" 2>/dev/null | head -n1 || true)"
  [[ "$pr" =~ ^[0-9]+$ ]] || return 1
  GRAD_HOW="PR #$pr merged at this tip"; return 0
}

# carries J_SHA SHA: every file SHA changes (vs. the default) has the same
# content in J_SHA, i.e. the earlier entry J already carries SHA's change.
carries() {
  local f
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    [[ "$(git rev-parse -q --verify "$1:$f" 2>/dev/null || echo -)" \
       == "$(git rev-parse -q --verify "$2:$f" 2>/dev/null || echo -)" ]] || return 1
  done < <(git diff --name-only "$BASE_SHA...$2")
}

# ---------------------------------------------------------------- 2. base must be green
if run_cmd test "base-$DEF"; then
  [[ -n "$TEST_CMD" ]] && BASE_TESTS="green"
else
  BASE_TESTS="red"; OUTCOME="base-red"; PUSH_NOTE="base red: nightly must never mask a broken core; nothing pushed"
  log "base $DEF is red; aborting without pushing (log: $LAST_LOG)"
  for i in "${!B[@]}"; do STATUS[$i]="PENDING"; done
  exit 1
fi

# ---------------------------------------------------------------- 4. merge each entry
for i in "${!B[@]}"; do
  b="${B[$i]}"
  if ! sha="$(git rev-parse -q --verify "refs/remotes/$REMOTE/$b^{commit}")"; then
    STATUS[$i]="GONE"; REASON[$i]="not on $REMOTE; remove it from the manifest"; continue
  fi
  SHA[$i]="$sha"
  if graduated "$b" "$sha"; then
    STATUS[$i]="GRADUATED"; REASON[$i]="already in $DEF ($GRAD_HOW); remove it from the manifest"; continue
  fi
  if git -C "$WT" merge-base --is-ancestor "$sha" HEAD; then
    by=""
    for j in ${INCLUDED[@]+"${INCLUDED[@]}"}; do
      git merge-base --is-ancestor "$sha" "${SHA[$j]}" && { by="${B[$j]}"; break; }
    done
    STATUS[$i]="CONTAINED"; REASON[$i]="already carried by ${by:-an earlier entry}"; continue
  fi
  pre_tree="$(git -C "$WT" rev-parse 'HEAD^{tree}')"
  if ! merge_entry "$i"; then
    STATUS[$i]="DROPPED"
    if [[ -n "$CONFLICT_FILES" ]]; then
      FILES[$i]="$CONFLICT_FILES"; CW[$i]="$(conflicts_with "$i")"; REASON[$i]="conflict"
    else
      REASON[$i]="merge failed: ${MERGE_ERR:-see logs}"
    fi
    log "DROPPED $b: ${REASON[$i]} ${FILES[$i]:-}"
    continue
  fi
  [[ "$RR_USED" -eq 1 ]] && REASON[$i]="conflict resolved by rerere"
  if [[ "$(git -C "$WT" rev-parse 'HEAD^{tree}')" == "$pre_tree" ]]; then
    # Not in the default (checked above), so earlier entries carry its content.
    git -C "$WT" reset -q --hard HEAD^1
    by=""
    for j in ${INCLUDED[@]+"${INCLUDED[@]}"}; do
      carries "${SHA[$j]}" "$sha" && { by="${B[$j]}"; break; }
    done
    STATUS[$i]="CONTAINED"
    REASON[$i]="patch-equivalent: already carried by ${by:-earlier entries} (merging it changes nothing)"
    continue
  fi
  if run_cmd smoke "$b"; then
    STATUS[$i]="MERGED"
  elif [[ "${MODE[$i]}" == required ]]; then
    git -C "$WT" reset -q --hard HEAD^1
    STATUS[$i]="DROPPED"; REASON[$i]="tests failed"; LOGF[$i]="$LAST_LOG"
    log "DROPPED $b: tests failed ($LAST_LOG)"
    continue
  else
    STATUS[$i]="WARN"; REASON[$i]="tests failed (advisory: kept)"; LOGF[$i]="$LAST_LOG"
  fi
  INCLUDED+=("$i")
  log "${STATUS[$i]} $b"
done

# ---------------------------------------------------------------- 5. final gate
# Advisory entries are allowed to be red. The gate is: the tree with only the
# required entries must be green. If it is not, drop entries (last first) until
# it is, spending at most MAX_REBUILDS real test runs; the base is known green.
mark_dropped() { # idx reason
  STATUS[$1]="DROPPED"; REASON[$1]="$2"
  local keep=() k
  for k in ${INCLUDED[@]+"${INCLUDED[@]}"}; do [[ "$k" == "$1" ]] || keep+=("$k"); done
  INCLUDED=(${keep[@]+"${keep[@]}"})
}
if [[ -n "$TEST_CMD" ]]; then
  if run_cmd test "final"; then
    FINAL_GATE="green"
  else
    FINAL_LOG="$LAST_LOG"
    REQ=(); WARNS=()
    for i in ${INCLUDED[@]+"${INCLUDED[@]}"}; do
      if [[ "${STATUS[$i]}" == WARN ]]; then WARNS+=("$i"); else REQ+=("$i"); fi
    done
    req_green=0
    if [[ ${#WARNS[@]} -gt 0 ]]; then
      if rebuild ${REQ[@]+"${REQ[@]}"}; then
        if run_cmd test "required-only"; then req_green=1; else FINAL_LOG="$LAST_LOG"; fi
      fi
    fi
    if [[ "$req_green" -eq 0 ]]; then
      budget="$MAX_REBUILDS"; culprit=""
      for ((k = ${#REQ[@]} - 1; k >= 0 && budget > 0; k--)); do
        cand=("${REQ[@]:0:k}" "${REQ[@]:k+1}")
        rebuild ${cand[@]+"${cand[@]}"} || continue
        would_run test && budget=$((budget - 1))
        if run_cmd test "without-${B[${REQ[$k]}]}"; then culprit="${REQ[$k]}"; break; fi
      done
      if [[ -n "$culprit" ]]; then
        mark_dropped "$culprit" "final tree red; green without it (interaction with other entries)"
        LOGF[$culprit]="$FINAL_LOG"
      else
        # prefix walk; base (k=0) is cached green.
        for ((k = ${#REQ[@]} - 1; k >= 0; k--)); do
          cand=("${REQ[@]:0:k}")
          rebuild ${cand[@]+"${cand[@]}"} || continue
          if would_run test; then
            [[ "$budget" -gt 0 ]] || continue
            budget=$((budget - 1))
          fi
          if run_cmd test "prefix-$k"; then
            for idx in "${REQ[@]:k}"; do
              mark_dropped "$idx" "final tree red; dropped while bisecting (culprit is among the dropped)"
              LOGF[$idx]="$FINAL_LOG"
            done
            break
          fi
        done
      fi
    fi
    # Reassemble the final tree: surviving entries in manifest order.
    git -C "$WT" reset -q --hard "$BASE_SHA"
    FINAL=(${INCLUDED[@]+"${INCLUDED[@]}"}); INCLUDED=()
    for i in ${FINAL[@]+"${FINAL[@]}"}; do
      if merge_entry "$i"; then INCLUDED+=("$i")
      else STATUS[$i]="DROPPED"; REASON[$i]="conflict after dropping a culprit"; FILES[$i]="$CONFLICT_FILES"; fi
    done
    if run_cmd test "final-rebuilt"; then
      FINAL_GATE="green"
    else
      # Only advisory entries may leave the tree red: verify required-only is green.
      REQ=()
      for i in ${INCLUDED[@]+"${INCLUDED[@]}"}; do [[ "${STATUS[$i]}" == WARN ]] || REQ+=("$i"); done
      HAVE_WARN=$(( ${#INCLUDED[@]} - ${#REQ[@]} ))
      if [[ "$HAVE_WARN" -gt 0 ]] && rebuild ${REQ[@]+"${REQ[@]}"} && run_cmd test "required-only-final"; then
        FINAL_GATE="red-advisory"
        git -C "$WT" reset -q --hard "$BASE_SHA"
        for i in "${INCLUDED[@]}"; do merge_entry "$i" || die "rebuild of a verified list failed to merge"; done
      else
        FINAL_GATE="red"; OUTCOME="final-red"
        PUSH_NOTE="final tree still red after $MAX_REBUILDS rebuilds; nothing pushed"
        die "final tree red and not attributable to advisory entries; not pushing"
      fi
    fi
  fi
fi

RESULT_SHA="$(git -C "$WT" rev-parse HEAD)"
RESULT_TREE="$(git -C "$WT" rev-parse 'HEAD^{tree}')"
git update-ref "refs/nightly/candidate" "$RESULT_SHA"
OUTCOME="rebuilt"

# ---------------------------------------------------------------- 7. publish
if [[ "$PUSH" -eq 0 ]]; then
  PUSH_NOTE="dry-run (local ref refs/nightly/candidate)"
elif [[ -n "$OLD" && "$(git rev-parse "$OLD^{tree}")" == "$RESULT_TREE" ]]; then
  PUSH_NOTE="unchanged: $TARGET already has this tree; nothing to publish"
else
  if [[ -z "$TEST_CMD" ]] && ! truthy "${NIGHTLY_ALLOW_NO_TESTS:-}"; then
    OUTCOME="error"; PUSH_NOTE="no test command; set NIGHTLY_TEST_CMD (or NIGHTLY_ALLOW_NO_TESTS=1)"
    die "$PUSH_NOTE"
  fi
  log "pushing $TARGET (lease ${OLD:0:10})"
  if ! git push --quiet --force-with-lease="refs/heads/$TARGET:$OLD" "$REMOTE" "$RESULT_SHA:refs/heads/$TARGET"; then
    OUTCOME="push-rejected"; PUSH_NOTE="push rejected ($TARGET moved since fetch?)"
    die "$PUSH_NOTE"
  fi
  PUSHED="true"
  TAG="$TARGET-$STAMP"
  git push --quiet "$REMOTE" "+$RESULT_SHA:refs/tags/$TAG" || { log "tag push failed"; TAG=""; }
  if [[ "$TAG_KEEP_DAYS" =~ ^[0-9]+$ && "$TAG_KEEP_DAYS" -gt 0 ]]; then
    cutoff="$(date -u -d "-$TAG_KEEP_DAYS days" +%Y%m%d 2>/dev/null || true)"
    if [[ -n "$cutoff" ]]; then
      old_tags=()
      while read -r _ ref; do
        d="${ref##*-}"
        [[ "$ref" =~ ^refs/tags/$TARGET-[0-9]{8}$ && "$d" < "$cutoff" ]] && old_tags+=("$ref")
      done < <(git ls-remote --tags "$REMOTE" "refs/tags/$TARGET-*" 2>/dev/null)
      if [[ ${#old_tags[@]} -gt 0 ]]; then
        git push --quiet "$REMOTE" --delete "${old_tags[@]}" || log "tag prune failed"
      fi
    fi
  fi
  if [[ "$RERERE" -eq 1 && "$SAVE_RERERE" -eq 1 && -d "$COMMON_DIR/rr-cache" ]]; then
    rrtmp="$(mktemp -d)"; rridx="$(mktemp -u)"
    cp -r "$COMMON_DIR/rr-cache" "$rrtmp/"
    GIT_INDEX_FILE="$rridx" git --work-tree="$rrtmp" add -A .
    rrtree="$(GIT_INDEX_FILE="$rridx" git write-tree)"
    rrold="$(git rev-parse -q --verify "refs/remotes/$REMOTE/nightly-rerere" || true)"
    if [[ -z "$rrold" || "$(git rev-parse "$rrold^{tree}")" != "$rrtree" ]]; then
      rrc="$(git commit-tree "$rrtree" ${rrold:+-p "$rrold"} -m "nightly: rerere cache $STAMP")"
      git push --quiet --force-with-lease="refs/heads/nightly-rerere:$rrold" "$REMOTE" "$rrc:refs/heads/nightly-rerere" \
        || log "rerere cache push failed"
    fi
    rm -rf "$rrtmp" "$rridx"
  fi
fi

write_report
log "done: $OUTCOME, gate $FINAL_GATE, ${PUSH_NOTE:-pushed $TARGET@${RESULT_SHA:0:10}}"
