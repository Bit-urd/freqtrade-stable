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

## Active strategy cleanup (2026-10-07)

- [x] Archive failed leverage, redundant single-coin weekly implementation and Growth/Recovery wrapper; retain source hashes, original config and dependency snapshot.
- [x] Put unchanged formal cycle-risk v2 implementation and required equity parent in active directory; retain original Portfolio, phased/fast variants, moderate CoreHold and own-coin trend as distinct directions.
- [x] Preserve running FastTest and existing Compose strategy compatibility. Growth config now references identical CoreHold defaults. No live restart or trading changes.

- [x] Translate active strategy English comments/docstrings to Chinese; retain identifiers and trade tags, archive pre-translation snapshots, verify unchanged non-docstring AST for all eight files and frozen formal dependencies.

## Retained profiles on BTC / ETH / SOL (2026-10-07)

- [x] Compare all six retained research profiles on three isolated coins over six windows: reuse 72 unchanged native results, add 36 native CoreHold/own-trend runs and 18 matching hold estimates.
- [x] Verify identical dates, unchanged executable strategy AST and identical daily/weekly data hashes for reused profiles; reconcile final balances (<3e-8 USDT). Record 126 comparison rows and standalone viewer.
- [x] Document SOL single-coin long-return shortfall, recent CoreHold strengths and own-trend bear cash defense; keep formal selection and running service unchanged.

## SOL upside diagnosis and fixed structural revision (2026-10-07)

- [x] Decompose bull return gap: 34.70% price rise before first entry creates 488.70 pp diagnostic gap; coin guard adds 194.18 pp and equity controller 287.45 pp versus successive controls. Original hold benchmark unchanged.
- [x] Test three fixed structural hypotheses, then replay formal and two final candidates on BTC/ETH/SOL six windows plus three-coin five-window portfolios: 81 native runs total and 21 passed rule checks; all fills and daily risk NAV reconcile, 46 formal/hold anchors match.
- [x] Retain trend recovery as SOL-single research candidate (bull 1029.45%/43.92%, long 736.56%/57.22%); do not replace formal three-coin profile. Combo improves long only slightly (512.01%/40.93%) and bull stays essentially flat. Single-coin ~2/3 hold target remains unmet.


## 趋势恢复版继续优化（2026-10-07）

- [x] 固定测试冷却补恢复与个币中期确认退出两项改动；完成三币各六段单币回测及五段共享账户，69 次原生回测，5 项新规则检查通过，46 条趋势恢复/持有历史基准复现。
- [x] 保留中期确认退出为 SOL 趋势参与研究候选：长周期 825.02%/53.44%，较趋势恢复版收益增加 88.46 个百分点、回撤减少 3.78 个百分点；BTC 不变，ETH 收益受损，近期略退步。
- [x] 记录三币组合折中：上涨 533.46%/30.12%，长期 519.05%/42.74%，近期 -20.91%/44.76%；不因个别指标退步否定研究价值，但趋势恢复版仍为优先通用方向。正式/运行策略未修改。
- [x] 冷却补恢复本轮无收益/回撤变化，标记不采用，保留源码与事件审计以复现。完整记录 validation/core_hold/trend_recovery_revision/REPORT.md。


## 选择性延迟个币退出（2026-10-07）

- [x] 固定比较 EMA50 上升确认与 BTC MA200 连续两天确认两项门控，69 次原生回测、6 项规则检查通过、46 条上一轮候选/持有基准复现，冻结来源与数据哈希一致。
- [x] 保留 BtcCoinGuardRisingMediumExitStrategy 为新的优先研究候选：三币长期 532.52%/40.93%，较趋势恢复版多赚 20.51 个百分点且回撤不变；近期 -18.40%/43.50% 略改善，其他三个主要阶段不变。
- [x] 记录 18 单币案例中 2 个同时改善、16 个不变；SOL 长期 778.76%/55.07%，保住部分收益提升并修复 ETH 损失。BTC 确认候选不列优先；完整取舍见 validation/core_hold/selective_coin_exit_revision/REPORT.md。
- [x] 正式与运行策略未切换；长周期收益约为持有 60.84%，仍未完全达到 2/3 目标。


## 2023 至最新完整日线连续账户（2026-10-07）

- [x] 隔离下载 2026-10-06 三币完整日线，过滤未收盘10月7日，冻结七策略；显式锁定数据路径，完成 2023-01-01～2026-10-06 七次原生连续账户比较与持有估值，共1375日。
- [x] 统计连续账户各年收益、年内回撤、新开仓/全平仓/加仓/部分减仓成交；不按年重置，剔除终点强平；年度复利与总收益核对、账本和每日风险权益核对通过。
- [x] CycleRisk +417.12%/49.71%，持有 +550.49%/68.57%；收益为持有75.77%。CoreHold +401.04%/34.56% 在本区间更均衡，但2022纯熊市承受能力仍弱，不因本窗口切换正式版本。
- [x] 记录趋势恢复本区间略逊正式版，最新 EMA50 候选 +430.06%/48.09% 小幅改善；保留全部真实结果，不将此前生产主线建议视为所有区间最优。详情 validation/core_hold/production_comparison_2023_latest/REPORT.md。
