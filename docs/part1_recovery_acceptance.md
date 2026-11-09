# Part 1 恢复验收基线

状态：R0、R1、R2 已完成。R1 隔离候选的 55 项单元测试与 F0 方法配置核对通过；R2 五方法 × seeds 2030–2039 共 50 项 300 s 回归通过。验收等级为 `regression-validated reconstruction`；旧服务器最终源码提交未找回，不能声称源码完全恢复。下文判据在回归运行前已冻结。不得用新运行冒充历史实验原始数据。

## 来源与隔离

- 新服务器：`root@49.123.2.32:25194`，原仓库 `/root/fencushiy` 当前 HEAD `d25e802`。已跟踪文件无差异，现有未跟踪结果必须保留。
- 旧服务器记录的 E5 实现提交为 `5dc79b6fb42f92b2e71440002497410c31672736`；新服务器 Git 对象中不存在该提交，远端 Git 当前 HEAD 为 `8ca2eea`。因此不能用 `git pull` 声称恢复原版。
- 本地候选：`D:/codex/fencu/e5-staging/source.tar.gz`（516 条目）、`e5_patch.tar.gz`（11 文件）、`e5_finalize.tar.gz`（3 文件）；最终文件可在 `e5-staging/` 查看。E10 独立脚本在 `server_fc_work/results/run_e10.py`。三归档 SHA-256 分别为 `EA55F5BE664D67FD708919168162451ACC70DA441F30466122B78996F191297C`、`34960CD5A0EA4A83705B48DA462A1549BAAF98F21B333B82371756C412D69BBB`、`6807317858D8A548FAA34490AFF7C1868B483A0694CA0367DEA4F2FED49B1837`。
- R1 必须先在新服务器的独立恢复目录验证候选，再决定如何集成；不得直接解压覆盖 `/root/fencushiy`。运行统一使用 Conda `fc`。
- 2026-11-02 本地 Windows Python 3.12 试运行 `tests/test_e5_energy.py` 在收集阶段因缺少 `simpy` 停止；这既非通过，也非代码断言失败。待服务器 `fc` 环境运行完整测试。
- 2026-11-02 三归档已按用户授权上传至 `/root/part1-recovery-20261102/`，服务器 SHA-256 与本地一致；按 source、patch、finalize 顺序解包于独立 `candidate/`。服务器 Conda `fc` 运行 `python -m unittest discover -s tests -q`：55 tests OK。`fc` 未安装 pytest，未使用 pytest 结果作为验收依据。
- 候选 `FROZEN_METHODS` 与现存 F0 manifest 的五方法配置完全相同；F0 定义为 N=80、v=15 m/s、2 pkt/s/UAV、250 m、300 s、seeds 2030–2039。尚未完成逐项代码参数和逐事件回归核对。
- R2 首项 Proposed seed 2030 已在候选目录启动，PID 初始为 `788988`，输出 `/root/part1-recovery-20261102/r2-proposed-seed2030/`，日志为同名 `.log`；复用现存 F0 轨迹。此为回归验证，不计入正式实验，也不覆盖 F0。
- 2026-11-02 Proposed seed 2030 已完成：旧 F0 与候选的全部 metrics CSV 逐字节一致，197 项 summary CSV 值无差异，`packet_outcomes.csv` SHA-256 同为 `8326fa989b57a87fc68d8da11ac27019881194fb7b387d6a747bd33b33ed29f8`。summary XLSX 二进制不同，但 `openpyxl` 读取的 sheet 与单元格值完全一致。此为单项逐输出回归通过，不代表全体 R2 或旧源码 hash 已恢复。
- Original seed 2030 已按顺序在同一隔离候选目录启动，PID 初始为 `870467`，输出 `/root/part1-recovery-20261102/r2-original-seed2030/`，日志为同名 `.log`；复用相同 F0 轨迹。
- 2026-11-02 Original seed 2030 已完成：候选与旧 F0 的全部 metrics CSV 逐字节一致，summary XLSX 单元格值完全一致，仅 XLSX 二进制封装不同；单项逐输出回归通过。
- DSDV seed 2030 已按顺序启动，PID 初始为 `996892`，输出 `/root/part1-recovery-20261102/r2-dsdv-seed2030/`，日志为同名 `.log`；仍只用于回归。
- 2026-11-03 DSDV seed 2030 已完成：全部 metrics CSV 与旧 F0 逐字节一致，summary XLSX 单元格值相同；单项逐输出回归通过。
- MOBIC seed 2030 已按顺序启动，PID 初始为 `1236933`，输出 `/root/part1-recovery-20261102/r2-mobic-seed2030/`，日志为同名 `.log`；仍只用于回归。
- 2026-11-03 MOBIC seed 2030 已完成：全部 metrics CSV 与旧 F0 逐字节一致，summary XLSX 单元格值相同；单项逐输出回归通过。
- TORP-like seed 2030 已按顺序启动，PID 初始为 `1360450`，输出 `/root/part1-recovery-20261102/r2-torp_like-seed2030/`，日志为同名 `.log`；仍只用于回归。
- 2026-11-03 TORP-like seed 2030 已完成：全部 metrics CSV 与旧 F0 逐字节一致，summary XLSX 单元格值相同。至此五方法的 seed 2030 单项逐输出回归全部通过。
- 扩展回归脚本为本地 `recovery_tools/r2_f0_regression.py`，已上传独立恢复目录；预检确认 45 个历史 F0 参考目录与 9 个轨迹文件存在。按 seed 逐组、每组最多 4 个进程，逐文件比较 metrics；发现差异即停止后续 seed，保留已完成输出，不覆盖 F0。后台初始 PID `1487444`，日志 `/root/part1-recovery-20261102/r2-batch.log`，输出 `/root/part1-recovery-20261102/r2-batch/`。
- 2026-11-05 扩展回归完成，日志结尾为 `R2 BATCH PASS 45/45`，无残留子进程。与五方法 seed 2030 合计 50/50；每个 run 的 metrics 目录除 XLSX 容器二进制外，其余文件与旧 F0 逐字节一致，XLSX 工作表及单元格值一致。因此配置、逐包输出、整数账本、时延与汇总均达到预注册的同环境回归标准。
- 独立审计 50/50 summary：`generated = delivered + terminal_drops + incomplete_at_horizon` 逐项成立；最大能耗守恒误差 `1.2924091796762127e-09 J`，小于 `1e-8 J`；最大逐包时延误差 `0 us`。十个 seed 内，五方法的 `packet_id` 与 `creation_time` 序列逐行相同，流量配对全部通过。
- 原仓库 `/root/fencushiy` 保持 HEAD `d25e802` 且已跟踪文件无变更；恢复候选与回归输出仍留在 `/root/part1-recovery-20261102/`。旧 E2/E3/E5/E8/E10 的正式原始数据未从回归中重建。

