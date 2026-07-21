"""M5 — Tests for Neena intelligence upgrade (Gemma-first, smart reply, job follow-through)."""
import os
import sys
import unittest
from unittest import mock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestModelRoles(unittest.TestCase):
    def test_gemma_primary_for_intent_and_conversation(self):
        from services.llm.model_roles import get_public_role_map

        roles = get_public_role_map()
        self.assertEqual(roles["COMMAND_INTERPRETER_MODEL"]["primary_option"], "gemma-2-26b")
        self.assertEqual(roles["CONVERSATION_MODEL"]["primary_option"], "gemma-2-26b")
        # Creative / real radio work stays on flash-lite
        self.assertEqual(roles["CREATIVE_MODEL"]["primary_option"], "gemini-3.1-flash-lite")

    def test_interpreter_falls_back_to_gemini(self):
        from services.llm.model_roles import get_public_role_map

        roles = get_public_role_map()
        self.assertEqual(roles["COMMAND_INTERPRETER_MODEL"]["fallback_option"], "gemini-3.1-flash-lite")

    def test_resolution_prefers_gemma_when_available(self):
        from services.llm.model_roles import CONFIG_APPROVED_API_IDS, resolve_role_to_api_id

        avail = set(CONFIG_APPROVED_API_IDS)
        self.assertIn("gemma", resolve_role_to_api_id("COMMAND_INTERPRETER_MODEL", avail))
        self.assertIn("gemma", resolve_role_to_api_id("CONVERSATION_MODEL", avail))


class TestFeatureFlags(unittest.TestCase):
    def test_defaults_enabled(self):
        import services.brain.feature_flags as ff

        # Defaults should be on unless explicitly disabled
        for name in ("NEENA_SMART_REPLY", "NEENA_CONV_MEMORY", "NEENA_JOB_FOLLOWUP", "NEENA_JOB_WHATSAPP_PUSH"):
            os.environ.pop(name, None)
        self.assertTrue(ff.smart_reply_enabled())
        self.assertTrue(ff.conversation_memory_enabled())
        self.assertTrue(ff.job_followup_enabled())
        self.assertTrue(ff.job_whatsapp_push_enabled())

    def test_can_disable(self):
        import services.brain.feature_flags as ff

        os.environ["NEENA_SMART_REPLY"] = "0"
        try:
            self.assertFalse(ff.smart_reply_enabled())
        finally:
            os.environ.pop("NEENA_SMART_REPLY", None)


class TestConversationRecallDetection(unittest.TestCase):
    def test_conversation_recall_helper_removed(self):
        import services.brain.brain as nb

        self.assertFalse(hasattr(nb, "_is_conversation_recall_question"))
        self.assertFalse(hasattr(nb, "CONVERSATION_RECALL_MARKERS"))


class TestConversationServiceGuards(unittest.TestCase):
    def test_returns_none_when_disabled(self):
        import services.brain.conversation as conv

        os.environ["NEENA_SMART_REPLY"] = "0"
        try:
            self.assertIsNone(conv.generate_conversational_reply("hello neena"))
        finally:
            os.environ.pop("NEENA_SMART_REPLY", None)

    def test_prompt_contains_truth_rules(self):
        import services.brain.conversation as conv

        prompt = conv.build_conversation_system_prompt({}, "", None)
        self.assertIn("NEVER claim", prompt)
        self.assertIn("If not checked, say so", prompt)


class TestJobFollowThrough(unittest.TestCase):
    def test_unseen_finished_job_roundtrip(self):
        import services.cockpit.job_service as jobs

        job_id = jobs.create_job("verify_latest_stream", {})
        jobs.mark_succeeded(job_id, "Stream verify complete.", {"allowed": True})

        unseen_ids = [j["job_id"] for j in jobs.list_unseen_finished_jobs(limit=50)]
        self.assertIn(job_id, unseen_ids)

        jobs.mark_owner_seen([job_id])
        unseen_ids_after = [j["job_id"] for j in jobs.list_unseen_finished_jobs(limit=50)]
        self.assertNotIn(job_id, unseen_ids_after)


class TestCockpitJobRepositorySplit(unittest.TestCase):
    """Phase 3 — SQL moved to cockpit_job_repository; service API stays stable."""

    def test_service_still_exposes_public_api(self):
        import services.cockpit.job_service as jobs

        for fn in ("create_job", "mark_running", "mark_succeeded", "mark_failed",
                   "get_job", "mark_owner_seen", "list_unseen_finished_jobs",
                   "submit_background_job", "update_progress"):
            self.assertTrue(callable(getattr(jobs, fn, None)), fn)

    def test_repository_roundtrip(self):
        import services.cockpit.job_repository as repo

        job_id = "job_test_" + os.urandom(4).hex()
        repo.insert_job(job_id, "verify_latest_stream", {"x": 1})
        repo.mark_succeeded(job_id, "done ok", {"allowed": True})
        got = repo.get_job(job_id)
        self.assertEqual(got["status"], "succeeded")
        self.assertEqual(got["owner_message"], "done ok")
        repo.mark_owner_seen([job_id])
        unseen = [j["job_id"] for j in repo.list_unseen_finished_jobs(limit=50)]
        self.assertNotIn(job_id, unseen)


