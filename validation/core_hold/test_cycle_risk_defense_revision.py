"""检查防守过滤只减少候选开仓，保留退出/风控及指标因果性。"""
import sys,unittest,json,os
from pathlib import Path
from unittest.mock import Mock,patch
import pandas as pd
sys.path.insert(0,'/research/cycle_risk_defense_revision/strategies')
from defensive_entry_strategy import BtcCoinGuardConfirmedBtcEntryStrategy as A,BtcCoinGuardSelectiveRecoveryEntryStrategy as B
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy as Base

class Rules(unittest.TestCase):
    def make(self,cls):return cls({'stake_currency':'USDT','max_open_trades':3,'dry_run':True})
    def frame(self):
        return pd.DataFrame({'enter_long':[1,1,1,1,0,1],'enter_tag':['original']*6,'defense_btc_confirmed':[False,False,True,True,True,None],'ema20':[9,12,9,12,12,9],'ema50':[10,11,10,11,11,10]})
    def entry(self,cls,frame):
        with patch.object(Base,'populate_entry_trend',autospec=True,side_effect=lambda obj,frame,meta:frame.copy()):return self.make(cls).populate_entry_trend(frame,{'pair':'SOL/USDT'})
    def test_confirmed_gate_blocks_unconfirmed_and_missing(self):self.assertEqual(self.entry(A,self.frame()).enter_long.tolist(),[0,0,1,1,0,0])
    def test_selective_allows_medium_strength_exception(self):self.assertEqual(self.entry(B,self.frame()).enter_long.tolist(),[0,1,1,1,0,0])
    def test_no_candidates_are_created(self):
        for cls in [A,B]:
            f=self.frame();f['enter_long']=0;self.assertTrue((self.entry(cls,f).enter_long==0).all())
    def test_tags_preserved(self):
        for cls in [A,B]:self.assertEqual(self.entry(cls,self.frame()).enter_tag.tolist(),self.frame().enter_tag.tolist())
    def test_risk_exit_budget_and_fill_methods_unchanged(self):
        for cls in [A,B]:
            for name in ['bot_loop_start','next_fraction','custom_exit','adjust_trade_position','custom_stake_amount','order_filled','_pair_budget','confirm_trade_entry']:self.assertIs(getattr(cls,name),getattr(Base,name))
    def test_future_prices_do_not_change_confirmation_history(self):
        s=self.make(A);h=pd.DataFrame({'date':pd.date_range('2024-01-01',periods=220,tz='UTC'),'close':list(range(100,320))})
        def indicators(hist):
            s._history=Mock(return_value=hist)
            with patch.object(Base,'populate_indicators',side_effect=lambda frame,meta:frame.copy()):return s.populate_indicators(hist[['date']].copy(),{'pair':'ETH/USDT'})
        old=indicators(h);future=pd.DataFrame({'date':[h.date.iloc[-1]+pd.Timedelta(days=1)],'close':[.001]})
        new=indicators(pd.concat([h,future],ignore_index=True))
        self.assertEqual(old.defense_btc_confirmed.tolist(),new.defense_btc_confirmed.iloc[:-1].tolist())
        self.assertFalse(old.defense_btc_confirmed.iloc[199]);self.assertTrue(old.defense_btc_confirmed.iloc[200])
    def test_future_rows_do_not_change_medium_entry(self):
        f=self.frame();old=self.entry(B,f)
        future=pd.DataFrame({'enter_long':[1],'enter_tag':['future'],'defense_btc_confirmed':[True],'ema20':[100000],'ema50':[.01]})
        new=self.entry(B,pd.concat([f,future],ignore_index=True));self.assertEqual(old.enter_long.tolist(),new.enter_long.iloc[:-1].tolist())

if __name__=='__main__':
    import test_equity_risk,test_cycle_risk
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Rules),unittest.defaultTestLoader.loadTestsFromModule(test_equity_risk),unittest.defaultTestLoader.loadTestsFromModule(test_cycle_risk)])
    result=unittest.TextTestRunner().run(suite)
    Path('/research/cycle_risk_defense_revision/rule_checks.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests_run':result.testsRun,'new_entry_checks':7,'existing_risk_checks':13},indent=2)+'\n')
    sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
