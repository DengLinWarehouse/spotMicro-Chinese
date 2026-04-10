# SpotMicro 雷达建图与 AMCL 定位阶段总结

## 1. 总体结论

本阶段已经完成 SpotMicro 从雷达接入、TF 联调、Hector 建图、静态地图保存，到 AMCL 静态地图定位的完整闭环验证。当前已经确认打通的链路如下：

- `RPLidar -> /scan`
- `TF(base_footprint / base_link / lidar_link / odom)`
- `Hector SLAM -> /map /slam_out_pose`
- `map_server -> 静态地图加载`
- `AMCL -> /amcl_pose`

这意味着系统已经从“机器人底层运动控制可用”，推进到“具备静态地图定位与导航联调条件”的阶段。当前剩余的核心工作，是继续完成：

- `AMCL -> move_base -> GlobalPlanner(A*) -> DWA -> /cmd_vel_nav_raw -> /cmd_vel`

也就是最终导航目标下发与实机运动验证。

---

## 2. 硬件与基础环境阶段

本次实际验证的平台环境为：

- 机器人平台：SpotMicro
- 主控平台：Orange Pi AI Pro
- 系统环境：Ubuntu 22.04.3 LTS (Jammy)
- ROS 环境：ROS1 Noetic 源码工作区
- 基础工作区：`~/Desktop/SpotMicro/ros_noetic_ws`
- 叠加工作区：`~/Desktop/SpotMicro/spotmicro_ws`

已确认可正常工作的基础组件包括：

- `spot_micro_motion_cmd`
- `i2cpwm_board`
- `rplidar_ros`
- `hector_slam`
- `spot_micro_navigation`

底层运动链路运行正常，`motion_cmd.launch` 能够正常启动，PCA9685/I2C 总线可访问，12 路舵机参数均能成功加载。系统中 `publish_odom: True` 已开启，说明当前可以提供基础里程计信息供 SLAM 与导航模块使用。

---

## 3. 雷达驱动安装与调试过程

### 3.1 驱动接入情况

本次使用的激光雷达为 `RPLidar A1`，串口设备为：

- `/dev/ttyUSB0`

最终确认可用的启动命令为：

```bash
roslaunch rplidar_ros rplidar_a1.launch serial_port:=/dev/ttyUSB0 frame_id:=lidar_link
```

启动后日志显示：

- 雷达型号识别正常
- 序列号读取正常
- 固件版本读取正常
- `RPLidar health status : OK`
- 采样模式与频率正常

说明雷达硬件连接与串口访问链路已打通。

### 3.2 实际遇到的问题与处理方法

#### 问题 1：`rplidar_ros` 在 Jammy + Noetic 源码环境中存在编译兼容性问题

在 Ubuntu 22.04 + ROS Noetic 源码环境下，旧版 ROS 包经常会遇到编译器标准或第三方库兼容问题。本次 `rplidar_ros` 需要在 `CMakeLists.txt` 中补充 C++17 编译选项，才可顺利编译通过。

处理思路：

- 在 `spotmicro_ws/src/rplidar_ros/CMakeLists.txt` 中增加：

```cmake
add_compile_options(-std=c++17)
```

这样做的目的，是解决 Jammy 环境下新版编译器/依赖库的兼容性问题。

#### 问题 2：ROS Python 工具受到 Conda / Python 环境污染

在实际操作中，多次出现 ROS Python 工具可能被 Conda 环境、`PYTHONPATH`、`PYTHONHOME` 干扰的问题。此类问题会导致：

- `rostopic`
- `roslaunch`
- `rosrun`
- `rosdep`

等命令出现异常行为或依赖错误。

处理思路：

每次开启新终端，统一执行：

```bash
conda deactivate 2>/dev/null || true
unset PYTHONPATH
unset PYTHONHOME
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
source ~/Desktop/SpotMicro/spotmicro_ws/devel/setup.bash
```

这一套动作已经成为当前环境下的标准初始化流程。

#### 问题 3：命令中误写字面量 `...`

在调试过程中，曾出现过：

```bash
roslaunch rplidar_ros rplidar_a1.launch ...
```

