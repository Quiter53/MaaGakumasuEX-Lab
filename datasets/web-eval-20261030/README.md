# 新网页截图离线验证（2026-10-30）

本轮从 5 篇公开文章采集 67 张图片，按原图字节去重后 66 张；筛出 20 张战斗截图，来自前四篇文章、两个站点，共 31 种基础卡名、66 次可见手牌。三个 Morishimemo 页面属于同一作者，不能视为三个独立玩家。Setandset 的说明面板未进入本次评分。不是此前两个 YouTube 录像的重复样本。

## 来源与处理

- [Morishimemo：HIF センス好調](https://morishimemo.com/gakumasu-memo-39)
- [Morishimemo：HIF アノマリー全力](https://morishimemo.com/gakumasu-memo-43)
- [Morishimemo：NIA マスター センス](https://morishimemo.com/gakumasu-memo-23)
- [AppGameLog：清夏 HIF](https://appgamelog.com/gkmas-hif-sumika/)
- [Setandset：アノマリー基础攻略](https://www.setandset.com/archives/gakumasanomaly.html)（仅采集，未评分）

`collection-manifest.json` 保存全部采集 URL、哈希和 Git blob；[采集任务](https://github.com/Quiter53/MaaGakumasuEX-Lab/actions/runs/41020233043)只访问公开页面，不使用登录、Cookie 或网站认证。所选 20 张原始图保存在 `originals/`，实际评分图保存在 `frames/`。

图像按比例裁成 9:16，再用 Pillow 12.3.0 Lanczos 缩放到 720×1280。长屏截图保留底部视口，稍宽的截图横向居中裁剪；逐图裁剪框、原始 URL 和 SHA-256 见 `labels.json`。已从原图重新构建并逐像素核对全部 20 张评分图。此次验证的是该手牌视口，不能代表完整长屏手机流程适配。

## 标注与固定版本

先目视查看卡名、对照原始卡图库并冻结基础卡名，再运行本批预测。标签由 Codex 核对，尚无独立真人审计；身份评分忽略强化 +/++。本批没有训练模型、调整阈值或修改主程序。

- 基线：v2.1.3 `6d54f4daf4146800a117f0f2ba78c02cab7242db`。
- 候选：v2.1.4 `8c7e1eaef07f8f0b6a112a0e75cd63de857fd234`。
- MaaFramework 5.13.0，原始 `cards.onnx` Git blob `c443c4e14c96309a296e4b269484b34d6c0fcf51`。
- Python 3.12.14 / NumPy 2.5.4 / Pillow 12.3.0，详见 `verification.json`。

保留原字节 `blind-labels.json`，其 SHA-256 为 `c48a30c312d8923496284fc8aa0b56a096a67c3ead9c73170df6aa7de355afd5`。复看整帧后有一项状态/角色修正：`morishi39-23` 的「天賦の才」是正常位置的唯一剩余手牌，最初被误记为动画浮牌；卡名未更改。修正过程见 `review-amendments.json`，最终标注见 `reviewed-labels.json`。

## 实际结果

两版结果完全一致；以下身份指标仅针对原模型检出的 65 个手牌框。漏检独立列出，未计成身份识别成功。

| 画面状态 | 帧数 | 检出的手牌 | 正确 | 未知/拒识 | 错认 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 静止 resting | 6 | 22 | 18 | 4 | 0 |
| 提示框 tooltip，手牌未抬起 | 1 | 3 | 3 | 0 | 0 |
| 选中 hover_selected | 7 | 22 | 0 | 22 | 0 |
| 出牌动画 card_animation，底部剩余牌 | 5 | 15 | 13 | 2 | 0 |
| 饮料动画 drink_animation | 1 | 3 | 3 | 0 | 0 |
| 合计 | 20 | 65 | 37 | 28 | 0 |

选中状态的 22 次未知由既有抬牌保护导致：手牌框纵坐标差超过 12 像素时不做身份确认。不能将这部分与静止画面的拒识混算。7 次目视可见角标身份中，3 次正确、4 次未知、0 次错认，两版一致。

**一处检测漏框**：`morishi43-17`（选中状态）可见五张手牌，原检测器仅输出四个手牌框；灰色「眠気」（从左数第 4 张）没有框。`labels.json` 保留全部五张预期牌名，并通过 `detectedToExpectedSlots=[0,1,2,4]` 对齐已检出的框；不是身份阈值拒识。其余 19 帧的手牌框数量与目视数量一致。本次没有全面标注其他界面目标，不能据此宣称完整检测精度。

**静止画面的四次拒识**均出现在五张重叠手牌，第一候选名称正确，但未达到原局部匹配分差门槛 `margin >= 0.17`（分数门槛 `score >= 0.4`）：

| 图像 / 从左起 1 基牌位 | 期望及第一候选 | score | margin | 可见掩码比例 |
| --- | --- | ---: | ---: | ---: |
| morishi39-10 / 3 | スポットライト | 0.424841 | 0.122983 | 0.274414 |
| morishi43-22 / 1 | 羽ばたけ！ | 0.422500 | 0.168830 | 0.251953 |
| morishi43-22 / 2 | 積み重ね | 0.552762 | 0.099393 | 0.251953 |
| morishi43-22 / 4 | ハッピー♪ | 0.781082 | 0.101472 | 0.251953 |

查看 [四个拒识样本](resting-unknowns.png)。JSON 中 slot 为 0 基。保持原阈值，未为通过这批截图放宽分差。

两版预测名称变化 **0**，基线全部已有结果字段变化 **0**，候选新增 `flat_artwork` 拒识 **0**。这批图没有发现纯色门控误伤真实卡面；有限的网页压缩截图不能证明全游戏准确率，尚未运行新一轮实机完整培育。

归档时重新核对原图/评分图 SHA-256、裁剪像素、两份评分统计及初始标签哈希；Lab 测试实际执行为 **12 passed，0 skipped**。

## 复现

在已按仓库 README 恢复的 Windows Lab 环境中运行；输出使用新目录。控制器禁止点击和滑动，不连接游戏。

```powershell
.\.venv\Scripts\python.exe tools/replay_hand_frames.py --source source --baseline 6d54f4daf4146800a117f0f2ba78c02cab7242db --frames datasets/web-eval-20261030/frames --output outputs/web-replay-001
.\.venv\Scripts\python.exe tools/evaluate_reviewed_frames.py --predictions outputs/web-replay-001/predictions.json --labels datasets/web-eval-20261030/labels.json --output outputs/web-score-001.json
```

`source` 须保持上述候选提交；基线 Git 对象须存在于主仓库，可先 `git -C source fetch origin main`。新电脑的 Git safe.directory 提示应按实际可信目录处理。推理耗时因硬件、预热而变化，不纳入身份结果一致性判断。

`predictions.json` 保存原检测框、标签、置信度及两版身份候选、分数、分差和可见比例；`evaluation.json` 为现有评分器实算输出，`evaluation-detail.json` 另含逐牌结果和漏检记录。评分按图像 SHA-256 关联；全部采集图不能因有 URL 就计入测试样本。`verification.json` 保存版本与核验结果，`checksums.json` 保存归档文件 SHA-256。

这些图用于离线评估，不自动加入训练集。网页截图和游戏素材权利归各原权利人，代码许可证不转授图像权利。
