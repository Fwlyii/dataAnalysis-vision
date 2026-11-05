# 设计与第三方来源

## 当前视觉依据

当前视觉方向为用户提供并批准的“知微 · 深海光学玻璃 v5”六张参考图。参考文件位于工作区相邻的 `../style-v5-reference/`：研究问题、数据采集、数据处理、总体规律、任务专项、五条建议。它们决定深海背景、白色中文、青／绿／紫／金玻璃边缘、双层边框和局部折射高光；不作为科研数据或页面截图直接铺进正文。

实现与规范分别位于 `app/research-ocean.css`、`app/research-content-ocean.css`、`app/research-findings-compact.css`、[design.md](design.md) 和 `.impeccable/design.json`。首页与其余四章继续沿用v5方向。

发现页四段构图参考工作区 `outputs/Compact_四屏设计参考_v6/01_总体规律.png`、`02_数学与文档.png`、`03_代码反馈.png`、`04_真实案例.png`。四张参考由内置image_gen生成，完整提示写入PNG元数据，并保存于同目录 `生成说明与提示词.json`。它们仅指导分组、密度与玻璃材质，不属于运行时素材；生成图中的文字、曲线、数值和代码均不作为研究证据。紧凑主线沿用v5背景。

## 运行时装饰素材

| 素材 | 来源与用途 | 来源记录 |
|---|---|---|
| `app/assets/visual/ocean-optics-v5.png` | 本轮通过 image_gen 编辑用户提供的研究问题参考图，移除全部文字、UI、图表、卡片、图标与连接线，生成安静的深海背景；1,436,304字节，仅作装饰 | PNG内嵌生成提示；同目录 `ocean-optics-v5.provenance.json` 保存输入说明、完整提示与用途 |
| `app/assets/visual/gateway-atmosphere.webp` | 先前实际生成的深海背景；现作首页背景加载失败时的后备素材 | [gateway-design.json](provenance/gateway-design.json) |
| `app/assets/visual/planet-question.webp`、`planet-collection.webp`、`planet-cleaning.webp`、`planet-landscape.webp`、`planet-findings.webp` | 原五颗玻璃气泡；继续用于同一首页入口，中央透镜另复用原气泡局部装饰 | [planet-design.json](provenance/planet-design.json) |

原六张WebP包含在1100项科研保护文件中，保持字节不变；来源记录外置于 `docs/provenance/`，不改写原素材元数据。旧来源记录中的生成输入、设计稿和临时路径属于历史迭代，完整版本可从Git提交 `c3d648a` 的 `optimization/` 查阅。

所有标题、导航、提示词、字段表、科学坐标与结论由HTML或SVG绘制。背景素材不承载数据。原37张科学SVG、六张新反馈图与一张历史强测复核图保持冻结版本字节，完整44图仍在独立图册与原图包；来源指纹随已发布 `app/data/code-feedback-extension.json` 保存。紧凑主线的总体、数学、文档和代码图由原生HTML／SVG直接读取冻结目录与发布快照生成，不改评分或统计。四个概览不计为独立图稿，主线导出的原生SVG与原44图另行保存。

## 第三方与历史参考

| 来源 | 使用范围 | 本地许可或记录 |
|---|---|---|
| [Geist](https://github.com/google/fonts/tree/main/ofl/geist) | 本地拉丁与界面数字字体；研究主壳实际加载Regular、Semibold | `app/assets/fonts/Geist-OFL.txt` |
| ECharts、D3、Vega-Lite、Plotly | 独立图册与课程交互图表库的现有能力 | `app/assets/vendor/visualization-libraries.json` 记录版本、校验和与许可 |
| Motion mini 14.9.0 | 保留的旧交互模块依赖；当前五气泡反馈由CSS过渡实现 | `app/assets/vendor/` |
| [AI Design Skills](https://github.com/elayadesign/ai-design-skills) | 历史字体层级、间距、焦点和窄屏检查参考 | MIT；`app/templates/ai-design-skills-LICENSE.txt`；参考版本 `4fdcdd52f15eda09da1257c303c860c13e0c879f` |
| [Relay](https://relay-sage-sigma.vercel.app/) | 历史首屏、稀疏排版与统计节奏参考；当前外观由v5六图决定 | 未引入该站点代码或图片 |
| OpenWAM | 历史研究图形表达参考 | 本项目图形按实际数据生成 |

保留的Scrollama资源用于模板溯源，当前主展示不加载它。字体、依赖与装饰图均从本地读取。历史截图、视频和未采用设计稿不属于网站运行时依赖；紧凑发现的当前视觉复核记录位于 `.impeccable/review/compact-v6/`，其他v5页面记录保留在 `.impeccable/review/final-v5/`。
