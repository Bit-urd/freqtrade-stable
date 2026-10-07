# CoreHold research

Backtests use the separate `config.json` here: spot, 1,000 USDT, 11 slots,
100% available balance, market orders at candle opens, 0.1% fees each way.
They do not start or change the trading service.

Download the configured 11 pairs:

```bash
docker run --rm \
  -v "$PWD/user_data:/freqtrade/user_data" \
  freqtradeorg/freqtrade:stable download-data \
  -c user_data/config.json --timerange 20170101-20261006 -t 1d 1w
```

Generate static subclasses with `prepare_sweep.py strategies/sweep.py`.
The `strategies/` directory includes the tested strategy snapshots.

Run each Python research command in this image, with these mounts:

```bash
docker run --rm --user root \
  -e PYTHONPATH=/freqtrade:/home/ftuser/.local/lib/python3.14/site-packages \
  --entrypoint python \
  -v "$PWD/user_data:/freqtrade/user_data" \
  -v "$PWD/validation/core_hold:/research" \
  freqtradeorg/freqtrade:stable /research/run_backtests.py --windows train
```

Then run `/research/analyze.py --windows train` to freeze selection using
training results. Run `/research/run_backtests.py --windows bear test`, then
`/research/analyze.py` to produce the complete comparison. Use the same image
wrapper for `/research/audit_data.py` and `/research/check_equity.py`.

Selection uses training return, plus an alternative score of
`return_pct - 2 * wallet_drawdown_pct`. Validation windows evaluate only these
choices and the original/default strategies. Training ends 2025-01-01; the
held-out backtest starts 2025-01-02 to prevent date overlap. The earlier
2021–2022 window is a historical stress check, not pristine unseen data:
strategy development has already considered this period.

`summary.csv` uses daily closing mark-to-market equity; terminal `force_exit`
orders are removed from those curves. `engine_final_balance` includes forced
liquidation at the engine's terminal execution price. A separate fill ledger
must reconcile that balance within 0.05 USDT before publishing any results.
All remaining token balances are included, and realized profits are not added
again. `liquidated_return_pct` charges 0.1% to remaining holdings at their
terminal closing prices, so both strategies and benchmark use the same
valuation convention.

The benchmark allocates 1/11 of initial cash per coin, buys at the first open
on/after the window start once 61 completed daily candles exist, and reserves
cash until then. It never rebalances. Strategy callbacks also require more
than 60 own candles. This is a benchmark for the current fixed whitelist;
it does not eliminate survivorship bias in choosing that list.

`median_bull_entry_lag_days` measures each bullish buy/top-up against the
most recent BTC MA200 bullish episode's first executable day. It is a
portfolio diagnostic, not a matched entry-event causal estimate.

Generate the final report with `/research/make_report.py`. This requires
Matplotlib, which is not included in the stable trading image. For this run
it was installed only into `/tmp/plotdeps` in a disposable container;
that directory was prepended to `PYTHONPATH` for report rendering. The trading
container and its Python dependencies were not changed.

The growth follow-up is documented in `improve_btc_sol_eth/REPORT.md`.
Run `/research/diagnose_gap.py`, `/research/run_improvements.py`, and
`/research/run_growth_validation.py` with the same image wrapper. Then run
`/research/analyze_improvements.py --labels requested recovery stress later`
and `/research/make_growth_report.py`. The research strategy directory keeps
the old default parameters for baseline replay. The current user_data core
strategy uses the moderate Growth defaults. Public Growth/Recovery profile
classes have the same tested fields; independent 3-pair configs are provided
in the growth report directory.


## Active candidates after requested cleanup

On 2026-10-06, 60 discarded or duplicate generated trial classes were removed
from active strategy code. Their measurements and exported Python source remain
in the original result ZIPs. Earlier sweep commands above describe historical
runs and require restoring their source from those archives.

Keep the original Portfolio / old CoreHold as comparison baselines, Growth as
legacy comparison, Recovery as the earlier higher-return long-window research
profile, and the two public trend candidates in the core strategy source.
The fast EMA10 recovery candidate has a bull-market advantage but poor bear risk;
the strict MA150 candidate has substantially better bear and transition risk.
Momentum allocations failed the bull-return goal and were removed. Current optimization combines the retained trend rules with a 14-day reentry cooldown below MA150.
See `trial_cleanup.json`, `trend_exposure/REPORT.md`, and `trend_momentum/`.

Replay retained profiles with `/research/run_trend_exposure.py --phase validation`.
Replay the frozen cooldown candidate with `/research/run_trend_cooldown.py`; see `trend_cooldown/REPORT.md` for final comparisons.


The official BTC/SOL/ETH implementation (approved by the user on 2026-10-06) is `BtcTrendPhasedStrategy`: 75%
exposure on early recovery below BTC MA150, full exposure above, and a 14-day
reentry cooldown below the long trend. It meets the 250 percentage-point gap
goal in 2023–2024 but fails cross-regime risk ceilings. The user selected it as
the official version after reviewing the hold comparison; Growth remains a legacy profile. See `trend_phased/REPORT.md` and `STRATEGIES.md` for retained choices.
Replay it with `/research/run_trend_phased.py`; rebuild the final retained
comparison with `/research/make_retained_report.py`.

Official configuration: `user_data/config_trend_btc_sol_eth.json` selects
`BtcTrendPhasedStrategy` with BTC/SOL/ETH and dry-run enabled. This promotion
does not start or switch the running trading service.

Git retains strategy sources, configurations, validation scripts, decisions and
CSV summaries. Raw result ZIPs, logs, equity artifacts under `results/`, plots
and downloaded market data remain local artifacts; replay commands regenerate them.

Drawdown revision: see `drawdown_revision/REPORT.md`. Public
`BtcTrendFastExitStrategy` inherits official phased v1 and changes only early
exposure to 100% and weak-trend exit confirmation to one day. Its separate
`user_data/config_trend_fast_exit_btc_sol_eth.json` stays in dry-run mode; the
original official configuration and running service remain unchanged.
Replay the selected public profile with `/research/run_drawdown_selected.py`.
The measured trial alias has an identical class AST after renaming/removing its
docstring; source and return-ratio checks are in `drawdown_revision/selection.json`.

Start-date checks: `/research/run_start_checks.py` compares official phased v1,
fast exit, original Portfolio and equal-weight holding across 60 monthly
12-month windows, 12 quarterly starts with a shared end, and five reference
windows. Sources are frozen under `start_checks/strategies`;
`/research/make_start_report.py` writes paired comparisons and aggregate counts.
Render standalone plots with `plot_start_checks.py` using Matplotlib installed
into an isolated temporary target, rather than the trading service environment.

Ten one-coin groups: `/research/run_single_coin_comparison.py` freezes the three
profiles and compares BTC/ETH/BNB/SOL/XRP/ADA/DOGE/LINK/AVAX/AAVE individually on
20221121-20251007. Each uses 1000 USDT, max_open_trades=1 and one pair; BTC remains
an informative signal for other assets. Results are in `single_coin_comparison/REPORT.md`.
Per-group configs are under `single_coin_comparison/configs`; summary and plots
are generated by `make_single_coin_report.py` and `plot_single_coin_comparison.py`.

## Current official profile (2026-10-07)

Original Portfolio is now official by user instruction; Phased and FastExit are comparison profiles. Failed BtcPortfolioImprovedStrategy and its split experiments are archived; records: [report](archive/portfolio_improvement/REPORT.md). Existing services are unchanged.
