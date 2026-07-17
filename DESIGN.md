---
name: 心宠 Conversation Console
description: A clear, light, state-aware control surface for voice, identity, and robot operation.
colors:
  canvas: "#F5F5F7"
  surface: "#FCFCFD"
  surface-neutral: "#ECECF0"
  ink: "#1D1D1F"
  ink-secondary: "#515154"
  ink-muted: "#6E6E73"
  line: "#D2D2D7"
  line-strong: "#A8A8AD"
  signal: "#E49B0F"
  signal-deep: "#8A5700"
  signal-soft: "#FFF6E5"
  success: "#16734B"
  success-soft: "#EAF7F0"
  danger: "#B42318"
  danger-soft: "#FDEDEA"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Microsoft YaHei, sans-serif"
    fontSize: "34px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0"
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Microsoft YaHei, sans-serif"
    fontSize: "26px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "0"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Microsoft YaHei, sans-serif"
    fontSize: "20px"
    fontWeight: 650
    lineHeight: 1.4
    letterSpacing: "0"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Microsoft YaHei, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.65
    letterSpacing: "0"
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Microsoft YaHei, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0"
rounded:
  sm: "4px"
  md: "8px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  xxl: "48px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "0 24px"
    height: "52px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "0 24px"
    height: "52px"
  field-search:
    backgroundColor: "{colors.surface-neutral}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "0 44px"
    height: "52px"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "24px"
---

# Design System: 心宠 Conversation Console

## Overview

**Creative North Star: “银色实验台”**

**Design Read:** 这是面向机器人专家和演示人员的桌面优先控制台。使用者通常站在光线明亮的实验室或办公室里，需要快速判断机器人是否连接、正在听、正在思考或正在说话。视觉语言应像精密消费电子的控制面板：明亮、安静、可信、触感清楚；参考 Apple 的信息克制和材质反馈，但不复制官网营销页，也不做滚动劫持。

本次属于**视觉重构、功能保留**。保留“对话、身份与语气、设置、关于”四个入口和所有现有回调，只重建布局、组件、状态表达与文案层级。`DESIGN_VARIANCE: 5`、`MOTION_INTENSITY: 4`、`VISUAL_DENSITY: 6`：足够精致，但始终让任务先于装饰。

### Information architecture

- 顶部是高度 88–104px 的设备栏：品牌、机器人连接状态、当前模式；不是营销 Hero。
- 导航使用水平标签页。当前标签由文字加 2px 信号色下划线表示，不使用整块彩色背景。
- “对话”页采用 8/4 栅格：左侧为会话操作和记录，右侧为连接、ASR、LLM、TTS 与动作状态。
- “身份与语气”页先选择现有身份，再创建新身份；每个字段有可见标签、图标和帮助文字。
- “设置”页用分组定义列表展示配置，敏感值只显示“已配置/未配置”，不直接显示密钥。
- “关于”页只解释语音链路和能力边界，不出现营销卡片阵列。

### Layout and responsive behavior

- 页面背景必须铺满视口，禁止出现右侧黑边。内容最大宽度 1440px，宽屏左右留白 48px，普通桌面 32px，移动端 16px。
- 使用 12 列网格，主间距 24px；卡片内部间距 24px。页面分区优先靠留白和分隔线，不把所有内容装进卡片。
- 低于 960px 时右侧状态栏移到主内容下方；低于 640px 时操作按钮纵向排列，标签页允许横向滚动。
- 所有固定工具区域使用稳定高度或 `min-height`，状态文案变化不得造成页面跳动。

**Key Characteristics:** 冷白银灰底、石墨文字、少量信号琥珀；中文大字号；显式状态；标准控件；轻量且有意义的动效。

## Colors

配色采用“纯净银灰 + 石墨 + 信号琥珀”。90%以上面积保持中性，颜色只承担操作、选中和状态含义。

### Primary

- **石墨操作色** (`#1D1D1F`)：主按钮、关键标题和高优先级图标。它提供稳定对比，不把界面变成深色主题。
- **信号琥珀** (`#E49B0F`)：当前标签下划线、活动指示灯和语音波形，单屏占比不得超过 8%。
- **深琥珀** (`#8A5700`)：浅色背景上的信号文字、焦点边框和警告文案，保证可读性。

### Neutral

- **实验台画布** (`#F5F5F7`)：整个浏览器视口的背景。
- **器件表面** (`#FCFCFD`)：输入框、对话区和主要内容面板；不是纯白。
- **控制槽** (`#ECECF0`)：搜索框、分段控制、禁用区域和次级工具栏。
- **一级文字** (`#1D1D1F`)：标题和正文重点。
- **二级文字** (`#515154`)：正文、说明和配置值。
- **辅助文字** (`#6E6E73`)：非关键提示；不得用于小字号占位符以规避对比度要求。
- **分隔线** (`#D2D2D7`) 与 **强调边界** (`#A8A8AD`)：结构分隔和悬停边界。

