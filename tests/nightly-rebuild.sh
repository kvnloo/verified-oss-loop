#!/usr/bin/env bash
# Fixture test for scripts/nightly-rebuild.sh. Builds a throwaway origin with
# clean, stacked, conflicting, failing, interacting and advisory branches, runs
# the rebuild, and asserts the report and the pushed refs.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
NR="$HERE/scripts/nightly-rebuild.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fail() { echo "FAIL (nightly-rebuild): $*" >&2; exit 1; }

export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=fixture@example.invalid
export GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=fixture@example.invalid
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
unset CI DRY_RUN NIGHTLY_TEST_CMD NIGHTLY_SMOKE_CMD NIGHTLY_MANIFEST NIGHTLY_GH NIGHTLY_GH_REPO || true

g() { git -C "$TMP/seed" "$@"; }
commit() { g add -A && g commit -qm "$1"; }

git init -q --bare -b main "$TMP/origin.git"
git init -q -b main "$TMP/seed"
g remote add origin "$TMP/origin.git"
printf 'line1\nshared: base\nline3\n' >"$TMP/seed/shared.txt"
# Full test: no FAIL marker, and the two "interaction" halves must not coexist.
cat >"$TMP/seed/check.sh" <<'EOF'
test ! -e FAIL || { echo "FAIL marker present"; exit 1; }
if [ -e INTERACT_X ] && [ -e INTERACT_Y ]; then echo "X and Y interact badly"; exit 1; fi
echo ok
EOF
commit "base"
g push -q origin main

branch() { # name base-ref file content
  g switch -q -c "$1" "$2"
  printf '%s\n' "$4" >"$TMP/seed/$3"
  commit "$1"
  g push -q origin "$1"
  g switch -q main
}
branch feat/a main a.txt a
branch feat/stack-base main s1.txt s1
branch feat/stack-tip feat/stack-base s2.txt s2
g switch -q -c feat/b main; sed -i 's/shared: base/shared: from-b/' "$TMP/seed/shared.txt"; commit b; g push -q origin feat/b; g switch -q main
g switch -q -c feat/c main; sed -i 's/shared: base/shared: from-c/' "$TMP/seed/shared.txt"; commit c; g push -q origin feat/c; g switch -q main
branch feat/bad main FAIL boom
branch feat/x main INTERACT_X x
branch feat/y main INTERACT_Y y
branch feat/adv main FAIL advisory-red
branch feat/grad main grad.txt grad
g merge -q --no-ff feat/grad -m "graduate feat/grad"; g push -q origin main
# Squash-merged: main gets the same change as a new commit (not an ancestor).
branch feat/squashed main sq.txt squashed
printf 'squashed\n' >"$TMP/seed/sq.txt"; commit "feat/squashed (#41)"
# Squash-merged, then main moved on the same file: only the merged PR (gh) knows.
branch feat/squash-moved main sm.txt v1
printf 'v1\n' >"$TMP/seed/sm.txt"; commit "feat/squash-moved (#42)"
printf 'v2\n' >"$TMP/seed/sm.txt"; commit "follow-up on sm.txt"; g push -q origin main
# Same content as feat/a in a different commit: carried by feat/a, not by main.
branch feat/dup-of-a main a.txt a
# Fake gh: PR #42 from feat/squash-moved is merged at its current tip.
mkdir -p "$TMP/bin"
printf '#!/bin/sh\ncase "$*" in *"--head feat/squash-moved "*) echo 42 ;; esac\n' >"$TMP/bin/gh"
chmod +x "$TMP/bin/gh"

MAN="$TMP/branches"
cat >"$MAN" <<'EOF'
# branch            mode      owner
feat/a              required  kevin
feat/stack-tip      required  claude-code   # stack tip first
feat/stack-base     required  claude-code
feat/b              required  kevin
feat/c              required  cursor
feat/bad            required  grok
feat/gone           required  omp
feat/grad           required  kevin
feat/squashed       required  kevin
feat/squash-moved   required  kevin
feat/dup-of-a       required  kevin
feat/x              required  codex
feat/y              required  codex
feat/adv            advisory  muse
EOF

git clone -q "$TMP/origin.git" "$TMP/work"
W="$TMP/work"
before_nightly="$(git -C "$TMP/origin.git" rev-parse -q --verify refs/heads/nightly || echo none)"

# ---- 1. full scenario, dry-run by default (CI unset)
( cd "$W" && PATH="$TMP/bin:$PATH" NIGHTLY_GH_REPO=fixture/repo \
    bash "$NR" --manifest "$MAN" --test-cmd 'bash check.sh' --smoke-cmd 'test ! -e FAIL' ) \
  >"$TMP/run1.log" 2>&1 || { cat "$TMP/run1.log"; fail "scenario 1 exited non-zero"; }
