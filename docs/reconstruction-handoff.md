# 知微 · 当前展示与维护接口

主入口采用用户确认的Claude「景深」版本：五屏导航、核心发现三页和七张图版。旧完整图册与探索模块在独立历史入口保留。两种界面读取同一套冻结科研快照。

## 当前结构

| 页面 | 内容 |
|---|---|
| `#s1` 研究问题 | 31策略切片、四模型、三任务及专项关系 |
| `#s2` 实验设计 | 四维策略矩阵、实际指令、五组展示账本和模型名册 |
| `#s3` 数据处理 | 两来源的同义异名字段、映射代码、统一记录与21列结构联动 |
| `#s4` 核心发现 | 总体I–IV、数学/文档V–VI、代码VII三个页签 |
| `#s5` 结论与反思 | 五条使用建议、范围说明和数据伦理 |

核心发现保留Token与边际收益、模型表现、简洁表达、限长反弹四个总体主题，以及数学作答模板、文档证据位置、代码执行反馈三个专项。图表说明和数据表按需展开；代码页可切换两模型、公开诊断/完整测试、六反馈策略与四个补充视图，并查看四个已保存真实案例。

## 源码与接口

| 文件 | 职责 |
|---|---|
| `app/index.html` | 五屏DOM、导航、图版、说明、案例抽屉和数据表弹窗 |
| `app/zhiwei.css` | 当前主界面全部样式、光场、字体、响应式及减少动态规则 |
| `app/src/zhiwei.js` | 读取四份JSON、派生展示值、绘制原生SVG、联动和放映控制 |
| `app/assets/fonts/zhiwei-serif.woff2` | 本地宋体子集；许可沿用 `Noto-CJK-OFL.txt` |
| `app/data/research-charts.json` | 原37图的目录、条件、数值和来源 |
| `app/data/code-feedback-extension.json` | 完整反馈批次、区间、案例和历史复核发布快照 |
| `app/legacy.html`、`app/src/research*.js` | 历史完整图册与探索 |
| `scripts/system/build_web_app.py` | 生成本地运行时、图包和 `app/dist/` |
| `scripts/figures/build_research_atlas.py` | 从冻结统计重绘原37图 |
| `scripts/analysis/derive_concise_ci.py` | 代码生成简洁对照的题簇bootstrap复算 |

主页面使用 `#s1`–`#s5` 定位。旧 `?chapter=question/collection/cleaning/findings/conclusion` 兼容到对应板块；`?chapter=atlas` 转入 `legacy.html?chapter=atlas`。历史图册保留37＋7张SVG、四个完整案例、13类通用图和4个代码视图；主展示维持当前导航。

四份核心JSON与原版逐字节相同。新增代码生成的三个简洁对照区间在脚本中独立复算和记录，固定种子91、按题聚类bootstrap 5,000次；原快照保持冻结。

## 研究口径

主页面选用267,610份物理响应：原248,586份中移出5,576份历史Mini反馈响应，再加入24,600份完整补充反馈响应。原始数据仍全部留在仓库，累计273,186份；原CSV与补充CSV分别保存。

补充反馈计数为：

`164题 × 2模型 × 3份初稿 ×（1共享初稿 + 6策略 × 4次修订）= 24,600份物理响应`

每模型每策略492份程序，独立样本以164个任务簇解释。公开测试负责产生模型可见反馈；完整通过要求公开诊断与保留测试同时通过，保留输入不交给模型。两种评分和各轮轨迹分别呈现。修复与回退采用各自分母，配对区间按题聚类，区间含0的差异按不确定结果解释。

四维是策略标签，31种为实际发送的提示词。中文模板比较保持相同题目；文档位置只连接九个实测位置；缺失字段保留null。模型介绍中的MoE骨干参数与激活参数按公开来源分别标注，原研究快照中的未知值保持冻结。详见仓库 `docs/model-spec-sources.md`。

完整代码反馈的统计与复算入口见 [ANALYSIS.md](../experiments/code_repair_v2/ANALYSIS.md)。

## 修改与核验

布局、材质、动画和SVG样式可继续维护；科研数值、条件、评分、分母、区间和来源由冻结快照及复算脚本确定。保留键盘焦点、数据表读取方式和 `prefers-reduced-motion`。旧图册的筛选、记录和导出继续对应同一集合。

在仓库根目录运行：

```bash
python3 app/launch.py --port 8770
python3 scripts/system/check_reconstruction.py
BASE_URL=http://127.0.0.1:8770/ node tests/browser/zhiwei.mjs
BASE_URL=http://127.0.0.1:8770/legacy.html node tests/browser/defense.mjs
```

首次依赖安装与浏览器路径见 [README](../README.md)。当前主界面报告位于 `artifacts/qa/zhiwei/report.json`；旧 `defense.mjs` 报告对应历史入口。原1,100项保护文件继续核对，保护指纹按原验收版本保留。

交付命令：

```bash
python3 scripts/system/package_reconstruction.py --output /绝对路径/交接目录
```

交付包的 `网站/` 对应仓库 `app/dist/`，包含当前主展示、兼容入口、模块源码、本地资源和冻结快照。`科研源图/`、`代码反馈源图/` 按白名单保存匿名聚合统计及绘图代码；随包重绘器更新SVG和图包。完整采集、原始请求与评测资料继续在研究仓库维护。
