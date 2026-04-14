# SpotMicro 雷达避障漫游自动建图方案

> 目标：在不依赖 RViz 手工点目标点的前提下，让机器狗仅依赖雷达完成“低速避障 + 持续游走 + 同步建图”。
>
> 适用场景：封闭房间、小办公室、实验室内的演示性自动建图。
>
> 设计原则：先做一个能稳定跑起来、对算力要求低、容易调试的工程版本，而不是一步到位上复杂的 frontier exploration。

---

## 1. 方案结论

当前推荐的自动探索建图方案为：

```text
RPLidar
  -> /scan
  -> 自动漫游避障节点
  -> /cmd_vel
  -> spot_micro_motion_cmd

同时：
RPLidar
  -> Hector SLAM
  -> /map
  -> 定时自动保存地图
```

这套方案的核心行为是：

1. 雷达持续感知障碍。
2. 机器人默认低速前进。
3. 前方遇障碍则停止并转向。
4. 朝更空旷的一侧继续前进。
5. 全程持续运行 SLAM。
6. 用户不发停止命令，机器人就一直探索并补充地图。

---

## 2. 为什么先选这个方案

和“RViz 点目标导航”相比，这个方案更适合当前硬件条件：

1. 不依赖 XRDP 下的 RViz 实时渲染，显著降低香橙派负载。
2. 不要求先把 `AMCL + move_base + 目标点下发` 完整调稳。
3. 只需要雷达、基础 `/cmd_vel` 控制和现有 Hector 建图链路。
4. 即使探索策略不完美，也能在封闭房间里逐步补图。

和“frontier exploration”相比，这个方案更适合先落地：

1. 算法简单。
2. 调参简单。
3. 对导航栈依赖更少。
4. 更适合四足机器人低速演示。

---

## 3. 功能边界

本方案**能做的事**：

1. 在封闭房间内自动低速游走。
2. 仅依赖雷达完成基础避障。
3. 边走边建图。
4. 在没有停止命令时持续补图。
5. 配合自动保存地图功能，减少断联或异常中断造成的数据丢失。

本方案**暂时不追求**：

1. 地图全覆盖最优。
2. 每次都选择最有价值的未知区域。
3. 高级全局探索路径规划。
4. 对透明障碍、低矮障碍、悬空障碍的完美识别。

---

## 4. 系统架构

推荐增加一个新节点，例如：

```text
spot_micro_navigation/scripts/laser_wander_explorer.py
```

整体话题关系如下：

```text
/scan
  -> laser_wander_explorer.py
      -> /cmd_vel
      -> /spot_micro/auto_explore/state   （可选调试状态）

/scan
  -> hector_mapping
      -> /map

/map
  -> periodic_map_saver.py
      -> autosave/*.pgm
      -> autosave/*.yaml
```

---

## 5. 节点职责设计

`laser_wander_explorer.py` 建议职责如下：

1. 订阅 `/scan`
2. 分析前方、左前方、右前方的障碍距离
3. 决定当前行为状态：
   - `FORWARD`
   - `TURN_LEFT`
   - `TURN_RIGHT`
   - `ESCAPE`
   - `STOP`
4. 发布低速 `/cmd_vel`
5. 支持外部停止命令
6. 支持简单脱困逻辑

建议不要让它直接负责：

1. 建图
2. 地图保存
3. 高级导航
4. 复杂状态机

保持单一职责，便于调试。

---

## 6. 探索逻辑设计

## 6.1 基本状态机

推荐使用最简单稳定的有限状态机：

```text
FORWARD     前进
TURN_LEFT   左转
TURN_RIGHT  右转
ESCAPE      脱困
STOP        停止
```

状态转换建议：

1. 默认进入 `FORWARD`
2. 当前方距离小于阈值时：
   - 比较左侧与右侧可通行空间
   - 哪边更空旷就转向哪边
3. 如果左右都很近：
   - 进入 `ESCAPE`
   - 先后退或原地转更大角度
4. 接收到停止命令：
   - 进入 `STOP`
   - 输出零速度

## 6.2 雷达扇区划分

建议把激光分为几个扇区：

1. `front_center`：正前方
2. `front_left`：左前方
3. `front_right`：右前方
4. `left`：左侧
5. `right`：右侧

工程上不需要一开始划太细，建议优先使用：

1. 正前 `-20° ~ +20°`
2. 左前 `+20° ~ +70°`
3. 右前 `-70° ~ -20°`

每个扇区取：

1. 最小距离
2. 中位数距离

优先使用中位数或去掉无效值后的均值，避免单个噪点触发误判。

