---
name: 知微 · 深海光学玻璃 v5
description: 以原生文字、图表与可编辑科学图稿承载证据的中文研究展示
colors:
  marine-bg: "#002030"
  glass-panel: "#042735"
  foreground: "#f5fbff"
  muted: "#b5d1de"
  content-muted: "#bad8e4"
  cyan: "#76daff"
  teal: "#83ebd6"
  lavender: "#d6c3ff"
  gold: "#f4cf84"
  coral: "#ff9584"
  glass-soft: "#124354"
  line: "#456776"
  chart-grid: "#315361"
  chart-teal: "#61e6d3"
  chart-coral: "#ff967f"
  chart-blue: "#76ccff"
typography:
  display:
    fontFamily: "ResearchGeist, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "clamp(28px, 3vw, 43px)"
    fontWeight: 650
    lineHeight: 1.4
    letterSpacing: ".015em"
  headline:
    fontFamily: "ResearchGeist, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "clamp(30px, 3.1vw, 46px)"
    fontWeight: 650
    lineHeight: 1.35
    letterSpacing: ".005em"
  title:
    fontFamily: "ResearchGeist, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "32px"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "-.02em"
  body:
    fontFamily: "ResearchGeist, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.8
    letterSpacing: normal
  content-body:
    fontFamily: "ResearchGeist, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.65
    letterSpacing: normal
  label:
    fontFamily: "ResearchGeist, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "17px"
    fontWeight: 500
    lineHeight: 1.8
    letterSpacing: ".045em"
  compact-study-title:
    fontFamily: "ResearchGeist, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "25px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: ".01em"
  compact-plot:
    fontFamily: "'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "15px"
    fontWeight: 400
  compact-code:
    fontFamily: "SFMono-Regular, Consolas, 'Liberation Mono', monospace"
    fontSize: "11.5px"
    fontWeight: 400
    lineHeight: 1.45
  home-brand:
    fontFamily: "'Songti SC', 'STSong', serif"
    fontSize: "86px"
    fontWeight: 400
    lineHeight: 1.25
    letterSpacing: ".12em"
rounded:
  optical-panel: "17px"
  optical-inner: "13px"
  figure-canvas: "12px"
  inset: "9px"
  result: "7px"
  badge: "28px"
  orb: "50%"
spacing:
  inset: "12px"
  grid: "14px"
  caption: "20px"
  figure-gap: "26px"
  section: "30px"
  compact-grid: "20px"
  compact-section: "42px"
components:
  chapter-nav:
    textColor: "{colors.foreground}"
    typography: "{typography.label}"
    padding: "0 16px"
    height: "52px"
  chapter-nav-current:
    textColor: "{colors.cyan}"
  optical-panel:
    textColor: "{colors.foreground}"
    rounded: "{rounded.optical-panel}"
  figure-canvas:
    backgroundColor: "{colors.glass-panel}"
    rounded: "{rounded.figure-canvas}"
  question-badge:
    textColor: "#f1faff"
    rounded: "{rounded.badge}"
    padding: "3px 26px 5px"
  result-strip:
    textColor: "{colors.foreground}"
    rounded: "{rounded.result}"
    padding: "7px 13px"
  source-field:
    backgroundColor: "#a75a5333"
    textColor: "{colors.coral}"
    rounded: "4px"
    padding: "0 2px"
  compact-study-panel:
    textColor: "{colors.foreground}"
    rounded: "{rounded.optical-panel}"
    padding: "0 0 14px"
  compact-saved-case:
    textColor: "{colors.foreground}"
    rounded: "{rounded.optical-inner}"
    padding: "14px"
  atlas-select:
    backgroundColor: "#063344"
    textColor: "{colors.foreground}"
    rounded: "5px"
    padding: "10px 34px 10px 12px"
---

# Design System: 知微 · 深海光学玻璃 v5

## Overview

**Creative North Star: "深海光学玻璃"**

以用户提供的六张 v5 参考图为视觉依据：深海背景、折射光弧、白色中文、带双层亮边的厚玻璃容器。玻璃边缘和局部高光具有明确的材质感，内部保持安静，供读者辨认原生文字、真实表格和科学图形。首页中央文字为“知微”。

光学素材只承担环境与装饰。问题、提示词、来源字段、坐标、数值、置信区间和结论全部由 HTML、原生 SVG 或独立科学 SVG 呈现。系统不把研究内容烘焙进背景图。

**Key Characteristics:**

