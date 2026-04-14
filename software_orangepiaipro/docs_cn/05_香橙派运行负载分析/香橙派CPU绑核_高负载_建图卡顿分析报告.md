# 香橙派 CPU 绑核、高负载与建图卡顿分析报告

> 适用对象：当前 SpotMicro + Orange Pi AIpro + ROS Noetic + RPLidar + Hector Mapping 的实机环境。
>
> 目的：对“建图时香橙派负载过高、前三核很忙第四核不怎么参与、系统容易卡顿甚至死机”的问题，做一次系统性的阶段分析与结论沉淀。

---

## 1. 问题背景

在当前机器狗实机建图过程中，出现了以下典型现象：

1. 启动雷达、运动控制、Hector 建图后，香橙派整体负载明显上升。
2. 若同时叠加 XRDP / RViz，系统更容易卡顿、掉线、黑屏或假死。
3. 观察 CPU 核心使用时，发现前三个核心长期较忙，而第四个核心明显不怎么参与。
4. 用户因此怀疑：
   - 是否香橙派只启用了 3 个核；
   - 是否第 4 个核未工作；
   - 是否系统调度异常；
   - 是否硬件算力本身不足。

在本次排查中，已经对 CPU 在线状态、进程 CPU affinity、父子进程链路、系统绑核配置、建图高负载进程状态等进行了逐步验证。

---

## 2. 关键问题清单

本次实际排查聚焦的是以下几个核心问题：

1. 第 4 个 CPU 核是否真正在线？
2. 第 4 个 CPU 核是否可以被 ROS 关键进程使用？
3. 为什么前三核高而第四核低？
4. 高负载到底来自：
   - 算法计算；
   - 进程绑核；
   - I2C / PWM 控制板阻塞；
   - 远程桌面图形渲染；
   - 还是其他系统级因素？
5. 后续应该优先优化哪一层？

---

## 3. 现场命令与关键日志证据

以下内容均来自当前实机排查过程。

## 3.1 CPU 在线状态

执行：

```bash
cat /sys/devices/system/cpu/online
```

输出：

```text
0-3
```

### 结论

1. `cpu0 cpu1 cpu2 cpu3` 全部在线。
2. 不是系统只开了 3 个核。
3. 第 4 个核并没有被关闭。

---

## 3.2 高负载时的 `top` 观测

建图运行中抓取到如下典型状态：

```text
top - 10:19:34 up 10 min,  1 user,  load average: 19.17, 15.96, 8.83
Tasks: 324 total,   2 running, 322 sleeping,   0 stopped,   0 zombie
%Cpu(s): 34.3 us,  6.1 sy,  0.0 ni, 57.3 id,  0.0 wa,  0.9 hi,  1.4 si,  0.0 st

PID    COMMAND              %CPU  STAT
9102   hector_mapping      113.2  R
8986   spot_micro_moti      22.8  S
8985   i2cpwm_board          4.6  D
8885   rplidarNode           3.0  S
```

### 直接观察结论

1. `hector_mapping` 是当前主 CPU 热点。
2. `spot_micro_motion_cmd` 也持续占用 CPU。
3. `i2cpwm_board` 处于 `D` 状态，说明其在不可中断睡眠，通常意味着：
   - 驱动等待；
   - I/O 等待；
   - 设备访问阻塞；
   - 或线程层面正在等待不可快速中断的内核同步。
4. `load average` 很高，但总 CPU 仍未完全打满，说明：
   - 问题不只是“算不过来”；
   - 还可能夹杂阻塞任务；
   - `load average` 不能简单等同于“4 核全满载计算”。

---

## 3.3 关键进程 affinity（CPU 亲和性）检查

执行：

```bash
taskset -pc 9102
taskset -pc 8986
taskset -pc 8985
```

输出：

```text
pid 9102's current affinity list: 0-2
pid 8986's current affinity list: 0-2
pid 8985's current affinity list: 0-2
```

### 结论

这一步是本次排查的**最关键证据**。

它直接说明：

1. `hector_mapping` 只能运行在 `CPU0 CPU1 CPU2`
2. `spot_micro_motion_cmd` 只能运行在 `CPU0 CPU1 CPU2`
3. `i2cpwm_board` 只能运行在 `CPU0 CPU1 CPU2`
4. `CPU3` 并不是“不会工作”，而是这些关键进程**根本不允许用它**

因此，“前三核高、第四核闲”的现象不是偶然，而是 **CPU affinity 被限制为 `0-2` 的直接结果**。

---

## 3.4 关键进程父进程链检查

执行：

```bash
ps -fp 8927
ps -fp 8985
ps -fp 8986
ps -fp 9102
```

