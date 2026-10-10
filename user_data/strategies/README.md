# 当前活动策略

正式版为 `BtcCoinGuardCycleRiskStrategy`，位于 `cycle_risk_strategy.py`。它直接继承 Freqtrade 的 `IStrategy`，不再引用其他自定义策略文件。旧版四文件、八策略类的实现已经冻结归档。

2026-10-08 用户选定 BTC 连续两天弱势退出为正式版，个币两天退出、14天冷却和账户风控不变。正式九币现货配置为 [config_cycle_risk_nine_assets.json](../config_cycle_risk_nine_assets.json)，包括 BTC、ETH、BNB、LINK、XRP、UNI、DOGE、SOL、ARB，九个预算槽位。ZEC/PUMP移除，HYPE现货验证历史不足暂不纳入。[当前正式记录](OFFICIAL.json)保存源码和配置哈希。

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

上述迁移报告记录的是此前代码结构整理。最新两天退出升级依据见[九币验证报告](../../validation/core_hold/without_zec_pump_20261008/REPORT.md)。本次正式升级未切换、重启运行服务。正式版账户风控状态的重启持久化缺口仍存在。

## 合约回测入口（2026-10-08）

[cycle_risk_futures_strategy.py](cycle_risk_futures_strategy.py) 提供独立类 `BtcCoinGuardCycleRiskFuturesStrategy`：USDT逐仓、1倍做多、BTC两天退出，其余信号与账户风控规则沿用已验证版本。文件独立继承IStrategy，不再从研究目录导入自定义Python模块。27币配置为 [config_cycle_risk_futures_27.json](../config_cycle_risk_futures_27.json)。

`cycle_risk_funding_data_dir` 指向冻结资金费raw目录，`datadir`指向相同快照的合约feather数据。配置默认按此前Docker研究挂载 `/research/requested_27_futures_half_year_20261008` 读取。本版本仍需同目录 `run.py` 的资金费结算边界适配才能精确复现此前收益，单独用原生CLI会采用引擎默认边界。本入口只支持回测，实时模拟盘/实盘需要另行接入资金费账本；现货正式选择和现有服务不变。原研究源文件保留用于复现历史报告。

## MA200 补仓版单文件入口（2026-10-11）

[ma200_cash_supplement.py](ma200_cash_supplement.py) 提供 `Ma200CashSupplementStrategy`，已将 MA200 父策略和趋势确认交接逻辑内置，不再依赖其他自定义策略文件。合并保持原交易逻辑及资金阻塞条件；未切换运行服务。类与函数 AST 等价核对通过，33 项补仓功能检查通过。配置选择 `"strategy": "Ma200CashSupplementStrategy"`；`cash_supplement_enabled` 默认为 true。

### 挂单只暂停本币补仓（2026-10-11）

单文件补仓版已取消“任一币挂单就暂停整个组合”的限制。有挂单的交易不参与额外补仓分配，其他合格交易使用钱包剩余可用现金，并仍受引擎 max_stake、手续费及目标缺口限制。原调仓、转档、新开仓预算及数据检查仍保留。历史归档对应修改前版本，本次没有重新计算历史收益或切换运行服务。

### 新开仓预算预留（2026-10-11）

单文件版遇到未持有币潜在入场信号时，改为预留所有空槽位的完整预算及手续费（熊市候选预算合计更大时采用更大值），仅将剩余现金用于补仓。未持有币数据未知时仍保留全部现金；原调仓、交接和持仓数据缺失保护保留。每日计划键升级为 v2，避免恢复旧版预算计划；每日请求防重标记保留。本次没有重新计算历史收益或切换运行服务。

挂单隔离与新开仓预留调整已完成五币、2021—2025五起点回测：[完整报告](../archive/ma200_cash_reservation_20261011/REPORT.md)。完整交易记录与旧版一致，未发现此次修改新增的收益或回撤变化；历史账本现金存在相同的小额负值，已单列说明。无充值，未部署。

### 买入手续费预算修正（2026-10-11）

单文件补仓版为模拟钱包保留剩余持仓买入手续费，实盘不重复扣历史费用；买单上限预留当笔手续费。父策略信号、档位、退出及目标公式未修改。43项功能检查及五币五起点回测通过：每日重建现金转正，收益差−0.013至−0.520个百分点，回撤略降。[完整修复对照](../archive/ma200_fee_budget_20261011/REPORT.md)。未切换服务。
