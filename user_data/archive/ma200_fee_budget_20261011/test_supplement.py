import json, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pandas as pd
from freqtrade.enums import RunMode
from ma200_cash_supplement import Ma200CashSupplementStrategy, proportional_cash


class FakeTrade:
    def __init__(self, i, now):
        self.id = i; self.pair = f'COIN{i}/USDT'; self.amount = 20.; self.stake_amount = 200.
        self.open_rate = 10.; self.fee_open = .001; self.open_date_utc = now-timedelta(days=10)
        self.enter_tag = 'bull_btc_regime_ema_alignment'; self.has_open_orders = False; self.data = {}
    def get_custom_data(self, key, default=None): return self.data.get(key, default)
    def set_custom_data(self, key, value): self.data[key] = value


class Tests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026,10,1,tzinfo=timezone.utc); self.cash = 1000.
        self.trades = [FakeTrade(i, self.now) for i in range(5)]
        self.s = self.strategy()
        self.proxy = patch('ma200_cash_supplement.Trade.get_trades_proxy', side_effect=lambda **kw:self.trades)
        self.proxy.start(); self.addCleanup(self.proxy.stop)
        self.parent = patch('ma200_cash_supplement._Ma200ConfirmedHandoverStrategy.adjust_trade_position', return_value=None)
        self.core = self.parent.start(); self.addCleanup(self.parent.stop)
    def row(self, pair, now):
        lag=(self.now-now).days
        return {'date':now-timedelta(days=1),'close':10.,'ema20':9.-lag*.1,'ema50':8.-lag*.1,
                'btc_bull_2d':True,'btc_above':True,'bull_exit':False,'weekly_bull':True,
                'volume':100.,'own_candles':500,'bear_target':0.}
    def strategy(self):
        s=Ma200CashSupplementStrategy({'stake_currency':'USDT','max_open_trades':5,'fee':.001})
        s.wallets=SimpleNamespace(get_free=lambda currency:self.cash)
        s.dp=SimpleNamespace(runmode=RunMode.BACKTEST,current_whitelist=lambda:[t.pair for t in self.trades])
        s._cash_row=self.row
        s._synthetic_fee_reserve=lambda:0.
        return s
    def call(self, t=None, now=None, s=None, minimum=5.):
        return (s or self.s).adjust_trade_position(t or self.trades[0],now or self.now,10.,0.,minimum,10000.,10.,10.,0.,0.)
    def test_deposit_with_unchanged_targets(self):self.assertAlmostEqual(self.call()[0],1000/1.001/5)
    def test_parent_buy_passthrough(self):self.core.return_value=123.;self.assertEqual(self.call(),123.);self.assertEqual(self.s.funding_trace,[])
    def test_parent_sell_passthrough(self):self.core.return_value=-100.;self.assertEqual(self.call(),-100.)
    def test_parent_tuple_passthrough(self):self.core.return_value=(40.,'parent');self.assertEqual(self.call(),(40.,'parent'))
    def test_parent_called_with_original_limits(self):
        self.call();self.assertEqual(self.core.call_args.args[0],self.trades[0]);self.assertEqual(self.core.call_args.args[4],5.);self.assertAlmostEqual(self.core.call_args.args[5],1000./1.001)
    def test_disabled_exact_parent(self):self.s.config['cash_supplement_enabled']=False;self.core.return_value=89.;self.assertEqual(self.call(),89.);self.assertEqual(self.s.funding_trace,[])
    def test_parent_state_change_without_order_blocks(self):
        def effect(trade,*args,**kw):trade.set_custom_data(self.s.TARGET_KEY,.5)
        self.core.side_effect=effect;self.assertIsNone(self.call());self.assertEqual(self.s.funding_trace,[])
    def test_supplement_never_changes_risk_state(self):
        t=self.trades[0];t.set_custom_data(self.s.TARGET_KEY,1.);t.set_custom_data(self.s.WEEKLY_SEEN_KEY,True)
        before={k:t.get_custom_data(k) for k in [self.s.TARGET_KEY,self.s.WEEKLY_SEEN_KEY,self.s.HANDOVER_KEY]}
        self.call();self.assertEqual(before,{k:t.get_custom_data(k) for k in before})
    def test_half_risk_target_remains_half_with_deposit(self):
        for t in self.trades:
            t.amount=10.;t.stake_amount=100.
            t.set_custom_data(self.s.WEEKLY_SEEN_KEY,True);t.set_custom_data(self.s.TARGET_KEY,.5)
        original=self.s._cash_row
        self.s._cash_row=lambda p,n:{**original(p,n),'weekly_bull':False}
        self.assertAlmostEqual(self.call()[0],50.)
        self.assertEqual(self.trades[0].get_custom_data(self.s.TARGET_KEY),.5)
    def test_other_coin_transition_reserves_cash(self):
        t=self.trades[1];t.set_custom_data(self.s.WEEKLY_SEEN_KEY,True);t.set_custom_data(self.s.TARGET_KEY,.5);self.assertIsNone(self.call())
    def test_other_coin_pending_order_only_blocks_itself(self):
        pending=self.trades[1];pending.has_open_orders=True
        self.assertIsNone(self.call(pending))
        self.assertIsNotNone(self.call())
        plan=self.s._supplement_plan
        self.assertNotIn(str(pending.id),plan['allocation'])
        self.assertNotIn(str(pending.id),plan['targets'])
    def test_pending_order_remaining_cash_is_not_overspent(self):
        self.cash=120.;self.trades[1].has_open_orders=True
        total=0.
        for t in reversed(self.trades):
            result=self.call(t)
            if result is None:continue
            amount=result[0];total+=amount
            self.cash-=amount*1.001;t.amount+=amount/10.
        self.assertLessEqual(total*1.001,120.+1e-8)
        self.assertGreater(total,0.)
        self.assertGreaterEqual(self.cash,-1e-8)
    def test_all_pending_orders_have_no_supplement_claims(self):
        for t in self.trades:t.has_open_orders=True
        self.assertEqual(self.s._cash_plan(self.now)['allocation'],{})
    def test_pending_order_does_not_override_another_parent_transition(self):
        self.trades[1].has_open_orders=True
        t=self.trades[2];t.set_custom_data(self.s.WEEKLY_SEEN_KEY,True)
        t.set_custom_data(self.s.TARGET_KEY,.5)
        self.assertIsNone(self.call())
    def test_other_coin_parent_action_reserves_cash(self):
        t=self.trades[1];self.core.return_value=100.;self.call(t);self.core.return_value=None;self.assertIsNone(self.call())
    def test_unhanded_bear_reserves_cash(self):self.trades[1].enter_tag='bear_accumulate';self.assertIsNone(self.call())
    def test_unheld_entry_reserves_slot_and_allows_remaining_cash(self):
        self.s.dp.current_whitelist=lambda:[t.pair for t in self.trades]+['NEW/USDT']
        self.trades.pop()
        self.assertIsNotNone(self.call())
        plan=self.s._supplement_plan
        self.assertAlmostEqual(plan['entry_cash_reserve'],360.*1.001)
        self.assertLessEqual(sum(plan['allocation'].values())*1.001,plan['supplement_cash']+1e-8)
    def test_unknown_unheld_history_reserves_all_cash(self):
        self.trades.pop();self.s.dp.current_whitelist=lambda:[t.pair for t in self.trades]+['NEW/USDT']
        original=self.s._cash_row
        self.s._cash_row=lambda p,n:None if p=='NEW/USDT' else original(p,n)
        self.assertIsNone(self.call())
        self.assertEqual(self.s._supplement_plan['entry_cash_reserve'],self.cash)
    def test_entry_reservation_leaves_cash_after_all_fills(self):
        self.trades.pop();self.s.dp.current_whitelist=lambda:[t.pair for t in self.trades]+['NEW/USDT']
        reserve=self.s._cash_plan(self.now)['entry_cash_reserve']
        for t in reversed(self.trades):
            r=self.call(t)
            if r:self.cash-=r[0]*1.001;t.amount+=r[0]/10.
        self.assertGreaterEqual(self.cash,reserve-1e-8)
    def test_no_entry_with_empty_slots_does_not_reserve(self):
        self.trades.pop();self.s.dp.current_whitelist=lambda:[t.pair for t in self.trades]+['NEW/USDT']
        original=self.s._cash_row
        self.s._cash_row=lambda p,n:{**original(p,n),'btc_above':False,'bear_target':0.} if p=='NEW/USDT' else original(p,n)
        self.assertEqual(self.s._cash_plan(self.now)['entry_cash_reserve'],0.)
    def test_inactive_empty_slot_keeps_its_budget(self):
        self.trades=self.trades[:2];self.assertAlmostEqual(sum(self.s._cash_plan(self.now)['allocation'].values()),160.)
    def test_fee_budget_and_order_independence(self):
        amounts=[]
        for t in reversed(self.trades):
            request=self.call(t);amount=request[0];amounts.append(amount);self.cash-=amount*1.001;t.amount+=amount/10.;t.stake_amount+=amount
        self.assertAlmostEqual(sum(amounts)*1.001,1000.);self.assertGreaterEqual(self.cash,-1e-8)
    def test_same_day_no_duplicate(self):self.call();self.assertIsNone(self.call())
    def test_restart_no_duplicate(self):self.call();self.assertIsNone(self.call(s=self.strategy()))
    def test_restart_restores_fixed_budget(self):
        a=self.s._cash_plan(self.now);self.cash=900.;self.assertEqual(self.strategy()._cash_plan(self.now),a)
    def test_cancellation_retries_next_day(self):self.call();self.assertIsNotNone(self.call(now=self.now+timedelta(days=1)))
    def test_partial_fill_remaining_next_day(self):
        r=self.call();self.trades[0].amount+=r[0]/20.;self.cash-=r[0]*.5*1.001;self.assertIsNotNone(self.call(now=self.now+timedelta(days=1)))
    def test_no_extra_buy_when_cash_zero(self):self.cash=0.;self.assertIsNone(self.call())
    def test_missing_held_history_blocks(self):
        original=self.s._cash_row;self.s._cash_row=lambda p,n:None if p==self.trades[1].pair else original(p,n);self.assertIsNone(self.call())
    def test_weak_coin_not_replenished(self):self.s._cash_qualified=lambda *args:False;self.assertIsNone(self.call())
    def test_no_forced_sell_of_winner(self):self.trades[0].amount=100.;self.assertIsNone(self.call())
    def test_minimum_order_not_marked_requested(self):self.assertIsNone(self.call(minimum=1000.));self.assertIsNone(self.trades[0].get_custom_data(self.s.REQUEST_KEY))
    def test_new_trade_not_supplemented(self):self.trades[0].open_date_utc=self.now;self.assertIsNone(self.call())
    def test_only_closed_rows_not_future(self):
        s=Ma200CashSupplementStrategy({'stake_currency':'USDT','max_open_trades':5});s.dp=self.s.dp
        s._supplement_frames['BTC/USDT']=pd.DataFrame({'date':[self.now-timedelta(days=1),self.now],'close':[10.,100.]})
        self.assertEqual(s._cash_row('BTC/USDT',self.now)['close'],10.)
    def test_stale_row_rejected(self):
        s=Ma200CashSupplementStrategy({'stake_currency':'USDT','max_open_trades':5});s.dp=self.s.dp
        s._supplement_frames['BTC/USDT']=pd.DataFrame({'date':[self.now-timedelta(days=3)],'close':[10.]})
        self.assertIsNone(s._cash_row('BTC/USDT',self.now))
    def test_real_parent_constant_target_allows_supplement(self):
        self.parent.stop();self.s._weekly_target=lambda *args:1.
        self.assertIsNotNone(self.call())
    def test_real_parent_weekly_sell_is_unchanged(self):
        self.parent.stop();t=self.trades[0];t.set_custom_data(self.s.WEEKLY_SEEN_KEY,True);t.set_custom_data(self.s.TARGET_KEY,1.)
        self.s._weekly_target=lambda *args:.5;self.assertEqual(self.call(),-100.);self.assertEqual(t.get_custom_data(self.s.TARGET_KEY),.5)
    def test_real_parent_restore_buy_is_unchanged(self):
        self.parent.stop();t=self.trades[0];t.set_custom_data(self.s.WEEKLY_SEEN_KEY,True);t.set_custom_data(self.s.TARGET_KEY,.5)
        self.s._weekly_target=lambda *args:1.;self.s._equity=lambda *args:2000.
        self.assertEqual(self.call(),200.);self.assertEqual(t.get_custom_data(self.s.TARGET_KEY),1.)
    def test_synthetic_cash_subtracts_remaining_entry_fees(self):
        del self.s._synthetic_fee_reserve
        self.assertAlmostEqual(self.s._spendable_cash(),999.)
    def test_live_cash_does_not_subtract_existing_fees(self):
        del self.s._synthetic_fee_reserve
        self.s.dp.runmode=RunMode.LIVE
        self.assertEqual(self.s._spendable_cash(),1000.)
    def test_synthetic_negative_cash_cannot_buy(self):
        del self.s._synthetic_fee_reserve
        self.cash=.5
        self.assertEqual(self.s._spendable_cash(),0.)
        self.assertIsNone(self.call())
    def test_entry_budget_includes_fee_and_minimum(self):
        with patch('ma200_cash_supplement._Ma200ConfirmedHandoverStrategy.custom_stake_amount',return_value=10000.):
            amount=self.s.custom_stake_amount('COIN0/USDT',self.now,10.,1000.,5.,10000.,1.,None,'long')
            self.assertAlmostEqual(amount*1.001,1000.)
            self.cash=1.
            self.assertEqual(self.s.custom_stake_amount('COIN0/USDT',self.now,10.,1000.,5.,10000.,1.,None,'long'),0.)
    def test_proportional_invalid_values(self):self.assertEqual(proportional_cash({'x':float('nan')},10.,.001),{})


if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    Path(__file__).with_name('unit_results.json').write_text(json.dumps({'tests':r.testsRun,'passed':r.wasSuccessful(),'scope':'actual callbacks, parent delegation and unchanged states, mocked wallet/trades'},indent=2)+'\n')
    import sys, os
    sys.stdout.flush(); sys.stderr.flush(); os._exit(0 if r.wasSuccessful() else 1)
