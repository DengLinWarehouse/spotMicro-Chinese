# SpotMicro 导航方案设计：Hector 建图 -> Odom 融合 -> AMCL -> A* -> 局部跟踪 -> /cmd_vel

> 适用对象：基于本仓库 `software_orangepiaipro/` 路线，在 SpotMicro 四足平台上接入 RPLidar，完成室内静态地图建图、已知图定位与基础自主导航。
>
> 设计目标：优先实现一条可落地、可调、可验证的导航链路，而不是理论上最完整但对硬件和参数极度敏感的方案。

---

## 1. 结论先行

在当前仓库约束下，推荐主方案为：

```text
Hector SLAM 建图
  -> 独立 odom 链（激光里程计；有 IMU 时再做融合）
  -> AMCL 已知图定位
  -> A* 全局规划
  -> 简化路径跟踪器（第一阶段）/ DWA（第二阶段）
  -> /cmd_vel
  -> spot_micro_motion_cmd
```

明确推荐：

1. 建图阶段优先使用 `Hector SLAM`，不要先上 `gmapping`。
2. 导航阶段必须引入独立 `odom` 源，不能继续把 `spot_micro_motion_cmd` 自带的伪 `odom` 当作主导航里程计。
3. 局部控制第一阶段优先使用“简化路径跟踪器”，稳定后再切 `DWA`。
4. 第一阶段自主导航只放开 `linear.x + angular.z`，先禁用 `linear.y` 侧向运动。

不推荐：

1. `Gmapping + 仓库自带伪 odom + AMCL`
2. 一上来就把 `DWA`、动态障碍避让、侧向步态一起打开
3. 在没有急停、限速和吊架保护的情况下直接上实机闭环导航

---

## 2. 当前仓库事实与工程约束

本结论基于当前仓库已有实现，而不是抽象假设。

### 2.1 已有能力

1. 已有 `RPLidar` 接入和 `Hector SLAM` 演示启动链路。
2. 已有 `spot_micro_motion_cmd`，并且已经订阅 `/cmd_vel`。
3. 已有 `base_footprint -> base_link -> lidar_link` 相关 TF 发布能力。
4. 已有 `spot_micro_rviz` 模型与 RViz 配置。

### 2.2 当前关键缺口

1. 没有可信的导航用 `odom`。
2. 没有 `AMCL + map_server + move_base/global_planner` 的定位规划闭环。
3. 没有导航专用的速度安全门。
4. 没有针对四足步态特性的局部跟踪层。

### 2.3 最重要的现有限制

`spot_micro_motion_cmd` 中的 `odom` 不是传感器里程计，而是对命令速度的开环积分：

```cpp
float x_spd = cmd_.getXSpeedCmd();
float y_spd = -cmd_.getYSpeedCmd();
float yaw_rate = -cmd_.getYawRateCmd();

robot_odometry_.xyz_pos.x += x_dot*dt;
robot_odometry_.xyz_pos.y += y_dot*dt;
robot_odometry_.euler_angs.psi += yaw_dot*dt;
```

这意味着：

1. 它没有观测闭环。
2. 它不会反映打滑、落脚误差、转向不足、地面摩擦差异。
3. 它只适合调试展示，不适合作为导航主里程计。

因此，一旦引入正式导航链路，必须避免 `odom` TF 冲突：

1. 要么关闭 `spot_micro_motion_cmd.yaml` 中的 `publish_odom`
2. 要么不让它参与导航 TF 树

推荐做法是：**导航阶段把 `publish_odom` 置为 `false`，由独立 odom 节点发布 `odom -> base_footprint`。**

---

## 3. 问题拆解与攻关顺序

