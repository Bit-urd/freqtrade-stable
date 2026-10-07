# 正式版单文件迁移前的冻结归档

2026-10-07归档，来源提交a72882a17。`strategies/`保存迁移前八个活动文件，`manifest.json`记录原始哈希。该目录保留历史继承链和研究入口；当前正式版为活动目录的单文件CycleRisk。

研究方向包括CoreHold、FullCycle、14日冷却、Phased、FastExit、CoinGuard、EquityRisk和个币独立趋势。Portfolio/FastTest/周线兼容策略也保存迁移前快照，活动目录继续保留它们以支持现有运行配置。

原活动研究配置已移至`configs/`：

- config_core_growth_btc_sol_eth.json
- config_trend_btc_sol_eth.json
- config_trend_fast_exit_btc_sol_eth.json
- config_trend_coin_guard_btc_sol_eth.json

配置中的strategy_path指向本归档的strategies。仓库根目录或Docker的/freqtrade工作目录下可按以下形式复现：

```bash
freqtrade backtesting -c user_data/archive/cycle_risk_flatten_20261007/configs/config_trend_btc_sol_eth.json --strategy-path user_data/archive/cycle_risk_flatten_20261007/strategies --timerange 20230101-20241231
```

旧CycleRisk也在归档内。比较旧版时需显式指定本目录，避免与当前正式版同名类混淆。此前研究目录的冻结源码、回测记录及结论保留原路径。

整理收益是依赖更短、规则更容易审查、减少对试验父类的耦合；代价是归档版本与正式版本分开维护，未来公共逻辑修改需明确同步范围。使用旧版专属指标列或继承父类的扩展，需继续指定归档路径或单独迁移。本次没有实现风险状态重启持久化，也没有部署。

旧清理审计脚本与报告对应当时目录结构，不用于断言当前正式源码逐字一致；当前迁移验证请使用verify_cycle_risk_flatten.py、test_cycle_risk_flatten.py和verify_flatten_strategy_loading.py。CoreHold/FastExit/CoinGuard的离线检查已支持归档路径。
