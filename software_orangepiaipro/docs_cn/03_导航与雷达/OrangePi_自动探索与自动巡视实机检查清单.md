# OrangePi 自动探索与自动巡视实机检查清单

> 用途：给 Orange Pi AI Pro 上机前最后一轮核查使用。
>
> 原则：先确认“低层能站稳、雷达能看见、手动能接管”，再放开自动模式。

---

## 1. 上机前硬件检查

每次通电前至少确认：

1. 舵机供电独立稳定，主控与舵机地线共地
2. PCA9685 已接到正确 I2C 总线
3. RPLidar 已接到正确串口，转头正常
4. 机器人四周至少留出 `1.5 m x 1.5 m` 空间
5. 周围没有人腿、桌脚、电源线这类细碎障碍贴得太近
6. 操作者能随时触及急停、断电或至少能立即按键接管

如果以上任何一条不满足，不建议直接上自动模式。

---

## 2. 工作区与脚本准备

## 2.1 source 环境

新终端先确认：

```bash
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
source ~/Desktop/SpotMicro/spotmicro_ws/devel/setup.bash
```

如果你的 overlay 不在这个位置，先导出：

```bash
export SPOTMICRO_SETUP_SCRIPT=/你的spotmicro_ws/devel/setup.bash
```

## 2.2 脚本执行权限

第一次拉代码后建议统一执行：

```bash
chmod +x ~/Desktop/SpotMicro/spotMicro-Chinese/software_orangepiaipro/scripts/*.sh
chmod +x ~/Desktop/SpotMicro/spotMicro-Chinese/software_orangepiaipro/scripts/*.py
chmod +x ~/Desktop/SpotMicro/spotMicro-Chinese/software_orangepiaipro/spot_micro_navigation/scripts/*.py
chmod +x ~/Desktop/SpotMicro/spotMicro-Chinese/software_orangepiaipro/spot_micro_keyboard_command/scripts/*.py
```

然后重新编译：

```bash
cd ~/Desktop/SpotMicro/spotmicro_ws
catkin_make
```

---

## 3. 低层单项验证

在任何自动模式之前，先分别确认下面三项。

## 3.1 运动控制链

确认下面命令能跑：

```bash
roslaunch spot_micro_motion_cmd motion_cmd.launch
```

成功标准：

1. `spot_micro_motion_cmd_node` 正常启动
2. `i2cpwm_board` 没有异常退出
3. 机器人可以进入 `stand`

## 3.2 键盘接管

确认：

```bash
rosrun spot_micro_keyboard_command spotMicroKeyboardMove.py
```

成功标准：

1. `stand` 能用
2. `walk` 能用
3. 低速前进和原地转向已验证不会立刻失稳

## 3.3 雷达链

确认：

```bash
roslaunch rplidar_ros rplidar_a1.launch serial_port:=/dev/ttyUSB0 frame_id:=lidar_link
rostopic hz /scan
```

成功标准：

1. `/scan` 稳定更新
2. 帧率不低于 `8 Hz`
3. `frame_id` 是 `lidar_link`

---

## 4. 自动探索建图模式上机顺序

## 4.1 启动

```bash
bash ~/Desktop/SpotMicro/spotMicro-Chinese/software_orangepiaipro/scripts/start_auto_explore_mapping.sh
```

脚本进入 `tmux` 后，优先看主 pane 日志。

## 4.2 启动后先不要马上放开

先观察：

```bash
rostopic hz /scan
rostopic hz /cmd_vel
rostopic echo /spot_micro/auto_explore/state
rostopic echo /spot_micro/cmd_vel_arbiter/source
```

成功标准：

1. `source` 在自动运行时显示 `auto`
2. 用键盘轻点方向键后，`source` 能切到 `manual`
3. 松开后几百毫秒内回到 `auto`
4. `/cmd_vel` 数值不超出你设置的安全上限

## 4.3 第一轮测试建议

第一轮只做：

1. 连续运行 `2 ~ 3 min`
2. 速度保持默认值，不加速
3. 操作者全程站在旁边

观察重点：

