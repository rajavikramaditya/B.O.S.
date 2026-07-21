"""Unit tests for M4 Command Center Availability and Health Checks."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure backend path is importable
_WORKSPACE = r"c:\Projects\radio station\radio-ai-manager\backend"
if os.path.isdir(_WORKSPACE):
    sys.path.insert(0, _WORKSPACE)

from fastapi.testclient import TestClient
from main import app

class TestCommandCenterAvailability(unittest.TestCase):
    """Test availability of health checks and readiness probes."""

    def setUp(self):
        self.client = TestClient(app)

    def test_healthz_endpoint_returns_ok_fast(self):
        """Verify /healthz returns {"ok": True, "service": "neena-backend"} instantly."""
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "service": "neena-backend"})

    def test_api_healthz_endpoint_returns_ok_fast(self):
        """Verify /api/healthz returns {"ok": True, "service": "neena-backend"} instantly."""
        response = self.client.get("/api/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "service": "neena-backend"})

    def test_health_probe_middleware_handles_both_paths(self):
        for path in ("/healthz", "/api/healthz"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertEqual(response.json(), {"ok": True, "service": "neena-backend"}, path)

    @patch("database.get_db_connection")
    @patch("psycopg2.connect")
    @patch("redis.Redis")
    def test_readyz_endpoint_success_when_all_up(self, mock_redis, mock_pg, mock_db):
        """Verify /readyz returns 200 and ok=True when all dependencies are reachable."""
        # SQLite Mock
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn

        # Postgres Mock
        mock_pg_conn = MagicMock()
        mock_pg.return_value = mock_pg_conn

        # Redis Mock
        mock_r = MagicMock()
        mock_redis.return_value = mock_r

        response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["checks"]["sqlite"]["available"], True)
        self.assertEqual(data["checks"]["postgres"]["available"], True)
        self.assertEqual(data["checks"]["redis"]["available"], True)

    @patch("database.get_db_connection")
    @patch("psycopg2.connect")
    @patch("redis.Redis")
    def test_readyz_endpoint_degraded_when_postgres_down(self, mock_redis, mock_pg, mock_db):
        """Verify /readyz returns 503 and ok=False when Postgres is degraded/unreachable."""
        # SQLite Mock
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn

        # Postgres Mock raises exception
        mock_pg.side_effect = Exception("Postgres connection timeout")

        # Redis Mock
        mock_r = MagicMock()
        mock_redis.return_value = mock_r

        response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertFalse(data["ok"])
        self.assertEqual(data["checks"]["sqlite"]["available"], True)
        self.assertEqual(data["checks"]["postgres"]["available"], False)
        self.assertEqual(data["checks"]["redis"]["available"], True)

if __name__ == "__main__":
    unittest.main(verbosity=2)
