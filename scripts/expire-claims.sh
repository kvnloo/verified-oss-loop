#!/usr/bin/env bash
# Release expired Verified OSS Loop claim leases. Does not merge. Does not close issues.
# Usage: expire-claims.sh [--dry-run] [--max-age-hours 24]
set -euo pipefail

DRY=0
MAX_HOURS=24
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --max-age-hours) MAX_HOURS="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,4p' "$0" | sed 's/^# //'
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if ! command -v gh >/dev/null 2>&1; then
  echo "gh is required" >&2
  exit 1
fi

export VOL_NOW_EPOCH
VOL_NOW_EPOCH="$(date -u +%s)"
export VOL_MAX_AGE_SECS=$((MAX_HOURS * 3600))

lease_state() {
  # JSON comments array on stdin → two lines: yes|no and reason
  # Must not use a python heredoc: that steals stdin from the pipe.
  python3 "$(cd "$(dirname "$0")" && pwd)/claim-lease.py"
}

issues="$(gh issue list --label claimed --state open --limit 100 --json number --jq '.[].number')"
if [[ -z "$issues" ]]; then
  echo "no claimed issues"
  exit 0
fi

released=0
while IFS= read -r num; do
  [[ -n "$num" ]] || continue
  comments="$(gh api "repos/{owner}/{repo}/issues/${num}/comments" --jq '[.[] | {body, createdAt: .created_at}]')"
  result="$(printf '%s' "$comments" | lease_state)"
  expired="$(printf '%s\n' "$result" | sed -n '1p')"
  reason="$(printf '%s\n' "$result" | sed -n '2p')"
  if [[ "$expired" != "yes" ]]; then
    echo "keep #$num ($reason)"
    continue
  fi
  echo "expire #$num ($reason)"
  if [[ "$DRY" -eq 1 ]]; then
    released=$((released + 1))
    continue
  fi
  gh issue edit "$num" --remove-label claimed --add-label claimable >/dev/null
  gh issue comment "$num" --body "Claim lease expired (\`${reason}\`). Returned to \`claimable\`. Workers do not merge. A new claimant may take this issue."
  released=$((released + 1))
done <<<"$issues"

echo "released $released lease(s)"