| 子问题 | 作用 | 对后续依赖 | 当前难度 | 优先级 |
|--------|------|------------|----------|--------|
| TF 树整理 | 保证所有模块坐标一致 | 建图/定位/规划全部依赖 | 中 | 1 |
| 独立 odom | 提供连续位姿先验 | AMCL、DWA 必需 | 高 | 1 |
| 静态建图 | 产出 `pgm + yaml` 地图 | AMCL、规划依赖 | 中 | 2 |
| 已知图定位 | 在地图中持续估计位姿 | 规划依赖 | 高 | 3 |
| 全局规划 | 给出无碰最短路 | 局部跟踪依赖 | 低 | 4 |
| 局部跟踪 | 将路径变成稳定速度命令 | 实机效果核心 | 高 | 4 |
| 安全门控 | 防止失控和误走 | 所有实机阶段必需 | 高 | 1 |

建议攻关顺序：

1. TF 与传感器链路
2. 独立 `odom`
3. Hector 建图与离线重放
4. AMCL
5. A* 全局规划
6. 简化路径跟踪器
7. DWA 替换或并行评估

---

## 4. 技术路线评估

### 4.1 建图：为什么先选 Hector，而不是 Gmapping 或 Cartographer

| 方案 | 原理概要 | 适用条件 | 性能预期 | 实现复杂度 | 调试难度 | 实机落地风险 |
|------|----------|----------|----------|------------|----------|--------------|
| Hector SLAM | 激光 scan matching 建图，对 odom 依赖较弱 | 无编码器、低速、小中型室内环境 | 地图可用，闭环一般 | 低 | 中 | 中 |
| Gmapping | RBPF，依赖较稳定 odom 先验 | 有可靠 odom、平稳底盘 | 地图可用，但对 odom 很敏感 | 中 | 高 | 高 |
| Cartographer 2D | 子图 + 回环优化，可融合 IMU | 有 IMU、CPU 足、接受较高复杂度 | 地图质量最好 | 高 | 高 | 中 |

推荐：`Hector SLAM`

推荐理由：

1. 当前仓库已经有 Hector 链路，复用成本最低。
2. 当前平台没有轮式编码器，仓库自带 `odom` 也不可信。
3. 四足步态带来的机体俯仰扰动对 `gmapping` 更不友好。

失效条件：

1. 长走廊或强对称环境
2. 原地快速旋转
3. 雷达扫描平面因机体俯仰而剧烈抖动
4. 地图过程中速度过快，导致 scan overlap 不足

控制建议：

1. 建图速度限制：`linear.x <= 0.10 m/s`
2. 建图角速度限制：`angular.z <= 0.20 rad/s`
3. 建图时优先走大弧线，不做急停急转

### 4.2 Odom：必须单独建设，而不是沿用现有伪 odom

候选方案如下。

| 方案 | 原理概要 | 适用条件 | 性能预期 | 实现复杂度 | 调试难度 | 实机落地风险 |
|------|----------|----------|----------|------------|----------|--------------|
| 伪 odom（现有） | 对 `/cmd_vel` 开环积分 | 仅调试演示 | 漂移大 | 低 | 低 | 高 |
| 激光里程计 | 相邻 scan 匹配输出 odom | 雷达稳定、低速 | 中等可用 | 中 | 中 | 中 |
| 激光里程计 + IMU EKF | scan matcher 提供平面位姿，IMU 提供角速度/姿态约束 | 有 IMU 且时序可控 | 最稳 | 中高 | 高 | 中 |

推荐：

1. 没有 IMU：使用激光里程计直接输出 `odom`
2. 有 IMU：激光里程计 + IMU 进入 `robot_localization` 的 2D EKF

不推荐：

1. 继续使用 `spot_micro_motion_cmd` 的伪 `odom`
2. 直接拿 IMU 双积分做平面位置估计

失效条件：

1. 雷达高度太低，脚或机身进入激光平面
2. 激光安装刚性不足，产生高频抖动
3. IMU 时间戳漂移、坐标轴定义错误
4. 四足步态引起的周期性俯仰/横滚扰动没有滤掉

### 4.3 定位：AMCL 是主选，但前提是 odom 可用

