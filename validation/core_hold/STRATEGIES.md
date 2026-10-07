# Active strategy profiles

See [current retained comparison and optimization](trend_phased/REPORT.md).

- Ma200BtcRegimeFullCycleCoreHoldGrowthStrategy: Growth（保留对照）
- BtcTrendFullCycleDefensiveStrategy: 严格 MA150
- BtcTrendRecoveryCooldownStrategy: 14 天冷却全仓
- BtcTrendPhasedStrategy: 75% 分阶段版（历史正式版，现为对照）

BtcCoinGuardCycleRiskStrategy (corrected v2) is the current official selected profile (2026-10-07); original Portfolio is the frozen comparison baseline; old CoreHold remains a historical baseline; Recovery remains the earlier higher-return research alternative. Removed generated strategies are listed in trial_cleanup.json; raw source backups remain in result ZIPs.

- BtcTrendFastExitStrategy: 独立快速退出优化方案；原正式版配置保持不变。见 [回撤优化](drawdown_revision/REPORT.md) 与 [三策略起点检查](start_checks/REPORT.md)。

- Ma200BtcRegimeFullCyclePortfolioStrategy: 历史正式版，现为原始对照，原算法冻结。配置 `user_data/config_portfolio_btc_sol_eth.json`。
- BtcPortfolioImprovedStrategy: **失败、已归档**，从活动策略及配置移除。见 [改进对照](archive/portfolio_improvement/REPORT.md)。

- Portfolio 拆分研究：`BtcPortfolioRecoveryTopUpStrategy` / `BtcPortfolioPullbackTrimStrategy`，**失败、已归档**，仅在 `archive/portfolio_ablation/strategies/` 内；不提供活动配置。见 [拆分报告](archive/portfolio_ablation/REPORT.md)。

- BtcTrendCoinGuardStrategy: **BTC/SOL/ETH 进攻研究候选**，上涨达标，长区间与近期回撤高于 Portfolio，十币迁移性差；不替代正式版。见 [验证报告](portfolio_coin_guard/REPORT.md)。

- BtcPortfolioRegimeSwitchStrategy: **上涨模式切换研究候选**，BTC 连续两天站上 MA200 使用个币保护，其余使用原 Portfolio；长区间收益/回撤 557.45%/41.15%，约持有收益 63.68%。代码仅在 `portfolio_regime_switch/strategies/`；见 [验证报告](portfolio_regime_switch/REPORT.md)。

- BtcPortfolioNoBearSwitchStrategy: **现金防守研究候选**，仅关闭旧切换版熊市抄底；牛转熊/熊市/近期回撤明显改善，长区间收益不足。
- BtcPortfolioHalfRecoveryStrategy: **半仓恢复研究候选**，BTC/个币支持下半仓恢复，BTC 连续两天站上 MA200 满仓，支持失效转现金；上涨 461.85%/29.70%，长区间 479.09%/42.78%，收益仍不到持有约 2/3。
- BtcPortfolioThreeRegimeStrategy: **研究未通过**，恢复/震荡额外交易未产生稳定优势，不进入活动策略目录。

上述三类代码仅在研究目录；[最终现金防守报告](portfolio_three_regime/REPORT.md) 包含全部五阶段和未达标说明，正式版本未改。

- BtcCoinGuardCycleRiskStrategy（修正版 v2）: **当前正式版本，用户确认于 2026-10-07**。按用户接受折中的标准，相对原 Portfolio 五窗口收益胜出 4/5、回撤胜出 3/5，上涨和两类熊市显著改善；代价是长区间回撤略高、近期收益与回撤更差。长区间收益为持有的 56.83%，仍未完全达到约 2/3。正式策略选择已更新；运行服务未切换，源代码与结果保留原路径。实盘重启状态持久化尚未实现，正式选定不代表已具备上线条件。BtcCoinGuardEquityRiskStrategy 继续保留为归档对照。见 [报告](archive/portfolio_cycle_risk_v2/REPORT.md)。

## 代表性标的跨周期验证（2026-10-07）

正式版、原 Portfolio、分阶段、快速退出、全天个币保护与持有：12 币、6 窗口，64 有效单币案例、320 原生回测；新币上市前 8 组跳过。上涨、牛转熊、纯熊市横截面较原版改善，长周期收益中位数 280.66% 对 204.23%，回撤中位数 57.45% 对 50.04%；近期正式版收益中位数 -18.04%/回撤中位数 51.66%，原版 -9.15%/44.99%。LINK、AVAX、ADA 迁移弱，不扩大既定 BTC/SOL/ETH 正式范围。统计为单币分布，不能当作组合收益或独立样本。见 [完整对比](representative_assets/REPORT.md) 与 [交互查看](representative_assets/comparison.html)。
