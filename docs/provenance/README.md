# 运行时素材来源

当前网站使用一个新v5背景和原五颗玻璃气泡；旧背景保留为首页加载失败时的后备。所有素材只承担装饰，研究文字、表格、坐标与数据由原生HTML／SVG呈现。

| 运行时素材 | 来源记录 | 当前用途 |
|---|---|---|
| `app/assets/visual/ocean-optics-v5.png` | `app/assets/visual/ocean-optics-v5.provenance.json`，另有PNG内嵌提示 | 本轮image_gen从用户提供的v5参考图编辑出纯背景，移除全部文字、界面与图表 |
| `app/assets/visual/gateway-atmosphere.webp` | [gateway-design.json](gateway-design.json) | 原生成背景，保留作后备 |
| `app/assets/visual/planet-question.webp` | [planet-design.json](planet-design.json) | 研究问题气泡与中央透镜局部装饰 |
| `app/assets/visual/planet-collection.webp` | 同上 | 采集设计气泡 |
| `app/assets/visual/planet-cleaning.webp` | 同上 | 数据处理气泡 |
| `app/assets/visual/planet-landscape.webp` | 同上 | 核心发现气泡 |
| `app/assets/visual/planet-findings.webp` | 同上 | 总结与反思气泡 |

v5方向来自用户提供的“知微_ImageGen深海光学玻璃风_v5_六张.zip”；工作区参考副本在相邻 `../style-v5-reference/`。新背景为1,436,304字节PNG，侧车保留输入参考、完整生成提示、日期和用途，不把参考图中的文字或科学图像复用为研究证据。

原背景与五颗气泡共六张WebP包含在1100项科研保护文件中，保持原字节。旧生成记录中的输入截图、设计稿和临时路径属于历史迭代，完整内容可从Git提交 `c3d648a` 的 `optimization/` 查阅；本工作区不依赖这些历史大文件。来源记录外置，原素材元数据不改写。

实际网页使用的字体、图标、第三方脚本及许可证位于 `app/assets/`；库版本与校验和见 `app/assets/vendor/visualization-libraries.json`。科学SVG来源与数值目录分别位于 `app/data/research-charts.json`、`app/data/code-feedback-extension.json`，与装饰图来源记录分开。
