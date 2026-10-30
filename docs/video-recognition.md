# 视频采集与角标验证

当前角标方案在原手牌身份匹配未确认时，检查右上缩略图边框，排除确认的单层或堆叠角标后复核。原候选与复核候选须一致；普通匹配门槛保持原值。2026-10-30 起，两条确认路径都要求角标区域之外的可见卡面具备实际空间变化，纯色卡面返回未知。完整实现与范围见主仓库的 `docs/fixes/hand-badge-matching-20261025.md`。

## 已保存的数据

`datasets/video-eval-20261025` 包含两个录像分组的 59 张 PNG、136 次目视核对身份、来源与哈希；近重复筛选后为 58 张 PNG、135 次身份。没有把现有识别器的预测直接作为标签。标签由 Codex 目视核对，尚未经过独立人工审计。

第一个录像属于开发集；第二个录像用于独立测试。普通、选中、发牌、闪光等状态分别评分。检测框经过目视检查，指标是给定框后的身份匹配，不等于整手检测召回或实机成功率。

```powershell
# 默认 source 是已固定的主仓库提交，可用 --source 指定另一个已检查的源码目录。
.\.venv\Scripts\python.exe tools/replay_hand_frames.py --frames datasets/video-eval-20261025 --output outputs/video-replay-001
.\.venv\Scripts\python.exe tools/evaluate_reviewed_frames.py --predictions outputs/video-replay-001/predictions.json --labels datasets/video-eval-20261025/first_labels.json --curation datasets/video-eval-20261025/curation.json --output outputs/video-first-001.json
.\.venv\Scripts\python.exe tools/evaluate_reviewed_frames.py --predictions outputs/video-replay-001/predictions.json --labels datasets/video-eval-20261025/second_labels.json --curation datasets/video-eval-20261025/curation.json --output outputs/video-test-001.json
```

`replay_hand_frames.py` 使用 MaaFramework 5.13.0 原模型，控制器禁止输入；结果为预测与无预测名称的检查图，不能自动当作真实标签。评分按帧 SHA-256 关联，不依赖机器路径或原始序号。

## 获取新录像

在已配置好的 Lab 环境外另建视频环境，沿用固定框架和测试依赖：

```powershell
.\.venv\Scripts\python.exe -m venv .venv-video
.\.venv-video\Scripts\python.exe -m pip install -r requirements.txt -r requirements-video.txt
.\.venv-video\Scripts\python.exe tools/collect_video_frames.py --url https://www.youtube.com/watch?v=VRT-g5GMTyk --start 231 --end 523 --interval 2 --crop 350 0 608 1080 --normalize --group youtube-VRT-g5GMTyk --output outputs/new-video-001
```

已有本机录像时另传 `--input <录像路径>`，仍提供原始 `--url` 与 `--group`。裁剪必须依据实际视频检查，不能沿用示例去拉伸其他布局。工具记录原视频 SHA-256、实际帧时间、裁剪、归一化、FFmpeg 版本与解码警告；发现解码异常应检查或更换视频编码，本轮全力录像选择无解码警告的 VP9 版本。

工具只提供未标注帧。先核对静止/过渡状态、卡名、可见区域及牌框，存成标签后再用 `curate_hand_dataset.py` 标出重复手牌：

```powershell
.\.venv\Scripts\python.exe tools/curate_hand_dataset.py --source source --dataset datasets/video-eval-20261025 --output outputs/curation-001.json
```

整段录像与转载共享一个分组。先分配训练/验证/测试，再调门槛；不能把相邻帧随机分到不同集合。保留角标、置灰、重复同名、四五张遮挡与无法确认的困难样本。

## 合成对照

```powershell
.\.venv\Scripts\python.exe tools/evaluate_badge_matching.py --per-k 200 --workers 8 --hard --seed 92471 --output outputs/badge-holdout-001.json
.\.venv\Scripts\python.exe tools/evaluate_badge_matching.py --per-k 100 --workers 6 --hard --stacked --seed 54077 --output outputs/badge-stack-001.json
```

同一画面分别交给 Git 基线 `v2.1.3`（固定提交 `1b3d1f7e7b9f06624fac747775820e20a39efcc9`）与当前实现；两者使用相同参考图库，基线门槛取自对应 Git 提交。工具默认使用提交 SHA，不依赖本机已获取标签。报告保存随机种子、工作进程数、源码状态与哈希。分别统计无角标、角标及无信息负样本，错误接受必须列出，不能只报成功率。

合成查询与参考卡图同源，不能作为独立实机准确率。带角标路径增加一次局部匹配；性能测试需在相同硬件、相同画面下比较，不能把多进程压力测试的毫秒数当作实机耗时。

## 本轮判断

角标分支带来新的正确确认，原本确认的结果与无角标对照维持原判断。独立测试没有新增错认。剩余难例是重度遮挡、置灰及相似图案，保留供后续扩大录像覆盖。本轮没有训练新神经网络；采用新模型前需增加独立录像来源，比较错认、拒识与耗时，而不是仅在原图增强上取得高分。

## 负样本逐例回放（2026-10-30）

`changes` 继续用于观察算法间的预测变化；`negativeFrames` 独立保存全部负样本的条件、完整牌框、两套结果、相似度/分差、工作进程种子及生成前 RNG 状态，包含双算法同错，且没有 60 条上限。任一算法接受负样本时，输出同名 `.cases` 目录中的无损 PNG、单例 JSON 和 HTML 检查页。

原有两组 20/900 次错误接受已经复现并修复为 0/900，原 9000 次正样本统计保持一致。逐例重建、像素哈希核验、源码/依赖信息与实际验证边界见 [复现记录](../datasets/negative-acceptance-20261030/README.md)。这些数字描述同源合成输入，不是实机错误率。
