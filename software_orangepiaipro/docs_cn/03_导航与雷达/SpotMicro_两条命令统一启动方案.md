# SpotMicro 两条命令统一启动方案

> 目标：把当前“建图 / 巡视 / 手动接管”整合为两个统一入口，避免每次在多个终端手动输入一长串命令。
>
> 方案重点：自动行为可一键启动，手动控制始终保留，并且手动控制优先级高于自动控制。

---

## 1. 方案结论

建议最终只保留两个主入口：

### 命令 1：自动探索建图

```bash
bash ~/Desktop/SpotMicro/scripts/start_auto_explore_mapping.sh
```

用途：

1. 机器人自动低速避障漫游
2. 同时运行 Hector 建图
3. 自动保存地图快照
4. 保留手动方向接管
5. 可手动开始 / 停止探索

### 命令 2：自动巡视

```bash
bash ~/Desktop/SpotMicro/scripts/start_auto_patrol.sh MAP:=/home/HwHiAiUser/Desktop/SpotMicro/maps/xxx.yaml
```

用途：

1. 在已建好的房间地图中自动低速巡视
2. 不要求固定航点
3. 不要求必须到达某个导航目标
4. 只要求不撞障碍、持续行走
5. 保留手动方向接管

---

## 2. 为什么是“两条命令”，而不是“两套复杂终端流程”

你当前真正需要的是：

1. **自动探索建图模式**
2. **自动巡视演示模式**

这两个模式的核心行为是不同的：

### 自动探索建图

```text
雷达 -> 避障漫游 -> /cmd_vel
     -> Hector SLAM -> /map
     -> 周期自动存图
```

### 自动巡视

```text
静态地图 + 定位（可选）
雷达 -> 避障漫游 -> /cmd_vel
```

它们都共享：

1. 雷达
2. 机器狗低层控制
3. 手动接管
4. 速度安全限制

因此最合理的工程做法不是每次重新拼命令，而是：

1. 抽出公共控制链
2. 按场景切换“建图模式”与“巡视模式”
3. 外层统一用两个启动脚本包装

---

## 3. 核心设计原则

这套统一启动方案必须满足以下原则：

1. **自动控制随时可停**
2. **手动控制优先级最高**
3. **自动与手动不直接抢同一个 `/cmd_vel`**
4. **所有速度最后都要经过安全门**
5. **尽量不依赖 RViz**
6. **尽量减少 XRDP 图形负载**
7. **地图路径通过配置文件管理，不靠命令行手写**

---

## 3.1 地图加载方式的最终设计

你已经明确提出一个非常重要的使用要求：

1. 不想每次启动时手动输入地图路径
2. 想直接改配置文件中的地图加载路径
3. 启动脚本自动读取配置文件并完成启动

这个要求非常合理，因此这里把地图加载方案单独固定下来。

### 最终建议

采用：

**配置文件 + 启动脚本读取配置文件 + roslaunch 内部使用解析后的路径**

也就是说：

1. 用户不再输入：
   ```bash
   roslaunch ... map_yaml:=xxx.yaml
   ```
2. 用户只需要修改一个统一配置文件
3. 启动脚本自动读取 `map_yaml`
4. 启动脚本再把这个值传给内部 launch

### 为什么不建议直接靠命令行传地图路径

因为命令行方式虽然灵活，但对现场使用不友好：

1. 容易输错路径
2. 路径太长
3. 不适合反复切换房间地图
4. 不适合做“一键演示”

### 为什么推荐“配置文件 + 脚本读取”

因为这种方式兼顾了：

1. 用户体验简单
2. 路径集中管理
3. launch 文件保持清晰
4. 后续很容易扩展更多参数

---

## 3.2 推荐配置文件结构

建议新增一个统一配置文件：

```text
software_orangepiaipro/spot_micro_navigation/config/robot_mode_config.yaml
```

这个文件建议专门放“当前启动模式会用到的总配置”。

### 建议内容

```yaml
common:
  map_yaml: /home/HwHiAiUser/Desktop/SpotMicro/maps/default_room.yaml
  scan_topic: /scan
  cmd_vel_topic: /cmd_vel
  cmd_vel_manual_topic: /cmd_vel_manual
  cmd_vel_auto_topic: /cmd_vel_auto
  cmd_vel_mux_topic: /cmd_vel_mux_raw

auto_explore_mapping:
  enabled: true
  autosave_enabled: true
  autosave_interval_sec: 120.0
  autosave_directory: /home/HwHiAiUser/Desktop/SpotMicro/maps/autosave
  autosave_prefix: hector_autosave
  autosave_keep_last: 10

auto_patrol:
  enabled: true
  use_map_server: true
  use_amcl: false
```

### 说明

#### `common.map_yaml`