class TestMemoryStatusTruth(unittest.TestCase):
    def test_embedding_model_is_consistent(self):
        from services.memory.status import build_neena_memory_status

        st = build_neena_memory_status()
        # Must reflect the real embedding model, not the stale text-embedding-004
        self.assertNotEqual(st["embedding_model"], "text-embedding-004")
        self.assertIn("embedding", st["embedding_model"])


class TestOneTapConfirmation(unittest.TestCase):
    """Frictionless one-tap approval for surfaced protected actions (hermetic — no network)."""

    def _pending(self, action="send_azuracast"):
        return {
            "action_type": action,
            "protected": True,
            "payload": {"resume_action": action, "resume_slots": {}},
        }

    def _run(self, message, pending, exec_return=None):
        """Drive process_owner_message with manager-state/trace/live-ops seams mocked."""
        import services.brain.brain as nb
        import services.brain.live_ops_executor as live_ops

        store = {"pending": pending}
        captured = {}

        def fake_exec(action, slots, *, snapshot=None, owner_message=""):
            captured["action"] = action
            captured["slots"] = slots
            return exec_return or {"reply": "Ho gaya sir.", "action_type": "SEND_AZURACAST"}

        patches = [
            mock.patch.object(nb.manager_state, "get_pending_action", side_effect=lambda: store["pending"]),
            mock.patch.object(nb.manager_state, "clear_pending_action",
                              side_effect=lambda: store.update(pending=None)),
            mock.patch.object(nb.memory_service, "get_pending_permanent_memory_candidate", return_value=None),
            mock.patch.object(nb.memory_service, "is_explicit_permanent_memory_request", return_value=False),
            mock.patch.object(nb, "_apply_session_trace", side_effect=lambda *a, **k: None),
            mock.patch.object(live_ops, "try_execute_live_ops", side_effect=fake_exec),
            mock.patch.object(nb, "_save_and_return", side_effect=lambda message, reply, **kw: {"reply": reply, **kw}),
        ]
        for p in patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patches])
        result = nb.process_owner_message(message)
        return result, captured, store

    def test_protected_action_set_is_irreversible_only(self):
        import services.brain.brain as nb

        for a in ("send_azuracast", "approve_latest_script", "approve_capsule"):
            self.assertIn(a, nb._ONE_TAP_PROTECTED_ACTIONS)
        # Reversible/read actions must never require confirmation
        self.assertNotIn("station_status", nb._ONE_TAP_PROTECTED_ACTIONS)
        self.assertNotIn("diagnostics", nb._ONE_TAP_PROTECTED_ACTIONS)

    def test_plain_haan_executes_pending_protected_action(self):
        result, captured, store = self._run(
            "haan",
            self._pending("send_azuracast"),
            exec_return={"reply": "Capsule #23 AzuraCast par upload ho gaya.", "action_type": "SEND_AZURACAST"},
        )
        self.assertEqual(captured.get("action"), "send_azuracast")
        self.assertTrue(captured["slots"].get("explicit_push"))
        self.assertIn("upload ho gaya", result["reply"])
        self.assertIsNone(store["pending"])

    def test_ha_kr_do_affirmative_executes_pending(self):
        """Recorder turn 241/262 — natural affirmative must execute, not clear+loop."""
        result, captured, store = self._run(
            "Ha kr do",
            self._pending("send_azuracast"),
            exec_return={"reply": "Capsule #9 AzuraCast par upload ho gaya.", "action_type": "SEND_AZURACAST"},
        )
        self.assertEqual(captured.get("action"), "send_azuracast")
        self.assertTrue(captured["slots"].get("explicit_push"))
        self.assertIsNone(store["pending"])
        self.assertIn("upload", result["reply"].lower())

    def test_bound_capsule_id_passed_on_confirm(self):
        pending = self._pending("send_azuracast")
        pending["payload"]["capsule_id"] = 9
        pending["payload"]["resume_slots"] = {"capsule_id": 9}
        result, captured, store = self._run(
            "haan",
            pending,
            exec_return={"reply": "ok", "action_type": "SEND_AZURACAST", "capsule_id": 9},
        )
        self.assertEqual(captured["slots"].get("capsule_id"), 9)
        self.assertTrue(captured["slots"].get("explicit_push"))

    def test_nahi_cancels_pending_without_executing(self):
        result, captured, store = self._run("nahi", self._pending("send_azuracast"))
        self.assertNotIn("action", captured)  # executor never called
        self.assertIn("cancel", result["reply"].lower())
        self.assertIsNone(store["pending"])


if __name__ == "__main__":
    unittest.main()
