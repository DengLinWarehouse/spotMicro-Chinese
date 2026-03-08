# SpotMicro Standalone – 使用与运行命令

本文位于 `spotmicro_standalone/docs/`，介绍如何在 Windows 或 Linux 上安装、
配置并启动无需 ROS 的运行时。

---

## 1. 环境搭建

| 步骤 | Windows (PowerShell) | Linux / macOS (bash) | 备注 |
| ---- | -------------------- | -------------------- | ---- |
| 创建虚拟环境 | `python -m venv .venv` | `python3 -m venv .venv` | Python 需 ≥ 3.10 |
| 激活 | `.\.venv\Scripts\activate` | `source .venv/bin/activate` | 终端应出现 `(spotmicro)` |
| 升级 pip | `python -m pip install --upgrade pip` | 同左 | 避免老旧安装器 |
| 安装项目 | `pip install -e .` | 同左 | 开发态可编辑安装 |
| 可选：硬件依赖 | `pip install '.[hardware]'` | 同左 | 引入 `smbus2` 驱动 PCA9685 |
| 运行测试 | `python -m pytest tests` | 同左 | 验证 mock 后端 |

CI 或离线设备也可以直接使用 `requirements.txt` 固定依赖（`pip install -r requirements.txt`）。

---

## 2. 运行命令

### 2.1 启动键盘遥控

```bash
spotmicro-teleop \
  --backend mock \
  --log-level INFO
```

常用覆盖参数：

| 选项 | 作用 | 示例 |
| ---- | ---- | ---- |
| `--config` | 指定自定义 YAML | `--config configs/lab.yaml` |
| `--backend` | 选择 `mock`（默认）或 `pca9685` | `--backend pca9685` |
| `--i2c-bus` | Linux I²C 总线编号 | `--i2c-bus 1` |
| `--i2c-address` | PCA9685 地址（十进制或十六进制） | `--i2c-address 0x40` |
| `--pwm-frequency` | 覆盖 PWM 频率（Hz） | `--pwm-frequency 60` |
| `--log-level` | 日志级别 | `--log-level DEBUG` |

### 2.2 键盘映射

| 按键 | 功能 |
| ---- | ---- |
| `w / s` | 增/减前进速度 |
| `a / d` | 向左/右平移 |
| `q / e` | 左/右偏航 |
| `r / f` | 升高/降低机身 |
| `t / g` | 俯仰调节 |
| `y / h` | 翻滚调节 |
| `space` | 触发快步事件 |
| `enter` | 唤醒/站立 |
| `c` | 清零所有速度与角度 |
| `esc` | 退出程序 |

所有增量来源于 `config/default.yaml::teleop`，可按需求调大/调小以改变响应。

---

## 3. 配置文件

所有默认参数存于 `spotmicro_standalone/config/default.yaml`。建议复制一份
维护不同场景：

```bash
cp spotmicro_standalone/config/default.yaml configs/my_robot.yaml
spotmicro-teleop --config configs/my_robot.yaml
```

关键区块说明：

- `robot` + `stance`：真实几何尺寸与中立姿态。
- `servo`：12 路舵机端口、中心、行程与方向。
- `control`：主循环周期 `dt` 与速度/偏航限幅。
- `gait`：MIT Pupper 风格的步态排程。
- `teleop`：键盘步进量。
- `hardware`：后端选择及 I²C 参数。

所有字段都会映射到 `config/loader.py` 的 dataclass，上线时若拼写错误会立即抛错。

---

## 4. 典型流程

1. **笔记本开发（mock 后端）**
   - `pip install -e .[plot]`
   - `spotmicro-teleop --backend mock --log-level DEBUG`
   - 在日志里观察 PWM 值是否合理。

2. **Linux SBC + PCA9685 台架测试**
   - 先启用 I²C（`raspi-config` 或 `dtoverlay`）。
   - `pip install -e .[hardware]`
   - `spotmicro-teleop --backend pca9685 --i2c-bus 1 --i2c-address 0x40`
   - 保持急停触手可及，抬腿前确认舵机方向。

3. **持续集成**
   - `pip install .[dev]`
   - `python -m pytest`（仅依赖 mock 后端即可）。

---

## 5. 快速排障

| 现象 | 检查项 |
| ---- | ------ |
| `ModuleNotFoundError: spotmicro_standalone` | 是否执行过 `pip install -e .`？运行测试时是否使用 `python -m pytest` 而不是直接 `python tests/...`？ |
| PCA9685 无响应 | 当前用户是否在 `i2c` 组？`i2cdetect -y 1` 能否识别地址？命令中是否选择 `--backend pca9685`？ |
| 启动时机器人猛跳 | 再次核对 `servo.layout.*.direction` 与 `center_angle_deg`，先用 mock 后端确认 PWM 范围合理。 |
| 键盘有延迟 | 确保终端窗口在前台，减小 `teleop` 增量，并避免在高频循环中使用 `--log-level DEBUG`。 |

---

更深入的调参请参阅 `docs/TUNING.md`，培训/上手材料见 `docs/LEARNING.md`。
