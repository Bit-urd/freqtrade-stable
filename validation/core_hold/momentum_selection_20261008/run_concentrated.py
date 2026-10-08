"""Fresh-wallet Freqtrade portfolio backtests with identical frozen market data."""
import argparse
import copy
import csv
import gc
import gzip
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path
import pandas as pd
from freqtrade.commands.arguments import Arguments
from freqtrade.commands.optimize_commands import setup_optimize_configuration
from freqtrade.configuration import TimeRange
from freqtrade.enums import RunMode
from freqtrade.optimize.backtesting import Backtesting
from freqtrade.resolvers import StrategyResolver

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root.parent))
import analyze as a
prior = root.parent / 'independent_trend_optimization_20261008'
data_path = prior / 'data'
names = ['WeeklyTop2ConcentratedCycleRiskStrategy']
columns = ['window', 'universe', 'pair_count', 'start', 'end', 'days', 'strategy',
           'return_pct', 'liquidated_return_pct', 'wallet_drawdown_pct', 'mean_idle_cash_pct',
           'ending_equity', 'normal_fills', 'quick_loss_positions', 'normal_fees', 'ledger_error', 'trades']
parser = argparse.ArgumentParser(); parser.add_argument('--labels', nargs='+'); args = parser.parse_args()
windows = json.loads((root / 'windows.json').read_text())
if args.labels: windows = [w for w in windows if w['label'] in args.labels]
cli = Arguments(['backtesting', '-c', str(root / 'config.json'), '--datadir', str(data_path),
    '--strategy-path', str(root / 'strategies'), '--timerange', windows[0]['timerange'],
    '--fee', '0.001', '--cache', 'none', '--strategy-list', *names]).get_parsed_arg()
