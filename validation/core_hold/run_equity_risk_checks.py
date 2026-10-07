"""Run both corrected-controller check suites in one process."""
import os
import sys
import unittest
import json
from pathlib import Path
import test_equity_risk
import test_cycle_risk
suite=unittest.TestSuite([
    unittest.defaultTestLoader.loadTestsFromModule(test_equity_risk),
    unittest.defaultTestLoader.loadTestsFromModule(test_cycle_risk),
])
result=unittest.TextTestRunner().run(suite)
Path('/research/archive/portfolio_cycle_risk_v2/rule_checks.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)},indent=2)+'\n')
sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
