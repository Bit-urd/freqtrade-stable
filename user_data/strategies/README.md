# 当前活动策略

正式版为 `BtcCoinGuardCycleRiskStrategy`，位于 `cycle_risk_strategy.py`。它直接继承 Freqtrade 的 `IStrategy`，不再引用其他自定义策略文件。旧版四文件、八策略类的实现已经冻结归档。

| 文件 | 用途 |
|---|---|
| `cycle_risk_strategy.py` | 当前正式版，日线BTC与个币趋势保护、独立复利预算、账户回撤降仓及BTC恢复时风险重启 |
| `ma200_btc_regime_full_cycle_portfolio_strategy.py` | 原Portfolio对照，以及FastTest运行策略的父类 |
| `ma200_btc_regime_full_cycle_fast_test_strategy.py` | 当前运行服务依赖的短周期执行验证版 |
| `ma200_btc_regime_weekly_sized_portfolio_strategy.py` | 现有Compose引用的兼容策略 |

正式版只需要一个自定义Python文件。整个活动目录保留四个文件，是因为还要支持原Portfolio对照、运行服务和现有配置；后三个文件均不是CycleRisk的依赖。

## 归档的研究方向

CoreHold、FullCycle、冷却、分阶段、FastExit、CoinGuard、EquityRisk，以及个币独立趋势实现，保存在 [归档目录](../archive/cycle_risk_flatten_20261007/README.md)。对应研究配置已移动至同目录下的 `configs/`，并设置归档策略路径。原文件名和类名保留，便于复现。

此前失败的EMA20过滤、单币仓位上限、亏损预算等试验仍在 `validation/core_hold` 研究目录，没有纳入正式版。历史冻结研究源文件不修改。

## 行为核对

[迁移报告](../../validation/core_hold/cycle_risk_flatten_verification/REPORT.md)核对了六个既有周期的收益、最大回撤、逐日权益、完整交易订单及风险轨迹，并检查缺失数据、冷却边界、退出优先级和已收盘数据因果性。

本次只整理代码结构，不调整交易规则或参数，不切换、重启运行服务。正式版账户风控状态的重启持久化缺口仍存在。
