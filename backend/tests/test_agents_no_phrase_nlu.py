"""Guardrail: no new owner phrase/regex NLU routers under brain/memory.

Allowed: Safety Kernel, exact confirm lists, slot extractors, LLM-down nets,
truth_gate scrub patterns, deprecated always-False stubs.
"""
from __future__ import annotations

import ast
import os
import sys
import unittest
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Files that may still contain confirm/slot/safety patterns.
_ALLOW_FILES = frozenset(
    {
        "services/llm/intent_router.py",  # confirm + forbidden + deprecated stubs
        "services/safety/kernel.py",
        "services/safety/policy_engine.py",
        "services/agent/truth_gate.py",  # Cannot scrub / wake-pause nets (policy)
        "services/brain/owner_customer_context.py",  # phone slot extractor only
        "services/memory/edit_service.py",  # id= slot + confirm
        "services/memory/future_intention.py",  # id=/date/lifecycle extractors inside tool
        "services/memory/day_memory.py",  # date slot extractors inside tool
        "services/memory/service.py",  # rejection phrases + content strip leftovers
        "services/memory/self_narrative.py",  # deprecated stubs remain until Wave C cleanup
        "services/brain/brain.py",  # one-tap cancel exact list
    }
)

# Banned symbol names if defined as live routers (not always-False stubs).
_BANNED_ROUTER_NAMES = frozenset(
    {
        "CONVERSATION_RECALL_MARKERS",
        "_is_conversation_recall_question",
        "_INQUIRY_MARKERS",
        "is_owner_customer_inquiry",
        "_CALL_ASK_MARKERS",
        "customer_asked_for_call_or_number",
    }
)


class TestAgentsNoPhraseNluRouters(unittest.TestCase):
    def test_banned_router_symbols_absent_or_stubbed(self):
        import services.brain.brain as brain
        import services.brain.customer_chat as customer_chat
        import services.brain.owner_customer_context as occ

        self.assertFalse(hasattr(brain, "CONVERSATION_RECALL_MARKERS"))
        self.assertFalse(hasattr(brain, "_is_conversation_recall_question"))
        self.assertFalse(hasattr(occ, "is_owner_customer_inquiry"))
        self.assertFalse(hasattr(occ, "_INQUIRY_MARKERS"))
        self.assertFalse(hasattr(customer_chat, "_CALL_ASK_MARKERS"))
        self.assertFalse(hasattr(customer_chat, "customer_asked_for_call_or_number"))
        self.assertTrue(hasattr(customer_chat, "parse_customer_reply_packet"))

    def test_memory_routers_are_always_false(self):
        from services.memory import day_memory, future_intention, self_narrative, service

        self.assertFalse(service.is_direct_memory_question("yaad hai kya"))
        self.assertFalse(service.is_explicit_permanent_memory_request("yaad rakh"))
        self.assertFalse(day_memory.is_day_memory_question("kal kya hua"))
        self.assertFalse(future_intention.is_future_intention_question("kal kya plan"))
        self.assertFalse(future_intention.is_future_intention_statement("kal karna hai"))
        self.assertFalse(self_narrative.is_self_who_question("tum kaun ho"))
        self.assertFalse(self_narrative.is_architecture_question("dimaag kaise"))
        self.assertFalse(self_narrative.is_life_story_question("life story"))

    def test_deterministic_routes_empty(self):
        from services.brain.deterministic_routes import resolve_deterministic_action

        self.assertIsNone(resolve_deterministic_action("command center lock karo"))
        self.assertIsNone(resolve_deterministic_action("5 min baad status bhej dena"))

    def test_exact_command_diagnostics_only(self):
        from services.llm.intent_router import is_exact_command

        self.assertTrue(is_exact_command("diagnostics"))
        self.assertFalse(is_exact_command("model status batao"))
        self.assertFalse(is_exact_command("stream status"))

    def test_no_banned_assignments_in_brain_local_router(self):
        brain_path = _BACKEND / "services" / "brain" / "brain.py"
        tree = ast.parse(brain_path.read_text(encoding="utf-8"), filename=str(brain_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id in _BANNED_ROUTER_NAMES:
                        self.fail(f"banned router symbol reintroduced: {t.id}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
