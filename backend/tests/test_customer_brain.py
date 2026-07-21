"""Public customer WhatsApp brain — human manager, situation-aware."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.brain.customer_chat import (
    _looks_like_ai_leak,
    build_station_situation,
    generate_customer_reply,
    humanize_customer_reply,
    parse_customer_reply_packet,
    strip_unsolicited_owner_number,
)


class TestCustomerBrain(unittest.TestCase):
    def test_situation_defaults_not_live(self):
        sit = build_station_situation()
        self.assertFalse(sit["app_public_ready"])
        self.assertFalse(sit["ads_live"])
        self.assertFalse(sit["can_take_voice_calls"])
        self.assertEqual(sit["channel"], "whatsapp_only")
        self.assertIn("Orai", sit["station_name"])

    def test_ai_leak_detector(self):
        self.assertTrue(_looks_like_ai_leak("Main ek AI hoon"))
        self.assertTrue(_looks_like_ai_leak("I am an AI assistant"))
        self.assertFalse(_looks_like_ai_leak("Main Neena, Orai Radio se bol rahi hoon"))

    def test_humanize_strips_emoji_spam_and_blank_paragraphs(self):
        raw = "Namaste!\n\n\nMain Neena hoon 🙂\n\nApp abhi ready nahi 😊✨"
        cleaned = humanize_customer_reply(raw)
        self.assertNotIn("🙂", cleaned)
        self.assertNotIn("😊", cleaned)
        self.assertNotIn("\n\n", cleaned)
        self.assertIn("Neena", cleaned)

    def test_humanize_collapses_mark_spam(self):
        cleaned = humanize_customer_reply("Kab start???? Abhi!!! Wait.....")
        self.assertNotIn("????", cleaned)
        self.assertNotIn("!!!", cleaned)
        self.assertIn("?", cleaned)

    def test_parse_customer_reply_packet_json(self):
        reply, allow = parse_customer_reply_packet(
            '{"reply":"WhatsApp pe madad karti hoon","customer_asks_call_or_number":false}'
        )
        self.assertEqual(reply, "WhatsApp pe madad karti hoon")
        self.assertFalse(allow)
        reply2, allow2 = parse_customer_reply_packet(
            '```json\n{"reply":"Vikram sir: +91 9876543210","customer_asks_call_or_number":true}\n```'
        )
        self.assertIn("9876543210", reply2)
        self.assertTrue(allow2)

    def test_parse_customer_reply_packet_fail_closed(self):
        reply, allow = parse_customer_reply_packet("Plain text without JSON")
        self.assertEqual(reply, "Plain text without JSON")
        self.assertFalse(allow)

    @patch.dict(
        os.environ,
        {"OWNER_WHATSAPP_NUMBER": "+919876543210", "OWNER_PHONE_NUMBER": ""},
        clear=False,
    )
    def test_strip_unsolicited_owner_number(self):
        raw = "Call ke liye Vikram sir: +91 9876543210"
        stripped = strip_unsolicited_owner_number(raw, allow=False)
        self.assertNotIn("9876543210", stripped)
        kept = strip_unsolicited_owner_number(raw, allow=True)
        self.assertIn("9876543210", kept)

    @patch("services.brain.customer_chat._load_history", return_value=([], "none"))
    @patch("services.brain.feature_flags.one_brain_foundation_enabled", return_value=False)
    @patch("services.brain.customer_chat.feature_flags.customer_brain_enabled", return_value=False)
    @patch("services.brain.customer_chat._remember_turn", return_value=True)
    def test_flag_off_static(self, _rem, _flag, _one, _hist):
        res = generate_customer_reply(
            "ad lagwani hai", sender_name="Ravi", phone="+919876543210",
        )
        self.assertEqual(res["action_type"], "CUSTOMER_STATIC")
        self.assertIn("Neena", res["reply"])
        self.assertNotIn("AI", res["reply"])
        self.assertEqual(res["customer_phone_last10"], "9876543210")
        self.assertIn("3210", res["customer_phone_masked"])
        # Static fallback must not dump owner number unsolicited
        self.assertNotIn("9876543210", res["reply"])

    @patch("services.brain.customer_chat._load_history", return_value=([], "none"))
    @patch("services.brain.feature_flags.one_brain_foundation_enabled", return_value=False)
    @patch("services.brain.customer_chat.feature_flags.customer_brain_enabled", return_value=True)
    @patch("services.brain.customer_chat.pr.get_gemini_api_key", return_value="")
    @patch("services.brain.customer_chat._remember_turn", return_value=True)
    def test_no_key_falls_back_human(self, _rem, _key, _flag, _one, _hist):
        res = generate_customer_reply("radio kab start", sender_name="Asha", phone="9123456789")
        self.assertIn(res["action_type"], ("CUSTOMER_FALLBACK", "CUSTOMER_STATIC"))
        self.assertTrue(res["reply"].strip())
        self.assertFalse(_looks_like_ai_leak(res["reply"]))
        self.assertEqual(res["customer_phone_last10"], "9123456789")
        self.assertIn(res.get("customer_history_source"), ("redis", "recorder", "none"))

    @patch("services.brain.feature_flags.one_brain_foundation_enabled", return_value=False)
    @patch("services.brain.customer_chat.feature_flags.customer_brain_enabled", return_value=True)
    @patch("services.brain.customer_chat.pr.get_gemini_api_key", return_value="")
    @patch("services.brain.customer_chat._remember_turn", return_value=True)
    @patch(
        "services.brain.customer_chat._load_history",
        return_value=(
            [
                {"role": "user", "text": "ad lagwani hai"},
                {"role": "assistant", "text": "Abhi ads live nahi hain"},
            ],
            "redis",
        ),
    )
    def test_history_source_reported(self, _hist, _rem, _key, _flag, _one):
        res = generate_customer_reply("ok note kar lo", sender_name="Ravi", phone="9876543210")
        self.assertEqual(res["customer_history_source"], "redis")

    @patch("services.brain.customer_chat.feature_flags.customer_brain_enabled", return_value=True)
    @patch("services.brain.customer_chat.pr.get_gemini_api_key", return_value="fake-key")
    @patch("services.brain.customer_chat._model_chain", return_value=["gemini-test"])
    @patch(
        "services.brain.customer_chat._call_model",
        return_value=(
            '{"reply":"Theek hai, note kar liya.","customer_asks_call_or_number":false}',
            "available",
        ),
    )
    @patch("services.brain.customer_chat._remember_turn", return_value=True)
    @patch("services.brain.customer_chat._load_history", return_value=([], "none"))
    def test_salient_extract_is_scheduled_not_inline(self, _hist, _rem, _call, _chain, _key, _flag):
        with patch(
            "services.memory.facade.recall",
            return_value={"hits": [], "context_text": ""},
        ), patch(
            "services.memory.customer_salient.maybe_seed_customer_name_from_pushname",
            return_value={"ok": False, "skipped": True},
        ), patch(
            "services.memory.customer_salient.schedule_customer_salient_extract"
        ) as sched, patch(
            "services.memory.customer_salient.maybe_extract_and_store_customer_salient"
        ) as inline:
            res = generate_customer_reply(
                "ad lagwani hai please", sender_name="Ravi", phone="9876543210",
            )
            self.assertEqual(res["action_type"], "CUSTOMER_CONVERSATION")
            sched.assert_called_once()
            inline.assert_not_called()

    def test_pushname_seed_skips_placeholder(self):
        from services.memory.customer_salient import maybe_seed_customer_name_from_pushname

        with patch("services.brain.feature_flags.customer_salient_memory_enabled", return_value=True), \
             patch("services.brain.feature_flags.one_brain_foundation_enabled", return_value=True):
            out = maybe_seed_customer_name_from_pushname(
                phone="9876543210", sender_name="ji", existing_hits=[],
            )
        self.assertTrue(out.get("skipped"))

    def test_pushname_seed_skips_when_name_exists(self):
        from services.memory.customer_salient import maybe_seed_customer_name_from_pushname

        with patch("services.brain.feature_flags.customer_salient_memory_enabled", return_value=True), \
             patch("services.brain.feature_flags.one_brain_foundation_enabled", return_value=True):
            out = maybe_seed_customer_name_from_pushname(
                phone="9876543210",
                sender_name="Ravi",
                existing_hits=[{"memory_type": "customer_name", "content": "Ravi"}],
            )
        self.assertEqual(out.get("reason"), "already_have_name")


if __name__ == "__main__":
    unittest.main()
