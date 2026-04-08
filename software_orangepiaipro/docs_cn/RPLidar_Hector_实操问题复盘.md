# RPLidar + Hector SLAM 实操问题复盘

本文总结本次 SpotMicro 在 Orange Pi AI Pro 上完成雷达接入、ROS1 Noetic 源码编译、RPLidar 调试、TF 校验、Hector 建图落地过程中遇到的真实问题、判断依据、修复动作与工程经验。

适用环境：

- 主控：Orange Pi AI Pro
- OS：Ubuntu 22.04.3 LTS (Jammy)
- ROS：ROS1 Noetic，源码编译基础工作区 `~/Desktop/SpotMicro/ros_noetic_ws`
- 业务工作区：`~/Desktop/SpotMicro/spotmicro_ws`
- 雷达：RPLidar A1
- 当前导航架构阶段：`RPLidar -> Hector -> map`

---

## 1. 结论先行

本轮已经实际打通的链路是：

```text
RPLidar -> /scan -> lidar_link
motion_cmd -> odom/base_footprint/base_link/lidar_link TF
Hector Mapping -> /map + /slam_out_pose
```

已验证通过的关键结果：

1. `rplidar_ros` 驱动正常识别雷达，健康状态 `OK`
2. `/scan` 频率约 `9.3 Hz`
3. `/scan.header.frame_id` 已统一为 `lidar_link`
4. `base_link -> lidar_link` TF 正常，外参为：
   - `x = 0.045 m`
   - `y = 0.000 m`
   - `z = 0.085 m`
   - `yaw = -180 deg`
5. Hector 已正常发布：
   - `/map`
   - `/slam_out_pose`
6. Hector 参数命名空间问题已修复，实际生效参数为：
   - `map_update_distance_thresh = 0.25`
   - `map_update_angle_thresh = 0.05`

当前尚未打通的部分：

1. `amcl`
2. `move_base`
3. `global_planner`
4. `dwa_local_planner`

原因不是方案错，而是对应 ROS 导航栈源码包尚未补进 `ros_noetic_ws`。

---

## 2. 本次实操采用的工程路线

不是走“Ubuntu 20.04 + apt 安装 Noetic 二进制包”路线，而是：

```text
Jammy + ROS1 Noetic 源码基础工作区 + SpotMicro overlay 工作区
```

工程原因：

1. Orange Pi 使用 Ubuntu 22.04
2. Jammy 的 apt 源里不存在大量 `ros-noetic-*` 二进制包
3. 若继续强走 apt，会在早期就被依赖缺包卡死

因此本次采用：

- `ros_noetic_ws`：只放 ROS1 Noetic 基础源码
- `spotmicro_ws`：只放 SpotMicro 业务包、Hector、RPLidar 等 overlay 包

这是本轮能真正落地的关键前提。

---

## 3. 问题总表

| 阶段 | 现象 | 根因 | 处理动作 | 最终结论 |
| --- | --- | --- | --- | --- |
| 依赖安装 | `ros-noetic-rplidar-ros`、`ros-noetic-hector-*` 在 apt 中不存在 | Jammy 不提供对应 Noetic 二进制包 | 改走源码安装 `rplidar_ros`、`hector_slam` | 正确 |
| rosdep | `rviz`、`laser_geometry`、`image_transport` 等无法解析 | 基础工作区不完整，且部分依赖不适合当前最小闭环 | 采用“最小可落地编译路径” | 正确 |
| 构建 1 | `cv_bridge` 缺失 | `hector_compressed_map_transport` 不是主链但触发构建 | 用 `CATKIN_IGNORE` 跳过该包 | 正确 |
| 构建 2 | `joy` 缺失 | `spot_micro_joy` 是手柄扩展包，不是导航主链 | 用 `CATKIN_IGNORE` 跳过 `spot_micro_joy` | 正确 |
| 构建 3 | `rvizConfig.cmake` 缺失 | `spot_micro_launch` 把 `rviz` 声明成编译硬依赖 | 去掉 `rviz` 构建依赖 | 正确 |
| 仓库同步 | `spot_micro_navigation` 不存在，链接脚本也未包含 | Orange Pi 上仓库副本落后 | 合并远端新增导航包提交 | 正确 |
| 构建 4 | `rplidar_ros` 编译时报 `shared_mutex` / `shared_lock` | Jammy 的 `log4cxx` 头文件需要更高 C++ 标准 | 给 `rplidar_ros` 加 `-std=c++17` | 正确 |
| 运行 1 | `rostopic` 报 `Cryptodome` 缺失 | 源码版 ROS 运行期 Python 依赖未补齐 | `sudo apt install python3-pycryptodome` | 正确 |
| 运行 2 | `rostopic` 报 `gnupg` 缺失 | `rosbag` 依赖链继续缺包 | `sudo apt install python3-gnupg` | 正确 |
| 雷达参数 | 启动时传了 `frame_id:=lidar_link`，实际仍是 `laser` | `rplidar_a1.launch` 内写死 `value=\"laser\"` | 直接改 launch 默认值 | 正确 |
| Hector 配置 | Hector 启动了，但阈值仍是默认值 | YAML 加载到了全局命名空间，不在节点私有命名空间 | 把 `<rosparam ...>` 移入 `<node>` 内 | 正确 |

