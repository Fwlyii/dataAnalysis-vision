# 案例报告

[← 项目首页](../README.md#delivery) · [课程要求](../guide/README.md) · [答辩材料](../presentation/README.md)

- [案例报告 PDF](case_report.pdf)：10 页，原五项实验中的两条低维、两条多维与一条异常发现。
- [报告正文](case_report.md)：便于查阅与修改的文字内容。
- [生成校验](current_documents.json)：对应两份文档的来源范围与 SHA-256。

报告的原批次为 248,586 条响应。新版主页面另使用完整代码反馈补充批次，页面选用总数为 267,610；不能把两者误认为同一个统计口径。补充批次见[分析协议](../experiments/code_repair_v2/ANALYSIS.md)和[结果](../reports/code_repair_extension/)。

重绘命令为 `python3 scripts/delivery/build_course_documents.py`，需要 `requirements/documents.txt`、绘图库及相应字体。供核查的 CSV/JSON/SVG 位于 [reports/](../reports/)，与本目录的阅读版报告分开存放。
