"""检查连续两天确认、退出优先级、缺失数据和因果性。"""
import sys,unittest,json,os
from pathlib import Path
from unittest.mock import Mock,patch
import pandas as pd
sys.path.insert(0,'/research/cycle_risk_coin_momentum_revision/strategies')
from coin_momentum_strategy import BtcCoinGuardCoinMomentumEntryStrategy as A,BtcCoinGuardCoinMomentumExitStrategy as B
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy as Base

class Rules(unittest.TestCase):
    def make(self,cls):return cls({'stake_currency':'USDT','max_open_trades':3,'dry_run':True})
    def indicators(self,cls,frame):
        with patch.object(Base,'populate_indicators',autospec=True,side_effect=lambda obj,frame,meta:frame.copy()):return self.make(cls).populate_indicators(frame,{'pair':'SOL/USDT'})
    def frame(self):return pd.DataFrame({'close':[9,11,12,9,8,11],'ema20':[10]*6,'enter_long':[1]*6,'enter_tag':['base']*6})
    def test_two_day_confirmation(self):
        f=self.indicators(A,self.frame());self.assertEqual(f.coin_medium_entry.tolist(),[False,False,True,False,False,False])
    def test_two_day_medium_exit(self):
        f=self.indicators(B,self.frame());self.assertEqual(f.coin_medium_exit.tolist(),[False,False,False,False,True,False])
    def test_entry_only_filters_candidates_and_preserves_tags(self):
        f=self.indicators(A,self.frame());f.loc[2,'enter_long']=0
        with patch.object(Base,'populate_entry_trend',autospec=True,side_effect=lambda obj,frame,meta:frame.copy()):out=self.make(A).populate_entry_trend(f,{'pair':'SOL/USDT'})
        self.assertEqual(out.enter_long.tolist(),[0]*6);self.assertEqual(out.enter_tag.tolist(),['base']*6)
    def test_future_data_does_not_change_prior_signals(self):
        f=self.frame();old=self.indicators(B,f);new=self.indicators(B,pd.concat([f,pd.DataFrame({'close':[1e9],'ema20':[.01]})],ignore_index=True))
        for key in ['coin_medium_entry','coin_medium_exit']:self.assertEqual(old[key].tolist(),new[key].iloc[:-1].tolist())
    def test_original_exit_priority(self):
        s=self.make(B);s._last_closed_row=Mock(return_value={'coin_medium_exit':True})
        with patch.object(Base,'custom_exit',return_value='trend_to_cash'):self.assertEqual(s.custom_exit('SOL/USDT',None,None,1,0),'trend_to_cash')
    def test_missing_exit_data_does_not_create_signal(self):
        s=self.make(B)
        with patch.object(Base,'custom_exit',return_value=None):
            for row in [None,{}, {'coin_medium_exit':float('nan')}]:s._last_closed_row=Mock(return_value=row);self.assertIsNone(s.custom_exit('SOL/USDT',None,None,1,0))
    def test_confirmed_new_exit(self):
        s=self.make(B);s._last_closed_row=Mock(return_value={'coin_medium_exit':True})
        with patch.object(Base,'custom_exit',return_value=None):self.assertEqual(s.custom_exit('SOL/USDT',None,None,1,0),'coin_medium_to_cash')
    def test_account_risk_stake_and_fills_unchanged(self):
        for cls in [A,B]:
            for method in ['bot_loop_start','next_fraction','custom_stake_amount','adjust_trade_position','order_filled','_pair_budget']:self.assertIs(getattr(cls,method),getattr(Base,method))

if __name__=='__main__':
    import test_equity_risk,test_cycle_risk
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Rules),unittest.defaultTestLoader.loadTestsFromModule(test_equity_risk),unittest.defaultTestLoader.loadTestsFromModule(test_cycle_risk)])
    result=unittest.TextTestRunner().run(suite)
    Path('/research/cycle_risk_coin_momentum_revision/rule_checks.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests_run':result.testsRun},indent=2)+'\n')
    sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
