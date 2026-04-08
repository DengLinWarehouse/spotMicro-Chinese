# Orange Pi Jammy Noetic 导航编译排障

本文对应当前环境：

- 主控：Orange Pi AI Pro
- OS：Ubuntu 22.04.3 LTS (Jammy)
- ROS：Noetic 源码工作区 `~/Desktop/SpotMicro/ros_noetic_ws`
- 业务工作区：`~/Desktop/SpotMicro/spotmicro_ws`
- 导航目标：`RPLidar -> Hector 建图 -> AMCL -> A* / Dijkstra -> DWA -> /cmd_vel -> spot_micro_motion_cmd`

---

## 1. 当前结论

当前 `catkin_make` 首个真正阻塞点不是你新加的 `spot_micro_navigation`，而是：

```text
Could not find a package configuration file provided by "cv_bridge"
```

这说明你的 `ros_noetic_ws` 目前是一个“裁剪版基础工作区”，缺少 ROS 感知/可视化栈中的若干包。

结合前面的 `rosdep` 输出，可以确认当前至少还缺这几类依赖：

| 缺失项 | 谁在要 | 是否导航最小闭环必需 | 处理建议 |
| --- | --- | --- | --- |
| `cv_bridge` | `hector_compressed_map_transport` | 否 | 直接跳过该包，最快 |
| `image_transport` | `hector_compressed_map_transport` | 否 | 随上一项一起跳过 |
| `laser_geometry` | `hector_mapping` | 是 | 必须补 |
| `rviz` | `spot_micro_launch` / `hector_slam_launch` | 对机器人本机编译不是必需 | 先解除构建硬依赖 |

结论先说：

1. **推荐走“最小可落地编译路径”**
2. **先不要在 Jammy/ARM 上硬啃完整 `rviz + vision_opencv + image_common` 全家桶**
3. **先让 `Hector + RPLidar + move_base + AMCL` 编译通过，再做可视化增强**

---

## 2. 为什么会这样

### 2.1 理论分析

`catkin_make` 在配置阶段会遍历整个 `spotmicro_ws/src`。只要任意一个包的 `find_package(...)` 找不到依赖，整个工作区就会停下。

你的报错链是：

```text
hector_compressed_map_transport
  -> find_package(catkin REQUIRED COMPONENTS cv_bridge image_transport ...)
  -> ros_noetic_ws 中没有 cv_bridge
  -> CMake 直接失败
```

### 2.2 工程判断

`hector_compressed_map_transport` 只是 Hector SLAM 的附加压缩地图传输组件，不是建图主链路。

对你当前机器狗任务：

- 建图核心是 `hector_mapping`
- 定位核心是 `amcl`
- 规划核心是 `move_base + global_planner + dwa_local_planner`

所以这个包可以先跳过，不影响主目标闭环。

---

## 3. 两条技术路线对比

| 方案 | 原理概要 | 适用条件 | 性能预期 | 实现复杂度 | 调试难度 | 实机落地风险 |
| --- | --- | --- | --- | --- | --- | --- |
| 方案 A：最小编译路径 | 跳过非关键包，只补 `laser_geometry`，解除 `rviz` 构建硬依赖 | 目标是尽快跑通雷达建图与导航 | 可较快形成可运行闭环 | 低 | 低 | 低 |
| 方案 B：完整桌面依赖路径 | 在 `ros_noetic_ws` 补齐 `vision_opencv`、`image_common`、`rviz` 等完整栈 | 你确实要在 Orange Pi 本机也能完整运行 RViz/图像桥 | 功能更全 | 高 | 高 | 中 |

### 3.1 失效条件

#### 方案 A 会在什么条件下失效

1. 你后面必须在 Orange Pi 本机运行 `rviz`
2. 你必须使用 `hector_compressed_map_transport`
3. 你后续还要接相机图像链路，需要 `cv_bridge`

#### 方案 B 会在什么条件下失效

1. Jammy + ARM 上某些 ROS1 老包源码兼容性继续冒出新问题
2. 编译时间和内存占用过大，拖慢整体进度
3. 你为了“完整桌面栈”投入太多时间，反而耽误核心导航链闭环

### 3.2 推荐

**主选：方案 A。**

推荐理由：

1. 你当前核心目标是“把机器狗雷达调通并跑通导航主链”，不是在 Orange Pi 本机做全功能桌面开发
2. `hector_compressed_map_transport` 对当前任务不是关键路径
3. `laser_geometry` 才是 `hector_mapping` 的硬依赖，优先级最高
4. `spot_micro_launch` 当前把 `rviz` 声明成构建依赖，这在工程上偏重了，可以解除

次选方案：

- 只有当你确认要在 Orange Pi 本机长期运行 RViz 或图像链时，再补完整桌面依赖

不推荐：

- 一边缺 `laser_geometry`，一边去折腾 `cv_bridge` 全家桶
- 还没编过就直接继续堆 Cartographer、激光里程计、EKF