这类命令。由于 `roslaunch` 会把 `...` 当成真实文件参数处理，因此会直接报错：

- 输入文件不存在

处理思路：

- 所有命令必须写真实参数
- 文档中的省略号不能直接复制到终端执行

---

## 4. TF 链与雷达安装位姿联调

导航与 SLAM 是否稳定，TF 是否正确是决定性因素。本阶段已确认以下 TF 关系可用：

- `odom -> base_footprint`
- `base_footprint -> base_link`
- `base_link -> lidar_link`

同时，雷达安装位姿参数已成功加载：

- `lidar_x_pos: 0.045`
- `lidar_y_pos: 0.0`
- `lidar_z_pos: 0.085`
- `lidar_yaw_angle: 180`

雷达最终统一使用：

- `frame_id = lidar_link`

这一步的意义在于：

- 如果雷达 frame 配置错误，`/scan` 虽然存在，但 SLAM 会漂移
- 如果安装方向与 yaw 配置不一致，地图会出现镜像、倒置或扫描方向错误
- 如果 `base_link` 与 `base_footprint` 链路缺失，导航代价地图与定位都会失败

本次通过话题和 TF 联调，确认了激光数据、机器人本体坐标系、里程计坐标系三者之间的关系已经具备正常运行条件。

---

## 5. Hector 建图阶段问题与修复

### 5.1 启动文件参数作用域问题

在最初版本中，`spot_micro_navigation` 里的 Hector / Gmapping 启动文件虽然写了：

```xml
<rosparam command="load" file="..." />
```

但参数没有正确加载到目标节点的私有命名空间，导致节点运行时并未真正使用配置文件内的参数。

受影响文件包括：

- `software_orangepiaipro/spot_micro_navigation/launch/slam_hector_mapping.launch`
- `software_orangepiaipro/spot_micro_navigation/launch/slam_gmapping_mapping.launch`

处理思路：

- 将 `<rosparam ...>` 放入对应 `<node>` 标签内部
- 使参数按节点私有命名空间正确加载

### 5.2 修复结果验证

修复后，从 Hector 日志中可以明确看到配置已生效，例如：

- `p_map_update_distance_threshold_: 0.250000`
- `p_map_update_angle_threshold_: 0.050000`

这说明 Hector 的 YAML 配置文件已经被正确读取，而不是退回到默认参数运行。

---

## 6. Hector 建图运行结果

Hector 建图最终可以正常启动，启动命令为：

```bash
roslaunch spot_micro_navigation slam_hector_mapping.launch
```

实际验证中，关键话题均已正常出现：

- `/scan`
- `/map`
- `/slam_out_pose`

地图信息验证结果为：

- 分辨率：`0.05 m/cell`
- 地图大小：`2048 x 2048`
- 原点位于约 `(-51.2, -51.2)`

同时，`/slam_out_pose` 能输出机器人在地图坐标系下的实时位姿，说明 Hector 已具备在线定位与建图能力。

`/map` 的发布频率约为 `0.5 Hz` 左右，这与配置中的地图发布周期一致，属于正常现象，不是故障。

---

## 7. 保存地图阶段的问题与解决

### 7.1 初始问题：`map_server` 不存在

在执行地图保存命令时：

```bash
rosrun map_server map_saver -f hector_map_$(date +%Y%m%d_%H%M%S)
```

最初系统报错：

- `package 'map_server' not found`

这说明虽然 Hector 已可运行，但基础 ROS 源码工作区中尚未补齐 Navigation Stack。

### 7.2 处理思路：补齐导航栈源码

为解决该问题，在 `ros_noetic_ws/src` 中补齐了以下仓库：

- `navigation`
- `navigation_msgs`
- `diagnostics`
- `rosbag_migration_rule`

另外还补齐了：

- `tf2_sensor_msgs`

补齐过程中遇到 Jammy + Noetic 的典型 rosdep 问题，例如：

- `hddtemp` 在当前系统上不可用
- `python3-catkin-pkg-modules` 无法通过 apt 找到
- `python3-rosdep-modules` 无法通过 apt 找到

