"""Code-quality guardrails — makes AGENTS.md architecture rules self-enforcing.

These tests run in the normal suite AND in scripts/neena_predeploy_check.py, so the
rules cannot silently drift again. Keep the baselines RATCHETING DOWN only: when a
file legitimately shrinks, lower its baseline; never raise a baseline to make a new
god-file pass.
"""
import os
import re
import unittest

# Repo root = three levels up from this file (backend/tests/<file>).
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_BACKEND = os.path.join(_ROOT, "backend")
_SERVICES = os.path.join(_BACKEND, "services")


def _iter_backend_py(include_tests: bool = False):
    for dp, _, fns in os.walk(_BACKEND):
        if "__pycache__" in dp:
            continue
        if not include_tests and (os.sep + "tests") in dp:
            continue
        for fn in fns:
            if fn.endswith(".py"):
                yield os.path.join(dp, fn)


def _rel(path: str) -> str:
    return os.path.relpath(path, _ROOT).replace(os.sep, "/")


def _line_count(path: str) -> int:
    with open(path, encoding="utf-8", errors="ignore") as f:
        return len(f.read().splitlines())


class TestNoDeadServiceModules(unittest.TestCase):
    """Rule: no orphan module — every service module must be imported somewhere."""

    # Intentional standalone modules (adoption/foundation pending). Keep tiny.
    ALLOWLIST = {"__init__", "error_response"}

    def test_every_service_module_is_imported(self):
        svc = sorted(
            f[:-3] for f in os.listdir(_SERVICES)
            if f.endswith(".py") and f != "__init__.py"
        )
        blobs = []
        for p in _iter_backend_py(include_tests=True):
            base = os.path.basename(p)[:-3]
            try:
                blobs.append((base, open(p, encoding="utf-8", errors="ignore").read()))
            except OSError:
                continue
        dead = []
        for s in svc:
            if s in self.ALLOWLIST:
                continue
            pat = re.compile(
                r"(from\s+services\.%s\b|import\s+%s\b|from\s+\.%s\b|services\.%s\b)"
                % ((re.escape(s),) * 4)
            )
            if not any(base != s and pat.search(txt) for base, txt in blobs):
                dead.append(s)
        self.assertEqual(
            dead, [],
            f"Dead service module(s) with zero importers: {dead}. "
            "Delete them or wire them in (rule: no orphan modules).",
        )


class TestRoutersMounted(unittest.TestCase):
    """Rule: no orphan router — every backend/routers/*.py must be mounted in main.

    A feature router that is never included is dead code AND a set of missing
    endpoints, so guard it the same way we guard dead service modules."""

    def test_every_router_is_included_in_main(self):
        routers_dir = os.path.join(_BACKEND, "routers")
        if not os.path.isdir(routers_dir):
            self.skipTest("no routers package")
        main_txt = open(os.path.join(_BACKEND, "main.py"), encoding="utf-8", errors="ignore").read()
        orphans = []
        for fn in sorted(os.listdir(routers_dir)):
            if not fn.endswith(".py") or fn == "__init__.py":
                continue
            mod = fn[:-3]
            # Must be imported from the routers package AND handed to include_router.
            imported = re.search(r"from\s+routers\s+import\s+[^\n]*\b%s\b" % re.escape(mod), main_txt)
            if not (imported and "include_router" in main_txt):
                orphans.append(mod)
        self.assertEqual(
            orphans, [],
            f"Router module(s) not mounted in main.py: {orphans}. "
            "Import them and call app.include_router(...) (no orphan routers).",
        )


