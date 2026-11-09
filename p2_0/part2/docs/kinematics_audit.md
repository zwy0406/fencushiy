# 运动学和时间尺度核查

## 已从当前仓库确认

- `Simulator.env.now`、`BackboneSnapshot.created_time_us` 和 `config.CLUSTER_INTERVAL=1e6` 的单位为微秒；网络维护周期 1 s。
- `GaussMarkov3D.position_update_interval=1e5` 微秒，即 0.1 s；方向/速度更新间隔 `5e5` 微秒，即 0.5 s。位置推进使用 `velocity × interval/1e6`，坐标为米。
- Drone 创建时 `speed=config.DEFAULT_UAV_SPEED`（默认 10 m/s），但 Gauss–Markov 的 `next_speed` 会随机变化；这个默认值不是经验证的最大速度。F0/R4 可通过运行配置覆盖速度。
- replay 模式也会在记录时间点直接设置位置/速度；若再由 Part2 直接移动同一 Drone，将造成重复推进。
- PHY 路损/路由邻居判定读取当前坐标；ClusterManager/BackbonePlanner 每次网络更新重建拓扑，R3 快照只在完成后发布。任务决策期间的坐标改变可能早于下一次骨干重算，需标识快照龄期。

## 尚不能从此仓库确认

已发表 RS-D-MADDPG 的方向角范围、移动距离动作的归一化、`d_max`、原决策步长及 `v_max` 源码未在本仓库找到。不能把 UavNetSim 的默认速度当作这些原算法常量。

## 对接约束

对周期 `Δt∈{2,3,5}` 秒，单动作的合法位移分别为 `min(d_max,2v_max)`、`min(d_max,3v_max)`、`min(d_max,5v_max)` 米。代码的 `max_legal_displacement` 和 `bounded_move` 仅验证该界，不改变位置。单元测试以**示例** `d_max=50 m, v_max=15 m/s` 得 30/45/50 m，不能作为论文正式参数。

P2-1 必须让同一 UAV 在同一时段只有一个位置写入者：在现有移动模型的单个 0.1 s 更新过程内执行 Part2 目标跟踪，或使用独立的新移动模型替换原模型；不得让 Gauss–Markov、replay 和 Part2 控制器同时写 `coords`。每次任务动作在周期内平滑执行，速度受限，边界和推进能耗按真实 0.1 s 积分。网络邻居/骨干在原 1 s 周期更新；覆盖状态按实际位置和 PoI 更新。持续失联可触发 Part2 任务状态变化，但 P2-0 不改 Part1 的路由更新频率。
