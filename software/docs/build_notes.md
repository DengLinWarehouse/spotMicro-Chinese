# Spot Micro 构建问题记录（2026-03-12）

本记录用于补充上游 README 未提及的构建细节，方便在 Linux 环境中复刻 `software/` 工程。

## 1. Catkin 工作区位置
- 建议固定在 `~/catkin_ws`。如果放在其他路径，记得把所有命令里的 `~/catkin_ws` 替换掉，并保证当前用户拥有读写权限。
- 新终端务必先执行 `source /opt/ros/noetic/setup.bash`，否则 `catkin`/`rosdep` 均不可用。
- **不要在 `~/spotMicro-Chinese/software` 里创建指向自身的 `software -> /home/<user>/spotMicro-Chinese/software` 符号链接。** 该链接会让 catkin 在 `~/catkin_ws/src/spot_micro` 里反复发现 `spot_micro/software/...`、`spot_micro/software/software/...` 等路径，从而报 `Multiple packages found with the same name`。若怀疑已出现，执行：
  ```bash
  cd ~/spotMicro-Chinese/software
  ls -l | grep ' software'
  find ~/catkin_ws/src/spot_micro -maxdepth 3 -type d -name ros-i2cpwmboard
  ```
  > **路径提示**：示例命令使用相对路径 `../../spotMicro-Chinese/software`，仅在仓库位于 `~/spotMicro-Chinese` 且工作区在 `~/catkin_ws` 时适用；若路径不同，请替换为实际位置或使用绝对路径。
  发现此类输出后，删除该链接并重新 `cd ~/catkin_ws/src && ln -s ../../spotMicro-Chinese/software spot_micro`。

## 2. 扩展包的 CATKIN_IGNORE
- `software/extensions/packages/` 里存有一份旧版中文扩展包，如果不忽略会导致 rosdep 报“找到多个同名包”。
- 解决：在该目录放一个空文件 `CATKIN_IGNORE`：
  ```bash
  cd ~/spotMicro-Chinese/software/extensions
  touch packages/CATKIN_IGNORE
  ```

## 3. ros-i2cpwmboard 子模块
- 上游仓库通过 git submodule 引入 `ros-i2cpwmboard`，镜像中只保留了目录结构。
- 有两种补齐方式：
  1. 复制本地备份：
     ```bash
     cd ~/spotMicro-Chinese/software
     rm -rf ros-i2cpwmboard
     cp -R extensions/packages/ros-i2cpwmboard ./ros-i2cpwmboard
     ```
  2. 在 `~/catkin_ws/src` 下重新 `git clone https://github.com/ros-drivers/ros-i2cpwmboard.git`。

## 4. 额外 apt 依赖
- 雷达：`sudo apt install ros-noetic-rplidar-ros`（包名前必须带 `ros-noetic-`，直接安装 `rplidar_ros` 会失败）。
- Hector SLAM：`sudo apt install ros-noetic-hector-geotiff ros-noetic-hector-geotiff-plugins ros-noetic-hector-trajectory-server ros-noetic-hector-mapping ros-noetic-hector-map-server`。
- I2C SMBus 头文件：`sudo apt install libi2c-dev`，否则 `i2cpwm_board` 编译时会提示 `i2c_smbus_*` 未定义。
- Ubuntu 20.04 默认无 `python` 命令。若脚本 shebang 使用 `/usr/bin/python`（如 `servo_move_keyboard`、`spot_micro_keyboard_command`、`spot_micro_plot` 等），请执行 `sudo apt install python-is-python3` 或将首行改为 `/usr/bin/env python3` 后重新 `catkin build`。
 另外，请给这些脚本加执行权限并重新构建，例如：
  ```bash
  chmod +x ~/catkin_ws/src/spot_micro/servo_move_keyboard/scripts/*.py
  chmod +x ~/catkin_ws/src/spot_micro/spot_micro_keyboard_command/scripts/*.py
  chmod +x ~/catkin_ws/src/spot_micro/lcd_monitor/scripts/*.py
  chmod +x ~/catkin_ws/src/spot_micro/spot_micro_plot/scripts/*.py
  catkin build servo_move_keyboard spot_micro_keyboard_command lcd_monitor spot_micro_plot
  ```

