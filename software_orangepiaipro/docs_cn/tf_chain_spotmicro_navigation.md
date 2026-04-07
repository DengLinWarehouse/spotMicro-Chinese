# SpotMicro 导航 TF 链说明：坐标系含义、当前发布者与后续发布责任

> 适用对象：基于本仓库 `software_orangepiaipro/` 的 SpotMicro 四足平台，准备接入雷达导航、SLAM、AMCL 与规划模块的开发者。
>
> 文档目标：把 “TF 链是什么” 讲清楚，并直接对应到当前仓库现有代码，明确导航上车前后每段 TF 应该由谁发布。

---

## 1. 结论先行

对 SpotMicro 这个项目，导航里最关键的 TF 链是：

```text
map
  -> odom
      -> base_footprint
          -> base_link
              -> lidar_link
```

这条链的职责分工应该是：

1. `map -> odom`：由定位模块发布，推荐 `AMCL`
2. `odom -> base_footprint`：由独立里程计模块发布，不能继续使用当前仓库的伪 odom
3. `base_footprint -> base_link`：继续由 `spot_micro_motion_cmd` 发布
4. `base_link -> lidar_link`：继续由 `spot_micro_motion_cmd` 发布静态外参

当前仓库里，`spot_micro_motion_cmd` 已经同时在发：

1. `odom -> base_footprint`
2. `base_footprint -> base_link`
3. `base_link -> lidar_link`
4. 各腿部关节 TF

但其中只有后 3 类适合保留，`odom -> base_footprint` 这一段在导航上车后必须改为由独立 odom 源发布。

---

## 2. TF 链是什么

TF 链本质上就是一棵“坐标变换树”。

它描述的是：

1. 一个坐标系相对于另一个坐标系的位置
2. 一个坐标系相对于另一个坐标系的朝向

例如：

```text
base_link -> lidar_link
```

意思是：

1. `lidar_link` 是雷达坐标系
2. 它相对于 `base_link` 的安装位置和安装角度是固定的

当系统里存在多个坐标系，并且这些坐标系之间能一层一层连起来，就形成了 TF 链。

对机器狗来说，TF 链就是：

1. 机身在哪里
2. 雷达装在哪里
3. 足部关节怎么摆
4. 机器人在局部里程计里走到了哪
5. 机器人在全局地图里又处于哪里

所以你的理解是对的：**TF 链本质上就是机器狗坐标变换关系。**

---

## 3. 这几个核心坐标系分别是什么

## 3.1 `base_link`

`base_link` 是机器人机身主坐标系。

可以把它理解成“绑在机身上的坐标系”。

特点：

1. 跟着机身一起平移
2. 跟着机身一起转向
3. 也会跟着机身一起俯仰、横滚

对机器狗来说：

1. 身体抬头，`base_link` 也抬头
2. 身体侧倾，`base_link` 也侧倾

适合用途：

1. 传感器安装外参
2. 机身姿态表达
3. 机械模型

---

## 3.2 `base_footprint`

`base_footprint` 是导航更喜欢使用的地面投影坐标系。

可以把它理解成：

1. 原点落在机器人投影到地面的参考点
2. 只保留平面位置和偏航角 `yaw`
3. 不保留机身俯仰 `pitch` 和横滚 `roll`

这对四足机器人尤其重要，因为：

1. 机器狗走路时机身会上下起伏
2. 会有明显的点头和左右摆动
3. 如果 2D 导航直接看 `base_link`，这些高频姿态扰动会污染定位和控制

所以在导航里更常用：

```text
odom -> base_footprint
```

而不是直接：

```text
odom -> base_link
```

一句话记忆：

1. `base_link`：真实机身姿态
2. `base_footprint`：压平到地面后的导航姿态

---

## 3.3 `odom`

`odom` 是局部里程计坐标系。

它的职责不是给出长期绝对准确位置，而是给出：

1. 连续的
2. 平滑的
3. 短时间可信的

机器人运动估计。

它回答的问题是：

