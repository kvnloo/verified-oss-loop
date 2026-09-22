#!/usr/bin/env bash
# Promote a channel downstream without losing unpushed work.
#
# This is the MANUAL counterpart to .github/workflows/promote-preview.yml. The
# workflow enforces the rollout scheme; this enforces one invariant the scheme
# cannot see: never reset a branch that has unpushed commits.
#
# It exists because that invariant was violated. A hand-run loop did
#
#     git checkout main && git reset --hard origin/main && git merge ... && git push
#
# while `main` held a new commit that had not been pushed. The reset discarded
# it and the merge then promoted the OLD main. The commits survived only in the
# reflog. Four commits were nearly lost to a promotion step that looked like a
# no-op.
#
# Rules enforced here:
#   1. refuse if ANY participating branch has unpushed commits;
#   2. push each target immediately, so the next iteration cannot reset over it;
#   3. treat "already contains" as success rather than creating an empty merge.
#
# Usage:
#   scripts/promote.sh <source> <target> [<target> ...]
#   scripts/promote.sh preview nightly
#   scripts/promote.sh dev nightly main
#
# Verify without promoting:
#   scripts/promote.sh --check preview nightly
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
usage: promote.sh [--check] <source> <target> [<target> ...]

Promotes <source> into each <target> in order. Refuses to run if any
participating branch has unpushed commits. --check reports what would happen
without changing anything.
EOF
  exit 2
}

CHECK=0
if [ "${1:-}" = "--check" ]; then CHECK=1; shift; fi
[ $# -ge 2 ] || usage
SRC="$1"; shift
TARGETS=("$@")

for B in "$SRC" "${TARGETS[@]}"; do
  git rev-parse --verify -q "origin/$B" >/dev/null || { echo "no such channel: $B" >&2; exit 2; }
done

# Rule 1 — the exact condition that caused the loss.
for B in "$SRC" "${TARGETS[@]}"; do
  if git rev-parse --verify -q "$B" >/dev/null; then
    AHEAD=$(git rev-list --count "origin/$B..$B" 2>/dev/null || echo 0)
    if [ "$AHEAD" != "0" ]; then
      echo "refusing: '$B' has $AHEAD unpushed commit(s). push it first." >&2
      git --no-pager log --oneline "origin/$B..$B" >&2 || true
      exit 1
    fi
  fi
done

START_BRANCH=$(git rev-parse --abbrev-ref HEAD)
restore() { git checkout -q "$START_BRANCH" 2>/dev/null || true; }
trap restore EXIT

git fetch -q origin

for TGT in "${TARGETS[@]}"; do
  echo "==> $SRC -> $TGT"
  if git merge-base --is-ancestor "origin/$SRC" "origin/$TGT"; then
    echo "    already contains $SRC; nothing to do"
    continue
  fi
  if [ "$CHECK" = "1" ]; then
    echo "    would merge origin/$SRC into $TGT and push"
    continue
  fi
  git checkout -q "$TGT"
  git reset -q --hard "origin/$TGT"
  git merge --no-ff "origin/$SRC" -m "Promote $SRC into $TGT"
  # Rule 2 — push immediately, so the next iteration cannot reset over this.
  git push origin "$TGT"
  printf '    %s = %s\n' "$TGT" "$(git rev-parse --short HEAD)"
done

[ "$CHECK" = "1" ] && echo "(check only; nothing changed)"
echo "done"
