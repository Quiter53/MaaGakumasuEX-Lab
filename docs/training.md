# YOLO 训练与验证

流程参考 [MaaXYZ 官方检测模型食谱](https://github.com/MaaXYZ/MaaNeuralNetworkCookbook/tree/main/NeuralNetworkDetect)。EX 当前运行环境固定 MaaFramework 5.13.0，重新导出的模型须在这一版本回放验证。

## 安装训练依赖

训练使用独立虚拟环境，避免更换 torch、numpy 等依赖影响回归测试环境：

```powershell
python -m venv .venv-train
# 先按 https://pytorch.org/get-started/locally/ 安装适合本机显卡的 torch、torchvision。
.\.venv-train\Scripts\python.exe -m pip install -r requirements-train.txt
.\.venv-train\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
```

`requirements-train.txt` 提供版本范围，GPU 依赖需要按设备选择；每次实验会保存 `pip freeze`，正式采纳某轮结果时连同依赖和显卡驱动版本归档。本次没有下载训练权重或启动 GPU 长时间训练。

## 准备数据

本仓库尚未包含完整原始标注数据集，也没有原 `.pt` 训练权重。现有程序的 ONNX 是推理模型，不能用来续训。可自行提供可信来源的 YOLO11 预训练 `.pt`，或先前保存的检查点；首次用通用预训练权重开始的是新训练。

将原生游戏画面和 YOLO detection 格式的 txt 标注按以下结构放置，并把 `datasets/cards.example.yaml` 复制为其中的 `data.yaml`：

```text
datasets/local/cards/
  data.yaml
  images/train/*.png
  images/val/*.png
  images/test/*.png
  labels/train/*.txt
  labels/val/*.txt
  labels/test/*.txt
weights/yolo11n.pt
```

图片保持 720×1280 原始游戏区域，桌面截图需先裁出正确游戏区域，再重新核对标注；不要拉伸带桌面边框的截图。每张图片有同名 txt，负样本用空 txt。每行 `class x_center y_center width height`，坐标归一化至 0～1。

类别编号与当前流水线保持一致：`0=cards`（普通可用）、`1=suggestions`（推荐，也称 recommend）、`2=useless`（不可用）。同一卡牌只标一个类别，其他牌遮挡形成的独立框继续保留。改变类别顺序会改变程序理解，不能直接替换模型。

按录制场次分离训练、验证和测试，避免连续画面泄漏。校验器会拒绝跨集合或同集合的相同解码像素、缺失标注、非法坐标及错序类别；相近帧和人工错标仍需复核。

```powershell
.\.venv\Scripts\python.exe train.py check --data datasets/local/cards/data.yaml
.\.venv-train\Scripts\python.exe train.py train --data datasets/local/cards/data.yaml --weights weights/yolo11n.pt --device 0 --epochs 100 --batch 8 --imgsz 640 --output outputs/yolo-001
```

没有 GPU 时用 `--device cpu`，适合流程验证。训练会保存实际依赖、源码版本、数据清单和参数，权重位于 `outputs/yolo-001/detect/weights/`。`best.pt` 用于后续导出；要延续训练请保存 `last.pt` 与完整实验目录，当前入口以给定权重启动新训练，不等同于 Ultralytics 的断点 resume。训练后的独立 test 集评估可使用：

```powershell
.\.venv-train\Scripts\yolo.exe detect val model=outputs/yolo-001/detect/weights/best.pt data=outputs/yolo-001/data.yaml split=test project=outputs name=yolo-001-test
```

## 导出与回放

```powershell
.\.venv-train\Scripts\python.exe train.py export --weights outputs/yolo-001/detect/weights/best.pt --imgsz 640 --output outputs/onnx-001
```

输出 `candidate.onnx`，默认 opset 17、固定输入、不融合 NMS，遵循官方食谱的标准 YOLO 输出。导出成功不等于可部署，仍需检查模型输入输出、类别顺序及真实框架检测结果。

先用 `lab.py model-check` 测试原模型并保存基线。候选验证时，把 `source/assets/resource/base` **复制到 `outputs/candidate-bundle`**，只替换复制目录的 `model/detect/cards.onnx`，然后用原有禁止输入的原生检测脚本回放：

```powershell
.\.venv\Scripts\python.exe source/tools/check_cards_model.py outputs/candidate-bundle --image fixtures/card_rules/stuck-game.png
```

对比误检、漏检、同卡重复框、不可用牌、3～5 手牌遮挡、动画、奖励、删换牌与商店场景，以及推理耗时。若没有这些验证素材，应补齐后再决定部署。当前入口不会修改源码模型，也不会发布到正式版。

## 换电脑继续训练

除 Git 中的脚本和截图外，还要备份 `datasets/local`、`weights`、实验完整目录及 SHA-256 清单；这些大文件默认忽略，**没有备份就不能只靠 clone 恢复**。允许公开的数据可上传到本仓库 Release 或 Git LFS；个人数据应另用私有存储，当前公开仓库不能提供私有 Release 附件。恢复后先验证哈希，再安装同轮记录的训练依赖。
