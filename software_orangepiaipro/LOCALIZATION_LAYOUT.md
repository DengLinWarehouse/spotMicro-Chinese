# Localization Layout (2026-03-12)

This directory mirrors `../spotMicro` to guarantee a pristine upstream workspace while preserving all Chinese resources.

## 2026-03 Orange Pi note
- `software_orangepiaipro` is now treated as a source archive plus documentation hub, not the recommended active workspace for Ubuntu 22.04.
- On Orange Pi AI Pro with Ubuntu 22.04, first build ROS1 Noetic from source in a dedicated base workspace such as `~/Desktop/SpotMicro/ros_noetic_ws`.
- Create a second overlay workspace such as `~/Desktop/SpotMicro/spotmicro_ws` for the robot packages. Do **not** mix SpotMicro packages directly into the ROS base source tree.
- For migration, prefer packages under `extensions/packages` when they already contain Python 3 / Noetic fixes. Root packages still preserve older Kinetic-era layouts for reference.
- If you only need to read, compare, or copy files, work from this mirror. If you need to build on Orange Pi, follow `docs_cn/README.md` and `docs_cn/实验操作手册.md`.

## Base mirror
- Root files (CMakeLists.txt, packages, docs, assets) are copied 1:1 from `D:/DevelopmentProject/ROBOOT/SpotMicro/spotMicro` except the `.git` directory.
- Legacy note: direct in-place `catkin_make` is only appropriate when intentionally reproducing the upstream Kinetic-style workspace. It is **not** the recommended path for Orange Pi Ubuntu 22.04.

## docs_cn
- Contains `README.md`, `LEARNING_GUIDE.md`, `servo_calibration.md`, `实验操作手册.md`, and `舵机校准参考表格.ods` from the Chinese bundle plus Orange Pi migration notes.
- Use this folder for any additional translation notes.

## extensions
- `extensions/packages` keeps the earlier customized ROS packages (`spot_micro_walk`, `spot_micro_simple_command`, etc.).
- `extensions/root_overrides/CMakeLists.local.txt` stores the previous workspace-level overrides for reference.
- When you need an extension package, copy or symlink it back into the workspace or add it via a catkin overlay to avoid polluting the base mirror.

## Diff script
Use `python scripts/compare_with_upstream.py` (see analysis logs) or rerun:
```powershell
@'
from pathlib import Path
IGNORE_DIRS = {'.git', '.vscode', '__pycache__', '.idea', '.tmp', 'extensions', 'docs_cn'}
root1 = Path('spotMicro')
root2 = Path('spotMicro-Chinese') / '软件部分'
missing = set(str(p.relative_to(root1)).replace('\\\\','/') for p in root1.rglob('*') if p.is_file()) - set(str(p.relative_to(root2)).replace('\\\\','/') for p in root2.rglob('*') if p.is_file())
print('Missing from 软件部分:', len(missing))
'@ | python -
```
It should report `Missing from 软件部分: 0`.