---

## 4. 已做的仓库侧修正

为了让 SpotMicro 自己的源码更适合 Jammy 最小编译路径，仓库已经建议改成：

1. `spot_micro_launch/CMakeLists.txt` 不再把 `rviz` 作为构建期 `find_package` 依赖
2. `spot_micro_launch/package.xml` 不再把 `rviz` 声明为构建/运行硬依赖

原因很简单：

- `spot_micro_launch` 是启动组织包，不链接 `rviz` 库
- 把 `rviz` 写成构建硬依赖，只会在 Jammy 源码环境里白白增加失败点

如果 Orange Pi 上的 `spotmicro_ws/src/spot_micro_launch` 是通过软链接指向本仓库，更新源码后会自然生效。

如果不是软链接，而是旧副本，请手动同步这两个文件。

---

## 5. 推荐执行步骤

### 5.0 先更正一个常见小坑

如果你手动创建忽略文件时写成了：

```bash
touch hector_slam/hector_compressed_map_transport/CATKIN_IGNOR
```

这是**无效**的，因为少了最后一个 `E`。catkin 只认：

```bash
touch hector_slam/hector_compressed_map_transport/CATKIN_IGNORE
```

只要文件名拼错，`hector_compressed_map_transport` 仍然会被遍历和编译。

### 5.1 第一步：补 `laser_geometry`

在 Orange Pi 上执行：

```bash
cd ~/Desktop/SpotMicro/spotmicro_ws/src
git clone -b noetic-devel https://github.com/ros-perception/laser_geometry.git
```

说明：

- 这里直接放进 `spotmicro_ws/src`，是为了先把 `hector_mapping` 编过
- 理论上也可以放到 `ros_noetic_ws/src`
- 但当前目标是快速闭环，先放 overlay 更省事

### 5.2 第二步：跳过 `hector_compressed_map_transport`

```bash
cd ~/Desktop/SpotMicro/spotmicro_ws/src
touch hector_slam/hector_compressed_map_transport/CATKIN_IGNORE
```

这一步的含义：

- 告诉 catkin：这个包先别编
- 代价只是没有压缩地图传输功能
- 对当前 `Hector -> map_server -> AMCL -> move_base` 主链无实质影响

### 5.3 第三步：重新链接 SpotMicro 源码

如果你已经把本仓库里最新导航改动同步到 Orange Pi，请再执行一次：

```bash
bash ~/Desktop/SpotMicro/spotMicro-Chinese/software_orangepiaipro/scripts/link_spotmicro_workspace.sh ~/Desktop/SpotMicro/spotmicro_ws
```

目的：

1. 确保 `spot_micro_navigation` 已经链接进工作区
2. 确保 `spot_micro_launch` 使用的是最新源码，而不是旧副本

如果脚本输出里**没有**这一行：

```text
[ok] spot_micro_navigation already linked
```

那就说明 Orange Pi 上的 `software_orangepiaipro/scripts/link_spotmicro_workspace.sh` 还是旧版本，远端仓库副本尚未同步到最新。

### 5.4 第四步：重新编译

```bash
cd ~/Desktop/SpotMicro/spotmicro_ws
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
catkin_make -DCATKIN_ENABLE_TESTING=OFF -DPYTHON_EXECUTABLE=/usr/bin/python3
```

### 5.5 如果出现 `joy` 缺失，优先跳过 `spot_micro_joy`

如果你看到类似报错：

```text
Could not find a package configuration file provided by "joy"
```

说明是 `spot_micro_joy` 这个手柄遥控扩展包卡住了，而不是导航主链卡住。

对当前任务，推荐先直接忽略它：

```bash
cd ~/Desktop/SpotMicro/spotmicro_ws/src
touch spot_micro_joy/CATKIN_IGNORE
```

原因：

1. `spot_micro_joy` 只是手柄输入扩展包
2. 当前导航主链并不依赖它
3. 你现在的优先目标是让雷达、建图、AMCL、规划先跑起来

如果你后续确实要接物理手柄，再单独补 `joy` 包即可

---

## 6. 如果下一轮还报错，按这个优先序看

### 6.1 如果报 `laser_geometry` 找不到

重点检查：

```bash
ls ~/Desktop/SpotMicro/spotmicro_ws/src/laser_geometry
```

再检查：

```bash
cat ~/Desktop/SpotMicro/spotmicro_ws/src/laser_geometry/package.xml | head
```

可能原因：

1. clone 目录不对
2. 分支不对
3. 没在 `spotmicro_ws` 根目录重新 `catkin_make`

### 6.2 如果报 `rvizConfig.cmake` 找不到

说明：

- Orange Pi 上仍在使用旧版 `spot_micro_launch`
- 或者还有别的包把 `rviz` 当成构建依赖

先检查：