输出关键信息如下：

```text
8927 -> roslaunch spot_micro_motion_cmd motion_cmd.launch
8985 -> i2cpwm_board  (PPID 8927)
8986 -> spot_micro_motion_cmd_node (PPID 8927)
9102 -> hector_mapping (PPID 9023)
```

继续检查父进程 affinity：

```bash
taskset -pc 8927
```

输出：

```text
pid 8927's current affinity list: 0-2
```

### 结论

1. 子进程继承了父进程的 CPU affinity。
2. `motion_cmd.launch` 对应的 `roslaunch` 进程本身就是 `0-2`。
3. 因此其下游关键节点自然全都落在 `0-2`。

---

## 3.5 当前 shell 自身 affinity 检查

执行：

```bash
echo $$
taskset -pc $$
```

输出：

```text
10419
pid 10419's current affinity list: 0-2
```

### 结论

这说明当前 shell 自己就已经被限制到了 `0-2`。

因此，只要是在这个 shell 中启动的 ROS 节点，都会默认继承：

```text
0-2
```

这一步进一步把问题范围缩小到了：

**不是 ROS 节点单独设置了绑核，而是启动它们的 shell / 终端环境本身已经被绑核。**

---

## 3.6 `pstree` 父子链路检查

执行：

```bash
pstree -sap 9102
```

输出核心链路如下：

```text
systemd
  -> bash
    -> cursor-server
      -> node
        -> ptyHost
          -> bash
            -> roslaunch
              -> hector_mapping
```

### 结论

1. 当前 ROS 启动链路是在 Cursor 终端 / ptyHost 链中完成的。
2. 绑定到 `0-2` 的很可能不是 `hector_mapping` 自己，而是更上游的终端链路环境。
3. 也就是说，Cursor 终端里的 shell 很可能从更上层继承了 `0-2`，再继续向下传递给所有 ROS 子进程。

---

## 3.7 systemd 绑核配置排除

执行：

```bash
systemctl show --property=CPUAffinity
grep -R "CPUAffinity" /etc/systemd /lib/systemd 2>/dev/null
sudo grep -R "CPUAffinity" /etc/systemd /lib/systemd 2>/dev/null
```

结果：

```text
未发现明确的 systemd CPUAffinity 绑定配置
```

### 结论

1. 当前问题基本不是 systemd 全局配置导致的。
2. 更像是用户会话 / 终端环境 / 上层启动链路带来的 CPU affinity 继承。

---

## 3.8 `i2cpwm_board` 进程堆栈

执行：

```bash
sudo cat /proc/8985/stack
```

输出：

```text
[<0>] __switch_to+0xb4/0x118
[<0>] futex_wait_queue_me+0xb8/0x138
[<0>] futex_wait+0xf4/0x228
[<0>] do_futex+0x458/0x8b8
[<0>] __arm64_sys_futex+0x124/0x1b8
[<0>] el0_svc_common.constprop.0+0x94/0x1a8
[<0>] do_el0_svc+0x34/0xa0
[<0>] el0_svc+0x1c/0x28
[<0>] el0_sync_handler+0x8c/0xb0
[<0>] el0_sync+0x158/0x180
```

### 解释

1. 这表明采样时 `i2cpwm_board` 正在等待 futex，同步阻塞在用户态/线程同步层面。
2. 这次采样没有直接显示它卡在内核 I2C 驱动函数里。
3. 但它仍然说明该进程**不是一个持续健康并行运行的高效计算任务**。

### 与此前日志的关系

此前系统中已出现过：

1. `hisi-i2c ... slave address not acknowledged`
2. `Ascend LPM fault`
3. 系统高负载与阻塞并存

因此当前不能直接下结论说：

- `i2cpwm_board` 当前堆栈就等于 I2C 故障现场

但可以说：

**它是系统负载与实时性问题中的高风险参与者，需要继续关注。**

---

## 3.9 内核日志附加信息

执行：

```bash
sudo dmesg -T | tail -n 100 | grep -Ei "i2c|pwm|hisi|ack|timeout"
```

当前抓取时主要出现：

```text
[bbox] [device-0] blackbox receive [LPM] exception ...
```

虽然这次没有直接再次抓到 `i2c no ack`，但结合之前已经出现过的 I2C 异常与 NPU / LPM 异常，可以判断：

1. 当前系统不是“纯净的只受 SLAM 影响”状态；
2. 板载底层异常与机器人实时控制链路存在叠加影响。

---

## 4. 核心分析结论

## 4.1 第 4 核不是坏了，也不是没开

根据：

```bash
cat /sys/devices/system/cpu/online
```

