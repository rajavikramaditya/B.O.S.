"""W3 deferred WhatsApp status + catalog integrity."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestCatalogInventory(unittest.TestCase):
    def test_action_ids_used_by_kernel(self):
        from services.tools.catalog import action_ids, reset_for_tests
        from services.tools import load_all
        from services.agent import run_kernel as rk

        reset_for_tests()
        # force reload
        import services.tools as tools_pkg

        tools_pkg._LOADED = False
        load_all()
        ids = action_ids()
        self.assertIn("arm_deferred_status", ids)
        self.assertIn("now_playing", ids)
        self.assertIn("catalog_health", ids)
        catalog = rk._catalog_ids()
        self.assertIn("arm_deferred_status", catalog)
        avail, missing = rk._inventory(["arm_deferred_status", "not_a_real_tool"])
        self.assertEqual(avail, ["arm_deferred_status"])
        self.assertEqual(missing, ["not_a_real_tool"])


class TestDeferredArm(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.job_path = Path(self.tmp.name) / "job.json"
        os.environ["NEENA_DEFERRED_STATUS"] = "1"
        os.environ["NEENA_DEFERRED_STATUS_FILE"] = str(self.job_path)

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("NEENA_DEFERRED_STATUS_FILE", None)

    def test_arm_and_tick_force(self):
        from services.cockpit.deferred_status import arm_deferred_status, tick_once

        armed = arm_deferred_status(
            message="5 min baad WhatsApp pe status bhej dena",
            slots={"delay_seconds": 60},
        )
        self.assertTrue(armed.get("ok"))
        self.assertEqual(armed.get("status"), "armed")
        with patch("services.brain.owner_notifier.notify_owner", return_value=True), patch(
            "services.cockpit.deferred_status._build_fact_lines",
            return_value="now_playing=ok",
        ):
            result = tick_once(force_due=True)
        self.assertIsNotNone(result)
        self.assertTrue(result.get("delivered"))

    def test_truth_gate_allows_when_worker_on(self):
        from services.agent.truth_gate import unavailable_action_reason

        self.assertIsNone(
            unavailable_action_reason("5 min baad WhatsApp pe status bhej dena")
        )

    def test_truth_gate_blocks_when_worker_off(self):
        from services.agent.truth_gate import unavailable_action_reason

        os.environ["NEENA_DEFERRED_STATUS"] = "0"
        self.assertEqual(
            unavailable_action_reason("5 min baad WhatsApp pe status bhej dena"),
            "deferred_followthrough_not_armed",
        )

    def test_wake_still_cannot(self):
        from services.agent.truth_gate import unavailable_action_reason

        self.assertEqual(
            unavailable_action_reason("kal subah jaga dena"),
            "no_wake_reminder_tool",
        )

    def test_tool_via_catalog(self):
        from services.tools.catalog import ToolContext, execute, reset_for_tests
        from services.tools import load_all
        import services.tools as tools_pkg

        reset_for_tests()
        tools_pkg._LOADED = False
        load_all()
        out = execute(
            "arm_deferred_status",
            ToolContext(
                action="arm_deferred_status",
                slots={"delay_seconds": 60},
                snapshot={},
                owner_message="5 min baad status WhatsApp pe bhejo",
            ),
        )
        self.assertIsNotNone(out)
        self.assertEqual(out.get("action_type"), "DEFERRED_STATUS_ARMED")
        self.assertEqual(out["factual_packet"].get("status"), "armed")

    def test_deterministic_route_gone(self):
        from services.brain.deterministic_routes import resolve_deterministic_action

        pkt = resolve_deterministic_action("5 min baad WhatsApp pe status bhej dena")
        self.assertIsNone(pkt)

    def test_kernel_arms(self):
        from services.agent.run_kernel import run_owner_kernel

        fake = {
            "reply": "ARMED",
            "action_type": "DEFERRED_STATUS_ARMED",
            "factual_packet": {
                "tool": "arm_deferred_status",
                "status": "armed",
                "job_id": "abc",
            },
        }
        with patch(
            "services.brain.operations_workflows.try_handle_interpreter_packet",
            return_value=None,
        ), patch(
            "services.tools.live_ops_executor.try_execute_live_ops",
            return_value=fake,
        ), patch(
            "services.tools.loop.extend_live_ops_result",
            side_effect=lambda **kw: kw["first_result"],
        ):
            out = run_owner_kernel(
                message="5 min baad WhatsApp pe status bhej dena",
                interpreter_packet={"action": "arm_deferred_status", "slots": {}},
                selected_model="test",
                mem_packet={},
                mem_context="",
                tb=MagicMock(),
            )
        self.assertEqual(out.get("action_type"), "DEFERRED_STATUS_ARMED")
        self.assertEqual(out["owner_run"].get("status"), "verified")


class TestPackV8(unittest.TestCase):
    def test_pack(self):
        import services.agent.system_knowledge_pack as sk

        with patch.object(sk.feature_flags, "system_knowledge_pack_enabled", return_value=True):
            text = sk.system_knowledge_pack_text()
        self.assertEqual(sk.PACK_VERSION, "2026-07-16.v8")
        self.assertIn("arm_deferred_status", text)
        self.assertIn("ADR-007", text)


if __name__ == "__main__":
    unittest.main()
