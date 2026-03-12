# Spot Micro 构建问题记录（2026-03-12）

本记录用于补充上游 README 未提及的构建细节，方便在 Linux 环境中复刻 `software/` 工程。

## 1. Catkin 工作区位置
- 建议固定在 `~/catkin_ws`。如果放在其他路径，记得把所有命令里的 `~/catkin_ws` 替换掉，并保证当前用户拥有读写权限。
- 新终端务必先执行 `source /opt/ros/noetic/setup.bash`，否则 `catkin`/`rosdep` 均不可用。

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
- Ubuntu 20.04 默认无 `python` 命令，遇到脚本请改用 `python3`。

## 5. 常见报错速查
| 报错信息 | 说明 | 处理 |
| --- | --- | --- |
| `Multiple packages found with the same name` | extensions 中的备份未忽略 | 创建 `CATKIN_IGNORE` 后重新 `rosdep install` |
| `Could not find a package configuration file provided by "i2cpwm_board"` | `ros-i2cpwmboard` 目录为空 | 复制或 clone 子模块源码 |
| `spot_micro_launch` 找不到 `hector_*`（geotiff / plugins / trajectory / mapping / map_server） | 未安装 hector 系列依赖 | `sudo apt install ros-noetic-hector-geotiff ros-noetic-hector-geotiff-plugins ros-noetic-hector-trajectory-server ros-noetic-hector-mapping ros-noetic-hector-map-server` |
| `i2cpwm_board` 编译中 `i2c_smbus_*` 未定义 / undefined reference | `libi2c-dev` 未安装或 CMake 未链接 i2c | `sudo apt install libi2c-dev`，并在 CMake 中 `target_link_libraries(... i2c)` |
| `rosdep` 提示 `rplidar_ros` 缺失 | 未安装雷达驱动包 | `sudo apt install ros-noetic-rplidar-ros` |

补齐以上步骤后，`rosdep install --from-paths src --ignore-src -r -y` 与 `catkin build` 应能顺利通过。
