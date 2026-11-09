# RS-D-MADDPG 历史开发与实验记录恢复报告

检查日期：2026-11-09  
范围：本机 Codex 会话索引、可访问的 Codex rollout/归档、授权本地项目与 GitHub 仓库副本、现存实验归档。全程只读；未改算法代码、未启动训练或仿真。

## 结论摘要

找到了 RS-D-MADDPG 的一份较完整**返修冻结版候选**：本地 `D:\codex\biai\mcs-upload`，分支 `revision/phycom-v1-frozen`，HEAD `3ad62c227e57da418c70b4bad58fcd5a309e1f2e`。其 `phycom/` 实现、协议配置、训练/评估入口和结果归档能支持有根据的迁移审查；也找到了更早的 root-level MADDPG 版本及多个 Codex 开发、调参和制图会话。

但证据链**不足以认定该候选就是 DOI 论文最终发表源码**：没有找到训练模型 checkpoint；本地结果包 README 明确排除 checkpoint、批量原始输出和生成图；若干旧数据文件明确标作 predicted/transcribed；论文草稿与代码的折扣因子等参数有冲突；也没有一条已验证的“发表版源码提交 → 实际训练命令与解析后配置 → 完整训练日志 → checkpoint → 论文图表原始数据”闭环。因此本报告称其为“返修冻结版候选”，不称“已确认发表版”。

## A. 找到的历史会话

本机 Codex SQLite 线程索引可读（约 20,465 条 item、165 个 thread ID）；本机 `.codex/sessions` rollout 和 `.codex/archived_sessions` 也做了针对关键词的检索，没有读取或输出凭据类内容。

| 会话 | 时间/位置 | 与 RS-D-MADDPG 的关系及证据等级 |
|---|---|---|
| `codex://threads/01a0c6d5-ca2c-7e80-8475-58f009377dd2` | 2026-09-22 至 2026-11-09；Codex 线程索引及本地 rollout | 可访问，但标题/内容主要是 Part1 服务器、恢复和后续集成；不是最初编写第二部分算法的会话。 |
| `019f79ba-c071-7722-bf31-24f9d41b7afd`，“连接我的服务器” | 2026-07-19/20；旧工作区 `D:\codex\biai` | 返修冻结和参数审查讨论；记录代码/表格 gamma 不一致、训练入口的 lr/tau 隐式倍率等。它不是最初原始算法实现会话。 |
| `019f83bd-747b-7630-8b69-749a0cda229f`，“继续会话任务” | 2026-07-21 后；`D:\codex\biai` | 实验方案与正式结果/预测结果的区分；不构成完整原始代码来源链。 |
| `019fa799-3621-76f2-ab85-3baddb5b60c4`、`019fa7bd-3e08-7cf2-a1eb-8475df9098ce` | 2026-07-28；旧工作区及 `D:\zhuomian\8.7\tu` | 图表调整、结果呈现和绘图数据路径。 |
| `019fb346-251f-7230-aba9-4790c40910d5`，“重新跑实验7.30” | 2026-07-30 至 2026-08-04 | 后期调参/hover 与 Ptx28 等试验。会话记录中 8 月初候选 pilot 仍未完成，不能当最终论文训练证据。 |
| `019fb331-a05d-7812-82e2-ca816d666702`，“预估结果” | 2026-07-30 至 2026-09 | 含尾部指标与制图讨论；有文件/表格明确为 predicted，不能冒充实测。 |
| `01a07192-5522-71e0-89a0-d8edbec9e7c4`，审稿意见讨论 | 2026-09-05 | 返修审计，涉及移动能耗解释等。 |

另检索到 ChatGPT 历史会话 `6a6d6428-306c-83ea-a2d1-8a9806d36077`（2026-08-01，“RS-D-MADDPG 调参计划”），主要是调参计划，不等于最后论文实验记录。`6a9d1cd2-d950-83ea-8026-61b25714e8f9`（返修讨论）、`6ab8b05f-0570-83ea-942c-f021f7a54a82`（Part1→Part2 设计）也不是原始第二部分算法开发完整记录。