- 深海底色与白色中文形成清楚的阅读层级。
- 青、绿、紫、金色玻璃边缘对应并列的研究内容。
- 双层边框、顶部亮线与内凹高光共同表达光学玻璃。
- 图形与文字直接展示，阅读路径不依赖展开或悬停。

## Colors

前置 token 是当前实现的规范值，来源为 `app/research-ocean.css`、`app/research-content-ocean.css`、`app/research-findings-compact.css` 与 `scripts/figures/build_research_atlas.py`。侧车的八级OKLCH色阶仅供设计面板预览，不是新增运行时颜色。

### Primary

- **光学青**：主边缘、当前章节、可聚焦图形与高亮结果的共同提示。
- **折射绿**：第二类玻璃面板、反馈结果与对照关系。面板使用 `teal`；根变量 `--teal` 仍为 `#7debdc`，不应把它误记成所有组件的实际颜色。

### Secondary

- **透镜紫**与**微光金**：并列维度、任务面板和科学系列的辅助区分。
- **映射珊瑚**：清洗图中同义异名的字段；它不表示字段错误。

### Neutral

- **深海底色**：整个章节背景；装饰 PNG 覆于其上。
- **深海玻璃面**：科学图稿与图形画布的稳定底色。
- **冰白正文**：标题、主要文字与坐标。
- **海雾次级文字**：条件、来源、范围说明；内容章节另使用 `content-muted`。

**The Scientific Palette Rule.** 科学图使用生成器的 `chart-teal`、`chart-coral`、`chart-blue`、金、紫和 `chart-grid`。界面边缘色与图形系列色分别维护；改配色只改呈现层，不改系列顺序、数据或统计。

## Typography

中文使用平台中文无衬线，拉丁字符与界面数字使用本地 ResearchGeist。当前研究壳实际载入 Regular 与 Semibold 两个字体文件；其他请求字重由浏览器匹配。首页“知微”保留宋体。代码区使用 `SFMono-Regular, Consolas, Liberation Mono, monospace`。

`display` 用于总研究问题的真实 h1；`headline` 用于章节标题；`title` 用于发现主题。主体阅读为 `body`，问题、采集、清洗和总结原生构图为 `content-body`。数字、结果表与科学图使用等宽数字。玻璃标签不替代标题语义。

手机上总问题变为27px、1.6行高；章节标题变为29px，紧凑发现标题为30px；首页品牌变为49px，359px以下变为43px。紧凑数学／文档图使用14–15px坐标与数值；案例代码为11.5px、1.45行高，640px以下为11px、1.55行高。宽图通过局部横向滚动保持可读。

## Layout

章节容器最大宽度 1530px，通常两侧各留 24px；850px 以下两侧各留 18px。顶栏桌面高度 58px，620px 以下分为品牌与五章两行，最小高度 107px。首页为独立的五气泡空间构图，宽度上限 1260px，桌面最小高度 760px、手机最小高度 790px；手机仍保留五颗气泡。

研究问题的中央总问题连接三张任务仪器；采集使用四维玻璃面板，完整列出 31 种实际提示词；清洗在同一 Figure 中并列 A/B/C，再接 D 的 21 列结构。具体页面约束以 `.impeccable/surfaces/app-index-html.md` 为准。

发现主线为四段连续构图：四个总体概览、数学与文档、代码反馈效果、真实修复与回退。1440×900下总高3061px，约3.4屏；使用自然内容高度，手机可更长。数学／文档面板为等宽双列、间距20px，1100px以下堆叠；段间距42px，手机收紧到30–32px。两例代码案例为双列，640px以下堆叠。主线不重复独立图册的44张附图。

620px以下概览改为单列，其原生图宽度保留560px。数学／文档图最低宽度620px；反馈端点图在1000px以下保留1040px宽度。图册补充图最低宽度1100px，结果表最低宽度760px。宽内容放入有名称、可键盘聚焦的局部横向滚动区域，页面本身不得横向溢出。采集、清洗、总结继续在1200px、1000px、640px调整原生构图。

## Elevation & Depth

深度由透明渐变、双层光学边框、内侧高光和少量外发光组成。双边框与明显高光是六张参考图指定的材质语言，应继续保留。主要面板使用 1px 彩色外边、内缩 2px 的第二边框和 2px 顶部亮线；内容面板第二边框内缩 3px。顶栏背景半透明并模糊 18px。

主要图形框的实际阴影为 `inset 0 1px 2px #f2ffffb0, inset 0 0 0 3px #9ddff533, inset 0 -2px 4px #40daff66, 0 0 9px #5fd9ff33, 0 14px 28px #000b1733`。内容面板使用同类语法，底边发光随所属色变化；完整值保存在 `.impeccable/design.json`。

