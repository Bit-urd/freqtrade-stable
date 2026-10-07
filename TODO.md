## Current official selection (2026-10-07)

- **BtcCoinGuardCycleRiskStrategy, corrected v2**: explicitly selected by the user as the official BTC/SOL/ETH version. Frozen source hashes: [OFFICIAL.json](validation/core_hold/archive/portfolio_cycle_risk_v2/OFFICIAL.json).
- Original Portfolio remains the unchanged comparison baseline. Running service has not been switched. Live restart-state persistence remains required before deployment.
- Historical decisions below describe their status at the time; this selection supersedes earlier official-profile labels.

# TODO

## Portfolio strategy follow-up

- [x] Compare `Ma200BtcRegimeFullCyclePortfolioStrategy` and `Ma200BtcRegimeFullCycleCoreHoldStrategy` against an equal-weight buy-and-hold benchmark using the same pair list, start date, end date, starting capital, and fees.
- [x] Reconcile open-trade end-of-period valuation with realized-trade profit so the comparison uses total portfolio equity for both strategies.
- [x] Investigate bull-market entry lag and idle-cash periods; test earlier entries while keeping the BTC regime filter.
- [x] Sweep the retained bullish core fraction (for example 25%, 50%, and 75%) and BTC bear-exit confirmation length; compare return and wallet drawdown across multiple market regimes.
- [x] Check that the chosen settings remain useful out of sample before considering them for live trading.

## CoreHold implementation progress (2026-10-06)

- [x] Parameterize retained core fraction and bullish-core BTC bear-exit confirmation length.
- [x] Add an optional earlier bullish entry mode retaining the BTC regime filter.
- [x] Use closed candles for weekly sizing and mark core trimming only after order fill.
- [x] Verify callbacks with six offline regression checks; add an 18-combination sweep generator.
- [x] Download the 11-pair daily/weekly history and run 20 training variants, plus the original/default/selected variants over a historical stress window and a later held-out window. Reconstruct daily equity and reconcile all fills against engine final balances. The training-selected early/75%/1-day variant underperforms the default in both validation windows; do not promote it to live settings.

Details: [CoreHold implementation and validation](validation/core_hold/REPORT.md).

Trial outcome: the original Portfolio strategy has higher returns than both default CoreHold and the training-selected candidate in all three windows. Equal-weight holding leads in the training bull market but suffers much larger drawdowns in the stress and held-out windows. See the linked report and `validation/core_hold/summary.csv` for the common closing-price valuation.

Additional requested comparison: BTC/SOL/ETH only, 3 slots, 2022-11-21 through 2025-10-07. Original Portfolio +403.44%, default CoreHold +407.96%, equal-weight holding +875.33% on closing mark-to-market equity. [Three-pair comparison](validation/core_hold/btc_sol_eth_20221121_20251007/REPORT.md).

## BTC/SOL/ETH growth follow-up (2026-10-06)

- [x] Attribute the requested-period gap by coin and inspect initial stakes and bullish idle cash. SOL explains about 79% of the gap; initial bear exposure is only 40%.
- [x] Test 9 targeted improvements and evaluate the moderate Growth and higher-risk Recovery choices on an earlier stress period and a nonoverlapping later period.
- [x] Adopt the moderate Growth defaults in the requested CoreHold source: handover top-up enabled, weekly half-slot sizing disabled, original entries / 50% core / two-day BTC exit preserved. All three tested periods improve relative to the old default; preserve snapshots for baseline reproduction.
- [x] Add optional recovery and unified-handover logic, with fill-based state updates and exchange minimum / available cash checks. Provide explicit Growth and Recovery strategy classes and separate research configs.
- [x] Verify 11 regression checks and reconcile each backtest's complete fill ledger against engine final balance. Running bot configuration is unchanged.

Details: [Gap attribution and growth validation](validation/core_hold/improve_btc_sol_eth/REPORT.md). Growth raises the requested-period return from +407.96% to +423.59%; Recovery reaches +451.22% at higher drawdown. Neither matches equal-weight holding's +875.33% in that rising-market interval.

## Requested market-regime checks (2026-10-06)

- [x] Freeze BTC/SOL/ETH, 3 slots, 1000 USDT, 0.1% per-side fees and compare original Portfolio, old CoreHold, current Growth, experimental Recovery and equal-weight holding over four independently funded windows.
- [x] Evaluate 2025-09-01 to 2026-10-05; 2022-01-01 to 2022-11-21 (bear); 2021-07-01 to 2022-11-21 (bull to bear); 2023-01-01 to 2024-12-31 (overall rising cycle).
- [x] Check BTC market-regime statistics and reconcile all 16 strategy fill ledgers; export 20 portfolio equity curves and full drawdown comparisons.

Results: [Market-regime report](validation/core_hold/regime_comparison/REPORT.md). Growth improves three windows and equals the old default in the pure bear window. All strategies lose 51.43% in the pure bear window; bull-to-bear Growth equity drawdown is 63.53% despite terminal loss of only 1.84%. Recovery does not outperform Growth in these checks.