### Semantic

- **正常** (`#16734B` / `#EAF7F0`)：连接成功、保存成功、正在运行。
- **错误** (`#B42318` / `#FDEDEA`)：连接失败、保存失败、服务异常。
- 等待和警告复用深琥珀与浅琥珀底，不再增加蓝、紫、薄荷绿或珊瑚红装饰色。

**The Signal Rule.** 信号色只表示“现在可以做什么”或“系统此刻在做什么”，绝不铺满标题区、整行按钮区或大面积面板。

## Typography

**Display Font:** 系统无衬线字体（macOS 为 SF Pro，Windows 为 Segoe UI / Microsoft YaHei）
**Body Font:** 同一字体族
**Data/Mono Font:** `SFMono-Regular, Consolas, monospace`，仅用于端口、模型名和配置键

**Character:** 单一系统字体保证中文清晰、跨平台稳定，也让工具界面显得熟悉。字阶固定，不随视口连续缩放；不用展示字体、斜体或负字距制造“高级感”。

### Hierarchy

- **Display** (700, 34px, 1.2)：页面标题，每页最多一个。
- **Headline** (700, 26px, 1.3)：页面内主要任务区标题。
- **Title** (650, 20px, 1.4)：面板标题、状态组标题。
- **Body** (400, 17px, 1.65)：说明、对话和配置值，长文最大 70ch。
- **Label** (600, 15px, 1.4)：表单标签、按钮和导航；不使用全大写，不增加字距。
- **Meta** (500, 14px, 1.5)：时间、端口、模型标识；颜色至少达到 WCAG AA。

**The Legibility Rule.** 任何关键操作和对话内容不得小于 17px；占位符也必须达到 4.5:1 对比度，标签永远不能只靠占位符代替。

## Elevation

系统以**色调分层和边界**表达深度，静止状态基本无阴影。画布、表面和控制槽形成三层；仅下拉浮层、提示气泡和正在拖动的元素获得阴影。这样既保留 Apple 式的干净材质，也避免当前“大黑框 + 白输入框”的割裂。

### Shadow Vocabulary

- **浮层** (`0 6px 16px rgb(29 29 31 / 0.12)`): 只用于下拉菜单、工具提示和临时弹层，不与粗边框同时使用。
- **焦点** (`0 0 0 3px rgb(228 155 15 / 0.24)`): 键盘焦点环，配合 `#8A5700` 边界。
- **按压**：不使用阴影；按下时 `transform: scale(0.98)`。

**The Flat-by-Default Rule.** 页面区块默认无阴影；若一个容器既有 1px 边框又有大于 8px 模糊阴影，视为不合格实现。

## Components

所有控件使用同一套 8px 圆角、1px 边界和 Lucide 图标。图标统一 20px、2px 描边；由本地打包的 Lucide 资源渲染，禁止使用“⌕”“+”等字符假装图标，也禁止手绘 SVG。

### Application shell and navigation

- 顶部设备栏使用项目资产 `src/reachy_mini_openclaw/assets/xinchong-logo.jpg` 作为心宠 Logo，不再使用通用机器人线框图标。
- 顶部设备栏为无框全宽区域，下方 1px 分隔线。左侧显示“心宠对话控制台”，右侧显示连接圆点和“本地设备 / 已连接”等真实状态。
- 标签页高 48px、间距 24px。默认文字 `#515154`，悬停为 `#1D1D1F`，当前项用 `#1D1D1F` 加 2px `#E49B0F` 下划线。
- 标签切换 180ms，不做页面入场编排，不隐藏内容等待动画结束。

### Buttons

- 主按钮高 52px、8px 圆角、石墨底和浅色文字；按钮前放与命令匹配的 Lucide 图标，如 `Play`、`Square`、`Save`。
- 次按钮为器件表面底和 `#D2D2D7` 边界；危险操作只在确实会中断会话时使用红色文字。
- 悬停只改变一个色阶；焦点显示 3px 焦点环；按下缩放到 0.98；禁用时仍保持文字可读且不响应悬停。
- 加载状态保留原按钮宽度，用短状态文字“正在连接…”和小型进度符号，避免布局跳动。

### Search, select, and text fields

- 每个字段上方有 15px 可见标签。控件高 52px、8px 圆角、`#ECECF0` 背景、1px 透明边界；悬停出现 `#A8A8AD` 边界。
- 搜索/选择身份控件必须像参考图：左侧 20px `Search` 图标，图标距左 16px，输入文字距左 44px；右侧使用标准 `ChevronDown`，不能只显示上下小三角。
- 聚焦时表面切换为 `#FCFCFD`，边界变为 `#8A5700`，同时显示 3px 柔和焦点环。错误状态使用 `#B42318` 边界并在字段下方给出具体中文说明。
- 多行文本区最小高 220px，可调整高度；长内容内边距 16px，行高 1.65。只读状态使用中性浅底，不伪装成可编辑输入框。

