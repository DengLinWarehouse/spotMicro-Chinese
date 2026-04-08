# 软件部分

## 重要提示：Orange Pi Ubuntu 22.04 不建议在此目录原地构建

截至 2026-03，本目录更适合作为 **源码镜像 + 文档入口**。如果主控是 Orange Pi AI Pro，系统为 Ubuntu 22.04，并且 ROS1 Noetic 需要源码编译，请采用下面的双工作区方案，避免以后误操作：

1. `~/Desktop/SpotMicro/ros_noetic_ws`  
   - 只放 ROS1 Noetic 基础源码  
   - 负责源码编译 `roscore`、`roscpp`、`roslaunch` 等基础能力  
   - **不要**把 SpotMicro 业务包混进来
2. `~/Desktop/SpotMicro/spotmicro_ws`  
   - 只放机器狗相关包  
   - 先 `source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash`，再在此工作区编译和运行

推荐初始化方式：

```bash
mkdir -p ~/Desktop/SpotMicro/spotmicro_ws/src
bash ~/Desktop/SpotMicro/spotMicro-Chinese/software_orangepiaipro/scripts/link_spotmicro_workspace.sh ~/Desktop/SpotMicro/spotmicro_ws
cd ~/Desktop/SpotMicro/spotmicro_ws
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
catkin_make
```

> 对 Orange Pi Ubuntu 22.04，推荐让 `spotmicro_ws/src` 中的每个 SpotMicro 包都通过软链接指向 `software_orangepiaipro/`。这样 `software_orangepiaipro` 成为唯一源码真值，修改 YAML 或源码后不会再出现“仓库内容和运行工作区内容不一致”的问题。

> **步态切换提示**：`spot_micro_motion_cmd.yaml` 现已新增 `stride_reference_*` 参数，用固定参考步态来归一化理论步幅。日常在 8 相/4 相之间切换时，通常只需要改 `num_phases`、接触相位数组、`overlap_time`、`swing_time`，不必再跟着手工重算一次步幅参数。

如果以后要开新终端，推荐在 `~/.bashrc` 中同时保留：

```bash
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
source ~/Desktop/SpotMicro/spotmicro_ws/devel/setup.bash
```

> 对于 Orange Pi Ubuntu 22.04，**不要**直接在 `software_orangepiaipro` 根目录执行 `catkin_make` 并期待它充当 ROS base + 机器人包的混合工作区。这样最容易把基础环境和业务包搅在一起，后续升级和排错都会变难。

## 推荐链接顺序

`link_spotmicro_workspace.sh` 会一次性为 `spotmicro_ws/src` 建立核心包的软链接。若你需要手工核对，优先确认这些包已经链接成功：

| 优先级 | 包 | 说明 |
| --- | --- | --- |
| 1 | `ros-i2cpwmboard` | PCA9685/I2C 驱动，必须先通 |
| 2 | `spot_micro_motion_cmd` | 主运动控制器 |
| 3 | `spot_micro_launch` | 启动组织 |
| 4 | `spot_micro_rviz` | 模型与可视化 |
| 5 | `spot_micro_keyboard_command` | 最基础的人机输入 |

如需调单舵机或做辅助可视化，再补：

- `servo_move_keyboard`
- `spot_micro_plot`
- `lcd_monitor`

## 2026-03 推荐选包策略

为减少 Orange Pi Ubuntu 22.04 上的兼容性风险，当前建议按下面的组合迁移：

| 包 | 推荐来源 | 原因 |
| --- | --- | --- |
| `ros-i2cpwmboard` | 根目录版 | 保留了完整的 I2C 依赖与源码结构；已修正文档中的 Orange Pi I2C 参数名 |
| `spot_micro_motion_cmd` | 根目录版 | 主控制逻辑以根目录版为主；已修正 `launch/motion_cmd.launch` 中的错误文本污染 |
| `spot_micro_launch` | 根目录版 | 仅根目录存在 |
| `spot_micro_rviz` | 根目录版 | 仅根目录存在 |
| `spot_micro_keyboard_command` | 根目录版包结构 + `extensions` 中的脚本 | `extensions` 里脚本更偏向 Python 3，但根目录保留了 launch 文件 |
| `servo_move_keyboard` | 根目录版包结构 + `extensions` 中的脚本 | 同上 |
| `spot_micro_plot` | 根目录版包结构 + `extensions` 中的脚本/kinematics 子目录 | `extensions` 中补齐了更多 Python 资源 |
| `lcd_monitor` | 根目录版包结构 + `extensions` 中的 Python 文件 | `extensions` 中包含 Python 3 调整 |

## root 包与 extensions 包如何选

Orange Pi Ubuntu 22.04 推荐遵循以下规则：

- `software_orangepiaipro/`：唯一源码真值与文档入口
- `spotmicro_ws/src`：仅保留指向这些包的软链接，不再手工复制目录
- 新拉代码、恢复工作区或怀疑链接失效时：重新执行 `scripts/link_spotmicro_workspace.sh`

> 简单说：这里是“资料总库”，`spotmicro_ws/src` 是“链接到资料总库的实际运行区”。

## 仓库结构

| 包 | 作用 |
| --- | --- |
| `ros-i2cpwmboard` | PCA9685 I2C servo 驱动，提供 `/servos_*` 话题和 `config_servos` 服务 |
| `spot_micro_motion_cmd` | C++ 主控制器 + 状态机 + 运动学库 |
| `spot_micro_walk` | Python 版步态（基于 MIT Pupper），当前仅做算法参考 |
| `spot_micro_keyboard_command` / `servo_move_keyboard` | 键盘遥控器，发布速度/事件或单个舵机命令 |
| `lcd_monitor` | ROS 状态在 I2C LCD 上显示 |
| `spot_micro_plot` | matplotlib 可视化 stick figure |
| `spot_micro_navigation` | 雷达建图、AMCL、A*/Dijkstra、DWA 与导航安全门集成 |

