# Orange Pi AI Pro 机器狗环境配置总结（2026-03-26）

> 适用对象：后续需要在 **Orange Pi AI Pro** 上复刻 SpotMicro 机器狗环境的维护者。  
> 本文基于一次真实落地过程整理，不是泛泛而谈的理论说明，而是按“实际踩坑 → 实际解决”的方式总结。  
> 目标是让后续设备配置时，尽量一次走对，避免把时间浪费在重复报错和环境污染上。

---

## 1. 本次验证环境

### 硬件
- 主控：Orange Pi AI Pro
- 舵机驱动：PCA9685
- 连接方式：I2C

### 系统
- 镜像：`opiaipro_ubuntu22.04_desktop_aarch64_20241128`
- 架构：`aarch64`
- 日期基线：`2026-03-26`

### 软件总体策略
- **ROS base 工作区**：`~/Desktop/SpotMicro/ros_noetic_ws`
- **SpotMicro overlay 工作区**：`~/Desktop/SpotMicro/spotmicro_ws`
- **源码/文档仓库**：`~/Desktop/SpotMicro/spotMicro-Chinese/software_orangepiaipro`
- **连接方式**：`spotmicro_ws/src` 内的 SpotMicro 包统一软链接到 `software_orangepiaipro`

---

## 2. 必须坚持的总体原则

### 原则 1：不要把 ROS base 和业务包混在一个工作区

本次实践证明，最稳妥的方式是拆成两层：

1. `ros_noetic_ws`
   - 只负责源码编译 ROS1 Noetic 基础能力
   - 包括 `roscore`、`roscpp`、`roslaunch`、`tf`、`urdf` 等
2. `spotmicro_ws`
   - 只放机器狗相关 ROS 包
   - 通过 `source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash` 叠加在 ROS base 之上

### 为什么必须分层
- 便于排错：能快速判断问题是在 ROS base 还是 SpotMicro 业务包
- 便于升级：以后调整机器狗包时，不会误伤 ROS base
- 便于复用：以后其他香橙派只需要复刻同样结构即可

### 不推荐的做法
- 直接在 `software_orangepiaipro` 根目录原地 `catkin_make`
- 把 SpotMicro 包直接复制进 `ros_noetic_ws/src`
- 在带 Conda 污染的 shell 中直接编译 ROS 或业务包

---

## 3. 本次最终采用的目录结构

```text
~/Desktop/SpotMicro/
├── ros_noetic_ws/          # ROS1 Noetic 源码基础工作区
├── spotmicro_ws/           # SpotMicro overlay 工作区
└── spotMicro-Chinese/      # 中文仓库与文档
    └── software_orangepiaipro/
```

建议以后所有 Orange Pi AI Pro 机器狗环境都沿用这个结构。

---

## 4. ROS1 Noetic 在 Ubuntu 22.04 上的注意事项

### 结论
- 在本次环境中，**不能依赖 Ubuntu 22.04 上的官方 ROS1 apt 二进制安装流程**
- 实际成功路径是：**ROS1 Noetic 源码编译**

### 经验判断
- Ubuntu 22.04 上做 ROS1 Noetic 时，不要先假设“apt 一条命令就能装好”
- 直接准备按源码编译路径来做，反而更高效

### base 工作区建议
- 工作区：`~/Desktop/SpotMicro/ros_noetic_ws`
- 构建命令优先统一为：

```bash
catkin_make -DCATKIN_ENABLE_TESTING=OFF -DPYTHON_EXECUTABLE=/usr/bin/python3
```

### 为什么要显式指定 `/usr/bin/python3`
因为本次环境中出现过 **Conda / 用户 Python 包污染**，如果不强制指定系统 Python，后续会反复踩坑。

---

## 5. 实际遇到的问题与解决办法

下面这部分是最重要的复用内容。

### 5.1 Shell 多行命令续行失败

#### 现象
- `\` 续行后命令没有真正接上
- 后一行被 shell 当成新命令执行
- 出现 `command not found`

#### 根因
- 反斜杠 `\` 后面带了空格
- 复制到终端时格式被破坏

#### 解决办法
- 对复杂命令优先使用**单行命令**
- 如果必须续行，`\` 必须是该行最后一个字符
- 后续文档和操作文件尽量写成可直接复制的单行形式

#### 建议
- 后续部署时，优先把命令写进文本文件，再复制到设备执行

---

### 5.2 apt 包名与预期不一致

#### 现象
- 某些包名写了以后提示 `Unable to locate package`
- 例如：
  - `python3-catkin-pkg-modules`
  - `python3-rospkg-modules`

#### 解决办法
本次实际可用的是：

```bash
python3-catkin-pkg
python3-rospkg
```

#### 经验
- Ubuntu 22.04 / Orange Pi 的 apt 仓库中，包名不一定和其他教程完全一致
- 遇到 `Unable to locate package`，先用：

```bash
apt-cache search <关键字>
```

不要盲目重复执行原命令。

---

### 5.3 ROS base 源码编译缺失系统依赖

#### 实际遇到的关键缺失依赖
- `TinyXML2`
- `lz4`
- `urdfdom_headers`
- `orocos_kdl`
- `GPGME`
- `defusedxml`（运行时）

#### 典型解决包
```bash
sudo apt install -y \
  libtinyxml2-dev \
  libtinyxml-dev \
  liblz4-dev \
  libbz2-dev \
  liburdfdom-dev \
  liburdfdom-headers-dev \
  liborocos-kdl-dev \
  libkdl-parser-dev \
  libgpgme-dev \
  python3-defusedxml
