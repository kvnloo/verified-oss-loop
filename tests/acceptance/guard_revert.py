#!/usr/bin/env python3
"""Prove each acceptance test guards something: remove one guard in a scratch copy, expect the
named test to FAIL, and expect it to PASS on the untouched copy.

  python3 tests/acceptance/guard_revert.py            # all guards
  python3 tests/acceptance/guard_revert.py self-review

Exit 0 only when every guard's test fails with the guard removed.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# guard name -> (file, exact guard code, replacement that disables it, test id)
GUARDS = {
    "claim-race": ("runtime/ledger.py", 'if row and row["owner"] and row["expires_at"] > now:', "if False:",
                   "test_factory_runtime.TestClaimRace"),
    "stale-fence": ("runtime/ledger.py",
                    'if not row or row["owner"] != lease.owner or row["fence"] != lease.fence or row["expires_at"] <= self.clock():',
                    "if False:", "test_factory_runtime.TestStaleFence"),
    "no-resend": ("runtime/ledger.py", "            if prior:\n", "            if False:\n",
                  "test_factory_runtime.TestCrashReconcile.test_crash_after_submit_before_receipt_reconciles_without_resend"),
    "full-sha": ("runtime/ledger.py", "if head and not FULL_SHA.match(head):", "if False:",
                 "test_factory_runtime.TestShaGuards.test_short_sha_complete_rejected"),
    "verifier-full-sha": ("runtime/verify.py", "if not FULL_SHA.match(head):", "if False:",
                          "test_factory_runtime.TestShaGuards.test_verifier_rejects_short_and_wrong_sha"),
    "self-review": ("runtime/ledger.py",
                    'if v["lease_owner"] == b["lease_owner"] or (v["session_id"] and v["session_id"] == b["session_id"]):',
                    "if False:", "test_factory_runtime.TestSelfReview.test_builder_cannot_verify_itself"),
    "no-substitution": ("adapters/hermes/adapter.py", 'if decision["decision"] != "allow":', "if False:",
                        "test_factory_runtime.TestHeldNoSubstitution.test_exhausted_lane_holds_without_provider_substitution"),
    "verifier-reruns": ("runtime/verify.py", 'green = _run_tests(green_dir, test_cmd, timeout, logs / "green.log")',
                        "green = 0", "test_factory_runtime.TestFabricatedSuccess"),
}


def run_test(tree: Path, test: str) -> int:
    return subprocess.run([sys.executable, "-m", "unittest", "-q", test], cwd=tree / "tests" / "acceptance",
                          capture_output=True, text=True, timeout=300).returncode


def copy_tree(dst: Path) -> Path:
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    return dst


def main(names: list[str]) -> int:
    names = names or list(GUARDS)
    ok = True
    with tempfile.TemporaryDirectory(prefix="vol-guard-") as tmp:
        for name in names:
            path, code, repl, test = GUARDS[name]
            base = copy_tree(Path(tmp) / f"{name}-base")
            src = (base / path).read_text()
            if src.count(code) != 1:
                print(f"{name}: guard code not found exactly once in {path}")
                ok = False
                continue
            passed = run_test(base, test) == 0
            broken = copy_tree(Path(tmp) / f"{name}-reverted")
            (broken / path).write_text(src.replace(code, repl))
            failed = run_test(broken, test) != 0
            verdict = "PROVEN" if passed and failed else "NOT PROVEN"
            ok &= passed and failed
            print(f"{name:18} test={'pass' if passed else 'FAIL'} with-guard  "
                  f"{'fail' if failed else 'PASS'} guard-removed  -> {verdict}  ({test})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
