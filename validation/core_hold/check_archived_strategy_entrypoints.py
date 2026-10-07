"""验证迁移后仍可复现归档CoreHold/FastExit/CoinGuard检查。"""
import unittest,sys,os,json
from pathlib import Path
import check_strategy,check_fast_exit,test_coin_guard
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in [check_strategy,check_fast_exit,test_coin_guard])
result=unittest.TextTestRunner().run(suite)
Path('/research/cycle_risk_flatten_verification/archived_entrypoint_checks.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests_run':result.testsRun},indent=2)+'\n');sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
