"""Phase 1 — global structured error envelope (AGENTS rule 6).

Verifies every HTTPException is upgraded to the rule-6 shape while staying
backward compatible (keeps `detail`).
"""
import os
import sys
import unittest
from unittest.mock import patch

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

PHRASE = "Hello Neena main Vikram hoon Mahil Kingdom unlock"
REQUIRED = "vikram,mahil,kingdom,unlock"


class TestErrorEnvelopeUnit(unittest.TestCase):
    def test_plain_httpexception_upgraded_and_backward_compatible(self):
        from fastapi import HTTPException
        from services.brain.error_handler import build_http_error_body

        body = build_http_error_body(HTTPException(status_code=404, detail="Capsule not found."))
        # Backward compatible: detail preserved for existing frontend parsing.
        self.assertEqual(body["detail"], "Capsule not found.")
        # Rule 6 structured fields present.
        self.assertFalse(body["ok"])
        self.assertEqual(body["error_code"], "HTTP_404")
        self.assertEqual(body["message"], "Capsule not found.")
        self.assertFalse(body["recoverable"])
        self.assertIn("next_action", body)

    def test_503_marked_recoverable(self):
        from fastapi import HTTPException
        from services.brain.error_handler import build_http_error_body

        body = build_http_error_body(HTTPException(status_code=503, detail="busy"))
        self.assertTrue(body["recoverable"])

    def test_neena_http_error_carries_fields(self):
        from services.brain.error_handler import NeenaHTTPError, build_http_error_body

        exc = NeenaHTTPError(
            400, "push blocked", error_code="AZURACAST_BLOCKED", next_action="approve_capsule_first"
        )
        body = build_http_error_body(exc)
        self.assertEqual(body["error_code"], "AZURACAST_BLOCKED")
        self.assertEqual(body["next_action"], "approve_capsule_first")
        self.assertEqual(body["detail"], "push blocked")


class TestErrorEnvelopeIntegration(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(
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
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def test_wrong_phrase_401_has_structured_envelope(self):
        from fastapi.testclient import TestClient
        import main as main_module

        client = TestClient(main_module.app)
        res = client.post("/api/admin/unlock", json={"phrase": "totally wrong phrase"})
        self.assertEqual(res.status_code, 401)
        data = res.json()
        # Backward compatible + structured.
        self.assertIn("detail", data)
        self.assertFalse(data.get("ok"))
        self.assertEqual(data.get("error_code"), "HTTP_401")


if __name__ == "__main__":
    unittest.main()
