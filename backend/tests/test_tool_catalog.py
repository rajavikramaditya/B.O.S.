"""Plug-and-play tool catalog — derive surfaces + register-only DX."""
from __future__ import annotations

import unittest


class TestToolCatalog(unittest.TestCase):
    def setUp(self):
        from services.tools.catalog import reset_for_tests

        reset_for_tests()

    def test_valid_actions_derived_from_catalog(self):
        from services.brain.command_interpreter import VALID_ACTIONS
        from services.tools.catalog import action_ids

        self.assertIn("station_status", VALID_ACTIONS)
        self.assertIn("send_azuracast", VALID_ACTIONS)
        self.assertIn("unknown", VALID_ACTIONS)
        self.assertIn("catalog_health", VALID_ACTIONS)
        self.assertTrue(action_ids().issubset(VALID_ACTIONS))

    def test_followup_only_reads(self):
        from services.tools.catalog import all_specs, followup_ids

        follow = followup_ids()
        self.assertIn("pipeline_status", follow)
        self.assertIn("catalog_health", follow)
        self.assertNotIn("send_azuracast", follow)
        self.assertNotIn("approve_capsule", follow)
        for spec in all_specs():
            if spec.followup_ok:
                self.assertEqual(spec.risk, "read", spec.id)

    def test_interpreter_enum_includes_new_tool(self):
        from services.brain.command_interpreter import get_interpreter_system

        text = get_interpreter_system()
        self.assertIn("catalog_health", text)
        self.assertIn("send_azuracast", text)

    def test_aliases_normalize(self):
        from services.brain.command_execution_kernel import normalize_action_key

        self.assertEqual(normalize_action_key("what_now"), "what_should_i_do_now")
        self.assertEqual(normalize_action_key("status"), "station_status")

    def test_live_ops_dispatch_catalog_health(self):
        from services.brain.live_ops_executor import try_execute_live_ops

        res = try_execute_live_ops("catalog_health", {}, snapshot={})
        self.assertIsInstance(res, dict)
        self.assertTrue(res.get("reply") or (res.get("factual_packet") is not None))

    def test_confirm_tools_not_in_followup(self):
        from services.tools.catalog import followup_ids, get

        for aid in (
            "send_azuracast",
            "fix_app_listener_path",
            "propose_permanent_memory",
            "generate_audio",
        ):
            spec = get(aid)
            self.assertIsNotNone(spec)
            self.assertEqual(spec.risk, "confirm_required")
            self.assertNotIn(aid, followup_ids())


if __name__ == "__main__":
    unittest.main()
