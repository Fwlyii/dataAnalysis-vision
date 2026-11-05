# 知微 · 深海光学玻璃 v5 交接

当前展示依据用户提供的六张 v5 参考图，采用深海背景、白色中文与青／绿／紫／金双层玻璃边缘。首页保留原五颗玻璃气泡，中央可见“知微”；五颗入口依次进入研究问题、采集设计、数据处理、核心发现、总结与反思。正文只保留五章顶导航与品牌返回首页，没有页底翻页、左右键跳章、跨章推荐或跳转 CTA。

设计 token、组件与响应式约束见 [design.md](design.md)，扩展阴影、动效和可独立预览的组件见 [.impeccable/design.json](../.impeccable/design.json)。素材来源见 [design-sources.md](design-sources.md)。

## 展示结构

- 研究问题：一个真实 h1 总问题，经静态连接线分到数学、文档、代码三张任务仪器；三组实际案例同时展示。
- 采集设计：四维面板、五项原实验的真实物理响应账本与完整31种提示词；末尾单独说明已发布的代码反馈补充批次。
- 数据处理：一个静态 Figure。A 两来源各四个同义异名字段，以珊瑚色全部标记；B 四组映射与规则；C 两条实际保存记录的九个关键字段；D 完整21列结构与保存原则。各部分同时出现，没有选择、折叠或步骤切换。
- 核心发现：四段连续构图覆盖四总体与三任务，1440×900下高3061px，约3.4屏。第一段为四个总体概览；第二段为数学四模型八柱及四个Token变化、文档九个真实位置的18点与95%区间；第三段为两模型六策略的12个终稿端点、模型间差异与Token成本；第四段为语义修复和隐蔽回退两例，展示实际反馈摘录及完整diff。
- 总结与反思：五条有证据的建议与适用范围；仅两种接近的已知参数规模不足以建立 Scaling Law，另外两模型的未知规模仍为未知。

发现主线不设固定屏高、不裁剪正文；数学与文档在1100px以下改为上下排列，代码案例在640px以下堆叠。手机宽图使用有名称、可聚焦的局部横向滚动区域，页面不得横向溢出。原44张独立SVG、四个完整前后代码／反馈案例和13＋4交互视图保留在 `?chapter=atlas` 与原图包，主线不重复全部附图。

## 文件与接口

| 内容 | 文件 |
|---|---|
| 首页五气泡与中央知微 | `app/src/research-home.js`、`app/research-home.css` |
| 主壳、五章路由与独立图册 | `app/index.html`、`app/src/research.js`、`app/research.css` |
| 四段紧凑发现主线 | `app/src/research-findings-compact.js`、`app/research-findings-compact.css` |
| v5外观覆盖层 | `app/research-ocean.css`、`app/research-content-ocean.css` |
| 四个真实数值概览 | `app/src/research-ocean-summary.js` |
| 三任务、31策略、清洗与总结 | `app/src/research-content.js`、`app/research-content.css` |
| 原37张科学图与目录 | `app/assets/research/`、`app/data/research-charts.json` |
| 原图生成器与呈现配色 | `scripts/figures/build_research_atlas.py` 的 `PALETTE` |
| 保留的完整探索 | `app/src/research-explorer.js`、`app/research-explorer.css` |
| 专项匿名记录能力与快照 | `app/src/research-special-records.js`、`app/data/special-records.json.gz` |
| 补充批次紧凑主线与完整图册 | `app/src/research-feedback-extension.js`、`app/research-feedback-extension.css` |
| 已发布补充快照与七图 | `app/data/code-feedback-extension.json`、`app/assets/research-extension/` |
| 两个独立图包 | `app/assets/research-svg.zip`、`app/assets/research-feedback-svg.zip` |
| 新批与历史重绘器 | `experiments/code_repair_v2/src/analyze.py`、`experiments/code_repair_v2/analysis/redraw_legacy.py` |
| 新批统一21列表与谱系 | `reports/code_repair_extension/code-repair-extension-free-full-20261105-3rep-v2/unified-format/` |
| v5背景与来源侧车 | `app/assets/visual/ocean-optics-v5.png`、同目录 `ocean-optics-v5.provenance.json` |

`renderHome()` 返回首页HTML；`mountHome(container,{onNavigate})` 返回清理函数。首页方向键只在五颗气泡之间移动焦点，正文没有方向键跳章。内容模块保留 `renderQuestion()`、`renderCollection()`、`renderCleaning()`、`renderConclusion()` 与 `bindContent(container,callbacks)`；问题与清洗的旧参数保留兼容，但现有输出为同时展示的静态内容。路由离开时先释放事件。

`renderCompactFindings(catalog,publication)` 生成四段发现主线，直接读取冻结图表目录与已发布反馈快照。它调用 `renderOceanOverview(catalog,feedbackPublished,{includeTasks:false,markTopics:true})` 绘制四个总体概览，再生成数学与文档图；不要另录科学数值。

`renderFeedbackCompact(evidence,figures,legacyEvidence?,{prefix?})` 生成代码端点图、模型差异和两例机制案例。两模型共用明确标示的60–100%截取横轴，全部初稿、终稿和95%区间须在轴内；此图以点和区间编码，不使用从截取起点算长的柱。案例反馈为已保存字段的明确标注摘录，完整diff保留；完整反馈与前后代码继续由图册提供。

