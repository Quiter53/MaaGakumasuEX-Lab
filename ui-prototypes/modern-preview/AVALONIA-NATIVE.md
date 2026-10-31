# 用 Avalonia 原生实现这个界面

本文从原 HTML 右上角的“Avalonia 架构”弹窗独立整理，并补充现有项目的接入位置、实现顺序和可复用提示词。界面原型仍为 HTML；本文是原生实现方案，尚未实施原生重构。

## 当前工程与功能基准

以 MaaGakumasuEX **v2.1.5 / `d08174d3d6c0aecb34b8343397a8f19749a1e947`** 为功能基准。工程已有 .NET 10、Avalonia 11.3.12、CommunityToolkit.Mvvm 8.4.0 和 SukiUI。应在已有工程上替换视图、样式和控件模板，继续使用已有 ViewModel、配置读写与任务生成逻辑。

| 内容 | 原程序入口（主仓库相对路径） |
| --- | --- |
| 工作台与任务参数 | `native-ui/MFAAvalonia/Views/Pages/TaskQueueView.axaml`、`Helper/TaskOptionGenerator.cs` |
| 可缩放面板布局 | `native-ui/MFAAvalonia/Views/UserControls/Dashboard/DashboardCardGrid.cs` |
| 卡牌规则与选卡 | `native-ui/MFAAvalonia/Views/Pages/CardRulesView.cs`、`CardRulesDialogs.cs` |
| 曲线绘制与交互 | `native-ui/MFAAvalonia/Views/Pages/CardRuleCurve.cs` |
| 排序与曲线计算 | `native-ui/MFAAvalonia/ViewModels/Pages/CardRulesViewModel.cs` |
| 回忆、卡组目标 | `native-ui/MFAAvalonia/Views/UserControls/MemoryTargetControl.cs` |
| 自动自定义 | `native-ui/MFAAvalonia/Views/UserControls/CustomizationTargetControl.cs` |
| 卡牌及自定义资料 | `assets/config/card_library.json`、`assets/card_library/`、`assets/data/card_customizations.json` |
| 参数范围与选项 | `assets/tasks/produce.json`、`produce_cn.json` |

