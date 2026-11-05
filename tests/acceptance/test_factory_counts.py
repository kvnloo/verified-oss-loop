"""Read-only receipt export, including an offline native-adapter CLI round trip."""
from __future__ import annotations

import json
import runpy
import subprocess
import sys
import unittest

from helpers import ROOT, EnvPatch, Home

SCRIPT = ROOT / "scripts" / "factory-counts.py"
SHA = "a" * 40


class TestFactoryCounts(unittest.TestCase):
    def setUp(self):
        self.h = Home()
        self.addCleanup(self.h.close)

    def export(self, *repos):
        return runpy.run_path(str(SCRIPT))["snapshot"](self.h.home, repos)

    def builder(self):
        led = self.h.ledger()
        led.register_task({"task_id": "alpha-calc#1", "repo": "alpha-calc", "issue": "1",
                           "base_revision": SHA, "goal_lock": {"objective": "fixture"}})
        lease = led.acquire("alpha-calc#1", "builder", "builder@fixture.invalid", 60)
        attempt, _ = led.begin_submit(lease, {"harness": "hermes"})
        return led, lease, attempt

    def test_pending_intent_is_not_a_send_or_queued_task(self):
        _, _, attempt = self.builder()
        result = self.export("not-registered")
        self.assertEqual(result["repos"]["alpha-calc"]["counts"],
                         {"queued": 0, "sent": 0, "returned": 0, "tested": 0, "merged": None})
        self.assertEqual(result["unresolved_attempts"], [attempt])
        self.assertFalse(result["repos"]["not-registered"]["registered"])

    def test_registered_task_without_attempt_counts_as_queued(self):
        led = self.h.ledger()
        led.register_task({"task_id": "alpha-calc#1", "repo": "alpha-calc", "issue": "1",
                           "base_revision": SHA, "goal_lock": {"objective": "fixture"}})
        self.assertEqual(self.export()["repos"]["alpha-calc"]["counts"]["queued"], 1)

    def test_revoked_session_is_sent_but_not_a_completed_return(self):
        led, _, attempt = self.builder()
        led.bind_native(attempt, "fixture-session")
        led.revoke(attempt, {"stopped": True})
        result = self.export()
        self.assertEqual(result["repos"]["alpha-calc"]["counts"],
                         {"queued": 0, "sent": 1, "returned": 0, "tested": 0, "merged": None})
        self.assertEqual(result["unresolved_attempts"], [])

    def test_builder_completion_alone_is_not_independent_test_evidence(self):
        led, lease, attempt = self.builder()
        led.bind_native(attempt, "fixture-session")
        led.complete(attempt, lease, {"head_revision": SHA, "exit_code": 0})
        self.assertEqual(self.export()["repos"]["alpha-calc"]["counts"]["tested"], 0)

    def test_cli_after_fake_native_run_does_not_mutate_ledger_or_dispatch(self):
        from runtime import factory
        with EnvPatch(self.h.env()):
            task = factory.run_task(self.h.home, "alpha-calc", "1", "fix", wall_budget=60)
        self.assertEqual(task["builder"]["state"], "independently_verified")
        before = self.h.ledger().events()
        calls = self.h.invocations()
        proc = subprocess.run([sys.executable, str(SCRIPT), "--home", str(self.h.home),
                               "--repo", "not-registered"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["repos"]["alpha-calc"]["counts"],
                         {"queued": 0, "sent": 1, "returned": 1, "tested": 1, "merged": None})
        self.assertEqual(len(result["attempts"]), 2, "verifier receipt retained, not counted as a send")
        self.assertEqual(self.h.ledger().events(), before)
        self.assertEqual(self.h.invocations(), calls)

    def test_missing_database_is_not_created(self):
        db = self.h.home / "state" / "ledger.sqlite"
        self.h.config["state_dir"] = "missing-state"
        (self.h.home / "factory.json").write_text(json.dumps(self.h.config))
        proc = subprocess.run([sys.executable, str(SCRIPT), "--home", str(self.h.home)],
                              capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertTrue(db.exists())
        self.assertFalse((self.h.home / "missing-state").exists())


if __name__ == "__main__":
    unittest.main()
