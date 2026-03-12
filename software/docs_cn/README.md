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
- `servo_calibration.md`：舵机校准全过程与参考表格说明。
- `SOFTWARE_ASSESSMENT.md`：软件可靠性评估与待办。
- `LEARNING_GUIDE.md`：学习路线与背景知识。
- `实验操作手册.md`：一步一步跑通实验程序的详细 runbook（环境准备、构建、调试、排错），零基础必读。


## 构建前置

1. 安装 ROS 所需依赖：`sudo apt install python3-rosdep python3-vcstool libeigen3-dev`.
2. 可选依赖：`sudo apt install doxygen python3-smbus python3-matplotlib`.
3. 初始化 workspace：`catkin init && catkin config --extend /opt/ros/$ROS_DISTRO`.

## 启动顺序（建议）

1. `roslaunch ros-i2cpwmboard i2cpwm_node.launch`
2. `rosrun servo_move_keyboard servoMoveKeyboard.py`（单舵机调试、确认硬件）
3. `rosrun spot_micro_keyboard_command spotMicroKeyboardMove.py` （键盘控制）
4. `rosrun spot_micro_motion_cmd spot_micro_motion_cmd_node`
5. 可选：`rosrun lcd_monitor sm_lcd_node.py`, `rosrun spot_micro_plot spotMicroPlot.py`

详细调试步骤与风险见 `SOFTWARE_ASSESSMENT.md`。
