"""Predeploy health and safety verification script for Neena command center."""
from __future__ import annotations

import sys
import os
import glob
import py_compile
import unittest

def run_compile_check() -> bool:
    print("=== Running Python Compilation Check ===")
    files = ['backend/main.py', 'backend/database.py'] + glob.glob('backend/services/*.py')
    for f in files:
        try:
            py_compile.compile(f, doraise=True)
        except Exception as e:
            print(f"Compilation FAILED for {f}: {e}")
            return False
    print("Compilation check: OK")
    return True

def run_unit_tests() -> bool:
    print("\n=== Running Safety & Foundation Unit Tests ===")
    # Ensure backend path is importable
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
        
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Load safety patch tests + code-quality guardrails (rules self-enforcement)
    try:
        suite.addTests(loader.discover('backend/tests', pattern='test_m4_a2_safety_patch.py'))
        suite.addTests(loader.discover('backend/tests', pattern='test_neena_foundation_m0.py'))
        suite.addTests(loader.discover('backend/tests', pattern='test_code_quality_guardrails.py'))
    except Exception as e:
        print(f"Error loading tests: {e}")
        return False
        
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()

if __name__ == '__main__':
    # Change working directory to radio-ai-manager root to match expected test cwd
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(root_dir)
    
    ok = run_compile_check() and run_unit_tests()
    if ok:
        print("\nPREDEPLOY CHECK: ALL PASSED")
        sys.exit(0)
    else:
        print("\nPREDEPLOY CHECK: FAILED")
        sys.exit(1)