`renderFeedbackExtension(evidence,figures,legacyEvidence?,{prefix?})` 保留完整静态HTML，供独立图册使用。新批 `figures` 为目录数组，历史数据为 `{checks,summary,figures?}`；默认路径 `assets/research-extension/`，历史图在 `legacy/` 子目录。仅真实且完整的快照可展示，代码与反馈按文本转义。`build_web_app.py` 在验证已发布快照后给构建页写入 `code-feedback-extension` meta，主壳读取该接口。

图稿资源页经 `?chapter=atlas` 直接访问，保留逐图SVG／CSV、完整图包、13类通用交互图与4个代码视图；主答辩页面不摆该入口。保留匿名记录模块不表示主线需要增加控件。

## 科研口径

原实验为248,586条物理响应，9,176条专项记录已在其中。新批独立归档，不改原 `all_records.csv.gz`：

`164题 × 2模型 × 3独立初稿 × (1共享初稿 + 6策略 × 4次修订) = 24,600条物理响应`

六条策略的逻辑轨迹复用同一初稿，不能按六条链分别重复计入初稿。独立题目仍为164个任务簇，每模型每策略有492份配对程序；累计物理响应273,186条不是独立题目数。补充统一表保存24,600行、21列，初稿编号另在 `lineage.csv` 中保留；原表与补充表不拼接覆盖。

完整发布快照中，单反例相对自行检查：Qwen3终稿强测84.96%对76.42%，差8.54个百分点，95%配对区间[4.88,12.60]；Qwen2.5为81.50%对79.67%，差1.83个百分点，区间[-0.20,4.07]。多反例相对单反例在两模型中的区间都包含0。后续表述须按模型区分，不能把区间含0的差异写成稳定提升。

- 四维是策略标签，31种是实际提示词，不是完整笛卡尔组合。
- 源字段片段按真实清洗代码重建所需视图，数值来自同条已保存记录，不冒充原API全文。
- 统一保存为gzip压缩CSV；不适用字段保留null，不混合任务评分，不把未知参数规模填0。
- 独立生成、反馈修订和HTTP重试分别计数；共享初稿只计一次。
- 公开测试负责反馈，完整保留测试结果不交给模型；公开五版曲线与离线强测五版曲线分开呈现。
- 强测轨迹使用全部模型、重复、策略、版本均完成强测的共同题目；子队列须写明分母。
- 95%配对区间按题目分簇；初错修复与初对回退使用各自分母，按模型报告。
- 历史Mini复核只重新执行保存代码，不重新生成；原Mini评分与完整强测分别呈现，不把环境差异全归因于更多测试。

完整研究复算、配对分母及测试规则见 [ANALYSIS.md](../experiments/code_repair_v2/ANALYSIS.md)。新批原始归档位于 `data/raw/code_repair_extension/`，仅供研究复算，不进入网页或课程交接包。

## 可修改边界

可调整光学配色、组件间距、页面转场和入口反馈；动效须支持减少动态偏好。背景与边缘反光不得在阅读文字后持续运动。发现页在桌面与手机均使用下部渐深遮罩，其他章节保留原v5手机遮罩；修改背景需重新检查自由段落对比度。

科研图的修改限于呈现层：原37张图的配色由生成器 `PALETTE` 控制，新批与历史重绘器也有呈现配色；不得移动实测点、改坐标范围或删单位、条件、来源、点线形状和必要标注。冻结数据、评分、分母、统计方法与置信区间须保持研究口径。原六张WebP素材包含在1100项原始科研保护文件中，来源记录外置保存，不改写旧素材元数据。

## 运行与核验

在仓库根目录执行：

```bash
python3 app/launch.py --port 8770
python3 scripts/system/check_reconstruction.py
BASE_URL=http://127.0.0.1:8770/ node tests/browser/defense.mjs
```

首次浏览器测试依赖安装见 [README](../README.md)。构建使用 `python3 scripts/system/build_web_app.py`。当前浏览器74项检查全部通过，四个断点的可访问性检查均无问题，原1100项科研保护文件保持一致；报告写入 `artifacts/qa/defense/report.json`。紧凑发现测量与视觉复核位于 `.impeccable/review/compact-v6/`，其中 `detector.json` 的布局检查结果为空。其他v5页面的对比度记录保留在 `.impeccable/review/final-v5/`。

交接包用 `python3 scripts/system/package_reconstruction.py --output /绝对路径/交接目录` 生成，目标目录已存在时停止。默认从 `reports/code_repair_extension/<batch_id>/` 读取同批聚合报告，也可用 `--extension-report` 指定。快照、图稿、来源指纹或完整性不一致时停止打包。

原图包输出 `知微科研SVG图包.zip`，补充图包输出 `知微代码反馈SVG图包.zip`。包内 `代码反馈源图/` 仅按白名单保存匿名聚合结果、公开CSV、复核摘要与重绘代码，不复制原始请求、逐程序评测、oracle、隐藏测试答案或凭证。网页及源码保留v5 CSS覆盖层、紧凑发现模块、原生概览模块与背景来源侧车。

在交接包内执行 `python3 重建代码反馈图.py`，可从冻结聚合结果更新六张新图、一张历史复核图及补充ZIP。只重绘不采集、不评测；调整样本、指标或统计须回原仓库核验并重新发布快照。独立重绘命令见 [README](../README.md)。
