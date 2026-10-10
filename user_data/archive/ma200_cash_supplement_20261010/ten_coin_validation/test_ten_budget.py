import json,unittest
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from ma200_cash_supplement import Ma200CashSupplementStrategy

class FakeTrade:
    def __init__(self,i,now):
        self.id=i;self.pair=f'COIN{i}/USDT';self.amount=10.;self.stake_amount=100.;self.open_rate=10.;self.fee_open=.001
        self.open_date_utc=now-timedelta(days=10);self.enter_tag='bull_btc_regime_ema_alignment';self.has_open_orders=False;self.data={}
    def get_custom_data(self,k,default=None):return self.data.get(k,default)
    def set_custom_data(self,k,v):self.data[k]=v

class TenBudget(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,1,tzinfo=timezone.utc);self.cash=1000.;self.trades=[FakeTrade(i,self.now) for i in range(10)]
        self.s=Ma200CashSupplementStrategy({'stake_currency':'USDT','max_open_trades':10,'fee':.001})
        self.s.wallets=SimpleNamespace(get_free=lambda c:self.cash);self.s.dp=SimpleNamespace(current_whitelist=lambda:[t.pair for t in self.trades])
        self.s._cash_row=lambda p,n:{'date':n-timedelta(days=1),'close':10.,'ema20':9.-(self.now-n).days*.1,'ema50':8.-(self.now-n).days*.1,'btc_bull_2d':True,'bull_exit':False,'weekly_bull':True,'volume':100.}
        for name,args in [('ma200_cash_supplement.Trade.get_trades_proxy',{'side_effect':lambda **kw:self.trades}),('ma200_cash_supplement.Ma200ConfirmedHandoverStrategy.adjust_trade_position',{'return_value':None})]:
            p=patch(name,**args);p.start();self.addCleanup(p.stop)
    def call(self,t):return self.s.adjust_trade_position(t,self.now,10.,0.,5.,10000.,10.,10.,0.,0.)
    def test_ten_deposit_no_duplicate_or_overspend(self):
        totals=[]
        for t in reversed(self.trades):
            amount,tag=self.call(t);totals.append(amount);self.cash-=amount*1.001;t.amount+=amount/10.;t.stake_amount+=amount
            self.assertIsNone(self.call(t))
        self.assertAlmostEqual(sum(totals)*1.001,1000.);self.assertGreaterEqual(self.cash,-1e-8)
        self.assertAlmostEqual(totals[0],1000/1.001/10)
    def test_ten_parent_transition_reserves_cash(self):
        self.trades[9].set_custom_data(self.s.WEEKLY_SEEN_KEY,True);self.trades[9].set_custom_data(self.s.TARGET_KEY,.5)
        self.assertIsNone(self.call(self.trades[0]))
    def test_winner_not_sold_or_replenished(self):self.trades[0].amount=100.;self.assertIsNone(self.call(self.trades[0]))

if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TenBudget))
    Path(__file__).with_name('unit_results.json').write_text(json.dumps({'tests':r.testsRun,'passed':r.wasSuccessful(),'scope':'actual unchanged callbacks with ten held trades and refreshed mock wallet'},indent=2)+'\n')
    import sys,os
    sys.stdout.flush();sys.stderr.flush();os._exit(0 if r.wasSuccessful() else 1)