1. “机器人刚才怎么走的？”
2. “机器人最近相对起点移动了多少？”

一个好的 `odom` 应该：

1. 不跳变
2. 局部连续
3. 短时间误差小

但允许：

1. 长时间漂移

---

## 3.4 `map`

`map` 是全局地图坐标系。

它代表：

1. 机器人在静态环境地图中的位置
2. 全局导航参考

它回答的问题是：

1. “机器人现在在整个环境地图里的哪里？”

`map` 一般由：

1. SLAM
2. AMCL
3. 其他全局定位模块

间接建立。

与 `odom` 的关键区别：

1. `odom` 追求连续，不追求长期绝对准确
2. `map` 追求全局准确，但允许在纠偏时发生跳变

---

## 4. 为什么导航里不能只用一个坐标系

因为这三个需求相互冲突：

1. 控制器需要连续平滑，不希望突然跳一下
2. 全局定位需要不断纠正长期漂移
3. 机身本体又确实会出现俯仰和横滚

因此需要分层：

```text
map -> odom -> base_footprint -> base_link
```

分工如下：

| 坐标系 | 主要职责 |
|--------|----------|
| `map` | 全局真实位置 |
| `odom` | 局部连续运动参考 |
| `base_footprint` | 2D 导航姿态 |
| `base_link` | 真实机身姿态 |

如果把这些职责混在一起，常见后果是：

1. 局部规划器振荡
2. AMCL 修正时控制器跳变
3. 机身俯仰被错误地送进平面导航

---

## 5. 适合 SpotMicro 的 TF 链示意图

## 5.1 当前项目推荐结构

```text
map
 └── odom
      └── base_footprint
           └── base_link
                ├── lidar_link
                ├── front_link
                ├── rear_link
                ├── front_right_shoulder_link
                │    └── front_right_leg_link
                │         └── front_right_foot_link
                │              └── front_right_toe_link
                ├── rear_right_shoulder_link
                │    └── rear_right_leg_link
                │         └── rear_right_foot_link
                │              └── rear_right_toe_link
                ├── front_left_shoulder_link
                │    └── front_left_leg_link
                │         └── front_left_foot_link
                │              └── front_left_toe_link
                └── rear_left_shoulder_link
                     └── rear_left_leg_link
                          └── rear_left_foot_link
                               └── rear_left_toe_link
```

## 5.2 这条链在运动中的含义

### 情况 A：机器人站着不动，但机身上下晃

变化关系：

1. `map` 不变
2. `odom` 不变
3. `base_footprint` 基本不变
4. `base_link` 会变化
5. `lidar_link` 也跟着 `base_link` 变化

含义：

这说明机身姿态变化不应直接等价于机器人平面位置变化。

### 情况 B：机器人向前走 1 米

变化关系：

1. `odom -> base_footprint` 会更新
2. `base_footprint -> base_link` 也可能随步态略变化
3. `map -> odom` 通常不动，除非定位模块在纠偏

### 情况 C：AMCL 发现之前定位有误

变化关系：

1. `map -> odom` 会修正
2. `odom -> base_footprint` 不应该跳变

含义：

这样全局位置被纠正了，但局部控制参考仍然连续。

---

## 6. 当前仓库里 TF 是谁在发

## 6.1 现有 TF 广播器

当前仓库里，核心 TF 广播器就在 `spot_micro_motion_cmd`：

1. 动态 TF 广播器：`transform_br_`
2. 静态 TF 广播器：`static_transform_br_`

定义位置：

[`spot_micro_motion_cmd.h`](D:/DevelopmentProject/ROBOOT/SpotMicro/spotMicro-Chinese/software_orangepiaipro/spot_micro_motion_cmd/include/spot_micro_motion_cmd/spot_micro_motion_cmd.h)

关键成员：

```cpp
tf2_ros::TransformBroadcaster transform_br_;
tf2_ros::StaticTransformBroadcaster static_transform_br_;
```

## 6.2 当前静态 TF

`spot_micro_motion_cmd::publishStaticTransforms()` 当前会发布这些静态变换：