class TestFileSizeBudget(unittest.TestCase):
    """Size is a SMELL SIGNAL / WARNING only — NOT a hard law.

    Owner rule: if Architecture & Code Quality Rules (single responsibility,
    no mixed god-file) are followed, extra lines are fine. Do NOT shrink modules
    just to pass a line count. This check prints a warning when a file grows past
    the advisory baseline; it must NOT fail predeploy.
    Enforced elsewhere: dead modules, router mount, raw sqlite, SQL sprawl, etc.
    """

    DEFAULT_MAX_BACKEND = 700
    DEFAULT_MAX_FRONTEND = 800

    # Advisory baselines (splitlines). Informational only — never fail the suite.
    BASELINE = {
        "backend/main.py": 936,
        "backend/database.py": 1055,
        "backend/services/brain/brain.py": 882,
        "backend/services/brain/live_ops_executor.py": 998,
        "backend/services/broadcast/capsule_service.py": 903,
        "backend/services/memory/service.py": 900,
        "backend/services/voice/gen_service.py": 803,
        "backend/services/broadcast/azuracast_client.py": 798,
        "backend/services/brain/operations_workflows.py": 745,
        "backend/services/content/source_tools.py": 727,
        "frontend/app.js": 68,
        "frontend/js/voice.js": 927,
        "frontend/js/panels.js": 868,
    }

    def test_backend_files_within_budget(self):
        offenders = []
        for p in _iter_backend_py(include_tests=False):
            rel = _rel(p)
            ceiling = self.BASELINE.get(rel, self.DEFAULT_MAX_BACKEND)
            n = _line_count(p)
            if n > ceiling:
                offenders.append(f"{rel}: {n} > {ceiling}")
        if offenders:
            print(
                "\n[WARNING] Line-count smell (advisory only — not a failure). "
                "Split only if responsibilities mixed: "
                f"{offenders}"
            )
        # Always pass — Architecture rules are enforced by other tests.
        self.assertTrue(True)

    def test_frontend_within_budget(self):
        """Advisory line-count smell for frontend modules — never fails the suite."""
        frontend = os.path.join(_ROOT, "frontend")
        targets = [os.path.join(frontend, "app.js")]
        js_dir = os.path.join(frontend, "js")
        if os.path.isdir(js_dir):
            targets += [
                os.path.join(js_dir, f)
                for f in sorted(os.listdir(js_dir))
                if f.endswith(".js")
            ]
        offenders = []
        for p in targets:
            if not os.path.exists(p):
                continue
            rel = _rel(p)
            ceiling = self.BASELINE.get(rel, self.DEFAULT_MAX_FRONTEND)
            n = _line_count(p)
            if n > ceiling:
                offenders.append(f"{rel}: {n} > {ceiling}")
        if offenders:
            print(
                "\n[WARNING] Frontend line-count smell (advisory only — not a failure): "
                f"{offenders}"
            )
        self.assertTrue(True)


class TestDbAccessCentralized(unittest.TestCase):
    """Rule: DB connections only via database.get_db_connection(); no raw
    sqlite3.connect() scattered in business modules."""

    def test_no_raw_sqlite_connect_outside_database(self):
        offenders = []
        for p in _iter_backend_py(include_tests=False):
            rel = _rel(p)
            if rel == "backend/database.py":
                continue
            txt = open(p, encoding="utf-8", errors="ignore").read()
            if re.search(r"sqlite3\.connect\s*\(", txt):
                offenders.append(rel)
        self.assertEqual(
            offenders, [],
            f"Raw sqlite3.connect() found outside database.py: {offenders}. "
            "Use database.get_db_connection() instead.",
        )


class TestSqlSprawlRatchet(unittest.TestCase):
    """Rule 2/3: SQL belongs in the data layer (database.py + *_repository.py).

    Business service modules should not accumulate SQL. Existing offenders are
    baselined and may only RATCHET DOWN; any non-repository module not in the
    baseline must contain zero SQL (blocks new sprawl)."""

    # Current SQL (.execute) counts in business modules. Lower over time; never raise.
    BASELINE = {
        "broadcast_capsule_service.py": 14,
        "capsule_review_service.py": 3,
        "neena_brain.py": 2,
        "approval_queue_module.py": 1,
        "voice_gen_service.py": 1,
    }

    @staticmethod
    def _sql_count(path: str) -> int:
        txt = open(path, encoding="utf-8", errors="ignore").read()
        return len(re.findall(r"\.execute\s*\(", txt))

    def test_no_new_sql_in_business_modules(self):
        offenders = []
        for fn in sorted(os.listdir(_SERVICES)):
            if not fn.endswith(".py"):
                continue
            if fn.endswith("_repository.py"):  # data layer is allowed SQL
                continue
            n = self._sql_count(os.path.join(_SERVICES, fn))
            ceiling = self.BASELINE.get(fn, 0)
            if n > ceiling:
                offenders.append(f"{fn}: {n} > {ceiling}")
        self.assertEqual(
            offenders, [],
            "SQL sprawl in business module(s) — move SQL into a *_repository.py "
            f"data layer (or, if a baselined file grew, that is a regression): {offenders}",
        )


class TestErrorResponseContract(unittest.TestCase):
    """Rule 6: standard structured error format is available and correct."""

    def test_error_response_has_mandated_fields(self):
        import sys
        if _BACKEND not in sys.path:
            sys.path.insert(0, _BACKEND)
        from services.brain.contracts_foundation import ErrorResponse
        from services.error_response import build_error_response

        model_fields = getattr(ErrorResponse, "model_fields", None) or ErrorResponse.__fields__
        for field in ("error_code", "message", "details", "recoverable", "next_action"):
            self.assertIn(field, model_fields, f"ErrorResponse missing rule-6 field: {field}")

        resp = build_error_response(
            "E_TEST", "kuch galat hua", recoverable=True, next_action="retry"
        )
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error_code"], "E_TEST")
        self.assertTrue(resp["recoverable"])
        self.assertEqual(resp["next_action"], "retry")


if __name__ == "__main__":
    unittest.main()