R="$W/.nightly-out/report.json"
[[ -f "$R" && -f "$W/.nightly-out/REPORT.md" ]] || fail "report files missing"
python3 - "$R" <<'PY' || fail "scenario 1 report assertions"
import json, sys
r = json.load(open(sys.argv[1]))
st = {e["branch"]: e for e in r["entries"]}
def want(b, s, sub=""):
    e = st[b]
    assert e["status"] == s, f"{b}: {e['status']} != {s} ({e['reason']})"
    assert sub in e["reason"], f"{b}: reason {e['reason']!r} lacks {sub!r}"
want("feat/a", "MERGED")
want("feat/stack-tip", "MERGED")
want("feat/stack-base", "CONTAINED", "feat/stack-tip")
want("feat/b", "MERGED")
want("feat/c", "DROPPED", "conflict")
assert st["feat/c"]["files"] == ["shared.txt"], st["feat/c"]["files"]
assert st["feat/c"]["conflicts_with"] == ["feat/b"], st["feat/c"]["conflicts_with"]
want("feat/bad", "DROPPED", "tests failed")
assert st["feat/bad"]["log_tail"], "dropped-for-tests entry needs a log tail"
want("feat/gone", "GONE")
want("feat/grad", "GRADUATED", "ancestor")
want("feat/squashed", "GRADUATED", "squash-merged")
want("feat/squash-moved", "GRADUATED", "PR #42")
want("feat/dup-of-a", "CONTAINED", "feat/a")
assert "remove it from the manifest" in st["feat/squashed"]["reason"]
assert "remove it" not in st["feat/dup-of-a"]["reason"], st["feat/dup-of-a"]["reason"]
want("feat/x", "MERGED")
want("feat/adv", "WARN", "advisory")
want("feat/y", "DROPPED", "interaction")
assert r["mode"] == "dry-run", r["mode"]
assert r["result"]["pushed"] is False
assert r["result"]["final_gate"] == "red-advisory", r["result"]["final_gate"]
assert r["base"]["tests"] == "green"
assert r["outcome"] == "rebuilt"
assert st["feat/a"]["owner"] == "kevin" and st["feat/adv"]["mode"] == "advisory"
PY
after_nightly="$(git -C "$TMP/origin.git" rev-parse -q --verify refs/heads/nightly || echo none)"
[[ "$before_nightly" == "$after_nightly" ]] || fail "dry-run pushed nightly"
[[ -z "$(git -C "$TMP/origin.git" tag -l 'nightly-*')" ]] || fail "dry-run pushed a tag"
CAND="$(git -C "$W" rev-parse refs/nightly/candidate)"
for f in a.txt s1.txt s2.txt INTERACT_X FAIL; do
  git -C "$W" cat-file -e "$CAND:$f" 2>/dev/null || fail "candidate missing $f"
done
for f in INTERACT_Y; do
  if git -C "$W" cat-file -e "$CAND:$f" 2>/dev/null; then fail "candidate still has $f"; fi
done
[[ "$(git -C "$W" show "$CAND:shared.txt" | sed -n 2p)" == "shared: from-b" ]] || fail "candidate shared.txt wrong"
[[ -z "$(git -C "$W" worktree list | grep nightly-build || true)" ]] || fail "build worktree left behind"
grep -q '## DROPPED (3)' "$W/.nightly-out/REPORT.md" || fail "REPORT.md missing DROPPED section"
grep -q '## GRADUATED (3)' "$W/.nightly-out/REPORT.md" || fail "REPORT.md missing GRADUATED section"
grep -q 'Manifest hygiene.*feat/squash-moved' "$W/.nightly-out/REPORT.md" || fail "REPORT.md missing hygiene hint"

# ---- 1b. without gh, a squash-merge that main has since edited is not provable: it conflicts
printf 'feat/squash-moved required kevin\n' >"$TMP/m1b"
( cd "$W" && PATH="$TMP/bin:$PATH" NIGHTLY_GH=0 NIGHTLY_GH_REPO=fixture/repo \
    bash "$NR" --manifest "$TMP/m1b" --test-cmd 'bash check.sh' --no-fetch ) >"$TMP/run1b.log" 2>&1 \
  || { cat "$TMP/run1b.log"; fail "scenario 1b exited non-zero"; }
grep -q '"status": "DROPPED"' "$W/.nightly-out/report.json" || fail "NIGHTLY_GH=0 must skip the gh check"
git -C "$W" log --format=%an -1 "$CAND" | grep -q 'github-actions\[bot\]' || fail "merge commits must use the bot identity"

# ---- 2. push mode: green gate, lease replaces an old nightly, tag, then unchanged skip
git -C "$TMP/origin.git" update-ref refs/heads/nightly "$(git -C "$TMP/origin.git" rev-parse feat/bad)"
printf 'feat/a required kevin\nfeat/b required kevin\nfeat/c required cursor\n' >"$TMP/m2"
( cd "$W" && CI=true bash "$NR" --manifest "$TMP/m2" --test-cmd 'bash check.sh' ) >"$TMP/run2.log" 2>&1 \
  || { cat "$TMP/run2.log"; fail "scenario 2 exited non-zero"; }