1. `base_link -> front_link`
2. `base_link -> rear_link`
3. `base_link -> lidar_link`
4. 各 `leg_link -> leg_link_cover`
5. 各 `foot_link -> toe_link`

相关代码位置：

[`spot_micro_motion_cmd.cpp`](D:/DevelopmentProject/ROBOOT/SpotMicro/spotMicro-Chinese/software_orangepiaipro/spot_micro_motion_cmd/src/spot_micro_motion_cmd.cpp)

对导航最重要的是：

```cpp
tr_stamped = createTransform("base_link", "lidar_link",
                             x_offset, y_offset, z_offset,
                             0.0, 0.0, yaw_angle);
```

这说明：

1. 当前 `lidar_link` 的外参来自 `spot_micro_motion_cmd.yaml`
2. 这个设计是合理的
3. 后续导航上车后，这一段可以继续保留在当前控制器中

## 6.3 当前动态 TF

`spot_micro_motion_cmd::publishDynamicTransforms()` 当前会发布：

1. `odom -> base_footprint`
2. `base_footprint -> base_link`
3. `base_link -> 各肩关节`
4. `肩关节 -> 大腿`
5. `大腿 -> 小腿/足部`

其中导航最关键的是这两段：

### 当前 `odom -> base_footprint`

```cpp
transform_stamped = eigAndFramesToTrans(getOdometryTransform(), "odom", "base_footprint");
transform_br_.sendTransform(transform_stamped);
```

### 当前 `base_footprint -> base_link`

```cpp
transform_stamped = eigAndFramesToTrans(temp_trans, "base_footprint", "base_link");
transform_br_.sendTransform(transform_stamped);
```

结论：

1. 当前仓库已经具备比较完整的机体 TF 结构
2. 最大问题不在于“没有 TF”
3. 而在于 `odom -> base_footprint` 这一段来源不适合导航

---

## 7. 当前 `odom -> base_footprint` 为什么不能直接用于导航

当前 `odom` 的计算方式不是传感器闭环，而是对速度命令开环积分。

它本质上是在假设：

1. 发了多大的速度命令
2. 机器人就准确执行了多大的位移和转角

这个假设对四足机器人通常不成立，因为会受到：

1. 地面摩擦变化
2. 落脚误差
3. 步态周期性偏差
4. 机身摆动
5. 转向不足

影响。

因此它可以作为：

1. 调试演示用 TF

但不适合作为：

1. AMCL 的预测输入
2. DWA 的速度前向仿真依据
3. 正式导航的 odom 参考

---

## 8. 导航上车后，每段 TF 应该谁来发布

## 8.1 推荐最终责任分工

| TF 段 | 当前发布者 | 导航上车后推荐发布者 | 是否保留现状 |
|-------|------------|----------------------|--------------|
| `map -> odom` | 当前无正式发布者 | `AMCL` | 新增 |
| `odom -> base_footprint` | `spot_micro_motion_cmd` 伪 odom | 独立 odom 节点 / 激光里程计 / EKF | 替换 |
| `base_footprint -> base_link` | `spot_micro_motion_cmd` | `spot_micro_motion_cmd` | 保留 |
| `base_link -> lidar_link` | `spot_micro_motion_cmd` | `spot_micro_motion_cmd` | 保留 |
| `base_link -> 各腿部关节` | `spot_micro_motion_cmd` | `spot_micro_motion_cmd` | 保留 |

## 8.2 推荐的导航阶段 TF 结构

```text
AMCL
  发布 map -> odom

激光里程计 / EKF
  发布 odom -> base_footprint

spot_micro_motion_cmd
  发布 base_footprint -> base_link
  发布 base_link -> lidar_link
  发布 base_link -> 各腿部动态关节
```

## 8.3 必须避免的 TF 冲突

导航上车后，下面两种情况都不允许：

### 冲突 1：两个节点同时发 `odom -> base_footprint`

例如：

1. `spot_micro_motion_cmd` 还在发伪 odom
2. 激光里程计也在发真实 odom

