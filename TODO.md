## Current official selection (2026-10-07)

- **BtcCoinGuardCycleRiskStrategy, corrected v2**: explicitly selected by the user as the official BTC/SOL/ETH version. Frozen source hashes: [OFFICIAL.json](validation/core_hold/archive/portfolio_cycle_risk_v2/OFFICIAL.json).
- Original Portfolio remains the unchanged comparison baseline. Running service has not been switched. Live restart-state persistence remains required before deployment.
- Historical decisions below describe their status at the time; this selection supersedes earlier official-profile labels.

# TODO

## 指定新币池与正式升级依据（2026-10-08）

- [x] 用户确认沿用现货口径：BTC、ETH、BNB、LINK、XRP、UNI、ZEC、DOGE、SOL、ARB、PUMP、HYPE。正式源文件冻结，两版只差 BTC 退出确认，持有全程同步比较。
- [x] 冻结 Binance 现货完整日线至 2026-10-06。P1–P8 的 96 个单币组合中 74 可测、22 不可用、3 为部分区间。PUMP 从 2025-09-11、HYPE 从 2026-09-24 才有该所现货；HYPE 仅 13 根，无法验证策略。
- [x] 完成 105 个窗口、210 次原生回测与 105 条持有曲线：74 单币阶段、16 阶段组合（历史可交易池与固定十二槽位现金预留）、15 连续组合/PUMP控制窗口。
- [x] 综合连续组合收益、回撤、极端损失和关键行情参与；将加入 PUMP 的十一币池与同日期十币控制池比较，另显示 HYPE 预算留现金的十二槽位账户。不能把现金预留改善误认为 HYPE 策略表现。
- [x] 核对规则、实际退出/冷却、每日风险权益和成交现金，生成完整三组收益/回撤报告及图表，更新正式升级建议；本轮不修改正式策略或运行服务。

结果：九币最长原版1473.31%/61.77%，两天版2162.18%/61.04%，持有291.73%/86.83%；十币连续原版177.63%/48.26%，两天版210.52%/44.13%，持有673.78%/56.75%；同日期十一币原版44.75%/13.15%，两天版53.62%/12.54%，持有94.34%/32.63%。支持成熟十/十一币组合采用两天确认；PUMP单币退步，HYPE仅13根现货日线尚无法验证。十币持有领先主要来自ZEC，不把相对原版改善当作普遍胜过持有。45项规则检查、315条权益重建、4227次实际BTC退出、3925次弱BTC入场冷却和51488日风险权益核验通过；正式源文件与运行服务未修改。[完整报告](validation/core_hold/requested_twelve_pool_20261008/REPORT.md)、[组合CSV](validation/core_hold/requested_twelve_pool_20261008/all_comparisons.csv)。

## 用户指定 P1–P8 × 12 标的验证（2026-10-08）

- [x] 固定用户提供的八阶段和 BTC、ETH、SOL、XRP、DOGE、LINK、AVAX、DOT、UNI、AAVE、ARB、APT；只比较冻结原版、BTC 两天退出单项和持有，取消 5pp 回撤硬门槛。
- [x] 补齐 DOT、ARB、APT Binance 日线，冻结十二币数据与源文件。96 个请求组合中 83 个可运行、6 个部分区间、13 个不可用；7 个起点 MA150 尚未形成案例单列。三组使用同一有效区间。
- [x] 完成 166 次新原生回测与 83 条持有基准，逐标的逐阶段同时报告收益、真实账户回撤、现金、成交与费用。
- [x] 重建全部权益与成交现金，检查实际 BTC 退出、指标截断历史不变性及数据/正式策略哈希；写完整矩阵、图表及综合结论，不切换正式版。

