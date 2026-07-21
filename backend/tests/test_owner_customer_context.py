"""Customer WhatsApp recall — catalog tool + packet helpers (no phrase NLU)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

_WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _WORKSPACE not in sys.path:
    sys.path.insert(0, _WORKSPACE)

import database as db
from services.brain.message_router import process_message
from services.brain.owner_customer_context import (
    build_customer_recall_packet,
    extract_phone_digits,
)


class TestPhoneSlotExtractor(unittest.TestCase):
    def test_extract_phone(self):
        self.assertEqual(extract_phone_digits("call +91 98765 43210"), "9876543210")
        self.assertEqual(extract_phone_digits("no phone here"), "")


class TestCustomerRecallPacket(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._orig_db = db.DB_PATH
        db.DB_PATH = self._tmp.name
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self._orig_db
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    def test_empty_recorder_is_explicit_empty(self):
        out = build_customer_recall_packet(owner_message="any")
        pkt = out["factual_packet"]
        self.assertTrue(pkt.get("checked"))
        self.assertEqual(pkt.get("status"), "empty")
        self.assertEqual(pkt.get("recorder_turn_count"), 0)
        self.assertIn("NONE", out.get("fallback_line") or "")

    def test_packet_includes_recorder_turns(self):
        with patch(
            "services.brain.owner_customer_context._listener_turns_for_window",
            return_value=[
                {
                    "created_at": "2026-07-16T10:00:00+00:00",
                    "session_id": "whatsapp-customer-9876516500-20260716",
                    "user_input": "[customer Client +91******1650] Hi",
                    "assistant_reply": "Main Neena, Orai Radio se.",
                }
            ],
        ):
            out = build_customer_recall_packet(owner_message="customer ask")
        pkt = out["factual_packet"]
        self.assertEqual(pkt.get("status"), "ok")
        self.assertEqual(pkt.get("recorder_turn_count"), 1)
        self.assertEqual(pkt.get("contact_count"), 1)
        self.assertEqual(pkt["recorder_turns"][0]["in"], "Hi")
        self.assertEqual(pkt["contacts"][0].get("phone_last10"), "9876516500")
        self.assertEqual(pkt["contacts"][0].get("masked_tail"), "1650")

    def test_day_window_not_last40_global(self):
        """Roster uses day-window helper, not shallow global last-N."""
        with patch(
            "services.brain.owner_customer_context._listener_turns_for_window",
            return_value=[
                {
                    "created_at": "2026-07-16T07:22:00+00:00",
                    "session_id": "whatsapp-customer-9999931350-20260716",
                    "user_input": "[customer VIKRAM +91******3135] Hello neena ji",
                    "assistant_reply": "Namaste",
                }
            ],
        ) as win:
            out = build_customer_recall_packet(
                owner_message="Batayo koi customer se bat hui ajj ??",
                date_ist="2026-07-16",
            )
        self.assertTrue(win.called)
        pkt = out["factual_packet"]
        self.assertEqual(pkt.get("date_ist"), "2026-07-16")
        self.assertEqual(pkt.get("status"), "ok")
        self.assertEqual(pkt.get("contact_count"), 1)
        self.assertIn("VIKRAM", pkt["contacts"][0]["name"])

    def test_redis_thread_when_phone_given(self):
        with patch(
            "services.brain.redis_state.get_customer_chat_turns",
            return_value=[
                {"role": "user", "text": "ad lagwani hai"},
                {"role": "assistant", "text": "Abhi ads live nahi hain"},
            ],
        ), patch(
            "services.brain.owner_customer_context._listener_turns_for_window",
            return_value=[],
        ):
            out = build_customer_recall_packet(phone_digits="9876543210")
        pkt = out["factual_packet"]
        self.assertEqual(pkt.get("status"), "ok")
        self.assertEqual(pkt.get("redis_turn_count"), 2)
        self.assertEqual(pkt["redis_thread"][0]["text"], "ad lagwani hai")


class TestCustomerWhatsappCatalogTool(unittest.TestCase):
    def test_tool_registered_and_returns_factual_packet(self):
        from services.tools.catalog import ToolContext, execute, reset_for_tests
        from services.tools import load_all

        reset_for_tests()
        load_all()
        with patch(
            "services.brain.owner_customer_context._listener_turns_for_window",
            return_value=[
                {
                    "created_at": "2026-07-16",
                    "session_id": "whatsapp-customer-9876516500-20260716",
                    "user_input": "[customer +91******1650] Hello",
                    "assistant_reply": "Namaste",
                }
            ],
        ):
            res = execute(
                "customer_whatsapp_recall",
                ToolContext(
                    action="customer_whatsapp_recall",
                    slots={},
                    snapshot={},
                    owner_message="Batayo koi customer se bat hui ajj ??",
                ),
            )
        self.assertIsNotNone(res)
        pkt = (res or {}).get("factual_packet") or {}
        self.assertEqual(pkt.get("tool"), "customer_whatsapp_recall")
        self.assertTrue(pkt.get("checked"))
        self.assertEqual(pkt.get("status"), "ok")
        self.assertGreaterEqual(int(pkt.get("recorder_turn_count") or 0), 1)


class TestMessageRouterRoles(unittest.TestCase):
    @patch("services.brain.brain.process_owner_message", return_value={"reply": "OK Sir", "action_type": "x"})
    def test_owner_delegates_unchanged(self, mock_owner):
        res = process_message(role="owner", message="status", selected_model="auto")
        mock_owner.assert_called_once_with("status", selected_model="auto", channel="command_center")
        self.assertEqual(res["reply"], "OK Sir")

    @patch(
        "services.brain.customer_chat.generate_customer_reply",
        return_value={"reply": "Namaste", "action_type": "CUSTOMER_CONVERSATION"},
    )
    def test_customer_never_hits_owner(self, mock_cust):
        res = process_message(role="customer", message="hi", sender_name="Ravi", phone="9876543210")
        mock_cust.assert_called_once()
        self.assertEqual(res["role"], "customer")
        self.assertEqual(res["reply"], "Namaste")

    def test_employee_stub(self):
        res = process_message(role="employee", message="hello")
        self.assertEqual(res["action_type"], "EMPLOYEE_STUB")
        self.assertIn("owner", res["reply"].lower())


class TestConversationKeepsEnrichedContext(unittest.TestCase):
    """Permanent memory hits must not drop enriched mem_context (trust bug)."""

    def test_memory_block_keeps_customer_threads_when_hits_exist(self):
        from services.brain import conversation as conv

        mem_packet = {
            "hits": [
                {
                    "source": "postgres_pgvector",
                    "content": "Owner prefers short replies",
                }
            ]
        }
        customer_ctx = (
            "SHORT-TERM MANAGER STATE:\n- Last Intent: CONVERSATION\n\n"
            "CUSTOMER WHATSAPP THREADS (owner-only visibility — never invent):\n"
            "Recent customer WhatsApp turns (Command Center recorder):\n"
            "  IN: [customer Client +91******1650] Hi\n"
            "  OUT: Main Neena, Orai Radio se."
        )
        block = conv._memory_block(mem_packet, customer_ctx)
        self.assertIn("Owner prefers short replies", block)
        self.assertIn("CUSTOMER WHATSAPP THREADS", block)
        self.assertIn("1650", block)


if __name__ == "__main__":
    unittest.main(verbosity=2)