| 方案 | 原理概要 | 适用条件 | 性能预期 | 实现复杂度 | 调试难度 | 实机落地风险 |
|------|----------|----------|----------|------------|----------|--------------|
| AMCL | 粒子滤波，融合 map + odom + scan | 已有静态地图和连续 odom | 标准 ROS 导航路线 | 中 | 中 | 中 |
| Hector 直接定位 | 继续 scan matching | 小场景可以 | 可跑但不适合正式导航 | 低 | 中 | 中 |
| Cartographer localization | 在既有子图上定位 | 已采用 Cartographer | 精度高 | 高 | 高 | 中 |

推荐：`AMCL`

推荐理由：

1. 与静态栅格地图和 `move_base` 生态匹配最好。
2. 调试工具成熟，问题定位路径清晰。
3. 后续切 `A*`、`DWA`、自定义 tracker 都容易。

AMCL 的失效条件：

1. `odom` 连续性差，粒子预测严重偏离
2. 初始位姿误差太大
3. 地图重复结构过多
4. 动态障碍大量遮挡静态结构

### 4.4 全局规划：A* 优先，Dijkstra 作为保守回退

| 方案 | 原理概要 | 适用条件 | 性能预期 | 实现复杂度 | 调试难度 | 实机落地风险 |
|------|----------|----------|----------|------------|----------|--------------|
| A* / GlobalPlanner | 启发式最短路径 | 常规静态栅格 | 速度快，路径较自然 | 低 | 低 | 低 |
| Dijkstra / Navfn | 无启发式最短路径 | 小图、简单任务 | 更保守 | 低 | 低 | 低 |

推荐：`A*`

理由：

1. 对当前地图规模已经足够。
2. 路径长度和规划耗时更平衡。
3. 与后续局部跟踪更兼容。

失效条件：

1. footprint 设太小，规划结果穿过实际不能走的缝隙
2. inflation 半径不足，导致贴墙行走
3. 地图中存在伪通道或墙体断裂

### 4.5 局部控制：先简化路径跟踪，再评估 DWA

| 方案 | 原理概要 | 适用条件 | 性能预期 | 实现复杂度 | 调试难度 | 实机落地风险 |
|------|----------|----------|----------|------------|----------|--------------|
| 简化路径跟踪器 | 路径切线 + 横向误差 + 航向误差生成速度 | 静态环境、速度较低 | 最容易落地 | 低 | 中 | 低 |
| DWA | 速度空间采样 + 前向仿真 | 需要连续稳定 odom 和局部代价地图 | 更完整 | 中 | 高 | 中高 |

推荐策略：

1. 第一阶段：简化路径跟踪器
2. 第二阶段：在 odom、AMCL、costmap 稳定后再切 DWA

原因：

1. `DWA` 对 `odom`、控制周期、速度响应一致性更敏感。
2. 四足步态不是标准差速底盘，控制到实际位移存在非线性。
3. 第一阶段先做“能稳稳走到点”，比“一次性上完整导航栈”更现实。

简化路径跟踪器的失效条件：

1. 急转弯过多
2. 动态障碍需要局部绕行
3. 路径采样太稀疏，局部参考方向跳变

DWA 的失效条件：

1. odom 抖动
2. `cmd_vel` 跟踪不一致
3. 本体 footprint 建模不真实
4. costmap 更新频率不足

---

## 5. 推荐系统架构

### 5.1 模块划分

```text
RPLidar 驱动
  -> /scan

IMU 驱动（可选）
  -> /imu/data

激光里程计
  -> /scan_odom
  -> TF: odom -> base_footprint

robot_localization（有 IMU 时）
  -> 融合 /scan_odom + /imu/data
  -> /odom
  -> TF: odom -> base_footprint

Hector SLAM（建图阶段）
  -> /map

map_server（定位/导航阶段）
  -> /map

AMCL
  -> /amcl_pose
  -> TF: map -> odom

Global Planner（A*）
  -> /move_base/GlobalPlanner/plan

局部跟踪器 或 DWA
  -> /cmd_vel_nav

cmd_vel 安全门
  -> /cmd_vel

模式管理器
  -> /stand_cmd
  -> /walk_cmd

spot_micro_motion_cmd
  -> 步态控制
  -> 舵机命令
```

