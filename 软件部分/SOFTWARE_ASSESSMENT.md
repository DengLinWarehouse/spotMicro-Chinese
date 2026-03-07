# Spot Micro 软件体检报告

## 结论
- 当前仓库中的“软件部分”不能直接在现代 ROS 环境上运行：顶层 CMakeLists.txt 指向 /opt/ros/kinetic，Python 节点依赖 Python2，多个包在构建阶段默认联网下载（gtest/doxygen），会导致 catkin_make 失败。
- 推荐以 C++ 状态机包 spot_micro_motion_cmd+os-i2cpwmboard 作为主控链，修复构建脚本、依赖和辅助节点后，再开展实机调试；Python 版 spot_micro_walk 仅适合算法参考。

## 关键问题
1. **工作空间锁死在 ROS Kinetic**：顶层 CMakeLists.txt 直接 include(/opt/ros/kinetic/share/catkin/cmake/toplevel.cmake)，在 Melodic/Noetic 将无法构建。
2. **构建期强制联网**：os-i2cpwmboard/CMakeLists.txt 调用 xecute_process(COMMAND doxygen …)，spot_micro_motion_cmd/libs/.../google-test 在配置期下载 gtest，离线或受限网络环境必失败。
3. **Python2 语法广泛存在**：所有脚本使用 #!/usr/bin/python、aw_input、旧式异常语法，在 Ubuntu 20.04+ 默认缺 python 解释器，运行即崩溃。
4. **重复且分散的舵机标定**：C++ YAML、Python 字典、文档中存在多套 servo 配置，稍有差异就会发出不一致指令。
5. **外设节点缺防护**：lcd_monitor 硬编码 I2C1/0x27 并无 try/except，没接 LCD 也会 crash；spot_micro_plot 直接导入 matplotlib，无显示时阻塞。

## 修复路线概览
- 重新初始化顶层 CMakeLists.txt，让 catkin 自动选择当前 ROS 发行版。
- 在 os-i2cpwmboard 和 gtest 子项目中增加可选开关，禁止构建阶段联网。
- 将 Python 节点迁移到 Python3（shebang、input、print()、f-string/format 等）。
- 统一 Servo 配置：以 spot_micro_motion_cmd/config/spot_micro_motion_cmd.yaml 为真源，其他脚本从 ROS 参数服务器读取；文档中修正 .ods 文件名。
- 对 LCD/Plot 节点增加硬件检测及 --headless 兼容。

## 下一步实验建议
| 实验 | 目的 | 判定标准 |
| --- | --- | --- |
| catkin_make 构建回归 | 验证 CMake 与依赖修复 | 全部包无 error/warn |
| Servo 配置一致性 | config_servos 能正确加载 YAML | 所有舵机回中位且方向正确 |
| FSM 站立↔行走循环 | 验证状态机 & 键盘控制 | /sm_state 能稳定切换，舵机无超限 |
| 辅助节点健壮性 | 观察在无 LCD/图形界面时的表现 | 节点仅报警不崩溃 |

创建时间：2026-03-07 16:36:19