**未找到**可明确认定为最初实现 Actor、Quantile Critic、CVaR 及 AMO 奖励的完整 Codex 对话。线程检索覆盖到当前可访问的索引和本地 rollout，但不能证明其他设备、已删除线程或未同步账号历史不存在。`.codex/archived_sessions` 中两个压缩存档未发现相关实现记录。

## B. 找到的源码版本与 Git 证据

### 本地 `mcs` 仓库候选

路径：[mcs-upload](</D:/codex/biai/mcs-upload>)  
分支：`revision/phycom-v1-frozen`  
HEAD：`3ad62c227e57da418c70b4bad58fcd5a309e1f2e`  
工作区：检查时 clean；该分支跟踪同名远端分支。Git 历史包含：

- `3ad62c2` — Complete revision statistics exports（2026-07-20）；
- `4a35f47` — AMO search gated on complete M1 pilot validation；
- `6a2a690` — experiment artifacts record runtime commit；
- `4515900` — paired initialization snapshots read-only；
- `77b48ae` — freeze training/evaluation manifests；
- 更早的 `e8d5ba3`（2026-01-05 左右，发布代码快照）、`89f1c76`、`e378419`、`0798b25` 等历史实现。

归档中有多个 Git bundle。HEAD bundle `phycom_rev_3ad62c2.bundle` 的 SHA256 与其旁边校验文件相符（`cc90da8e57c1d2a7f028564cebe64cca8d46e86a50a8db0359184086b373c021`）。

仓库 README 自称用于 manuscript revision 的 research snapshot，并说明仓库**不含**模型 checkpoint、大型日志、生成图和批量实验输出，数值引用前应重新复现/审计。此说明限制了它作为发表版完整证据包的证明力。

### 版本分层

1. **root-level 旧实现**：`train.py`、`env_A.py`、`env_AMO.py`、`maddpg/maddpg_uav.py`、`maddpg/agents_vector.py` 等。该版本有 5 维 observation，Critic 默认 32 quantiles，且不是当前冻结配置的准确实现。
2. **`phycom/` 返修冻结实现**：有显式配置、quantile Huber、fractional lower-tail CVaR、manifest/评估代码，技术上最接近当前论文草稿/返修工作流；但仍不能据此确认是正式出版时实际运行的最终版。
3. **`main` 发布快照**：存在公开 GitHub 仓库 `zwy0406/mcs`，但其本身也不含权重和完整批量结果。不能仅因其是 main 或公开仓库就认定是最终发表版本。

本机历史 Git 分支、commit、bundle 和文件均只读检查；没有 reset、clean、checkout 或 stash 操作。此前指定的 Codex 归档分支 `codex/part1-part2-archive-20261109` 是 UavNetSim 项目归档，不是 mcs 的 RS-D-MADDPG 训练源码。

## C. 最接近论文的版本及依据

目前最接近所给论文主题和返修文本的是 `revision/phycom-v1-frozen` 的 `phycom/` 版本，依据是它同时包含：RS-D-MADDPG 的集中式 Critic/分布式 Actor、分位数分布价值、CVaR 下尾聚合、AMO 配置、Random/Clustered 评估设置、6 UAV/40 PoI 的配置、协议清单及论文统计导出工具。

这只是“最接近的可审计候选”，并非“已验证最终发表代码”。以下冲突仍未消解：

- 本地论文草稿 Table 2 写 `gamma=0.82`，冻结配置及历史会话所述代码为 `gamma=0.83`；
- 用户给出的待核线索 tau=.15 与冻结配置 tau=.01 不同；旧 `train.py` 还会把 tau 乘 1.5，实际值可能由 CLI 与隐式倍率共同决定；
- root-level 旧代码 observation 为 5 维，`phycom` README/论文返修设计称 4 维；
- root-level Quantile Critic 默认 32 个分位，而冻结配置显式 K=50；
- checkpoint 缺失，无法从训练权重反推实际运行代码/配置。

所读本地稿件：[Manuscript-PYyuangao.docx](</D:/zhuomian/8.7/tu/Manuscript-PYyuangao.docx>) 是本地返修稿，不是已验证的出版社最终 PDF。其 Fig. 3–8 captions 可读到；该文件未检索到 Fig. 9 或 Tables 6–7 的完整内容，因此不能声称已恢复它们的最终绘图输入。

## D. 训练配置、权重、原始结果是否找到

