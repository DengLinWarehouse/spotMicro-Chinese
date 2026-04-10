# 舵机校准指南

本文档提供了一份完整指南，帮助你在 Spot Micro 机体上校准舵机，并生成 ROS 控制软件所需的舵机配置字典。仓库内包含名为《舵机校准参考表格.ods》的电子表格，可辅助计算舵机配置值。

> **深入理解**：如果你想了解 YAML 参数的数学推导过程、IK 源码分析、以及标定结果的正确性验证，请阅读 [舵机标定计算说明](舵机标定计算说明.md)。

舵机配置字典存放于 `spot_micro_motion_cmd.yaml`，示例如下：
```yaml
num_servos: 12
servo_max_angle_deg: 55.0    # PDI-HV5523MG: 120° total (±60° from center), 5° safety margin
# Wiring: LF(1-3) -> RF(4-6) -> LB(7-9) -> RB(10-12), per leg: HIP -> UPPER -> LOWER
LF_1: {num: 1,  center: 306, range: 389, direction:  1, center_angle_deg:  -7.6}
LF_2: {num: 2,  center: 306, range: 397, direction:  1, center_angle_deg:  38.6}
LF_3: {num: 3,  center: 306, range: 387, direction:  1, center_angle_deg: -82.8}
RF_1: {num: 4,  center: 306, range: 396, direction: -1, center_angle_deg:  -5.4}
...
```

舵机命名由腿位置缩写加编号组成："RF" 表示右前腿、"RB" 表示右后腿，左腿分别为 "LF""LB"。数字 1 对应 Link 1（髋关节），2 对应 Link 2（大腿/肩关节），3 对应 Link 3（小腿/膝关节）。

接线顺序为 **左前(1-3) → 右前(4-6) → 左后(7-9) → 右后(10-12)**，每条腿内部按 **肩→大腿→小腿** 排列。

## 舵机配置字段说明
* **num_servos**：本平台固定为 12 个舵机。

* **servo_max_angle_deg**：舵机单侧允许的最大命令角度。本项目使用 PDI-HV5523MG 舵机，总行程为 **120°**（中心左右各 ±60°），设为 **55.0°** 留有 5° 安全余量。如果你使用 180° 舵机（±90°），可适当增大此值（如 82.5°），但 **不得超过舵机实际单侧行程**，否则会导致堵转损坏。

* **num**：舵机接入 PCA9685 板的端口（编号 1–16）。

* **center**：对应舵机中心位置的原始 PWM 值。PCA9685 以 12 bit PWM 表示 20 ms 周期脉宽：0 表示无脉冲，4096 表示常高，2048 约等于 10 ms。PDI-HV5523MG 的中心脉宽为 1500 µs，对应 PWM ≈ **307**。使用 `servo_move_keyboard` 将舵机拨到中心，保证双向行程相等。
  > **PDI-HV5523MG 安全范围**：有效 PWM 范围约 **184–430**（对应 900–2100 µs / 0°–120°），标定时切勿超出此范围。

* **range**：覆盖最大正负角范围的原始 PWM 差值，相当于 +θ 与 -θ 两点 PWM 的差。电子表格会自动计算该值并与 `servo_max_angle_deg` 对应。

* **direction**：取 1 或 -1，根据各关节坐标系决定是否翻转舵机旋转方向，由表格计算。

* **center_angle_deg**：舵机位于中心 PWM 时的关节角度（各自坐标系下），由表格计算。

## 舵机安装
建议在舵机通电并命令到中心位置时安装，使关节处于"中立"姿态，保证常用动作附近拥有最大行程。下图演示了中心姿态示例：

![Side View Neutral Positions](assets/1_robot_right_links.png)
![Back View Neutral Positions](assets/12_robot_back_overview.png)

## 使用 `servo_move_keyboard` 校准单个舵机
连接好 PCA9685 与舵机后，按照以下步骤校准：

> **★ 每个终端都要先执行初始化**（或使用别名 `spot`，详见 `../01_环境部署/实验操作手册.md`）：
> ```bash
> cd <你的catkin_ws路径> && source /opt/ros/noetic/setup.bash && source devel/setup.bash
> ```

1. 终端 1 — 启动驱动节点：
   ```bash
   [初始化]
   roscore
   ```
2. 终端 2 — 启动驱动节点：
   ```bash
   [初始化]
   rosrun i2cpwm_board i2cpwm_board
   ```
3. 终端 3 — 启动校准工具：
   ```bash
   [初始化]
   rosrun servo_move_keyboard servoMoveKeyboard.py
   ```