输出：

```text
0-3
```

可以明确：

1. 第 4 核在线；
2. 系统识别正常；
3. 内核线程也在 CPU3 上运行；
4. 因此 CPU3 不是失效状态。

---

## 4.2 第 4 核没有参与关键负载，是因为关键 ROS 进程被绑到 0-2

这是本次最核心结论。

关键证据：

```text
hector_mapping       -> 0-2
spot_micro_motion_cmd -> 0-2
i2cpwm_board         -> 0-2
当前 shell           -> 0-2
父 roslaunch         -> 0-2
```

因此此前观察到的：

1. 前三核忙
2. 第四核闲

并不是 Linux 调度“偏心”，而是这些进程**根本无法跑到 CPU3**。

---

## 4.3 当前终端环境是问题源头之一

由于：

```bash
taskset -pc $$
```

输出：

```text
0-2
```

说明：

1. 你当前使用的终端 shell 已经被限制在前三核；
2. 该 shell 启动的所有 ROS 进程都会继承这个限制；
3. 所以只要启动路径不变，ROS 关键节点就一直只能用前三核。

从 `pstree` 看，这个终端来自 Cursor 的 pty host 链路，因此：

**当前问题与 Cursor 终端启动环境高度相关。**

---

## 4.4 当前负载问题不只是算力问题，还叠加了阻塞问题

高负载状态下同时出现：

1. `hector_mapping` 高 CPU；
2. `spot_micro_motion_cmd` 持续占用 CPU；
3. `i2cpwm_board` 出现 `D` 状态；
4. `load average` 很高，但 CPU 并未全满；

这说明：

1. 问题并非纯粹“CPU 不够”；
2. 还夹杂了等待与阻塞；
3. 机器人控制链的实时性会因此进一步恶化。

这也解释了为什么现场会出现：

1. 建图卡顿；
2. SSH / XRDP 更容易掉；
3. 系统整体“像死机”，但又未必是 4 核全算满。

---

## 4.5 当前系统属于“多因素叠加”而非单点故障

当前阶段更合理的问题画像是：

1. **CPU affinity 把关键计算进程限制在 0-2**
2. **Hector Mapping 本身是主要 CPU 热点**
3. **I2C/PWM 控制链可能存在同步等待或实时性问题**
4. **系统还曾出现 NPU / LPM / bbox 相关底层告警**
5. **如果叠加 XRDP / RViz，会进一步放大整体不稳定**

因此不应把问题简单归因为：

- “第 4 核没工作”

更准确的说法应该是：

**关键进程被绑核 + 建图热点线程 + 控制链阻塞 + 底层系统不稳定，共同导致了当前卡顿与高负载表现。**

---

## 5. 当前阶段的优化优先级

推荐把优化分成三层。

## 5.1 第一优先级：解除关键 ROS 进程的 `0-2` 绑核

这是当前最明确、最可执行、最值得先做的优化项。

### 推荐先做临时验证

在启动 ROS 之前，先把当前 shell 放开到四核：

```bash
taskset -pc 0-3 $$
taskset -pc $$
```

或直接开一个新的四核 shell：

```bash
taskset -c 0-3 bash
```

然后在这个新 shell 里启动：

1. `motion_cmd.launch`
2. `slam_hector_mapping.launch`

再检查新进程：

```bash
taskset -pc <hector_mapping_pid>
taskset -pc <spot_micro_motion_cmd_pid>
taskset -pc <i2cpwm_board_pid>
```

目标结果：

```text
0-3
```

### 预期收益

1. 让 CPU3 参与关键进程调度；
2. 给 `hector_mapping` 更多调度空间；
3. 减轻前三核集中拥堵；
4. 进一步观察系统负载是否改善。

---

## 5.2 第二优先级：减少图形链路负担

此前已多次观察到：

1. XRDP + RViz 会显著拉高负载；
2. 远程桌面渲染容易放大系统卡顿。

因此建议：

1. 建图时尽量不用 XRDP 中的 RViz 实时显示；
2. 采用：
   - 纯后台建图
   - 自动周期存图
   - 任务结束后再查看结果图
3. 如果必须实时看图，尽量迁移显示负担到外部主机。

---

## 5.3 第三优先级：继续跟踪 `i2cpwm_board` / I2C 控制链

虽然这次 `stack` 没直接显示卡在 I2C 驱动，但结合前期已有异常：

1. `i2c no ack`
2. `hisi-i2c ... slave address not acknowledged`
3. `i2cpwm_board` 高负载场景下进入 `D`

仍建议把它作为重点观察对象。

### 推荐继续观察的方向

