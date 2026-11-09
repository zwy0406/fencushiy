# TAE-MWMP-DCA A3 与 Part1→Part2 研究材料（2026-11-09）

本目录是拟上传到 `zwy0406/fencushiy` **独立分支**的可追溯材料包。该仓库现有 `main` 记录的是较早的 GA-MP-DCA / relay-hold 实验；本目录的 A3 配置、实验编号和结果属于后续研究，不能与旧结果合并统计。

## 已有材料

| 路径 | 内容 | 证据等级 |
|---|---|---|
| `part1_reconstruction/source.tar.gz` + `e5_patch.tar.gz` + `e5_finalize.tar.gz` | R0–R2 恢复候选源码，按此顺序叠加；另有 E10 独立计时脚本 | F0 50/50 同环境逐输出回归通过；旧最终源码提交未找回，等级为 `regression-validated reconstruction` |
| `docs/part1_recovery_acceptance.md` | F0 五方法×十种子回归验收、账本/流量一致性与来源记录 | 完整验收记录；不能将回归输出冒称历史新实验 |
| `docs/first_part_experiments_draft.md` | F0、E1、E2、E3、E5、E7、E8、E10 的历史结果摘要和论文讨论 | 历史报告；部分逐 seed 原始目录尚未恢复 |
| `docs/e8_prediction_report.md`、`docs/e10_complexity_report.md` | E8 配对比较及 E10 CPU 计时统计 | 旧服务器完成时核验过；本包不含旧原始运行目录 |
| `docs/r3_snapshot_validation.md` | R3 只读簇快照日志及开关一致性验收 | 报告；R3 提交 `83964df` 的完整服务器源码不在本包 |
| `r4_0/`、`r4_1/`、`r4_1_5/` | 离线分析/分阶段运行脚本、单元测试与诊断报告 | R4-1 原始 300 s 日志在服务器 NFS，当前未能拉入本包；单种子诊断 |
| `p2_0/` | NetworkStateAdapter、ClusterTaskManager、接口文档及测试 | P2-0 提交 `93125c1`，当时服务器 64 项单元测试通过；未训练 Part2 |
| `docs/experiment_figure_inventory_20261109.md` | 论文图表台账与各结果边界 | 写作规划，不是原始数据 |

## 尚缺的原始文件

- 新服务器持久化 NFS：`/opt/data/private/LCX/fencushiy/results/` 中的 F0、R3、R4-1 原始运行目录目前尚未复制进来；本包不宣称包含这些逐包和逐快照数据。
- 旧服务器的 E2、E3、E5-H1、E8、E10 正式逐 seed 原始目录在换服务器后未找回。本包只保存已记录的统计报告；没有从均值、SD 或置信区间反造实验数据。
- E5-H2 未完成且用户已决定不补跑，不纳入论文正式表。R4-2 和 Part2 正式训练尚未执行。
- R3 的完整 `83964df` 代码和 P2-0 所在的服务器 Git 提交需要从 NFS 仓库或授权的服务器连接另行取回。这里的 P2-0 文件是本地保存的对应模块副本，不能代替服务器完整 Git 历史。

## 使用与核对

先阅读 `docs/part1_recovery_acceptance.md` 和 `docs/experiment_figure_inventory_20261109.md`。图表以逐 seed 原始数据为准；若只能用本包摘要作草图，应标记为“历史汇总重绘”，不可补造误差条。R4-1/1.5 每种规模仅 seed2025 一组，不作跨种子显著性声明。所有文件的 SHA-256 见 `FILE_SHA256.txt`。

本目录不包含私人论文全文、账户凭据或历史 GA-MP-DCA 大型试验文件。
