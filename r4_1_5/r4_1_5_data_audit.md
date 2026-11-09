# R4-1.5 数据可用性审查

数据源：`results/r4_1_a3_seed2025_20261106/n{60,80,100}`。只读分析；三个 `n*_stage.json` 均为 `passed`。分支 `feature/part2-uavnetsim`，原实验代码提交 `83964df`。分析仅涉及 seed2025。

| 项目 | N60 | N80 | N100 | 口径 |
|---|---:|---:|---:|---|
| 网络快照 | 299 | 299 | 299 | 1–299 s，每秒一次 |
| 逐包结果 | 35495 | 47319 | 58969 | 与 summary 生成包数一致 |
| 已交付 | 8535 | 7340 | 5753 | `packet_outcomes.csv` |
| 末端未结算 | 1034 | 1437 | 1803 | `IncompleteAtHorizon`，不是已丢包 |

三组均有 `cluster_snapshots.csv`、`node_roles.csv`、`backbone_snapshots.jsonl`、`run_manifest.json`、`packet_outcomes.csv`、`packet_hops.csv`、汇总指标、ClusterMetrics 时序文件。R4-1 已完成簇/节点/BR/路径和能量账本验收；本分析另外逐行核对 299 个时间点、每点 N−1 个活动 UAV、簇归属、CH 及 BR 标志，并核对逐包数。

**可直接使用：** 包生成时间、ID、最终结果及原因、成功包交付时间与时延；每秒的 CH、成员、BR、BS 路径与路由快照。`packet_hops.csv` 有部分逐跳时间。根据相邻快照推断 CH/成员/BR/路径变化，时间分辨率仅为 1 s，无法断言秒内事件顺序。

**缺失或不可等价替代：** `packet_outcomes.csv` 没有所有丢包的统一精确终止时间；没有连续时间的真实通信中断起止时间；没有可逐包直接归因于某次 CH 轮换的标签；没有 Service UAV 集合。`R_BS^graph`、`R_BS^route` 是原实验整体指标，本分析的 `snapshot_path_available` 仅表示快照中 CH 路径以 BS 节点 0 终止，三者不可混称。

窗口 PDR 按**生成时间**把全部生成包放入分母；未结算包给出下界（视为未交付）和上界（未来均交付）。成功包时延是最终交付包的条件均值，不表示仅在窗口内完成交付。`RouteUnavailable`、`MigrationExhausted` 只表示窗口生成包的最终结果，不表示失败恰在该窗口发生。原始结果未修改。