结果：83 个可测案例，两天版相对原版收益提高 16、下降 37、相同 30；76 个完整且 MA150 就绪案例为 15/36/25。P7 ARB 收益提高 15.96pp、回撤下降 9.23pp；AAVE 实际避免 2024-08-19 的一天 BTC 弱势退出，参与后续上涨。P4 十币均有代价，不能单凭此阶段或胜率淘汰；按用户最新要求一并保留此前三币连续账户明显改善的证据，综合关键改善与最差阶段损失。36 项规则检查、249 条权益重建、463 次实际 BTC 退出、466 次弱 BTC 入场冷却和 32698 日风险权益核验通过。两天版仍保留研究价值，正式策略未切换。[完整八阶段十二币收益/回撤报告](validation/core_hold/p1_p8_twelve_assets_20261008/REPORT.md)、[96组合CSV](validation/core_hold/p1_p8_twelve_assets_20261008/comparison_matrix.csv)。

此前广义历史单币验证已完成 55 个旧窗口，因用户明确指定新阶段/新币池，保留原始结果并以本轮固定矩阵为交付范围。[覆盖清单](validation/core_hold/p1_p8_twelve_assets_20261008/coverage.csv)。

## CycleRisk 与持有差距：依次实验验证（2026-10-08）

当前保留 `cycle_risk_strategy.py` 的原 CycleRisk；集中前二版不替换正式版。以下按 1 → 4 顺序推进，每轮独立对比冻结原版和等额买入持有，不自动叠加上一轮改动。通过单项验证后才另测组合；所有候选先放研究目录。

- [x] **1. BTC 退出确认**：仅将 BTC 弱势退出从连续 1 天改成 2 天，入场、个币退出、冷却、预算和账户风控不变。统计退出后短期重新走强、重新买入的事件及其费用与机会损失；验证是否提高上涨阶段收益，同时检查 2022 熊市损失和牛转熊最大回撤是否扩大。
  - 结果：19 个窗口，收益改善 12 个、回撤降低 9 个、同时改善 8 个。三币全周期 18736.96%/63.67%，原版 10639.45%/66.62%；三币 2023 至今 599.39%/40.51%，原版 417.12%/49.71%。2022 熊市和两个 2023—2024 上涨窗口退步。保留为研究候选，未替换正式版；按用户要求取消 5pp 硬门槛。[报告](validation/core_hold/btc_exit_confirmation_20261008/REPORT.md)。
- [x] **2. 减仓后的仓位恢复**：先归因账户 75%/50% 风险档位在行情恢复后的停留时长、资金暴露和收益影响，核对已有恢复/峰值重启实验，避免重复。若证据支持，再固定一个分阶段恢复候选，仅修改账户仓位恢复逻辑；检查趋势恢复参与率、再次下跌风险及调仓费用，不取消原回撤控制。
  - 结果：先归因，再固定恢复阈值 20%/30% → 22.5%/32.5%，降仓线不变。19 窗口收益提高 6、下降 3、相同 10；同时改善 2。三币 2023 至今 417.32%/49.73%，原版 417.12%/49.71%，实际提升有限；八币 2024 和最近窗口退步。暂不列优先候选。[报告](validation/core_hold/recovery_speed_20261008/REPORT.md)。
- [x] **3. 弱 BTC 下的 14 天冷却**：先统计冷却期内原本满足入场条件的机会。事先固定较短冷却或趋势重新确认后提前解除的候选，分别与原版比较，不边看结果边搜索天数；检查新增收益能否覆盖新增小亏、交易费用及熊市回撤。
  - 结果：固定 14 → 7 天，19 窗口收益提高 13、下降 6，回撤降低 14，同时改善 12。三币 2023 至今 453.66%/48.99%，2026 年 30.41%/16.33%；三币全周期 8254.46%/66.05%，原版 10639.45%/66.62%，2022 亏损由 31.55% 扩至 44.50%。近期有价值，不能概括为所有周期更优；2011 次弱 BTC 实际入场冷却核验通过。[报告](validation/core_hold/short_cooldown_20261008/REPORT.md)。
