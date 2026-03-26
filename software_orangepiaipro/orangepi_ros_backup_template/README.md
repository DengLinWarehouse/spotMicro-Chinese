# Orange Pi ROS 备份模板

这个模板用于备份 **Orange Pi AI Pro / Ubuntu 22.04 / ROS1 Noetic 源码环境**，目标不是保存一份不可维护的编译产物，而是保存一份 **可重建、可恢复、可继续演进** 的工作副本。

## 这个方案可不可行

可行，但请按下面的原则执行：

- 远程仓库主要保存 `src/` 源码、补丁、文档、依赖清单、恢复脚本。
- 不要把 `build/`、`devel/`、`install/`、日志目录提交到 Git。
- 如果担心远程仓库不够大，可以把完整源码快照额外打包成 `tar.gz`，只在本地/NAS/网盘保存，不进 Git。
- 如果你以后要恢复到另一台香橙派，优先恢复源码和依赖，再重新编译，不要试图直接复用旧机器的编译目录。

## 推荐目录结构

```text
orangepi_ros_backup_template/
├── README.md
├── .gitignore
├── docs/
├── manifests/
├── patches/
├── scripts/
├── workspaces/
│   ├── ros_noetic_ws/
│   │   └── src/
│   └── spotmicro_ws/
│       └── src/
└── archives/
```

## 建议备份策略

### 第 1 层：Git 远程仓库

适合长期维护，建议提交以下内容：

- `workspaces/ros_noetic_ws/src/`
- `workspaces/spotmicro_ws/src/`
- `patches/`
- `docs/`
- `manifests/`
- `scripts/`

### 第 2 层：源码压缩包

适合断网恢复或快速复制到其他机器：

- `archives/ros_noetic_ws_src_YYYYMMDD_HHMMSS.tar.gz`
- `archives/spotmicro_ws_src_YYYYMMDD_HHMMSS.tar.gz`

> `archives/` 默认被 `.gitignore` 忽略，避免把大文件推上 Git。

### 第 3 层：系统镜像/整盘备份

如果你的香橙派环境已经非常稳定，建议额外保留：

- 系统镜像
- `/etc` 中的关键配置备份
- I2C、串口、udev、网络等主机级配置说明

## 在香橙派上的标准用法

先把本模板目录复制到香橙派，例如：

```bash
mkdir -p ~/Desktop/SpotMicro
cp -a orangepi_ros_backup_template ~/Desktop/SpotMicro/
cd ~/Desktop/SpotMicro/orangepi_ros_backup_template
chmod +x scripts/*.sh
```

然后按顺序执行：

```bash
bash scripts/verify_env.sh
bash scripts/capture_manifests.sh
bash scripts/export_ros_base_src.sh
bash scripts/export_spotmicro_overlay.sh
bash scripts/create_archives.sh
```

执行完成后，可在香橙派上初始化 Git 并推送远程仓库：

```bash
git init
git add .
git commit -m "backup: orangepi ros noetic base and spotmicro overlay"
git branch -M main
git remote add origin <你的远程仓库地址>
git push -u origin main
```

## 恢复原则

- `ros_noetic_ws` 和 `spotmicro_ws` 必须分开恢复。
- 恢复时先处理基础环境，再处理 SpotMicro overlay。
- 恢复后一定要重新执行 `catkin_make`。
- 新终端使用前先 `source` base，再 `source` overlay。
- Conda 环境不要混进 ROS 构建链。

详细说明见：

- `docs/备份策略说明.md`
- `docs/依赖清单维护.md`
- `docs/恢复流程.md`
- `docs/香橙派环境注意事项.md`
