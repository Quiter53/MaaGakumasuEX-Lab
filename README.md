# MaaGakumasuEX Lab

Quiter53 的私有训练、回归测试与截图回放环境。主程序继续在 [MaaGakumasuEX](https://github.com/Quiter53/MaaGakumasuEX) 维护；这里通过 `source` 子模块固定对应源码，不另存一套程序逻辑。

目前固定源码提交为 `5eef68e731d85287cf30c00a6d486f86a89543ff`（v2.1.2 发布后的 README 维护提交）。版本号一致仍可能有不同的代码，以子模块提交为准。

## 换电脑使用

需要 Windows x64、Git、完整安装的 Python 3.12。原生界面测试另需 .NET 10 SDK；YOLO 训练另需适合显卡的 PyTorch。先在 Git 中登录能访问本私有仓库的 GitHub 账号。

```powershell
git clone --recurse-submodules https://github.com/Quiter53/MaaGakumasuEX-Lab.git
cd MaaGakumasuEX-Lab
powershell -ExecutionPolicy Bypass -File .\setup.ps1
.\.venv\Scripts\python.exe lab.py test --output outputs/first-test
```

如果系统的 `python` 不是完整 Python 3.12，可指定安装位置：

```powershell
.\setup.ps1 -Python 'C:\Python312\python.exe'
```

安装脚本下载子模块、创建本地虚拟环境、按验证过的 `requirements-lock.txt` 安装依赖并恢复截图。无需复制旧电脑的 Python、账号配置或运行包。输出目录必须是新目录；再次运行请换名字，已有结果不会覆盖。

## 测试与回放

```powershell
# 按原项目测试组织运行，可追加 pytest 参数。
.\.venv\Scripts\python.exe lab.py test --output outputs/battle -- -k battle

# 真实 MaaFramework 5.13.0 检测器，读取保存的游戏画面，控制器禁止输入。
.\.venv\Scripts\python.exe lab.py model-check --image fixtures/card_rules/stuck-game.png

# 原生 UI 测试，只使用 outputs 下从公共默认配置生成的副本。
.\.venv\Scripts\python.exe lab.py ui CardRulesUi --output outputs/ui-rules
.\.venv\Scripts\python.exe lab.py ui DrinkUi --output outputs/ui-drinks
.\.venv\Scripts\python.exe lab.py ui CardListUi --output outputs/ui-lists
.\.venv\Scripts\python.exe lab.py ui FocusImages --output outputs/ui-focus
.\.venv\Scripts\python.exe lab.py ui native_task_watchdog --output outputs/watchdog

# 使用原生 UI 生成的对照数据，补上 Python/原生策略一致性测试。
.\.venv\Scripts\python.exe lab.py test --vectors outputs/ui-rules/native-policy-vectors.json --output outputs/full-test
```

SDK 不在 PATH 时，UI 命令可加 `--dotnet 'C:\dotnet\dotnet.exe'`。首次构建会下载 NuGet 依赖。`PortableLayout` 涉及打包后的 depsfile、DLL 和本地化装载，需独立运行包，不属于上述普通 UI 入口。

原项目其他离线识别工具保留在 `source/tools` 和 `source/tests/run_*.py`。部分脚本面向实机，不要因文件名含 test 就直接执行；先查看说明和参数。这里的默认命令只运行回归测试或禁止输入的截图检测。

## 训练

卡面识别阈值校准已经具备所需参考卡图库，可直接运行：

```powershell
.\.venv\Scripts\python.exe lab.py calibrate --output outputs/calibration-001
```

结果为候选阈值及合成样本训练/留出集报告，**这不是 YOLO 训练，也不表示真实游戏识别准确率**。不会修改正式校准文件。

YOLO11 的标注格式、GPU 环境、训练与导出命令见 [训练说明](docs/training.md)。仓库目前没有完整 YOLO 原始标注集和原 `.pt` 权重，不能从现有 `cards.onnx` 恢复原训练状态；补齐数据与权重后才能重新训练。已迁移的 16 张截图用于回归，不自动转成训练样本。

## 内容与迁移边界

| 目录或文件 | 用途 |
| --- | --- |
| `source/` | 固定提交的主仓库，包含测试、脚本、资源、原生 UI 源码 |
| `fixtures/` | 16 张本机回放截图及 SHA-256 清单，约 10 MB |
| `lab.py`、`setup.ps1` | 恢复环境、测试、回放与校准入口 |
| `train.py`、`datasets/cards.example.yaml` | 标注校验、YOLO 训练及候选 ONNX 导出 |
| `requirements-lock.txt` | 本次实际验证的 Windows Python 测试依赖 |
| `outputs/` | 本机结果、依赖版本、源码状态与报告，默认不提交 |
| `datasets/local/`、`weights/` | 本机标注集和训练权重，默认不提交 |

本机运行包、个人 config、连接信息、日志、历史临时构建与发布凭据没有迁移。旧 `hand_identity_labels.json` 对应的 10 张历史战斗原图未在本机找到，该独立评估集尚不完整，不宣称已经备份。

新增训练集放 `datasets/local`；大文件应通过**本私有仓库的私有 Release 附件或 Git LFS**备份，另附 SHA-256。默认忽略大权重是为了防止误提交，不代表它们会自动同步。账号密钥不要写进数据、脚本或文档。

## 更新对应的主程序代码

```powershell
git -C source fetch origin
git -C source checkout <已确认的主仓库提交SHA>
.\.venv\Scripts\python.exe lab.py prepare
.\.venv\Scripts\python.exe lab.py test --output outputs/updated-source
git add source
git commit -m 'lab: update tested source revision'
git push
```

切换主仓库提交前检查 `git -C source status`；不要覆盖源码改动。主仓库原有测试继续保留。实验模型不会自动复制进主仓库、运行包或正式版。

许可证沿用 [AGPL-3.0](LICENSE)。游戏截图和素材仅用于本私有测试工作区，不随许可证转授游戏素材权利。
