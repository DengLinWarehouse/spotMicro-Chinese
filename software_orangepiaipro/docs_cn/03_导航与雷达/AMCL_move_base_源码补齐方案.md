# AMCL 与 move_base 源码补齐方案

本文用于承接当前已完成的链路：

```text
RPLidar -> /scan -> TF -> Hector -> /map
```

目标是继续补齐 ROS1 Noetic 导航运行栈，使当前 SpotMicro 项目具备以下能力：

1. `AMCL`：在静态地图上进行激光定位
2. `map_server`：加载与保存静态地图
3. `move_base`：整合全局规划与局部规划
4. `global_planner`：A* / Dijkstra 全局路径
5. `dwa_local_planner`：局部速度规划

适用环境：

- 主控：Orange Pi AI Pro
- OS：Ubuntu 22.04.3 LTS
- ROS：ROS1 Noetic（源码工作区）
- 基础工作区：`~/Desktop/SpotMicro/ros_noetic_ws`
- 业务工作区：`~/Desktop/SpotMicro/spotmicro_ws`

---

## 1. 结论先行

当前系统已经能完成雷达建图，但还不能进入 AMCL 和导航闭环，直接原因是这些包还不存在：

- `amcl`
- `move_base`
- `global_planner`
- `dwa_local_planner`
- `map_server`

经确认，这些包在 ROS1 Noetic 中属于同一个源码仓库：

- `navigation`

因此当前推荐路线非常明确：

```text
把 navigation 及其缺失的配套 ROS 仓库补到 ros_noetic_ws/src
-> 用 rosdep 补系统依赖
-> 先编译 ros_noetic_ws
-> 再回到 spotmicro_ws 做运行验证
```

主选方案：

- **把 `navigation` 放入 `ros_noetic_ws/src`**

不推荐方案：

- 把 `amcl`、`move_base` 等单独拆到 `spotmicro_ws/src`

原因：

1. `navigation` 属于通用 ROS 导航基础栈，不是 SpotMicro 专属业务包
2. 放进基础工作区更符合“基础能力 / 业务 overlay”分层
3. 后续你若还有别的机器人工作区，也可直接复用

---

## 2. 当前状态与缺口

### 2.1 已经打通的部分

已实际验证：

1. `rplidar_ros`
2. `hector_mapping`
3. `/scan`
4. `/map`
5. `/slam_out_pose`
6. `odom -> base_footprint -> base_link -> lidar_link`

### 2.2 仍缺失的部分

通过 `rospack find` 已确认缺失：

```bash
rospack find amcl
rospack find move_base
```

因此当前不能做：

1. 静态地图定位
2. `2D Pose Estimate`
3. `2D Nav Goal`
4. 全局规划 + DWA 局部规划闭环

---

## 3. 技术路线对比

| 方案 | 原理概要 | 适用条件 | 性能预期 | 实现复杂度 | 调试难度 | 实机落地风险 |
| --- | --- | --- | --- | --- | --- | --- |
| 方案 A：补整个 `navigation` 仓库 | 一次性引入 `amcl`、`map_server`、`move_base`、`global_planner`、`dwa_local_planner` 等完整导航运行栈 | 当前最推荐 | 一次性补齐后续定位与导航主链 | 中 | 中 | 低 |
| 方案 B：只手动挑几个包 | 手动拆分部分子包复制进工作区 | 理论可行，但不推荐 | 容易遗漏内部依赖 | 高 | 高 | 中 |

### 3.1 推荐

**推荐方案 A。**

推荐理由：

1. `amcl / move_base / map_server / global_planner / dwa_local_planner` 本就属于同一个官方仓库
2. 一次性补齐内部依赖更稳
3. 减少后续“缺一个子包再补一个”的碎片化排障

### 3.2 方案 A 的失效条件

该方案会在以下场景受阻：

1. `navigation` 的 `noetic-devel` 在 Jammy 上出现新的编译兼容问题
2. 基础工作区 `ros_noetic_ws` 里还缺某些通用底层依赖
3. `rosdep` 解析到的系统依赖在当前 apt 源中仍不完整

但总体风险仍明显低于方案 B。

---

## 4. 建议的源码补齐步骤

### 4.1 进入基础工作区源码目录

```bash
cd ~/Desktop/SpotMicro/ros_noetic_ws/src
```

### 4.2 拉取官方 `navigation` 仓库与配套依赖仓库

若目录不存在：

```bash
git clone -b noetic-devel https://github.com/ros-planning/navigation.git
git clone -b ros1 https://github.com/ros-planning/navigation_msgs.git
git clone -b noetic-devel https://github.com/ros/diagnostics.git
git clone -b noetic-devel https://github.com/ros/rosbag_migration_rule.git
```