---

## 4. 关键问题详解

### 4.1 Jammy 下 apt 不存在 Noetic 雷达/SLAM 二进制包

#### 现象

用户环境已经确认：

- Ubuntu 22.04.3 LTS
- `rosdep` 可用
- 但 `ros-noetic-rplidar-ros`、`ros-noetic-hector-*` 在 apt 源中不存在

#### 根因

ROS1 Noetic 官方主要面向 Ubuntu 20.04。  
Jammy 上很多 `ros-noetic-*` 包没有现成可用的二进制仓库。

#### 处理策略

直接改走源码：

- `rplidar_ros`
- `hector_slam`

#### 工程经验

在 Orange Pi + Jammy 场景下，不要一开始就反复尝试 `apt install ros-noetic-*`。  
先接受“基础环境源码化，业务栈 overlay 化”的事实，效率更高。

---

### 4.2 `hector_compressed_map_transport` 导致 `cv_bridge` 缺失

#### 现象

首次 `catkin_make` 被卡在：

```text
Could not find a package configuration file provided by "cv_bridge"
```

#### 根因

真正触发报错的是：

- `hector_compressed_map_transport`

它依赖：

- `cv_bridge`
- `image_transport`

但该包只是 Hector 的附加压缩地图传输组件，不是当前主建图链所必需。

#### 处理动作

在 `spotmicro_ws/src` 中直接忽略：

```bash
touch hector_slam/hector_compressed_map_transport/CATKIN_IGNORE
```

注意本次实际踩到的坑：

- 第一次误写成了 `CATKIN_IGNOR`
- 少一个 `E` 会导致包并未真正被忽略

#### 工程经验

对落地主链不必需的包，优先“隔离”，不要急着补全所有生态依赖。

---

### 4.3 `spot_micro_joy` 导致 `joy` 缺失

#### 现象

后续构建被卡在：

```text
Could not find a package configuration file provided by "joy"
```

#### 根因

触发包是：

- `spot_micro_joy`

这是手柄输入扩展，不是当前雷达建图主链所必需。

#### 处理动作

```bash
touch spot_micro_joy/CATKIN_IGNORE
```

#### 工程经验

导航调试阶段，键盘控制已经足够。  
手柄输入链可后补，不应阻断主线。

---

### 4.4 `spot_micro_launch` 不应把 `rviz` 当成构建硬依赖

#### 现象

构建继续卡在：

```text
Could not find a package configuration file provided by "rviz"
```

#### 根因

`spot_micro_launch` 本质是启动组织包，不链接 `rviz` 库。  
但旧版 `CMakeLists.txt` / `package.xml` 中把 `rviz` 写成了构建硬依赖。

#### 处理动作

从 `spot_micro_launch` 中去掉：

- `CMakeLists.txt` 的 `find_package(... rviz ...)`
- `package.xml` 中的 `rviz` build / export / exec 依赖

#### 工程经验

Jammy 源码环境下，凡是“只在运行时可选使用”的可视化组件，都不应轻易作为构建硬依赖。

---

### 4.5 Orange Pi 上仓库副本落后，导航包根本不存在

#### 现象

一度出现：

- `spot_micro_navigation` 不存在
- `link_spotmicro_workspace.sh` 里也没有这一包

#### 根因

Orange Pi 上的 `spotMicro-Chinese` 仓库副本落后于本地仓库。

#### 处理动作

先检查：

```bash
git status --short
git branch -vv
git fetch --all --prune
git log --oneline --graph --decorate --left-right HEAD...@{upstream}
```

实际发现：

- 本地 ahead 1
- 远端 behind 1

最终采用：

```bash
git branch backup_before_nav_sync_2026_04_08
git merge origin/master
```

合并成功后，`spot_micro_navigation` 才真正进入 Orange Pi 仓库。

#### 工程经验

如果“新增包/脚本在本地有、远端没有”，继续排构建只会浪费时间。  
先确认仓库版本一致。

---

