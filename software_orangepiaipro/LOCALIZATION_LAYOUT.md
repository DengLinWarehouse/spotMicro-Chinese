# Localization Layout (2026-03-12)

This directory mirrors `../spotMicro` to guarantee a pristine upstream workspace while preserving all Chinese resources.

## Base mirror
- Root files (CMakeLists.txt, packages, docs, assets) are copied 1:1 from `D:/DevelopmentProject/ROBOOT/SpotMicro/spotMicro` except the `.git` directory.
- You can build directly here with `catkin_make` the same way as in the upstream repo.

## docs_cn
- Contains `README.md`, `LEARNING_GUIDE.md`, `SOFTWARE_ASSESSMENT.md`, `servo_calibration.md`, and `舵机校准参考表格.ods` from the previous Chinese bundle.
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