### Status system

| 状态 | 中文文案 | 视觉 | 动效 |
| --- | --- | --- | --- |
| 空闲 | 准备开始对话 | 灰色圆点 | 静止 |
| 连接中 | 正在连接机器人 | 琥珀圆点 | 800ms 旋转，仅加载时运行 |
| 倾听 | 正在听你说话 | 琥珀波形 | 跟随真实麦克风能量变化 |
| 思考 | 正在组织回答 | 三点进度 | 900ms 顺序淡入 |
| 说话 | 正在回答 | 石墨波形 + 琥珀游标 | 跟随真实播放状态 |
| 成功 | 对话已启动 | 绿色圆点 | 180ms 交叉淡化 |
| 错误 | 连接失败：具体原因 | 红色图标和浅红底 | 出现一次轻微位移，不循环 |

状态变化使用 180–240ms `cubic-bezier(0.16, 1, 0.3, 1)`。所有循环动效必须绑定真实的连接、倾听、思考或播放状态；`prefers-reduced-motion` 下改为静态图标和文案。

### Conversation transcript

- 对话记录是主任务表面，不再嵌套卡片。消息之间用 16px 间距和角色标签区分。
- 用户消息使用控制槽灰背景；机器人消息使用器件表面与 1px 分隔线。文字 17–18px，最大宽度 72ch。
- 空状态显示麦克风图标、标题“还没有对话”和一个主按钮“开始对话”；加载使用与消息形状一致的骨架，不使用居中转圈。

### Panels and page blueprints

- 右侧会话配置面板采用中性表面和分隔列表，不使用薄荷绿整块背景。每行是图标、名称、当前值和状态点。
- 身份页分为“当前身份”和“创建身份”两个连续区段，用 32px 留白和 1px 分隔线组织，不放卡片套卡片。
- 设置页使用两列定义列表：左侧项目名，右侧值与状态；窄屏改为单列。API 密钥永远不在页面中明文回显。
- 关于页使用简短流程 `语音输入 → 百度 ASR → Qwen → 百度 TTS → 心宠`，配统一线性图标，不使用相同尺寸的功能卡片阵列。

### Accessibility and implementation contract

- 正文和占位符对比度至少 4.5:1；大字至少 3:1；目标尺寸至少 44×44px。状态不能只用颜色表达。
- 键盘顺序遵循视觉顺序；所有图标按钮有中文 `aria-label` 和工具提示；聊天记录更新使用 `aria-live="polite"`。
- Gradio 组件必须设置稳定 `elem_id`，CSS 只作用于这些 ID 或项目类名。禁止再全局覆盖 `.wrap`、`.block`、所有 `button *` 等内部类。
- 页面根节点宽度 100%，内层 `.app-frame` 控制 1440px 最大宽度。实现时先在 7861 绑定源码预览，确认后才重建 7860 正式容器。

## Do's and Don'ts

### Do:

- **Do** 使用冷白画布、清楚边界和大号中文，先保证专家在远距离也能识别状态。
- **Do** 在搜索、选择、保存、播放和停止等控件前使用同一套 Lucide 图标。
- **Do** 为默认、悬停、焦点、按下、禁用、加载、错误和成功状态都写出视觉规则。
- **Do** 让动效对应机器人真实状态；监听、思考和说话必须看起来不同。
- **Do** 在 1920×1080、1440×900、1024×768 和 390×844 四个视口检查溢出、黑边、文字遮挡和控件可见性。
- **Do** 保持所有功能回调、Docker 配置和环境变量行为不变。

### Don't:

- **Don't** 使用深色主题、黑色大面板、紫蓝渐变、玻璃拟态、装饰网格或 CSS 光球。
- **Don't** 大面积铺满蓝、薄荷绿、珊瑚红或信号琥珀；强调色单屏占比不得超过 8%。
- **Don't** 使用字符“⌕”“+”“▲▼”代替图标，也不要手绘图标。
- **Don't** 把标签隐藏进占位符；不要让输入框和页面背景融为一体。
- **Don't** 使用 12px 以上卡片圆角、胶囊形输入框、嵌套卡片或“边框 + 大柔光阴影”的幽灵卡片。
- **Don't** 给每个区域套相同的入场动画、无限扫光或与状态无关的语音波形。
- **Don't** 为追求“苹果感”加入营销 Hero、滚动劫持、超大标题或无关产品图；这是控制工具，不是落地页。

**Acceptance gate:** 页面没有横向溢出和右侧黑边；所有输入框一眼可辨；四个页面共享同一组件词汇；状态文案与真实运行一致；关闭动效后仍能完整使用；关键文字通过 WCAG AA。
