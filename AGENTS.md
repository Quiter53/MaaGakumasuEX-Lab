# MaaGakumasuEX-Lab

这是 Quiter53 的私有训练与测试仓库。先阅读 README.md 和 docs/training.md。

- source 是主仓库的固定提交子模块，保留主仓库的测试与许可证，不复制维护另一套业务逻辑。
- 默认只运行离线测试、截图回放与训练。实机输入需要用户明确要求。
- 训练与校准结果放 outputs，不覆盖 source 的模型，不自动同步正式版。
- fixtures 为用户授权迁移到私有仓库的本机回放截图，不向公开仓库、外部数据服务或公开 Release 上传。
- 不提交账号配置、Git 凭据、.env、日志、完整运行包和临时构建目录。
- 修改 source 时遵守其中 AGENTS.md；更新子模块提交前检查 diff 与测试。
- 更换电脑后优先使用 setup.ps1 与 requirements-lock.txt，测试结果须注明源代码提交、依赖和跳过项。