其余子目录为 kinematics 子库、LCD 驱动、舵机标定文档等。

## 中文指南索引
- `ORANGEPI_AI_PRO_NOETIC_DEPLOYMENT.md`：基于 2026-03 实际落地过程整理的香橙派 AI Pro + Ubuntu 22.04 + ROS1 Noetic + SpotMicro 部署总结，适合作为后续批量复刻的标准参考。
- `SpotMicro 导航方案设计.md`：围绕 RPLidar 室内导航链路给出的专项设计文档，覆盖 Hector 建图、独立 odom、AMCL、A*、局部跟踪、速度安全门、风险分析和实验计划，适合作为导航功能落地基线。
- `tf_chain_spotmicro_navigation.md`：围绕 SpotMicro 导航 TF 链给出的专项说明文档，解释 `map/odom/base_footprint/base_link/lidar_link` 的含义，并结合现有代码说明“当前谁在发 TF、后续应该谁来发”。
- `navigation_stack_runbook.md`：围绕新加入的 `spot_micro_navigation` 包给出的运行手册，覆盖雷达调试、Hector/Gmapping 建图、AMCL 定位、A*/Dijkstra 全局规划、DWA 与速度安全门的启动方式。
- `OrangePi_Jammy_Noetic_导航编译排障.md`：针对 Orange Pi Ubuntu 22.04 + ROS1 Noetic 源码工作区整理的导航编译排障手册，覆盖 `cv_bridge` / `laser_geometry` / `rviz` 缺失时的最小可落地修复路径。
- `../orangepi_ros_backup_template/README.md`：香橙派 ROS 远程备份模板入口，包含源码导出脚本、依赖清单采集脚本、恢复说明和补丁目录规范，适合把 `ros_noetic_ws` / `spotmicro_ws` 备份到远程仓库。
- `大模型与训练模型接入路线图.md`：围绕现有 SpotMicro 仓库的模型接入边界、推荐架构、阶段路线图、安全约束和实施顺序的专项设计文档，适合作为后续智能化改造的主参考。
- `servo_calibration.md`：舵机校准全过程与参考表格说明。
- `LEARNING_GUIDE.md`：学习路线与背景知识。
- `实验操作手册.md`：一步一步跑通实验程序的详细 runbook；已补充 Orange Pi Ubuntu 22.04 与双工作区避坑说明。
- `../docs/build_notes.md`：记录复刻过程中的额外构建问题（CATKIN_IGNORE、子模块、依赖安装），与 runbook 互补。


## 构建前置

1. 若是 Ubuntu 20.04 + 官方 Noetic apt 方案，安装 ROS 所需依赖：`sudo apt install python3-rosdep python3-vcstool libeigen3-dev`.
2. 若是 Orange Pi Ubuntu 22.04 + ROS1 源码编译方案，先完成 `ros_noetic_ws` 基础环境，再进入 `spotmicro_ws` 迁移本目录中的包。
3. 可选依赖：`sudo apt install doxygen python3-smbus python3-matplotlib`.
4. 初始化 workspace：`catkin init && catkin config --extend /opt/ros/$ROS_DISTRO`.

## 启动顺序（建议）

> **运行前置**：以下命令均在 Ubuntu 终端执行，且务必先 `cd ~/catkin_ws`。若 `source /opt/ros/$ROS_DISTRO/setup.bash` 报 “No such file or directory”，说明 `$ROS_DISTRO` 未设置，请手动替换为当前发行版（例如 `source /opt/ros/noetic/setup.bash`），再执行 `source ~/catkin_ws/devel/setup.bash`。每开一个新终端都要重复以上两条命令，否则 ROS 包与自定义消息无法被找到。

0. `roscore`（单独终端先启动 ROS Master，否则其余节点会连续报 `Failed to contact master`）
1. `roslaunch i2cpwm_board i2cpwm_node.launch`（包名是 `i2cpwm_board`，不是 `ros-i2cpwmboard`；未连接 PCA9685 会提示 `Failed to open I2C bus /dev/i2c-1` 属正常现象）
2. `rosrun servo_move_keyboard servoMoveKeyboard.py`（单舵机调试、确认硬件）
3. `rosrun spot_micro_keyboard_command spotMicroKeyboardMove.py` （键盘控制）
4. `rosrun spot_micro_motion_cmd spot_micro_motion_cmd_node`
5. 可选：`rosrun lcd_monitor sm_lcd_node.py`, `rosrun spot_micro_plot spotMicroPlot.py`


> **脚本/解释器提示**：如 `rosrun ... .py` 仍提示“Found ... but not executable”，请运行 `chmod +x ~/catkin_ws/src/spot_micro/<package>/scripts/*.py` 并重新 `catkin build <package>` 后再启动；若提示 `/usr/bin/python: No such file or directory`，请 `sudo apt install python-is-python3` 或将脚本首行改为 `/usr/bin/env python3`。其中 `<package>` 需替换为下列实际包名（命令可直接复制）：
```bash
chmod +x ~/catkin_ws/src/spot_micro/servo_move_keyboard/scripts/*.py
chmod +x ~/catkin_ws/src/spot_micro/spot_micro_keyboard_command/scripts/*.py
chmod +x ~/catkin_ws/src/spot_micro/lcd_monitor/scripts/*.py
chmod +x ~/catkin_ws/src/spot_micro/spot_micro_plot/scripts/*.py
catkin build servo_move_keyboard spot_micro_keyboard_command lcd_monitor spot_micro_plot
```
