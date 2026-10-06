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
