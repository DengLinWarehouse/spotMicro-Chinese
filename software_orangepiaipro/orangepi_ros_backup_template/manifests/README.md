# manifests 目录说明

这个目录用于保存香橙派当前环境的依赖与状态快照。

建议通过 `bash scripts/capture_manifests.sh` 自动生成下列文件：

- `system-info.txt`
- `apt-manual.txt`
- `python3-freeze.txt`
- `ros-environment.txt`
- `notes.txt`

其中 `notes.txt` 建议手工维护，补充 I2C、launch、补丁来源等自动脚本无法完整表达的信息。
