# P2-0 实施与验收

基线：服务器 `/opt/data/private/LCX/fencushiy`，分支 `feature/part2-uavnetsim`，审查时 HEAD `83964df`，已有历史结果目录均未覆盖。新增 `part2/integration/network_state_adapter.py`、`cluster_task_manager.py`、包初始化文件、`tests/test_part2_integration.py` 及本目录文档；未修改 Part1、RS-D-MADDPG、配置或实验数据。

适配器直接读取当前 Simulator/Drone 与已发布 BackboneSnapshot；任务群管理器只维护自己的纯 Python 状态。测试覆盖未发布快照拒绝、状态脱离原对象、移动后路径几何失效、CH/簇编号变化、加入/退出、分裂/合并、BR 变化、短时/持续不可达、服务能量/占用约束、迟滞、2/3/5 s 位移上界，以及现有 R4 快照作为离线夹具。远端 Conda `fc` 的完整 `unittest discover` 结果：**64 项通过**（原 54 项 + 新增 10 项），无新仿真、无训练。

限制：本阶段只进行人工状态及历史快照离线测试，没有把慢任务周期挂到 SimPy，也没有用原 RS-D-MADDPG 源码做动作/价值兼容验证。原算法源码与动作上限仍需提供。默认服务筛选/迟滞阈值只是工程起点，不能被写成已优化结果。

P2-1 建议：先取得原 RS-D-MADDPG 源码和参数；核验固定六机输出；接入显式 PoI 任务候选与观测/动作 mask；再在独立 Part2 分支设置唯一移动写入者及双时间尺度调度，并用开发种子筛选参数。保持 Part1 冻结，正式实验等待新批准。
