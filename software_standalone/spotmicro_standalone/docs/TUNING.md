# SpotMicro Standalone – 微调与配置指导

本手册聚焦在 `spotmicro_standalone/config/*.yaml` 与相关代码可调参数，帮助你
在没有 ROS 的情况下完成舵机标定、步态参数微调、控制稳定性验证等工作。

---

## 1. 配置文件结构速览

| 区段 | 关键字段 | 影响模块 | 说明 |
| ---- | -------- | -------- | ---- |
| `robot` | `hip_link_length`, `body_length` | 运动学/StickFigure | 真实几何尺寸 |
| `stance` | `default_stand_height`, `lie_down_height` | 初始姿态 | 决定初始化脚点 |
| `servo` | `layout.*(num, center, range, direction, center_angle_deg)` | `hardware.servo_driver` | 角度→PWM 的映射 |
| `control` | `dt`, `max_*` | `runtime.teleop` | 控制频率 & 上限 |
| `gait` | `alpha`, `beta`, `contact_phases`, `swing_time` | `pupper_src.Controller` | 步态/摆动配置 |
| `teleop` | `speed_increment`, `angle_increment_deg` | `interfaces.keyboard` | 键盘步进量 |
| `hardware` | `backend`, `i2c_bus`, `pwm_frequency` | `hardware.board` | 底层驱动 |

保存修改后，直接重新运行 `spotmicro-teleop --config <file>` 即可，不需要
重建或签入 ROS 参数服务器。

> **提示**：每个新终端需先 cd 到 `software_standalone/` 并激活虚拟环境（`source .venv/bin/activate`），详见 `docs/USAGE.md`。

---

## 2. 舵机/硬件标定

1. **对照表准备**：使用原 ROS 工程中的 `servo_calibration.md` 或
   `舵机校准参考表格.ods`，对照 `default.yaml::servo.layout`。
2. **Mock 验证**：先用 `--backend mock` 观察 12 个舵机的 PWM 输出是否在
   `[center - range/2, center + range/2]`。若超界则 `servo_max_angle_deg` 过大。
3. **实际通电**：
   - 仅安装一条腿，执行 `spotmicro-teleop --backend pca9685`；
   - 通过键盘微调 `r/f/t/g/y/h` 观察姿态是否与预期一致；
   - 若正负方向相反，修改对应 `direction`。
4. **安全界限**：`servo.range` 对应 12bit PCA9685 计数（0-4095），确保
   `center ± range/2` 不超过该范围，否则会在底层 driver 报错。
5. **节流测试**：设置 `hardware.pwm_frequency` 在 50-60Hz 范围内试验噪音与
   温升，必要时配合 `config/hardware` 中的 `pwm_frequency` 覆盖值。

---

## 3. 步态 & 运动控制

### 3.1 关键时间常数

| 参数 | 默认值 | 调整要点 |
| ---- | ------ | -------- |
| `control.dt` | 0.02 s | 主循环周期；Windows 下建议 ≥ 0.02 以避免调度抖动 |
| `gait.swing_time` | 0.20 s | 摆腿时间，越小步频越高但冲击大 |
| `gait.overlap_time` | 0.0 s | 四足同时着地时间，>0 可提升稳定性 |
| `gait.foot_height_time_constant` | 0.02 | 调节脚尖轨迹滤波 |

### 3.2 触地序列 (contact phases)

顺序为 `RF, LF, RB, LB`。值为：

- `1`：向前支撑
- `0`：摆动
- `-1`：向后支撑
- `2`：保持

可以参考 MIT Pupper 的 `Controller.py`，保持 8 相位即可。调整时务必保证每条腿
有完整 swing + stance，否则步态会崩溃。

### 3.3 姿态平衡

`gait.body_shift_*` 控制重心偏移；若发现切换步态时机体左右晃动过大，可增加
`side_body_balance_shift` 或延长 `overlap_time`。

---

## 4. 键盘控制调参

`teleop` 区段负责所有按键增量：

- 将 `speed_increment` 调小（例如 0.01）可以细调速度；
- `yaw_rate_increment_deg` 设置得太大时机器人容易“点头”，建议保持 ≤ 2°；
- `height_increment` 用于抬升/趴下，结合 `stance.default_stand_height`。

调参流程：

1. 复制默认配置：`cp config/default.yaml configs/lab.yaml`；
2. 修改 `teleop` 下的数值；
3. `spotmicro-teleop --config configs/lab.yaml --backend mock` 验收；
4. 满意后再上真实硬件。

---

## 5. 模型/仿真与实机差异 (Sim2Real)

| 风险 | 对策 |
| ---- | ---- |
| 实机摩擦与 Pupper 模型不同 | 在 `gait.alpha/beta` 中增减默认落脚位置，或在 `Controller.step_gait` 里增加摩擦补偿 |
| 实机舵机死区 | 在 `servo.layout.*.center_angle_deg` 加入经验值，确保 `0` 对应真实中立 |
| 控制周期抖动 | Windows 下建议关闭高帧率 logging；必要时迁移到 Linux SBC |
| 传感器缺失 | 当前实现无 IMU/力反馈，若需要请扩展 `interfaces/` 读取传感器数据并写入 `Command` |

---

## 6. 数据记录与回放

虽然无 ROS bag，可通过以下方式采集：

1. 把 `hardware.MockBoard` 改为自定义类，将 `send_absolute` 的命令写入 CSV；
2. 在 `runtime/teleop.py` 中对 `leg_angles` 或 `command` 做 `csv.writer` 记录；
3. 通过 `numpy.loadtxt` 离线分析，或用 `matplotlib`（安装 `.[plot]`）。

---

## 7. 推荐调试顺序

1. `mock` 后端验证命令范围 →
2. 单腿接入 PCA9685，调 `direction/center` →
3. 安装全身但悬空，验证步态 →
4. 地面缓慢行走，逐步开放更大速度。  

有任何新的调参经验，可追加到本文件或提交 PR。