### 4.6 `rplidar_ros` 在 Jammy 上需要 C++17

#### 现象

`rplidar_ros` 编译时报：

```text
shared_mutex in namespace std does not name a type
shared_lock is only available from C++14 onwards
```

#### 根因

Jammy 自带的 `log4cxx` 头文件链路要求更高的 C++ 标准。  
而 `rplidar_ros` 仍按旧默认标准在编译。

#### 处理动作

在 `rplidar_ros/CMakeLists.txt` 中加：

```cmake
add_compile_options(-std=c++17)
```

#### 工程经验

在 Jammy 上做 ROS1 源码编译时，不要惊讶于个别老包需要单独提升 C++ 标准。  
优先“按包修复”，不要一上来全局提高整个工作区的标准。

---

### 4.7 `rostopic` 不是坏了，是 Python 依赖没补齐

#### 现象

`rplidar_ros` 已能启动，但：

```text
rostopic list
rostopic hz /scan
rostopic echo -n 1 /scan
```

先后报：

- `No module named 'Cryptodome'`
- `No module named 'gnupg'`

#### 根因

源码版 ROS1 环境中，`rostopic` 通过 `rosbag` 依赖链会 import：

- `Cryptodome`
- `gnupg`

系统未安装这些 Python 模块。

#### 处理动作

```bash
sudo apt install python3-pycryptodome
sudo apt install python3-gnupg
```

验证：

```bash
python3 -c "from Cryptodome.Cipher import AES; print('Cryptodome OK')"
python3 -c "import gnupg; print('gnupg OK')"
```

#### 工程经验

源码版 ROS1 的运行期依赖，常常不会在最早期一次性暴露。  
命令行工具恢复策略应是：

- 缺哪个补哪个
- 优先系统包
- 尽量避免 Conda / pip 与系统 Python 混装

---

### 4.8 `frame_id:=lidar_link` 没生效

#### 现象

虽然启动命令中写了：

```bash
roslaunch rplidar_ros rplidar_a1.launch serial_port:=/dev/ttyUSB0 frame_id:=lidar_link
```

但实际参数仍显示：

```text
/rplidarNode/frame_id: laser
```

`/scan.header.frame_id` 也仍是 `laser`。

#### 根因

`rplidar_a1.launch` 中直接写死了：

```xml
<param name="frame_id" type="string" value="laser"/>
```

不是 `<arg>` + `<param value="$(arg frame_id)">` 的形式。

#### 处理动作

直接修改 launch：

```xml
<param name="frame_id" type="string" value="lidar_link"/>
```

修正后验证：

- `rosparam get /rplidarNode/frame_id` -> `lidar_link`
- `rostopic echo -n 1 /scan/header` -> `frame_id: "lidar_link"`

#### 工程经验

不要只相信启动命令参数。  
一旦运行结果和预期不一致，优先检查 launch 文件本身是“参数化”还是“硬编码”。

---

### 4.9 TF 主干验证

本次实际验证通过的 TF：

#### `base_link -> lidar_link`

实测：

- Translation: `[0.045, 0.000, 0.085]`
- Yaw: `-180 deg`

与 `spot_micro_motion_cmd.yaml` 中参数一致：

- `lidar_x_pos: 0.045`
- `lidar_y_pos: 0.0`
- `lidar_z_pos: 0.085`
- `lidar_yaw_angle: 180`

#### `odom -> base_footprint`

静止时为零位姿：

- 平移全零
- 旋转全零

这是合理现象，因为机器人尚未运动。

#### `base_footprint -> base_link`

实测：

- `z ≈ 0.083 m`

说明机体高度 TF 正常发布。

#### 工程结论

当前建图链使用的坐标主干已经成立：

```text
map -> odom -> base_footprint -> base_link -> lidar_link
```

---

### 4.10 Hector 能启动，但 YAML 参数未进入节点私有命名空间

#### 现象

Hector 已经能发布：

- `/map`
- `/slam_out_pose`

但日志中仍显示默认值：

- `p_map_update_distance_threshold_: 0.400000`
- `p_map_update_angle_threshold_: 0.900000`

而配置文件期望值是：

- `0.25`
- `0.05`

#### 根因

原先 launch 写法是：

```xml
<rosparam command="load" file="$(arg config_file)" />
<node ...>
  ...
</node>
```

这样 YAML 被加载到全局命名空间，而 `hector_mapping` 节点读取的是自己的私有参数。

#### 处理动作

改成：

```xml
<node ...>
  <rosparam command="load" file="$(arg config_file)" />
  ...
</node>
```

同时顺手对 `slam_gmapping_mapping.launch` 做同样修正。

#### 修正后实际验证