背景图固定铺满视口。发现页在所有宽度使用下部渐深遮罩；其他章节保留620px以下的v5遮罩，降低自由段落背后的亮度。紧凑反馈图与案例沿用双层亮边和内凹高光，不增加新背景。当前发现复核见 `.impeccable/review/compact-v6/`，其他章节对比度记录见 `.impeccable/review/final-v5/contrast-results.json`。

## Shapes

主要光学容器采用 `optical-panel` 圆角；内边缘跟随较小圆角。嵌入问题、字段映射和结果条采用更紧的曲率。首页使用圆形玻璃气泡与中央透镜。连接线是信息关系的静态表达，不是新的章节按钮。

## Components

### Navigation

顶栏左侧“知微”返回首页，右侧仅五个章节链接。当前项为光学青、细亮下划线与局部发光；桌面章节间有斜线，手机移除斜线并保留五项。正文没有页底前后翻页、左右键跳章、跨章推荐或跳转 CTA。独立的 `?chapter=atlas` 仍有筛选、图稿导出、13 类通用交互图与 4 个代码视图，主线不展示其入口。

### Glass Panels and Insets

外层玻璃面承载任务、维度与科学图；内嵌面用于具体问题、回答、规则与结果。青、绿、紫、金色主题共享同样的边框结构。增加内容时使用原有结构，避免把长段文字分成大量小玻璃框。

### Scientific Figures

`renderCompactFindings(catalog,publication)` 从冻结目录与已发布快照生成主线原生HTML／SVG，四个总体概览使用 `renderOceanOverview`。数学保留四模型八柱与四个Token变化；文档保留九个真实位置、两模型18点及各点95%区间。代码端点图保留两模型六策略，使用共同且明确标示的60–100%截取轴，全部初稿、终稿与区间均在轴内；它使用点与区间编码。

完整44张独立科学SVG、四个完整案例与13＋4交互视图继续由 `?chapter=atlas` 提供。主线图形和四个概览不算作原44张。图内标题、坐标、单位、条件、标注、范围和来源必须可读；旧实验与新完整评测分别保存、分别叙述，不裁掉图例或坐标。

### Compact Evidence and Cases

数学／文档面板继承主要光学容器，标题与条件在上，图形、数值和一句结论依次排列。代码端点图与案例采用 `optical-inner` 圆角、稳定深海底面和双层光学亮边。案例展示真实反馈字段的标注摘录、完整保存diff，以及公开／完整测试的前后结果；完整反馈和前后代码在图册保留。紧凑密度通过合并构图与缩短说明实现，不能裁剪研究内容或伪造数值。

### Source Fields and Saved Records

两种来源各有四个珊瑚色同义异名字段，四组映射全部出现；保存表同时展示两条记录的九个关键字段，完整 21 列结构继续可见。字段高亮使用 `source-field`；完整数据记录和字段类型来自实际数据对象，不为视觉对称修改值。

### Home Lens and Bubbles

`renderHome()` 保留原五颗玻璃素材与可见中央“知微”。气泡悬停或键盘聚焦放大至 1.045，过渡 0.4s，缓动 `cubic-bezier(.16,1,.3,1)`；光学背景没有持续运动。首页方向键仅在五个入口间移动焦点，不直接切换正文章节。

### Focus and Reduced Motion

常规焦点为 3px 明确轮廓，颜色由深海层改为浅青；首页气泡使用 2px 轮廓与 9px 偏移。滚动图表与表格也能获得焦点。`prefers-reduced-motion: reduce` 关闭动效和过渡，气泡不缩放；静态阅读仍完整。

## Do's and Don'ts

### Do:

- **Do** 保留深海底色、光学双边框和参考图中的局部边缘高光。
- **Do** 使用原生文字与真实科学图呈现全部证据，维护局部滚动区域的名称与键盘焦点。
- **Do** 将视觉配色、布局和可选转场与冻结统计、评分口径分别维护。
- **Do** 在 1440px 与 390px 检查首屏、长文、图内文字和背景对比。

### Don't:

- **Don't** 将背景素材用于承载文字、界面或科研数据。
- **Don't** 增加第六颗气泡、正文跳转 CTA、页底翻页或左右键跳章。
- **Don't** 隐藏清洗步骤、实际提示词，或删除独立图册的完整44图与案例。
- **Don't** 改写数值、坐标、分母、置信区间、任务评分或把未知模型规模填为零。
- **Don't** 把两种接近的已知参数规模与另外两个未知规模解释为已建立 Scaling Law。
