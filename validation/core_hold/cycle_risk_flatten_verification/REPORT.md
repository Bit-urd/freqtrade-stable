# CycleRisk 正式版单文件迁移

正式类保持BtcCoinGuardCycleRiskStrategy，依赖从4个自定义Python文件、8个策略类缩短至1个文件、1个策略类，直接继承IStrategy。正式参数、进退出、冷却、独立复利预算、账户降仓及BTC风险重启不变；删去未参与正式决策的周线和熊市/核心仓指标计算。

历史实现与研究配置归档至user_data/archive/cycle_risk_flatten_20261007。原Portfolio/FastTest和Compose引用的周线策略继续保留；运行服务未切换、未重启。原有账户风险状态重启持久化缺口仍存在，本次仅整理结构。

## 六窗口与旧版一致

| 区间 | 收益 | 最大回撤 |
|---|---:|---:|
| 2023-01-01～2024-12-31 | +527.79% | 30.31% |
| 2021-07-01～2022-11-21 | +69.40% | 44.55% |
| 2022-01-01～2022-11-21 | -29.14% | 31.54% |
| 2025-09-01～2026-10-06 | -18.85% | 43.68% |
| 2022-11-21～2025-10-07 | +497.43% | 40.83% |
| 2023-01-01～2026-10-06 | +417.12% | 49.71% |

不仅最终指标相同：逐日权益、完整交易记录、全部订单及每日风险轨迹均核对。已完成边界与因果性检查；额外信号列删除是有意的，使用这些历史列的第三方扩展需继续使用归档父类或显式迁移。

{"passed": true, "native_runs": 6, "matching_summary_rows": 12, "compared_strategy_days": 4393, "compared_trades_including_terminal_force_exit": 376, "compared_orders_including_terminal_force_exit": 822, "max_numeric_difference": 0.0, "daily_equity_matches": true, "all_fills_match": true, "risk_traces_match": true, "rule_checks": {"passed": true, "tests_run": 14}, "loading_checks": {"passed": true, "active_python_files": 4, "archive_configs_loaded": 4, "loaded": [{"strategy": "BtcCoinGuardCycleRiskStrategy", "location": "active"}, {"strategy": "Ma200BtcRegimeFullCycleFastTestStrategy", "location": "active"}, {"strategy": "Ma200BtcRegimeFullCyclePortfolioStrategy", "location": "active"}, {"strategy": "Ma200BtcRegimeWeeklySizedPortfolioStrategy", "location": "active"}, {"strategy": "Ma200BtcRegimeFullCycleCoreHoldStrategy", "config": "config_core_growth_btc_sol_eth.json", "location": "archive"}, {"strategy": "BtcTrendPhasedStrategy", "config": "config_trend_btc_sol_eth.json", "location": "archive"}, {"strategy": "BtcTrendCoinGuardStrategy", "config": "config_trend_coin_guard_btc_sol_eth.json", "location": "archive"}, {"strategy": "BtcTrendFastExitStrategy", "config": "config_trend_fast_exit_btc_sol_eth.json", "location": "archive"}]}, "archived_entrypoint_checks": {"passed": true, "tests_run": 20}, "archive_hashes_match": true, "active_source_matches_replayed_source": true, "custom_files_before": 4, "custom_files_after": 1, "custom_classes_before": 8, "custom_classes_after": 1}

复现：以原研究容器挂载方式运行run_cycle_risk_flatten_verification.py，再运行test_cycle_risk_flatten.py，宿主机运行verify_cycle_risk_flatten.py。使用同一冻结行情、手续费和1000 USDT账户，不引入新的参数选择。
