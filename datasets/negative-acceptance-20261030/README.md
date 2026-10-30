# 负样本错误接受的复现与修复

2026-10-30 重现原来的 20 个失败个例。所有个例都是保留角标的纯色卡面，两套识别器均预测「夢はまだ続く」；18 例没有检出角标边框。详情见 `diagnosis.json`。识别修复在普通确认和角标恢复后，要求右侧角标区域之外有超过一个 8 位像素级别的空间变化。原相似度和分差门槛保持原值。

| 评估 | 修复前/基线错误接受 | 修复后错误接受 |
| --- | --- | --- |
| seed 92471，600 个负样本 | 14 | 0 |
| seed 54077，300 个负样本 | 6 | 0 |
| 额外 seed 20261030，150 个负样本 | 2 | 0 |

两组原实验共 9000 次正样本身份判断，统计与原结果一致（8820 正确、180 未知、0 错认）。额外种子 1500 次正样本判断为 1440 正确、60 未知、0 错认。34 次历史身份与 135 次去重录像身份和原角标实现相比，名称及原有全部结果字段保持一致。录像标签由 Codex 目视核对，尚无独立人工审计。合成卡图与参考图库同源，这些数据不能解释为实机准确率。

## 文件

- `summary.json`：各轮参数、源代码哈希、实际依赖、完整分组统计、原完整报告哈希与测试结论。旧的 `video-eval-20261025/evaluation.json` 保持原样。
- `recorded-final.json`、`recorded-stacked.json`：最终记录器保存的全部错误接受帧，包括基线与候选一致的错误；每帧都有完整牌框、各牌预测与分数、样本类型、颜色/噪声种子、工作进程种子、样本序号、生成前 RNG 状态及像素 SHA-256。归档仅筛选失败帧，保留整轮统计；工具原始输出包含所有负样本逐例预测。
- `reviewed-comparison.json`：历史及去重录像上的逐例配对结果。
- 对应 source 的 `tests/fixtures/hand_flat_badge_cases.npz` 与同名 JSON：20 个原失败卡面的无损 RGB 裁剪及原始预测，供直接回归，不依赖重新合成。

归档不重复提交完整游戏画面。失败画面可以从现有公开素材和每帧 RNG 状态独立重建，并逐字节验证像素哈希。先按仓库 README 初始化 source 子模块，使用以下命令生成完整 PNG、带牌框的 HTML 检查页和配对回放结果：

```powershell
python tools/replay_badge_failures.py datasets/negative-acceptance-20261030/recorded-final.json --regenerate --check-recorded --expect-no-candidate-accepts --export-cases outputs/negative-final-view --output outputs/negative-final-replay.json
python tools/replay_badge_failures.py datasets/negative-acceptance-20261030/recorded-stacked.json --regenerate --check-recorded --expect-no-candidate-accepts --export-cases outputs/negative-stack-view --output outputs/negative-stack-replay.json
```

打开导出目录内的 `index.html` 查看原失败条件与牌框。JSON 回放结果同时列出记录时与当前源码的预测；检查标志会在分数/名称变化或候选再次接受负样本时返回非零退出码。可传 `--case w92471-n0002` 只回放一个画面。原始完整报告还支持 `--all-negative`，重建包含拒识样本在内的全部负样本。

## 完整重跑

```powershell
python tools/evaluate_badge_matching.py --per-k 200 --workers 8 --hard --seed 92471 --output outputs/negative-final-new.json
python tools/evaluate_badge_matching.py --per-k 100 --workers 6 --hard --stacked --seed 54077 --output outputs/negative-stack-new.json
python tools/compare_reviewed_identity.py --output outputs/reviewed-identity-new.json
python -m pytest -q lab-tests
python lab.py test --output outputs/python-suite-new
```

输出 JSON 同名 `.cases` 目录保存所有基线或候选错误接受画面的 PNG、单例 JSON 与 HTML 索引。`changes` 仍保留原有含义与数量上限，新的 `negativeFrames` 独立记录所有负样本，包含双算法同错，且不受该上限影响。相似度不是概率；这里的框是合成输入框，并非实时检测器输出。

`--negative-only` 仅跳过正样本评分，仍生成前面的样本以保持历史随机序列。工作进程数会改变序列，复现原整轮实验必须同时保留 seed、per-k、workers、hard、stacked；单例回放使用保存的 RNG 状态，不依赖前面是否跑过。原脚本的 stacked 选项只改变正样本角标与随机序列，负样本仍添加一层角标，记录中的 `negativeBadgeLayers=1` 明确了这一点。

## 验证边界

实际运行：Python 3.12.14、Pillow 12.3.0；正式修复重跑使用 NumPy 2.5.4，初次复现第一组使用 2.3.5，随后在 2.5.4 上重建像素并核对预测通过。全套 Python 1241 passed、1307 subtests passed、1 skipped；Lab 12 passed，编译与 diff 检查通过。跳过项需要 Windows CardRulesUi 生成原生策略向量。

未进行新的实机完整培育，也未完成原生界面向量检查。源码验证不表示现有安装包已更新；预发布测试包需单独构建、上传及核验。低对比度真实场景仍需扩大实机覆盖。