1. 会不会贴墙前冲
2. 会不会快速连续原地转圈
3. 会不会在桌脚附近左右抖动
4. 地图是否在持续更新

---

## 5. 自动巡视模式上机顺序

## 5.1 启动前先确认地图文件

检查：

```bash
grep -n "map_yaml" ~/Desktop/SpotMicro/spotMicro-Chinese/software_orangepiaipro/spot_micro_navigation/config/robot_mode_config.yaml
ls /你的地图路径.yaml
```

## 5.2 启动

```bash
bash ~/Desktop/SpotMicro/spotMicro-Chinese/software_orangepiaipro/scripts/start_auto_patrol.sh
```

## 5.3 如果当前先不用 AMCL

建议配置：

```yaml
auto_patrol:
  use_map_server: true
  use_amcl: false
```

这版巡视本质上仍然是“已知地图背景下的雷达避障漫游”，不是固定航点导航。

---

## 6. 手动接管验证

这是当前实机最关键的一步，必须单独确认。

启动自动模式后，在键盘 pane 做下面动作：

1. 输入 `walk`
2. 轻点方向控制
3. 观察机器人是否立刻按手动指令转向
4. 松开一小段时间，看是否恢复自动

同时观察：

```bash
rostopic echo /spot_micro/cmd_vel_arbiter/source
```

预期：

1. 接管时变成 `manual`
2. 松开后回到 `auto`

如果看不到这个切换，不要继续长时间自动运行。

---

## 7. 停机与急停建议

## 7.1 推荐停机方式

### 停自动模式

```bash
rostopic pub -1 /spot_micro/auto_mode/enable std_msgs/Bool "data: false"
```

### 停探索节点

```bash
rostopic pub -1 /spot_micro/auto_explore/stop std_msgs/Bool "data: true"
```

### 直接 Ctrl+C

对当前 pane 直接 `Ctrl+C`，这是最直接的人工停机方式。

## 7.2 更保守的现场建议

第一次实机自动模式时，建议同时保留：

1. 键盘接管窗口
2. 断电手段
3. 现场看护人

---

## 8. 运行中异常现象与建议处理

## 8.1 一直原地转圈

优先检查：

1. 雷达安装朝向是否反了
2. `lidar_link` 外参是否错误
3. `turn_speed` 是否过大
4. 左右扇区判断是否一直偏同一边

建议先调：

1. `turn_speed`
2. `turn_duration_sec`
3. `random_turn_bias`

## 8.2 总在障碍前急停，不敢走

优先检查：

1. `front_stop_distance`
2. `turn_trigger_dist`
3. 雷达近距离噪声

## 8.3 地图扭曲严重

优先检查：

1. 线速度是否过快
2. 原地转是否过猛
3. 底层步态是否抖动大

建议先降：

1. `cruise_speed`
2. `turn_speed`

## 8.4 手动接管不生效

优先检查：

1. 键盘脚本是否真的重映射到 `/cmd_vel_manual`
2. `cmd_vel_arbiter.py` 是否正常启动
3. `/spot_micro/cmd_vel_arbiter/source` 是否变化

---

## 9. 当前推荐的首轮实机参数

如果你要做第一轮保守测试，建议先用当前默认值，不要盲目提速：

### 自动探索

1. `cruise_speed: 0.06`
2. `turn_speed: 0.22`
3. `turn_trigger_dist: 0.42`
4. `stuck_dist: 0.30`

### 安全门

1. `max_vx: 0.12`
2. `max_wz: 0.20`
3. `front_stop_distance: 0.35`
4. `hard_stop_distance: 0.20`

---

## 10. 实机验收最低标准

这版第一阶段不追求漂亮，只追求“可控、可停、可复现”。

建议最低验收标准是：

1. 自动探索可连续运行 `3 min`，无明显碰撞
2. 手动接管可稳定覆盖自动控制
3. 停机命令可靠
4. autosave 目录可生成地图快照
5. 自动巡视可在已知房间内持续低速漫游，不出现失控快速旋转

只要这 5 条都达成，就说明第一版已经具备继续迭代的工程基础。

