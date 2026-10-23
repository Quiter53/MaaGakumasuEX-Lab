# 首次迁移验证

2026-10-24，在独立 Lab 目录中新建 Python 3.12 虚拟环境，按 requirements.txt 安装依赖后冻结为 requirements-lock.txt。主仓库作为新克隆的子模块，固定 `5eef68e731d85287cf30c00a6d486f86a89543ff`；没有使用主仓库的个人运行配置。

| 验证 | 结果 |
| --- | --- |
| 截图清单恢复 | 16 个 PNG，10,271,620 字节，SHA-256 核对通过 |
| Python 完整回归 | 1173 passed，346 subtests passed，无跳过 |
| 训练数据校验器回归 | 4 passed，覆盖重复帧泄漏、缺失标注、非法坐标与类别顺序 |
| 原生出牌规则 UI | 631 checks passed，3600 policy vectors |
| 饮料 UI | DRINK_UI_TESTS_PASSED |
| 卡牌名单 UI | CARD_LIST_UI_TESTS_PASSED |
| 日志图片处理 | 28 checks passed |
| 循环监测与任务结果 | 1036 checks passed |
| MaaFramework 5.13.0 原模型回放 | stuck-game.png 识别成功，控制器输入禁用 |
| 校准入口 | per-mode=40 的小规模流程验证完成，结果未部署 |
| pip check / Python 编译 / diff 空白检查 | 通过 |

完整 Python 回归使用 CardRulesUi 导出的 native-policy-vectors.json。未提供该文件时，有 1 项原生/Python 策略对照会跳过，其余测试仍能独立运行。

小规模校准的留出集中出现过 1 个误接受，因此该结果只作为脚本能运行的证据，不作为模型质量提升或部署依据。现有程序的校准参数及模型没有被替换。

本次没有完整 YOLO 标注集和 `.pt` 权重，没有进行真实 YOLO 训练、GPU 性能验证、候选 ONNX 导出或新一轮实机培育。原生 UI 构建提示的第三方依赖告警沿用固定源码，不在此次环境迁移中更换依赖。

同日核对历史聊天后，找回扩展名为 `.png.bmp` 的 10 张手牌评估原图。逐图无损转为 PNG 并核对像素完全一致，截图清单增至 26 张、20,158,790 字节，哈希恢复通过。新增 evaluate-hand 入口的实际结果为：34 个人工给定牌位中 33 个正确、1 个拒识、0 个错名；其中 5 张重叠手牌的那一帧为 5/5。当前机器身份识别耗时中位数 38.51 毫秒、p95 39.93 毫秒。这是历史开发样本、人工牌框下的离线评估，不代表检测器或完整游戏流程的准确率。
