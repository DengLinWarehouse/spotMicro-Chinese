# SpotMicro Standalone 栈

该目录将原“软件部分” catkin 工作区重构为一个纯 Python 包，在 **Linux** 与
**Windows** 上均可无 ROS 运行。我们复用原有的运动学、步态与控制逻辑，只是把
ROS 的话题/服务换成了轻量级运行时、硬件抽象与键盘输入环路。

## 目录结构

```
software_standalone/
├── pyproject.toml                # PEP‑621 元信息、依赖与命令入口
├── README.md                     # 当前文件
└── spotmicro_standalone/         # 可安装的 Python 包
    ├── apps/                     # 命令行入口（当前提供 teleop）
    ├── config/                   # 默认 YAML + 加载器
    ├── hardware/                 # 舵机板驱动抽象
    ├── interfaces/               # 键盘/输入接口
    ├── runtime/                  # 无 ROS 的运行调度
    ├── pupper/, pupper_src/,     # 原 MIT Pupper 步态/控制逻辑
    │   first_order_filter/, spot_micro_kinematics/  # 运动学&滤波库
```

## 快速上手

```bash
cd software_standalone
python -m venv .venv && . .venv/bin/activate   # Windows 运行 `.\.venv\Scripts\activate`
pip install --upgrade pip
pip install -e .                                # 开发态安装
# 若在 Linux + PCA9685 实机运行，还需：
pip install '.[hardware]'

# 启动键盘遥控（默认使用 mock 后端）
spotmicro-teleop
# 若 PowerShell 未能识别命令，可改为：
python -m spotmicro_standalone.apps.teleop --backend mock --log-level INFO
```

键盘映射（Win/Linux 相同）：

| 键位 | 功能 |
| --- | ---- |
| `w` / `s` | 增/减前进速度 |
| `a` / `d` | 向左/右平移 |
| `q` / `e` | 向左/右偏航 |
| `r` / `f` | 升高/降低机身 |
| `t` / `g` | 前后俯仰 |
| `y` / `h` | 左右翻滚 |
| `space` | 触发/切换快步模式 |
| `enter` | 待机唤醒/站立 |
| `c` | 清零所有速度/角度 |
| `esc` | 退出程序 |

## 硬件后端配置

所有几何、舵机、步态与键盘参数保存在 `spotmicro_standalone/config/default.yaml`
。可复制该文件，修改舵机映射或按键步进，再通过 `--config` 指向自定义版本：

```bash
spotmicro-teleop --config my_spotmicro.yaml
```

YAML 中的 `hardware` 区块用于选择后端：

```yaml
hardware:
  backend: mock      # 或 pca9685
  i2c_bus: 1         # Linux I2C 总线号
  i2c_address: 64    # 十进制地址（64 == 0x40）
  pwm_frequency: 50  # Hz
```

当 `backend=mock` 时仅打印 PWM 命令，适合无硬件开发。切换到 `pca9685` 会启用
`hardware/board.py` 中的底层驱动，通过 `smbus2` 与舵机板通信（需
`pip install '.[hardware]'`）。运行时会按照原 ROS 参数表中的标定信息自动把关节
角转换为 PWM，无需 ROS 服务。

## 与原 ROS 节点对应关系

| 原 ROS 包 | Standalone 对应模块 |
| --------- | -------------------- |
| `spot_micro_motion_cmd` | `runtime/teleop.py` + `hardware/servo_driver.py` |
| `spot_micro_walk` | 直接复用（`pupper*`, `spot_micro_kinematics`） |
| `ros-i2cpwmboard` | `hardware/board.py`（PCA9685 实现） |
| `spot_micro_keyboard_command` / `servo_move_keyboard` | `interfaces/keyboard.py` |
| `spot_micro_plot` | 视需要调用 `spot_micro_kinematics`（安装 plot 额外依赖） |

由于已不依赖 ROS 话题/服务，整个控制环路仅在一个 Python 进程内完成。
`config/loader.py` 会读取 `spot_micro_motion_cmd/config/spot_micro_motion_cmd.yaml`
中全部参数，因此所有调参仍然集中在一个 YAML 文件中。为保证回归安全，原运动学
与步态库（`pupper`, `spot_micro_kinematics` 等）保持原貌，只移除了强制的
`matplotlib` 引用。

## 后续可做的事

- 若需要绘图/标定界面，可增加 CLI 子命令，复刻 `spot_micro_plot`、
  `servo_move_keyboard` 的功能。
- 为配置加载器与舵机驱动补充更多单元测试（`pyproject.toml` 中已包含 pytest
  依赖）。
- 想接入除键盘外的输入（如手柄、UDP 指令、IMU），可在 `interfaces/` 下新增类，
  通过 `KeyboardCommandState` 数据类传递，易于热插拔。