## Retained-candidate cleanup and phased optimization (2026-10-06)

- [x] Remove 60 discarded or duplicate generated trial classes from active strategy files; retain original baselines, Growth / Recovery, strict MA150, cooldown and phased research profiles. Keep raw result ZIPs and CSV measurements as evidence.
- [x] Test momentum allocation, peak protection, reentry cooldown and staged exposure. Freeze the selected 75% / MA150 / EMA10 / 14-day phased rule before replaying five common-equity windows.
- [x] Reach the revised ≤250 percentage-point bull-market gap in 2023–2024: phased +604.65%, holding +813.60%, gap 208.95 points, closing-equity drawdown 30.34%.
- [x] Reconcile all selected fills, verify public / frozen research equity equality in five windows, and pass 34 checks including partial-profit accounting, exchange limits and fill-only exposure states.
- [x] Preserve Growth default and the running trading service because the new candidate fails the defined cross-regime risk ceilings and regresses in the recent window.
- [ ] Achieve the bull-return gap together with consistently lower cross-regime risk; the longer 2022-11-21–2025-10-07 gap remains 342.35 points, and the phased drawdown is 54.17%.

Details: [Retained strategies and final phased comparison](validation/core_hold/trend_phased/REPORT.md). Active catalog: [STRATEGIES](validation/core_hold/STRATEGIES.md). Deleted trial inventory: `validation/core_hold/trial_cleanup.json`.

## Official phased strategy (2026-10-06)

- [x] Following the user’s explicit decision after the hold/drawdown comparison, promote BtcTrendPhasedStrategy as the official BTC/SOL/ETH profile, superseding the earlier research-only status.
- [x] Preserve the measured 75% / MA150 / EMA10 / 14-day rules and historical risk results; retain Growth for comparison.
- [x] Provide an official dry-run configuration without changing the running trading service.

## Drawdown revision with hold-relative return target (2026-10-06)

- [x] Replace the fixed 250-point shortfall objective with approximately two-thirds of positive buy-and-hold returns and drawdown below hold.
- [x] Compare 12 targeted revisions across five regimes; preserve all measured results and reconcile every fill.
- [x] Retain BtcTrendFastExitStrategy (full early exposure, one-day weak-trend exit, inherited 14-day cooldown) as the closest tested revision: 63.01% of long-window hold return, 78.60% of bull-window hold return; lower drawdown than hold in all five windows.
- [x] Keep official phased v1 and its configuration unchanged for comparison because recent-window return and drawdown regress in the new revision.
- [ ] Strictly achieve at least two-thirds hold return in both positive-hold windows: not achieved in the long window.

## Three-profile start-date checks (2026-10-06)

- [x] Freeze Phased v1, FastExit and original Portfolio on BTC/SOL/ETH with identical capital, fees and valuation.
- [x] Run 60 monthly-start fixed-year windows, 12 quarterly-start common-end windows and five reference windows (231 engine backtests plus 77 hold baselines).
- [x] Reconcile fills, confirm matching dates, verify source checksums and previous reference measurements, publish paired CSVs and standalone plots.
- [x] Preserve all three profiles: FastExit has a higher fixed-year target hit rate, while Portfolio has materially lower common-end drawdown at similar median return to v1. No live service or official config switch.

## Ten single-coin groups (2026-10-07)

- [x] Test BTC/ETH/BNB/SOL/XRP/ADA/DOGE/LINK/AVAX/AAVE independently with one slot and 1000 USDT per run on 20221121-20251007.
- [x] Download missing DOGE/LINK/AVAX daily and weekly history; audit common dates, warmup and single-coin-only fills.
- [x] Compare Phased, FastExit, Portfolio and each coin's buy-and-hold; reconcile all 30 engine runs. Strict joint target passes 1/10, 2/10 and 5/10 respectively.
- [x] Publish per-coin table, standalone figure, summary CSV, frozen sources and separate one-coin replay configs; keep official configuration and live service unchanged.

## Portfolio official baseline and independent improvement (2026-10-07)

- [x] User selected original Portfolio as current official version; retain its algorithm and supply a separate BTC/SOL/ETH dry-run config.
- [x] Create independent BtcPortfolioImprovedStrategy: strong recovery top-up, daily weakness half exposure within a strong weekly trend, full exit on BTC breakdown or combined coin daily/weekly weakness.
- [x] Complete identical ten-coin comparison against Portfolio, Phased, FastExit and holding; reconcile all ten candidate runs and pass six rule checks. Candidate regresses (median return 152.45%, median drawdown 55.50%, joint target 3/10); retain as research only, Portfolio remains official.

## Portfolio mechanism split (2026-10-07)

- [x] Freeze independent recovery-top-up and pullback-trim experiments; preserve official Portfolio rules and live service.
- [x] Run both variants across ten individual coins; pass six mechanism/fill-state checks, reconcile all twenty runs.
- [x] Stop further tests at user request after three of five BTC/SOL/ETH windows; archive both split variants and the combined candidate, preserve completed results and document the two uncompleted windows.

