# 无 RViz 纯命令行导航测试手册

## 1. 文档目的

本文档用于在 **没有 RViz 图形界面** 的情况下，仅通过 SSH 终端和命令行工具，完成 SpotMicro 导航链路的验证。适用于以下场景：

- Orange Pi 通过 SSH 远程登录
- 当前环境没有桌面 GUI
- 暂时不方便使用 RViz 的 `2D Pose Estimate` 和 `2D Nav Goal`
- 希望先验证导航链路本身是否打通

本文档默认你已经具备以下基础条件：

- `rplidar_ros` 可正常启动
- `spot_micro_motion_cmd` 可正常启动
- 已经成功保存 Hector 地图
- 已经成功编译并可找到：
  - `map_server`
  - `amcl`
  - `move_base`
  - `global_planner`
  - `dwa_local_planner`

---

## 2. 适用地图文件

如果你沿用了当前联调结果，实际保存出来的地图文件为：

- `/home/HwHiAiUser/Desktop/SpotMicro/maps/hector_map_20260409_111304.yaml`

后续命令中的 `map_yaml:=...`，可以直接使用这个路径。若以后重新保存了新地图，请替换成新的实际文件路径。

---

## 3. 纯命令行导航测试的总体思路

无 RViz 测试的核心流程是：

1. 启动 `roscore`
2. 启动 `rplidar_ros`
3. 启动 `spot_micro_motion_cmd`
4. 启动完整导航：
   - `map_server`
   - `amcl`
   - `move_base`
   - `cmd_vel_safety_gate`
   - `nav_mode_manager`
5. 命令行发布初始位姿 `/initialpose`
6. 命令行发布导航目标 `/move_base_simple/goal`
7. 观察：
   - `/amcl_pose`
   - `/move_base/status`
   - `/cmd_vel_nav_raw`
   - `/cmd_vel`

如果 `/cmd_vel_nav_raw` 和 `/cmd_vel` 开始出现合理的速度输出，且机器人实际做出对应动作，就说明导航链路已经基本打通。

---

## 4. 测试前安全要求

在进行第一次实机导航测试前，务必满足以下要求：

- 测试环境前方空旷，无台阶、桌脚、电线、狭窄缝隙
- 第一次测试目标距离很近，建议 `0.1 ~ 0.2 m`
- 线速度保持较低，建议不超过 `0.10 ~ 0.12 m/s`
- 角速度保持较低，建议不超过 `0.20 rad/s`
- 旁边有人随时准备扶稳机体或切断动力
- 测试开始前，确认当前没有运行 Hector 建图

特别强调：

- **做静态地图导航时，必须关闭 Hector**
- 否则 `Hector` 与 `AMCL` 会同时处理地图，容易造成定位与导航异常

---

## 5. 每个终端通用环境初始化

建议每个新终端都先执行：

```bash
cd ~/Desktop/SpotMicro/spotmicro_ws
conda deactivate 2>/dev/null || true
unset PYTHONPATH
unset PYTHONHOME
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
source ~/Desktop/SpotMicro/spotmicro_ws/devel/setup.bash
```

这样可以避免 Conda、Python 环境变量以及工作区 overlay 顺序影响 ROS 工具行为。

---

## 6. 启动顺序

建议使用 5 个终端分别执行。

### 终端 A：启动 roscore

```bash
cd ~/Desktop/SpotMicro/spotmicro_ws
conda deactivate 2>/dev/null || true
unset PYTHONPATH
unset PYTHONHOME
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
source ~/Desktop/SpotMicro/spotmicro_ws/devel/setup.bash
roscore
```

### 终端 B：启动 RPLidar

```bash
cd ~/Desktop/SpotMicro/spotmicro_ws
conda deactivate 2>/dev/null || true
unset PYTHONPATH
unset PYTHONHOME
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
source ~/Desktop/SpotMicro/spotmicro_ws/devel/setup.bash
roslaunch rplidar_ros rplidar_a1.launch serial_port:=/dev/ttyUSB0 frame_id:=lidar_link
```