若目录已存在并怀疑版本不对：

```bash
cd ~/Desktop/SpotMicro/ros_noetic_ws/src/navigation
git fetch --all --prune
git checkout noetic-devel
git pull --ff-only
```

对应缺口关系如下：

| 缺失包 | 对应源码仓库 |
| --- | --- |
| `map_msgs`、`move_base_msgs` | `navigation_msgs` |
| `diagnostic_updater` | `diagnostics` |
| `rosbag_migration_rule` | `rosbag_migration_rule` |

### 4.3 回到基础工作区并补系统依赖

```bash
cd ~/Desktop/SpotMicro/ros_noetic_ws
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
rosdep install --from-paths src --ignore-src -r -y --rosdistro noetic
```

注意：

1. 若 `rosdep` 仍提示 `map_msgs` / `move_base_msgs` / `diagnostic_updater` / `rosbag_migration_rule` 无法解析，先不要继续编译，说明上述配套源码仓库仍未补齐
2. 若只剩 `python3-catkin-pkg-modules`、`python3-rosdep-modules` 之类 Jammy 中不存在的系统包错误，而你本机 `catkin_make`、`rosdep` 已可正常工作，则通常可以继续编译

### 4.4 Jammy 上常见的两个剩余问题

#### 问题 A：`diagnostic_common_diagnostics: [hddtemp] defined as "not available"`

这说明：

- `diagnostics` 仓库里的 `diagnostic_common_diagnostics` 子包依赖 `hddtemp`
- 但 Jammy 上该系统包通常不可用

对当前 SpotMicro 导航任务，这个子包不是导航主链关键包，但**不建议长期直接 `CATKIN_IGNORE` 它**，因为这样会让 `diagnostics` 元包在依赖解析时继续报：

```text
diagnostics: Cannot locate rosdep definition for [diagnostic_common_diagnostics]
```

当前更实用的做法是：

1. 保留 `diagnostic_common_diagnostics` 源码
2. 接受 `hddtemp` 在 Jammy 上不可用的 rosdep 报警
3. 在确认其它核心依赖补齐后，直接继续 `catkin_make`

#### 问题 B：`costmap_2d: Cannot locate rosdep definition for [tf2_sensor_msgs]`

这说明当前 `geometry2` 源码中缺少 `tf2_sensor_msgs` 子包。

可用官方 `geometry2` 临时补齐：

```bash
cd ~/Desktop/SpotMicro/ros_noetic_ws/src
git clone -b noetic-devel https://github.com/ros/geometry2.git geometry2_full
cp -r ~/Desktop/SpotMicro/ros_noetic_ws/src/geometry2_full/tf2_sensor_msgs \
      ~/Desktop/SpotMicro/ros_noetic_ws/src/geometry2/
rm -rf ~/Desktop/SpotMicro/ros_noetic_ws/src/geometry2_full
```

如果你之前已经给 `diagnostic_common_diagnostics` 加了 `CATKIN_IGNORE`，先撤销：

```bash
rm -f ~/Desktop/SpotMicro/ros_noetic_ws/src/diagnostics/diagnostic_common_diagnostics/CATKIN_IGNORE
```

然后再次执行：

```bash
cd ~/Desktop/SpotMicro/ros_noetic_ws
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
rosdep install --from-paths src --ignore-src -r -y --rosdistro noetic
```

### 4.4 编译基础工作区

```bash
cd ~/Desktop/SpotMicro/ros_noetic_ws
conda deactivate 2>/dev/null || true
unset PYTHONPATH
unset PYTHONHOME
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
catkin_make -DCATKIN_ENABLE_TESTING=OFF -DPYTHON_EXECUTABLE=/usr/bin/python3
```

### 4.5 验证关键导航包是否可见

```bash
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
rospack find amcl
rospack find map_server
rospack find move_base
rospack find global_planner
rospack find dwa_local_planner
```

期望全部返回路径。

### 4.6 再切回 SpotMicro overlay 验证

```bash
cd ~/Desktop/SpotMicro/spotmicro_ws
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
source ~/Desktop/SpotMicro/spotmicro_ws/devel/setup.bash
rospack find spot_micro_navigation
```

必要时重新编译 overlay：

```bash
cd ~/Desktop/SpotMicro/spotmicro_ws
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
catkin_make -DCATKIN_ENABLE_TESTING=OFF -DPYTHON_EXECUTABLE=/usr/bin/python3
```

---

## 5. 运行验证顺序

### 阶段 A：先完成地图保存

