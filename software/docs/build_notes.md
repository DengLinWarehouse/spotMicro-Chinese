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
| `Multiple packages found with the same name` | extensions 中的备份未忽略，或 `~/catkin_ws/src/spot_micro` 里出现递归 `software/.../ros-*` 副本 | 1) 在 `software/extensions/packages/` 下创建 `CATKIN_IGNORE`。<br>2) 若 `find ~/catkin_ws/src/spot_micro -maxdepth 3 -type d -name ros-i2cpwmboard` 输出多条，删除当前 `spot_micro` 目录重新 `ln -s ~/spotMicro-Chinese/software spot_micro`，必要时对多余副本放置 `CATKIN_IGNORE`。 |
| `Could not find a package configuration file provided by "i2cpwm_board"` | `ros-i2cpwmboard` 目录为空 | 复制或 clone 子模块源码 |
| `spot_micro_launch` 找不到 `hector_*`（geotiff / plugins / trajectory / mapping / map_server） | 未安装 hector 系列依赖 | `sudo apt install ros-noetic-hector-geotiff ros-noetic-hector-geotiff-plugins ros-noetic-hector-trajectory-server ros-noetic-hector-mapping ros-noetic-hector-map-server` |
| `i2cpwm_board` 编译中 `i2c_smbus_*` 未定义 / undefined reference | `libi2c-dev` 未安装或 CMake 未正确链接 `libi2c.so` | `sudo apt install libi2c-dev`，并在 CMake 中 `find_library(I2C_LIB i2c REQUIRED ...)` + `target_link_libraries(... ${I2C_LIB})` |
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