处理策略并不是死磕 apt，而是根据导航主链的实际需求进行取舍：

- `diagnostic_common_diagnostics` 并非当前导航主链必需，可临时忽略
- `python3-catkin-pkg-modules` 与 `python3-rosdep-modules` 在 Jammy 上可跳过，继续源码编译

最终结果是：

- `catkin_make` 成功完成
- 关键导航包全部可被 `rospack find` 找到

包括：

- `map_server`
- `amcl`
- `move_base`
- `global_planner`
- `dwa_local_planner`
- `map_msgs`
- `move_base_msgs`
- `diagnostic_updater`
- `tf2_sensor_msgs`

### 7.3 地图保存最终成功

在导航栈源码补齐后，地图保存命令最终执行成功，生成了：

- `~/Desktop/SpotMicro/maps/hector_map_20260409_111304.pgm`
- `~/Desktop/SpotMicro/maps/hector_map_20260409_111304.yaml`

这表明：

- Hector 实时构建的地图已经成功固化为静态地图文件
- 后续 `map_server + amcl + move_base` 已经具备输入基础

---

## 8. AMCL 静态地图定位阶段的问题与解决

### 8.1 问题 1：地图文件路径写错

在首次启动 AMCL 时，使用了错误路径：

- `/home/HwHiAiUser/Desktop/SpotMicro/maps/hector_map_111304.yaml`

但真实保存出来的文件名为：

- `/home/HwHiAiUser/Desktop/SpotMicro/maps/hector_map_20260409_111304.yaml`

因此 `map_server` 报错：

- 无法打开 YAML 文件

处理思路：

- 地图文件必须使用完整真实文件名
- 时间戳中的日期部分不能省略

### 8.2 问题 2：Hector 与 AMCL 同时运行

在第一次尝试 AMCL 时，Hector 仍处于运行状态。这样会造成：

- Hector 持续发布 `/map`
- AMCL 设置 `use_map_topic: True`
- AMCL 不断收到“新地图”
- 重复打印：
  - `Received a 2048 X 2048 map`
  - `Initializing likelihood field model`
- 同时还可能伴随：
  - `Costmap2DROS transform timeout`

根因是：

- Hector 适用于“在线建图”
- AMCL 适用于“静态地图定位”
- 两者不能同时承担地图来源

正确处理方式是：

- 建图阶段：开启 Hector，关闭 AMCL / move_base
- 定位阶段：关闭 Hector，仅保留静态地图 + AMCL

### 8.3 问题 3：重复启动同名节点

后续还出现过：

- `new node registered with same name`

其根因是：

- `localization_amcl.launch` 会启动 `amcl` 与 `map_server`
- `navigation_astar_dwa.launch` 也会启动 `amcl` 与 `map_server`

如果两个 launch 同时运行，就会导致后启动的节点将前面的同名节点挤掉。

正确处理方式是：

- 只做定位验证时：启动 `localization_amcl.launch`
- 做完整导航验证时：直接启动 `navigation_astar_dwa.launch`
- 两者不能同时运行

---

## 9. AMCL 最终验证结果

在关闭 Hector、使用正确静态地图路径后，AMCL 启动成功，日志明确显示：

- 成功加载 `.pgm` 地图
- 成功读取 `2048 x 2048` 地图
- 成功初始化 likelihood field 模型

关键话题正常存在：

- `/map`
- `/amcl_pose`
- `/particlecloud`

实际输出的 `/amcl_pose` 已经具备：

- 位姿估计
- 姿态估计
- 协方差矩阵

例如本次验证中可见：

- `x ≈ -0.0646`
- `y ≈ 0.0324`
- 朝向接近 0

这说明：

- `静态地图 + 激光 + odom + TF + AMCL`

已经组成了可用的定位系统。

---

## 10. 完整导航链路当前状态

在导航总 launch 中，以下关键节点已成功出现过：

- `map_server`
- `amcl`
- `move_base`
- `cmd_vel_safety_gate`
- `nav_mode_manager`

关键话题也已存在：

- `/cmd_vel_nav_raw`
- `/cmd_vel`
- `/move_base/...`

当前观察到：

