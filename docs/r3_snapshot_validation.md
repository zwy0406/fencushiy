# R3 动态簇快照记录验收（2026-11-06）

- 代码仓库：`/opt/data/private/LCX/fencushiy`
- 审查基线：`d25e802`；R3 完成提交：`83964df`；分支：`feature/part2-uavnetsim`
- 恢复等级：`regression-validated reconstruction`，历史最终源码提交尚未找回。
- 历史 F0、R0–R2 数据未覆盖。R3 的 50 次 F0 回归批次已终止，未继续运行。

## 代码

相对审查基线改动：`experiments/run_experiment.py`、`experiments/r3_f0_regression.py`、`tests/test_cluster_snapshot_logger.py`、`topology/mwmp_dca/cluster_manager.py`、`topology/mwmp_dca/cluster_snapshot_logger.py`、`utils/config.py`。记录调用位于 `ClusterManager.recluster()` 尾部第 404 行，在骨干规划、簇指标记录、路由角色更新之后。记录阶段只将必要字段复制入内存，仿真结束后导出。

输出 `cluster_snapshots.csv`、`node_roles.csv`、`backbone_snapshots.jsonl`、`run_manifest.json`。`member_ids` 是含 CH 的 JSON 数组；BR 为全局骨干中继角色；`service_uav_definition` 为 `undefined`。manifest 含 schema、提交、seed、节点数、时长、更新周期、日志开关和实验配置。

## R3-B 30 秒开关一致性

Proposed，N=80（含 BS），seed2030，15 m/s，2 pkt/s/UAV，250 m，F0 轨迹重放，开关两臂均启用逐包诊断。独立输出：`results/r3_b_30s_20261105/off` 和 `results/r3_b_30s_20261105/on`。

- 13 个非汇总指标 CSV 逐字节相同，包括 4,799 条 `packet_outcomes.csv`；汇总 CSV 仅实验名称不同。性能与能耗统计、能耗守恒误差（1.1164339314140292e-09 J）一致，结束时间均为 30 秒。
- 开启日志得到 29 个唯一且连续的快照、418 条簇记录、2,291 条节点角色记录，记录错误 0。每个簇的成员数正确且包含 CH；每轮 79 个活动 UAV，BR 标志与发布的骨干快照一致；路径和路由为 JSON 对象结构。
- 墙钟：关闭 493.325 秒，开启 500.259 秒。
- 无可靠的全局事件计数器，因此没有比较事件数量。

## R3-C 300 秒验证：情况 A

复用历史 F0 `results/f0_formal_a3_seeds2030_2039_20261005/proposed/seed2030`。R3 日志开启运行位于 `results/r3_f0_logging_seeds2030_2039_20261105/proposed/seed2030`。两者 14 个指标 CSV 逐字节相同，逐包记录 47,352 条；R3 产生 299 个快照、记录错误 0。该 R3 运行墙钟 5084.832 秒。此运行属于恢复代码的回归验证，不能据此称找回历史原源码。后续提交仅增加 manifest 字段和修正未继续使用的回归脚本预期，没有改动网络算法或快照采集逻辑。

## R4 接口

快照包含簇成员集合、CH、节点角色、骨干中继、BS 路径和路由，支持按相邻时刻成员集合做 Jaccard/Hungarian 匹配，并单独分析 CH 与群成员寿命。R3 未执行 R4 的 9 组正式实验，也未实现 R4 的统计分析。簇成员数组顺序与骨干快照中的成员数组顺序可能不同，离线匹配应使用集合。