| 材料 | 结果 | 说明 |
|---|---|---|
| 训练代码 | **找到候选** | `mcs-upload/phycom/` 和 root-level 旧实现；具体哪个实际产生论文权重未知。 |
| 配置 | **部分找到** | `configs/protocol_v1.json` 与 `protocol_v1_fully_resolved.json`；有 6 UAV、40 PoI、K=50、alpha=.1、gamma=.83、dmax=1km、vmax=20m/s、decision interval=50s、1200 episodes、seeds2025–2029 等。解析配置中 AMO 参数有与普通配置不同值，需依据训练实际读取的 resolved config。 |
| 模型权重 | **未找到** | 在已检查的 mcs、结果包、paper_data、`D:\codex\fencu` 和相关论文目录中未找到 RS-D-MADDPG 的 `.pt/.pth/.ckpt`。搜索范围外仍可能存在。 |
| 训练/评估记录 | **部分找到** | 结果归档有 JSON/TXT/日志与 manifests；README 明确说批量输出、大型日志和权重不在代码仓库中。若干结果目录只包括有限场景/种子或中间指标。 |
| 原始论文图数据 | **部分找到且来源混杂** | `D:\codex\biai\paper_data` 有 CSV/TSV；部分 README 指定仅 3 个种子/M1、M5、M6，或文件名含 `predicted`/`transcribed`。不能将其全部视为最终发表原始数据。 |
| 完整证据链 | **未找到** | 未能将某次训练的精确源码提交、实际命令、resolved config、完整日志、checkpoint、测试输出和 Fig.3–9/Table6–7 输入逐一 hash/manifest 关联。 |

公开/归档代码树的文件清单和 bundle 可支持源码审计；它们本身不能替代训练过程产物。当前 SSH 对新服务器不可用；先前 P2-1A 记录中服务器目录仅为浅层搜索且认证被拒，不能声称这次检查已穷尽服务器内容。

## E. 核心算法与历史源码对应

以下标记：**[SRC]** 当前可读源码直接确认；**[MAN]** 本地论文返修稿确认；**[CHAT]** Codex 历史会话记载；**[INF]** 由代码/材料推断；**[UNK]** 当前无法确认发表实验实际采用情况。

| 内容 | 可核实情况 |
|---|---|
| 分布式 Actor / CTDE | [SRC] `phycom/networks.py` 和 `phycom` agent 使用每 UAV Actor 与集中式 Critic。root-level 旧版也有 per-agent Actor、joint obs/action Critic。实际论文实验所用提交仍 [UNK]。 |
| Actor 输入输出 | [SRC] root-level `env_A.py`/`env_AMO.py` 为 5 维 observation；actor 输出 2 维 tanh 连续动作。返修冻结版描述/配置为 4 维 observation。正式稿/发表实验最终维数 [UNK]，形成明显版本差异。 |
| 动作映射 | [SRC] 旧环境将动作映射为方向角 `(a_0+1)π` 与距离 `(a_1+1)*0.5*(0.1*region_size)`，region=10 km 时上界为 1 km/step。速度约束还取决于 50 s 决策步。 |
| Quantile Critic | [SRC] root-level Critic 默认 K=32，训练入口没有显式传 K=50；冻结 `phycom` 配置为 K=50，并使用 pairwise quantile Huber。论文 Algorithm 1/稿件 Table 2 声称 50。故旧 root-level 不匹配当前论文表述。 |
| CVaR | [SRC] root-level 按排序后的最低 `max(1,int(alpha*K))` 个 quantile 求均值；冻结版实现 fractional tail mass 的 lower-tail CVaR，并可处理非整数尾部。稿件描述提取最低分位，但“发表版精确采用哪个计算实现” [UNK]。 |
| Critic 更新 | [SRC] root-level 使用 MSE 标量 Critic 更新，不是分位数对分位数的 quantile Huber；冻结版 `phycom` 使用 quantile Huber。版本差异是关键。 |
| AMO 奖励 | [SRC] `env_AMO.py` 有 coverage、fairness、energy、penalty 等动态奖励项及 configurable weights/thresholds；冻结配置也提供 AMO 值。历史调参会话记录了 P0/P1…候选和后续调整 [CHAT]，但没有完整逐轮 diff→正式运行→权重文件链，无法可靠断言“哪次改动真正提高论文结果”。 |
| 奖励的最终值 | [SRC] 普通配置/fully-resolved 配置存在差异；本地稿 Table 3 记录一组候选与选定值，但表格文字提取存在公式/符号丢失。发表训练实际加载值 [UNK]，必须回到每个 run 的 resolved config。 |
| 训练超参 | [SRC] 冻结配置有 gamma=.83、tau=.01、K=50、alpha=.1、hidden=160×2、batch=256、replay=300k、warmup=2k、1200 episodes、5 个训练 seeds。旧入口默认 gamma=.95、tau=.01 并有 critic LR/tau 倍率；这些差异说明入口默认值不等于实际运行值。 |
| 论文表格参数 | [MAN] 本地稿 Table 2 有 6 UAV、40 PoI、K=50、alpha=.1、gamma=.82；没有从当前文档摘取到 tau=.15 的证据。需要出版社 PDF 和最终补充材料核实。 |
| 终止/评价 | [SRC] 有训练、评估脚本和多个 scenario 配置；[UNK] 无法证明具体论文图所用 checkpoint、评估 episode 数及每个统计汇总的逐样本定义。 |

