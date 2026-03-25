# OrangePi AI Pro PCA9685 测试驱动

在香橙派 AI Pro 上直接验证 PCA9685 舵机驱动板是否可通过 I2C 正常工作，**不依赖 ROS**。

## 硬件接线

```
OrangePi AI Pro 40-pin 扩展座            PCA9685 16CH PWM 板
─────────────────────────────────────────────────────────────
Pin 1  (3.3V/5V)                ->  VCC
Pin 3  (GPIO2_12 / SDA7)       ->  SDA
Pin 5  (GPIO2_11 / SCL7)       ->  SCL
Pin 6  (GND)                   ->  GND

注意: PCA9685 的 V+ (舵机电源) 需要外接 5-6V 电源，不要从 OrangePi 取电。
```

## I2C 总线映射

| 信号 | GPIO 编号 | Linux GPIO 号 | 引脚 | I2C 总线 |
|------|-----------|---------------|------|----------|
| SCL7 | GPIO2_11  | GPIO249       | Pin 5 | /dev/i2c-7 |
| SDA7 | GPIO2_12  | GPIO250       | Pin 3 | /dev/i2c-7 |

> 华为昇腾镜像中，I2C2 被映射到了 `/dev/i2c-7`，而非标准 RK3566 的 `/dev/i2c-1` 或 `/dev/i2c-2`。
> 可通过 `sudo i2ctransfer -y -f 7 w2@0x40 0x00 0x20` 和 `sudo i2ctransfer -y 7 r1@0x40` 验证 PCA9685 响应。

## 依赖安装

```bash
sudo apt update
sudo apt install python3-pip python3-smbus i2c-tools
sudo pip3 install smbus2
```

如果遇到 `ModuleNotFoundError: No module named 'smbus2'`，确认 pip 安装的是 Python3 版本：

```bash
sudo python3 -m pip install smbus2
```

## 前置检查

在运行脚本前，建议先验证硬件连通性：

```bash
# 1. 检查 I2C 总线 7 是否存在
ls /dev/i2c-7

# 2. 扫描总线 7，确认看到 0x40 (PCA9685)
sudo i2cdetect -y -f 7

# 3. 直接用 i2ctransfer 测试 PCA9685 寄存器读取
sudo i2ctransfer -y 7 r1@0x40
# 期望输出: 0x11 (MODE1 默认值) 或类似非 0xFF 值

# 4. 读取 MODE1 (0x00) 和 MODE2 (0x01)
sudo i2ctransfer -y 7 r2@0x40
# 期望: 0x11 0x04
```

如果以上都正常，脚本就能工作。

## 脚本说明

### 脚本 1：最小连通性测试

```bash
cd orangepi_pca9685_test/
sudo python3 pca9685_test.py
```

执行 16 通道完整扫频测试：中心(60deg) → 0deg → 120deg → 中心，自动停止所有舵机。

### 脚本 2：批量设置 16 路舵机角度

```bash
sudo python3 set_all_servos.py --angle 60    # 所有通道到中心 (60°)
sudo python3 set_all_servos.py --angle 0      # 所有通道到 0° 极限
sudo python3 set_all_servos.py --angle 120    # 所有通道到 120° 极限
```

### 脚本 3：单舵机角度设置

```bash
sudo python3 set_servo.py 3 90    # 舵机3 (LF_3 左前小腿) -> 90°
sudo python3 set_servo.py 1 60    # 舵机1 (LF_1 左前肩) -> 60° (中心)
sudo python3 set_servo.py 7 45    # 舵机7 (LB_1 左后肩) -> 45°
```

**编号采用 1-based**，与 ROS `i2cpwm_board` 及 `spot_micro_motion_cmd.yaml` 中的 `num` 字段一致。

舵机编号与关节对应关系：

| 编号 | YAML 名称 | 位置 |
|------|-----------|------|
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

## 舵机型号与参数

本项目使用 **PDI-HV5523MG** 舵机：

| 参数 | 值 |
|------|----|
| 旋转角度 | 120° |
| 脉宽范围 | 900–2100 µs |
| 中心脉宽 | 1500 µs (60°) |
| 工作电压 | 6.0–8.4V |
| 扭力 | 19.2 kg·cm (6V) |

> **安全警告**：所有脚本参数均按 PDI-HV5523MG 配置（900–2100 µs / 120°）。如果使用其他型号舵机，**必须修改脚本中的 `SERVO_MIN_US`、`SERVO_MAX_US` 常量**，否则可能导致舵机堵转过热甚至烧毁。

## 与 ROS 驱动的对接

香橙派运行完整 ROS 的步骤：

```bash
# 1. 安装 ROS Noetic (ARM64)
# 参考: http://wiki.ros.org/noetic/Installation/Ubuntu

# 2. 创建 catkin 工作空间
mkdir -p ~/catkin_ws/src
cd ~/catkin_ws/src
source /opt/ros/noetic/setup.bash
catkin_init_workspace

# 3. 复制软件包
cp -r <spotMicro-Chinese>/software_orangepiaipro/extensions/packages/* ~/catkin_ws/src/
cp -r <spotMicro-Chinese>/software_orangepiaipro/ros-i2cpwmboard ~/catkin_ws/src/

# 4. 编译
cd ~/catkin_ws
catkin_make

# 5. 启动节点
source devel/setup.bash
roscore &
roslaunch i2cpwm_board i2cpwm_node.launch    # 驱动节点
rosrun spot_micro_motion_cmd spot_micro_motion_cmd_node
```

**重要**：`i2cpwm_node.launch` 中已配置 `i2c_bus=/dev/i2c-7`，无需额外修改。
