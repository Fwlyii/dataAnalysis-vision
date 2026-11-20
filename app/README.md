# 知微可视交互系统

[← 项目首页](../README.md) · [课程对照](../guide/README.md) · [设计说明](../docs/design.md) · [测试](../tests/README.md)

在仓库根目录运行 `python3 app/launch.py --port 8770`，再打开 <http://127.0.0.1:8770/>。网站构建和启动使用 Python 标准库；数据、字体、SVG 和图表库均随项目保存，不需要 API 密钥。

| 入口 | 职责 |
|---|---|
| `index.html` | 五个研究板块、图版、弹窗和课程材料跳转 |
| `zhiwei.css` / `src/zhiwei.js` | 当前景深界面、原生 SVG、模型/指标切换与案例 |
| `zhiwei-gate.css` / `src/zhiwei-gate.js` | 五球开场、进入/返回、键盘和减少动态效果 |
| `data/` | 四份核心研究快照与补充匿名数据 |
| `assets/` | 字体、许可证、科研图稿与本地图表依赖 |
| `legacy.html` / `src/research*.js` | 完整历史图册和补充探索 |
| `explore.html` / `src/app.js` | 图表库、匿名记录与导出 |
| `src/intro.js` / `src/gateway.js` 等 | 补充入口所用的既有前端模块 |
| `runtime/` / `dist/` | 构建生成，忽略且不手动修改 |

修改源码后运行 `python3 scripts/system/build_web_app.py` 或重启 `launch.py`。构建会复制课程 PDF、报告和答辩材料到网站，并为 CSS/JS 生成内容版本，防止浏览器混用旧资源。
