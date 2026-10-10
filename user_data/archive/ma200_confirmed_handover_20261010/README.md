# 保留的 MA200 优化候选：趋势确认后交接补仓

2026-10-10 用户明确选择保留；状态为保留的研究候选，未替换正式策略或切换运行服务。

策略类：`Ma200ConfirmedHandoverStrategy`。文件：[ma200_confirmed_handover.py](strategies/ma200_confirmed_handover.py)。同目录冻结父策略 [ma200_btc_regime_full_cycle_portfolio_strategy.py](strategies/ma200_btc_regime_full_cycle_portfolio_strategy.py)，后续正式父策略变化不会改动此快照。

机制：BTC连续两根完整日线站上MA200，且个币满足现有牛市EMA20/50排列与上升条件，才把熊市交接仓位补到目标槽位；之后使用既有周线仓位规则。均线、退出及熊市分档买入参数未调整，没有币名特例，没有增加灾难止损或历史账户回撤控制。

五币、十币各六个起点均比MA200原版提高收益，回撤最多分别增加约0.50、0.22个百分点。六币18个独立案例11个提高、4个下降、3个相同，SOL2023是明显反例。总计36次新原生回测均通过逐日现金/净值独立复算。所有源文件和关键证据摘要见 [RETAINED.json](RETAINED.json)。

[完整对照报告](evidence/FINAL_REPORT.md) · [其他标的与反例](evidence/OTHER_ASSETS_AND_COUNTEREXAMPLES.md)。证据目录保存组合及单币汇总、原始测试协议、门槛判断与核对记录。

完整成交、逐日净值、原始数据引用与复现脚本保留在 `validation/core_hold/ma200_confirmed_handover_20261010`；在仓库根目录执行 `bash validation/core_hold/ma200_confirmed_handover_20261010/run_docker.sh` 可重跑五币阶段。十币和单币驱动脚本分别位于该目录的 `ten/driver.py`、`single_assets/driver.py`，采用已记录的固定Docker镜像、/research研究挂载，并要求上阶段通过。

候选尚需订单取消、成交失败和重启恢复验证。此轮保留不等于实盘上线；下一项分阶段补仓实验尚未实现，不能混入本版本。