## 6.3 行为规则

建议第一版规则如下：

### 规则 A：前方畅通

若：

```text
front_center > forward_safe_dist
```

则：

```text
linear.x = cruise_speed
angular.z = small_bias
```

其中 `small_bias` 可用于轻微随机扰动，避免一直走直线后反复卡在同一路径。

### 规则 B：前方受阻，左侧更空

若：

```text
front_center <= turn_trigger_dist
且 front_left > front_right
```

则进入 `TURN_LEFT`：

```text
linear.x = 0
angular.z = +turn_speed
```

### 规则 C：前方受阻，右侧更空

若：

```text
front_center <= turn_trigger_dist
且 front_right >= front_left
```

则进入 `TURN_RIGHT`：

```text
linear.x = 0
angular.z = -turn_speed
```

### 规则 D：前方和左右都很近

若：

```text
front_center < stuck_dist
且 front_left < stuck_side_dist
且 front_right < stuck_side_dist
```

则进入 `ESCAPE`：

可选动作：

1. 停止 0.3 秒
2. 原地转 0.8 ~ 1.5 秒
3. 若底层支持安全后退，则低速后退 0.2 ~ 0.5 秒再转向

如果四足平台后退不稳定，建议第一阶段**不做后退**，只做原地转向脱困。

---

## 7. 建议参数

以下参数适合作为第一版起点：

| 参数 | 建议值 | 说明 |
|------|--------|------|
| `cruise_speed` | `0.05 ~ 0.08 m/s` | 默认前进速度 |
| `turn_speed` | `0.18 ~ 0.30 rad/s` | 避障转向角速度 |
| `forward_safe_dist` | `0.60 m` | 前方畅通判据 |
| `turn_trigger_dist` | `0.40 ~ 0.45 m` | 触发转向距离 |
| `stuck_dist` | `0.28 ~ 0.35 m` | 判定前方严重受阻 |
| `stuck_side_dist` | `0.25 ~ 0.30 m` | 判定左右空间不足 |
| `scan_timeout` | `0.30 s` | 雷达超时后立即停车 |
| `cmd_rate` | `10 Hz` | 控制发布频率 |
| `random_turn_bias` | 小幅启用 | 降低重复绕圈概率 |

四足平台首轮测试强烈建议：

1. 线速度宁可慢，不要快
2. 原地转速度不要超过当前手动建图安全值
3. 先在小房间做 3~5 分钟测试

---

## 8. 停止机制设计

用户说“如果我没有手动输入停止命令，机器狗就一直探索”，因此必须补一个明确的停止机制。

建议支持两种停止方式：

### 方式 1：ROS 参数控制

例如：

```text
~enabled = true / false
```

节点启动时：

1. `enabled=true` 就自动探索
2. `enabled=false` 就保持停车

### 方式 2：专用停止话题

例如订阅：

```text
/spot_micro/auto_explore/stop   std_msgs/Bool
```

规则：

1. 收到 `True`：
   - 立即停机
   - 状态切到 `STOP`
2. 收到恢复命令：
   - 再进入 `FORWARD`

推荐同时保留：

1. 键盘遥控急停
2. 底层速度安全门

---

## 9. 安全门设计

自动探索建图一定要有额外安全约束，不能直接裸发速度。

建议最少加入以下保护：

1. `/scan` 超时超过 `0.3s`，立即输出 `0`
2. 雷达最近距离小于硬阈值，例如 `0.20m`，立即停止
3. 发布速度始终限幅
4. 建图时线速度和角速度固定上限
5. 支持外部急停

如果后面已有 `cmd_vel_safety_gate.py`，建议自动探索节点输出到：

```text
/cmd_vel_nav
```

再由安全门转发到：

```text
/cmd_vel
```

如果当前尚未补齐安全门，也至少要在自动探索节点内部自行做限幅和超时停车。

---

## 10. 脱困策略

自动漫游最常见问题不是撞墙，而是：

1. 在椅子腿附近原地抖动
2. 在角落里左右反复切换
3. 在窄区域来回打转

建议加入一个简单脱困机制。

## 10.1 卡住判定

可使用以下任一条件：

1. 连续 `N` 次循环前方都小于 `turn_trigger_dist`
2. 连续若干秒都处于转向状态
3. 若有 `/slam_out_pose` 或里程计，可判断位姿变化过小

## 10.2 脱困动作

建议顺序：

1. 停止 0.2~0.5 秒
2. 强制原地转向 1.0~1.5 秒
3. 转向方向与上一次相反
4. 再恢复 `FORWARD`