日志已经变成：

- `p_map_update_distance_threshold_: 0.250000`
- `p_map_update_angle_threshold_: 0.050000`

并且 `/map/info` 已变为：

- `resolution ≈ 0.05`
- `width = 2048`
- `height = 2048`

#### 工程经验

ROS launch 里“参数有没有生效”，不能只看 YAML 文件写了什么，必须看节点启动日志的实际读取值。

---

## 5. 当前可确认的工作状态

### 5.1 雷达状态

已确认：

- 串口识别正常
- 硬件健康状态 `OK`
- 扫描模式正常
- 频率约 `9.33 Hz`
- `/scan` 数据有效

### 5.2 TF 状态

已确认：

- `base_link -> lidar_link` 正常
- `odom -> base_footprint` 正常
- `base_footprint -> base_link` 正常

### 5.3 Hector 状态

已确认：

- `/map` 正常发布
- `/slam_out_pose` 正常发布
- 参数命名空间修正后，配置已实际生效

---

## 6. 当前仍未完成的部分

### 6.1 `amcl`、`move_base` 缺失

通过 `rospack find` 已确认当前系统仍缺：

- `amcl`
- `move_base`

这说明：

- 可以做 Hector 建图
- 还不能做完整导航闭环

### 6.2 真实 odom 仍然较弱

当前链路仍主要依赖：

- `spot_micro_motion_cmd` 发布的 `odom -> base_footprint`

这可以支撑当前调试和基础建图，但对后续：

- AMCL 稳定性
- DWA 跟踪平滑性
- 回环和狭窄场景导航

仍是风险点。

---

## 7. 本轮最关键的工程经验

### 7.1 不要追求“一次装全”

当前能落地的关键不是把所有 ROS 包一次性补齐，而是：

```text
先打通最短关键链：RPLidar -> TF -> Hector -> map
```

### 7.2 区分“编译期问题”和“运行期问题”

- `cv_bridge`、`joy`、`rviz`、`shared_mutex` 属于编译期问题
- `Cryptodome`、`gnupg`、`frame_id`、参数命名空间 属于运行期问题

两类问题要分开排，不要混在一起。

### 7.3 任何参数都必须看“实际生效值”

不要只看：

- YAML 写了什么
- 启动命令传了什么

必须看：

- 节点日志
- `rosparam get`
- `rostopic echo`
- `tf_echo`

### 7.4 SSH 场景下环境污染很常见

本轮多次出现的现象说明：

- Conda
- `PYTHONPATH`
- `PYTHONHOME`
- ROS 源码工作区

之间很容易互相污染。

推荐每次开新终端都先做：

```bash
conda deactivate 2>/dev/null || true
unset PYTHONPATH
unset PYTHONHOME
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
source ~/Desktop/SpotMicro/spotmicro_ws/devel/setup.bash
```

---

## 8. 当前推荐的后续推进顺序

### 阶段 A：完成一张可用 Hector 地图

1. 保持以下节点运行：
   - `roscore`
   - `rplidar_ros`
   - `spot_micro_motion_cmd`
   - `hector_mapping`
2. 低速移动机器人完成小范围建图
3. 观察：
   - `/slam_out_pose`
   - `/map`
4. 地图质量可接受后保存地图

### 阶段 B：补导航运行栈源码

补到 `ros_noetic_ws/src`：

- `navigation`

目标获得：

- `amcl`
- `move_base`
- `global_planner`
- `dwa_local_planner`
- `map_server`

### 阶段 C：再进入定位与规划

1. 载入静态地图
2. 启动 `AMCL`
3. 启动 `move_base`
4. 再接 `cmd_vel_safety_gate`

---

## 9. 当前阶段的安全建议

1. 实机建图时，速度务必保守：
   - `linear.x <= 0.10 m/s`
   - `angular.z <= 0.20 rad/s`
2. 初次建图建议机器人先架空确认步态，再落地慢速运动
3. 发现地图明显扭曲时，不要继续硬跑，应优先检查：
   - 雷达安装朝向
   - `lidar_yaw_angle`
   - 机体振动
   - 地面打滑
4. 当前 `publish_odom: true` 是临时可用方案，不应当把它当成最终导航级 odom

---

## 10. 一句话总结

本轮最重要的成果，不是“理论上可以导航”，而是已经在 Orange Pi + Jammy + 源码 ROS1 的真实环境里，把下面这条链路实际跑通了：

```text
RPLidar -> /scan -> lidar_link -> TF -> Hector -> /map
```

下一步应先完成一张可用地图，再补 `AMCL + move_base`，而不是在建图尚未稳定前就急着推进全导航闭环。