## 5. 常见报错速查
| 报错信息 | 说明 | 处理 |
| --- | --- | --- |
| `Multiple packages found with the same name` | extensions 中的备份未忽略，或 `~/catkin_ws/src/spot_micro` 里出现递归 `software/.../ros-*` 副本 | 1) 在 `software/extensions/packages/` 下创建 `CATKIN_IGNORE`。<br>2) 若 `find ~/catkin_ws/src/spot_micro -maxdepth 3 -type d -name ros-i2cpwmboard` 输出多条，删除当前 `spot_micro` 目录重新 `cd ~/catkin_ws/src && ln -s ../../spotMicro-Chinese/software spot_micro`，必要时对多余副本放置 `CATKIN_IGNORE`。 |
| `Could not find a package configuration file provided by "i2cpwm_board"` | `ros-i2cpwmboard` 目录为空 | 复制或 clone 子模块源码 |
| `spot_micro_launch` 找不到 `hector_*`（geotiff / plugins / trajectory / mapping / map_server） | 未安装 hector 系列依赖 | `sudo apt install ros-noetic-hector-geotiff ros-noetic-hector-geotiff-plugins ros-noetic-hector-trajectory-server ros-noetic-hector-mapping ros-noetic-hector-map-server` |
| `i2cpwm_board` 编译中 `i2c_smbus_*` 未定义 / undefined reference | `libi2c-dev` 未安装或 CMake 未正确链接 `libi2c.so` | `sudo apt install libi2c-dev`，并在 CMake 中 `find_library(I2C_LIB i2c REQUIRED ...)` + `target_link_libraries(... ${I2C_LIB})` |
| `spot_micro_motion_cmd` 报 `tf2_eigen/tf2_eigen.h` 缺失 | 没安装 `tf2_eigen` | `sudo apt install ros-noetic-tf2-eigen` |
| `spot_micro_motion_cmd` 报 `libs/spot_micro_kinematics_cpp` 不存在 | 主仓库自带目录为空，需要复制备份或初始化子模块 | `cd ~/spotMicro-Chinese/software/spot_micro_motion_cmd/libs && rm -rf spot_micro_kinematics_cpp && cp -R ../extensions/packages/spot_micro_motion_cmd/libs/spot_micro_kinematics_cpp .` |
| `rosdep` 提示 `rplidar_ros` 缺失 | 未安装雷达驱动包 | `sudo apt install ros-noetic-rplidar-ros` |

补齐以上步骤后，`rosdep install --from-paths src --ignore-src -r -y` 与 `catkin build` 应能顺利通过。

## 6. i2cpwm_board 链接失败排查（`i2c_smbus_*` undefined reference）
1. **确认系统库是否存在**  
   ```bash
   dpkg -s libi2c-dev >/dev/null || sudo apt install libi2c-dev
   ldconfig -p | grep libi2c
   ls /usr/lib/aarch64-linux-gnu/libi2c.so /lib/aarch64-linux-gnu/libi2c.so
   ```  
   若上述命令任一失败，说明 I2C 库未部署完整。
2. **检查 CMake 缓存**  
   `cat ~/catkin_ws/build/i2cpwm_board/CMakeCache.txt | grep -A1 I2C_LIB`，确认 `I2C_LIB:FILEPATH=/usr/lib/aarch64-linux-gnu/libi2c.so` 等条目已写入。
3. **核对 CMakeLists**  
   `software/ros-i2cpwmboard/CMakeLists.txt` 必须包含：
   ```cmake
   find_library(I2C_LIB i2c REQUIRED
                PATHS /usr/lib/aarch64-linux-gnu /lib/aarch64-linux-gnu
                      /usr/lib/x86_64-linux-gnu /lib/x86_64-linux-gnu
                      /usr/lib /lib)
   target_link_libraries(i2cpwm_board ${catkin_LIBRARIES} ${I2C_LIB})
   ```
   修改后执行 `catkin clean i2cpwm_board`.
4. **复建并检查 link.txt**  
   ```bash
   cd ~/catkin_ws
   catkin build i2cpwm_board
   cat build/i2cpwm_board/CMakeFiles/i2cpwm_board.dir/link.txt
   ```  
   在 `link.txt` 内确认末尾存在 `/usr/lib/aarch64-linux-gnu/libi2c.so` 或 `-li2c`。若仍缺失，请删除 `build/i2cpwm_board` 目录后重跑 `catkin build`，或使用 `VERBOSE=1` 观察完整链接命令。