[查看固定基准源码](https://github.com/Quiter53/MaaGakumasuEX/tree/d08174d3d6c0aecb34b8343397a8f19749a1e947)。Lab 的 `source` 子模块版本独立管理；本次原型工作没有移动子模块。

## 控件与视觉映射

1. **设计变量**：将 HTML 的颜色、玻璃底色、分隔线、边框、高光、圆角、阴影分别转为 `ResourceDictionary` 资源。亮暗主题使用 `ThemeDictionaries` 与 `DynamicResource`。主题按钮图标、文字和实际主题绑定同一状态。
2. **玻璃容器**：使用 `Border`、半透明填充、渐变高光和细边框组成可复用模板。基础外观先做到与 HTML 一致，再评估透明背景和模糊成本。CSS `backdrop-filter` 不是 Avalonia 控件的直接等价属性；窗口 Acrylic/Mica 与控件后方内容模糊也不同。若需要局部背景模糊，应单独验证合成实现与性能，并保留同配色的半透明降级外观。
3. **指针高光**：通过附加行为监听当前控件的 `PointerMoved`、`PointerExited`，用本地坐标更新 `RadialGradientBrush.GradientOrigin`。渐变位于内容下方，`IsHitTestVisible=False`。不在每次移动时遍历全窗口所有玻璃卡片。
4. **滑动分段控件**：用 `ItemsControl` 或模板化控件承载选项，一个共享选中胶囊根据实际 `Bounds` 移动，动画作用于 `TranslateTransform` 和宽度。重新测量后再更新位置，兼容语言切换、DPI 与窗口缩放。
5. **输入与选择**：保留原生 `TextBox`、`ComboBox`、`NumericUpDown`、`ToggleButton` 的键盘和自动化语义，只替换模板。数字框隐藏默认微型上下箭头，以左右圆形减/加按钮调用同一值变更逻辑。等待时间维持 0～5 秒、最多两位小数、默认 1.5；出错显示原因且不写入非法配置。
6. **浮层**：统一选卡、目标编辑和确认弹窗的标题、滚动正文、底部操作区。设置焦点循环，Escape 取消，关闭后恢复打开按钮焦点。选卡先选择再确认，编辑器使用草稿，取消不写入配置。
7. **离场动效**：沿用 160～220ms 淡出、轻缩放和少量位移；按下反馈约 80～120ms。使用 Avalonia `Transitions` 或 `Animation`。浮层重开时取消上一轮退出，动画结束时核对实例身份。删除动画使用不可交互的视觉层，真实业务状态及时更新。系统或应用关闭动画时直接完成状态迁移。
8. **侧栏与面板**：用 `Grid` 和一致的图标列宽组织侧栏，底部设置按钮与其他导航使用同一模板；展开只增加文字列。保留 `DashboardCardGrid` 的布局保存、拖拽和缩放能力，检查 100%、125%、150%、200% DPI。
9. **出牌曲线**：继续使用原生 `CardRuleCurve` 与策略模型；主图、小图和手牌预览必须共享曲线语义。绘制和命中检测使用同一坐标变换；拖动始终关联同一节点，处理 `PointerCaptureLost`，避免节点越过相邻节点后改错对象。若新原型语义与原策略不一致，先列差异供审核，不能为了匹配外观悄悄更改策略。
10. **卡库规模**：按卡牌标识缓存缩略图，使用虚拟化或分页，过滤时保留搜索输入框和焦点；输入法组字期间不抢先筛选或确认。卡牌名称、图像和筛选属性来自同一目录数据，禁止用固定示例图冒充不同卡牌。

原弹窗中的两个核心建议保留在以上第 3、4、5、8 项：`PointerMoved + RadialGradientBrush` 的指针高光，以及 `ComboBox.Popup` 模板与 `DashboardCardGrid` 的原生实现。

## 工作台布局的原生迁移

原型默认布局为左侧任务列表／任务说明上下排列、中间任务设置、右侧运行日志，实时画面默认隐藏。原生实现应在现有 `DashboardCardGrid` 基础上接入统一的布局模型，不复制 HTML 中当前窗口的绝对像素坐标。

- 模型保存版本号、列顺序、列宽权重、列内面板顺序和高度权重，以及实时画面显隐；面板使用稳定标识，隐藏后仍保留位置。现有用户布局应通过明确的版本迁移继续读取。
- 一次布局计算统一分配可用区域，先满足各面板最小尺寸，再按权重分配空间。上／下投放在同列叠放，左／右投放分列；源列剩余面板补满，空列移除。列宽与行高分隔条也修改同一模型。
- 指针按下保存原模型，越过拖动阈值后生成预览模型；命中检测使用稳定的拖动前布局，避免周围面板动画导致目标跳动。预览时同时更新全部面板的排列和尺寸，松手确认后才持久保存。
- 用原生布局与视觉层保留控件实例、焦点和未提交输入，不在每次移动时重新创建视图。拖动影像不可交互，不能复制运行中的业务控件绑定或事件。
- Escape、工作区外释放、窗口失焦、窗口尺寸变化和 `PointerCaptureLost` 应清理影像与事件并恢复原布局；正常释放时先结束事务，避免释放捕获触发二次取消。
- 提供键盘移动、恢复默认布局、最大化／还原；隐藏实时画面后重新分配空间。窗口太小时允许工作区滚动，避免压成无法操作的面板。
- 延用玻璃高光和位移／尺寸过渡；减少动画模式直接完成布局。检查 DPI、窄窗口、跨列连续移动、取消与重启恢复，以及布局保存失败时的提示。

以上为原生迁移要求；本轮实现和浏览器验证仅覆盖 HTML 原型。

## 功能对照要求

- 通用选卡：搜索、稀有度、计划、技能分类、来源、转换、再动、解锁等级、排列方式、重置筛选、结果数量、选中态、取消/确认。
- 国民配合目标：使用原程序的候选规则，排除国民自身；支持选择和清除。
- 回忆目标：强化不限/未强化/已强化、绿豆下限，SSR 最多 1，R/SR 最多 2；普通目标排除 LR、角色卡和支援卡；允许多个不同条件目标，拒绝完全重复条件。
- 卡组目标：角色卡、支援卡、四个普通卡槽，可留空；以同一份回忆满足全部已选条件为目标。槽位类别不应被解释为后四张牌必须按列表顺序出现。
- 自定义目标：来自实际自定义资料，选项次数、单项上限、单卡总上限、目标排序与删除，草稿保存/取消。
- 使用道具：名称与选择状态分开绑定，点选不得覆盖名称。两个道具独立选择，默认状态以任务配置为准。

## 可直接复用的实现提示词

```text
请在现有 MaaGakumasuEX 的 native-ui 工程中，用 Avalonia 原生控件实现
MaaGakumasuEX-Lab/ui-prototypes/modern-preview/MaaGakumasu-UI-Modern-Preview.html
展示的液态玻璃界面。先读取两个仓库的 AGENTS.md 和该原型目录说明。

功能基准为 v2.1.5，提交 d08174d3d6c0aecb34b8343397a8f19749a1e947。
目标是复刻视觉与交互，不使用 WebView，不直接执行 HTML 的演示逻辑。
沿用现有 ViewModel、配置结构、任务生成、识别和出牌策略；保留用户配置兼容性。

先对照 TaskQueueView、CardRulesView、CardRulesDialogs、CardRuleCurve、
MemoryTargetControl、CustomizationTargetControl、DrinkSettingsView、
CardListSettingsView，列出原型与原程序的控件和参数差异。
对照 assets/tasks/produce.json、produce_cn.json 确认字段范围、默认值与级联关系。
发现策略或数据含义冲突时列出具体差异，不擅自改业务含义。

先建立共享浅/深主题资源，再实现 GlassPanel、按钮、分段控件、下拉框、
数字步进器、弹窗和 Toast。按本文“工作台布局的原生迁移”实现统一布局模型、
自动让位和尺寸分配、拖动预览与提交、分隔条缩放、保存与恢复；
默认左侧任务列表与说明上下排列、中间设置、右侧日志。保留现有用户布局兼容性。
主题状态统一绑定；数字输入不得暴露不协调的系统上下箭头；
道具名称不可被选中状态覆盖；自动自定义开关不额外套上下分隔线；
窗口标题栏不显示 Avalonia 技术说明入口。

选卡使用真实完整卡库和缩略图，补齐本目录 AVALONIA-NATIVE.md 的功能对照要求。
编辑使用草稿，取消不保存，确认才提交；保留输入法组字、焦点、键盘和自动化支持。
浮层重开取消旧退出动画；减少动画模式立即完成；不增加全窗口逐帧遍历。
曲线绘制、拖动命中与权重计算共享坐标和语义。

按主题/基础控件、工作台、规则页、选卡与目标编辑器、其他页面的顺序实现。
每阶段用实际原生窗口验证，提供深浅主题截图及 100%/150% DPI 结果；
运行与改动相关的原生 UI 和配置兼容性检查，区分通过、失败、未验证。
不要为了迁就预览改识别阈值、战斗等待策略或培育流程。
发布动作遵循当前用户授权和仓库要求。
```
