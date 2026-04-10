# SpotMicro 软件全流程操作手册（2026-03 修订）

> **目标**：让零经验的新手在一次操作内成功搭建、校准并运行 `spotMicro-Chinese/软件部分`。  
> **适配环境**：Raspberry Pi 4B（4 GB/8 GB）+ Ubuntu 20.04.6 LTS 64-bit（强烈推荐）。  
> **说明**：若坚持 Debian/Raspberry Pi OS 或 Ubuntu 24.04，请参见附录 B，了解需要额外执行的源码编译步骤。

---

## 1. 型号与版本要求

| 分类 | 推荐型号/版本 | 备注 |
| --- | --- | --- |
| **主控** | Raspberry Pi 4 Model B (4 GB+) | 需 64-bit OS，USB-C 5 V/3 A 供电 |
| **操作系统** | Ubuntu 20.04.6 LTS 64-bit（Server 或 Desktop） | 预装 SSH/网络工具，初始登录后立即 `sudo apt update && sudo apt upgrade -y` |
| **ROS** | **ROS1** Noetic (`ros-noetic-ros-base`) | 由官方 apt 仓库提供，仅支持 Ubuntu 20.04；ROS2 请另行选择 Jazzy/其他版本并自行适配 |
| **舵机驱动** | PCA9685 I2C 16 通道板（Adafruit 兼容） | I2C 地址默认 0x40，可通过焊接修改 |
| **舵机** | 12 × MG996R / DS3218 或同规格大扭矩舵机 | 保证力矩一致，供电与主控地线共用 |
| **电源** | 舵机侧 2S~3S 锂电 + 高电流 BEC 或 6 V 大电流稳压 | 瞬时电流≥10 A，主控侧独立供电 |
| **可选外设** | 16×2 I2C LCD（地址 0x27）、HDMI 显示器、USB 键盘 | 用于状态显示与调试 |

**为什么一定要 Ubuntu 20.04？**  
`spot_micro_motion_cmd` 等所有包均为 ROS1/catkin。ROS Noetic 官方只支持 Ubuntu 20.04，24.04 并无 ROS1 apt 仓库。若使用其他系统，需要自行源码编译 ROS（成本高且易出错），因此默认手册仅针对 20.04。

---

## 2. 安装与初始化流程（必做）

### 2.1 刷机与基础配置
1. 使用 Raspberry Pi Imager 选择 **Ubuntu Server 20.04.6 LTS (64-bit)**。
2. 烧录 TF 卡并设置默认用户名/密码、Wi-Fi（如需）及 SSH。
3. 首次开机后，连入网络，执行：
   ```bash
   sudo apt update
   sudo apt upgrade -y
   sudo reboot
   ```
4. 验证 OS 版本：`lsb_release -a` 应显示 `Ubuntu 20.04.x LTS (focal)`。

### 2.2 添加 ROS 官方仓库
```bash
sudo apt install curl gnupg lsb-release -y
sudo mkdir -p /usr/share/keyrings
curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc \
     | sudo tee /usr/share/keyrings/ros-archive-keyring.gpg >/dev/null
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros/ubuntu $(lsb_release -sc) main" \
| sudo tee /etc/apt/sources.list.d/ros1-latest.list >/dev/null
sudo apt update
```

### 2.3 安装 ROS Noetic 及常用工具
```bash
sudo apt install ros-noetic-ros-base python3-rosdep python3-vcstools \
     python3-catkin-tools python3-rosinstall python3-rosinstall-generator \
     build-essential git curl libeigen3-dev python3-venv python3-pip -y
echo "source /opt/ros/noetic/setup.bash" >> ~/.bashrc
source /opt/ros/noetic/setup.bash
```