### 5.2 TF 树

推荐 TF 树如下：

```text
map
  -> odom
      -> base_footprint
          -> base_link
              -> lidar_link
```

约束说明：

1. `map -> odom` 由 `AMCL` 发布
2. `odom -> base_footprint` 由独立 `odom` 源发布
3. `base_footprint -> base_link` 继续由 `spot_micro_motion_cmd` 发布
4. `base_link -> lidar_link` 继续复用当前 YAML 里的雷达外参

禁止：

1. 同时让多个节点发布 `odom -> base_footprint`
2. 同时让多个节点发布 `map -> odom`

### 5.3 软件包组织建议

建议新增一个导航包，例如 `spot_micro_navigation`，结构如下：

```text
spot_micro_navigation/
  launch/
    slam_mapping.launch
    localization.launch
    navigation.launch
  config/
    hector_mapping.yaml
    laser_scan_matcher.yaml
    ekf_odom.yaml
    amcl.yaml
    costmap_common.yaml
    global_costmap.yaml
    local_costmap.yaml
    global_planner.yaml
    path_tracker.yaml
    dwa_local_planner.yaml
    safety_gate.yaml
  scripts/
    nav_mode_manager.py
    cmd_vel_safety_gate.py
    path_tracker.py
  maps/
    <saved_map>.pgm
    <saved_map>.yaml
```

这样做的原因：

1. 不污染 `spot_micro_motion_cmd`
2. 导航参数和步态参数解耦
3. 后续替换 `path_tracker` 为 `DWA` 时，不影响低层控制包

---

## 6. 各模块具体设计

## 6.1 Hector 建图阶段

### 目标

产出用于后续 `AMCL + A*` 的静态地图。

### 启动模式

建图阶段只保留以下链路：

```text
spot_micro_motion_cmd
  + RPLidar
  + Hector SLAM
  + RViz
```

### 关键参数建议

| 参数 | 建议值 | 说明 |
|------|--------|------|
| `map_resolution` | `0.05` | 足够平衡精度和开销 |
| `map_size` | `1024` 或 `2048` | 小房间 `1024`，户型/走廊 `2048` |
| `map_update_distance_thresh` | `0.20-0.30` | 低速四足比现有 `0.4` 更保守 |
| `map_update_angle_thresh` | `0.04-0.08` rad | 降低角度更新阈值有助于慢速闭环 |
| `scan_subscriber_queue_size` | `5` | 与现有一致即可 |

### 调参顺序

1. 先确认 `lidar_link` 外参正确
2. 再确认建图速度限制
3. 再调距离/角度更新阈值
4. 最后才考虑地图尺寸和多分辨率层数

### 实机策略

1. 雷达尽量安装在机身顶部中心附近
2. 激光平面不要穿过前腿摆动区域
3. 建图时优先匀速直行和大半径转弯
4. 每次只建 `5-10 min` 数据，先做小环境闭环

---

## 6.2 Odom 设计

## 6.2.1 目标

为 `AMCL` 和局部控制提供连续、平滑、可用的短时位姿先验。

## 6.2.2 方案 A：无 IMU

使用激光里程计直接输出 `odom -> base_footprint`。

建议：

1. 优先使用 scan matcher 类方案
2. 输出频率目标：`10-20 Hz`
3. 只估计平面 `x, y, yaw`

适用条件：

1. 室内结构明显
2. 速度低
3. 没有明显动态遮挡

## 6.2.3 方案 B：有 IMU

推荐结构：

```text
/scan
  -> 激光里程计 -> /scan_odom
/imu/data
  -> robot_localization EKF (two_d_mode)
  -> /odom
  -> TF: odom -> base_footprint
```

EKF 融合思路：

状态向量可理解为：

```text
x = [px, py, yaw, vx, vy, wz]^T
```

观测：