这是最关键的字段。

以后如果你要切换地图，只需要改：

```yaml
common:
  map_yaml: /home/HwHiAiUser/Desktop/SpotMicro/maps/另一个地图.yaml
```

然后重新执行启动脚本即可。

#### 为什么放在 `common`

因为：

1. 自动巡视一定会用到地图
2. 自动探索建图结束后，也可能要把最终地图路径切进来
3. 放在 `common` 里最方便统一管理

---

## 3.3 启动脚本如何读取配置文件

推荐外层脚本使用 `python3` 或 `python3 + yaml` 读取配置文件。

### 推荐原因

相比在 bash 里直接硬解析 yaml：

1. Python 读取 yaml 更稳
2. 出错更少
3. 后面扩展参数更容易

### 推荐行为

例如：

```bash
bash ~/Desktop/SpotMicro/scripts/start_auto_patrol.sh
```

脚本内部做这些事：

1. 读取：
   ```text
   ~/Desktop/SpotMicro/spotmicro_ws/src/spot_micro_navigation/config/robot_mode_config.yaml
   ```
   或你最终安装后的对应路径
2. 提取：
   - `common.map_yaml`
   - `common.scan_topic`
   - `auto_patrol.use_map_server`
   - `auto_patrol.use_amcl`
3. 自动拼好 roslaunch 命令
4. 用户不需要再输入地图路径

### 用户体验

最终用户只做两件事：

1. 改配置文件
2. 运行统一启动脚本

这就达到了你要的效果。

---

## 4. 推荐控制链路

推荐增加一个“速度仲裁器”节点：

```text
cmd_vel_arbiter.py
```

整体话题关系推荐改成：

```text
自动探索节点 / 自动巡视节点
  -> /cmd_vel_auto

键盘手动控制
  -> /cmd_vel_manual

cmd_vel_arbiter.py
  -> /cmd_vel_mux_raw

cmd_vel_safety_gate.py
  -> /cmd_vel

/cmd_vel
  -> spot_micro_motion_cmd
```

### 关键点

#### 自动控制不再直接发 `/cmd_vel`

而是发：

```text
/cmd_vel_auto
```

#### 手动控制也不再直接发 `/cmd_vel`

而是发：

```text
/cmd_vel_manual
```

#### 只有仲裁器可以输出合并后的速度

输出到：

```text
/cmd_vel_mux_raw
```

#### 最终仍然经过安全门

```text
/cmd_vel_mux_raw -> cmd_vel_safety_gate.py -> /cmd_vel
```

这样做的好处是：

1. 自动和手动不会互相覆盖
2. 可以明确设置优先级
3. 任意模式都能复用同一套低层输出

---

## 5. 手动接管机制设计

这是整个方案最关键的一部分。

你的要求不是“只能自动”，而是：

1. 自动能跑
2. 但我仍然要随时手动控制前进方向

因此推荐：

## 5.1 手动优先级高于自动

`cmd_vel_arbiter.py` 规则建议如下：

1. 如果最近 `manual_timeout` 时间内收到过 `/cmd_vel_manual`
   - 直接采用手动速度
   - 忽略自动速度
2. 如果手动速度超时
   - 自动恢复采用 `/cmd_vel_auto`

例如：

```text
manual_timeout = 0.6 s
```

这意味着：

1. 你一旦按键控制
2. 机器人立即听你的
3. 你松开一小段时间后
4. 自动模式再接管回来

这就是最适合演示的“手动接管”体验。

## 5.2 手动开始 / 停止自动模式

建议再加一个简单控制话题：

```text
/spot_micro/auto_mode/enable   std_msgs/Bool
```

规则：

1. `True`：允许自动控制输出
2. `False`：自动控制输出清零

这样你可以：

1. 启动整套系统
2. 先手动控制机器人站稳 / 转向
3. 再开启自动模式
4. 需要时再关闭自动模式

---

## 6. 自动探索建图模式设计

## 6.1 功能目标

自动探索建图模式要求：

1. 机器人默认低速前进
2. 前方遇障碍自动转向
3. 持续运行 Hector SLAM
4. 周期自动保存地图
5. 用户不停止，它就一直探索
6. 用户可以随时手动接管

## 6.2 推荐组成

```text
nav_mode_manager.py
laser_wander_explorer.py
cmd_vel_arbiter.py
cmd_vel_safety_gate.py
hector_mapping
periodic_map_saver.py
spot_micro_keyboard_command（重映射到 /cmd_vel_manual）
```

## 6.3 启动后行为

启动后流程建议为：

1. `nav_mode_manager.py` 让机器人自动进入站立 / 行走态
2. 自动探索节点开始发布 `/cmd_vel_auto`
3. Hector 开始建图
4. 自动存图开始工作
5. 键盘控制节点始终待命，可随时接管

