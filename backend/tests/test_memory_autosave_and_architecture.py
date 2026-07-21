"""Owner directive autosave + architecture / milestone narrative (contract path)."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import services.brain.always_reply  # noqa: F401 — warm brain package

from services.memory.contract import ALLOWED_PERMANENT_MEMORY_TYPES
from services.memory import self_narrative as sn
import services.memory.service as memory_service
from services.brain.response_composer import _REPORT_HUMANIZE_ACTION_TYPES


class TestOwnerDirectiveAutosave(unittest.TestCase):
    def test_markers_include_directives(self):
        self.assertFalse(memory_service.is_explicit_permanent_memory_request("aage se short jawab dena"))  # router deprecated
        self.assertFalse(memory_service.is_explicit_permanent_memory_request("RJ tone Hinglish rakhna, yaad rakh"))

    def test_propose_saves_without_pending_and_uses_facts(self):
        fake = {
            "status": "saved",
            "ok": True,
            "require_confirmation": False,
            "reply": "Permanent memory saved. type=owner_style_preference content=x postgres_id=1 sqlite_id=2.",
            "factual_packet": {
                "tool": "permanent_memory_save",
                "status": "saved",
                "saved": True,
                "content": "x",
                "intent_hint": "acknowledge_saved_preference",
            },
            "memory_save_status": "permanent_saved_sqlite_fallback",
        }
        with patch.object(memory_service, "_persist_confirmed_permanent_candidate", return_value=fake) as persisted:
            out = memory_service.propose_permanent_memory_candidate(
                content="RJ scripts Hinglish me rakho",
                memory_type="owner_style_preference",
            )
        persisted.assert_called_once()
        self.assertEqual(out["status"], "saved")
        self.assertFalse(out.get("require_confirmation"))
        self.assertIn("Permanent memory saved", out["reply"])
        self.assertNotIn("samajh gayi", out["reply"].lower())
        self.assertEqual(out["factual_packet"]["tool"], "permanent_memory_save")
        self.assertIsNone(memory_service.get_pending_permanent_memory_candidate())

    def test_humanize_allowlists_memory_actions(self):
        for a in (
            "PERMANENT_MEMORY_SAVED",
            "PROPOSE_PERMANENT_MEMORY",
            "SELF_PROFILE",
            "SELF_LIFE_STORY",
            "SELF_ARCHITECTURE",
        ):
            self.assertIn(a, _REPORT_HUMANIZE_ACTION_TYPES)


class TestArchitectureNarrative(unittest.TestCase):
    def test_type_allowed(self):
        self.assertIn(sn.TYPE_ARCHITECTURE, ALLOWED_PERMANENT_MEMORY_TYPES)

    def test_arch_question(self):
        self.assertFalse(sn.is_architecture_question("tumhara dimaag kaise kaam karta hai"))
        self.assertFalse(sn.is_architecture_question("Safety Kernel kis file me hai"))
        self.assertFalse(sn.is_architecture_question("kaisi ho aaj?"))

    def test_who_not_arch(self):
        self.assertFalse(sn.is_self_who_question("tumhara dimaag kaise kaam karta"))
        self.assertFalse(sn.is_self_who_question("tum kaun ho?"))

    def test_format_architecture_packet(self):
        fake = [
            {
                "memory_type": sn.TYPE_ARCHITECTURE,
                "content": "Entry via process_message.",
                "metadata": {"title": "Entry", "episode_order": 101},
                "importance": 5,
            }
        ]
        with patch.object(sn, "_list_by_types", return_value=fake):
            out = sn.format_architecture_answer()
        self.assertIsNotNone(out)
        self.assertIn("Entry", out["fallback_line"])
        self.assertEqual(out["factual_packet"]["tool"], "self_narrative_architecture")
        self.assertNotIn("sir,", out["fallback_line"].lower())

    def test_record_milestone(self):
        with patch("services.memory.pg_repository.is_postgres_available", return_value={"available": True}):
            with patch(
                "services.memory.pg_repository.create_memory_pg_idempotent",
                return_value={"success": True, "deduped": False},
            ):
                out = sn.record_life_milestone(
                    title="Test mile",
                    content="Something big happened.",
                    dedupe_key="test_mile_1",
                    episode_order=99,
                )
        self.assertTrue(out["success"])
        self.assertTrue(out["created"])
        self.assertIn("Life milestone recorded", out["reply"])
        self.assertEqual(out["factual_packet"]["tool"], "self_life_milestone")
        self.assertNotIn("sir,", out["reply"].lower())


if __name__ == "__main__":
    unittest.main()
