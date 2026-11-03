"""Acceptance tests for the factory runtime slice. Offline: fake harness, fictional repos.

Run: python3 -m unittest discover -s tests/acceptance -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path

from helpers import FIXES, ROOT, EnvPatch, Home, git

from runtime import factory
from runtime.ledger import (AlreadySubmitted, CompletionConflict, InvalidEvidence, LaneHeld, Ledger, LeaseHeld,
                            NeedsReconcile, SelfReview, StaleFence)
from runtime.schema import validate
from runtime.verify import verify_exact_head

SCHEMA = json.loads((ROOT / "contracts" / "attempt.schema.json").read_text())
SHA_A = "a" * 40


class Clock:
    def __init__(self, t: float = 1_800_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


def task(ledger: Ledger, tid: str = "alpha-calc#1") -> str:
    return ledger.register_task({"task_id": tid, "repo": "alpha-calc", "issue": "1", "base_revision": SHA_A,
                                 "goal_lock": {"objective": "fix add"}})


class Base(unittest.TestCase):
    mode = "fix"

    def setUp(self):
        self.h = Home()
        self.addCleanup(self.h.close)
        self.envp = EnvPatch(self.h.env(self.mode))
        self.envp.__enter__()
        self.addCleanup(self.envp.__exit__)


class TestTwoReposSharedRoster(Base):
    def test_two_fictional_repos_share_one_builder_and_verifier(self):
        results = [factory.run_task(self.h.home, rid, "1", "fix the failing test", wall_budget=60)
                   for rid in ("alpha-calc", "beta-strings")]
        for r in results:
            self.assertEqual(r["builder"]["state"], "independently_verified", r)
            self.assertEqual(r["verifier"]["verdict"], "APPROVE_EXACT_HEAD")
            self.assertEqual(r["builder"]["head_revision"], r["verifier"]["checked_out"])
        led = self.h.ledger()
        builders = [a for a in led.attempts() if a["role"] == "builder"]
        verifiers = [a for a in led.attempts() if a["role"] == "verifier"]
        self.assertEqual({a["lease_owner"] for a in builders}, {"builder@factory.example"})
        self.assertEqual({a["lease_owner"] for a in verifiers}, {"verifier@factory.example"})
        self.assertEqual({a["native"]["profile"] for a in builders}, {"factory-builder"})
        calls = self.h.invocations()
        self.assertEqual(len(calls), 2)
        self.assertEqual(len({c["in"] for c in calls}), 2, "each repo gets its own isolated worktree")
        for c in calls:
            self.assertNotIn("/repos/", c["in"], "the builder never runs in the source checkout")
        for r in results:
            doc = led.to_contract(r["builder"]["attempt_id"])
            self.assertEqual(validate(doc, SCHEMA), [])


class TestClaimRace(unittest.TestCase):
    def test_one_lease_and_one_submit_under_contention(self):
        tmp = Home()
        self.addCleanup(tmp.close)
        path = tmp.home / "state" / "race.sqlite"
        task(Ledger(path))
        barrier = threading.Barrier(8)
        won, lost = [], []

        def claim(i: int):
            led = Ledger(path)
            barrier.wait()
            try:
                won.append(led.acquire("alpha-calc#1", "builder", f"worker-{i}", 60))
            except LeaseHeld:
                lost.append(i)

        threads = [threading.Thread(target=claim, args=(i,)) for i in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(len(won), 1, f"exactly one lease, got {won}")
        self.assertEqual(len(lost), 7)
        lease = won[0]
        submits, refused = [], []
        barrier2 = threading.Barrier(4)

        def submit():
            led = Ledger(path)
            barrier2.wait()
            try:
                submits.append(led.begin_submit(lease, {"harness": "hermes"}))
            except AlreadySubmitted:
                refused.append(1)

        threads = [threading.Thread(target=submit) for _ in range(4)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual((len(submits), len(refused)), (1, 3))


class TestCrashReconcile(Base):
    mode = "slow"

    def test_crash_after_submit_before_receipt_reconciles_without_resend(self):
        env = {**os.environ, "VOL_FACTORY_CRASH_AT": "after_launch", "FAKE_HERMES_SLEEP": "1"}
        proc = subprocess.run([sys.executable, str(ROOT / "bin" / "vol-factory"), "submit", "--home", str(self.h.home),
                               "--repo", "alpha-calc", "--issue", "7", "--objective", "fix the failing test"],
                              env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 137, proc.stderr)
        led = self.h.ledger()
        [att] = led.attempts()
        self.assertEqual(att["state"], "authorized")
        self.assertIsNone(att["session_id"], "the crash happened before the receipt was stored")
        cfg = factory.load_config(self.h.home / "factory.json")
        adapter = factory.make_adapter(cfg, led, self.h.home)
        for _ in range(100):  # the native run outlives the crashed adapter
            if adapter.observe(att["attempt_id"])["terminal"]:
                break
            time.sleep(0.1)
        out = adapter.reconcile(att["attempt_id"])
        [call] = self.h.invocations()
        self.assertEqual(out["attempt"]["session_id"], call["session_id"], "reconcile found the original admission")
        self.assertEqual(call["intent"], att["submit_intent_id"])
        self.assertEqual(out["attempt"]["state"], "submitted")
        lease = led.acquire(att["task_id"], "builder", "builder@factory.example", 900)  # same owner, same fence
        self.assertEqual(lease.fence, att["fence"])
        with self.assertRaises(AlreadySubmitted):
            led.begin_submit(lease, {"harness": "hermes"})
        self.assertEqual(len(self.h.invocations()), 1, "never re-sent")

    def test_unknown_outcome_stays_reconciling(self):
        led = self.h.ledger()
        cfg = factory.load_config(self.h.home / "factory.json")
        prep = factory.prepare_builder(self.h.home, "alpha-calc", "8", "fix", ledger=led)
        att, _ = led.begin_submit(prep.lease, {"harness": "hermes"})  # intent written, then the process died
        adapter = factory.make_adapter(cfg, led, self.h.home)
        out = adapter.reconcile(att)
        self.assertEqual(out["attempt"]["state"], "reconciling")
        self.assertEqual(self.h.invocations(), [])


class TestStaleFence(unittest.TestCase):
    def setUp(self):
        self.h = Home()
        self.addCleanup(self.h.close)
        self.clock = Clock()
        self.led = Ledger(self.h.home / "state" / "fence.sqlite", clock=self.clock)
        task(self.led)

    def test_stale_fence_cannot_complete_and_replacement_waits_for_revocation(self):
        a = self.led.acquire("alpha-calc#1", "builder", "worker-a", 10)
        att_a, _ = self.led.begin_submit(a, {"harness": "hermes"})
        self.led.bind_native(att_a, "local-a")
        self.clock.t += 30  # lease expired; worker-a may still be running
        with self.assertRaises(StaleFence):
            self.led.complete(att_a, a, {"head_revision": "b" * 40})
        with self.assertRaises(StaleFence):
            self.led.renew(a, 10)
        with self.assertRaises(NeedsReconcile):
            self.led.acquire("alpha-calc#1", "builder", "worker-b", 10)
        self.led.revoke(att_a, {"stopped": True, "pid_alive": False})
        b = self.led.acquire("alpha-calc#1", "builder", "worker-b", 10)
        self.assertGreater(b.fence, a.fence)
        with self.assertRaises(StaleFence):
            self.led.complete(att_a, a, {"head_revision": "b" * 40})
        att_b, _ = self.led.begin_submit(b, {"harness": "hermes"})
        done = self.led.complete(att_b, b, {"head_revision": "c" * 40})
        self.assertEqual(done["state"], "completed")
        self.assertEqual(self.led.complete(att_b, b, {"head_revision": "c" * 40})["result_digest"], done["result_digest"])
        with self.assertRaises(CompletionConflict):
            self.led.complete(att_b, b, {"head_revision": "d" * 40})
        completed = [e for e in self.led.events(att_b) if e["kind"] == "completed"]
        self.assertEqual(len(completed), 1, "idempotent replay adds no second outcome")


class TestHeldNoSubstitution(unittest.TestCase):
    def _run(self, lane_state="available", age=0.0, remove_admission=False):
        h = Home(lane_state=lane_state, admission_age=age)
        self.addCleanup(h.close)
        if remove_admission:
            (h.home / "admission.json").unlink()
        with EnvPatch(h.env("fix")):
            out = factory.run_task(h.home, "alpha-calc", "3", "fix the failing test", wall_budget=60)
        return h, out

    def test_exhausted_lane_holds_without_provider_substitution(self):
        h, out = self._run(lane_state="exhausted")
        self.assertEqual(out["builder"]["state"], "held")
        self.assertEqual(out["builder"]["reason"], "lane_exhausted")
        self.assertEqual(out["builder"]["resume_trigger"], "fictional pool resets at 00:00Z")
        self.assertEqual(h.invocations(), [], "no harness call, and the available paid lane was not used")
        led = h.ledger()
        self.assertEqual(led.held(out["task_id"], "builder")["reason"], "lane_exhausted")
        lease = led.acquire(out["task_id"], "builder", "builder@factory.example", 60)
        with self.assertRaises(LaneHeld):
            led.begin_submit(lease, {"harness": "hermes"})

    def test_stale_and_missing_admission_hold(self):
        h, out = self._run(age=3600)
        self.assertEqual(out["builder"]["reason"], "admission_stale")
        h2, out2 = self._run(remove_admission=True)
        self.assertEqual(out2["builder"]["reason"], "admission_missing")
        self.assertEqual(h.invocations() + h2.invocations(), [])


class TestFabricatedSuccess(Base):
    mode = "fabricate"

    def test_exit_zero_with_failing_test_log_is_rejected(self):
        out = factory.run_task(self.h.home, "alpha-calc", "4", "fix the failing test", wall_budget=60)
        b = out["builder"]
        self.assertEqual(out["observation"]["exit_code"], 0, "the builder claimed success")
        self.assertIn("claimed_success_with_failing_tests", b["evidence"]["builder_claim_problems"])
        self.assertEqual(out["verifier"]["verdict"], "CHANGES_REQUIRED")
        self.assertIn("tests_fail_at_head", out["verifier"]["reasons"])
        self.assertEqual(b["state"], "completed", "never independently_verified")


class TestOutOfScope(Base):
    mode = "cheat"

    def test_editing_the_test_instead_of_the_code_is_rejected(self):
        out = factory.run_task(self.h.home, "alpha-calc", "5", "fix the failing test", wall_budget=60)
        self.assertEqual(out["verifier"]["verdict"], "CHANGES_REQUIRED")
        self.assertTrue(any(r.startswith("out_of_scope_change:test_calc.py") for r in out["verifier"]["reasons"]))
        self.assertNotEqual(out["builder"]["state"], "independently_verified")


class TestShaGuards(unittest.TestCase):
    def setUp(self):
        self.h = Home()
        self.addCleanup(self.h.close)
        self.led = Ledger(self.h.home / "state" / "sha.sqlite")
        task(self.led)

    def test_short_sha_complete_rejected(self):
        lease = self.led.acquire("alpha-calc#1", "builder", "w", 60)
        att, _ = self.led.begin_submit(lease, {"harness": "hermes"})
        with self.assertRaises(InvalidEvidence):
            self.led.complete(att, lease, {"head_revision": "abc1234"})
        self.assertEqual(self.led.attempt(att)["state"], "authorized")

    def test_verifier_rejects_short_and_wrong_sha(self):
        repo = self.h.home / "repos" / "alpha-calc"
        base = git(repo, "rev-parse", "HEAD")
        common = dict(repo=repo, issue="1", base=base, test_cmd=["python3", "-m", "unittest", "-q"],
                      work_root=self.h.home / "work")
        short = verify_exact_head(head=base[:7], **common)
        self.assertEqual((short["verdict"], short["reasons"]), ("CHANGES_REQUIRED", ["head_not_full_sha"]))
        wrong = verify_exact_head(head="0" * 40, **common)
        self.assertEqual((wrong["verdict"], wrong["reasons"]), ("CHANGES_REQUIRED", ["head_not_found"]))

    def test_verdict_for_another_head_is_rejected(self):
        b = self.led.acquire("alpha-calc#1", "builder", "builder@x", 60)
        att, _ = self.led.begin_submit(b, {"harness": "hermes"})
        self.led.complete(att, b, {"head_revision": "c" * 40})
        v = self.led.acquire("alpha-calc#1", "verifier", "verifier@x", 60)
        vatt, _ = self.led.begin_submit(v, {"harness": "local-exec"}, verifies_attempt=att)
        with self.assertRaises(InvalidEvidence):
            self.led.record_verification(att, vatt, v, {"verdict": "APPROVE_EXACT_HEAD", "head_revision": "d" * 40})


class TestSelfReview(unittest.TestCase):
    def test_builder_cannot_verify_itself(self):
        h = Home()
        self.addCleanup(h.close)
        led = Ledger(h.home / "state" / "self.sqlite")
        task(led)
        b = led.acquire("alpha-calc#1", "builder", "same@factory.example", 60)
        att, _ = led.begin_submit(b, {"harness": "hermes"})
        led.complete(att, b, {"head_revision": "c" * 40})
        v = led.acquire("alpha-calc#1", "verifier", "same@factory.example", 60)
        vatt, _ = led.begin_submit(v, {"harness": "local-exec"}, verifies_attempt=att)
        with self.assertRaises(SelfReview):
            led.record_verification(att, vatt, v, {"verdict": "APPROVE_EXACT_HEAD", "head_revision": "c" * 40})
        self.assertEqual(led.attempt(att)["state"], "completed")

    def test_config_refuses_one_principal_for_both_roles(self):
        h = Home()
        self.addCleanup(h.close)
        cfg = dict(h.config)
        cfg["roster"] = {"builder": {"harness": "hermes-builder", "principal": "same"},
                         "verifier": {"kind": "local-exec", "principal": "same"}}
        bad = Path(h.tmp.name) / "bad.json"
        bad.write_text(json.dumps(cfg))
        with self.assertRaises(ValueError):
            factory.load_config(bad)


class TestCancel(Base):
    mode = "hang"

    def test_cancel_owned_process_group_with_readback(self):
        led = self.h.ledger()
        cfg = factory.load_config(self.h.home / "factory.json")
        prep = factory.prepare_builder(self.h.home, "alpha-calc", "9", "fix", ledger=led)
        adapter = factory.make_adapter(cfg, led, self.h.home)
        from runtime import admission
        sub = adapter.submit(prep.lease, prep.worktree, prep.prompt, admission.load(self.h.home / "admission.json"))
        self.assertEqual(sub["state"], "submitted")
        readback = adapter.cancel(sub["attempt_id"], "test_cancel")
        self.assertTrue(readback["stopped"], readback)
        self.assertFalse(readback["pid_alive"])
        self.assertFalse(Path(f"/proc/{readback['pid']}").exists() and
                         open(f"/proc/{readback['pid']}/stat").read().split(")")[-1].split()[0] not in "ZX")
        a = led.attempt(sub["attempt_id"])
        self.assertEqual((a["state"], a["reason"], a["revoked"]), ("held", "revoked", 1))


class TestApplyAndContract(unittest.TestCase):
    def test_fresh_home_apply_then_noop(self):
        h = Home()
        self.addCleanup(h.close)
        self.assertTrue(h.changes)
        cli = [sys.executable, str(ROOT / "bin" / "vol-factory"), "apply", "--home", str(h.home), "--config", str(h.cfg_path)]
        second = subprocess.run(cli, capture_output=True, text=True, check=True)
        self.assertEqual(second.stdout.strip(), "no-op")
        fresh = Path(h.tmp.name) / "fresh-home"
        first = subprocess.run(cli[:4] + [str(fresh), "--config", str(ROOT / "examples" / "factory.example.json")],
                               capture_output=True, text=True, check=True)
        self.assertIn("init", first.stdout)
        again = subprocess.run(cli[:4] + [str(fresh), "--config", str(ROOT / "examples" / "factory.example.json")],
                               capture_output=True, text=True, check=True)
        self.assertEqual(again.stdout.strip(), "no-op")

    def test_example_validates_and_held_needs_resume_trigger(self):
        example = json.loads((ROOT / "contracts" / "examples" / "attempt.example.json").read_text())
        self.assertEqual(validate(example, SCHEMA), [])
        bad = json.loads(json.dumps(example))
        bad["disposition"] = {"state": "held", "reason": "lane_exhausted"}
        self.assertTrue(any("resume_trigger" in e for e in validate(bad, SCHEMA)))
        bad2 = json.loads(json.dumps(example))
        bad2["head_revision"] = "abc1234"
        self.assertTrue(validate(bad2, SCHEMA))

    def test_forbidden_bypass_args_refused(self):
        from adapters.hermes.adapter import HermesAdapter
        h = Home()
        self.addCleanup(h.close)
        cfg = {"profile": "p", "provider": "x", "model": "m", "extra_args": ["--yolo"]}
        with self.assertRaises(ValueError):
            HermesAdapter(cfg, h.ledger(), h.home / "state").build_argv(Path("q"), Path("."))
        with self.assertRaises(ValueError):
            HermesAdapter({"profile": "p", "model": "m"}, h.ledger(), h.home / "state")


if __name__ == "__main__":
    unittest.main()