### 2.4 初始化 rosdep（国内镜像）
```bash
sudo rosdep init
sudo mkdir -p /etc/ros/rosdep/sources.list.d
sudo tee /etc/ros/rosdep/sources.list.d/20-default.list >/dev/null <<'EOF'
yaml https://mirrors.tuna.tsinghua.edu.cn/rosdistro/rosdep/base.yaml
yaml https://mirrors.tuna.tsinghua.edu.cn/rosdistro/rosdep/python.yaml
yaml https://mirrors.tuna.tsinghua.edu.cn/rosdistro/rosdep/ruby.yaml
EOF
rosdep update
```
> 若镜像暂时不可用，可临时设置 `https_proxy`，或换用中科大/阿里云镜像。

---

## 3. 工作区与代码准备

1. 创建 catkin 工作区：
   ```bash
   mkdir -p ~/spotmicro_ws/src
   cd ~/spotmicro_ws/src
   ```
2. 将 `spotMicro-Chinese/软件部分` 复制或克隆进入 `src`：
   ```bash
   git clone <你的仓库地址> spotmicro_software
   ```
3. 返回工作区根：
   ```bash
   cd ~/spotmicro_ws
   ```
4. 安装依赖并构建：
   ```bash
   rosdep install --from-paths src --ignore-src -r -y
   catkin init
   catkin config --extend /opt/ros/noetic
   catkin build
   source devel/setup.bash
   echo "source ~/spotmicro_ws/devel/setup.bash" >> ~/.bashrc
   ```
5. 检查环境变量：新开终端运行 `echo $ROS_DISTRO`，应显示 `noetic`。

---

## 4. 舵机校准与硬件连线

### 4.1 供电与连线检查
- 将 PCA9685 接到树莓派 I2C（SDA=GPIO2, SCL=GPIO3），确认 `sudo raspi-config` 中启用 I2C。
- 舵机供电独立，GND 与树莓派 GND 共用；切勿直接用 Pi 5 V 输出驱动舵机。
- I2C LCD（如有）连接至同一总线，默认地址 0x27。

### 4.2 舵机校准流程（节选自 `../02_标定与运动/servo_calibration.md`）
1. 启动 PCA9685 驱动：
   ```bash
   roslaunch ros-i2cpwmboard i2cpwm_node.launch
   ```
2. 运行舵机键盘工具：
   ```bash
   rosrun servo_move_keyboard servoMoveKeyboard.py
   ```
3. 进入 `oneServo` 模式，依次校准 12 个舵机，记录 0°/±90°（Link1 用 ±45°）的 PWM 值。
4. 将记录填写进《../02_标定与运动/舵机校准参考表格.ods》，再把粗体结果同步至 `spot_micro_motion_cmd/config/spot_micro_motion_cmd.yaml`。
5. 舵机安装时保持通电且命令在中心，确保物理中立位一致。

---

## 5. 节点启动顺序

1. **舵机驱动**（必须常驻）  
   `roslaunch ros-i2cpwmboard i2cpwm_node.launch`
2. **舵机调试（按需）**  
   `rosrun servo_move_keyboard servoMoveKeyboard.py`
3. **键盘控制器**  
   `rosrun spot_micro_keyboard_command spotMicroKeyboardMove.py`
   - 模式指令：`walk`/`stand`/`idle`/`angle_cmd`
   - 控制键：`w/a/s/d`（线速度）、`q/e`（偏航）、`f`（复位）、`u`（退出模式）
4. **主控状态机**  
   `roslaunch spot_micro_motion_cmd spot_micro_motion_cmd.launch`
5. **可选监控**  
   - LCD：`rosrun lcd_monitor sm_lcd_node.py`
   - 3D Plot：`rosrun spot_micro_plot spotMicroPlot.py`

> **提示**：务必在 `spot_micro_motion_cmd` 之前启动 PCA9685 节点，否则 `config_servos` 调用会失败并导致主节点退出。

---

## 6. 常见错误与排查

