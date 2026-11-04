# MaaGakumasuEX Lab

Quiter53 的训练、回归测试与截图回放环境。仓库当前公开，本次游戏原图已由用户确认公开上传。主程序继续在 [MaaGakumasuEX](https://github.com/Quiter53/MaaGakumasuEX) 维护；这里通过 `source` 子模块固定对应源码，不另存一套程序逻辑。

目前固定源码提交为 `e974586d1d26522952dcbbb0c117b64e7af42408`（v2.2.0 正式版，包含原生界面、配置保存、更新解压与发行包依赖修复；[下载正式版](https://github.com/Quiter53/MaaGakumasuEX/releases/tag/v2.2.0)）。版本号一致仍可能有不同的代码，以子模块提交为准。

## 界面原型

[Modern UI 交互原型](ui-prototypes/modern-preview/)：独立 HTML，包含内嵌图片，可下载后直接打开，用于新版界面的布局、出牌曲线与液态玻璃交互评审。

## 换电脑使用

需要 Windows x64、Git、完整安装的 Python 3.12。原生界面测试另需 .NET 10 SDK；YOLO 训练另需适合显卡的 PyTorch。克隆公开仓库无需登录，推送修改时需登录有写入权限的 GitHub 账号。

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

# 10 张历史手牌评估截图，使用人工给定牌框，不等同于完整检测精度。
.\.venv\Scripts\python.exe lab.py evaluate-hand --output outputs/hand-evaluation

# 原生 UI 测试，只使用 outputs 下从公共默认配置生成的副本。
.\.venv\Scripts\python.exe lab.py ui CardRulesUi --output outputs/ui-rules
.\.venv\Scripts\python.exe lab.py ui DrinkUi --output outputs/ui-drinks
.\.venv\Scripts\python.exe lab.py ui CardListUi --output outputs/ui-lists
.\.venv\Scripts\python.exe lab.py ui FocusImages --output outputs/ui-focus
.\.venv\Scripts\python.exe lab.py ui native_task_watchdog --output outputs/watchdog

# 使用原生 UI 生成的对照数据，补上 Python/原生策略一致性测试。
.\.venv\Scripts\python.exe lab.py test --vectors outputs/ui-rules/native-policy-vectors.json --require-vectors --output outputs/full-test
```

SDK 不在 PATH 时，UI 命令可加 `--dotnet 'C:\dotnet\dotnet.exe'`。首次构建会下载 NuGet 依赖。原生测试构建到各自输出目录中的 `runtime`，测试生成的配置、截图和日志保存在该次输出内。

`CardRulesUi` 同时保存向量摘要和源码身份到 `native-policy-provenance.json`。Python 回归校验生成时的提交、未提交改动、未跟踪源码与当前输入一致。修改源码后重新生成向量。`--require-vectors` 还检查 JUnit 报告，向量比较被过滤或跳过时整次验证失败。所选源码包含固定预期和职业分享用例时，这些检查也必须全部执行。发布前使用该选项。

### 检查当前开发版本

默认测试 `source` 的固定提交。检查其他工作区时，在子命令前明确传入 `--source`。`environment.json` 记录实际源码路径、提交、工作区改动、Python 与依赖版本。每次执行保留 `run.log` 和 `result.json`，只有整条命令执行成功才标记 `passed`。Python 回归另保存包含失败与跳过项的 `junit.xml`，临时目录和 pytest 缓存也归入当次输出。

```powershell
# 对当前 pre 源码执行回归，不切换固定子模块。
.\.venv\Scripts\python.exe lab.py --source ..\MaaGakumasu-card-strategy-git test --output outputs/pre-python

# 新界面布局、并发配置保存和发布渠道策略。
.\.venv\Scripts\python.exe lab.py --source ..\MaaGakumasu-card-strategy-git ui LiquidBoardTests --output outputs/pre-layout
.\.venv\Scripts\python.exe lab.py --source ..\MaaGakumasu-card-strategy-git ui ConfigSaveTests --output outputs/pre-config
.\.venv\Scripts\python.exe lab.py --source ..\MaaGakumasu-card-strategy-git ui native_release_policy --output outputs/pre-channel
.\.venv\Scripts\python.exe lab.py --source ..\MaaGakumasu-card-strategy-git ui native_archive_policy --output outputs/pre-archive

# 真实 App 的 Avalonia Headless 测试，使用公共默认配置。
.\.venv\Scripts\python.exe lab.py --source ..\MaaGakumasu-card-strategy-git ui NativeShots --script taskopts --output outputs/pre-task-options
.\.venv\Scripts\python.exe lab.py --source ..\MaaGakumasu-card-strategy-git ui NativeShots --script round4 --output outputs/pre-scale-drag
.\.venv\Scripts\python.exe lab.py --source ..\MaaGakumasu-card-strategy-git ui NativeShots --script round5 --output outputs/pre-options-surfaces
.\.venv\Scripts\python.exe lab.py --source ..\MaaGakumasu-card-strategy-git ui NativeShots --script audit --output outputs/pre-ui-contracts

# 独立发行包的依赖与四种语言资源装载。
.\.venv\Scripts\python.exe lab.py --source ..\MaaGakumasu-card-strategy-git ui PortableLayout --runtime ..\MaaGakumasuEX-pre --output outputs/pre-portable
```

`NativeShots` 的 `taskopts`、`round4`、`round5`、`audit` 执行断言，`basic`、`all`、`sizes`、`small` 和 `lang:语言` 生成页面渲染证据，截图仍需查看。原生测试使用无头输入管线。`PortableLayout` 复制包内依赖、启动钩子和运行时描述文件到隔离目录，保存其摘要及构建信息。该命令按指定源码的翻译逐项验证实际发行包。旧源码缺少所选测试项目时会报错，应选择包含该项目的提交。

2026-11-04 通过外部 `--source` 验证开发提交 `3aae1e3aaccabd1692f17a61145a6f51603b08df`。`CardRulesUi` 通过 806 项检查并生成 3640 条向量，随后带 `--require-vectors` 的完整 Python 回归通过 1480 项测试及 1325 个子测试，跳过项为 0。固定预期覆盖 40 个策略用例和 61 个配置验证用例，并检查 C# 职业分享导入保存后的配置能够由 Python 读取执行。依赖为 Python 3.12.14、pytest 9.1.1、MaaFramework 5.13.0 和 .NET SDK 10.0.100。原生运行与 Python 回归的来源摘要一致，已跟踪文件没有未提交改动。Lab 默认子模块继续固定上述 v2.2.0 正式版。本轮采用离线和无头测试，游戏实机全流程尚未验证。[对应源码](https://github.com/Quiter53/MaaGakumasuEX/commit/3aae1e3aaccabd1692f17a61145a6f51603b08df)

原项目其他离线识别工具保留在 `source/tools` 和 `source/tests/run_*.py`。部分脚本面向实机，不要因文件名含 test 就直接执行；先查看说明和参数。这里的默认命令只运行回归测试或禁止输入的截图检测。

## 训练

卡面识别阈值校准已经具备所需参考卡图库，可直接运行：

```powershell
.\.venv\Scripts\python.exe lab.py calibrate --output outputs/calibration-001
```

结果为候选阈值及合成样本训练/留出集报告，**这不是 YOLO 训练，也不表示真实游戏识别准确率**。不会修改正式校准文件。

YOLO11 的标注格式、GPU 环境、训练与导出命令见 [训练说明](docs/training.md)。仓库目前没有完整 YOLO 原始标注集和原 `.pt` 权重，不能从现有 `cards.onnx` 恢复原训练状态；补齐数据与权重后才能重新训练。已迁移的 26 张截图用于回归或评估，不自动转成训练样本。早期识别修复的具体方法见 [历史识别方案](docs/recognition-history.md)。

## 内容与迁移边界

| 目录或文件 | 用途 |
| --- | --- |
| `source/` | 固定提交的主仓库，包含测试、脚本、资源、原生 UI 源码 |
| `fixtures/` | 26 张本机回放与手牌评估截图及 SHA-256 清单，约 20 MB |
| [`datasets/video-eval-20261025/`](datasets/video-eval-20261025/README.md) | 两段公开视频的 59 张目视核对截图、136 次身份及来源；去重后 58 帧、135 次身份 |
| [`datasets/web-eval-20261030/`](datasets/web-eval-20261030/README.md) | 新网页来源的 20 张战斗图、66 次可见手牌、65 个原模型手牌框；静止 18 正确 / 4 未知 / 0 错认，两版一致 |
| [`game-assets/`](game-assets/README.md) | 3191 张原尺寸卡图、饮料、按钮和 UI 素材，约 185 MiB，附离线预览及来源清单 |
| `lab.py`、`setup.ps1` | 恢复环境、测试、回放与校准入口 |
| `train.py`、`datasets/cards.example.yaml` | 标注校验、YOLO 训练及候选 ONNX 导出 |
| `requirements-lock.txt` | 本次实际验证的 Windows Python 测试依赖 |
| `outputs/` | 本机结果、依赖版本、源码状态与报告，默认不提交 |
| `datasets/local/`、`weights/` | 本机标注集和训练权重，默认不提交 |

本机运行包、个人 config、连接信息、日志、历史临时构建与发布凭据没有迁移。旧 `hand_identity_labels.json` 对应的 10 张战斗原图后来在历史诊断目录中找到，原扩展名是 `.png.bmp`。现已无损转为 PNG 并纳入 `fixtures/hand`，像素逐字节核对一致；此前“原图未找到”的判断已更正。这些是历史开发评估样本，不用于宣称独立泛化精度，也不自动加入训练集。

新增训练集放 `datasets/local`；允许公开的大文件可通过本仓库 Release 或 Git LFS 备份，另附 SHA-256。个人数据应另用私有存储，公开仓库的 Release 附件也会公开。默认忽略大权重不代表它们会自动同步，账号密钥不要写进数据、脚本或文档。

游戏原图已直接纳入 Git；可打开 `game-assets/index.html` 搜索和浏览，也可运行 `python tools/verify_game_assets.py` 核对所有图像。它们用于参考图库和模板研究，与真实回放截图、YOLO 标注集分别保存。

角标恢复的配对评估、公开视频下载、精确时间抽帧、手牌去重及已核对标签评分见 [视频采集与角标验证](docs/video-recognition.md)。本轮录像帧用于身份评估，不能自动转作 YOLO 训练集。

负样本错误接受的逐例证据、独立回放命令与 2026-10-30 修复结果见 [负样本复现记录](datasets/negative-acceptance-20261030/README.md)。原有评估 JSON 保持原样。

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

代码许可证沿用 [AGPL-3.0](LICENSE)。游戏素材权利归原权利人，不随代码许可证转授素材权利。