```text
z_scan = [px, py, yaw]^T
z_imu  = [yaw_rate]^T
```

工程建议：

1. `two_d_mode: true`
2. IMU 第一阶段只融合 `yaw_rate`
3. 不要急着把 `roll/pitch` 直接喂给 2D 导航 EKF
4. 若 IMU 姿态抖动明显，先只用陀螺仪角速度，不用绝对姿态

原因：

1. 四足步态天然带来周期性俯仰/横滚
2. 未做步态相位补偿时，IMU 姿态容易把高频摆动带进导航层

## 6.2.4 与现有控制器的关系

导航上车后，建议在 `spot_micro_motion_cmd.yaml` 中改为：

```yaml
publish_odom: false
```

理由：

1. 避免 `odom -> base_footprint` 重复发布
2. 避免 AMCL 和局部控制吃到错误 odom

如果短期内还要保留原伪 `odom` 做调试，可改名发布到其他主题，但不要再占用标准导航 TF。

---

## 6.3 AMCL 设计

### 目标

在已知静态地图中利用 `map + odom + scan` 持续估计机器人位姿。

### 推荐参数起点

| 参数 | 建议范围 |
|------|----------|
| `min_particles` | `300-500` |
| `max_particles` | `1500-2500` |
| `update_min_d` | `0.05-0.10` m |
| `update_min_a` | `0.05-0.10` rad |
| `resample_interval` | `1-2` |
| `laser_max_beams` | `40-60` |
| `laser_z_hit` | `0.85-0.95` |
| `laser_z_rand` | `0.02-0.08` |
| `transform_tolerance` | `0.20-0.30` s |

### 调参顺序

1. 先保守增大粒子数，确认能收敛
2. 再调 `update_min_d / update_min_a`
3. 再调 laser model 参数
4. 最后再压低 CPU 占用

### 成功判据

1. 上电后人工给初始位姿，`10 s` 内收敛
2. 静止 `1 min` 漂移小于 `0.10 m`
3. 原地小角度转向后，位姿不会跳变

### 失效场景

1. 初始位姿偏差过大
2. 地图闭环质量差
3. `odom` 抖动导致粒子预测分散
4. 雷达平面被腿或障碍周期性遮挡

---

## 6.4 全局规划：A*

### 推荐选择

优先使用 `global_planner` 的 `A*` 模式。

### 栅格地图参数

| 参数 | 建议值 |
|------|--------|
| 全局地图分辨率 | `0.05 m/cell` |
| 机器人等效 footprint | 先按 `0.32 m x 0.22 m` 矩形估算 |
| `inflation_radius` | `0.12-0.18 m` |
| `cost_scaling_factor` | `5.0-10.0` |

### footprint 建议

四足不能只按机身矩形建模，要把步态包络留进去。第一阶段宁可保守：

```text
[(0.16, 0.11),
 (0.16,-0.11),
 (-0.16,-0.11),
 (-0.16, 0.11)]
```

后续再根据实测擦碰情况收缩。

### 为什么不先用更激进的 footprint

因为当前真实落脚包络、转弯摆幅、侧向滑移都还没有标定。  
导航第一阶段更怕“规划能过、实机过不去”，而不是“规划略保守”。

---

## 6.5 局部控制

## 6.5.1 第一阶段推荐：简化路径跟踪器

设计目标：

1. 把全局路径转换为稳定低速 `/cmd_vel`
2. 与四足低层的实际响应不一致性解耦
3. 先做“安全到点”，再做“优雅避障”

### 控制结构

从全局路径上选一个前视点：

```text
L_d = 0.25 ~ 0.40 m
```

定义误差：

```text
e_y     = 机器人到路径切线的横向误差
e_theta = 当前航向与路径切线航向之差
```

建议控制律：

```text
v   = clamp(k_v * cos(e_theta), 0, v_max)
w_z = clamp(k_theta * e_theta + k_y * e_y, -w_max, w_max)
```

起始参数建议：

