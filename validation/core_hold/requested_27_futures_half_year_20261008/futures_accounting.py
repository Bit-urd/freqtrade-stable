import json
from pathlib import Path
import numpy as np
import pandas as pd
from freqtrade.persistence import Trade
ROOT=Path(__file__).resolve().parent
CAPITAL=10000.;FEE=.0005;PAIRS=[];HISTORY={};FUND={};PREFIX={}
for path in (ROOT/'raw').glob('*.json'):
    rows=json.loads(path.read_text())['funding']['rows'];pair=path.stem+'/USDT:USDT'
    f=pd.DataFrame(rows);f['date']=pd.to_datetime(f.fundingTime,unit='ms',utc=True);f['unit_cost']=f.fundingRate.astype(float)*f.markPrice.astype(float)
    FUND[pair]=f.set_index('date').unit_cost.sort_index();FUND[pair].index=FUND[pair].index.as_unit('ns');PREFIX[pair]=FUND[pair].cumsum()
def cumulative(pair,when):
    data=PREFIX[pair];i=data.index.searchsorted(pd.Timestamp(when),side='right');return float(data.iloc[i-1]) if i else 0.
def live_equity(strategy,current_time):
    cutoff=pd.Timestamp(current_time).floor('D')-pd.Timedelta(nanoseconds=1);cash=10000.;quantities={}
    for trade in Trade.get_trades_proxy(is_open=True)+Trade.get_trades_proxy(is_open=False):
        pair=trade.pair
        for order in trade.orders:
            if order.ft_is_open or not order.filled or order.order_filled_date is None:continue
            when=pd.Timestamp(order.order_filled_utc)
            if when>cutoff:continue
            qty=float(order.safe_amount_after_fee);rate=float(order.safe_price);entry=order.ft_order_side==trade.entry_side;delta=qty if entry else -qty
            cash+=-qty*rate*(1+trade.fee_open) if entry else qty*rate*(1-trade.fee_close)
            cash-=delta*(cumulative(pair,cutoff)-cumulative(pair,when));quantities[pair]=quantities.get(pair,0)+delta
    for pair,qty in quantities.items():
        if abs(qty)>1e-8:
            price=strategy._closed_price(pair,current_time)
            if price is None:raise ValueError('Missing prior complete price')
            cash+=qty*price
    return cash

def stats(curve):
    peak=curve.equity.cummax().clip(lower=10000)
    return dict(return_pct=(curve.equity.iloc[-1]/10000-1)*100,liquidated_return_pct=(curve.equity.iloc[-1]/10000-1)*100,wallet_drawdown_pct=(1-curve.equity/peak).max()*100,mean_idle_cash_pct=(curve.cash/curve.equity).mean()*100,ending_equity=curve.equity.iloc[-1])
def ledger(trades,dates,skip_force=True):
    flows=pd.Series(0.,index=dates);dq=pd.DataFrame(0.,index=dates,columns=PAIRS);fundflows=pd.Series(0.,index=dates);terminal_cash=10000.;events=[]
    for trade in trades:
        pair=trade['pair'];normal=[]
        orders=[o for o in trade['orders'] if o['order_filled_timestamp'] is not None]
        for i,order in enumerate(orders):
            qty=float(order['amount']);rate=float(order['safe_price']);entry=order['ft_is_entry'];fee=trade['fee_open'] if entry else trade['fee_close'];flow=-qty*rate*(1+fee) if entry else qty*rate*(1-fee);terminal_cash+=flow
            when=pd.to_datetime(order['order_filled_timestamp'],unit='ms',utc=True);delta=qty if entry else -qty
            if not(skip_force and trade['exit_reason']=='force_exit' and i==len(orders)-1):
                day=when.floor('D');flows.loc[day]+=flow;dq.loc[day,pair]+=delta;normal.append((when,delta));events.append((pair,day,entry))
        terminal_cash+=float(trade.get('funding_fees') or 0)
        for when,delta in normal:
            f=FUND[pair];f=f.loc[(f.index>when)&(f.index<=dates[-1]+pd.Timedelta(days=1)-pd.Timedelta(nanoseconds=1))]
            for time,cost in f.items():fundflows.loc[time.floor('D')]-=delta*cost
    cash=10000+flows.cumsum()+fundflows.cumsum();qty=dq.cumsum();prices=pd.DataFrame({p:HISTORY[p].close.reindex(dates) for p in PAIRS})
    assert not ((qty.abs()>1e-7)&prices.isna()).any().any()
    curve=pd.DataFrame({'cash':cash,'equity':cash+(qty*prices).fillna(0).sum(axis=1),'funding_pnl':fundflows.cumsum()})
    return curve,terminal_cash,events

def benchmark(dates):
    flows=pd.Series(0.,index=dates);dq=pd.DataFrame(0.,index=dates,columns=PAIRS);fundflows=pd.Series(0.,index=dates)
    for pair,hist in HISTORY.items():
        available=hist.iloc[61:];available=available.loc[(available.index>=dates[0])&(available.index<=dates[-1])]
        if available.empty:continue
        day=available.index[0];budget=10000/len(PAIRS);qty=budget/(1+FEE)/float(hist.loc[day,'open']);flows.loc[day]-=budget;dq.loc[day,pair]=qty
        for time,cost in FUND[pair].loc[FUND[pair].index>day].items():
            if time.floor('D') in dates:fundflows.loc[time.floor('D')]-=qty*cost
    cash=10000+flows.cumsum()+fundflows.cumsum();prices=pd.DataFrame({p:HISTORY[p].close.reindex(dates) for p in PAIRS});return pd.DataFrame({'cash':cash,'equity':cash+(dq.cumsum()*prices).fillna(0).sum(axis=1),'funding_pnl':fundflows.cumsum()})
