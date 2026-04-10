# SpotMicro 雷达导航落地手册

本手册对应 `software_orangepiaipro/spot_micro_navigation/`，目标是把雷达调试、静态地图构建、AMCL 定位与 A*/Dijkstra 全局规划落到当前 SpotMicro 工程里。

## 1. 目标与范围

当前落地内容包括：

1. 雷达接入与基础调试
2. 建图：`Hector` 或 `Gmapping`
3. 定位：`AMCL`
4. 全局规划：`global_planner`，支持 A* / Dijkstra 切换
5. 局部规划：`DWA`
6. 速度安全门：`cmd_vel_safety_gate.py`
7. 机器狗模式切换：`nav_mode_manager.py`

注意：

1. 本仓库新增的是导航集成包与配置
2. 真实独立 `odom` 源仍建议由外部激光里程计或 IMU+EKF 提供
3. 若你暂时只能使用现有伪 `odom`，系统可以先跑通，但定位和规划效果会明显受限

## 2. 新增包位置

新增包位于：

- `software_orangepiaipro/spot_micro_navigation`

若在 Orange Pi 的 `spotmicro_ws` 中运行，请重新执行：

```bash
bash ~/Desktop/SpotMicro/spotMicro-Chinese/software_orangepiaipro/scripts/link_spotmicro_workspace.sh ~/Desktop/SpotMicro/spotmicro_ws
```

这样新包会被链接进 `spotmicro_ws/src`。

## 3. 依赖建议

### 3.1 Ubuntu 20.04 / 官方 Noetic apt 场景

如果你的主机是 Ubuntu 20.04，且已经启用官方 ROS Noetic apt 源，可直接安装：

```bash
sudo apt install \
  ros-noetic-rplidar-ros \
  ros-noetic-hector-mapping \
  ros-noetic-map-server \
  ros-noetic-amcl \
  ros-noetic-move-base \
  ros-noetic-global-planner \
  ros-noetic-dwa-local-planner \
  ros-noetic-gmapping
```

如需 IMU+EKF 融合 odom，再补：

```bash
sudo apt install ros-noetic-robot-localization
```

### 3.2 Orange Pi Ubuntu 22.04 / Jammy 源码编译场景

如果你当前环境是 Orange Pi + Ubuntu 22.04 + `ros_noetic_ws` 源码工作区：

1. 不要再假设 `ros-noetic-rplidar-ros`、`ros-noetic-hector-*`、`ros-noetic-rviz` 等包能从 apt 直接装好
2. `rplidar_ros`、`hector_slam`、`laser_geometry` 等请走源码路径
3. 当前仓库新增导航包已经按这个方向组织，但 Jammy 下还需要额外处理一轮编译依赖裁剪

请优先查看：

- `software_orangepiaipro/docs_cn/01_环境部署/OrangePi_Jammy_Noetic_导航编译排障.md`

说明：

1. `gmapping` 依赖 odom，强烈建议先有独立 odom 再使用
2. `hector_mapping` 对 odom 依赖更弱，更适合作为当前机器狗的首选建图方案

## 4. 雷达调试

先确认低层链路：

```bash
roslaunch rplidar_ros rplidar_a1.launch serial_port:=/dev/ttyUSB0 frame_id:=lidar_link
rostopic hz /scan
rostopic echo /scan
```

成功标准：

1. `/scan` 有稳定数据
2. 雷达帧率不低于 `8 Hz`
3. `frame_id` 为 `lidar_link`

再确认 TF：

```bash
rosrun tf tf_echo base_link lidar_link
rosrun tf view_frames
```

若 `lidar_link` 外参不对，请修改：

- `software_orangepiaipro/spot_micro_motion_cmd/config/spot_micro_motion_cmd.yaml`

关键参数：

```yaml
lidar_x_pos
lidar_y_pos
lidar_z_pos
lidar_yaw_angle
```

## 5. 建图

### 5.1 Hector 建图（推荐）

先启动底层控制与雷达，再单独启动：

```bash
roslaunch spot_micro_navigation slam_hector_mapping.launch
```

建议速度限制：

1. `linear.x <= 0.10 m/s`
2. `angular.z <= 0.20 rad/s`

保存地图：

```bash
rosrun map_server map_saver -f my_map
```

### 5.2 Gmapping 建图（有独立 odom 时再用）

```bash
roslaunch spot_micro_navigation slam_gmapping_mapping.launch
```

说明：

1. `slam_gmapping` 会读取 `/tf` 中的 `odom -> base_footprint`
2. 当前机器狗若仍使用伪 `odom`，地图可能会漂

## 6. 定位