| 参数 | 建议值 |
|------|--------|
| `L_d` | `0.30 m` |
| `k_v` | `0.08-0.12` |
| `k_theta` | `1.2-2.0` |
| `k_y` | `0.8-1.5` |
| `v_max` | `0.10-0.12 m/s` |
| `w_max` | `0.15-0.20 rad/s` |

第一阶段建议：

1. `linear.y = 0`
2. 只用 `linear.x + angular.z`
3. 到点半径设置为 `0.15-0.20 m`

原因：

1. 四足侧向步态与实际侧移速度更难标定
2. 局部跟踪先简化维度更容易收敛

## 6.5.2 第二阶段再评估 DWA

只有在以下条件都满足时才建议切 `DWA`：

1. `odom` 平滑稳定
2. AMCL 长时间不发散
3. 全局地图和局部 costmap 没有明显误检
4. `/cmd_vel` 到实际运动响应相对一致

切 DWA 后的建议限制：

| 参数 | 建议值 |
|------|--------|
| `max_vel_x` | `0.10-0.12` |
| `min_vel_x` | `0.00` |
| `max_vel_y` | `0.00` 第一阶段保持关闭 |
| `max_rot_vel` | `0.15-0.20` |
| `acc_lim_x` | `0.15-0.25` |
| `acc_lim_theta` | `0.25-0.40` |
| `sim_time` | `1.0-1.5` |
| `controller_frequency` | `10-15 Hz` |

不建议一开始就打开 `max_vel_y`。

---

## 6.6 /cmd_vel 安全门

这是实机导航必须补的一层，不能省。

### 输入

1. `/cmd_vel_nav`
2. `/scan`
3. `/amcl_pose`
4. `/tf`
5. 可选 `/odom`

### 输出

`/cmd_vel`

### 建议门控逻辑

```text
若 scan 超时 > 0.30 s -> 输出 0
若 TF 查询超时 > 0.20 s -> 输出 0
若 AMCL 协方差超阈值 -> 输出 0
若 前方 0.35 m 内障碍出现 -> 输出 0
否则：
  限幅 v_x, v_y, w_z
  限加速度
  再转发到 /cmd_vel
```

第一阶段限幅建议：

| 量 | 上限 |
|----|------|
| `linear.x` | `0.12 m/s` |
| `linear.y` | `0.00 m/s` |
| `angular.z` | `0.20 rad/s` |

---

## 7. 推荐部署阶段

### 阶段 A：只做建图

目标：

1. 证明雷达外参、TF、建图链路正常
2. 产出可用静态地图

交付标准：

1. 单房间闭环误差小于 `0.30 m`
2. 墙体不出现明显双线
3. 同一路线重复建图，形状差异可接受

### 阶段 B：定位闭环

目标：

1. 地图固定
2. 接入独立 `odom`
3. AMCL 收敛稳定

交付标准：

1. 10 次随机初始位姿手动设置，至少 `9/10` 成功收敛
2. 静止 `1 min` 位姿漂移小于 `0.10 m`
3. 5 m 低速往返后回点误差小于 `0.30-0.50 m`

### 阶段 C：全局路径 + 简化路径跟踪

目标：

1. 从 RViz 点击目标点
2. 机器人安全到达

交付标准：

1. 20 次任务成功率大于 `90%`
2. 无碰撞、无跌倒
3. 到点误差小于 `0.20 m`

### 阶段 D：局部动态避障 / DWA

目标：

1. 局部 costmap 生效
2. 能处理临时障碍

交付标准：

1. 10 次插入障碍测试成功率大于 `80%`
2. 不出现明显振荡和原地抽搐

---

## 8. 风险识别与安全分析