- [x] **4. 有限共享闲置资金**：保留各币入场机会、原币池和原持仓槽位；先量化预算限制导致的闲置资金，再测试带明确单币上限的有限共享预算。避免硬性只允许涨幅前二或最多两仓；核对赢家利润复利、单币集中度、钱包余额限制和账户风控的相互影响。

  - 结果：仅新入场共享资金，保护其他未持仓币当前预算，新增投入最多原投入的 50%。19 窗口收益提高 5、下降 14，同时改善 5。两个 2023—2024 上涨组合改善，三币/七币全周期及部分近期窗口明显退步；2590 次实际初次成交预算核验通过，暂不列通用优先方案。[报告](validation/core_hold/limited_shared_cash_20261008/REPORT.md)。

- [x] **5. 组合验证**：固定 BTC 两天退出 + 弱 BTC 七天冷却，与原版、两个单项和持有对比相同 19 个窗口；不叠加提前恢复或共享资金，不搜索参数。检查改善是否能叠加及熊市代价。[研究目录](validation/core_hold/exit_cooldown_combo_20261008/plan.json)。

  - 结果：19 次新回测；组合相对原版收益改善 13、下降 6，相对两天退出单项改善 10、下降 9，同时改善 5；相对七天冷却单项改善 6、下降 13。三币全周期 9283.84%/70.84%，两天退出单项 18736.96%/63.67%；近期 10.61%/29.68% 优于单项，但主要长周期没有叠加优势。36 项规则检查、实际退出/冷却及 95 条持仓权益重建通过。组合仅保留记录，优先研究两天退出单项，不切换正式版。[报告](validation/core_hold/exit_cooldown_combo_20261008/REPORT.md)。

统一验证要求：

- [x] 每轮开始前冻结假设、候选参数、数据、策略来源和验收标准；先查历史报告，注明新实验与既有实验的差异。
- [x] 使用相同币池、起止日期、初始资金、手续费及日终盯市口径；覆盖 2022 熊市、2023—2024 上涨、2025、2026、最近窗口及连续全周期账户。分年独立开户与连续账户年度结果分别报告。
- [x] 同时记录累计收益、最大回撤、期末权益相对持有、现金比例、实际持仓集中度、交易/调仓次数和费用；对差异作事件及标的归因，不能把现金比例下降直接当作改善。
- [x] 按用户最新要求综合考虑最终收益、最大回撤、熊市损失、各周期表现与复杂度，不设置“回撤最多扩大 5 个百分点”等固定淘汰门槛；报告所有退步窗口，不因单一币种或窗口大赚就升级。
- [x] 检查完成日线因果性、实际成交后状态更新、每日风险权益和完整现金账；验证来源/数据一致，重建 114 条逐币持仓曲线，归因文件记录实际集中度。
- [ ] 独立验证：已有反复查看的窗口视为回溯研究，重叠窗口不计独立证据；另安排未参与调参的历史区间或后续前向验证，并披露事后选择币池偏差。
- [x] 每轮写报告并更新本 TODO 的结果及下一步；生产策略、配置和运行服务的切换另行决定。

四项顺序验证全部完成，89 项规则检查、成交及每日权益核对通过；BTC 两天退出与七天冷却保留研究候选，随后已完成第 5 项组合验证；未升级正式版。[综合报告](validation/core_hold/cycle_risk_sequential_validation_20261008/REPORT.md)。

参考：[本轮原版/持有/选币对照](validation/core_hold/momentum_selection_20261008/REPORT.md)。重点问题：三币 2023—2024 原版收益 527.79%、持有 813.60%；七币 2023 至 2026-10-06 原版收益 219.42%、持有 751.44%，最大回撤均约 58%。差距原因仍需逐项归因，不能仅凭汇总认定某规则无效。

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


## CycleRisk 防守优化：保留收益（2026-10-07）