基于已保存好的地图：

```bash
roslaunch spot_micro_navigation localization_amcl.launch map_yaml:=/path/to/my_map.yaml
```

启动后在 RViz 中：

1. 用 `2D Pose Estimate` 设初值
2. 观察 `/amcl_pose`
3. 确认 `map -> odom` 开始稳定发布

## 7. 导航

完整导航链启动：

```bash
roslaunch spot_micro_navigation navigation_astar_dwa.launch map_yaml:=/path/to/my_map.yaml
```

默认行为：

1. `AMCL` 启动
2. `move_base` 启动
3. `GlobalPlanner` 以 A* 模式运行
4. `DWAPlannerROS` 作为局部规划器
5. `cmd_vel_safety_gate.py` 将 `/cmd_vel_nav_raw` 转为安全后的 `/cmd_vel`
6. `nav_mode_manager.py` 自动向机器狗发送 `stand` 与 `walk` 事件

在 RViz 中可用：

1. `2D Pose Estimate`
2. `2D Nav Goal`

## 8. A* 与 Dijkstra 切换

默认是 A*。

若你要切到 Dijkstra：

```bash
roslaunch spot_micro_navigation navigation_astar_dwa.launch \
  map_yaml:=/path/to/my_map.yaml \
  use_dijkstra:=true
```

## 9. 与现有控制器的关系

当前 `spot_micro_motion_cmd` 订阅：

- `/cmd_vel`

新增导航包不会改这个接口，只是在中间插入：

```text
move_base -> /cmd_vel_nav_raw -> cmd_vel_safety_gate.py -> /cmd_vel
```

这样可以：

1. 在异常时强制清零速度
2. 做速度限幅和限加速度
3. 减少规划器抖动直接传给步态层

## 10. 当前默认参数含义

### 10.1 全局规划

文件：

- `spot_micro_navigation/config/global_planner.yaml`

默认：

1. A*
2. `allow_unknown: true`
3. 机器人 footprint 先按保守矩形配置

### 10.2 局部规划

文件：

- `spot_micro_navigation/config/dwa_local_planner.yaml`

默认限速：

1. `max_vel_x: 0.12`
2. `max_vel_y: 0.00`
3. `max_rot_vel: 0.20`

### 10.3 安全门

文件：

- `spot_micro_navigation/config/safety_gate.yaml`

默认保护：

1. `scan_timeout: 0.30`
2. 正前方 `0.35 m` 内障碍则停车
3. `AMCL` 协方差过大则停车

## 11. 当前最重要的工程提醒

### 11.1 关于 odom

当前低层配置里：

- `software_orangepiaipro/spot_micro_motion_cmd/config/spot_micro_motion_cmd.yaml`

默认：

```yaml
publish_odom: true
```

这会发布伪 `odom`。

建议：

1. 建图演示阶段可以先保留
2. 正式 AMCL + move_base 导航阶段，最好切换到独立 odom 源
3. 一旦外部 odom 节点开始发布 `odom -> base_footprint`，必须避免 TF 冲突

### 11.2 关于 Gmapping

`gmapping` 不是不能用，而是：

1. 它比 `hector_mapping` 更依赖 odom
2. 当前机器狗如果没有独立 odom，效果会明显不稳

### 11.3 关于 DWA

当前参数是保守值，优先保证：

1. 不跌倒
2. 不擦墙
3. 不抖动

## 12. 建议的实际启动顺序

### 阶段 A：雷达与底层控制

1. `roscore`
2. `roslaunch spot_micro_motion_cmd motion_cmd.launch`
3. `roslaunch rplidar_ros rplidar_a1.launch serial_port:=/dev/ttyUSB0 frame_id:=lidar_link`

### 阶段 B：建图

4. `roslaunch spot_micro_navigation slam_hector_mapping.launch`
5. 手动遥控建图
6. `rosrun map_server map_saver -f my_map`

### 阶段 C：定位与导航

4. `roslaunch spot_micro_navigation navigation_astar_dwa.launch map_yaml:=/path/to/my_map.yaml`
5. RViz 中先 `2D Pose Estimate`
6. 再 `2D Nav Goal`

## 13. 当前版本的边界

本次落地已经把：

1. 包结构
2. launch
3. AMCL 配置
4. A*/Dijkstra 配置
5. DWA 配置
6. 安全门
7. 模式管理

补进仓库。

但还没有在仓库内额外实现：

1. 独立激光里程计节点
2. IMU + EKF 融合节点
3. Cartographer 配置

如果下一步继续推进，优先建议补：

1. 独立 odom 链
2. RViz 导航配置优化
3. 导航专用调试脚本
