# 设计与第三方来源

## 当前主展示

当前主展示来自用户于2026-11-15提供并确认的 `知微可视化系统-完整版.zip`。仓库保留可编辑的 `app/index.html`、`app/zhiwei.css` 和 `app/src/zhiwei.js`，按既有构建流程生成静态网站。附件的内嵌单文件预览和压缩资源副本属于交付产物，规范源码继续复用仓库中的冻结快照与本地资产。

视觉母题为“景深”：CSS光场、刻度环、磨砂玻璃展板与前景取景框。主界面的标题、数据和图形使用HTML及原生SVG，光场使用CSS与装饰SVG；实现细节见 [设计说明](design.md)。

| 来源 | 当前用途 | 许可/记录 |
|---|---|---|
| 用户确认的Claude页面 | 五屏版式、景深样式、原生SVG及交互 | `app/index.html`、`app/zhiwei.css`、`app/src/zhiwei.js` |
| 思源宋体子集 | 标题，`app/assets/fonts/zhiwei-serif.woff2` | SIL OFL 1.1；`app/assets/fonts/Noto-CJK-OFL.txt` |
| [Geist](https://github.com/google/fonts/tree/main/ofl/geist) | 本地拉丁字体与界面数字 | `app/assets/fonts/Geist-OFL.txt` |
| 冻结科研快照 | 全部主图和关键数字 | `app/data/summary.json`、`research-charts.json`、`research-content.json`、`code-feedback-extension.json` |

模型公开规格与采集端点的对应证据由仓库 `docs/model-spec-sources.md` 记录。MoE骨干参数、激活参数和稠密参数保留各自来源口径。

## 科研图稿

原37张科学SVG、六张完整反馈图和一张历史强测复核图继续保留在原资产目录与两个SVG/CSV图包中。当前主展示的原生SVG直接读取相同快照；已发布图稿的数值和来源指纹保持冻结。图稿重绘代码及统计说明见 [交接说明](reconstruction-handoff.md)。

## 历史素材与兼容图册

以下资产继续支持 `app/legacy.html` 的历史图册与研究模块；原来源记录保持原样。

| 素材/依赖 | 用途 | 记录 |
|---|---|---|
| `app/assets/visual/ocean-optics-v5.png` | 历史深海光学玻璃v5背景，由image_gen编辑用户参考图生成 | 同目录 `ocean-optics-v5.provenance.json` 与PNG元数据 |
| `gateway-atmosphere.webp` | 历史背景与后备装饰 | [gateway-design.json](provenance/gateway-design.json) |
| `planet-question.webp`、`planet-collection.webp`、`planet-cleaning.webp`、`planet-landscape.webp`、`planet-findings.webp` | 历史五气泡入口与透镜装饰 | [planet-design.json](provenance/planet-design.json) |
| ECharts、D3、Vega-Lite、Plotly | 完整旧图册与课程交互视图 | `app/assets/vendor/visualization-libraries.json` 及同目录许可证 |
| Motion mini 14.9.0 | 历史交互模块 | `app/assets/vendor/` |
| [AI Design Skills](https://github.com/elayadesign/ai-design-skills) | 历史字体、间距和焦点参考 | MIT；`app/templates/ai-design-skills-LICENSE.txt` |

上述旧素材和实现中纳入1,100项保护清单的文件保持原字节。原始设计稿、录屏和临时优化产物可从Git历史查阅，不作为主页面运行依赖。