排查链路完成后，再执行一次 `source ~/catkin_ws/devel/setup.bash`，即可恢复其余包的构建。

## 7. spot_micro_motion_cmd 补丁流程
1. **确认运动学子库存在**：`ls ~/spotMicro-Chinese/software/spot_micro_motion_cmd/libs/spot_micro_kinematics_cpp` 应包含 `CMakeLists.txt、include、src` 等子目录。若为空，执行：
   ```bash
   cd ~/spotMicro-Chinese/software/spot_micro_motion_cmd/libs
   rm -rf spot_micro_kinematics_cpp
   cp -R ~/spotMicro-Chinese/software/extensions/packages/spot_micro_motion_cmd/libs/spot_micro_kinematics_cpp .
   ```
   亦可改为 `git submodule update --init --recursive`，效果相同。
2. **补齐 tf2_eigen 依赖**：`spot_micro_motion_cmd` 默认包含 `#include <tf2_eigen/tf2_eigen.h>`，Ubuntu 20.04 需安装 `ros-noetic-tf2-eigen`：
   ```bash
   sudo apt install ros-noetic-tf2-eigen
   ```
3. **重建并验证**：
   ```bash
   cd ~/catkin_ws
   catkin clean spot_micro_motion_cmd
   catkin build spot_micro_motion_cmd
   ```
   若只需检查该包，可使用 `--no-deps`，并在日志中确认 `spot_micro_motion_cmd_node` 已链接。

## 8. 运行节点前必须确认的事项
- **ROS Master**：除 `roslaunch` 已经包含 `roscore` 的场景外，请手动开启一个独立终端运行 `roscore`，否则所有 `rosrun`/`roslaunch` 都会出现 `Failed to contact master`、`Duration is out of range` 等异常。
- **I2C 硬件**：`i2cpwm_board` 需要 /dev/i2c-1 和 PCA9685 节点可用；若在无硬件环境中运行，`roslaunch i2cpwm_board i2cpwm_node.launch` 会输出 `Failed to open I2C bus /dev/i2c-1` 并退出，这是预期行为。调试其它节点前请确保 I2C 总线和地址 0x40 的驱动板已连接、`i2c-tools` 能够 `i2cdetect` 到设备。
- **脚本执行权限**：`servo_move_keyboard`、`spot_micro_keyboard_command`、`lcd_monitor`、`spot_micro_plot` 的 Python 节点在第一次 checkout 后没有执行权限。运行 `chmod +x ~/catkin_ws/src/spot_micro/<package>/scripts/*.py && catkin build <package>`，否则 `rosrun` 会提示 “Found ... but not executable”。
- **舵机通道参考**：`spot_micro_motion_cmd/config/spot_micro_motion_cmd.yaml` 默认将 12 个通道映射到四足的肩/大腿/小腿：
  | 通道 | 名称 | 部位 |
  | --- | --- | --- |
  | 1 | FL_HIP | 左前腿肩部 |
  | 2 | FL_UPPER_LEG | 左前腿大腿 |
  | 3 | FL_LOWER_LEG | 左前腿小腿 |
  | 4 | FR_HIP | 右前腿肩部 |
  | 5 | FR_UPPER_LEG | 右前腿大腿 |
  | 6 | FR_LOWER_LEG | 右前腿小腿 |
  | 7 | RL_HIP | 左后腿肩部 |
  | 8 | RL_UPPER_LEG | 左后腿大腿 |
  | 9 | RL_LOWER_LEG | 左后腿小腿 |
  | 10 | RR_HIP | 右前腿肩部 |
  | 11 | RR_UPPER_LEG | 右前腿大腿 |
  | 12 | RR_LOWER_LEG | 右后腿小腿 |
  `servo_move_keyboard` 中输入对应通道即可操作特定关节；若重新布线，请同步修改 YAML 的 `servo_mapping`。
- **RPLidar A1 快速测试**- **雷达 ≠ 自主导航**：当前仓库仅提供 RPLidar 数据接入（发布 `/scan`），并未集成 SLAM、定位或路径规划模块。要实现“自动行走”，需要自行搭建 SLAM/导航栈（gmapping/move_base 等）或编写发布运动指令的节点。默认 `spot_micro_motion_cmd` 仍通过键盘或自定义指令驱动步态。

