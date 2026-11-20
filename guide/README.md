# 课程要求与实现对照

[← 项目首页](../README.md) · [课程 PDF 原文](数据分析和可视化-题目2.pdf) · [提交清单](../docs/submission.md)

本项目选择题目二的 **选项 B：可视交互系统**。以下按老师 PDF 的第 5–8 页整理；建议图种不等于必须逐种实现，结构示例不要求使用特定前端框架。

## 交付结构

| 老师示例 | 仓库实际入口 |
|---|---|
| `README.md` | [运行、研究、数据与验收说明](../README.md) |
| `app/` 可运行系统 | [源码说明](../app/README.md)，启动 `python3 app/launch.py --port 8770` |
| `data/raw/` | [原始材料](../data/raw/)，大文件下载与校验见[数据说明](../data/DOWNLOAD.md) |
| `data/processed/` | [结构化特征与清洗表](../data/processed/) |
| `data/data_dictionary.md` | [字段、来源、单位和缺失规则](../data/data_dictionary.md) |
| `report/案例报告.pdf` | [case_report.pdf](../report/case_report.pdf)，10 页 |
| `presentation/答辩PPT.pdf` | [defense_slides.pdf](../presentation/defense_slides.pdf)，12 页 |

正式提交的外层目录按老师示例填写为 `学号_姓名_AI对话行为分析_系统`。内部 PDF 使用英文文件名，含义与老师示例一致。

## 系统组必要功能

| 要求 | 实现或证据 |
|---|---|
| 明确分析目标 | 输出表达、证据位置、执行反馈与模型表现；见[研究设计](../README.md#research) |
| 至少 2–3 类任务 | 数学/选择题、文档问答、代码生成与修复 |
| 日志解析 → 分类 → 结构化数据 | [清洗实现](../scripts/cleaning/) · [方法说明](../docs/methodology.md) |
| 至少 3 个核心交互视图 | 策略矩阵、质量与开销比较、位置曲线、代码修复轨迹与案例；见[操作入口](../README.md#interaction) |
| 至少一种有效联动 | 策略选择联动指令与条件结果；模型/指标切换联动图表；代码案例联动差异与测试结果 |
| 案例洞察与短报告 | [案例报告](../report/case_report.pdf) · [原统计结果](../reports/) |
| 可运行代码仓库、README 与演示 | 标准库启动；自动验收；最终录屏按下文补齐 |

## 五项结论要求

老师要求至少 **2 条低维发现 + 2 条三维及以上关系 + 1 条异常或局限**。本项目对应为：

1. 低维：温和简洁表达与质量、Token 开销的关系。
2. 低维：中文作答模板与数学任务的得分、截断和开销。
3. 多维：模型 × 证据位置 × 问答命中率。
4. 多维：模型 × 反馈方式 × 修改轮次 × 代码通过率。
5. 异常：极端长度约束下的输出反弹与评分下降。

完整依据见[发现与来源](../README.md#findings)；各结论按对应实验条件解释，不能将相关性泛化为因果。

## 系统组评分表（PDF 第 8 页）

| 项目 | 分值 | 查阅位置 |
|---|---:|---|
| 研究问题与选题 | 8 | [研究设计](../README.md#research) |
| 数据采集与伦理 | 8 | [采集与 AI 使用说明](../docs/collection-and-ai-use.md) |
| 数据清洗与分类 | 15 | [数据字典](../data/data_dictionary.md) · [清洗代码](../scripts/cleaning/) |
| 指标计算与分析 | 15 | [方法](../docs/methodology.md) · [统计结果](../reports/) |
| 可视化质量 | 15 | [系统操作入口](../README.md#interaction) · [设计说明](../docs/design.md) |
| 系统功能与交互 | 20 | [源码](../app/) · [浏览器检查](../tests/README.md) |
| 洞察与案例 | 9 | [案例报告](../report/case_report.pdf) |
| 代码与可复现性 | 5 | [复算步骤](../docs/reproducibility.md) |
| 文档与答辩 | 5 | [PPT](../presentation/defense_slides.pdf) · [演示路线](../docs/demo-guide.md) |
| 合计 | 100 | |

## 小组最终提交事项

- [x] 系统、数据目录、字典、报告及 PPT 均有仓库入口。
- [x] README 给出相对路径、启动、复算与测试说明。
- [x] 大文件注明 Git LFS 获取方法，原始和派生数据分开保存。
- [ ] 填写真实学号、姓名和实际分工。
- [ ] 人工录制并检查 5–6 分钟、1080P 的实际系统演示视频。
- [ ] 在学校指定位置提交成片，并注明下载位置或提交记录。

AI 辅助范围见[说明](../docs/collection-and-ai-use.md)。组员需要能够解释提交的代码、指标与结论。
