# Raspberry Pi PCA9685 Test Driver

该目录用于在树莓派上直接验证 `PCA9685` 舵机驱动板是否可通过 I2C 正常工作，不依赖 ROS。

当前包含三个脚本：

- `pca9685_test.py`：最小连通性测试，用于确认板卡是否能被初始化。
- `set_all_servos.py`：将 16 路通道一次性设置到同一个角度，适合做批量归位和硬件通电检查。
- `set_servo.py`：将指定单个舵机设置到指定角度，编号与 ROS `i2cpwm_board` 及 YAML 配置一致（1-based），适合逐路舵机标定和故障排查。

## 舵机型号与参数

本项目使用 **PDI-HV5523MG** 舵机，关键参数如下：

| 参数 | 值 | 说明 |
| --- | --- | --- |
| 旋转角度 | **120°** | 总行程，中心向每侧各 60° |
| 脉宽范围 | **900–2100 µs** | 0° 对应 900 µs，120° 对应 2100 µs |
| 中心脉宽 | 1500 µs | 对应 60°，PCA9685 PWM ≈ 307 |
| 工作电压 | 6.0–8.4V | 请确保 LiPo 输出在此范围内 |
| 扭力 | 19.2 kg·cm (6V) / 23 kg·cm (8.4V) | |
| 速度 | 0.18 sec/60° (6V) / 0.16 sec/60° (8.4V) | |
| 死区 | 2 µs | |

> **⚠ 舵机型号警告**：所有脚本的脉宽和角度参数均按 PDI-HV5523MG 配置（900–2100 µs / 120°）。如果你使用的是其他型号（如常见 180° 舵机，通常为 500–2500 µs），**必须修改脚本中的 `SERVO_MIN_US`、`SERVO_MAX_US` 和 `SERVO_ANGLE_RANGE` 常量**，否则可能导致舵机堵转过热甚至烧毁。

## 适用场景

在进入 `spotMicro-Chinese` 的 ROS 调试之前，建议先用这里的脚本确认以下事项：

- `/dev/i2c-1` 可访问。
- `i2cdetect -y 1` 能扫描到 `0x40`。
- PCA9685 可以稳定输出 PWM。
- 舵机电源、共地和接线没有问题。

如果这里都不通，ROS 侧的 `i2cpwm_board` 也不会正常工作。

## 依赖安装

```bash
sudo apt update
sudo apt install python3-pip python3-smbus i2c-tools
sudo pip3 install adafruit-blinka adafruit-circuitpython-pca9685
```

如果你在 `conda` 环境中运行，也需要在当前解释器里安装这些依赖；否则常见报错会是：

- `ModuleNotFoundError: No module named 'board'`
- `ModuleNotFoundError: No module named 'RPi'`

最省事的方式是直接使用系统 Python：

```bash
sudo python3 set_all_servos.py --angle 60
```

## I2C 前置检查

1. 在树莓派中启用 I2C：
   `sudo raspi-config -> Interface Options -> I2C -> Enable`
2. 确认当前用户已加入 `i2c`/`dialout` 组：
   ```bash
   sudo usermod -a -G i2c,dialout $USER
   ```
   执行后需要重新登录或重启。
3. 确认设备节点与地址存在：
   ```bash
   ls /dev/i2c-1
   sudo i2cdetect -y 1
   ```

正常情况下应看到 `0x40`。

如果出现以下情况：

- `PermissionError: [Errno 13] Permission denied: '/dev/i2c-1'`
  说明当前用户没有 I2C 访问权限，临时可用 `sudo`，长期建议加入 `i2c` 组。
- `ValueError: No I2C device at address: 0x40`
  说明脚本没有找到目标板卡，先检查供电、SDA/SCL、地址拨码和 `i2cdetect` 结果。

## 接线要求

- 树莓派 `GPIO2(SDA)` -> PCA9685 `SDA`
- 树莓派 `GPIO3(SCL)` -> PCA9685 `SCL`
- 树莓派 `GND` 与 PCA9685/舵机电源 `GND` 共地
- 舵机电源单独供给 PCA9685 的 `V+`

不要直接用树莓派 5V 给多路舵机供电。

## 脚本 1：最小连通性测试

> **提示**：本目录的脚本**不需要 ROS 环境**，无需执行 `source /opt/ros/noetic/setup.bash`。只要 cd 到本目录即可运行。