- **雷达 ≠ 自动导航**：仓库只提供 `/scan` 数据接入。若要让机器人“自动行走”，需要自行搭建 SLAM/定位/路径规划（gmapping、move_base 等）并发布运动指令，默认 `spot_micro_motion_cmd` 仍通过键盘或自定义节点控制步态。

 Spot Micro 构建问题记录（2026-03-12）

本记录用于补充上游 README 未提及的构建细节，方便在 Linux 环境中复刻 `software/` 工程。

## 1. Catkin 工作区位置
- 建议固定在 `~/catkin_ws`。如果放在其他路径，记得把所有命令里的 `~/catkin_ws` 替换掉，并保证当前用户拥有读写权限。
- 新终端务必先执行 `source /opt/ros/noetic/setup.bash`，否则 `catkin`/`rosdep` 均不可用。
- **不要在 `~/spotMicro-Chinese/software` 里创建指向自身的 `software -> /home/<user>/spotMicro-Chinese/software` 符号链接。** 该链接会让 catkin 在 `~/catkin_ws/src/spot_micro` 里反复发现 `spot_micro/software/...`、`spot_micro/software/software/...` 等路径，从而报 `Multiple packages found with the same name`。若怀疑已出现，执行：
  ```bash
  cd ~/spotMicro-Chinese/software
  ls -l | grep ' software'
  find ~/catkin_ws/src/spot_micro -maxdepth 3 -type d -name ros-i2cpwmboard
  ```
  发现此类输出后，删除该链接并重新 `cd ~/catkin_ws/src && ln -s ../../spotMicro-Chinese/software spot_micro`。

## 2. 扩展包的 CATKIN_IGNORE
- `software/extensions/packages/` 里存有一份旧版中文扩展包，如果不忽略会导致 rosdep 报“找到多个同名包”。
- 解决：在该目录放一个空文件 `CATKIN_IGNORE`：
  ```bash
  cd ~/spotMicro-Chinese/software/extensions
  touch packages/CATKIN_IGNORE
  ```

## 3. ros-i2cpwmboard 子模块
- 上游仓库通过 git submodule 引入 `ros-i2cpwmboard`，镜像中只保留了目录结构。
- 有两种补齐方式：
  1. 复制本地备份：
     ```bash
     cd ~/spotMicro-Chinese/software
     rm -rf ros-i2cpwmboard
     cp -R extensions/packages/ros-i2cpwmboard ./ros-i2cpwmboard
     ```
  2. 在 `~/catkin_ws/src` 下重新 `git clone https://github.com/ros-drivers/ros-i2cpwmboard.git`。

## 4. 额外 apt 依赖
- 雷达：`sudo apt install ros-noetic-rplidar-ros`（包名前必须带 `ros-noetic-`，直接安装 `rplidar_ros` 会失败）。
- Hector SLAM：`sudo apt install ros-noetic-hector-geotiff ros-noetic-hector-geotiff-plugins ros-noetic-hector-trajectory-server ros-noetic-hector-mapping ros-noetic-hector-map-server`。
- I2C SMBus 头文件：`sudo apt install libi2c-dev`，否则 `i2cpwm_board` 编译时会提示 `i2c_smbus_*` 未定义。
- Ubuntu 20.04 默认无 `python` 命令。若脚本 shebang 使用 `/usr/bin/python`（如 `servo_move_keyboard`、`spot_micro_keyboard_command`、`spot_micro_plot` 等），请执行 `sudo apt install python-is-python3` 或将首行改为 `/usr/bin/env python3` 后重新 `catkin build`。
 另外，请给这些脚本加执行权限并重新构建，例如：
  ```bash
  chmod +x ~/catkin_ws/src/spot_micro/servo_move_keyboard/scripts/*.py
  chmod +x ~/catkin_ws/src/spot_micro/spot_micro_keyboard_command/scripts/*.py
  chmod +x ~/catkin_ws/src/spot_micro/lcd_monitor/scripts/*.py
  chmod +x ~/catkin_ws/src/spot_micro/spot_micro_plot/scripts/*.py
  catkin build servo_move_keyboard spot_micro_keyboard_command lcd_monitor spot_micro_plot
  ```