```bash
grep -R \"rviz\" -n ~/Desktop/SpotMicro/spotmicro_ws/src/spot_micro_launch
```

如果你看到 `spot_micro_launch/CMakeLists.txt` 里仍有：

```cmake
find_package(catkin REQUIRED COMPONENTS
  ...
  rviz
  ...
)
```

那就说明远端 `spot_micro_launch` 还没同步到本仓库当前版本。

这时有两种处理方式：

#### 方案 A：直接在 Orange Pi 上热修

```bash
sed -i '/^[[:space:]]*rviz$/d' ~/Desktop/SpotMicro/spotmicro_ws/src/spot_micro_launch/CMakeLists.txt
sed -i '/<build_depend>rviz<\\/build_depend>/d' ~/Desktop/SpotMicro/spotmicro_ws/src/spot_micro_launch/package.xml
sed -i '/<build_export_depend>rviz<\\/build_export_depend>/d' ~/Desktop/SpotMicro/spotmicro_ws/src/spot_micro_launch/package.xml
sed -i '/<exec_depend>rviz<\\/exec_depend>/d' ~/Desktop/SpotMicro/spotmicro_ws/src/spot_micro_launch/package.xml
```

优点：

1. 最快
2. 不依赖你先同步整仓库

缺点：

1. 这是远端热修，后续最好仍把仓库同步一致

#### 方案 B：同步 Orange Pi 上的 `software_orangepiaipro`

如果你本地 Windows 仓库才是最新版，而 Orange Pi 上的是旧副本，就把新版同步过去，再重新执行链接脚本。

### 6.3 如果报 `joy` 找不到

优先检查：

```bash
ls ~/Desktop/SpotMicro/spotmicro_ws/src/spot_micro_joy/CATKIN_IGNORE
```

如果没有这个文件，就说明 `spot_micro_joy` 还在参与编译。

### 6.4 如果报 `cv_bridge` / `image_transport` 仍找不到

说明大概率是：

- `CATKIN_IGNORE` 没放到 `hector_slam/hector_compressed_map_transport/`
- 路径放错了

正确位置应为：

```text
~/Desktop/SpotMicro/spotmicro_ws/src/hector_slam/hector_compressed_map_transport/CATKIN_IGNORE
```

---

### 6.5 如果 `link_spotmicro_workspace.sh` 输出里没有 `spot_micro_navigation`

正常情况下，重新链接时应当能看到：

```text
[ok] spot_micro_navigation already linked
```

如果没有这行，需要额外检查：

```bash
ls -l ~/Desktop/SpotMicro/spotmicro_ws/src/spot_micro_navigation
```

如果目录不存在，说明 Orange Pi 上的仓库副本还没同步到最新版本，或者链接脚本不是最新版本。

还可以再看一眼编译遍历列表：

- 如果 `catkin_make` 开头的包列表里没有 `spot_micro_navigation`
- 那就说明当前工作区里实际上还没加入这个导航包

这种情况下，即便其它包编过了，也还没有真正开始编译你新增的导航集成部分。

## 7. 风险分析

| 风险项 | 严重度 | 发生概率 | 触发条件 | 缓解措施 |
| --- | --- | --- | --- | --- |
| 跳过 `hector_compressed_map_transport` 后误以为 Hector 功能不完整 | 低 | 中 | 看到包被忽略后担心主链不可用 | 明确它不是主建图链必需组件 |
| 跳过 `spot_micro_joy` 后误以为控制链断掉 | 低 | 中 | 当前没有物理手柄输入 | 明确键盘控制与导航链不依赖它 |
| `laser_geometry` 放在 overlay 导致后期基础环境不统一 | 中 | 中 | 后续你开始维护多个机器人工作区 | 等主链跑通后，再决定是否上移到 `ros_noetic_ws` |
| `rviz` 不在本机，调试可视化不方便 | 中 | 中 | 想在 Orange Pi 本机直接点 `2D Nav Goal` | 可改为远端 PC 跑 RViz，或后续再补 `rviz` |
| 继续沿用伪 `odom`，导致 AMCL/DWA 稳定性差 | 高 | 高 | 建图跑通后直接做闭环导航 | 下一阶段尽快补真实 odom 源 |

---

## 8. 下一阶段建议

一旦这轮编译通过，下一步按这个顺序推进：

1. 验证 `/scan`
2. 验证 `base_link -> lidar_link` TF
3. 单独启动 `slam_hector_mapping.launch`
4. 保存地图
5. 启动 `localization_amcl.launch`
6. 启动 `navigation_astar_dwa.launch`
7. 最后再处理更稳的 `odom`

---

## 9. 一句话判断标准

当前阶段的正确策略不是“把所有 ROS1 生态包一次性补齐”，而是：

**先让最短关键链编过并跑起来：`RPLidar -> Hector -> map -> AMCL -> move_base -> /cmd_vel`。**