| 风险项 | 严重度 | 发生概率 | 触发条件 | 缓解措施 |
|--------|--------|----------|----------|----------|
| 伪 odom 干扰导航 | 高 | 高 | 未关闭现有 `publish_odom` | 导航阶段关闭该 TF 发布 |
| AMCL 发散 | 高 | 中高 | odom 跳变、地图质量差 | 先做 odom 稳定性验证，再上 AMCL |
| 地图扭曲 | 中高 | 中 | 急转、速度过快 | 建图限速，优先大弧线 |
| 雷达被腿遮挡 | 高 | 中 | 安装过低或过前 | 提高安装位，调整激光平面 |
| DWA 振荡 | 中高 | 中 | odom 噪声大、局部代价地图不稳 | 第一阶段先用简化路径跟踪 |
| 规划擦墙 | 高 | 中 | footprint 太小、inflation 太小 | 初期保守放大 footprint |
| 实机跌倒 | 高 | 中 | 原地急转、速度突变 | 限速、限加速度、吊架保护 |
| 误定位继续走 | 高 | 中 | AMCL 协方差飙升未处理 | 安全门对定位质量做硬切断 |
| 电源跌落复位 | 高 | 低中 | 舵机峰值电流大 | 主控与舵机供电隔离，共地，监测跌压 |
| TF 断链 | 高 | 中 | 多节点重复发 TF 或时序错误 | 明确 TF 责任边界，逐项验链 |

### 实机安全要求

1. 必须有急停
2. 首轮导航必须使用吊架、保护绳或软环境围挡
3. 首轮速度不得超过 `0.12 m/s`
4. 雷达、定位、TF 任一超时都必须停车
5. 未确认步态稳定前，不允许原地高速自旋

---

## 9. 依赖与包级实施建议

### 9.1 概念依赖

导航方案需要补齐的能力包括：

1. `map_server`
2. `amcl`
3. `move_base`
4. `global_planner`
5. `dwa_local_planner` 或自定义 `path_tracker`
6. `robot_localization`（有 IMU 时强烈建议）
7. 激光里程计或 scan matcher

### 9.2 Ubuntu 20.04 与 Orange Pi 22.04 的区别

若是 Ubuntu 20.04 + 官方 Noetic apt：

1. 可以优先走二进制包
2. 但仍建议先用 `apt-cache search` 确认包名

若是 Orange Pi AI Pro + Ubuntu 22.04 + ROS1 Noetic 源码编译：

1. 不要默认认为所有导航包都有现成 apt
2. 优先将导航相关包迁移到 `spotmicro_ws/src`
3. 把导航包与 `ros_noetic_ws` 基础 ROS 分层

### 9.3 对现有仓库的最小侵入改造

推荐修改策略：

1. 不大改 `spot_micro_motion_cmd`
2. 新建 `spot_micro_navigation`
3. 仅在导航上车阶段将 `spot_micro_motion_cmd.yaml` 中的 `publish_odom` 置为 `false`
4. 复用现有 `/cmd_vel`、`/stand_cmd`、`/walk_cmd`

### 9.4 模式管理器建议

导航节点不能只发 `/cmd_vel`，还需要确保机器人进入正确状态。  
建议增加 `nav_mode_manager.py`，职责如下：

1. 上电后发送一次 `/stand_cmd`
2. 确认站稳后发送一次 `/walk_cmd`
3. 导航退出或故障时发送 `/idle_cmd`

原因：

1. `spot_micro_motion_cmd` 有状态机
2. 仅发速度命令并不保证机器人已进入行走态

---

## 10. 实验设计

