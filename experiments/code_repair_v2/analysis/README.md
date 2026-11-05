# 事后复核与聚合图稿重绘

本目录不属于冻结的评测器或反馈协议。下列命令从仓库根目录运行；原始 LFS 记录、oracle 与私有执行日志保存在仓库外的 `../repair_v2/legacy/`，不覆盖旧科研文件。配置仍固定为 `configs/code_repair_extension.json`。

## 只重绘图稿：不需要响应、数据集或模型调用

新补充实验使用已导出的匿名聚合快照：

```bash
python3 -m experiments.code_repair_v2.src.analyze \
  --figures-only /path/to/app-evidence.json \
  --output /path/to/svg-output
```

完整 `results.json` 也支持；匿名交付优先使用 `app-evidence.json`。命令只读取聚合指标并生成实际已有数据对应的 SVG 与 `figure-manifest.json`，不执行候选代码。全五版强测队列存在时生成第六张图，题数保留真实分母。

旧 Mini→Full 图只需要聚合 CSV：

```bash
python3 experiments/code_repair_v2/analysis/redraw_legacy.py \
  --report reports/code_repair_extension/legacy-full-recheck \
  --output /path/to/legacy-svg-output
```

源目录必须含 `legacy-vs-strong-summary.csv`。这两种重绘只用 Python 标准库；保留代码目录结构与仓库根 `project.json` 即可，NumPy不是重绘依赖。图稿可直接在浏览器中打开或导出。

## 完整复核的生成顺序

已有5,576条基础结果与资源overlay时，直接从build_legacy_report.py开始重建报告；不要重新运行基础评测或resolver，否则会产生新执行版本，旧overlay的原记录hash将不再匹配。

下面从空工作目录开始的研究复算需要原始物理候选及固定数据集、已通过预检的 oracle、研究 venv；不会调用模型 API。固定代码和输入经 `legacy_reevaluate.py` 的 SHA 校验后才运行沙箱。

```bash
../repair_v2/venv/bin/python -m experiments.code_repair_v2.src.legacy_reevaluate \
  --config configs/code_repair_extension.json --concurrency 2
# 仅原始5576条里仍有那个已审计的内存未知、且尚无overlay时执行：
../repair_v2/venv/bin/python experiments/code_repair_v2/analysis/resolve_legacy_resource.py
# 以下离线合并不执行候选：
../repair_v2/venv/bin/python experiments/code_repair_v2/analysis/build_legacy_report.py
# 下条用原worker/原Mini/原oracle/原时间公式对4条历史反向候选各复跑2次：
../repair_v2/venv/bin/python experiments/code_repair_v2/analysis/audit_legacy_reversals.py
# 汇总反向审计、题目聚类配对区间和终稿SVG：
../repair_v2/venv/bin/python experiments/code_repair_v2/analysis/finish_legacy_report.py
```

解析器默认输出到新目录 `reports/code_repair_extension/legacy-full-recheck/`。资源未知的原始记录保持不变；独立 overlay 只有在相同预算 canonical 全通过、候选同类资源违规重复出现时，才确认联合任务失败。未执行用例仍未测。已有 overlay 时不重复运行 resolver。

首次运行反向核查前，按保护指针 OID 使用 `git lfs fetch` 只取 object，不 checkout：旧 `evaluations.jsonl` 和 `oracles/HumanEval_{15,83,147}.pkl`。将前者经 OID/size 校验后复制到外部 `legacy/original-evaluations.jsonl`；后者脚本直接从本地 LFS object 按指针 hash 读取。不要修改受保护工作树文件。

报告中的原始执行源码审计副本及哈希保留当次执行版本；本目录是后续复现入口。`reverse-change-audit.json` 只导出 verdict、限时、hash、匿名之外的公开 benchmark 题号，不导出隐藏输入或答案。原失败输入与输出的逐项核对在本地完成。

## 安全导出范围

可交付聚合快照、SVG、manifest、summary/curves/contrasts、逻辑缺失边界、初始错误支持数、强测完整性与执行计账、移除隐藏答案的反向审计，以及本目录重绘源码。匿名网站使用 `app-evidence.json`。

不要打包原 `responses.jsonl`、原执行请求、原 `evaluations.jsonl`、`resource-audit.jsonl`、私有反向复跑日志、oracle pickle、凭证或环境文件。`results.json` 和 `examples.json` 包含原记录键与题号，匿名交付使用快照替代。
