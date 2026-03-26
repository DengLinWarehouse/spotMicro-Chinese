# patches 目录说明

这个目录专门保存你对第三方源码做过的手工补丁，方便以后恢复或对比。

建议做法：

1. 每次手工修改第三方源码后，立即记录补丁原因。
2. 尽量保存成独立的 `.patch` 文件，或至少写一份对应说明文档。
3. 补丁文件命名建议带日期和包名，例如：
   - `20260326-kdl_parser-cxx17.patch`
   - `20260326-spot_micro_motion_cmd-remove-tf2_eigen.patch`
   - `20260326-i2cpwm-launch-param-fix.patch`

如果你没有现成 patch，也至少要记录：

- 修改了哪个文件
- 为什么改
- 改完后用什么命令验证通过