logging.disable(logging.WARNING)
config = setup_optimize_configuration(cli, RunMode.BACKTEST)
assert config['dry_run_wallet'] == 1000 and config['fee'] == .001
assert Path(config['datadir']) == data_path
bt = Backtesting(config, progress_callback=lambda task: None)
gc.freeze()
summary = root / 'summary.csv'
rows = list(csv.DictReader(summary.open())) if summary.exists() else []
references = {(r['window'], r['strategy']): r for r in csv.DictReader((prior / 'summary.csv').open())}
started = time.monotonic()
for i, window in enumerate(windows, 1):
    label, pairs = window['label'], window['pairs']
    folder = root / 'results' / label; folder.mkdir(parents=True, exist_ok=True)
    done = folder / 'concentrated_completed.json'
    if done.exists() and names[0] in {r['strategy'] for r in rows if r['window'] == label}:
        print('Cached', label, flush=True); continue
    rows = [r for r in rows if not (r['window'] == label and r['strategy'] in names)]
    bt.config['max_open_trades'] = 2
    bt.config['exchange']['pair_whitelist'] = pairs
    for handler in bt.pairlists._pairlist_handlers:
        if hasattr(handler, '_bt_pair_cache'): handler._bt_pair_cache.clear()
    bt.pairlists.refresh_pairlist(pairs=pairs)
    assert bt.pairlists.whitelist == pairs and bt.dataprovider.current_whitelist() == pairs
    bt.config['timerange'] = window['timerange']; bt.timerange = TimeRange.parse_timerange(window['timerange'])
    bt.available_pairs = []
    data, timerange = bt.load_bt_data()
    assert set(data) == set(pairs)
    bt.all_bt_content = {}
    dates = pd.date_range(window['start'], window['end'], freq='D', tz='UTC')
    common = dict(window=label, universe=window['universe'], pair_count=len(pairs),
                  start=window['start'], end=window['end'], days=len(dates))
    a.PAIRS = pairs
    a.HISTORY = {p: pd.read_feather(data_path / (p.replace('/', '_') + '-1d.feather')).set_index('date').sort_index() for p in pairs}
    current = []
    for name in names:
        old = references.get((window['reference_window'], name))
        if name == names[0] and old:
            assert old['start'] == window['start'] and old['end'] == window['end']
            assert (root / 'strategies/cycle_risk_strategy.py').read_bytes() == (prior / 'strategies/cycle_risk_strategy.py').read_bytes()
            assert abs(float(old['ledger_error'])) < .05
            row = {**common, 'strategy': name, **{k: old[k] for k in columns[7:]}}
            current.append(row)
            for filename in [name + '.json.gz', 'equity_' + name + '.csv', 'risk_trace_' + name + '.json']:
                source = prior / 'results' / window['reference_window'] / filename
                if source.exists(): shutil.copy2(source, folder / filename)
            print('Reused reconciled baseline', label, flush=True); continue
        stratconf = copy.deepcopy(bt.config); stratconf['strategy'] = name; stratconf.pop('strategy_list', None)
        strategy = StrategyResolver.load_strategy(stratconf)
        assert not hasattr(strategy, '_phase_initial_capital')
        bt.init_backtest()
        assert abs(bt.wallets.get_starting_balance() - 1000) < 1e-8
        minimum, maximum = bt.backtest_one_strategy(strategy, data, timerange)
        assert dates.equals(pd.date_range(minimum, maximum, freq='D')), (label, name, 'window changed')
        assert strategy._slots() == 2
        content = bt.all_bt_content[name]
        trades = content['results'].to_dict(orient='records')
        assert all(t['pair'] in pairs for t in trades)
        curve, cash, _ = a.ledger(trades, dates)
        error = cash - content['final_balance']; assert abs(error) < .05, (label, name, error)
        for trace in strategy.risk_trace:
            day = pd.Timestamp(trace['execution_date']) - pd.Timedelta(days=1)
            if day in curve.index:
                assert abs(trace['prior_closed_equity'] - float(curve.loc[day, 'equity'])) < .05
        normal_orders, quick_loss = [], 0
        for trade in trades:
            filled = [o for o in trade['orders'] if o['order_filled_timestamp'] is not None]
            if trade['exit_reason'] == 'force_exit': filled = filled[:-1]
            elif trade['profit_abs'] < 0 and trade['trade_duration'] <= 14400: quick_loss += 1
            normal_orders.extend((o, trade['fee_open'] if o['ft_is_entry'] else trade['fee_close']) for o in filled)
        stats = a.stats(curve)
        stats.update(normal_fills=len(normal_orders), quick_loss_positions=quick_loss,
            normal_fees=sum(float(o['amount']) * float(o['safe_price']) * float(fee) for o, fee in normal_orders),
            ledger_error=error, trades=len(trades))
        current.append({**common, 'strategy': name, **stats})
        curve.to_csv(folder / ('equity_' + name + '.csv'))
        (folder / ('risk_trace_' + name + '.json')).write_text(json.dumps(strategy.risk_trace, indent=2) + '\n')
        with gzip.open(folder / (name + '.json.gz'), 'wt') as f:
            json.dump(dict(strategy=name, window=label, start=window['start'], end=window['end'],
                final_balance=content['final_balance'], trades=trades), f, default=str)
        print(f"Finished {label} {name}: {stats['return_pct']:+.2f}% / DD {stats['wallet_drawdown_pct']:.2f}% / cash {stats['mean_idle_cash_pct']:.1f}%", flush=True)
        del bt.all_bt_content[name]
    rows += current
    temp = summary.with_suffix('.tmp')
    with temp.open('w') as f:
        writer = csv.DictWriter(f, fieldnames=columns); writer.writeheader(); writer.writerows(rows)
    temp.replace(summary)
    done.write_text(json.dumps(dict(window=window, strategies=names, initial_wallet=1000,
        max_ledger_error=max(abs(float(r['ledger_error'] or 0)) for r in current), fresh_strategy_instances=True), indent=2) + '\n')
    (root / 'concentrated_progress.json').write_text(json.dumps(dict(completed=sum((root / 'results' / w['label'] / 'concentrated_completed.json').exists() for w in windows),
        total=len(windows), last_window=label, elapsed_seconds=time.monotonic() - started), indent=2) + '\n')
    print(f'{i}/{len(windows)} {label} completed', flush=True)
print('Completed concentrated selection follow-up', flush=True)
sys.stdout.flush(); sys.stderr.flush(); os._exit(0)