## 5. 常见报错速查
| 报错信息 | 说明 | 处理 |
| --- | --- | --- |
| `Multiple packages found with the same name` | extensions 中的备份未忽略，或 `~/catkin_ws/src/spot_micro` 里出现递归 `software/.../ros-*` 副本 | 1) 在 `software/extensions/packages/` 下创建 `CATKIN_IGNORE`。<br>2) 若 `find ~/catkin_ws/src/spot_micro -maxdepth 3 -type d -name ros-i2cpwmboard` 输出多条，删除当前 `spot_micro` 目录重新 `cd ~/catkin_ws/src && ln -s ../../spotMicro-Chinese/software spot_micro`，必要时对多余副本放置 `CATKIN_IGNORE`。 |
| `Could not find a package configuration file provided by "i2cpwm_board"` | `ros-i2cpwmboard` 目录为空 | 复制或 clone 子模块源码 |
| `spot_micro_launch` 找不到 `hector_*`（geotiff / plugins / trajectory / mapping / map_server） | 未安装 hector 系列依赖 | `sudo apt install ros-noetic-hector-geotiff ros-noetic-hector-geotiff-plugins ros-noetic-hector-trajectory-server ros-noetic-hector-mapping ros-noetic-hector-map-server` |
| `i2cpwm_board` 编译中 `i2c_smbus_*` 未定义 / undefined reference | `libi2c-dev` 未安装或 CMake 未正确链接 `libi2c.so` | `sudo apt install libi2c-dev`，并在 CMake 中 `find_library(I2C_LIB i2c REQUIRED ...)` + `target_link_libraries(... ${I2C_LIB})` |
| `spot_micro_motion_cmd` 报 `tf2_eigen/tf2_eigen.h` 缺失 | 没安装 `tf2_eigen` | `sudo apt install ros-noetic-tf2-eigen` |
| `spot_micro_motion_cmd` 报 `libs/spot_micro_kinematics_cpp` 不存在 | 主仓库自带目录为空，需要复制备份或初始化子模块 | `cd ~/spotMicro-Chinese/software/spot_micro_motion_cmd/libs && rm -rf spot_micro_kinematics_cpp && cp -R ../extensions/packages/spot_micro_motion_cmd/libs/spot_micro_kinematics_cpp .` |
| `rosdep` 提示 `rplidar_ros` 缺失 | 未安装雷达驱动包 | `sudo apt install ros-noetic-rplidar-ros` |

补齐以上步骤后，`rosdep install --from-paths src --ignore-src -r -y` 与 `catkin build` 应能顺利通过。

## 6. i2cpwm_board 链接失败排查（`i2c_smbus_*` undefined reference）
1. **确认系统库是否存在**  
   ```bash
   dpkg -s libi2c-dev >/dev/null || sudo apt install libi2c-dev
   ldconfig -p | grep libi2c
   ls /usr/lib/aarch64-linux-gnu/libi2c.so /lib/aarch64-linux-gnu/libi2c.so
   ```  
   若上述命令任一失败，说明 I2C 库未部署完整。
2. **检查 CMake 缓存**  
   `cat ~/catkin_ws/build/i2cpwm_board/CMakeCache.txt | grep -A1 I2C_LIB`，确认 `I2C_LIB:FILEPATH=/usr/lib/aarch64-linux-gnu/libi2c.so` 等条目已写入。
3. **核对 CMakeLists**  
   `software/ros-i2cpwmboard/CMakeLists.txt` 必须包含：
   ```cmake
   find_library(I2C_LIB i2c REQUIRED
                PATHS /usr/lib/aarch64-linux-gnu /lib/aarch64-linux-gnu
                      /usr/lib/x86_64-linux-gnu /lib/x86_64-linux-gnu
                      /usr/lib /lib)
   target_link_libraries(i2cpwm_board ${catkin_LIBRARIES} ${I2C_LIB})
   ```
   修改后执行 `catkin clean i2cpwm_board`.
4. **复建并检查 link.txt**  
   ```bash
   cd ~/catkin_ws
   catkin build i2cpwm_board
   cat build/i2cpwm_board/CMakeFiles/i2cpwm_board.dir/link.txt
   ```  
   在 `link.txt` 内确认末尾存在 `/usr/lib/aarch64-linux-gnu/libi2c.so` 或 `-li2c`。若仍缺失，请删除 `build/i2cpwm_board` 目录后重跑 `catkin build`，或使用 `VERBOSE=1` 观察完整链接命令。

