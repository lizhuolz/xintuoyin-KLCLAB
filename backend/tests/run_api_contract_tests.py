import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

suite = unittest.defaultTestLoader.discover(str(ROOT), pattern="test_api_contract.py")
result = unittest.TextTestRunner(verbosity=2).run(suite)
print(f"\nArtifacts: {ROOT / 'api_contract_results'}")
sys.exit(0 if result.wasSuccessful() else 1)
