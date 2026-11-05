# LENS 前端

在仓库根目录执行 `python3 app/launch.py --port 8770`，浏览器打开 `http://127.0.0.1:8770`。启动和构建只使用Python标准库；全部科学数据、字体和图表依赖从本地读取。

| 位置 | 内容 |
|---|---|
| `index.html` / `story.css` | 知微之门与五个研究章节 |
| `explore.html` / `styles.css` | 图表库、代码研究与匿名记录 |
| `src/story.js` / `src/story-charts.js` | 研究控制与真实科学SVG |
| `src/narrative.js` | 实验、处理流程和数据全貌 |
| `src/app.js` 及其他模块 | 图表库筛选、图表、记录和导出 |
| `src/intro.js` / `src/gateway.js` | 原创开场、五球交接与导航 |
| `src/interaction.js` / `interaction.css` | 方向卡、实验窗口、流程选择、转场及图表聚焦 |
| `palette.css` / `content-layout.css` | 统一色彩与电脑阅读布局 |
| `assets/` | 当前网站实际使用的图稿、装饰、字体、依赖与许可证 |
| `data/` | 冻结的匿名特征、统计与研究证据 |
| `runtime/` / `dist/` | 构建生成，不直接编辑、不提交 |

修改真实源码后，执行 `python3 scripts/system/build_web_app.py` 或重新启动服务。CSS/JS版本由构建自动更新。自动检查见[tests说明](../tests/README.md)，部署见[GitHub Pages说明](../docs/github-pages.md)。
