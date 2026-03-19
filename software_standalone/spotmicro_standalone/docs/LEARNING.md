# SpotMicro Standalone – 学习与操作手册

该手册面向新工程师或学生，帮助快速理解仓库结构、核心代码路径、以及如何
扩展/学习。推荐与 `docs/USAGE.md`、`docs/TUNING.md` 一起阅读。

---

## 1. 角色与模块速记

| 模块 | 位置 | 作用 | 需要掌握的技能 |
| ---- | ---- | ---- | -------------- |
| `config/loader.py` | 数据类解析 YAML | Python dataclass / 配置管理 |
| `hardware/board.py` | 硬件抽象（mock, PCA9685） | I²C, smbus2, PWM |
| `hardware/servo_driver.py` | 角度→PWM | 三角函数、标定 |
| `interfaces/keyboard.py` | 键盘输入线程 | 跨平台 I/O、线程同步 |
| `runtime/teleop.py` | 主控制循环 | 控制任务编排 |
| `pupper_src/*` | MIT Pupper 控制器 | 运动控制、步态算法 |
| `spot_micro_kinematics/*` | 运动学/StickFigure | 数学、可视化 |

了解调用链：

```
KeyboardInput --> Command --> Controller --> SpotMicroStickFigure
              -> ServoDriver --> ServoBoard (mock/pca9685)
```

---

## 2. 推荐学习路径

| 阶段 | 目标 | 建议练习 |
| ---- | ---- | -------- |
| 入门 (Day 1) | 能够运行 mock teleop | 按 `docs/USAGE.md` 完成安装，阅读 `runtime/teleop.py` |
| 进阶 (Week 1) | 理解 gait/controller | 通读 `pupper_src/Controller.py` 及相关测试 |
| 实机 (Week 2) | 驱动 PCA9685 | 阅读 `hardware/board.py`, 搭建单腿实验平台 |
| 扩展 (Week 3+) | 添加新输入或传感器 | 在 `interfaces/` 中新增模块（如 UDP/Joystick） |
| 研究 (long-term) | 自定义控制策略 | 替换 `Controller` 或增加 RL 模块 |

---

## 3. 关键命令备忘

> **★ 每个新终端的第一步**：cd 到 `software_standalone/` 并激活虚拟环境：
> ```bash
> # 从仓库根目录 spotMicro-Chinese 出发
> cd software_standalone && source .venv/bin/activate
> ```

| 场景 | 命令 |
| ---- | ---- |
| 安装开发依赖 | `pip install -e .[dev]` |
| 运行所有测试 | `python -m pytest` |
| 快速导入验证 | `python -c "import spotmicro_standalone";` |
| Mock 运行 | `spotmicro-teleop --backend mock` |
| 硬件运行 | `spotmicro-teleop --backend pca9685 --i2c-bus 1 --i2c-address 0x40` |

---

## 4. 代码阅读指引

1. **从配置到代码**：在 `config/default.yaml` 找到你关心的参数，如
   `servo.layout.RF_1.center`，然后在 `ServoDriver._angle_to_pwm` 里查它如何被使用。
2. **跟踪数据流**：使用 IDE “Find References” 或简单 `rg "servo_cmds_rad"` 看值
   如何从控制器流向硬件。
3. **练习题**：
   - 修改 `teleop.angle_increment_deg`，观察顶层 CLI 变化；
   - 在 `MockBoard.send_absolute` 中打印关节角度，以便理解 PWM 变化；
   - 扩展 `KeyboardInput` 支持 `z/x` 控制俯仰速度。

---

## 5. 常见学习问题 (FAQ)

| 问题 | 解答 |
| ---- | ---- |
| *为什么不用 ROS?* | 本仓库针对没有 ROS 的 Windows/Linux 环境，将原 ROS 节点逻辑拆成纯 Python 模块，便于教学和快速迭代。 |
| *如何添加手柄或网络控制?* | 在 `interfaces/` 新建类，输出 `KeyboardCommandState` 风格的结构，再在 `runtime/teleop.py` 中选择性启用。 |
| *能否做强化学习?* | 可以，把 `Controller` 替换为 RL policy，仍然通过 `ServoDriver` 输出 PWM。建议先写仿真接口。 |
| *如何记录数据?* | 在 `runtime/teleop.py` 或 `ServoDriver` 里写入 CSV；或利用 `MockBoard` 将命令保存在 `last_commands`。 |

---

## 6. 贡献指南摘要

1. 分支 `feature/<topic>`，完成修改。
2. 运行 `python -m pytest` 确认通过。
3. 文档更新：若涉及使用方式或参数，务必同步 `docs/*.md` 与顶层 `README.md`。
4. `git diff` 确认只包含必要改动，再提交 PR。

---

## 7. 进一步阅读

- [MIT Mini Cheetah / Pupper 论文与资料（外链，自行搜索）]
- `servo_calibration.md` (仓库根目录) – 详细舵机调试过程
- `SOFTWARE_ASSESSMENT.md` – 原 ROS 版的安全与调试建议，可类比到此处

欢迎将自己的学习笔记或实验心得追加到本文件，保持团队知识共享。
