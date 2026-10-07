"""检查退出优先级、缺失信号防守、行情门控及指标因果性。"""
import sys,unittest,json,os
from pathlib import Path
from unittest.mock import Mock,patch
import pandas as pd
sys.path.insert(0,'/research/selective_coin_exit_revision/strategies')
from selective_coin_exit_strategy import BtcCoinGuardRisingMediumExitStrategy as S,BtcCoinGuardBtcConfirmedExitStrategy as T
from trend_aware_risk_strategy import BtcCoinGuardTrendRecoveryRiskStrategy as B
from recovery_refinement_strategy import BtcCoinGuardConfirmedCoinExitStrategy as C

class Rules(unittest.TestCase):
    def make(self,cls,row=None,btc=True):
        s=cls({'stake_currency':'USDT','max_open_trades':1,'dry_run':True})
        s._last_closed_row=Mock(return_value=row);s._btc_bull_confirmed=Mock(return_value=btc);return s
    def exit(self,s,original='coin_trend_to_cash'):
        with patch.object(B,'custom_exit',return_value=original):return s.custom_exit('SOL/USDT',None,None,1,0)
    def test_btc_exit_always_has_priority(self):
        for cls in [S,T]:self.assertEqual(self.exit(self.make(cls,{'coin_medium_weak':False,'coin_medium_rising':True}), 'trend_to_cash'),'trend_to_cash')
    def test_rising_requires_both_conditions(self):
        for weak,rising,expected in [(False,True,None),(False,False,'coin_trend_to_cash'),(True,True,'coin_trend_to_cash'),(True,False,'coin_trend_to_cash')]:
            self.assertEqual(self.exit(self.make(S,{'coin_medium_weak':weak,'coin_medium_rising':rising})),expected)
    def test_btc_gate_requires_both_conditions(self):
        for weak,btc,expected in [(False,True,None),(False,False,'coin_trend_to_cash'),(True,True,'coin_trend_to_cash'),(True,False,'coin_trend_to_cash')]:
            self.assertEqual(self.exit(self.make(T,{'coin_medium_weak':weak},btc)),expected)
    def test_missing_signal_never_delays_exit(self):
        for cls in [S,T]:
            for row in [None,{}, {'coin_medium_weak':float('nan'),'coin_medium_rising':float('nan')}]:self.assertEqual(self.exit(self.make(cls,row)),'coin_trend_to_cash')
    def test_no_exit_is_not_created(self):
        for cls in [S,T]:self.assertIsNone(self.exit(self.make(cls,{}),None))
    def test_future_rows_do_not_change_medium_slope(self):
        s=self.make(S);h=pd.DataFrame({'date':pd.date_range('2024-01-01',periods=220,tz='UTC'),'close':list(range(100,320))})
        def indicators(history):
            s._history=Mock(return_value=history)
            with patch.object(C,'populate_indicators',side_effect=lambda frame,meta:frame.copy()):return s.populate_indicators(history[['date']].copy(),{'pair':'SOL/USDT'})
        old=indicators(h)
        future=pd.DataFrame({'date':[h.date.iloc[-1]+pd.Timedelta(days=1)],'close':[.001]})
        new=indicators(pd.concat([h,future],ignore_index=True))
        self.assertEqual(old.coin_medium_rising.tolist(),new.coin_medium_rising.iloc[:-1].tolist())

if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Rules))
    Path('/research/selective_coin_exit_revision/rule_checks.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests_run':result.testsRun},indent=2)+'\n')
    sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