## F. 目前发现的源码/论文差异

1. `gamma`: 本地稿 Table 2 `.82`，返修冻结配置 `.83`；历史对话也记载表格/代码不一致。
2. `tau`: 用户提供线索 `.15`，冻结配置 `.01`；旧入口可能将命令行 tau 乘 1.5。实际运行配置必须从对应 manifest 查验。
3. Observation：旧 root-level 为 5 维；`phycom` 返修设计为 4 维。
4. Quantile 数量：旧 root-level 默认 32；冻结协议配置明确 50。
5. Critic loss：旧 root-level 是 aggregate scalar 的 MSE；冻结版有 pairwise quantile Huber。
6. CVaR：旧版按整数下尾分位数取均值；冻结版允许 fractional alpha tail；当 `alpha*K` 为整数时两者可能相同，其他情况下定义不完全相同。
7. 实验配置：普通与 fully-resolved 配置对 AMO mobility gain/threshold 等存在值差异；应以每次 run 的解析后 manifest 为准。
8. 证据工件：绘图稿和数据包混有估算/转录文件，且缺 checkpoints，不能以图形外观或表格数值反推最终模型。

## G. 可复用模块

- `phycom/networks.py` 的 Actor/Critic 网络骨架、集中式联合输入、分位数输出与 quantile Huber，可作为迁移候选，但迁移前应固定旧模型尺寸并写逐层 shape/权重兼容检查。
- `phycom` 中下尾 CVaR 聚合与风险诊断代码可作为算法参考；需对照论文定义及旧实验日志确认风险目标究竟作用于 actor、critic target 还是 evaluation。
- 训练/评估编排、seed/config manifest、风险/quantile diagnostics、绘图汇总脚本可以复用其工程结构，但 UavNetSim 中 observation、action、奖励和 episode 语义均不同。
- P2-0 的 `NetworkStateAdapter`、`ClusterTaskManager` 是新的 UavNetSim 连接接口，不是原 RS-D-MADDPG 训练实现。历史报告：[P2-0 report](</D:/codex/fencu/p2_0/part2/docs/p2_0_report.md>)。

## H. 必须重写或适配的模块

- 环境侧 observation builder：映射到 UavNetSim 的真实位置/能量/覆盖/网络连通状态；原 4/5 维向量不可未经定义直接套用。
- 动作执行适配：旧动作是每决策步方向+距离，UavNetSim 有自己的物理位置更新；必须设单一移动写入者，将动作裁剪为 `d_move ≤ min(d_max, v_max Δt)`，禁止与现有物理更新重复推进。
- 动态智能体/任务群到 RL batch 的 mask、加入退出和 replay transition 语义；原六机固定数组不能直接用于动态成员数。
- Part1 通信可达性、路径状态及“有效 PoI 覆盖”评估；纯几何覆盖不能替代通信可达的有效服务。
- 环境奖励、移动能耗/通信能耗记账、终止条件与指标定义；应单独定义 Part2 跨层实验，不改 Part1 奖励或网络算法。

## I. 尚未找到或尚未确认

