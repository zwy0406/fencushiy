# 论文与 RS-D-MADDPG 返修候选的差异

基线是 `zwy0406/mcs` 的 `revision/phycom-v1-frozen@3ad62c2`，重点审查 `phycom/`。论文侧的 0.15、28 dBm、0.55、0.551 和悬停项来自本轮提供的发表版核对口径。DOI 入口未能读取全文，公式编号和发表版归一化分母仍待核实。下表不把本地返修稿等同于发表全文。

| 项目与公式 | 候选源码及一致性 | 历史运行证据 | 复用、调整与结果影响 |
|---|---|---|---|
| 目标网络软更新 `θ′ ← (1−τ)θ′ + τθ`，论文 τ=0.15 | `phycom/maddpg.py` 的 `soft_update` 直接读取配置，无根目录旧入口的 1.5 倍倍率。基础配置 τ=0.01，不一致 | 7 月 pilot 和 fully resolved 配置、PTX26 实验配置、PTX28 启动配置均为 0.01。未找到 0.15 的同版本运行工件 | 可复用函数。未来按实验协议显式传参并记录有效值。0.15 的单次混合系数是 0.01 的 15 倍，会改变 bootstrap target 的变化速度，无法据此预判收益 |
| A2G `SNR_dB = P_tx + G_tx + G_rx − PL − N`，论文 28 dBm | `phycom/link_budget.py` 读取 `link_budget.a2g_tx_power_dbm`；基础及 7 月 fully resolved 均为 30 dBm | `shiyan_remote_setup/protocol_v1_shiyan_hover05_ptx28.json` 显式为 28；同目录 shell 脚本将它传入训练与评估。另有 26 dBm 归档。28 dBm 的配置和命令可查，未核实对应的完整模型及发表图表链 | 链路预算代码可作为论文复核候选。应将发射功率与场景、阈值、功率模型一起冻结。其他参数固定时接收 SNR 减 2 dB，边缘 PoI 及有效覆盖可能改变。P2-1B 使用 Part1 自身的通信模型 |
| AMO 归一化移动代价阈值 0.55 | `phycom/environment.py` 读取 `amo.mobility_threshold`；基础配置为 null。 `scripts/analyze_m1_validation.py` 按 pilot 的单步 Q70 解析，`prepare_amo_search.py` 也构造 Q60/Q80 候选；`finalize_protocol_freeze.py` 拒绝未解析阈值 | 7 月 pilot 和 fully resolved 工件值为 `1.457046276e−08`。PTX26 与 PTX28 悬停配置为 1.4，smoke 脚本的 0.25 仅用于冒烟。未查得可归属正式运行的 0.55 配置 | 可复用阈值解析和记录机制。先验证代价定义和单位，再确定阈值，禁止把 0.55 直接套到不同尺度。若代价限制在 [0,0.5]，0.55 不会被越过，AMO 惩罚触发会改变 |
| 论文移动代价有悬停基准项，报告值 0.551 | `phycom/environment.py` 按裁剪后的实际位移计算 `0.5 × d_actual/d_max`，无悬停项；在合法动作下上界 0.5 | `remote_setup_energy_ptx26.py` 有候选环境的历史覆盖代码，实际位移近零用 0.5，其他为 `0.5+2d_actual/d_max`，失效节点置零。PTX28 配置也指定此模型及系数，但原提交环境不消费该配置，必须有对应环境补丁。未把 0.551 追溯到已核实原始样本或明确分母 | 0.551 在带悬停项的模型内可出现，不能据此识别版本或证明数值复现。后续应核实每步/每机分母、失效节点及悬停口径，用原始位移和统计程序复算。P2-1B 的推进账本使用焦耳和现有 EnergyModel |

## 文件与证据

- 源码与基础配置在 `D:/codex/biai/mcs-upload/phycom/`、`configs/protocol_v1.json`、`scripts/`。
- 解析后配置在 `D:/codex/biai/phycom_results_data_figures_20260724/configs/`，26 dBm 配置和部分评估工件在 `D:/codex/biai/revised_energy_ptx26_paper_results_2025_2027/`。
- 28 dBm 历史启动文件在 `D:/codex/biai/shiyan_remote_setup/`。含 predicted 的绘图资料未用作运行证据。

28 dBm 和悬停代价已有历史实现线索。仍缺同时匹配论文四项口径的源码提交、运行配置、checkpoint 和原始图表数据。修改默认配置无法补齐这些证据。

## 下一阶段可复用模块

- `phycom/networks.py` 的 Actor 和集中式 Quantile Critic 架构，以及 quantile Huber、下尾 CVaR 数学实现。先核对 tensor shape、分位索引和发表公式。
- `phycom/maddpg.py` 的 CTDE 更新结构及显式 τ 软更新。固定六机核对完成后再扩展动态 agent mask。
- 候选回放、种子清单和评估导出结构。动态成员身份、掩码与终止语义需要另行定义。
- P2-0 的实时网络状态适配器和独立任务群。旧 AMO 奖励、归一化代价和旧环境位置更新不进入 P2-1B。
