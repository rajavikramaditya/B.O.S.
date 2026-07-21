"""Tests for ADR-011 self-heal allowlist + smell kills."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch


class TestSelfHealAllowlist(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        os.environ["NEENA_SELF_HEAL_DIR"] = self._tmpdir.name
        os.environ["NEENA_SELF_HEAL"] = "1"
        os.environ["NEENA_SELF_HEAL_ALLOW_REBOOT"] = "1"
        os.environ["NEENA_SELF_HEAL_DRY_RUN"] = "0"
        # Reset feature flag override cache if loaded.
        import services.brain.feature_flags as ff

        ff._OVERRIDES.clear()
        ff._OVERRIDES_LOADED = False

    def test_rejects_unknown_action(self):
        from services.cockpit import self_heal

        res = self_heal.request_heal("rm_rf", reason="nope")
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("error"), "action_not_allowlisted")

    def test_writes_gateway_request(self):
        from services.cockpit import self_heal

        res = self_heal.request_heal(
            "gateway_restart", reason="cpu high", metrics={"cpu": 96}
        )
        self.assertTrue(res.get("ok"))
        path = os.path.join(self._tmpdir.name, "self_heal_request.json")
        self.assertTrue(os.path.isfile(path))
        data = json.loads(open(path, encoding="utf-8").read())
        self.assertEqual(data["action"], "gateway_restart")

    def test_reboot_writes_pending(self):
        from services.cockpit import self_heal

        res = self_heal.request_heal("host_reboot", reason="still critical")
        self.assertTrue(res.get("ok"))
        pending = self_heal.load_pending_announce()
        self.assertIsNotNone(pending)
        self.assertEqual(pending.get("action"), "host_reboot")

    def test_reboot_blocked_without_flag(self):
        os.environ["NEENA_SELF_HEAL_ALLOW_REBOOT"] = "0"
        import services.brain.feature_flags as ff

        ff._OVERRIDES_LOADED = False
        from services.cockpit import self_heal

        res = self_heal.request_heal("host_reboot", reason="x")
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("error"), "reboot_not_allowed")

    def test_azura_not_in_allowlist(self):
        from services.cockpit.self_heal import ALLOWED_ACTIONS

        self.assertNotIn("azuracast_restart", ALLOWED_ACTIONS)
        self.assertNotIn("postgres_restart", ALLOWED_ACTIONS)
        self.assertEqual(
            ALLOWED_ACTIONS,
            frozenset({"gateway_restart", "backend_restart", "host_reboot"}),
        )


class TestDeepDiagnosticsRemoved(unittest.TestCase):
    def test_submit_diagnostics_deep_rejected(self):
        import services.cockpit.job_service as jobs

        res = jobs.submit_background_job("diagnostics_deep", {})
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("mode"), "rejected")

    def test_cockpit_actions_no_deep(self):
        from services.cockpit.action_service import BACKGROUND_ACTIONS, COCKPIT_ACTIONS

        self.assertNotIn("diagnostics_deep", COCKPIT_ACTIONS)
        self.assertNotIn("diagnostics_deep", BACKGROUND_ACTIONS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