## Stop trials and archive failed candidates (2026-10-07)

- [x] Stop only the research container; retain the existing trading service.
- [x] Archive three failed Portfolio improvement candidates, their configurations, replay scripts, rule checks, raw fills, equity curves and conclusions under validation/core_hold/archive/.
- [x] Remove the failed combined candidate from user_data/strategies and active configs; retain official Portfolio and useful existing comparisons.

## Reopened bull-participation optimization (2026-10-07)

- [x] Following renewed user authorization, diagnose low 2023–2024 exposure: original first allocations total about 200 USDT, mean cash 44.22%.
- [x] Run one built-in immediate-handover toggle across five regimes; small return gain with worse bull drawdown, research record only.
- [x] Replay retained Growth on bull and long windows; both match prior results and improve Portfolio return/drawdown.
- [x] Freeze one dual BTC/coin MA150/EMA10 candidate, run five regimes and ten single coins, then replay public code on all five regimes; pass five causal/gate/missing-signal checks.
- [x] Bull candidate meets 2/3 hold-return target at lower drawdown (559.13%/30.00%). Keep candidate research-only: long target fails, recent risk regresses, cross-coin target passes only 3/10. Official Portfolio and running service remain unchanged.

## Bull-only guarded trend / Portfolio switch (2026-10-07)

- [x] Implement user-requested causal mode switch: BTC two closed days above MA200 uses guarded trend, otherwise original Portfolio; one wallet and explicit position handover.
- [x] Freeze one rule and replay five BTC/SOL/ETH windows; seven policy/fill checks pass and all fills reconcile.
- [x] Retain as research candidate: long 557.45%/41.15% (~63.68% of hold return), bull 433.06%/29.69%; better long results than all-time coin guard, but pure bear reverts to original losses and bull-to-bear/recent drawdown still exceeds original. No official/live switch.

## Cash defense / three-regime optimization (2026-10-07)

- [x] Test one-change no-bear control and fixed three-mode recovery/range rule across five BTC/SOL/ETH windows; seven policy checks pass.
- [x] Add fixed 50% recovery / 100% confirmed-bull cash-exit candidate; correct trade-direction constraints and independently replay all five windows; six fill/cost/direction checks pass.
- [x] Reconcile 15 final runs against native balances and frozen hold references; archive intermediate source/results, exclude them from final comparison.
- [x] Retain no-bear switch as defense research and half recovery as compromise research. Three-regime extra range trading is not adopted; official Portfolio/service unchanged.
- [ ] Achieve hold-relative ~2/3 return while improving all regimes: final candidates do not achieve this; bull/long returns are still insufficient and long drawdown slightly regresses against old switch.

## Account drawdown controller and risk rearm (2026-10-07)

- [x] Continue with fixed 25%/35% drawdown tiers, 20%/30% hysteresis and BTC MA200-confirmed risk rearm with 14-day reset spacing; include holding in all windows.
- [x] Correct bot_loop_start stale analyzed-cache prices and simulated open entry-fee accounting. Preserve intermediate results, independently rerun both candidates in fresh v2 folders.
- [x] Complete 10 final backtests, 13 passed checks, matching hold references and every-day prior closed equity reconciliation (max error 3.2e-8 USDT).
- [x] Record failure to meet full-cycle return target; archive both trial versions and corrected candidates, keep formal Portfolio and live service unchanged. Cycle-rearm bull 527.79%/30.31%, long 497.43%/40.83%, recent -18.65%/43.68%.

## Tradeoff criterion clarified (2026-10-07)

- [x] Replace all-window dominance with substantial overall improvement versus original Portfolio; explicitly disclose sacrificed periods.
- [x] Retain corrected BtcCoinGuardCycleRiskStrategy as an improvement research candidate: returns improve in 4/5 measured windows, drawdown improves in 3/5. Strong bull and bear benefits compensate for modest long-window drawdown increase; recent weakness remains material. Results/source stay at the existing archive path for reproducibility; candidate is not classified as failed. Official/live strategy unchanged.
- [ ] Long-window return near 2/3 of holding remains unmet (56.83%); no claim of independent out-of-sample validation.

## Representative assets and regimes (2026-10-07)

- [x] Freeze five major profiles and compare BTC/ETH/BNB/SOL/XRP/ADA/DOGE/LINK/AVAX/AAVE/SUI/PEPE with holding over six regimes; complete 64 eligible single-coin cases (320 native runs), explicitly skip eight unavailable listing/history cases.
- [x] Update missing AVAX candles; use 2026-10-05 common recent endpoint; reconcile final balances and every-day controller equity (<3e-8 USDT); reproduce 50 historical anchor rows.
- [x] Record per-window/per-asset results, tradeoffs, source/data hashes and standalone comparison viewer. No parameter tuning, official scope expansion or live service changes.
