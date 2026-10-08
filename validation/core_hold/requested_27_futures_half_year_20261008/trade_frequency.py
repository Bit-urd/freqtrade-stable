import collections,csv,datetime,gzip,json,statistics
from pathlib import Path
root=Path(__file__).resolve().parent
output=[]
def gaps(times):
    times=sorted(times);return [(b-a)/86400000 for a,b in zip(times,times[1:])]
def describe(times):
    times=sorted(times);days=sorted(set(t//86400000 for t in times));delta=gaps(times);daygap=[b-a for a,b in zip(days,days[1:])]
    return dict(count=len(times),active_days=len(days),mean_event_gap_days=statistics.mean(delta) if delta else None,min_event_gap_days=min(delta) if delta else None,mean_active_day_gap_days=statistics.mean(daygap) if daygap else None,min_active_day_gap_days=min(daygap) if daygap else None,max_active_day_gap_days=max(daygap) if daygap else None,max_orders_same_day=max(collections.Counter(t//86400000 for t in times).values()) if times else 0)
for window in ['Requested27','Mature26','Official9']:
 for name in ['BtcCoinGuardCycleRiskStrategy','BtcTwoDayExitCycleRiskStrategy']:
    payload=json.load(gzip.open(root/'results'/window/(name+'.json.gz'),'rt'));trades=payload['trades'];buy=[];sell=[];entries=[];pair_entries=collections.defaultdict(list);real_durations=[];flat_intervals=[]
    for trade in trades:
      orders=[o for o in trade['orders'] if o['order_filled_timestamp'] is not None]
      entries.append(trade['open_timestamp']);pair_entries[trade['pair']].append(trade['open_timestamp'])
      if trade['exit_reason']=='force_exit':orders=orders[:-1]
      else:real_durations.append((trade['close_timestamp']-trade['open_timestamp'])/86400000)
      for o in orders:(buy if o['ft_is_entry'] else sell).append(o['order_filled_timestamp'])
    same_coin=[]
    for p,times in pair_entries.items():same_coin+=gaps(times)
    for p in pair_entries:
      group=sorted([t for t in trades if t['pair']==p],key=lambda t:t['open_timestamp'])
      for prev,current in zip(group,group[1:]):flat_intervals.append((current['open_timestamp']-prev['close_timestamp'])/86400000)
    record=dict(window=window,strategy=name,calendar_days=183,entries=describe(entries),buys=describe(buy),sells=describe(sell),all_actual_orders=describe(buy+sell),real_closed_positions=len(real_durations),ending_open_positions=sum(t['exit_reason']=='force_exit' for t in trades),calendar_days_per_entry=183/len(entries),calendar_days_per_active_order_day=183/describe(buy+sell)['active_days'],same_coin_entry_gap_mean_days=statistics.mean(same_coin),same_coin_entry_gap_min_days=min(same_coin),flat_before_reentry_min_days=min(flat_intervals),real_closed_holding_mean_days=statistics.mean(real_durations),real_closed_holding_min_days=min(real_durations))
    output.append(record)
(root/'trade_frequency.json').write_text(json.dumps(dict(excludes_terminal_force_exits=True,counts_filled_orders_only=True,results=output),ensure_ascii=False,indent=2)+'\n')
for r in output:print(json.dumps(r,ensure_ascii=False))
