# 知微 · 模型行为研究

当前系统维护于 `Fwlyii/dataAnalysis-vision` 的 `Master` 分支。根目录的 `app/` 为最新知微系统；`submission/` 保留历史 LENS 匿名提交快照，未随本次系统更新重新生成。

中文模型行为研究与可视化系统。界面采用用户指定的深海光学玻璃 v5：原五颗玻璃气泡环绕中央“知微”，进入研究问题、采集设计、数据处理、核心发现、总结与反思。正文只保留五章顶导航与品牌返回首页，核心发现以四段连续构图覆盖七个研究主题，桌面约3–4屏；没有页底翻页、左右键跳章或正文跳转按钮。

核心发现采用**四个总体主题＋三个任务专项**：Token与成功率的log关系、模型规模、简洁表达、限长反弹，以及数学语言模板、文档证据位置、代码执行反馈。

发现主线依次展示四个总体概览、数学模板与文档证据位置、双模型六策略代码反馈、两例真实修复／回退。图形由冻结目录与发布快照直接生成原生HTML／SVG，保留实测点、区间、条件及完整代码diff。1440×900下页面高3061px，约3.4屏；手机纵向堆叠，宽图在有名称、可聚焦的局部区域内横向滚动。

**原37张可编辑SVG＋六张新完整反馈图＋一张历史Mini→完整强测复核图**共44张，连同四个完整案例、13类通用交互图和4个代码视图，保留在独立的 `?chapter=atlas` 与原图包，主线不重复44张附图。清洗页仍完整同时展示两来源各四个同义异名字段、四组映射、两条记录的九个关键字段及21列结构。

完整代码反馈补充批次已发布为 `app/data/code-feedback-extension.json`。164道独立题目 × 2模型 × 3份独立初稿，每份初稿进入六条策略链并各修订四次；共享初稿只保存一次，共24,600份物理响应。原248,586份保持分开，其中包含9,176条专项快照；累计273,186份。新批次另存同样21列的 `reports/code_repair_extension/code-repair-extension-free-full-20261105-3rep-v2/unified-format/unified-records.csv.gz`，不修改原 `all_records.csv.gz`。新批次原始归档位于 `data/raw/code_repair_extension/`，不进入网站或交接包。

[研究概述](docs/project-summary.md) · [内容与美化交接](docs/reconstruction-handoff.md) · [设计系统](docs/design.md) · [素材来源](docs/design-sources.md) · [目录说明](docs/repository-structure.md) · [录制指南](docs/submission.md)

## 启动

在仓库根目录运行：

```bash
python3 app/launch.py --port 8770
```

浏览器打开 `http://127.0.0.1:8770`。运行与构建只用Python标准库，使用已保存的匿名网页快照，不需要npm、模型密钥或常驻后端。请通过本地HTTP服务打开，避免直接双击HTML。

## 图表与静态构建

```bash
# 从冻结统计生成原37张SVG和图表目录（呈现层深海配色）
python3 scripts/figures/build_research_atlas.py

# 打包主系统、探索模块、快照及SVG/CSV图包
python3 scripts/system/build_web_app.py

# 检查图包、真实记录与1100项科研文件保护
python3 scripts/system/check_reconstruction.py
```

- `app/assets/research/*.svg`：可编辑科学图。
- `app/data/research-charts.json`：图表主题、条件、来源与数值。
- `app/assets/research-svg.zip`：完整SVG图包及各图CSV。
- `app/assets/research-feedback-svg.zip`：已发布的七张代码反馈补充图包，与原37张图包分开。
- `app/dist/`：生成后的静态网站，可由HTTP静态服务提供。

补充图可只用匿名聚合结果重绘，不需要模型密钥、原始请求、数据集或oracle：

```bash
python3 -m experiments.code_repair_v2.src.analyze \
  --figures-only reports/code_repair_extension/code-repair-extension-free-full-20261105-3rep-v2/app-evidence.json \
  --output /绝对路径/补充图稿

python3 experiments/code_repair_v2/analysis/redraw_legacy.py \
  --report reports/code_repair_extension/legacy-full-recheck \
  --output /绝对路径/历史复核图稿
```

这两个命令只重绘已有统计，不重新采集或评测。完整研究复算、配对分母和公开／保留测试规则见[补充实验分析说明](experiments/code_repair_v2/ANALYSIS.md)。