- [x] 已提交并推送前序整理和实验报告：165c40406，origin/stable-dryrun；排除用户运行配置、交易数据库、行情和原始回测结果。
- [x] 固定测试四项结构假设：BTC确认入场、个币强势修复例外、亏损后弱BTC冷却、恢复时保留一半峰值差额；最终42次原生回测，另保留布尔缺失信号修复前18次，修复后完整重跑结果一致。
- [x] 三组20/21/20项新规则与原风控检查通过；各复现10条正式/持有基准，逐日权益和成交现金核对，数据/源码哈希一致。前三项收益代价过大，标记不采用。
- [x] 原先保留BtcCoinGuardHalfPeakRearmStrategy；用户认为回撤改善不足，现标记不采用，仅保留实验记录，不替换正式版：2023至今433.22%/47.78%，较正式版多赚16.10个百分点、回撤低1.93个百分点；长周期只少赚0.94个百分点、回撤低0.59个百分点；近期改善，上涨/牛转熊/纯熊市不变。
- [x] 记录2025年度收益略退步、接近48%回撤仍较大及重启持久化缺口；完整结论validation/core_hold/cycle_risk_half_peak_revision/CONCLUSIONS.md。

## CycleRisk 按回撤阶段与标的归因（2026-10-07）

- [x] 逐笔重建三币权益、持仓、日损益和费用；确认最大回撤2025-01-18～2026-08-11为49.71%，SOL占峰谷损失86.70%、峰值时持仓65.31%；拆分老仓回吐1379.95和后续入场损失2019.92，核对误差低于0.000001 USDT。
- [x] 固定验证EMA20两天确认入场/对称退出及统一50%新增/持仓约束，共36次原生回测，六窗口均对比持有，两组各21项规则检查通过。收益代价过大或完整周期回撤改善不足，均不替换正式版。
- [x] 验证50%持仓约束减少老仓回吐但改变账户降仓路径，后续反弹入场损失仍大；连续账户396.35%/48.18%不构成足够改进。记录全部失败和下一步假设，详见validation/core_hold/cycle_risk_weight_cap_revision/CONCLUSIONS.md。

## 个币亏损预算与趋势恢复（2026-10-07）

- [x] 固定测试上一笔亏损75%、连续两笔亏损50%的个币预算，与账户风险档位取较小值；比较盈利平仓恢复、动态中期趋势恢复、该笔趋势确认后保持恢复三种结构。六窗口对比持有，共30次原生回测；两组27/36项规则检查和逐日账本核对通过。
- [x] 发现动态恢复长周期加仓95次、部分减仓93次；恢复保持版降至24/8次，原版9/11次。减少调仓有局部收益改善，但不保证所有窗口更优。
- [x] 恢复保持版连续368.56%/45.71%，收益约持有66.95%；指定长周期374.08%/37.56%和上涨440.61%/30.01%仍付出明显收益代价，三版均不升级正式版，只保留记录，不继续调参数。详见validation/core_hold/cycle_risk_latched_budget_revision/CONCLUSIONS.md。

## 活动策略目录再次清理（2026-10-07）

- [x] 核对八个活动策略文件的继承关系、活动JSON配置和Compose引用；删除无配置、运行或子类引用的严格MA150历史类BtcTrendFullCycleDefensiveStrategy及过期字节码缓存。
- [x] 保留正式版依赖链、原Portfolio、CoreHold、分阶段/快速退出、独立趋势及运行/Compose兼容策略；最新失败实验仍仅在研究目录，历史冻结代码与报告未删除。
- [x] 删除前后其余核心类可执行AST一致；离线加载与既有回归检查记录于validation/core_hold/strategy_cleanup_20261007_second/verification.json。

## 正式版调用链缩短及研究入口归档（2026-10-07）

- [x] 冻结迁移前八个活动文件与哈希；将CoreHold/Phased/FastExit/CoinGuard/EquityRisk/独立趋势及四个研究配置移至user_data/archive/cycle_risk_flatten_20261007，配置更新归档策略路径。
- [x] CycleRisk从四个文件、八个自定义类的继承链改为单文件直接继承IStrategy；保留真实生效的进退出、冷却、独立复利预算、成交档位、账户风控及BTC风险重启，删除未用于决策的周线/熊市/核心仓指标。
- [x] 六次原生回测与迁移前对比逐日权益、完整交易订单和风险轨迹；14项因果性、缺失行情、冷却边界、资金调整及风险重启规则检查通过。运行Portfolio/FastTest及Compose兼容策略保留，未部署或重启服务。
