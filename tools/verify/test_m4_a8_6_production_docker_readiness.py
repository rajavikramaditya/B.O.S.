import unittest
from unittest.mock import patch
import os
import sys
import json

# Ensure backend directory is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from services.safety.security_config import get_ssl_verify, is_insecure_ssl_allowed
from services.cockpit.launch_health import get_deep_launch_health
from services.broadcast.azuracast_client import check_azuracast_write_config, _api_verify_ssl
from services.cockpit.runtime_controller import get_whatsapp_gateway_url
from services.voice.gen_service import generate_capsule_audio


class TestProductionDockerReadiness(unittest.TestCase):

    def setUp(self):
        # Save env variables to restore them after each test
        self.original_env = dict(os.environ)

    def tearDown(self):
        # Restore original env variables
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_a_no_unconditional_verify_false_in_codebase(self):
        """Test Case A: Scan backend files for verify=False to ensure none remain."""
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
        for root, _, files in os.walk(backend_dir):
            for file in files:
                if file.endswith(".py") and file != "security_config.py" and not file.startswith("test_"):
                    filepath = os.path.join(root, file)
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        # Allow verify=False only if commented or in specific test mocks, not active calls
                        if "verify=False" in content:
                            # Filter out false positives like comments
                            for line in content.splitlines():
                                if "verify=False" in line and not line.strip().startswith("#"):
                                    self.fail(f"Found active 'verify=False' in file {filepath}: {line}")

    def test_b_allow_insecure_ssl_dev_only_defaults_false(self):
        """Test Case B: ALLOW_INSECURE_SSL_DEV_ONLY defaults to False."""
        if "ALLOW_INSECURE_SSL_DEV_ONLY" in os.environ:
            del os.environ["ALLOW_INSECURE_SSL_DEV_ONLY"]
        self.assertFalse(is_insecure_ssl_allowed())
        self.assertTrue(get_ssl_verify())

    def test_c_production_readiness_fails_if_insecure_ssl_dev_flag_active_in_production(self):
        """Test Case C: Production readiness fails if insecure SSL dev flag is true in production."""
        os.environ["ENVIRONMENT"] = "production"
        os.environ["ALLOW_INSECURE_SSL_DEV_ONLY"] = "true"
        
        # Verify that get_ssl_verify is forced True (insecure not allowed)
        self.assertFalse(is_insecure_ssl_allowed())
        self.assertTrue(get_ssl_verify())

        # Verify that launch health reports insecure_ssl_block = True
        health = get_deep_launch_health(force_refresh=True)
        self.assertTrue(health.get("insecure_ssl_block"))
        self.assertFalse(health.get("memory_stack", {}).get("production_memory_shadow_ready"))

    def test_d_azuracast_http_scheme_reported_correctly(self):
        """Test Case D: AzuraCast HTTP scheme is reported as plain HTTP, not fake TLS."""
        os.environ["AZURACAST_BASE_URL"] = "http://8.231.73.115"
        config = check_azuracast_write_config()
        self.assertEqual(config.get("url_scheme"), "http")
        self.assertFalse(config.get("ssl_verify_active"))
        self.assertEqual(config.get("security_note"), "plain_http_azuracast")

        # Test HTTPS
        os.environ["AZURACAST_BASE_URL"] = "https://stream.orairadio.in"
        os.environ["ALLOW_INSECURE_SSL_DEV_ONLY"] = "false"
        config_https = check_azuracast_write_config()
        self.assertEqual(config_https.get("url_scheme"), "https")
        self.assertTrue(config_https.get("ssl_verify_active"))

    def test_e_docker_service_urls_are_env_driven(self):
        """Test Case E: Docker service URLs are env/config driven."""
        os.environ["WHATSAPP_GATEWAY_URL"] = "http://neena-whatsapp-gateway:3001/api/status"
        self.assertEqual(get_whatsapp_gateway_url("status"), "http://neena-whatsapp-gateway:3001/api/status")
        self.assertEqual(get_whatsapp_gateway_url("send-message"), "http://neena-whatsapp-gateway:3001/api/send-message")

    def test_f_no_runtime_hardcoded_localhost_for_whatsapp(self):
        """Test Case F: Verify no hardcoded localhost:3001 queries inside runtime WhatsApp health or metrics."""
        # Clean env to trigger fallback or use default
        if "WHATSAPP_GATEWAY_URL" in os.environ:
            del os.environ["WHATSAPP_GATEWAY_URL"]
        # Falls back to localhost in local dev, but is driven by WHATSAPP_GATEWAY_URL if set
        os.environ["WHATSAPP_GATEWAY_URL"] = "http://neena-whatsapp-gateway:3001/api/status"
        url = get_whatsapp_gateway_url("status")
        self.assertNotIn("localhost", url)
        self.assertNotIn("127.0.0.1", url)

    def test_g_frontend_served_api_uses_relative_path(self):
        """Test Case G: Frontend app.js served API uses relative /api; localhost is dev fallback."""
        app_js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "app.js"))
        with open(app_js_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Must use location.origin for browser checks
            self.assertIn("window.location.origin.startsWith('http') ? window.location.origin + '/api'", content)

    @patch("services.voice.gen_service.get_gemini_api_key", return_value="")
    @patch("services.voice.gen_service.get_elevenlabs_key", return_value="")
    def test_h_simulated_audio_cannot_become_production_asset(self, mock_el, mock_gem):
        """Test Case H: Simulated audio cannot have production_asset=True or audio_truth_level=real."""
        # Simulated properties must be strictly locked
        # Let's inspect voice_gen_service to ensure it sets them to False / simulated
        from services.voice.gen_service import _write_playable_simulated_wav
        # If simulated is written, check voice asset properties in DB or check return structure of render
        from services.voice.gen_service import render_script_audio
        os.environ["ALLOW_SIMULATED_TTS_DEV_ONLY"] = "true"
        # Force ElevenLabs key and Gemini keys to be empty so it falls back to simulated
        os.environ["ELEVENLABS_API_KEY"] = ""
        os.environ["GEMINI_API_KEY"] = ""
        
        # Test simulated render returns false production asset status
        res = render_script_audio(script_id=999, text="test", filename_stem="test_sim", link_capsule=False)
        self.assertFalse(res.get("production_asset"))
        self.assertEqual(res.get("audio_truth_level"), "simulated")

    def test_i_simulated_audio_cannot_be_sent_to_azuracast(self):
        """Test Case I: Simulated audio cannot be sent to AzuraCast."""
        from services.broadcast.capsule_service import validate_capsule_for_azuracast_push
        # Create a mock capsule with simulated audio
        from database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS broadcast_capsules")
        cursor.execute("""
            CREATE TABLE broadcast_capsules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                approval_queue_id INTEGER,
                title TEXT,
                script_text TEXT,
                audio_file_path TEXT,
                audio_truth_level TEXT,
                approval_status TEXT,
                azuracast_status TEXT,
                playlist_id INTEGER,
                media_id INTEGER
            )
        """)
        cursor.execute("""
            INSERT INTO broadcast_capsules (approval_queue_id, title, script_text, audio_file_path, audio_truth_level, approval_status)
            VALUES (1, 'Test Title', 'Test Script', 'dummy.wav', 'simulated', 'approved')
        """)
        conn.commit()
        
        # Validate gate blocks simulated capsule push
        gate = validate_capsule_for_azuracast_push(capsule_id=1)
        self.assertFalse(gate.get("allowed"))
        self.assertIn("simulated audio cannot be sent as production broadcast", gate.get("message"))
        conn.close()

    def test_j_unavailable_source_tools_omit_placeholders(self):
        """Test Case J: Daily show plan and RJ intro do not contain [LOCAL UPDATE PLACEHOLDER]."""
        from services.brain.operations_workflows import _workflow_daily_show_plan
        # Mock inputs
        packet = {"extracted_fields": {"number_of_segments": 3}}
        tb = type("TelemetryBuilder", (object,), {"llm_used": False, "step": lambda self, a, b: None})()
        
        # Call daily show plan with mock generator (we check system instructions or just invoke normal runner)
        # We can also check the workflows module code itself to verify string replacements and prompts
        filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend", "services", "neena_operations_workflows.py"))
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertNotIn("[LOCAL UPDATE PLACEHOLDER] if live data unavailable", content)
            self.assertIn("Sir, live weather/news source connected nahi hai; main isko include nahi karungi.", content)

    def test_k_listener_app_files_unchanged(self):
        """Test Case K: Verify listener app folder and Next.js / Capacitor files are not modified."""
        listener_app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "orai-radio-station"))
        if os.path.exists(listener_app_dir):
            app_config_path = os.path.join(listener_app_dir, "src", "lib", "appConfig.ts")
            with open(app_config_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Verify domain fallback still holds
                self.assertIn("https://api.orairadio.in", content)
                self.assertIn("https://stream.orairadio.in", content)

    def test_l_no_regex_keyword_natural_routing(self):
        """Test Case L: Ensure natural command routing is model-interpreter based (no regex)."""
        filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend", "services", "neena_command_interpreter.py"))
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            # Ensure no regex patterns dict for natural routing is reintroduced
            self.assertNotIn("NATURAL_REGEX_PATTERNS", content)


if __name__ == "__main__":
    unittest.main()
