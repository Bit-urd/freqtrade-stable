import sys,unittest,json,os
from pathlib import Path
import test_sol_upside_revision
import test_equity_risk
import test_cycle_risk
suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(m) for m in [test_sol_upside_revision,test_equity_risk,test_cycle_risk]])
r=unittest.TextTestRunner().run(suite)
Path('/research/sol_upside_revision_v2/rule_checks.json').write_text(json.dumps({'passed':r.wasSuccessful(),'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors)},indent=2)+'\n')
sys.stdout.flush();sys.stderr.flush();os._exit(0 if r.wasSuccessful() else 1)