- `/cmd_vel` 输出全 0
- `/cmd_vel_nav_raw` 暂无有效控制输出

这在当前阶段是正常的，因为还没有正式下发导航目标点。没有目标时，局部规划器不会生成运动指令，安全门也不会放行有效速度输出。

因此，此时不能说“自主导航已完成”，但可以明确说：

- 完整导航框架已经具备启动条件
- 剩余任务是进行目标点测试与实机运动联调

---

## 11. 本阶段最关键的工程经验

通过本轮联调，可以总结出以下实践经验：

### 11.1 必须按链路拆分调试，不能一口气全启动

推荐顺序是：

1. 雷达驱动
2. TF / odom
3. Hector 建图
4. 保存静态地图
5. AMCL 定位
6. move_base 全导航

这样可以避免多个问题叠加后难以定位根因。

### 11.2 Jammy + Noetic 下更适合源码补齐，而不是死磕 apt 包

在 Ubuntu 22.04 上，ROS1 Noetic 已经不是官方标准二进制目标环境，很多包：

- 找不到
- 版本不完整
- 依赖映射不兼容

因此对于导航栈这类关键包，更可靠的做法是源码补齐并在本地编译。

### 11.3 Python 环境干扰是高频故障源

如果不清理 Conda 和 Python 环境变量，经常会导致 ROS Python 工具链异常。因此每个新终端的环境初始化动作应固定化。

### 11.4 地图文件路径必须真实、完整、可复制

任何文件名简写、示例名、手写省略，都可能直接导致 `map_server` 启动失败。

### 11.5 Hector 与 AMCL 不能同时承担地图来源

这是 SLAM 与定位切换时最关键的原则之一：

- Hector 用于建图
- map_server + AMCL 用于静态地图定位

二者同时运行往往会引发地图反复刷新、定位模型重建、TF 冲突等问题。

### 11.6 没有导航目标时 `/cmd_vel` 为 0 是正常的

不能把“当前不动”直接判断为导航失败，需要结合：

- 是否有 goal
- `/move_base/status`
- `/cmd_vel_nav_raw`
- `/cmd_vel`

综合判断。

---

## 12. 当前阶段性结论

截至本阶段结束，SpotMicro 已经完成：

- 雷达驱动联通
- 机器人底层运动节点联通
- TF 主链联通
- Hector 实时建图成功
- 静态地图保存成功
- AMCL 静态地图定位成功
- move_base 导航框架可启动

因此，当前项目状态可以定义为：

**SpotMicro 已进入“静态地图定位与自主导航联调阶段”。**

---

## 13. 下一步建议

下一阶段建议继续做以下工作：

1. 启动 `navigation_astar_dwa.launch`
2. 通过命令行或 RViz 发布 `/initialpose`
3. 通过命令行或 RViz 发布 `/move_base_simple/goal`
4. 检查：
   - `/cmd_vel_nav_raw`
   - `/cmd_vel`
   - `/move_base/status`
5. 在低速、安全条件下进行小范围实机验证

保守建议的首次导航测试速度限制：

- 线速度：`<= 0.10 ~ 0.12 m/s`
- 角速度：`<= 0.20 rad/s`

第一次测试时，目标距离建议控制在：

- `0.1 ~ 0.2 m`

先验证规划、限速、安全门和底层运动响应是否一致，再逐步扩大移动范围。

---

## 14. 相关文档

本阶段相关文档与记录如下：

- `software_orangepiaipro/docs_cn/03_导航与雷达/RPLidar_Hector_实操问题复盘.md`
- `software_orangepiaipro/docs_cn/03_导航与雷达/AMCL_move_base_源码补齐方案.md`
- `software_orangepiaipro/docs_cn/01_环境部署/OrangePi_Jammy_Noetic_导航编译排障.md`
- `software_orangepiaipro/docs_cn/03_导航与雷达/navigation_stack_runbook.md`
- `temp/命令缓存.txt`

本文件用于对“雷达接入 -> Hector 建图 -> 静态地图保存 -> AMCL 定位”这一阶段进行系统归档，便于后续继续推进完整导航联调。