## 6.4 停止方式

建议至少保留 3 种停止方式：

1. 发布 `/spot_micro/auto_mode/enable false`
2. 键盘手动发送零速度并接管
3. 直接 `Ctrl+C` 结束整个启动脚本

---

## 7. 自动巡视模式设计

## 7.1 功能目标

你的要求是：

1. 不要求固定航线
2. 不要求预先设导航点
3. 不要求必须走到某个目标点
4. 只要求在房间里一直行走且不撞障碍

这说明“自动巡视”本质上不是 `move_base 航点巡逻`，而是：

**基于已知地图背景下的避障漫游。**

所以它和自动探索建图的核心控制器可以是同一个：

```text
laser_wander_explorer.py
```

两者差别主要在于是否同时运行建图链路。

## 7.2 推荐组成

```text
nav_mode_manager.py
laser_wander_explorer.py
cmd_vel_arbiter.py
cmd_vel_safety_gate.py
spot_micro_keyboard_command（重映射到 /cmd_vel_manual）
```

可选增加：

1. `map_server`
2. `AMCL`

但注意：

### 如果巡视模式只是“看起来在房间里自己走”

那其实不一定非要启动 `move_base`。

因为你并不依赖：

1. 固定目标点
2. 全局规划
3. 航点导航

所以第一版自动巡视模式可以设计成：

```text
已知地图存在
但运行时只用雷达避障漫游
不强依赖 RViz 点目标
```

这样负载最低，也最稳。

## 7.3 什么时候再加 AMCL

如果后续你希望：

1. 巡视时在地图上显示机器人位置
2. 记录巡视轨迹
3. 限制机器人只在某一区域巡逻

那么再加：

1. `map_server`
2. `AMCL`

但在当前阶段，它不是必须依赖。

---

## 8. 为什么两个模式都保留“手动方向控制”

因为你的真实使用场景不是完全无人值守，而是：

1. 平时让机器狗自动演示
2. 发现方向不理想时人工接一下
3. 接完再放回自动

这比“纯自动”更符合当前硬件和工程条件。

因此手动控制不是辅助功能，而是整个方案的一部分。

建议行为体验定义为：

1. 自动模式默认运行
2. 人手一接管，立即优先手动
3. 人手松开后，自动恢复

---

## 9. 为什么不建议把键盘控制直接继续发 `/cmd_vel`

现有 `spot_micro_keyboard_command` 直接发布到：

```text
/cmd_vel
```

这样的问题是：

1. 它会和自动节点抢输出
2. 也会绕过统一仲裁逻辑
3. 后面难以做“手动优先”

因此推荐改法是：

### 方案 A：在 launch 里 remap

把键盘控制输出重映射到：

```text
/cmd_vel_manual
```

### 方案 B：直接修改脚本默认输出主题

但更推荐先用 remap，侵入更小。

---

## 10. 为什么目前不推荐把自动巡视做成固定航点巡逻

你现在明确说了：

1. 不要求固定路线
2. 不要求非得走到某些导航点

那固定航点巡逻反而会带来额外成本：

1. 每张新地图都要重新录点
2. 依赖 `AMCL + move_base`
3. 依赖更完整的导航链
4. 调试更重

而“避障漫游巡视”更贴合你的现阶段目标：

1. 简单
2. 稳
3. 负载更低
4. 演示效果也足够

---

## 11. 推荐实现清单

为了达成这两个统一启动命令，建议新增 / 调整以下内容：

### 新增节点

1. `laser_wander_explorer.py`
   - 自动探索 / 自动巡视共用
2. `cmd_vel_arbiter.py`
   - 手动优先的速度仲裁器

### 复用现有节点

1. `nav_mode_manager.py`
2. `cmd_vel_safety_gate.py`
3. `periodic_map_saver.py`
4. `hector_mapping`

### 新增 launch

1. `auto_explore_mapping.launch`
2. `auto_patrol.launch`

### 新增启动脚本

1. `~/Desktop/SpotMicro/scripts/start_auto_explore_mapping.sh`
2. `~/Desktop/SpotMicro/scripts/start_auto_patrol.sh`

### 新增统一配置文件

1. `spot_micro_navigation/config/robot_mode_config.yaml`

---

## 12. 推荐 launch 结构

## 12.1 自动探索建图 launch

建议：

```text
auto_explore_mapping.launch
  -> nav_mode_manager
  -> hector_mapping
  -> periodic_map_saver
  -> laser_wander_explorer
  -> cmd_vel_arbiter
  -> cmd_vel_safety_gate
  -> keyboard_control (remap /cmd_vel -> /cmd_vel_manual)
```

## 12.2 自动巡视 launch

建议：