### 终端 C：启动机器人底层运动节点

```bash
cd ~/Desktop/SpotMicro/spotmicro_ws
conda deactivate 2>/dev/null || true
unset PYTHONPATH
unset PYTHONHOME
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
source ~/Desktop/SpotMicro/spotmicro_ws/devel/setup.bash
roslaunch spot_micro_motion_cmd motion_cmd.launch
```

### 终端 D：启动完整导航

注意：

- 这里不要再单独启动 `localization_amcl.launch`
- 也不要启动 `slam_hector_mapping.launch`
- 直接启动完整导航 launch

```bash
cd ~/Desktop/SpotMicro/spotmicro_ws
conda deactivate 2>/dev/null || true
unset PYTHONPATH
unset PYTHONHOME
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
source ~/Desktop/SpotMicro/spotmicro_ws/devel/setup.bash
roslaunch spot_micro_navigation navigation_astar_dwa.launch map_yaml:=/home/HwHiAiUser/Desktop/SpotMicro/maps/hector_map_20260409_111304.yaml
```

### 终端 E：导航链基础检查

```bash
cd ~/Desktop/SpotMicro/spotmicro_ws
conda deactivate 2>/dev/null || true
unset PYTHONPATH
unset PYTHONHOME
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
source ~/Desktop/SpotMicro/spotmicro_ws/devel/setup.bash
rostopic list | grep -E "move_base|cmd_vel|amcl|scan|map"
```

如果以下关键话题都存在，说明导航主链已启动：

- `/scan`
- `/map`
- `/amcl_pose`
- `/particlecloud`
- `/cmd_vel_nav_raw`
- `/cmd_vel`
- `/move_base/status`
- `/move_base_simple/goal`

---

## 7. 先检查 AMCL 当前位姿

在正式发目标前，先看当前定位输出是否存在：

```bash
rostopic echo -n 1 /amcl_pose
```

如果能看到：

- `header`
- `pose.pose.position`
- `pose.pose.orientation`
- `covariance`

说明 AMCL 已经在工作。

若此时位置明显接近机器人真实所在位置，后续导航成功率会更高。

---

## 8. 命令行发布初始位姿 `/initialpose`

无 RViz 环境下，`2D Pose Estimate` 要用命令行手动替代。

下面是推荐的初始位姿发布命令：

```bash
rostopic pub -1 /initialpose geometry_msgs/PoseWithCovarianceStamped "header:
  frame_id: 'map'
pose:
  pose:
    position:
      x: -0.06
      y: 0.03
      z: 0.0
    orientation:
      x: 0.0
      y: 0.0
      z: 0.0
      w: 1.0
  covariance: [0.05, 0, 0, 0, 0, 0,
               0, 0.05, 0, 0, 0, 0,
               0, 0, 0, 0, 0, 0,
               0, 0, 0, 0, 0, 0,
               0, 0, 0, 0, 0, 0,
               0, 0, 0, 0, 0, 0.03]"
```

### 说明

- `frame_id` 必须是 `map`
- `x / y` 建议先参考当前 `amcl_pose` 的数值
- `orientation` 第一次可以先设为朝向 0
- `covariance` 不宜过大，也不宜为全 0

发布后可以再次查看：

```bash
rostopic echo -n 3 /amcl_pose
```

如果三次输出位置比较接近，说明定位已经相对稳定。

---

## 9. 命令行发布导航目标 `/move_base_simple/goal`

无 RViz 环境下，`2D Nav Goal` 要用命令行替代。

### 9.1 推荐首次测试目标

第一次不要发远目标，建议只发一个很近的小目标，例如：

- 当前位置附近前方 `0.1 ~ 0.2 m`

例如，若当前机器人在：

- `x ≈ -0.06`
- `y ≈ 0.03`

则可以先发一个小目标：

```bash
rostopic pub -1 /move_base_simple/goal geometry_msgs/PoseStamped "header:
  frame_id: 'map'
pose:
  position:
    x: 0.10
    y: 0.03
    z: 0.0
  orientation:
    x: 0.0
    y: 0.0
    z: 0.0
    w: 1.0"
```

