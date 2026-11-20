# 复算与可复现性

[← 项目首页](../README.md#reproduce) · [数据下载](../data/DOWNLOAD.md#download) · [测试](../tests/README.md)

## 只运行网站

```bash
python3 app/launch.py --port 8770
```

Python 3.10 及以上的标准库即可。构建读取保存的 JSON/SVG，不需要模型密钥或 npm，也不会调用模型或执行模型生成的程序。

## 从匿名数值重算原五项实验

先取得 Git LFS 对象 `data/processed/all_records.csv.gz`，再运行：

```bash
python3 scripts/reproduce_anonymous.py
```

此步骤使用标准库，读取原 248,586 行匿名特征并重新计算条件汇总，输出 `reports/reproduced/condition_summary.csv` 与 `summary.json`。任务原评分分别保留，缺失值不补 0，共享初稿不重复计数。

匿名数值不能恢复对话全文、重新做语义判定或重新生成模型回答。完整补充批次有独立的[分析协议](../experiments/code_repair_v2/ANALYSIS.md)与[统计结果](../reports/code_repair_extension/)，不并入原统一表。

## 完整离线管道

建议使用 Python 3.12 虚拟环境：

```bash
python3 -m venv .venv
```

激活虚拟环境后安装 `requirements/analysis.txt`；需要生成报告和 PPT 时另安装 `requirements/documents.txt`。字体与平台依赖以对应生成脚本为准，中文字体可通过 `COURSE_CJK_FONT_FILE` 指定。先查看执行计划：

```bash
python3 scripts/pipeline.py all --plan
```

| 阶段 | 功能与前提 |
|---|---|
| `clean` | 校验原始制品、解析和清洗；需要对应方向的完整 LFS 原始材料 |
| `analyze` | 保留源评分，做按题配对比较与各专项分析；需要清洗结果和分析依赖 |
| `figures` | 重绘科研图；需要统计输入、绘图库及合法字体 |
| `web` | 从保存快照构建 `app/dist/`；仅需标准库 |
| `documents` | 重绘原五项实验的 10 页报告和 12 页答辩 PDF；需要文档依赖与字体 |

例如 `python3 scripts/pipeline.py web` 只构建网站。根目录已按课程结构交付，不再通过管道生成另一份旧 `submission/` 副本。

## 科研文件与评分校验

```bash
python3 scripts/system/check_coursework.py
python3 scripts/system/build_web_app.py
python3 scripts/system/check_reconstruction.py
```

第一项核对课程材料和文档链接；第二项生成图包和网站；第三项核对 37 张原图、图包内容、原统一表行数与 1,100 个受保护文件。完整浏览器验证使用 `python3 tests/check_presentation.py`。

## 重新采集与重新评分

采集脚本位于 `scripts/acquisition/`，默认计划或干跑，仅明确执行采集时才向模型接口发送请求。代码生成重测需要原 CodePromptEval 项目环境；历史代码修复采集/执行依赖原平台沙箱。日常复现使用保存评分，不把新请求当作旧实验的精确重放。
