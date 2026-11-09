# P2-1B 确定性运动与通信闭环

开发分支 `codex/p2-1b` 基于本机可用的 Git 归档 `e473d80`。工作区根目录的 Git HEAD 指向无效引用，远端 SSH 未连接成功。本次在隔离解包的 `uavnetsim_source_93125c1.tar.gz` 上完成集成和测试。交付形式是归档分支中的增量文件，服务器运行目录尚未部署。

## 改动与运行方式

| 文件 | 用途 |
|---|---|
| `part2/integration/movement_controller.py` | 确定性平面角度、距离动作，限速限距，100 ms 物理步进，边界裁剪和推进能耗记账 |
| `part2/integration/deterministic_loop.py` | 装配显式受控 UAV，读取已发布网络状态，调用 P2-0 任务群，按分配评价 PoI |
| `part2/simulator_drone_factory.patch` | 为仿真器提供 Drone 类型装配点。普通 Simulator 默认继续构造 Drone |
| `tests/test_p2_1b_loop.py` | 两节点真实仿真集成测试、空控制对照和候选周期动作边界测试 |

在独立目录解包 `part1_reconstruction/uavnetsim_source_93125c1.tar.gz`。从解包根目录执行 `git apply --check <归档分支路径>/part2/simulator_drone_factory.patch`，成功后用 `git apply` 应用。把新增的两个集成模块和测试复制到解包树中的同名路径。P2-0 模块已在源码包内。依赖就绪时，在该目录运行 `python -m unittest discover -s tests -p test_p2_1b_loop.py -v`。

`DeterministicSimulator` 根据显式 UAV ID 选择单一运动写入者。它使用 live MWMP_DCA 模式及现有 BS，未选择的节点使用原移动模型。调用者在网络快照已发布、当前物理 tick 已执行之后调用 `DeterministicLoop.decide`。该接口接收 UAV→PoI ID 集合、方向弧度和请求距离米，动作周期以微秒计，必须是物理步长的整数倍。测试使用 2 秒。3 秒和 5 秒仅通过位移约束验证。动作到期后悬停。时间、位置、速度和推进账本分别使用 µs、m、m/s、J。

Part1 的网络进程在原有时钟内更新。覆盖评价读取当前坐标、明确分配的 PoI 和 P2-0 的实时路径判定。几何覆盖要求可用服务 UAV 在 3D 感知半径内，有效覆盖另外要求路径当前可用。每个 PoI 最多计一次。该指标是拓扑可达代理，实际投递、延迟和端到端吞吐仍需单独测量。决策间路径失效会立即影响评价，动作重分配由下一次外部决策负责。

## 测试结果

- 本地 `unittest discover` 共 67 项，65 项通过、2 项跳过。三项新增测试全部通过。
- 小规模闭环运行到约 3.1 秒。2 秒动作实际位移 40 m，单步位移不超过 2 m。新增推进能耗与 `2 s × P(20 m/s)` 一致，电池损耗等于推进和通信能耗之和。
- 移出范围时，已发布规划路径仍存在的一个采样点上，当前路径判定已不可用，有效覆盖清空，随后观测到 Part1 快照 epoch 前进。PoI 的几何覆盖仍可为真。
- 空控制选择与原 Simulator 的移动类型、位置、推进能耗及网络快照相同。原有 P2-0 测试通过，包括真实 R4-1 快照夹具、CH 变化、成员增减、分裂及合并。
- 本机 PyTorch 安装不可用，两项 PyTorch 相关用例跳过。测试启动器避开受限的 Windows MIME 注册表读取，并按缺少 PyTorch 的路径验证现有预测器回退。未验证真实 PyTorch 推理和远端完整环境。

本阶段的运行范围是短时确定性测试。Part1 的分簇、路由、MAC、能耗公式及参数来自 `93125c1` 源码包。本文不报告原论文模型复现或跨场景统计结果。

下一阶段可复用的网络、分位价值、风险聚合和训练框架见 [论文与候选代码差异审查](paper_vs_recovered_code_audit.md)。