1. 舵机控制板供电是否稳定；
2. I2C 线缆和接插件是否可靠；
3. 控制板响应是否存在偶发阻塞；
4. 运动控制频率是否过高；
5. 是否有驱动层等待导致动作链路拖慢。

---

## 6. 后续建议的验证步骤

建议按以下顺序做下一轮验证。

## 6.1 临时四核放开验证

```bash
taskset -c 0-3 bash
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
source ~/Desktop/SpotMicro/spotmicro_ws/devel/setup.bash
```

然后重新启动建图链。

验证：

```bash
taskset -pc <关键PID>
```

目标：

```text
0-3
```

## 6.2 对比放开前后的负载

在相同建图流程下对比：

1. `top`
2. `load average`
3. `hector_mapping` CPU 占用
4. 系统卡顿程度
5. SSH / 终端响应情况

## 6.3 继续跟踪控制链阻塞

在高负载时再抓：

```bash
ps -eLo pid,tid,psr,pcpu,stat,comm --sort=-pcpu | head -n 30
sudo cat /proc/<i2cpwm_board_pid>/stack
sudo dmesg -T | tail -n 200
```

目标：

1. 判断 `i2cpwm_board` 是否稳定进入 `D`
2. 判断是否再次出现明确 I2C 错误

## 6.4 查清 Cursor 终端链为什么默认是 `0-2`

这一项不是当前最紧急，但后续值得追查。

建议继续顺着父进程链检查：

```bash
taskset -pc 7347
taskset -pc 7570
taskset -pc 5208
taskset -pc 4846
```

目的：

1. 找到最上游哪一层开始变成 `0-2`
2. 判断是否为 Cursor 终端链默认行为
3. 决定后续是否换用普通 SSH shell / tmux shell 启动 ROS

---

## 7. 对当前主线任务的建议

结合当前阶段的工程目标，建议按如下原则继续推进：

### 7.1 机器人主线

继续优先推进：

1. 雷达建图
2. 自动探索建图
3. 自动巡视
4. 手动接管能力

### 7.2 不建议当前阶段继续深挖的点

暂不建议把主要精力投入到：

1. NPU / Ascend 恢复
2. RViz 图形重度依赖
3. 复杂 frontier exploration

### 7.3 当前最实际的路线

推荐路线：

1. 先解除 ROS 关键进程 `0-2` 绑核
2. 减少 XRDP / RViz 实时显示
3. 优先跑后台建图 + 自动保存地图
4. 再实现自动探索建图与自动巡视的一键启动方案

---

## 8. 阶段性结论

本轮排查已经得到一个非常明确且可操作的阶段结论：

### 结论 A：第 4 核不是失效，而是关键进程被限制不能使用它

这已经有直接证据，不再是猜测。

### 结论 B：当前 shell 就是绑核源头之一

当前用于启动 ROS 的 shell 已被限制为 `0-2`，其子进程全部继承了这一限制。

### 结论 C：系统卡顿不只是算力不足，还叠加了阻塞与控制链问题

特别是：

1. `hector_mapping` 高 CPU
2. `spot_micro_motion_cmd` 持续占用 CPU
3. `i2cpwm_board` 在高负载场景下表现异常

### 结论 D：当前最应该先做的优化，是放开到 `0-3` 再验证系统行为

这是最直接、成本最低、最可能立刻改善现象的一步。

---

## 9. 推荐作为后续排障基线的命令

### 9.1 检查 CPU 在线

```bash
cat /sys/devices/system/cpu/online
```

### 9.2 检查当前 shell 绑核

```bash
echo $$
taskset -pc $$
```

### 9.3 启动前放开到四核

```bash
taskset -pc 0-3 $$
```

或：

```bash
taskset -c 0-3 bash
```

### 9.4 高负载时看进程与线程

```bash
top
ps -eLo pid,tid,psr,pcpu,stat,comm --sort=-pcpu | head -n 30
```

### 9.5 检查关键进程 affinity

```bash
taskset -pc <PID>
```

### 9.6 检查控制链堆栈

```bash
sudo cat /proc/<PID>/stack
```

### 9.7 检查相关内核日志

```bash
sudo dmesg -T | tail -n 200
```

---

## 10. 最终一句话总结

**当前香橙派建图卡顿与负载异常的核心原因，不是第 4 核失效，而是机器人关键 ROS 进程被限制在 `CPU0-2` 上运行，同时叠加了 `hector_mapping` 的高 CPU 占用、控制链阻塞风险以及系统底层不稳定因素。当前最值得优先验证的优化方向，是先解除 `0-2` 绑核限制，再继续观察建图链路与控制链表现。**
