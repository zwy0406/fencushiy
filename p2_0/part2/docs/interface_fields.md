# P2-0 Part1→Part2 字段与边界

代码基线：`feature/part2-uavnetsim`、Part1 HEAD `83964df`。新增文件仅在 `part2/` 和独立测试内。适配器从当前 `Simulator.cluster_manager.backbone_planner.active_snapshot`、`Simulator.drones`、`env.now` 读取，**不读取 R4 CSV 作为正式运行状态**，不调用 planner.plan、RNG 或 SimPy 事件。首次 1 s 网络快照发布前拒绝读取。

| 输出 | 来源 | 单位/含义 |
|---|---|---|
| `time_us`, `snapshot_time_us`, `epoch` | `env.now`, `active_snapshot.created_time_us/epoch` | 微秒；可计算快照龄期 |
| `node_id`, `position_m` | `Drone.identifier`, `coords` | 稳定 ID、三维米坐标 |
| `residual_energy_j`, `initial_energy_j`, `available` | Drone 能量、sleep | 焦耳；可用需未休眠且电量>0 |
| `cluster_id`, `ch_id`, `cluster_role` | Drone 字段 | 当前网络角色，可随 1 s 重分簇变化 |
| `is_backbone_relay` | 已发布 `backbone_relays` | 全局骨干角色，非固定簇角色 |
| `clusters`, `cluster_heads`, `backbone_relays` | BackboneSnapshot | 复制为独立整数/元组映射 |
| `paths_to_bs`, `routes` | BackboneSnapshot | 已发布规划结果，不重算路径 |
| `planned_path_to_bs` | CH 的已发布路径；BR 的路由表；CM 的 CM→CH + CH 路径 | 路径候选，不能视为成功投递 |
| `planned_path_available` | 路径起止为 UAV 与 BS | 快照拓扑口径 |
| `route_available_now` | 上述路径各跳存在于快照有效边、当前几何距离≤通信范围、节点可用 | 保守实时几何口径；仍不代表信道/MAC 成功 |

`NetworkState` 和 `NodeState` 都是只读数据副本；映射采用 `MappingProxyType`，路径为元组。普通 CM 没有直接骨干路由表项，因此必须显式检查 CM→CH 附着边，不可把 CH 可达性直接赋予所有成员。快照到下一次 1 s 更新之间可能变旧；`route_available_now` 做当前几何复核，但不会更新 Part1 路由。

`ClusterTaskManager.advance()` 消费该状态，独立维护任务群；任务群 ID 不使用网络 `cluster_id` 或 CH ID。`task_group_anchor` 初始为成员位置质心，仅是工程定位锚点，**不是 PoI 目标**。`service_uav_ids` 由显式 PoI 候选集合与资源规则计算。状态 `active/degraded` 表示任务群层判断，不改 Drone 角色。默认 Jaccard≥0.40 匹配、连续 2 次成员变化确认、最短 2 s 保持、连续 2 次路径全失联降级，均为可测试初始值，未经开发集选参。

服务节点规则：候选必须由覆盖层明确提名；节点需可用、存在保守 BS 路径、未被其他任务占用，电量≥25%。出现在骨干 CH→BS 路径内部的关键转发节点需电量≥50%。CH/BR 可以服务，只要满足这些约束；CM 不自动服务。若未提供覆盖候选集合，服务集合为空。这尚未评估 PoI 覆盖质量、队列负担或最优能耗，下一阶段需接入任务分配器后做消融。