| 问题 | 触发条件 | 解决方案 |
| --- | --- | --- |
| `Unable to locate package ros-noetic-ros-base` | OS 不是 Ubuntu 20.04 | 重刷 20.04 或按照附录 B 源码编译 |
| `E: The repository ... noble Release` | 在 24.04 添加了 ROS1 源 | 删除 `/etc/apt/sources.list.d/ros1-latest.list`，改用 20.04 |
| `rosdep init` 超时 | 无法访问 GitHub | 使用镜像或代理，重新执行 `rosdep update` |
| `rosdep install --from-paths src` 提示 path 不存在 | 当前目录不是 catkin 根 | `cd ~/spotmicro_ws` 后再执行 |
| 运行键盘节点时机器人跳动 | 舵机方向/中心未校准 | 重新按 `../02_标定与运动/servo_calibration.md` 调整并更新 YAML |
| `spot_micro_motion_cmd` 无输出 | 未接收 `/walk_cmd` 或 `/speed_cmd` | 确认键盘节点是否运行、话题是否更新 |
| LCD 节点崩溃 | 未连接 I2C LCD | 若无 LCD，直接跳过，不要启动 |

---

## 7. 验证清单

1. `rostopic list` 包含 `/servos_absolute`、`/servos_proportional`、`/sm_state`、`/speed_cmd` 等。
2. `rostopic echo /sm_state` 可看到 Idle ↔ Stand ↔ Walk 的状态切换。
3. `rostopic echo /servos_absolute`：命令范围约 80~530，变化与键盘输入一致。
4. 机器人抬离地面运行 ≥5 分钟无异常噪音、无过流保护。
5. 舵机冷态至热态变化后仍能回到 YAML 中的中心位置。

---

## 8. 版本升级建议

- 若后续引入 IMU/视觉，请另建节点发布 `/angle_cmd` 或 `/speed_cmd`，保持现有接口。
- 可将常用命令写入 `~/spotmicro_ws/scripts/bringup.sh`（内含 `source` + 各节点启动），避免重复输入。
- 使用 `rosbag record /sm_state /servos_absolute /body_state` 保存调试数据，便于离线分析。

---

## 附录 A：参考文件
- `README.md`：简要构建与启动顺序。
- `../02_标定与运动/servo_calibration.md`：舵机校准图示与步骤。
- `SOFTWARE_ASSESSMENT.md`：2026-03 体检报告，列出了遗留问题及修复路线。

---

## 附录 B：在非 Ubuntu 20.04 环境运行

### B1. Ubuntu 24.04 (Noble)
1. 删除 ROS1 apt 源：`sudo rm /etc/apt/sources.list.d/ros1-latest.list`。
2. 参照官方文档源码编译 ROS Noetic，或改用 ROS2 Jazzy 并重构全部节点。
3. 源码编译概述：  
   ```
   sudo apt install python3-rosdep python3-rosinstall-generator python3-wstool build-essential cmake
   sudo rosdep init && rosdep update
   mkdir -p ~/ros_catkin_ws && cd ~/ros_catkin_ws
   rosinstall_generator ros_base --rosdistro noetic --deps --tar > noetic.rosinstall
   wstool init src noetic.rosinstall
   rosdep install --from-paths src --ignore-src -r -y --rosdistro noetic
   ./src/catkin/bin/catkin_make_isolated --install
   source ~/ros_catkin_ws/install_isolated/setup.bash
   ```
4. 编译完成后再回到 `~/spotmicro_ws` 执行 `catkin build`。如需 ROS2，请重新设计所有包以适配 `rclcpp`/`rclpy`。

### B2. Raspberry Pi OS (Debian)
- 同样需要源码编译 ROS Noetic，且部分系统包需从 backports 获得；官方教程详见 `wiki.ros.org/noetic/Installation/Debian`.
- 建议仅在熟悉 Debian 打包的用户尝试，普通用户直接使用 Ubuntu 20.04 更稳妥。

---

**最后提醒**：任何“Unable to locate package”或 `rosdep` 找不到依赖的情况，优先检查系统/ROS 版本是否符合本文要求；不要混用 Noble/Focal 的源。按本手册逐项执行，可最大限度避免重复踩坑。祝调试顺利！