```text
auto_patrol.launch
  -> nav_mode_manager
  -> laser_wander_explorer
  -> cmd_vel_arbiter
  -> cmd_vel_safety_gate
  -> keyboard_control (remap /cmd_vel -> /cmd_vel_manual)
  -> （可选）map_server + AMCL
```

### 关于地图路径

这里的 `map_server + AMCL` 不建议让用户从命令行手写：

```bash
MAP:=...
```

而建议：

1. 启动脚本先从 `robot_mode_config.yaml` 读取 `common.map_yaml`
2. 再把这个值传给 `auto_patrol.launch`

这样 launch 仍然能保持标准 ROS 写法，而用户操作依然是“一键启动”。

---

## 13. 推荐启动脚本结构

外层不要让用户再手工开很多终端，建议脚本内部使用：

```text
tmux
```

原因：

1. 一个命令即可拉起整套系统
2. 还能保留一个交互 pane 给键盘控制
3. 方便后续查看日志

推荐的使用方式：

### 自动探索建图

```bash
bash ~/Desktop/SpotMicro/scripts/start_auto_explore_mapping.sh
```

脚本内部创建 tmux session，例如：

1. pane 1：ROS 主链路
2. pane 2：键盘控制
3. pane 3：日志监控

### 自动巡视

```bash
bash ~/Desktop/SpotMicro/scripts/start_auto_patrol.sh MAP:=/home/HwHiAiUser/Desktop/SpotMicro/maps/room.yaml
```

同理创建 tmux session。

这样从用户视角看，就真的只有两条命令。

## 13.1 启动脚本的配置读取职责

为了满足“通过配置文件切地图”的要求，两个启动脚本都要承担“读取配置”的职责。

### `start_auto_explore_mapping.sh`

建议读取：

1. `common.scan_topic`
2. `common.cmd_vel_*`
3. `auto_explore_mapping.autosave_*`

这个模式本身不强依赖既有地图，但仍然可以共用统一配置文件。

### `start_auto_patrol.sh`

建议读取：

1. `common.map_yaml`
2. `common.scan_topic`
3. `auto_patrol.use_map_server`
4. `auto_patrol.use_amcl`

这样以后切换巡视地图时：

1. 不改脚本
2. 不改命令
3. 只改 yaml

## 13.2 推荐脚本行为

两个脚本都建议做以下检查：

1. 配置文件是否存在
2. 地图文件是否存在
3. 地图路径是否是 `.yaml`
4. 依赖工作空间是否已经 `source`
5. 是否已经存在同名 tmux session

如果检查失败，脚本应直接提示：

1. 哪个配置项缺失
2. 哪个地图路径不存在
3. 应该去修改哪个配置文件

这样才能真正达到“好用”的标准。

---

## 14. 最终推荐的最小可用版本

如果只做第一版，建议范围控制在下面：

### 第一版一定做

1. `laser_wander_explorer.py`
2. `cmd_vel_arbiter.py`
3. `auto_explore_mapping.launch`
4. `auto_patrol.launch`
5. 两个启动脚本
6. `robot_mode_config.yaml`

### 第一版先不做

1. frontier exploration
2. 固定航点巡逻
3. 巡逻区域语义化管理
4. 自动回充 / 自动回点
5. RViz 图形化操作依赖

---

## 14.1 第一版配置管理的落地要求

第一版必须满足下面这条体验要求：

### 切换地图操作流程

用户只需要：

1. 打开：
   ```text
   robot_mode_config.yaml
   ```
2. 修改：
   ```yaml
   common:
     map_yaml: /home/HwHiAiUser/Desktop/SpotMicro/maps/new_room.yaml
   ```
3. 执行：
   ```bash
   bash ~/Desktop/SpotMicro/scripts/start_auto_patrol.sh
   ```

不需要：

1. 命令行追加地图参数
2. 修改 launch 文件
3. 修改 Python 源码

这条体验要求建议作为后续实现是否合格的验收标准之一。

---

## 15. 最终建议

对当前 SpotMicro + Orange Pi AIpro 的条件，最合理的统一入口方案是：

1. **自动探索建图命令**
   - 低速避障漫游
   - Hector 建图
   - 自动保存地图
   - 手动方向接管优先
   - 配置文件集中管理参数

2. **自动巡视命令**
   - 低速避障漫游
   - 不依赖固定航点
   - 不依赖 RViz 点目标
   - 手动方向接管优先
   - 地图路径来自统一配置文件

而这两个命令背后的关键实现，不是复杂导航算法，而是：

**`自动速度`、`手动速度`、`安全门`、`配置文件读取` 四者的统一组织。**

只要这层设计做好，你以后就可以真正做到：

**只输入两条命令，就能完成“自动建图演示”和“自动巡视演示”。**