## 浏览器回归

先启动上面的本地服务，在另一个终端运行：

```bash
npm ci --prefix tests
npm run browser:install --prefix tests
BASE_URL=http://127.0.0.1:8770/ node tests/browser/defense.mjs
```

已有Chrome等浏览器时，可用 `CHROMIUM_PATH` 指定其可执行文件。当前74项回归检查全部通过，覆盖五气泡首页、五章路径、四段发现构图与七主题证据、真实数学／文档／代码区间及案例谱系、图册44图与完整案例、四个断点和可访问性；结果写入 `artifacts/qa/defense/report.json`。紧凑发现的视觉复核与测量位于 `.impeccable/review/compact-v6/`，其余v5页面的背景对比度记录保留在 `.impeccable/review/final-v5/`。

`tests/run.py`和 `tests/browser/reconstruction.mjs` 保留此前界面的基线，不代表当前精简后的控件数量，不能替代上述回归。

## 源码入口

| 内容 | 入口 |
|---|---|
| 主页面、路由、主题图册 | `app/index.html`、`app/src/research.js`、`app/research.css` |
| v5深海外观与原生概览 | `app/research-ocean.css`、`app/research-content-ocean.css`、`app/src/research-ocean-summary.js` |
| 四段紧凑发现主线 | `app/src/research-findings-compact.js`、`app/research-findings-compact.css` |
| 五气泡首页 | `app/src/research-home.js`、`app/research-home.css` |
| 中文章节、策略与清洗演示 | `app/src/research-content.js`、`app/research-content.css` |
| 通用图表、代码生成探索 | `app/src/research-explorer.js`、`app/research-explorer.css` |
| 位置与反馈专项记录 | `app/src/research-special-records.js`、`app/data/special-records.json.gz` |
| SVG生成与目录 | `scripts/figures/build_research_atlas.py`、`app/data/research-charts.json` |
| 代码反馈紧凑主线与完整图册 | `app/src/research-feedback-extension.js`、`app/research-feedback-extension.css` |
| 补充实验统计与重绘 | `experiments/code_repair_v2/src/analyze.py`、`experiments/code_repair_v2/analysis/` |
| 冻结数据、清洗、统计 | `data/`、`scripts/cleaning/`、`scripts/analysis/`、`reports/` |
| 参考报告与答辩材料 | `report/`、`presentation/` |
| 设计规范与光学素材来源 | `docs/design.md`、`.impeccable/design.json`、`app/assets/visual/ocean-optics-v5.provenance.json` |

`app/dist/`、`app/runtime/`和`artifacts/`为生成或临时目录。后续页面切换、动效与布局的修改边界见[交接说明](docs/reconstruction-handoff.md)。

向队友提供可运行网站及图稿源文件，可运行 `python3 scripts/system/package_reconstruction.py --output /绝对路径/交接目录`。它保留网页模块源码、离线数据、SVG生成器与冻结统计，并附独立启动器；目标目录已存在时会停止，避免覆盖队友修改。

若构建网站已发布完整补充批次，打包器会额外附上 `知微代码反馈SVG图包.zip`、匿名聚合结果和独立重绘代码；没有已发布快照时，交付包保持原37张版本。默认按网站的批次标识寻找 `reports/code_repair_extension/<batch_id>/`，也可用 `--extension-report /绝对路径/聚合报告目录` 指定同一批次。快照、图稿与构建结果不一致或评测不完整时停止打包。交付不包含模型凭证、原始HTTP请求、逐程序评测或隐藏测试答案。

## 数据复算与课程演示

完整分析表通过Git LFS管理。要重算统一匿名表的条件汇总，先取回该表：

```bash
git lfs install --local
git lfs pull --include='data/processed/all_records.csv.gz' --exclude=''
python3 scripts/reproduce_anonymous.py
```

完整离线流程见[复算说明](docs/reproducibility.md)。网页浏览不要求下载完整问答全文。专项网页快照可用 `python3 scripts/system/export_special_records.py` 从已取回的统一表更新。

报告与PPT作为参考，最终演示视频由人工录制并提交；不在仓库保存成片。系统、演讲稿、报告和PPT应使用同一套图形、数据范围与结论。