| 实验目标 | 验证假设 | 输入/操作 | 观测指标 | 成功标准 | 预估耗时 |
|----------|----------|-----------|----------|----------|----------|
| 雷达链路验证 | `/scan` 与 TF 正常 | 原地运行雷达与 RViz | 扫描频率、帧方向、TF 是否连续 | `scan >= 8 Hz`，TF 无断链 | 0.5 天 |
| 建图验证 | Hector 可在低速下闭环 | 遥控绕单房间一圈 | 地图形变、闭环误差 | 闭环误差 `< 0.30 m` | 1 天 |
| Odom 验证 | 独立 odom 可提供连续先验 | 直行、转弯、回点 | 轨迹平滑度、回点误差 | 5 m 回点误差 `< 0.50 m` | 1-2 天 |
| AMCL 验证 | 已知图定位可稳定收敛 | 多点初始化重复测试 | 收敛时间、静止漂移 | `10 s` 内收敛，静止漂移 `< 0.10 m/min` | 1 天 |
| 全局规划验证 | A* 可稳定给出可行路径 | RViz 多目标点下发 | 规划成功率、耗时 | 20 次成功率 `> 95%` | 0.5 天 |
| 局部跟踪验证 | 简化 tracker 能把路径变成平稳速度 | 小范围到点测试 | 到点误差、振荡、跌倒率 | 20 次 0 碰撞、0 跌倒 | 2 天 |
| 安全门验证 | 异常时可立即停车 | 手工断开 scan / TF / 定位 | 停车延迟 | `< 0.3 s` 停车 | 0.5 天 |

---

## 11. 调试路径

```text
问题定位路线图：

1. 现象观察
   记录 /scan、/tf、/tf_static、/odom、/amcl_pose、/cmd_vel、/move_base/*、rosbag

2. 假设列表（按概率排序）
   A. TF 树错误
   B. lidar 外参错误
   C. odom 连续性不足
   D. 地图质量差
   E. AMCL 参数不合适
   F. 局部跟踪器增益过大
   G. 速度安全门阈值不合理

3. 隔离验证
   A. 静止看 AMCL 是否漂
   B. 手推或低速直行看 odom 是否平滑
   C. 原地小角度转动看 yaw 是否连续
   D. 关闭局部跟踪器，只看全局路径是否合理
   E. 关闭 DWA，回到简化 tracker

4. 修复验证
   每次只改一项参数
   每项至少重复 10 次

5. 回归测试
   A. 键盘遥控
   B. 原地站立
   C. 雷达稳定输出
   D. AMCL 稳定
   E. 到点停车
```

---

## 12. 最终推荐实施顺序

如果目标是尽快得到一条能走通的链路，建议按下面的里程碑执行：

### 里程碑 1：建图跑通

1. 检查 `lidar_link` 外参
2. 用 Hector 保存一张小环境地图
3. 用 rosbag 录一段建图数据，支持离线复现

### 里程碑 2：独立 odom 跑通

1. 关闭现有伪 `odom`
2. 上激光里程计
3. 有 IMU 时再加 EKF 融合

### 里程碑 3：定位跑通

1. 固定地图
2. 启动 `map_server + AMCL`
3. 在 RViz 中反复做初始定位和回点测试

### 里程碑 4：全局路径跑通

1. 启动 `A*`
2. 在 RViz 里下发目标点
3. 仅验证路径可生成，不急着实机闭环

### 里程碑 5：简化路径跟踪闭环

1. 新增 `path_tracker`
2. 新增 `cmd_vel_safety_gate`
3. 低速到点

### 里程碑 6：局部规划增强

1. 评估是否切换 `DWA`
2. 评估是否逐步开放 `linear.y`
3. 评估动态障碍避让

---

## 13. 参考资料

1. Hector SLAM: Stefan Kohlbrecher et al., "A Flexible and Scalable SLAM System with Full 3D Motion Estimation"
2. Gmapping: Grisetti, Stachniss, Burgard, "Improved Techniques for Grid Mapping with Rao-Blackwellized Particle Filters"
3. AMCL / KLD-Sampling: Dieter Fox, "KLD-Sampling: Adaptive Particle Filters"
4. Cartographer 2D: Hess et al., "Real-Time Loop Closure in 2D LIDAR SLAM"
5. ROS1 Navigation Stack: `map_server`, `amcl`, `move_base`, `global_planner`, `dwa_local_planner`

---

## 14. 本文档给出的最终工程建议

如果只保留一句话，结论是：

**先用 Hector 把地图做稳，再单独把 odom 做对，再用 AMCL 和 A* 建完整导航链；局部控制先用简化路径跟踪器保守落地，稳定后再考虑 DWA。**