```bash
cd <本目录的路径>/raspi_pca9685_test
sudo python3 pca9685_test.py
```

该脚本适合确认：

- I2C 可初始化
- PCA9685 地址正确
- 板卡能接受基础 PWM 设置

## 脚本 2：批量设置 16 路舵机角度

`set_all_servos.py` 当前支持命令行参数：

```bash
sudo python3 set_all_servos.py --angle 60       # 所有通道到中心 (60°)
sudo python3 set_all_servos.py --angle 0         # 所有通道到 0° 极限
sudo python3 set_all_servos.py --angle 120       # 所有通道到 120° 极限
```

参数说明：

- `--angle`：目标角度，范围 `0–120`（PDI-HV5523MG 总行程 120°，60° 为中心）
- `--address`：PCA9685 I2C 地址，默认 `0x40`

示例输出：

```text
Set all 16 channels to 60.0° (~1500 µs, duty 0x1999) at address 0x40
```

## 脚本 3：单舵机角度设置

`set_servo.py` 用于将指定编号的舵机设置到指定角度，不影响其他舵机的当前状态。

**编号采用 1-based**，与 ROS `i2cpwm_board` 及 `spot_micro_motion_cmd.yaml` 中的 `num` 字段一致，脚本内部自动减 1 映射到 PCA9685 硬件通道。

```bash
sudo python3 set_servo.py <舵机编号> <角度>
```

舵机编号与关节对应关系（与 `spot_micro_motion_cmd.yaml` 的 `num` 一致）：

| 编号 | YAML 名称 | 位置 |
| --- | --- | --- |
| 1 | LF_1 | 左前肩 |
| 2 | LF_2 | 左前大腿 |
| 3 | LF_3 | 左前小腿 |
| 4 | RF_1 | 右前肩 |
| 5 | RF_2 | 右前大腿 |
| 6 | RF_3 | 右前小腿 |
| 7 | LB_1 | 左后肩 |
| 8 | LB_2 | 左后大腿 |
| 9 | LB_3 | 左后小腿 |
| 10 | RB_1 | 右后肩 |
| 11 | RB_2 | 右后大腿 |
| 12 | RB_3 | 右后小腿 |

示例：

```bash
sudo python3 set_servo.py 3 90           # 舵机3 (LF_3 左前小腿) -> 90°
sudo python3 set_servo.py 1 60           # 舵机1 (LF_1 左前肩) -> 60° (中心)
sudo python3 set_servo.py 7 45           # 舵机7 (LB_1 左后肩) -> 45°
```

参数说明：

- `servo`（位置参数）：舵机编号，范围 `1–16`（SpotMicro 使用 1–12）
- `angle`（位置参数）：目标角度，范围 `0–120`
- `--address`：PCA9685 I2C 地址，默认 `0x40`

示例输出：

```text
Servo 3 [LF_3  左前小腿] -> 90.0° (~1800 µs, duty 0x1C28, hw_ch=2) at address 0x40
```

> **安全提示**：编号超出 1–16 会直接报错退出；角度超出 0–120 会被 clamp 并打印警告。

## 与 ROS 驱动的关系

这个目录只是硬件级验证工具，不负责：

- ROS 话题/服务通信
- 步态控制

这些能力由 `spotMicro-Chinese/software/ros-i2cpwmboard` 和 `spotMicro-Chinese/software/spot_micro_motion_cmd` 提供。

ROS 侧的 `i2cpwm_board` 和 `spot_micro_motion_cmd` 全程使用 PCA9685 原始 PWM 值（0–4096），不涉及脉宽常量。对于 PDI-HV5523MG 舵机，有效 PWM 范围约为 **184–430**（对应 900–2100 µs），中心值约 **307**（对应 1500 µs）。使用 `servo_move_keyboard` 标定时请勿超出此范围。

建议调试顺序：

1. 先用本目录脚本确认 `0x40`、供电和 PWM 正常（无需 ROS）。
2. 再进入 ROS 工作区（每个终端都要执行初始化，详见 `spotMicro-Chinese/software/docs_cn/实验操作手册.md`）：
   ```bash
   cd <你的catkin_ws路径> && source /opt/ros/noetic/setup.bash && source devel/setup.bash
   ```
   然后运行 `roscore`、`i2cpwm_board`、`servo_move_keyboard`。
3. 最后再跑 `spot_micro_motion_cmd` 做站立和步态测试。