后果：

1. TF 树抖动
2. AMCL 发散
3. DWA 振荡

### 冲突 2：两个节点同时发 `map -> odom`

例如：

1. Hector 或其他 SLAM 还在占用 `map -> odom`
2. AMCL 也在发 `map -> odom`

后果：

1. 全局定位不断打架
2. RViz 里机器人来回跳

---

## 9. 结合当前方案，导航分阶段时 TF 应该怎么切换

## 9.1 阶段 A：建图阶段

目标：

1. 用 Hector SLAM 建静态地图

推荐 TF：

```text
map -> odom              由 Hector 发布
odom -> base_footprint   暂时可由当前伪 odom 提供，仅用于建图演示
base_footprint -> base_link   由 spot_micro_motion_cmd 发布
base_link -> lidar_link       由 spot_micro_motion_cmd 发布
```

说明：

1. 建图阶段对 odom 的要求比 AMCL 阶段低
2. 但如果伪 odom 太差，地图质量仍会下降
3. 有条件时，建图阶段也建议尽早换成独立 odom

## 9.2 阶段 B：已知图定位阶段

目标：

1. 用 AMCL 在静态地图中定位

推荐 TF：

```text
map -> odom              由 AMCL 发布
odom -> base_footprint   由独立 odom 节点发布
base_footprint -> base_link   由 spot_micro_motion_cmd 发布
base_link -> lidar_link       由 spot_micro_motion_cmd 发布
```

此阶段必须做的改动：

1. 关闭 `spot_micro_motion_cmd` 中的 `publish_odom`

推荐配置：

```yaml
publish_odom: false
```

## 9.3 阶段 C：完整导航阶段

目标：

1. `AMCL + A* + 局部跟踪/DWA + /cmd_vel`

TF 不再变化，继续沿用阶段 B 的结构。

---

## 10. 适合 SpotMicro 的工程建议

## 10.1 哪些 TF 继续放在 `spot_micro_motion_cmd`

建议继续保留在当前控制器中：

1. `base_footprint -> base_link`
2. `base_link -> lidar_link`
3. 机体到各腿部关节的 TF

原因：

1. 它们本来就直接依赖当前步态和机身状态
2. 放在低层控制器里最自然
3. 不需要额外复制机器人运动学逻辑

## 10.2 哪些 TF 必须迁出

必须迁出或关闭：

1. `odom -> base_footprint` 的伪 odom 发布

原因：

1. 这段应该由导航里程计系统负责
2. 不能继续由命令积分来冒充真实运动估计

## 10.3 雷达外参放在哪里更合适

当前仓库把雷达外参放在：

[`spot_micro_motion_cmd.yaml`](D:/DevelopmentProject/ROBOOT/SpotMicro/spotMicro-Chinese/software_orangepiaipro/spot_micro_motion_cmd/config/spot_micro_motion_cmd.yaml)

参数包括：

1. `lidar_x_pos`
2. `lidar_y_pos`
3. `lidar_z_pos`
4. `lidar_yaw_angle`

短期建议：

1. 先继续放在这里

长期更合理的做法：

1. 单独抽到导航或传感器描述配置中

但这不是当前优先级。

---

## 11. 一个最容易记住的理解方式

把这几个坐标系记成下面四句话：

1. `map`：我在环境地图里的哪里
2. `odom`：我最近是怎么连续走过来的
3. `base_footprint`：我在地面上的导航姿态
4. `base_link`：我机身真实怎么摆

再加一句：

5. `lidar_link`：雷达装在机身哪里

---

## 12. 对当前项目的最终建议

如果只保留一句工程结论，就是：

**导航上车后，保留 `spot_micro_motion_cmd` 对机身和传感器的 TF 发布职责，但把 `odom -> base_footprint` 从当前伪 odom 中剥离出来，交给独立 odom 源；再由 `AMCL` 负责 `map -> odom`。**

这样分工最清晰，也最符合后续 `Hector/AMCL/A*/局部跟踪` 的落地路径。