在 Hector 地图满意后，先保存地图：

```bash
cd ~/Desktop/SpotMicro/spotmicro_ws
conda deactivate 2>/dev/null || true
unset PYTHONPATH
unset PYTHONHOME
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
source ~/Desktop/SpotMicro/spotmicro_ws/devel/setup.bash
mkdir -p ~/Desktop/SpotMicro/maps
cd ~/Desktop/SpotMicro/maps
rosrun map_server map_saver -f hector_map_$(date +%Y%m%d_%H%M%S)
```

### 阶段 B：先测 AMCL

在 `navigation` 编译完成后，可先做：

```bash
roslaunch spot_micro_navigation localization_amcl.launch map_yaml:=/path/to/hector_map.yaml
```

检查：

```bash
rostopic echo -n 1 /amcl_pose
```

### 阶段 C：再测完整导航

```bash
roslaunch spot_micro_navigation navigation_astar_dwa.launch map_yaml:=/path/to/hector_map.yaml
```

再检查：

```bash
rostopic list | grep -E "move_base|cmd_vel|amcl"
```

---

## 6. 风险识别

| 风险项 | 严重度 | 发生概率 | 触发条件 | 缓解措施 |
| --- | --- | --- | --- | --- |
| `navigation` 继续出现 Jammy 编译兼容问题 | 中 | 中 | 编译到 `move_base` / `costmap_2d` 等子包时失败 | 逐包排障，优先保留 `noetic-devel` 官方分支 |
| `rosdep` 无法完全补齐系统依赖 | 中 | 中 | apt 源不完整或 ARM 平台包缺失 | 记录缺包名，按系统包逐项补装 |
| `amcl` 可运行但定位抖动 | 高 | 高 | 当前 `odom` 仍较弱 | 后续补真实 odom 源或 IMU+融合链 |
| `move_base` 可起但局部规划不稳 | 高 | 高 | 四足底盘与轮式底盘模型差异大，`cmd_vel` 响应滞后 | 保守限速、启用安全门、逐项降参数 |
| 使用 Hector 地图直接导航时闭环精度不足 | 中 | 中 | 建图质量一般、回环误差偏大 | 先做小环境验证，必要时重建地图 |

---

## 7. 当前推荐参数与验证标准

### 7.1 建图阶段

- `linear.x <= 0.10 m/s`
- `angular.z <= 0.20 rad/s`

### 7.2 AMCL 阶段

先不追求高速，只追求可定位：

- 站立初始化
- `2D Pose Estimate` 后原地观察
- 机器人小范围前后移动，观察姿态是否连续

### 7.3 导航阶段

建议维持保守速度：

- `max_vel_x <= 0.12 m/s`
- `max_rot_vel <= 0.20 rad/s`

成功标准建议：

1. `AMCL` 初始定位后不持续跳变
2. `2D Nav Goal` 可稳定生成路径
3. `/cmd_vel` 输出无明显高频抖动
4. 四足步态执行过程中不明显左右摆头或原地乱修正

---

## 8. 当前不推荐立即做的事

1. 不建议在 `amcl` / `move_base` 还没补齐前就讨论 DWA 细调
2. 不建议在 `odom` 仍较弱时就追求大范围复杂导航
3. 不建议此时切换到 `gmapping` 作为主建图方案
4. 不建议同时做“补导航栈”和“改底盘控制器”两件大事

当前正确顺序应是：

```text
Hector 地图可用
-> navigation 源码补齐
-> AMCL 可定位
-> move_base 可出路径
-> 再做 DWA/安全门/步态联调
```

---

## 9. 推荐的下一步执行清单

### 9.1 代码与依赖

1. 在 `ros_noetic_ws/src` 拉取 `navigation`
2. 运行 `rosdep install`
3. 编译 `ros_noetic_ws`
4. 验证 `amcl / move_base / map_server / global_planner / dwa_local_planner`

### 9.2 运行链

1. 保存 Hector 地图
2. 启动 `localization_amcl.launch`
3. 做 `2D Pose Estimate`
4. 观察 `/amcl_pose`
5. 再启动 `navigation_astar_dwa.launch`

---

## 10. 参考来源

本方案主要基于以下官方/主仓库来源整理：

1. ROS Index：`navigation` 仓库概览  
   https://index.ros.org/r/navigation/
2. ROS Index：`move_base` 包概览  
   https://index.ros.org/p/move_base/
3. ROS Index：`map_server` 包概览  
   https://index.ros.org/p/map_server
4. 官方源码仓库：`ros-planning/navigation`  
   https://github.com/ros-planning/navigation.git
