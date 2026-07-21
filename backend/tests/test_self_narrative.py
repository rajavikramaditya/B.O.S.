"""Phase A/B — Neena self-narrative (identity / personality / life episodes)."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Warm brain package first — cold import of memory.contract alone hits
# contract → brain.contracts → brain.__init__ → brain → memory.service → contract.
import services.brain.always_reply  # noqa: F401
from services.memory.contract import ALLOWED_PERMANENT_MEMORY_TYPES, classify_memory_candidate
from services.memory import self_narrative as sn


class TestSelfNarrativeContract(unittest.TestCase):
    def test_types_allowed(self):
        for t in (
            sn.TYPE_IDENTITY,
            sn.TYPE_PERSONALITY,
            sn.TYPE_EPISODE,
            sn.TYPE_ARCHITECTURE,
        ):
            self.assertIn(t, ALLOWED_PERMANENT_MEMORY_TYPES)

    def test_classify_confirm_gated(self):
        c = classify_memory_candidate(
            content="Neena is the station manager",
            memory_type=sn.TYPE_IDENTITY,
            owner_confirmed=False,
        )
        self.assertTrue(c["owner_confirmation_required"])
        self.assertFalse(c["should_save"])


class TestSelfNarrativeRouting(unittest.TestCase):
    def test_who_question(self):
        self.assertFalse(sn.is_self_who_question("tum kaun ho?"))  # router deprecated
        self.assertFalse(sn.is_self_who_question("Who are you Neena"))
        self.assertFalse(sn.is_self_who_question("kaisi ho aaj?"))

    def test_life_question(self):
        self.assertFalse(sn.is_life_story_question("apni zindagi ki kahani sunao"))
        self.assertFalse(sn.is_life_story_question("tell me your life story"))
        self.assertFalse(sn.is_life_story_question("stream status batao"))

    def test_format_from_rows(self):
        fake_rows = [
            {
                "memory_type": sn.TYPE_IDENTITY,
                "content": "Main Neena hoon.",
                "metadata": {"title": "Identity", "episode_order": 0},
                "importance": 5,
            },
            {
                "memory_type": sn.TYPE_PERSONALITY,
                "content": "Hinglish manager tone.",
                "metadata": {"title": "Personality", "episode_order": 0},
                "importance": 5,
            },
        ]
        with patch.object(sn, "_list_by_types", return_value=fake_rows):
            out = sn.format_self_profile_answer()
        self.assertIsNotNone(out)
        self.assertIn("Neena", out["fallback_line"])
        self.assertIn("Personality", out["fallback_line"])
        self.assertEqual(out["factual_packet"]["tool"], "self_narrative_profile")
        self.assertNotIn("sir,", out["fallback_line"].lower())

    def test_life_format_orders_episodes(self):
        fake = [
            {
                "memory_type": sn.TYPE_EPISODE,
                "content": "Second mile.",
                "metadata": {"title": "Two", "episode_order": 2},
                "importance": 4,
            },
            {
                "memory_type": sn.TYPE_EPISODE,
                "content": "First mile.",
                "metadata": {"title": "One", "episode_order": 1},
                "importance": 4,
            },
        ]
        with patch.object(sn, "_list_by_types", return_value=fake):
            out = sn.format_life_story_answer()
        self.assertIsNotNone(out)
        text = out["fallback_line"]
        self.assertLess(text.index("One"), text.index("Two"))
        self.assertEqual(out["factual_packet"]["tool"], "self_narrative_life_story")
        self.assertNotIn("sir,", text.lower())


if __name__ == "__main__":
    unittest.main()