## R2 预注册验收表

| 层级 | 对象 | 通过条件 | 失败处理 |
| --- | --- | --- | --- |
| 定义 | A3 模块开关、权重、TLET、迁移上限、10 s PacketLifetime、能量与 PHY/MAC 参数、N/v/负载/T、seed | 与现存 F0 manifest 和冻结计划逐项相同；非实验性路径、时间戳除外 | 停止回归，修复来源/配置，不按结果调参数 |
| 输入 | 初始坐标、移动轨迹、逐包生成序列及 packet ID | 同 seed 使用现存 F0 轨迹；规范化后的逐项序列完全一致，不只比较包数 | 停止，检查 RNG、依赖版本和 replay 入口 |
| 账本 | generated/delivered/各 drop reason、包终态、通信与控制能耗 | 整数和事件分类逐项相同；能耗账本守恒误差不超过既有检查口径 `1e-8 J` | 停止，定位实现或导出差异 |
| 逐包时延 | delivered packet ID 对应的生成/交付时间 | 同 ID 对齐后逐项一致；仅序列化浮点误差允许 `1e-6 us` | 停止，检查事件顺序和浮点环境 |
| 汇总 | PDR、E_pkt、Delay、RoutingLoad、ControlEnergy、R_BS | 只在上述层级通过后比较；同一实现及环境要求与 F0 导出精度一致 | 不以近似 PDR 单独宣布恢复成功 |

回归顺序：先固定 seed 2030 的 Proposed 和 Original，随后覆盖 F0 五方法的相同 seed；全部通过后再扩大 seed。源代码、依赖锁定、输入轨迹和逐事件输出均可核对且一致时才可称 `exactly recovered`。若只能证明配置相同与核心行为回归、但缺少旧源码 hash 或逐事件一致性，应标为 `regression-validated reconstruction`，不得称原版完全恢复。

## 后续边界

R3 只加被动簇快照记录，并检验日志开关前后随机流和输出一致；D0 簇动态诊断独立命名，不替代旧 E1/E2/E3。`T_task`、Jaccard 迟滞和 Part 2 控制仅在 R5 冻结后的 `part2-integration` 分支实现。历史原始结果恢复与这条代码恢复线并行，不将新数据并入旧实验。