如果底层已验证后退稳定，可再增加：

1. 低速后退 0.2~0.4 秒
2. 再大角度转向

---

## 11. 建图链路配合

本方案推荐继续沿用：

1. `rplidar_ros`
2. `hector_mapping`
3. `periodic_map_saver.py`

推荐启动组合：

```text
雷达驱动
  + hector_mapping
  + 自动探索节点
  + 自动保存地图
```

推荐不要同时启动：

1. XRDP 下的 RViz 实时渲染
2. 大量额外调试图形界面

原因很明确：

1. 当前香橙派在 `XRDP + RViz` 场景下负载过高
2. 自动探索建图本来就是为减少 GUI 依赖

---

## 12. 地图自动保存策略

建议保留之前已经加入的自动保存功能：

```bash
roslaunch spot_micro_navigation slam_hector_mapping.launch \
  autosave_enabled:=true \
  autosave_interval_sec:=120.0 \
  autosave_directory:=/home/HwHiAiUser/Desktop/SpotMicro/maps/autosave \
  autosave_prefix:=hector_autosave \
  autosave_keep_last:=10
```

自动探索场景下尤其建议：

1. 每 `60~120s` 自动保存一次
2. 探索停止时再额外手动保存一次正式地图

任务结束后建议执行：

```bash
cd ~/Desktop/SpotMicro/maps
rosrun map_server map_saver -f auto_explore_final_$(date +%Y%m%d_%H%M%S)
```

---

## 13. 启动流程建议

建议后续整理成一个专用 launch，例如：

```text
auto_explore_hector.launch
```

推荐启动顺序：

1. 启动底层控制与雷达
2. 启动 Hector 建图
3. 启动自动保存地图
4. 启动自动探索节点
5. 观察 1~2 分钟是否稳定
6. 稳定后再放开长时间运行

推荐行为：

1. 第一次测试 3 分钟
2. 第二次测试 5 分钟
3. 再做 10 分钟以上连续探索

---

## 14. 调试建议

建议至少保留以下观测手段：

```bash
rostopic hz /scan
rostopic hz /cmd_vel
rostopic echo -n 1 /slam_out_pose
top
```

如果后续自动探索节点发布状态话题，例如：

```text
/spot_micro/auto_explore/state
```

则建议实时查看：

```bash
rostopic echo /spot_micro/auto_explore/state
```

常见调试方向：

1. 总是撞前方：
   - 增大 `turn_trigger_dist`
   - 降低 `cruise_speed`
2. 总是原地转圈：
   - 降低 `turn_speed`
   - 给 `FORWARD` 增加最小持续时间
3. 总在角落抖动：
   - 增强 `ESCAPE` 逻辑
   - 提高转向持续时间
4. 地图扭曲严重：
   - 降低前进速度
   - 降低角速度
   - 减少急停急转

---

## 15. 推荐实现步骤

建议按下面顺序开发：

### 第 1 步：最小版本

完成：

1. 订阅 `/scan`
2. 发布 `/cmd_vel`
3. 实现前进 / 左转 / 右转

目标：

1. 机器人能在房间中持续游走 2~3 分钟
2. 不发生明显碰撞

### 第 2 步：加停止机制

完成：

1. 停止话题
2. 启停状态管理

目标：

1. 能一键停下
2. 能一键恢复

### 第 3 步：加脱困

完成：

1. 卡住计数
2. 强制脱困动作

目标：

1. 能减少角落原地打转

### 第 4 步：联调自动保存地图

完成：

1. 长时间探索
2. 周期保存地图
3. 手动保存最终图

目标：

1. 即使异常中断，也能保留阶段性地图

---

## 16. 后续升级方向

当第一版“避障漫游建图”稳定后，再考虑：

1. 读取 `/map` 做未知区域补图判断
2. 根据 `/slam_out_pose` 判断是否长时间在原地重复绕圈
3. 增加简单“优先走向未知区域”的启发式
4. 最终再升级为 frontier exploration

建议升级路线：

```text
雷达避障漫游
  -> 加脱困
  -> 加未知区域偏好
  -> 再做 frontier exploration
```

---

## 17. 最终建议

对于当前 SpotMicro + Orange Pi AIpro 的工程条件，推荐路线是：

**先实现“仅依赖雷达的低速避障漫游自动建图”，让机器狗在封闭房间里持续游走并补图；等这一版稳定后，再考虑更复杂的自主探索算法。**

这条路线最符合当前目标：

1. 不依赖 RViz 点目标
2. 不要求探索最优
3. 对算力更友好
4. 更适合演示
5. 更容易尽快落地