python3 - "$W/.nightly-out/report.json" <<'PY' || fail "scenario 2 report assertions"
import json, sys
r = json.load(open(sys.argv[1]))
assert r["mode"] == "push" and r["result"]["pushed"] is True, r["result"]
assert r["result"]["final_gate"] == "green"
assert r["result"]["tag"].startswith("nightly-")
assert [e["status"] for e in r["entries"]] == ["MERGED", "MERGED", "DROPPED"]
PY
N="$(git -C "$TMP/origin.git" rev-parse refs/heads/nightly)"
[[ "$N" == "$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["result"]["sha"])' "$W/.nightly-out/report.json")" ]] \
  || fail "origin nightly is not the reported result"
git -C "$TMP/origin.git" merge-base --is-ancestor main "$N" || fail "nightly must be built on main"
if git -C "$TMP/origin.git" merge-base --is-ancestor feat/bad "$N"; then fail "old nightly content survived"; fi
[[ -n "$(git -C "$TMP/origin.git" tag -l 'nightly-*')" ]] || fail "dated tag not pushed"
( cd "$W" && CI=true bash "$NR" --manifest "$TMP/m2" --test-cmd 'bash check.sh' ) >"$TMP/run3.log" 2>&1 \
  || { cat "$TMP/run3.log"; fail "scenario 2b exited non-zero"; }
grep -q '"push_note": "unchanged' "$W/.nightly-out/report.json" || fail "unchanged rebuild must skip the push"
[[ "$(git -C "$TMP/origin.git" rev-parse refs/heads/nightly)" == "$N" ]] || fail "unchanged rebuild moved nightly"

# ---- 3. DRY_RUN beats CI
( cd "$W" && CI=true DRY_RUN=true bash "$NR" --manifest "$MAN" --test-cmd 'bash check.sh' ) >/dev/null 2>&1 \
  || fail "DRY_RUN scenario failed"
[[ "$(git -C "$TMP/origin.git" rev-parse refs/heads/nightly)" == "$N" ]] || fail "DRY_RUN=true pushed"

# ---- 4. base red: abort, exit 1, nothing pushed
set +e
( cd "$W" && CI=true bash "$NR" --manifest "$TMP/m2" --test-cmd 'false' ) >/dev/null 2>&1
rc=$?
set -e
[[ "$rc" == 1 ]] || fail "base red must exit 1, got $rc"
grep -q '"outcome": "base-red"' "$W/.nightly-out/report.json" || fail "base red not reported"
[[ "$(git -C "$TMP/origin.git" rev-parse refs/heads/nightly)" == "$N" ]] || fail "base red pushed"

# ---- 5. manifest errors fail closed with 2
printf 'feat/a sometimes kevin\n' >"$TMP/bad-mode"
set +e
( cd "$W" && bash "$NR" --manifest "$TMP/bad-mode" --test-cmd true ) >/dev/null 2>&1; rc=$?
set -e
[[ "$rc" == 2 ]] || fail "bad mode must exit 2, got $rc"
printf 'feat/a\nfeat/a\n' >"$TMP/dup"
set +e
( cd "$W" && bash "$NR" --manifest "$TMP/dup" --test-cmd true ) >/dev/null 2>&1; rc=$?
set -e
[[ "$rc" == 2 ]] || fail "duplicate entry must exit 2, got $rc"

# ---- 6. manifest read from the default branch
g switch -q main; mkdir -p "$TMP/seed/.nightly"; printf 'feat/a required kevin\n' >"$TMP/seed/.nightly/branches"
commit "add manifest"; g push -q origin main
( cd "$W" && bash "$NR" --test-cmd 'bash check.sh' ) >/dev/null 2>&1 || fail "default-branch manifest run failed"
grep -q '"manifest": "origin/main:.nightly/branches"' "$W/.nightly-out/report.json" || fail "manifest not read from default"

# ---- 7. rerere: a recorded resolution lets a known conflict merge
git -C "$W" config rerere.enabled true
git -C "$W" switch -q -c scratch origin/feat/b
git -C "$W" merge -q origin/feat/c >/dev/null 2>&1 || true
printf 'line1\nshared: from-b-and-c\nline3\n' >"$W/shared.txt"
git -C "$W" add shared.txt; git -C "$W" commit -qm resolve
git -C "$W" switch -q --detach origin/main; git -C "$W" branch -qD scratch
git -C "$W" config --unset rerere.enabled
( cd "$W" && bash "$NR" --manifest "$TMP/m2" --test-cmd 'bash check.sh' --rerere --no-fetch ) >/dev/null 2>&1 \
  || fail "rerere run failed"
python3 - "$W/.nightly-out/report.json" <<'PY' || fail "rerere assertions"
import json, sys
r = json.load(open(sys.argv[1]))
st = {e["branch"]: e for e in r["entries"]}
assert st["feat/c"]["status"] == "MERGED", st["feat/c"]
assert "rerere" in st["feat/c"]["reason"], st["feat/c"]["reason"]
PY

echo "ok nightly-rebuild"
