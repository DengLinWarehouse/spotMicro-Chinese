# 软件部分

该目录即一个标准的 catkin 工作空间（src 根目录）。已经将顶层 `CMakeLists.txt` 修改为通用的 `catkin_workspace()` 模式，可直接在 ROS Kinetic/Melodic/Noetic 中使用：

```bash
cd <your_catkin_ws>
catkin config --extend /opt/ros/$ROS_DISTRO
catkin build    # 或 catkin_make
```

## 仓库结构

| 包 | 作用 |
| --- | --- |
| `ros-i2cpwmboard` | PCA9685 I2C servo 驱动，提供 `/servos_*` 话题和 `config_servos` 服务 |
| `spot_micro_motion_cmd` | C++ 主控制器 + 状态机 + 运动学库 |
| `spot_micro_walk` | Python 版步态（基于 MIT Pupper），当前仅做算法参考 |
| `spot_micro_keyboard_command` / `servo_move_keyboard` | 键盘遥控器，发布速度/事件或单个舵机命令 |
| `lcd_monitor` | ROS 状态在 I2C LCD 上显示 |
| `spot_micro_plot` | matplotlib 可视化 stick figure |

其余子目录为 kinematics 子库、LCD 驱动、舵机标定文档等。

## 中文指南索引
- `机器狗组装与舵机初始值设置.md`：装配前如何给 12 个舵机设置预装角度，解决“大腿/小腿总是装在危险区”的问题，建议先读。
- `servo_calibration.md`：舵机校准全过程与参考表格说明。
- `SOFTWARE_ASSESSMENT.md`：软件可靠性评估与待办。
- `LEARNING_GUIDE.md`：学习路线与背景知识。
- `实验操作手册.md`：一步一步跑通实验程序的详细 runbook（环境准备、构建、调试、排错），零基础必读。
- `../docs/build_notes.md`：记录复刻过程中的额外构建问题（CATKIN_IGNORE、子模块、依赖安装），与 runbook 互补。


## 构建前置

1. 安装 ROS 所需依赖：`sudo apt install python3-rosdep python3-vcstool libeigen3-dev`.
2. 可选依赖：`sudo apt install doxygen python3-smbus python3-matplotlib`.
3. 初始化 workspace：`catkin init && catkin config --extend /opt/ros/$ROS_DISTRO`.

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
