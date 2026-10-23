# 4. 离线复现与限制

## 一键顺序重算（从仓库根目录执行）

```bash
git lfs install
git lfs pull
python -m pip install -r experiments/lost-in-the-middle/requirements.txt
python experiments/lost-in-the-middle/src/verify_delivery.py
python experiments/lost-in-the-middle/src/analyze.py
python experiments/lost-in-the-middle/src/plot_results.py
```

命令只读取随仓库保存的输入与原始响应，重算评分和图表，不调用 API、不需要 key，也不依赖 `ccfa-workfiles/` 或其本地依赖缓存。读取 gzip，无需先解压。默认目录由脚本位置确定，从任何工作目录调用都可；可用 `--input`/`--out` 指定其他位置。要保留已提交分析时间，可用 `analyze.py --out /tmp/litm-reanalysis`，然后向绘图脚本传入该目录的 `analysis.json` 和 `scores.csv`。

预计需数分钟，完整回答解压约 891 MB；分析会构建数据表，请预留数 GB 内存。`snapshot_at` 是分析时间，重算会变化；采集时间不变，分组率和固定种子的 bootstrap 结果应一致。

## 文件校验

`data/CHECKSUMS.json` 同时保存压缩文件与解压内容的哈希和字节数。完整回答的解压 SHA-256 是：

```text
5a08b420d18823e22b22bac3dc4ea8db873f441c24f9849267a6a3847fd8d75e
```

`verify_delivery.py` 校验压缩/解压哈希、JSON 行、输入 prompt 哈希、唯一键、全部分组覆盖、标准答案、模型和最终评分行数。`package_final.py --source <原采集目录>` 用于维护者重新打包已结束采集，会重新生成 data 中的最终文件、覆盖表和样例文档；队友日常使用无需运行。

## 来源与历史源码

论文：[Lost in the Middle](https://arxiv.org/abs/2307.03172)。数据和评分来自 [官方仓库](https://github.com/nelson-liu/lost-in-the-middle) 的固定提交 `29b8a6d042ce29abccee3db1a73171a107d7e6af`；原始文件地址/哈希在 `data/dataset_sources.json`。`src/official_metrics.py`、`src/official_evaluate_qa.py`、`src/qa.prompt` 是当次核对保存的上游文件，归原作者所有；`official_evaluate_qa.py` 是上游参考入口，其导入/依赖沿用原仓库，日常复算请使用 `analyze.py`。

`src/experiment.py` 原样保存历史采集实现以便审核评分辅助函数、参数和请求流程。它的运行目录、缓存和 Git 历史依赖属于原采集环境，**不是交付目录的采集启动入口**；`analyze.py` 仅导入其中无副作用的评分函数。此次提供的是已有响应的离线复现，不保证第三方现在重调服务得到逐字相同输出；temperature=0 也不能消除服务端版本与调度差异。

## 统计与语义限制

1. 200 道题是独立统计单位；位置和 31 提示词产生配对观测。95% 区间按题聚类，未做多重比较校正。
2. 只测试两个模型、10/20 篇资料、三个位置；不能推断其他模型、更长上下文或所有位置，也不能复制原论文所有数值。
3. 策略原文加统一 `FINAL ANSWER` 后缀，是任务适配；格式要求可能与简短、列表、中文要求竞争。
4. Qwen3 `enable_thinking=false`；DefaultCoT 只改变可见文字要求，不代表服务端思考模式。
5. 首行、严格最终、最终包含、全文包含各有偏差。尤其中文与压缩拼写还需要单独评分，原始标准答案未擅自改动。
6. 长度比较使用不同官方干扰资料集合；输出长度与准确率散点是关联而非因果。
7. 扩展前 109 条来自初期单 worker，之后为每模型 3 workers；耗时含平台状态变化，不能作受控速度基准。
8. 日志包含重试与截断，成功只指最终接口成功；待复核队列仍需人工处理。

## 版本替换记录

提交 `7f4c7ca` 中保留的是 38,912 条阶段性快照。本次以 gzip 完整数据、`derived/analysis.json` 和六组最终图替换旧快照、旧进度表、旧图及只能在临时目录运行的分析参考文件。旧版可从 Git 历史恢复；本机原始采集目录没有删除。此前“74,800 个场景定义”的表述已修正为“37,400 个场景定义，两个模型共 74,800 次调用”。
