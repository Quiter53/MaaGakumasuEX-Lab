# 游戏原始识别参考素材

此目录保存从本机 DMM《学園アイドルマスター》资源解出的原尺寸图像，供模板匹配、卡名检索、标注和识别实验使用。本次素材已由用户确认公开上传。PNG 保留解码后的像素和透明通道，没有放大缩略图或做图像增强。

| 目录 | 数量 | 内容 |
| --- | ---: | --- |
| `cards/` | 783 | 512×512 技能卡卡面，保留已缓存的角色、服装等变体 |
| `drinks/` | 35 | 饮料及相关图像；28 张 512×512、6 张 512×256、1 张 128×128 |
| `ui/sprites/` | 1852 | 从图集中解出的独立 Sprite，含按钮、角标、课程、属性、回忆、选择与确认相关图标 |
| `ui/textures/` | 521 | 完整 Texture2D，含原图集、背景、卡框与其他界面纹理 |

合计 **3191 张 PNG**，约 **185 MiB**。这些图片直接存入 Git，克隆本仓库即可取得，不需要额外下载 Release 附件。

打开 [index.html](index.html) 可离线搜索资源名、卡名并预览图片；[catalog.csv](catalog.csv) 可用表格软件打开，[catalog.json](catalog.json) 供脚本读取。文件名保留资源名并附 Unity 对象编号，避免同名素材互相覆盖。

## 来源与完整性

- `card-drink-manifest.json` 记录 818 个本机可用 Octo 缓存包的资源名、源包 SHA-256、每张 PNG 的尺寸、文件 SHA-256 与 RGBA 像素 SHA-256。能够关联的卡图同时附卡牌 ID、卡名和基础 assetId；文件名后缀保留具体变体。
- `ui/manifest.json` 记录本机 `gakumas_Data/data.unity3d` 的 SHA-256、Unity 对象类型、资源名、序列化文件、pathId、尺寸与校验值。另有 8 个 0×0 的运行时字体空纹理没有像素，列在 skipped 中，没有伪造图片。
- 此次导出覆盖当前本机已缓存的这些卡图、饮料包和基础资源中的 Sprite/Texture2D。游戏索引中未下载到本机的包没有联网补齐，因此不宣称是全版本、全服装图库。
- 游戏文件只读，未被修改；没有纳入游戏账号配置、代码、音频、视频或完整资源包。

核对图片是否完整：

```powershell
.\.venv\Scripts\python.exe tools/verify_game_assets.py
```

## 如何用于识别

原始卡面适合更新参考图库、研究局部特征与生成受控扰动。它们不包含实机 UI 背景、遮挡和按钮状态，不能直接冒充已标注的 YOLO 检测截图。

按钮常由背景、图标、文字、透明边缘及九宫格拉伸共同组成。原图是制作模板的起点；仍需在目标游戏分辨率截图上核对缩放、裁剪、状态和 ROI，不能保证把每个原始 PNG 直接设为模板就能命中。

当前程序已经使用的加工后模板仍保存在 `source/assets/resource/base/image`，与这里的原图分别保存。实验时从这些素材生成候选模板并在离线截图上对比，验证后再决定是否修改主程序。

## 从另一份本地 Unity 资源追加导出

现有图片的使用与校验不需要 UnityPy。重新导出基础 UI 图片时，在单独环境安装 `requirements-assets.txt`，然后执行：

```powershell
python -m venv .venv-assets
.\.venv-assets\Scripts\python.exe -m pip install -r requirements-assets.txt
.\.venv-assets\Scripts\python.exe tools/export_unity_images.py 'E:\DMM\gakumas\gakumas_Data\data.unity3d' outputs/new-ui-export
```

脚本只读输入，新输出目录必须尚不存在；有无法导出的实际图像时会报告失败并留下清单。加密 Octo 卡图包的解析沿用了此前本机提取工具，此仓库只保存已导出的图像和来源清单，没有复制解密依赖或凭据。

游戏素材的权利归原权利人，不随代码的 AGPL 许可证转授素材权利。
