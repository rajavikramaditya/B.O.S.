"""
Owner-friendly fuzzy unlock tests — local only, no VM, no TTS, no AzuraCast.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

PHRASE = "Hello Neena main Vikram hoon Mahil Kingdom unlock"
REQUIRED = "vikram,mahil,kingdom,unlock"


class UnlockEnvMixin:
    def setUp(self):
        self._env_patch = patch.dict(
            os.environ,
            {
                "ADMIN_UNLOCK_PHRASE": PHRASE,
                "ADMIN_UNLOCK_MIN_SCORE": "0.82",
                "ADMIN_UNLOCK_REQUIRED_WORDS": REQUIRED,
                "ADMIN_AUTH_ENABLED": "true",
                "ADMIN_API_KEY": "test-admin-key",
                "COMMAND_CENTER_LOCAL_ONLY": "false",
                "ENVIRONMENT": "test",
            },
            clear=False,
        )
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()


class TestUnlockPhraseMatching(UnlockEnvMixin, unittest.TestCase):
    def test_exact_phrase_accepted(self):
        from services.safety.admin_unlock import verify_unlock_phrase

        ok, score = verify_unlock_phrase(PHRASE)
        self.assertTrue(ok)
        self.assertGreaterEqual(score, 0.82)

    def test_punctuation_mismatch_accepted(self):
        from services.safety.admin_unlock import verify_unlock_phrase

        ok, _ = verify_unlock_phrase("Hello, Neena! main Vikram hoon. Mahil Kingdom unlock.")
        self.assertTrue(ok)

    def test_hinglish_variant_accepted(self):
        from services.safety.admin_unlock import verify_unlock_phrase

        ok, _ = verify_unlock_phrase("hello neena mein vikram hu mahil kingdom unlock")
        self.assertTrue(ok)

    def test_missing_private_word_rejected(self):
        from services.safety.admin_unlock import verify_unlock_phrase

        ok, _ = verify_unlock_phrase("hello neena unlock")
        self.assertFalse(ok)

    def test_wrong_phrase_rejected(self):
        from services.safety.admin_unlock import verify_unlock_phrase

        ok, _ = verify_unlock_phrase("hello neena main amit hoon random place unlock")
        self.assertFalse(ok)


class TestUnlockNormalization(unittest.TestCase):
    def test_normalize_variants(self):
        from services.safety.admin_unlock import normalize_unlock_text

        self.assertEqual(
            normalize_unlock_text("Hello, Neena! mein Vikram hu."),
            "hello neena main vikram hoon",
        )

    def test_devanagari_voice_transcript_romanized(self):
        from services.safety.admin_unlock import normalize_unlock_text

        self.assertEqual(
            normalize_unlock_text("हाय नीना आई एम विक्रम कूल"),
            "hi neena i am vikram cool",
        )


class TestVikramCoolVoiceUnlock(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(
            os.environ,
            {
                "ADMIN_UNLOCK_PHRASE": "hi neena i am vikram cool",
                "ADMIN_UNLOCK_MIN_SCORE": "0.70",
                "ADMIN_UNLOCK_REQUIRED_WORDS": "neena,vikram,cool",
                "ADMIN_AUTH_ENABLED": "true",
                "ADMIN_API_KEY": "test-admin-key",
            },
            clear=False,
        )
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()

    def test_devanagari_full_phrase_accepted(self):
        from services.safety.admin_unlock import verify_unlock_phrase

        ok, _ = verify_unlock_phrase("हाय नीना आई एम विक्रम कूल")
        self.assertTrue(ok)

    def test_devanagari_hinglish_mixed_accepted(self):
        from services.safety.admin_unlock import verify_unlock_phrase

        ok, _ = verify_unlock_phrase("hi neena i am विक्रम cool")
        self.assertTrue(ok)

    def test_hinglish_main_variant_accepted(self):
        from services.safety.admin_unlock import verify_unlock_phrase

        ok, _ = verify_unlock_phrase("hello neena main vikram cool")
        self.assertTrue(ok)

    def test_wrong_name_rejected(self):
        from services.safety.admin_unlock import verify_unlock_phrase

        ok, _ = verify_unlock_phrase("hello neena main amit cool")
        self.assertFalse(ok)


class TestSessionCookie(UnlockEnvMixin, unittest.TestCase):
    def test_session_token_roundtrip(self):
        from services.safety.admin_unlock import create_session_token, verify_session_token

        token = create_session_token()
        self.assertTrue(verify_session_token(token))

    def test_tampered_token_rejected(self):
        from services.safety.admin_unlock import create_session_token, verify_session_token

        token = create_session_token()
        bad = token[:-1] + ("0" if token[-1] != "0" else "1")
        self.assertFalse(verify_session_token(bad))


class TestAdminSecurityMiddleware(UnlockEnvMixin, unittest.TestCase):
    def _client(self):
        from fastapi.testclient import TestClient
        import main as main_module

        return TestClient(main_module.app)

    def test_unlock_endpoint_sets_cookie(self):
        client = self._client()
        res = client.post("/api/admin/unlock", json={"phrase": PHRASE})
        self.assertEqual(res.status_code, 200)
        self.assertIn("neena_admin_session", res.cookies)
        self.assertTrue(res.cookies["neena_admin_session"])

    def test_wrong_phrase_returns_401(self):
        client = self._client()
        res = client.post("/api/admin/unlock", json={"phrase": "hello neena unlock"})
        self.assertEqual(res.status_code, 401)

    def test_session_cookie_accepted_for_protected_route(self):
        client = self._client()
        unlock = client.post("/api/admin/unlock", json={"phrase": PHRASE})
        cookie = unlock.cookies.get("neena_admin_session")
        self.assertTrue(cookie)
        res = client.post(
            "/api/neena/chat",
            json={"message": "status", "model": "auto"},
            cookies={"neena_admin_session": cookie},
        )
        self.assertNotEqual(res.status_code, 401)

    def test_locked_command_blocked_without_session(self):
        client = self._client()
        res = client.post("/api/neena/chat", json={"message": "status", "model": "auto"})
        self.assertEqual(res.status_code, 401)

    def test_security_status_shows_session_unlocked(self):
        client = self._client()
        unlock = client.post("/api/admin/unlock", json={"phrase": PHRASE})
        cookie = unlock.cookies.get("neena_admin_session")
        res = client.get("/api/neena/security-status", cookies={"neena_admin_session": cookie})
        self.assertEqual(res.status_code, 200)
        sec = res.json().get("security") or {}
        self.assertTrue(sec.get("session_unlocked"))


class TestBroadcastStillBlockedAfterUnlock(UnlockEnvMixin, unittest.TestCase):
    def test_broadcast_routing_unchanged(self):
        from services.brain.command_interpreter import _safety_reclassify

        packet = {"action": "generate_audio", "confidence": 0.9, "slots": {}}
        result = _safety_reclassify(packet, "broadcast now")
        self.assertEqual(result["action"], "send_azuracast")


if __name__ == "__main__":
    unittest.main()