### 9.2 更稳妥的建议

如果你担心一下跳太远，可以先只改小一点，例如：

```bash
rostopic pub -1 /move_base_simple/goal geometry_msgs/PoseStamped "header:
  frame_id: 'map'
pose:
  position:
    x: 0.02
    y: 0.03
    z: 0.0
  orientation:
    x: 0.0
    y: 0.0
    z: 0.0
    w: 1.0"
```

第一次测试的核心目的不是跑远，而是验证：

- 规划器能否接收目标
- 局部规划器能否生成轨迹
- 安全门是否会放行
- 机器人底层是否会响应 `/cmd_vel`

---

## 10. 发目标后观察哪些话题

### 10.1 查看导航状态

```bash
rostopic echo -n 1 /move_base/status
```

如果看到 Goal 状态变化，说明 `move_base` 已经收到目标。

### 10.2 查看全局/局部规划输出

```bash
rostopic echo -n 5 /cmd_vel_nav_raw
```

如果这里开始出现非零速度，说明：

- 全局规划器和局部规划器已经开始工作

### 10.3 查看安全门后的最终速度

```bash
rostopic echo -n 5 /cmd_vel
```

如果这里也有非零输出，说明：

- 安全门没有拦截
- 速度指令已经进入底层运动控制链

### 10.4 查看定位是否持续更新

```bash
rostopic echo -n 5 /amcl_pose
```

如果位置持续更新且变化方向合理，说明：

- AMCL 在导航过程中仍然能正常工作

---

## 11. 如何判断导航链已经打通

如果发出导航目标后同时满足以下现象，可以认为导航主链已经基本打通：

1. `/move_base/status` 出现目标状态
2. `/cmd_vel_nav_raw` 出现非零速度
3. `/cmd_vel` 也出现非零速度
4. 机器人实际向目标方向有小范围移动
5. `/amcl_pose` 在移动过程中持续更新

如果 1~3 成立但机器人不动，优先怀疑底层执行链或安全门配置。

如果 1 成立但 2 不成立，优先怀疑规划器、代价地图、目标点不可达、定位不稳定。

如果 2 成立但 3 不成立，优先怀疑：

- `cmd_vel_safety_gate`
- `/scan` 超时
- AMCL 协方差过大
- 前方障碍判定触发

---

## 12. 常见问题与排查方法

### 问题 1：`/cmd_vel_nav_raw` 没有消息

可能原因：

- 还没发 `/move_base_simple/goal`
- 目标点无效或太远
- `move_base` 没正常收到目标
- AMCL 没稳定

优先检查：

```bash
rostopic echo -n 1 /move_base/status
rostopic echo -n 3 /amcl_pose
```

### 问题 2：`/cmd_vel_nav_raw` 有值，但 `/cmd_vel` 为 0

可能原因：

- 安全门触发
- `/scan` 中断或超时
- 前方被判定有障碍
- 定位协方差超阈值

优先检查：

```bash
rostopic hz /scan
rostopic echo -n 1 /amcl_pose
rostopic echo -n 5 /cmd_vel
```

### 问题 3：`move_base/status` 有目标，但机器人不动

可能原因：

- `spot_micro_motion_cmd` 没收到 `/cmd_vel`
- 运动模式没有切到 walk
- 底层控制链未正确接入导航速度

优先检查：

```bash
rostopic echo -n 5 /cmd_vel
rostopic list | grep -E "idle_cmd|stand_cmd|walk_cmd"
```

### 问题 4：AMCL 定位漂移很大

可能原因：

- 初始位姿给得太偏
- 雷达安装方向与 TF 不一致
- 机器人抖动大
- 地图质量不够好

优先处理：

- 重新发布 `/initialpose`
- 确认 `lidar_yaw_angle`
- 检查地图是否存在明显变形

### 问题 5：costmap transform timeout

可能原因：

