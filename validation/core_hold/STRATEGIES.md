## 当前目录筛选（2026-10-07）

当前清单以 [策略目录说明](../../user_data/strategies/README.md) 为准：新正式版、原 Portfolio、分阶段/快速退出、温和 CoreHold、个币独立趋势。旧 Growth/Recovery 包装和旧单币周线版停止单独维护，失败杠杆版归档。依赖及运行/配置兼容类单列，不视为独立探索方向；下文为历史研究状态。

# 历史策略研究清单

See [current retained comparison and optimization](trend_phased/REPORT.md).

- Ma200BtcRegimeFullCycleCoreHoldGrowthStrategy: Growth（保留对照）
- BtcTrendFullCycleDefensiveStrategy: 严格 MA150（已从活动文件删除，仅保留历史冻结记录）
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

## 保留方向三币独立账户复核

六版本分别测试 BTC、ETH、SOL 的六个窗口；新正式版 BTC/ETH 折中较好，但 SOL 长周期收益仅持有的约 32%，近期温和 CoreHold 与个币独立趋势有不同优势。完整表格见 [三币逐版本报告](retained_btc_eth_sol/REPORT.md)，交互查看见 [对比页面](retained_btc_eth_sol/comparison.html)。组合与单币账户结果不混用。

## SOL 上涨方向的固定结构优化

`BtcCoinGuardTrendRecoveryRiskStrategy` 保留为 SOL 单币研究候选，源码仅在 `sol_upside_revision_v2/strategies/`，不新增活动策略方向。上涨收益/回撤 1029.45%/43.92%，长周期 736.56%/57.22%，仍不足持有约 2/3；三币组合改善很小，当前正式版不替换。强趋势优先对照未采用。见 [诊断与完整回测](sol_upside_revision_v2/REPORT.md)。


## 2026-10-07 趋势恢复版第二轮研究

中期确认个币退出 `BtcCoinGuardConfirmedCoinExitStrategy` 保留为 SOL 趋势参与候选，源代码冻结于 `trend_recovery_revision/strategies/recovery_refinement_strategy.py`。SOL 长周期 825.02%/53.44%，上涨期 1047.40%/43.45%；ETH 部分窗口退步，三币长周期 519.05%/42.74%、近期 -20.91%/44.76%。这是局部收益/风险改进，不是三币无条件正式升级。继续优先保留趋势恢复版为通用改进方向。冷却补恢复未触发增益，本轮不采用。完整比较及基准见 `trend_recovery_revision/REPORT.md`。


## 2026-10-07 选择性延迟退出：新的优先研究方向

`BtcCoinGuardRisingMediumExitStrategy` 仅在个币 EMA20>EMA50 且 EMA50 仍上升时延迟原个币退出，BTC 退出不延迟。相比趋势恢复版，三币长期收益增加 20.51 个百分点、最大回撤不变（532.52%/40.93%）；近期略改善，其余三个主要阶段不变。18 个单币案例 2 个共同改善、16 个不变。优先保留该方向，不自动替换正式版本；上一轮更激进 SOL 候选保留局部研究价值。源码冻结于 `selective_coin_exit_revision/strategies/selective_coin_exit_strategy.py`，完整比较见同目录上级 `REPORT.md`。第二个 BTC MA200 门控候选不列为优先。


## 2026-10-07 防守候选：半峰值恢复

优先保留 `BtcCoinGuardHalfPeakRearmStrategy` 为防守研究方向，源码冻结于 `cycle_risk_half_peak_revision/strategies/half_peak_rearm_strategy.py`。BTC风险恢复时仍恢复原仓位，但内部峰值取旧峰值与当前权益中点，保留部分损失记忆；不增加账户状态、不修改入场退出或原阈值。2023至今433.22%/47.78%，正式版417.12%/49.71%；长周期496.49%/40.24%，正式版497.43%/40.83%；近期收益与回撤略改善，其余三个主要阶段相同。2025年度收益略差，改善有限，尚未生产部署。前三项入场防守规则不采用，完整代价见 `cycle_risk_half_peak_revision/CONCLUSIONS.md`。正式版仍为CycleRisk，运行服务不变。

半峰值恢复取舍更新：用户明确否定其回撤改善幅度，不列为优先候选，仅保留实验记录；正式版不变。

### 回撤归因后验证（2026-10-07）

最大回撤主要由SOL老仓回吐与后续反复入场共同造成。EMA20确认/退出、50%单币新增/持仓约束四项固定假设已跑完六窗口并对比持有；均未达到明显降低完整周期回撤且保留大部分收益的要求，不推广至strategies根目录。正式版保持CycleRisk。归因与全部折中记录见cycle_risk_drawdown_diagnosis/REPORT.md和cycle_risk_weight_cap_revision/CONCLUSIONS.md。

### 个币亏损预算后续验证（2026-10-07）

盈利平仓恢复、动态趋势恢复、恢复保持至该笔结束三种预算结构已完成六窗口比较。熊市和近期改善，但上涨与指定长周期收益损失偏大；最后一版2023至今368.56%/45.71%，约持有收益66.95%，仍不足以成为通用显著改进。全部只留在研究目录，不增加正式strategies文件，不升级、不列新通用优先候选。完整取舍见cycle_risk_latched_budget_revision/CONCLUSIONS.md。

### 活动目录再次清理（2026-10-07）

删除无依赖、无活动配置引用的严格MA150历史类BtcTrendFullCycleDefensiveStrategy及旧字节码缓存。保留8个Python文件，正式版及其继承链、原Portfolio、温和CoreHold、独立趋势、运行与Compose兼容类均有用途；最新失败实验没有进入活动目录。其余核心类AST与清理前一致，冻结研究数据与源码不变。

### 正式版单文件迁移（2026-10-07）

当前CycleRisk直接继承IStrategy，只需cycle_risk_strategy.py一个自定义文件、一个策略类；不再依赖CoreHold/Phased/FastExit/CoinGuard/EquityRisk。原八文件和四个研究配置冻结于user_data/archive/cycle_risk_flatten_20261007；研究方向仍可用归档策略路径复现。活动目录保留四个文件，其余三个用于原Portfolio对照、现有运行服务及Compose兼容。六个原生周期、逐日权益、全部交易订单与风险轨迹均与迁移前核对；规则不变、运行服务未切换。详见cycle_risk_flatten_verification/REPORT.md。
