# 知微 · AI 对话数据与模型行为分析

《数据分析与可视化实践》课程设计题目二，选择 **B：可视交互系统**。本项目研究：**输出表达、证据位置与执行反馈，如何影响模型回答的质量和开销？**

系统将数学与选择题、文档问答、代码生成与修复的保存实验连接到五个交互板块，提供模型和策略比较、统计区间、匿名案例及数据表。运行网站使用本地数据，不调用模型 API，也不需要密钥。

> **教师查阅入口：** [课程原文](guide/数据分析和可视化-题目2.pdf) · [要求与实现对照](guide/README.md) · [案例报告 PDF](report/case_report.pdf) · [答辩 PPT PDF](presentation/defense_slides.pdf) · [数据字典](data/data_dictionary.md)
>
> **系统入口：** [本地预览](http://127.0.0.1:8770/)（先运行下方启动命令） · [在线部署设置](docs/github-pages.md)（本仓库尚未启用 Pages）

<a id="contents"></a>
## 阅读导航

| 想做什么 | 从这里开始 |
|---|---|
| 启动并体验系统 | [快速运行](#quick-start) → [交互操作](#interaction) |
| 按老师要求验收 | [提交结构](#layout) → [课程要求对照](guide/README.md) |
| 了解数据与结论 | [研究设计](#research) → [五项发现](#findings) → [数据口径](#data) |
| 复算或检查项目 | [复现方法](#reproduce) → [自动检查](#checks) |
| 准备报告与演示 | [报告与答辩](#delivery) → [演示顺序](docs/demo-guide.md) |
| 修改代码、查找文档 | [代码地图](#source) → [文档索引](docs/README.md) |

<a id="quick-start"></a>
## 快速运行

网站构建与启动只使用 **Python 3.10 及以上版本的标准库**。npm 和分析库只在浏览器测试或数据复算时需要。

### 1. 获取源码

```bash
git clone https://github.com/Fwlyii/dataAnalysis-vision.git
cd dataAnalysis-vision
git switch main
```

已有仓库可执行 `git pull --ff-only origin main`。大体积研究材料使用 Git LFS，下载方法见[数据说明](data/DOWNLOAD.md#download)。网站使用随仓库保存的匿名 JSON、字体和 SVG，可以先运行系统，再按复算需要下载数据。

### 2. 启动服务

```bash
python3 app/launch.py --port 8770
```

在浏览器打开 **<http://127.0.0.1:8770/>**。Windows 可使用 `py -3 app/launch.py --port 8770`。端口已占用时改为 `--port 8780`；使用 `--no-open` 可以关闭自动打开浏览器。

通过 VS Code Remote SSH 运行时，在“端口”面板转发服务端口，再打开本机的对应地址。源码页面会通过 HTTP 加载数据，请使用启动命令，不要直接双击 HTML。

### 3. 只构建静态网站

```bash
python3 scripts/system/build_web_app.py
python3 -m http.server 8770 --bind 127.0.0.1 --directory app/dist
```

`app/dist/` 是构建产物，不手动维护、不提交。修改源码后重新运行构建或启动命令，即可得到带 CSS/JS 版本标识的新页面。

[↑ 返回导航](#contents)

<a id="interaction"></a>
## 系统交互与访问路径

| 板块 | 访问地址（服务启动后） | 可以操作什么 |
|---|---|---|
| 五球入口 | [首页](http://127.0.0.1:8770/) | 跳过或重播开场；点击光球进入章节；点击左上角“知微”返回 |
| 研究问题 | [第一屏](http://127.0.0.1:8770/#s1) | 切换模型，查看 31 项提示策略在三个题库中的表现 |
| 实验设计 | [第二屏](http://127.0.0.1:8770/#s2) | 点选策略矩阵，联动实际指令、实验设计与条件统计 |
| 数据处理 | [第三屏](http://127.0.0.1:8770/#s3) | 选择字段，查看来源映射、转换方式与统一结构 |
| 核心发现 | [第四屏](http://127.0.0.1:8770/#s4) | 切换三页发现、模型、题库、代码反馈与测试口径；查看说明和数据表 |
| 结论与反思 | [第五屏](http://127.0.0.1:8770/#s5) | 阅读五项建议与适用边界，直接打开课程要求、报告和答辩 PDF |
| 完整图册 | [补充探索](http://127.0.0.1:8770/legacy.html?chapter=atlas) | 查看完整历史图册、原始交互视图及匿名记录联动 |

五屏支持页内滚动，章节深链接支持刷新恢复。光球支持 Tab、方向键、Home/End 和 Enter；Escape 可跳过开场或返回上次进入的章节。系统适配手机和矮屏，并遵循“减少动态效果”偏好。

[↑ 返回导航](#contents)

<a id="layout"></a>
## 按课程要求组织的仓库

对应[课程 PDF 第 6–8 页](guide/数据分析和可视化-题目2.pdf)的“系统组”结构。教师可直接从以下四个核心目录检查交付物；其余目录保存复现所需代码、统计证据和测试。

```text
dataAnalysis-vision/
├── README.md                  运行、研究、导航和验收说明
├── guide/                     老师课程要求原文及逐项对照
├── app/                       可运行系统的 HTML/CSS/JS、字体和匿名快照
├── data/
│   ├── raw/                   原始实验材料与采集来源（大文件使用 LFS）
│   ├── processed/             清洗结果、统一匿名特征和字段表
│   ├── quality/               缺失、排除、评分与质量记录
│   ├── inventory/             原始材料和处理产物的校验清单
│   └── data_dictionary.md     字段含义、单位、来源和缺失规则
├── report/
│   └── case_report.pdf        案例报告（10 页）
├── presentation/
│   └── defense_slides.pdf     答辩 PPT 的 PDF 版（12 页）
├── scripts/                   采集、清洗、分析、绘图、构建与文档生成
├── experiments/               各专项实验的协议和实现
├── reports/                   CSV/JSON 统计、区间、研究结论和 SVG 证据
├── configs/                   实验配置示例，不含密钥
├── requirements/              按分析与生成任务划分的依赖
├── docs/                      方法、复算、演示、设计和部署说明
└── tests/                     浏览器回归与科研文件保护
```

`report/` 是供阅读的案例报告，`reports/` 是支撑报告和图表的统计结果。两者用途不同。根目录就是规范源码入口，不再在 Git 中保存另一份 `submission/` 源码副本。

老师示例中的外层文件夹命名为 `学号_姓名_AI对话行为分析_系统`；正式提交时填写实际信息。仓库没有代填成员姓名、学号或分工。

[↑ 返回导航](#contents)

<a id="research"></a>
## 研究设计与数据管道

我们围绕五个可以由数据回答的问题展开分析：简洁表达能否保留得分？中文模板如何影响数学作答？极端限长为什么出现反弹？证据位置如何影响模型比较？具体执行反馈能否帮助代码修复？

| 实验 | 对照维度 | 原批次物理响应数 |
|---|---|---:|
| 推理与选择题 | 模型 × 题库 × 31 项提示策略 | 74,400 |
| 文档问答 | 模型 × 提示 × 文档数 × 证据位置 | 74,800 |
| 代码生成 | 模型 × 提示 × 5 次独立采样 | 90,210 |
| 文档位置专项 | 固定问题和文档，改变相关证据位置 | 3,600 |
| 历史代码修复 | 模型 × 反馈方式 × 修改轮次 | 5,576 |
| 代码反馈补充 | 164 题 × 2 模型 × 3 份初稿，六种反馈 | 24,600 |

处理流程为：**原始记录备份 → 字段解析与匿名化 → 规则分类与质量检查 → 统一特征 → 指标和配对比较 → 冻结快照 → 交互可视化**。

原始数据保留源字节；缺失评分不填 0；评测环境排除不计为模型错误；共享初稿只计一次；同一问题的重复测量与独立题目数分别解释。详见[数据字典](data/data_dictionary.md)、[分析方法](docs/methodology.md)和[来源与 AI 辅助范围](docs/collection-and-ai-use.md)。

<a id="findings"></a>
## 五项发现与证据

| 课程要求类别 | 发现 | 统计或方法入口 |
|---|---|---|
| 低维发现 1 | 温和简洁表达可在部分条件下保留得分并缩短输出 | [提示策略结果](reports/prompt_variants/) · [图版说明](docs/insight-audit.md) |
| 低维发现 2 | 中文作答模板在 MATH500 上帮助多数受测模型省 Token、提分 | [推理结果](reports/prompt_variants/) · [方法](docs/methodology.md) |
| 多维发现 1 | 模型间的问答优势随证据位置变化 | [文档位置统计](reports/document_positions/) · [专项说明](docs/document_positions.md) |
| 多维发现 2 | 代码修复效果与反馈内容、模型及轮次共同相关 | [补充批次结果](reports/code_repair_extension/) · [分析协议](experiments/code_repair_v2/ANALYSIS.md) |
| 异常 / 局限 | 极端长度约束可能引发输出反弹并损害得分 | [限长统计](reports/prompt_variants/) · [案例报告](report/case_report.pdf) |

每项发现对应具体条件和评分口径。不同任务的评分不合并为“总体准确率”；观察到的关系按实验范围解释，不外推为所有模型、任务或平台上的普遍因果规律。

[↑ 返回导航](#contents)

<a id="data"></a>
## 数据规模与统计口径

| 口径 | 物理响应数 | 说明 |
|---|---:|---|
| 原五项实验 | 248,586 | 原统一表，包含历史 Mini 反馈批次 |
| 完整代码反馈补充批次 | 24,600 | 独立保存，与原统一表分开 |
| 仓库累计 | 273,186 | 上述两批相加 |
| 当前主页面选用 | 267,610 | 248,586 − 5,576 条历史反馈 + 24,600 条补充反馈 |

补充反馈的计数公式为 `164 × 2 × 3 × (1 + 6 × 4) = 24,600`。每模型每策略有 492 份配对程序，独立题目数仍为 164。原统一表不追加或重写为新的页面总数。

主页面读取四份保存的研究快照：[summary.json](app/data/summary.json)、[research-charts.json](app/data/research-charts.json)、[research-content.json](app/data/research-content.json)、[code-feedback-extension.json](app/data/code-feedback-extension.json)。补充统一表位于[补充批次目录](reports/code_repair_extension/code-repair-extension-free-full-20261105-3rep-v2/unified-format/)。模型参数与架构差异见[规格来源](docs/model-spec-sources.md)。

[↑ 返回导航](#contents)

<a id="reproduce"></a>
## 复现分析与图表

**仅运行网站**使用前面的标准库启动命令，不会重新采集或重新评分。

**从匿名特征复算原五项实验**：先按[数据下载说明](data/DOWNLOAD.md#download)取得统一表，再执行：

```bash
python3 scripts/reproduce_anonymous.py
```

输出写入 `reports/reproduced/`。补充批次按其[独立分析说明](experiments/code_repair_v2/ANALYSIS.md)复算，不与原五项实验混计。

**查看完整离线管道**：

```bash
python3 scripts/pipeline.py all --plan
```

需要执行清洗、统计或绘图时，在虚拟环境安装 `requirements/analysis.txt`；报告和 PPT 生成另需 `requirements/documents.txt` 及对应字体。具体阶段、数据依赖和平台限制见[复算说明](docs/reproducibility.md)。采集入口位于 `scripts/acquisition/`，只有明确执行采集操作才会向外部模型发送请求。

[↑ 返回导航](#contents)

<a id="checks"></a>
## 检查与验收

仓库组织、课程交付物和文档链接检查只需要 Python 标准库：

```bash
python3 scripts/system/check_coursework.py
```

安装浏览器检查依赖，然后验证入口、五屏、历史图册与科研保护：

```bash
npm ci --prefix tests
npm run browser:install --prefix tests
python3 tests/check_presentation.py
```

完整科研校验会读取 LFS 保存的原统一表，先执行数据说明中的下载步骤。已有 Chromium 可通过 `CHROMIUM_PATH` 指定。单独检查已启动的页面：

```bash
BASE_URL=http://127.0.0.1:8770/ node tests/browser/zhiwei-gate.mjs
BASE_URL=http://127.0.0.1:8770/ node tests/browser/zhiwei.mjs
```

报告写入 `artifacts/qa/`，不进入版本管理。科研保护清单核对 1,100 项源文件；浏览器检查覆盖五球导航、五屏、七图版、数据表、真实代码案例、响应式、键盘和减少动态效果。详见[测试说明](tests/README.md)。

<a id="delivery"></a>
## 报告、答辩与提交

| 材料 | 入口 | 使用说明 |
|---|---|---|
| 课程要求及验收表 | [guide/](guide/README.md) | 按系统组逐项检查，避免将建议图种误作全部必做项 |
| 案例报告 | [PDF](report/case_report.pdf) · [正文](report/case_report.md) | 10 页，原五项实验的五条发现与证据；当前补充批次另见上面的独立分析说明 |
| 答辩 PPT | [PDF](presentation/defense_slides.pdf) · [讲稿](presentation/defense_slides.md) | 12 页；展示新版系统时以当前页面和数据口径为准 |
| 系统演示路线 | [演示指南](docs/demo-guide.md) | 依次展示问题、数据管道、交互发现、案例和局限 |
| 最终提交检查 | [提交说明](docs/submission.md) | 核对文件夹名称、可运行性、材料和录屏 |

**仍需由小组完成的交付项：** 按课程要求录制 **5–6 分钟、1080P** 的实际系统讲解视频，并填写真实成员信息。仓库不将旧的自动合成幻灯片视频当作已完成的系统演示。视频放在学校指定提交位置，仓库中提供实际提交位置或下载说明即可。

<a id="source"></a>
## 代码地图与维护

| 工作内容 | 修改位置 |
|---|---|
| 五屏结构与材料跳转 | [app/index.html](app/index.html) |
| 五球开场与返回导航 | [zhiwei-gate.js](app/src/zhiwei-gate.js) · [zhiwei-gate.css](app/zhiwei-gate.css) |
| 原生 SVG、模型/题库切换、统计和案例联动 | [zhiwei.js](app/src/zhiwei.js) |
| 景深、字体、布局与响应式 | [zhiwei.css](app/zhiwei.css) |
| 静态构建、公开材料复制与资源版本 | [build_web_app.py](scripts/system/build_web_app.py) |
| 自动检查 | [tests/](tests/README.md) · [课程结构检查](scripts/system/check_coursework.py) |
| 设计、数据、部署等说明 | [文档索引](docs/README.md) |

本次整理移除了重复提交副本、重复要求 PDF、过时的自动视频产物及独立预览分支工作流。科研原始材料、统计证据、许可证和复算实现继续保存；历史版本可从 Git 提交记录查阅。`app/dist/`、`app/runtime/`、测试报告和 `node_modules/` 均为可生成内容。

[↑ 返回导航](#contents)
