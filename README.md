# TAE-MWMP-DCA A3 与 Part1→Part2 研究材料（2026-11-09）

本目录是上传到 `zwy0406/fencushiy` **独立分支**的可追溯材料包。该仓库现有 `main` 记录的是较早的 GA-MP-DCA / relay-hold 实验；本目录的 A3 配置、实验编号和结果属于后续研究，不能与旧结果合并统计。

## 已有材料

| 路径 | 内容 | 证据等级 |
|---|---|---|
| `part1_reconstruction/source.tar.gz` + `e5_patch.tar.gz` + `e5_finalize.tar.gz` | R0–R2 恢复候选源码，按此顺序叠加；另有 E10 独立计时脚本 | F0 50/50 同环境逐输出回归通过；旧最终源码提交未找回，等级为 `regression-validated reconstruction` |
| `docs/part1_recovery_acceptance.md` | F0 五方法×十种子回归验收、账本/流量一致性与来源记录 | 完整验收记录；不能将回归输出冒称历史新实验 |
| `docs/first_part_experiments_draft.md` | F0、E1、E2、E3、E5、E7、E8、E10 的历史结果摘要和论文讨论 | 历史报告；部分逐 seed 原始目录尚未恢复 |
| `docs/e8_prediction_report.md`、`docs/e10_complexity_report.md` | E8 配对比较及 E10 CPU 计时统计 | 旧服务器完成时核验过；本包不含旧原始运行目录 |
| `docs/r3_snapshot_validation.md` | R3 只读簇快照日志及开关一致性验收 | 报告；R3 提交 `83964df` 的完整服务器源码不在本包 |
| `results_archive/results/f0_formal_a3_seeds2030_2039_20261005/` | F0 50 次运行的逐次 metrics、manifest 与矩阵文件 | 从 NFS 原目录复制；未包含 figures、models 或 mobility replay 输入 |
| `results_archive/results/e1_n60_a3_seeds2030_2039_20261006/`、`e1_n100.../` | E1 N=60/100 的逐次 metrics 和 manifest；N=80 沿用 F0 | 原始运行指标已归档；未包含大体积 mobility replay 输入 |
| `results_archive/results/r3_f0_logging_seeds2030_2039_20261105/` | R3 日志版 F0 输出、指标与簇快照 | 同目录保存 cluster/node/backbone 日志；R3 验收报告见 `docs/r3_snapshot_validation.md` |
| `results_archive/results/r4_0_seed2030_20261106/`、`r4_1_a3_seed2025_20261106/`、`r4_1_5_seed2025_20261107/` | R4 先导与 N=60/80/100 seed2025 的 metrics、快照、分析 CSV/报告 | 单种子诊断数据，不是跨种子统计结论 |
| `results_archive/results/e7_formal_three_seed_20260929/`、`e7_b_followup_three_seed_20261001/` | E7 探索性消融结果 | 需按清单中的限制解释，不作为十种子正式结论 |
| `r4_0/`、`r4_1/`、`r4_1_5/` | 离线分析/分阶段运行脚本、单元测试与诊断报告 | 原始对应文件也在 `results_archive/` |
| `p2_0/` | NetworkStateAdapter、ClusterTaskManager、接口文档及测试 | P2-0 提交 `93125c1`，当时服务器 64 项单元测试通过；未训练 Part2 |
| `docs/experiment_figure_inventory_20261109.md` | 论文图表台账与各结果边界 | 写作规划，不是原始数据 |

## 尚缺的原始文件

- 归档的 F0/E1/R3/R4 运行保留逐次 metrics 和簇快照，但**不含 mobility replay 输入、生成图像、模型目录和运行日志**；服务器 NFS 仍是这些文件的完整保管副本。每次原始指标均附于 `results_archive/`，原始源目录结构保留。
- 旧服务器的 E2、E3、E5-H1、E8、E10 正式逐 seed 原始目录在换服务器后未找回。当前服务器顶层 `results/` 目录清单也没有这些实验；本包只保存已记录的统计报告；没有从均值、SD 或置信区间反造实验数据。
- E5-H2 未完成且用户已决定不补跑，不纳入论文正式表。R4-2 和 Part2 正式训练尚未执行。
- R3 的完整 `83964df` 代码和 P2-0 所在的服务器 Git 提交需要从 NFS 仓库或授权的服务器连接另行取回。这里的 P2-0 文件是本地保存的对应模块副本，不能代替服务器完整 Git 历史。

## 使用与核对

先阅读 `docs/part1_recovery_acceptance.md` 和 `docs/experiment_figure_inventory_20261109.md`。图表以逐 seed 原始数据为准；若只能用本包摘要作草图，应标记为“历史汇总重绘”，不可补造误差条。R4-1/1.5 每种规模仅 seed2025 一组，不作跨种子显著性声明。所有文件的 SHA-256 见 `FILE_SHA256.txt`。

本目录不包含私人论文全文、账户凭据或历史 GA-MP-DCA 大型试验文件。服务器快照源码、实验逐次指标和 R4 结果均来自 `feature/part2-uavnetsim` 的 HEAD `93125c1ae95d8ee07e8a6b457c6c9d6c2dbb0d3b`；代码恢复等级仍为 regression-validated reconstruction。
