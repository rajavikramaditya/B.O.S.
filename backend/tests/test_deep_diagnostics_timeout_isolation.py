"""Unit tests for M4-A7 Deep Diagnostics Timeout Isolation."""
from __future__ import annotations

import os
import sys
import time
import unittest
from unittest.mock import patch

# Ensure backend path is in sys.path
_WORKSPACE = r"c:\Projects\radio station\radio-ai-manager\backend"
if os.path.isdir(_WORKSPACE):
    sys.path.insert(0, _WORKSPACE)


class TestDiagnosticsIsolation(unittest.TestCase):
    """Test diagnostics run under bounded timeout and do not block thread execution."""

    def test_run_with_timeout_returns_none_instantly_on_slow_call(self):
        """Verify that _run_with_timeout returns None and does not wait on hanging calls."""
        from services.cockpit.launch_health import _run_with_timeout
        
        def extremely_slow_call():
            time.sleep(10)
            return "finished"
            
        t0 = time.time()
        result = _run_with_timeout(extremely_slow_call, timeout=0.5)
        duration = time.time() - t0
        
        self.assertIsNone(result, "Expected None returned from timeout.")
        self.assertTrue(duration < 1.0, f"Expected call to exit in under 1 second, took {duration:.2f}s")

    def test_collect_memory_health_with_hung_postgres(self):
        """Verify diagnostics handles hung postgres gracefully and returns status within timeout limits."""
        from services.cockpit.launch_health import _collect_memory_health_parallel
        
        def hung_check():
            time.sleep(10)
            return {"available": True}
            
        with patch("services.cockpit.launch_health.is_postgres_available", hung_check), \
             patch("services.cockpit.launch_health.is_redis_available", lambda: {"available": True}):
            
            t0 = time.time()
            health = _collect_memory_health_parallel()
            duration = time.time() - t0
            
            self.assertFalse(health.get("postgres_available"), "Expected postgres to report unavailable due to timeout.")
            self.assertTrue(health.get("redis_available"), "Expected redis to report healthy.")
            self.assertTrue(duration < 3.0, f"Expected parallel collect to finish under 3 seconds, took {duration:.2f}s")


if __name__ == "__main__":
    unittest.main(verbosity=2)