- 最初 Codex 算法实现对话及完整变更序列；
- DOI 对应出版社最终 PDF/补充材料与最终发表代码的精确关联；
- 最终训练使用的 Git commit、命令行、完全解析配置与运行环境；
- 论文最终模型权重/checkpoint；
- 与 Fig. 3–9、Tables 6–7 一一对应的完整原始样本文件和生成脚本；
- 每次 run 的完整 episode/step 日志及所有场景、方法、种子工件；
- 旧调参中哪些变化被纳入正式训练，哪些只是 pilot/估值；
- 目前无法登录的服务器上是否另有源码、权重或历史工件。

## J. UavNetSim 迁移建议

1. **先补证据**：用户提供出版社最终 PDF、最终运行目录/压缩包（含 `resolved_config`、log、checkpoint、评估原始数据）及缺失的 Codex 会话导出；记录 SHA256 和来源，不覆盖现有文件。
2. **固定候选基线**：以 `revision/phycom-v1-frozen` 为审计候选，在独立 Part2 分支保存 commit/bundle；明确论文版 vs 返修候选的差异清单。
3. **固定六智能体兼容层**：先映射六机静态状态/action，复现源模型输入输出 shape、CVaR/quantile loss 单元测试；不要一开始就做可变数量策略。
4. **连接 P2-0**：由 `NetworkStateAdapter` 只读提供网络状态；`ClusterTaskManager` 维护慢层协作组；构造独立 RL observation 与 alive/communication/service mask。网络簇 ID/CH 不作为 task-group identity。
5. **运动闭环先短测**：实现唯一 `MovementController` 写入位置，验证物理步长、2/3/5 秒动作位移约束、邻居/路由更新、能耗守恒及可达 PoI 覆盖；只做短时确定性冒烟，不碰 Part1 核心。
6. **再做动态 agent 与 replay**：固定六机基线稳定后，定义可变集合的 padding+mask 或参数共享；明确 agent 加入/退出后的 recurrent/actor state、replay tuple 与 centralized critic 聚合规则。
7. **分开论文结论**：原论文实验只由其已确认 checkpoint/配置/数据支持；UavNetSim 新实验标作跨平台迁移/扩展，使用独立配置、seeds、manifest 和结果目录，不混写为原论文复现。

### 需要用户手动提供的材料

优先提供：① DOI 对应出版社最终 PDF 与补充材料；② 当年训练机/服务器打包出的最终源码和 `resolved_config.json`；③ checkpoints；④ Fig. 3–9、Tables 6–7 的源 CSV/绘图脚本；⑤ 上述会话若在另一设备/账号，请从该 Codex 导出涉及初始实现、最终训练、奖励/CVaR 修改的会话；⑥ 若旧服务器还有数据，请提供可用登录方式或离线备份。无需发送任何密码或私钥；通过安全方式共享文件/账号内连接即可。

## 证据与材料索引

- 源码候选：[mcs-upload](</D:/codex/biai/mcs-upload>)
- 返修稿：[Manuscript-PYyuangao.docx](</D:/zhuomian/8.7/tu/Manuscript-PYyuangao.docx>)
- 返修数据包：[phycom_results_data_figures_20260724](</D:/codex/biai/phycom_results_data_figures_20260724>)
- 图表工作数据：[paper_data](</D:/codex/biai/paper_data>)
- 本地图表/Origin 工程：[D:\zhuomian\8.7\tu](</D:/zhuomian/8.7/tu>)
- P2-0 接口状态：[p2_0_report.md](</D:/codex/fencu/p2_0/part2/docs/p2_0_report.md>)
- 之前 P2-1A 审查记录：[p2_1a_source_audit.md](</D:/codex/fencu/p2_1a/p2_1a_source_audit.md>)（当时检查范围有限；本次扩大检索后找到了上述独立 `mcs-upload` 候选，应以本报告的分层结论为准。）

---

**最终判断：** 找到了可审计的返修冻结代码和部分实验记录，但未找到足以证明“这就是最终发表版本”的完整证据链，也未找到模型权重。下一步不应从零盲写算法；先由用户补齐出版社最终稿及 checkpoint/运行工件，再以冻结候选做受控核对。完成本报告不代表算法迁移或训练已开始。