3. 根据提示输入 `oneServo` 进入单舵机模式。
4. 输入要控制的 PCA9685 端口号（例如 2）。选定后其它舵机会空转，便于手动移动。终端会出现如下提示界面：

![Servo move prompt](assets/servo_move_prompt.png)

5. 常用按键：`y` 发送中心值（默认 PWM=306）、`g/j` 以 1 为步进递减/递增、`f/k` 以 10 为步进、`t/u` 快速到最小/最大值（默认 83/520，可在提示中修改）。终端实时打印当前 PWM。
6. 记录参考姿态的 PWM 值并填入表格，按 `q` 退出当前舵机，返回步骤 3 选择下一只。

## 生成舵机配置值
只凭目测即可获得较好结果，也可用手机倾角仪辅助（例如 Link 1 使用 45° 参考）。建议将机器人架空，让腿部自由下垂。调试时把连杆视作关节轴之间的直线，而非 3D 打印件外壳。

电子表格流程：为每个连杆记录两个参考角度（如 0° 与 90°）对应的 PWM，表格即可计算斜率与范围。各舵机斜率应接近，若差异很大说明测量出错。

![Servo Calibration Spreadsheet](assets/servo_calibration_spreadsheet.png)

### 右侧腿 Link 2 与 Link 3

**一致性比绝对精度更重要。**

1. 参考坐标系如图所示：
   ![Right side zero degree positions](assets/2_right_straight_links.png)
   Link 3 角度相对于 Link 2（见下图）：
   ![Example right side link 3 angles](assets/3_right_link_angles_example.png)
2. Link 2：命令到 0° 和 -90°，记录 PWM（见 `assets/4_right_link2_config_step_1.png` 与 `assets/4_right_link2_config_step_2.png`）。
3. Link 3：先手动让 Link 2 竖直，再命令 Link 3 到 0° 和 +90°，记录 PWM（见 `assets/5_right_link3_config_step_1.png`、`assets/6_right_link3_config_step_2.png`）。
4. 另一条右腿重复以上步骤。

### 左侧腿 Link 2 与 Link 3

左腿坐标方向不同（`assets/7_robot_left_overview.png`）。

1. Link 2：命令 0° 与 +90°，记录 PWM（`assets/8_left_link2_config_step_1.png`、`assets/9_left_link2_config_step_2.png`）。
2. Link 3：将 Link 2 竖直，命令 0° 与 -90°，记录 PWM（`assets/10_left_link3_config_step_1.png`、`assets/11_left_link3_config_step_2.png`）。
3. 两条左腿都需完成上述步骤。

### 左右腿 Link 1

后视坐标系见 `assets/12_robot_back_overview.png` 和 `assets/13_robot_back_angle_directions.png`。由于机械限制，采用 0° 与 45° 作为参考：

- 右腿：0°、-45°（`assets/14_right_link1_config_step_1.png`、`assets/15_right_link1_config_step_2.png`）
- 左腿：0°、+45°（`assets/16_left_link1_config_step_1.png`、`assets/17_left_link1_config_step_2.png`）

## 完成校准

完成所有腿部舵机的两点测量后，将电子表格中标粗的最终结果复制到 `spot_micro_motion_cmd.yaml` 的舵机配置字典中，即可供 ROS 控制软件使用。

如果同时使用 standalone 版本，请同步更新 `software_standalone/spotmicro_standalone/config/default.yaml` 中的对应字段。

## 舵机型号兼容性提醒

本项目所有配置和脚本均针对 **PDI-HV5523MG** 舵机校准：

| 参数 | PDI-HV5523MG | 常见 180° 舵机 |
| --- | --- | --- |
| 旋转角度 | 120° | 180° |
| 脉宽范围 | 900–2100 µs | 500–2500 µs |
| PCA9685 有效 PWM | 184–430 | 102–512 |
| servo_max_angle_deg | 55.0 (±60° 减 5° 余量) | 82.5 (±90° 减 7.5° 余量) |

**更换舵机型号时，必须同步修改以下位置的参数：**

1. `spot_micro_motion_cmd.yaml` → `servo_max_angle_deg`
2. `software_standalone/.../default.yaml` → `servo_max_angle_deg`
3. `SERVO_PAC9685/raspi_pca9685_test/` 下所有脚本的 `SERVO_MIN_US`、`SERVO_MAX_US`、`SERVO_ANGLE_RANGE`
4. 标定时的 PWM 安全范围上下界

**使用不匹配的参数可能导致舵机堵转过热、齿轮损坏或电路烧毁。**