```

#### 经验
- 源码编译 ROS1 Noetic 时，不要期待一次性零报错
- 最稳的方法是：**根据报错逐个补系统依赖**
- 每解决一个依赖后，重新：

```bash
rm -f build/CMakeCache.txt
catkin_make --force-cmake ...
```

---

### 5.4 Conda / 用户 Python 污染 ROS 构建

#### 实际现象 1：`em` / `empy` 冲突
报错形式：
- `module 'em' has no attribute 'RAW_OPT'`

#### 根因
- Python 实际导入的是：
  - `~/.local/lib/python3.10/site-packages/em.py`
  - 版本：`4.2.1`
- ROS Noetic 的消息生成器并不兼容这个版本

#### 解决办法
1. 退出 Conda：
```bash
conda deactivate
unset PYTHONPATH
unset PYTHONHOME
```
2. 检查实际导入位置：
```bash
/usr/bin/python3 - <<'PY'
import sys, em
print(sys.executable)
print(em.__file__)
print(getattr(em, "__version__", "<no __version__>"))
print(hasattr(em, "RAW_OPT"))
PY
```
3. 卸载用户目录里的冲突包，回到系统 `python3-empy`

#### 实际现象 2：overlay 工作区又跑回 Conda Python
表现为：
- `Found PythonInterp: /usr/local/miniconda3/bin/python3`
- 缺 `catkin_pkg`
- 测试系统 / gmock 行为异常

#### 解决办法
在 ROS/SpotMicro 编译前固定做法：

```bash
conda deactivate
unset PYTHONPATH
unset PYTHONHOME
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
catkin_make -DCATKIN_ENABLE_TESTING=OFF -DPYTHON_EXECUTABLE=/usr/bin/python3
```

#### 长期建议
- ROS 相关终端尽量不要让 `(base)` 自动激活
- 必要时使用：

```bash
bash --noprofile --norc
```

启动一个干净 shell

---

### 5.5 `rosconsole` 与 Ubuntu 22.04 的 `log4cxx` 兼容问题

#### 实际现象
在 `ros_noetic_ws` 编译过程中，`rosconsole_log4cxx.cpp` 出现大量 `shared_ptr` / `AppenderPtr` 相关错误。

#### 根因
- Ubuntu 22.04 自带的 `log4cxx` API 与 ROS Noetic 原始 `rosconsole` 存在兼容问题

#### 实际解决办法
- 替换 `rosconsole` 为兼容 `log4cxx-0.12` 的修正版本

#### 经验
- 这类问题不属于 SpotMicro 本身，而属于 **Jammy + Noetic** 的基础兼容问题
- 一旦 base 工作区解决，后续机器狗包才能继续推进

---

### 5.6 `shared_mutex` / C++17 问题

#### 实际现象
报错形式类似：
- `std::shared_mutex is only available from C++17 onwards`

#### 触发位置
- ROS base 中的 `kdl_parser`、`urdf`
- SpotMicro overlay 中的 `spot_micro_motion_cmd`

#### 根因
- Ubuntu 22.04 下 `log4cxx` 相关头文件要求至少 `C++17`
- 但原始 ROS/SpotMicro 某些包仍写死在 `C++14`

#### 解决办法
1. ROS base 中对相关包强制切到 C++17
2. SpotMicro 中对 `spot_micro_motion_cmd` 和 `spot_micro_kinematics_cpp` 切到 C++17

#### SpotMicro 实际改动点
- `spot_micro_motion_cmd/CMakeLists.txt`
  - `add_compile_options(-std=c++14)` 改为 `gnu++17`
- `spot_micro_motion_cmd/libs/spot_micro_kinematics_cpp/CMakeLists.txt`
  - `set(CMAKE_CXX_STANDARD 14)` 改为 `17`

#### 经验
- 后续其他香橙派环境若再遇到 `shared_mutex` 报错，优先检查：
  - 当前目标实际编译参数是不是 `-std=gnu++17`

---

### 5.7 overlay 工作区测试系统误打开，触发 gmock 问题

#### 现象
- 配置 `spotmicro_ws` 时出现 `/usr/src/gmock` 相关错误

#### 根因
- `CATKIN_ENABLE_TESTING` 没有效关闭
- 或缓存中仍保留之前 ON 的结果

#### 解决办法
```bash
rm -rf build devel
source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash
catkin_make -DCATKIN_ENABLE_TESTING=OFF -DPYTHON_EXECUTABLE=/usr/bin/python3
```

#### 经验
- 对于部署环境，**一律建议关闭 testing**

---

### 5.8 `ros-i2cpwmboard` 的 I2C 库问题

#### 现象
- `Could not find I2C_LIB using the following names: i2c`

#### 解决办法
```bash
sudo apt install -y libi2c-dev i2c-tools python3-smbus
```

#### 验证方式
```bash
ls /usr/lib/aarch64-linux-gnu/libi2c.so*
dpkg -L libi2c-dev | grep libi2c
```

---

### 5.9 `spot_micro_launch` 依赖 `hector_geotiff`

#### 现象
- 编译 overlay 时卡在：
  - `Could not find a package configuration file provided by "hector_geotiff"`

#### 根因
- `spot_micro_launch` 中包含 SLAM / hector 相关启动配置
- 但当前目标只是先把机器狗主链路跑起来，不需要先解这个依赖

#### 解决办法
临时跳过：
```bash
touch ~/Desktop/SpotMicro/spotmicro_ws/src/spot_micro_launch/CATKIN_IGNORE
```

#### 经验
- 机器狗主链路优先级高于 SLAM
- 先跑通运动控制，再回头处理 hector slam 相关扩展

---

### 5.10 `tf2_eigen` 头文件缺失

#### 现象
- `tf2_eigen/tf2_eigen.h: No such file or directory`

#### 实际触发点
- `spot_micro_motion_cmd.cpp`
- `include/spot_micro_motion_cmd/utils.h`
- `src/utils.cpp`

#### 根因
- 代码中残留 `tf2_eigen` include
- 实际只用到了“把 `Eigen::Affine3d` 转成 `geometry_msgs::TransformStamped`”这个能力

#### 实际解决办法
- 不再额外扩展 base 工作区
- 直接删除 `tf2_eigen` include
- 在 `utils.cpp` 中手动将 `Eigen::Affine3d` 转成 `TransformStamped`

#### 经验
- 对于这类单点依赖，如果功能很简单，优先改业务包源码去掉无谓依赖
- 这样比继续扩大 base 工作区依赖更稳

---

### 5.11 `spot_micro_motion_cmd/launch/motion_cmd.launch` 文件被污染

#### 现象
- launch 文件中混入异常文本，存在 XML 解析风险

#### 解决办法
- 已修正文档仓库中的 `motion_cmd.launch`

#### 经验
- 迁移旧工程时，不能默认 launch 文件百分百可信
- 遇到奇怪 XML 报错时，优先直接打开文件检查

---

### 5.12 Orange Pi I2C 参数名与 launch 文件不一致

#### 现象
- launch 中使用：
  - `i2c_bus=/dev/i2c-7`
- 但源码实际读取的是：
  - `i2c_device_number`

#### 根因
- 参数名和源码不匹配，launch 启动后可能根本没有用上正确总线

#### 实际解决办法
将 launch 文件统一改为：

```xml
<param name="i2c_device_number" value="7" />
```

#### 重要提醒
- `7` 只是本次 Orange Pi AI Pro 的目标值
- **后续每台设备都必须实际确认总线号**

验证命令：
```bash
ls /dev/i2c*
sudo i2cdetect -y 7
```

---

## 6. SpotMicro overlay 工作区的实际迁移策略

### 首批迁移包
本次先迁以下 8 个包：

- `ros-i2cpwmboard`
- `spot_micro_motion_cmd`
- `spot_micro_launch`
- `spot_micro_rviz`
- `spot_micro_keyboard_command`
- `servo_move_keyboard`
- `spot_micro_plot`
- `lcd_monitor`

### 实际经验：不要简单只用 root 包，优先“root 结构 + extensions 覆盖”

#### 建议做法
- 用根目录版本保留完整包结构和 launch/config
- 用 `extensions/packages` 中的 Python3 友好脚本覆盖部分文件

#### 本次实际覆盖过的内容
- `spot_micro_keyboard_command/scripts/spotMicroKeyboardMove.py`
- `servo_move_keyboard/scripts/servoMoveKeyboard.py`
- `servo_move_keyboard/scripts/servoConfigTest.py`
- `spot_micro_plot/scripts/spotMicroPlot.py`
- `spot_micro_plot/scripts/spot_micro_kinematics_python/`
- `lcd_monitor/src/lcd_monitor/I2C_LCD_driver.py`
- `lcd_monitor/src/lcd_monitor/sm_lcd_driver.py`

#### 经验
- 旧 ROS 项目迁移到 Noetic 时，最容易出问题的是 Python 脚本，不一定是 C++
- 所以“包结构从 root 来，脚本优先参考 extensions”是比较稳的策略

---

## 7. 本次最终可复用的标准流程

### 阶段 A：搭 ROS base
1. 创建 `ros_noetic_ws`
2. 源码编译 ROS1 Noetic
3. 修正 Jammy/Noetic 兼容问题
4. 确认 `roscore` 正常启动

### 阶段 B：搭 SpotMicro overlay
1. 创建 `spotmicro_ws`
2. `source ~/Desktop/SpotMicro/ros_noetic_ws/devel/setup.bash`
3. 运行 `software_orangepiaipro/scripts/link_spotmicro_workspace.sh` 建立软链接
4. 只在 `software_orangepiaipro` 中维护源码与 YAML，避免 overlay 漂移
5. 暂时屏蔽 `spot_micro_launch`
6. 编译 overlay

### 阶段 C：运行验证
1. `roscore`
2. `rospack find i2cpwm_board`
3. `rospack find spot_micro_motion_cmd`
4. `ls /dev/i2c*`
5. `sudo i2cdetect -y <总线号>`
6. `roslaunch i2cpwm_board i2cpwm_node.launch`
7. `rosrun servo_move_keyboard servoMoveKeyboard.py`
8. `rosrun spot_micro_motion_cmd spot_micro_motion_cmd_node`

---

## 8. 强烈建议写入后续部署规范的“硬规则”

下面这些建议，建议以后直接变成项目内部规范：

### 规则 1
**任何香橙派机器狗环境，一律采用双工作区：**
- `ros_noetic_ws`
- `spotmicro_ws`

### 规则 2
**任何 ROS 编译和运行前，先退出 Conda：**

```bash
conda deactivate
unset PYTHONPATH
unset PYTHONHOME
```

### 规则 3
**统一使用系统 Python：**

```bash
-DPYTHON_EXECUTABLE=/usr/bin/python3
```

### 规则 4
**统一关闭 testing：**

```bash
-DCATKIN_ENABLE_TESTING=OFF
```

### 规则 5
**不要默认 I2C 总线号固定，必须现场确认**

### 规则 6
**SpotMicro 迁移优先处理 Python3 与 C++17 问题，再碰硬件**

### 规则 7
**先跑运动主链路，再处理 hector slam / geotiff / 扩展可视化**

---

## 9. 建议的现场检查清单

每次在新香橙派部署机器狗环境时，建议按下面顺序打勾：

### 系统与 Python
- [ ] `which python3` 为 `/usr/bin/python3`
- [ ] 未处于 Conda `(base)` 污染状态
- [ ] `python3-empy`、`python3-defusedxml`、`python3-catkin-pkg`、`python3-rospkg` 正常

### ROS base
- [ ] `ros_noetic_ws` 已编译通过
- [ ] `roscore` 正常启动
- [ ] `rospack find roscpp` 正常

### overlay
- [ ] `spotmicro_ws` 已编译通过
- [ ] `rospack find i2cpwm_board`
- [ ] `rospack find spot_micro_motion_cmd`
- [ ] `rospack find spot_micro_keyboard_command`

### I2C / 硬件
- [ ] `ls /dev/i2c*` 看到目标总线
- [ ] `sudo i2cdetect -y <bus>` 能扫到 PCA9685
- [ ] launch 文件参数名是 `i2c_device_number`
- [ ] PCA9685 供电与主控共地

---

## 10. 最后结论

本次实践证明，**Orange Pi AI Pro + Ubuntu 22.04 + SpotMicro + ROS1 Noetic** 是可以落地的，但要成功，必须接受下面这几个现实：

1. ROS1 Noetic 在这套环境里要按**源码编译**思路做
2. 必须使用 **ROS base 工作区 + SpotMicro overlay 工作区** 的双层结构
3. **Conda 与用户 Python 污染** 是高频致命问题，必须主动规避
4. Ubuntu 22.04 下的 `log4cxx` 会把多个包逼到 **C++17**
5. 某些旧依赖（如 `tf2_eigen`）与其继续扩 base，不如在业务代码里移除无谓引用
6. `spot_micro_launch` 这类扩展包不要一开始就死磕，先跑通主链路
7. Orange Pi 的 I2C 总线编号和 launch 参数名一定要现场验证

如果后续在别的香橙派上继续部署，优先复用本文的目录结构、编译参数、排错顺序和工作区边界，不要重新走“单工作区混编”的老路。