排查链路完成后，再执行一次 `source ~/catkin_ws/devel/setup.bash`，即可恢复其余包的构建。

## 7. spot_micro_motion_cmd 补丁流程
1. **确认运动学子库存在**：`ls ~/spotMicro-Chinese/software/spot_micro_motion_cmd/libs/spot_micro_kinematics_cpp` 应包含 `CMakeLists.txt、include、src` 等子目录。若为空，执行：
   ```bash
   cd ~/spotMicro-Chinese/software/spot_micro_motion_cmd/libs
   rm -rf spot_micro_kinematics_cpp
   cp -R ~/spotMicro-Chinese/software/extensions/packages/spot_micro_motion_cmd/libs/spot_micro_kinematics_cpp .
   ```
   亦可改为 `git submodule update --init --recursive`，效果相同。
2. **补齐 tf2_eigen 依赖**：`spot_micro_motion_cmd` 默认包含 `#include <tf2_eigen/tf2_eigen.h>`，Ubuntu 20.04 需安装 `ros-noetic-tf2-eigen`：
   ```bash
   sudo apt install ros-noetic-tf2-eigen
   ```
3. **重建并验证**：
   ```bash
   cd ~/catkin_ws
   catkin clean spot_micro_motion_cmd
   catkin build spot_micro_motion_cmd
   ```
   若只需检查该包，可使用 `--no-deps`，并在日志中确认 `spot_micro_motion_cmd_node` 已链接。

## 8. 运行节点前必须确认的事项
- **ROS Master**：除 `roslaunch` 已经包含 `roscore` 的场景外，请手动开启一个独立终端运行 `roscore`，否则所有 `rosrun`/`roslaunch` 都会出现 `Failed to contact master`、`Duration is out of range` 等异常。
- **I2C 硬件**：`i2cpwm_board` 需要 /dev/i2c-1 和 PCA9685 节点可用；若在无硬件环境中运行，`roslaunch i2cpwm_board i2cpwm_node.launch` 会输出 `Failed to open I2C bus /dev/i2c-1` 并退出，这是预期行为。调试其它节点前请确保 I2C 总线和地址 0x40 的驱动板已连接、`i2c-tools` 能够 `i2cdetect` 到设备。
- **脚本执行权限**：`servo_move_keyboard`、`spot_micro_keyboard_command`、`lcd_monitor`、`spot_micro_plot` 的 Python 节点在第一次 checkout 后没有执行权限。运行 `chmod +x ~/catkin_ws/src/spot_micro/<package>/scripts/*.py && catkin build <package>`，否则 `rosrun` 会提示 “Found ... but not executable”。
- **舵机通道参考**：`spot_micro_motion_cmd/config/spot_micro_motion_cmd.yaml` 默认将 12 个通道映射到四足的肩/大腿/小腿：
  | 通道 | 名称 | 部位 |
  | --- | --- | --- |
  | 1 | FL_HIP | 左前腿肩部 |
  | 2 | FL_UPPER_LEG | 左前腿大腿 |
  | 3 | FL_LOWER_LEG | 左前腿小腿 |
  | 4 | FR_HIP | 右前腿肩部 |
  | 5 | FR_UPPER_LEG | 右前腿大腿 |
  | 6 | FR_LOWER_LEG | 右前腿小腿 |
  | 7 | RL_HIP | 左后腿肩部 |
  | 8 | RL_UPPER_LEG | 左后腿大腿 |
  | 9 | RL_LOWER_LEG | 左后腿小腿 |
  | 10 | RR_HIP | 右前腿肩部 |
  | 11 | RR_UPPER_LEG | 右前腿大腿 |
  | 12 | RR_LOWER_LEG | 右后腿小腿 |
  `servo_move_keyboard` 中输入对应通道即可操作特定关节；若重新布线，请同步修改 YAML 的 `servo_mapping`。
- **RPLidar A1 快速测试**：`sudo apt install ros-noetic-rplidar-ros` 后，确认 `/dev/ttyUSB*` 设备号并运行 `roslaunch rplidar_ros rplidar_a1.launch serial_port:=/dev/ttyUSB0 frame_id:=laser`。在无图形界面下可使用 `rostopic hz /scan`、`rostopic echo /scan` 验证数据，必要时 `rosbag record /scan` 拷贝到有 RViz 的环境查看。
