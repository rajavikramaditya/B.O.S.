"""Hermetic tests for self-change awareness (ADR-010)."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch


class TestFingerprintDiff(unittest.TestCase):
    def test_stable_under_tool_reorder(self):
        from services.memory.self_change import build_self_fingerprint, diff_fingerprints

        a = SimpleNamespace(
            id="b_tool",
            risk="read",
            route="live_ops",
            category="status",
            feature_flag=None,
            capability_label="B",
            description="B",
        )
        b = SimpleNamespace(
            id="a_tool",
            risk="read",
            route="live_ops",
            category="status",
            feature_flag=None,
            capability_label="A",
            description="A",
        )
        with patch("services.tools.catalog.all_specs", side_effect=lambda: [a, b]), patch(
            "services.memory.self_narrative.architecture_seed_dedupe_keys",
            return_value=["neena_arch_001"],
        ), patch(
            "services.brain.feature_flags.smart_reply_enabled", return_value=True
        ), patch(
            "services.brain.feature_flags.conversation_memory_enabled", return_value=True
        ), patch(
            "services.brain.feature_flags.owner_working_context_enabled", return_value=True
        ), patch(
            "services.brain.feature_flags.system_knowledge_pack_enabled", return_value=True
        ), patch(
            "services.brain.feature_flags.bounded_tool_loop_enabled", return_value=True
        ), patch(
            "services.brain.feature_flags.deep_agent_loop_enabled", return_value=False
        ), patch(
            "services.brain.feature_flags.one_brain_foundation_enabled", return_value=True
        ), patch(
            "services.brain.feature_flags.customer_salient_memory_enabled", return_value=True
        ), patch(
            "services.brain.feature_flags.memory_soft_fade_enabled", return_value=True
        ), patch(
            "services.brain.feature_flags.self_change_awareness_enabled", return_value=True
        ):
            fp1 = build_self_fingerprint()
        with patch("services.tools.catalog.all_specs", side_effect=lambda: [b, a]), patch(
            "services.memory.self_narrative.architecture_seed_dedupe_keys",
            return_value=["neena_arch_001"],
        ), patch(
            "services.brain.feature_flags.smart_reply_enabled", return_value=True
        ), patch(
            "services.brain.feature_flags.conversation_memory_enabled", return_value=True
        ), patch(
            "services.brain.feature_flags.owner_working_context_enabled", return_value=True
        ), patch(
            "services.brain.feature_flags.system_knowledge_pack_enabled", return_value=True
        ), patch(
            "services.brain.feature_flags.bounded_tool_loop_enabled", return_value=True
        ), patch(
            "services.brain.feature_flags.deep_agent_loop_enabled", return_value=False
        ), patch(
            "services.brain.feature_flags.one_brain_foundation_enabled", return_value=True
        ), patch(
            "services.brain.feature_flags.customer_salient_memory_enabled", return_value=True
        ), patch(
            "services.brain.feature_flags.memory_soft_fade_enabled", return_value=True
        ), patch(
            "services.brain.feature_flags.self_change_awareness_enabled", return_value=True
        ):
            fp2 = build_self_fingerprint()
        self.assertEqual(fp1["digest"], fp2["digest"])
        self.assertFalse(diff_fingerprints(fp1, fp2)["has_changes"])

    def test_added_removed_tool_and_flag(self):
        from services.memory.self_change import diff_fingerprints

        prev = {
            "digest": "prev",
            "tools": [
                {
                    "id": "old_tool",
                    "risk": "read",
                    "route": "live_ops",
                    "category": "status",
                    "feature_flag": None,
                    "label": "Old",
                }
            ],
            "flags": {"NEENA_SMART_REPLY": True},
            "arch_seed_keys": ["neena_arch_001"],
        }
        curr = {
            "digest": "curr",
            "tools": [
                {
                    "id": "new_tool",
                    "risk": "read",
                    "route": "live_ops",
                    "category": "status",
                    "feature_flag": None,
                    "label": "New ability",
                }
            ],
            "flags": {"NEENA_SMART_REPLY": False},
            "arch_seed_keys": ["neena_arch_001", "neena_arch_009"],
        }
        delta = diff_fingerprints(prev, curr)
        self.assertTrue(delta["has_changes"])
        self.assertEqual([t["id"] for t in delta["added_tools"]], ["new_tool"])
        self.assertEqual([t["id"] for t in delta["removed_tools"]], ["old_tool"])
        self.assertEqual(delta["changed_flags"][0]["flag"], "NEENA_SMART_REPLY")
        self.assertIn("neena_arch_009", delta["added_arch_keys"])
        self.assertEqual(delta["next_abilities"], ["New ability"])


class TestReconcilePending(unittest.TestCase):
    def test_baseline_no_pending(self):
        from services.memory import self_change as sc

        curr = {
            "schema_version": 1,
            "digest": "abc",
            "tools": [],
            "flags": {},
            "arch_seed_keys": [],
        }
        with patch.object(sc, "build_self_fingerprint", return_value=curr), patch.object(
            sc, "_load_previous_fingerprint", return_value=None
        ), patch.object(sc, "_persist_fingerprint", return_value={"success": True}), patch.object(
            sc, "_clear_pending_announce"
        ) as clear, patch.object(sc, "_set_pending_announce") as set_p, patch(
            "services.brain.feature_flags.self_change_awareness_enabled", return_value=True
        ):
            out = sc.reconcile_on_boot()
        self.assertTrue(out["baseline"])
        self.assertFalse(out["pending"])
        clear.assert_called_once()
        set_p.assert_not_called()

    def test_change_sets_pending_once_consume(self):
        from services.memory import self_change as sc

        prev = {
            "digest": "prev",
            "tools": [{"id": "a", "risk": "read", "route": "live_ops", "category": "x", "feature_flag": None, "label": "A"}],
            "flags": {},
            "arch_seed_keys": [],
        }
        curr = {
            "schema_version": 1,
            "digest": "curr",
            "tools": [
                {"id": "a", "risk": "read", "route": "live_ops", "category": "x", "feature_flag": None, "label": "A"},
                {"id": "b", "risk": "read", "route": "live_ops", "category": "x", "feature_flag": None, "label": "B tool"},
            ],
            "flags": {},
            "arch_seed_keys": [],
        }
        store: dict = {}

        def _set(p):
            store["pending"] = dict(p)

        def _get():
            return store.get("pending")

        def _clear():
            store.pop("pending", None)

        with patch.object(sc, "build_self_fingerprint", return_value=curr), patch.object(
            sc, "_load_previous_fingerprint", return_value=prev
        ), patch.object(sc, "_persist_fingerprint", return_value={"success": True}), patch.object(
            sc, "_write_change_episode", return_value={"success": True, "created": True}
        ), patch.object(sc, "_set_pending_announce", side_effect=_set), patch.object(
            sc, "_get_pending_announce", side_effect=_get
        ), patch.object(sc, "_clear_pending_announce", side_effect=_clear), patch(
            "services.brain.feature_flags.self_change_awareness_enabled", return_value=True
        ):
            out = sc.reconcile_on_boot()
            self.assertTrue(out["pending"])
            first = sc.consume_pending_announce()
            second = sc.consume_pending_announce()
        self.assertIsNotNone(first)
        self.assertEqual(first["status"], "changed")
        self.assertIsNone(second)
        self.assertNotIn("sir,", (sc._fallback_line(store.get("pending") or first or {})).lower())

    def test_flag_off_skips(self):
        from services.memory import self_change as sc

        with patch(
            "services.brain.feature_flags.self_change_awareness_enabled", return_value=False
        ), patch.object(sc, "build_self_fingerprint") as build:
            out = sc.reconcile_on_boot()
        self.assertTrue(out.get("skipped"))
        build.assert_not_called()

    def test_prepend_consumes_and_no_sir_in_fallback(self):
        from services.memory import self_change as sc

        pending = {
            "digest": "deadbeefcafe",
            "added_tools": [{"id": "self_change_status", "label": "Self-change"}],
            "removed_tools": [],
            "changed_flags": [],
            "next_abilities": ["Self-change"],
        }
        with patch(
            "services.brain.feature_flags.self_change_awareness_enabled", return_value=True
        ), patch.object(sc, "peek_pending_announce", return_value=pending), patch.object(
            sc, "consume_pending_announce", return_value=sc._announce_packet(pending)
        ), patch(
            "services.brain.response_composer.maybe_humanize_report",
            side_effect=lambda *a, **k: a[1],
        ):
            reply, packet = sc.maybe_prepend_boot_change_announce(
                owner_message="hi",
                reply="Normal reply.",
                factual_packet={"tool": "x"},
            )
        self.assertIn("Normal reply.", reply)
        self.assertIn("Self-change detected", reply)
        self.assertNotIn("sir,", reply.lower().split("normal")[0])
        self.assertIn("self_change_announce", packet or {})


if __name__ == "__main__":
    unittest.main()