- TF 时间戳不同步
- `odom -> base_footprint` 更新不连续
- 同时运行了 Hector 和 AMCL

优先检查：

```bash
rosnode list | grep -E "hector|amcl|move_base"
```

并确保：

- 导航阶段不要运行 `slam_hector_mapping.launch`

---

## 13. 推荐的最小闭环测试流程

如果只想做一次最小验证，建议按下面顺序执行：

### 步骤 1：启动基础节点

- `roscore`
- `rplidar_ros`
- `spot_micro_motion_cmd`
- `navigation_astar_dwa.launch`

### 步骤 2：确认导航节点存在

```bash
rostopic list | grep -E "move_base|cmd_vel|amcl|scan|map"
```

### 步骤 3：确认定位存在

```bash
rostopic echo -n 1 /amcl_pose
```

### 步骤 4：发布一次初始位姿

```bash
rostopic pub -1 /initialpose geometry_msgs/PoseWithCovarianceStamped "header:
  frame_id: 'map'
pose:
  pose:
    position:
      x: -0.06
      y: 0.03
      z: 0.0
    orientation:
      x: 0.0
      y: 0.0
      z: 0.0
      w: 1.0
  covariance: [0.05, 0, 0, 0, 0, 0,
               0, 0.05, 0, 0, 0, 0,
               0, 0, 0, 0, 0, 0,
               0, 0, 0, 0, 0, 0,
               0, 0, 0, 0, 0, 0,
               0, 0, 0, 0, 0, 0.03]"
```

### 步骤 5：发布一个很近的导航目标

```bash
rostopic pub -1 /move_base_simple/goal geometry_msgs/PoseStamped "header:
  frame_id: 'map'
pose:
  position:
    x: 0.02
    y: 0.03
    z: 0.0
  orientation:
    x: 0.0
    y: 0.0
    z: 0.0
    w: 1.0"
```

### 步骤 6：查看结果

```bash
rostopic echo -n 1 /move_base/status
rostopic echo -n 5 /cmd_vel_nav_raw
rostopic echo -n 5 /cmd_vel
```

---

## 14. 停止测试的方法

如果机器人动作异常或测试需要立即停止，可以按以下顺序处理：

### 方法 1：直接 Ctrl+C 停掉导航 launch

在运行 `navigation_astar_dwa.launch` 的终端按：

```bash
Ctrl+C
```

### 方法 2：人工发布零速度

```bash
rostopic pub -1 /cmd_vel geometry_msgs/Twist "linear:
  x: 0.0
  y: 0.0
  z: 0.0
angular:
  x: 0.0
  y: 0.0
  z: 0.0"
```

### 方法 3：停掉底层运动节点

在 `motion_cmd.launch` 终端按：

```bash
Ctrl+C
```

若出现明显危险，以“停底层运动节点”优先。

---

## 15. 本手册适用结论

通过本文档，即使没有 RViz，也可以完成以下验证：

- `AMCL` 是否正常定位
- `move_base` 是否正常接收目标
- `GlobalPlanner` 与 `DWA` 是否开始输出速度
- `cmd_vel_safety_gate` 是否放行
- `spot_micro_motion_cmd` 是否收到最终速度指令

因此，本文档可作为：

- SSH 远程调试手册
- 无显示器环境导航联调手册
- 现场快速验证导航链路的标准操作流程

---

## 16. 相关文档

- `software_orangepiaipro/docs_cn/03_导航与雷达/SpotMicro_雷达建图与AMCL定位阶段总结.md`
- `software_orangepiaipro/docs_cn/03_导航与雷达/RPLidar_Hector_实操问题复盘.md`
- `software_orangepiaipro/docs_cn/03_导航与雷达/AMCL_move_base_源码补齐方案.md`
- `software_orangepiaipro/docs_cn/03_导航与雷达/navigation_stack_runbook.md`
- `temp/命令缓存.txt`

本文档建议与阶段总结文档配合使用：

- 阶段总结文档用于回顾问题与解决思路
- 本手册用于直接执行无 RViz 的命令行导航测试
