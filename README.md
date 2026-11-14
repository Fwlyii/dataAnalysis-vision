# 知微 · 模型行为研究

当前主展示采用用户确认的 Claude「景深」版本，维护于 [Fwlyii/dataAnalysis-vision 的 Master 分支](https://github.com/Fwlyii/dataAnalysis-vision/tree/Master)。页面按五个板块放映：研究问题 → 实验设计 → 数据处理 → 核心发现 → 结论与反思。核心发现分为三页、七张原生 SVG 图版，保留四个总体主题与数学、文档、代码三个专项。

主界面使用本地 HTML、CSS、JavaScript、字体和冻结 JSON，运行与构建只需 Python 标准库。图形切换、说明、数据表和真实代码案例均在同一系统内完成。

## 启动与构建

在仓库根目录运行：

```bash
python3 app/launch.py --port 8770
```

浏览器打开 `http://127.0.0.1:8770/`。端口占用时改用 `--port 8780`；加 `--no-open` 可只启动服务。独立构建静态网站：

```bash
python3 scripts/system/build_web_app.py
```

产物位于 `app/dist/`，可直接由 HTTP 静态服务提供。页面通过 HTTP 读取四份科研快照；直接双击源码 HTML 不适合作为运行入口。

## 页面与源码

| 内容 | 入口 |
|---|---|
| 五屏结构、导航、图版和弹窗 | `app/index.html` |
| 景深光场、玻璃展板、字体与响应式 | `app/zhiwei.css` |
| 数据读取、SVG、模型/题库切换与放映控制 | `app/src/zhiwei.js` |
| 原37张科研图及真实数值目录 | `app/assets/research/`、`app/data/research-charts.json` |
| 六张补充反馈图与一张历史复核图 | `app/assets/research-extension/` |
| 冻结主快照 | `app/data/summary.json`、`research-content.json`、`code-feedback-extension.json` |
| 原图生成器 | `scripts/figures/build_research_atlas.py` |
| 代码生成简洁对照区间复算 | `scripts/analysis/derive_concise_ci.py` |
| 历史完整图册与探索 | `app/legacy.html`、`app/src/research*.js` |

五屏分别以 `#s1` 至 `#s5` 定位；核心发现的三个页签依次展示总体规律、数学与文档、代码执行反馈。桌面适合整屏放映，手机与矮屏使用自然滚动。浏览器支持时可使用右上角“全屏放映”。

旧 `?chapter=question/collection/cleaning/findings/conclusion` 地址兼容到对应板块。`?chapter=atlas` 转入 `legacy.html?chapter=atlas`，保留原44张独立 SVG、四个完整修复案例、13类通用交互图和4个代码视图；新主界面保持用户确认的导航。

## 研究数据与展示口径

四份核心 JSON 沿用冻结版本：`summary.json`、`research-charts.json`、`research-content.json`、`code-feedback-extension.json`。原始记录、评分和已发布图稿保持独立保存。

| 口径 | 物理响应数 | 保存方式 |
|---|---:|---|
| 原五项实验 | 248,586 | 原统一表，含9,176条专项记录 |
| 完整代码反馈补充批次 | 24,600 | 独立统一表与原始归档 |
| 仓库累计 | 273,186 | 上述两批相加，原表与补充表分别保留 |
| 新主页面选用的五组实验 | 267,610 | 248,586 − 5,576条历史Mini反馈响应 + 24,600条补充响应 |

新代码反馈批次为 `164题 × 2模型 × 3份初稿 ×（1共享初稿 + 6组 × 4次修订）= 24,600份物理响应`。每模型每策略有492份配对程序；独立题目数仍为164。原 `data/processed/all_records.csv.gz` 保持248,586行，补充21列表位于 `reports/code_repair_extension/code-repair-extension-free-full-20261105-3rep-v2/unified-format/`。

MoE 的公开骨干参数与稠密参数按各自来源解释，模型比较保留架构差异。来源与采集端点证据见 [模型规格来源](docs/model-spec-sources.md)。代码反馈的配对分母、公开/保留测试与区间方法见 [补充实验分析说明](experiments/code_repair_v2/ANALYSIS.md)。

## 验证

完整检查会自行构建、启动临时本地服务，并依次验证新版主页面、历史图册与科研保护：

```bash
python3 tests/check_presentation.py
```

安装锁定的浏览器测试依赖，启动本地服务后运行当前主界面套件：

```bash
npm ci --prefix tests
npm run browser:install --prefix tests
BASE_URL=http://127.0.0.1:8770/ node tests/browser/zhiwei.mjs
python3 scripts/system/check_reconstruction.py
```

`CHROMIUM_PATH` 可指定已有浏览器。新主界面报告位于 `artifacts/qa/zhiwei/report.json`，覆盖导航、图版、数据表、模型/题库切换、代码视图、响应式和页面资源。科研检查核对37张原图、图包、真实记录与1,100项保护文件。

历史图册继续使用原界面套件：

```bash
BASE_URL=http://127.0.0.1:8770/legacy.html node tests/browser/defense.mjs
```

`tests/run.py`、旧烟雾检查与历史布局结果保留原验收用途；当前主展示的验证以 `zhiwei.mjs` 为准。测试说明见 [tests/README.md](tests/README.md)。

## 图稿与交付

原37张 SVG 和对应 CSV 保存在 `app/assets/research-svg.zip`，代码反馈七图保存在 `app/assets/research-feedback-svg.zip`。重绘原图：

```bash
python3 scripts/figures/build_research_atlas.py
```

只从匿名聚合结果重绘补充图：

```bash
python3 -m experiments.code_repair_v2.src.analyze \
  --figures-only reports/code_repair_extension/code-repair-extension-free-full-20261105-3rep-v2/app-evidence.json \
  --output /绝对路径/补充图稿
python3 experiments/code_repair_v2/analysis/redraw_legacy.py \
  --report reports/code_repair_extension/legacy-full-recheck \
  --output /绝对路径/历史复核图稿
```

向队友提供网站、模块源码与重绘输入：

```bash
python3 scripts/system/package_reconstruction.py --output /绝对路径/交接目录
```

交付器按白名单附带公开聚合结果和绘图代码，检查发布批次、图稿与来源指纹一致。`app/dist/`、`app/runtime/`、浏览器报告和独立单文件预览属于可生成产物；源码仓库保留一份规范入口。

`submission/` 为历史 LENS 匿名课程提交快照，继续作为历史材料保存。完整复算见 [复算说明](docs/reproducibility.md)，当前内容与接口见 [交接说明](docs/reconstruction-handoff.md)，视觉规范见 [设计说明](docs/design.md)，素材见 [来源说明](docs/design-sources.md)。
