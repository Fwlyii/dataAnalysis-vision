# Lost in the Middle：长上下文资料读取实验

这是 `fwl` 分支上题目 2（交互系统）的资料读取实验交付目录。实验复用了 [Lost in the Middle](https://arxiv.org/html/2307.03172v3) 的 NQ-Open 多文档问答设置，并使用官方仓库固定提交 `29b8a6d042ce29abccee3db1a73171a107d7e6af` 的资料。

## 当前快照

快照时间为北京时间 **2026-10-21 23:17:42**。采集器当时已保存 38,912 条记录；计划总量是 74,800 条。两个模型都已覆盖 200 道基础题，但每道题的全部策略和位置组合尚未完成。后台采集仍在原暂存目录继续，实时进度不覆盖这个可审阅快照。

当前阶段性结论是：前置证据相对中间位置的优势已经出现，Qwen3 的差异最清楚；后置证据相对中间位置的优势尚未稳定。因此可以说复现了“位置会影响读取效果、开头更有利”的核心方向，暂时不能声称两个模型都完整复现了论文的对称 U 形曲线。

## 目录

```text
experiments/lost-in-the-middle/
├── README.md
├── docs/
│   ├── 01-benchmark-and-scenarios.md
│   ├── 02-prompt-strategies.md
│   ├── 03-results-and-outputs.md
│   └── 04-reproduction-and-limitations.md
├── data/                         # 题目、场景、原始输出快照、完整 prompt 示例
├── derived/                      # CSV/JSON 评分表和阶段性分析
├── figures/                      # 已生成图表
└── src/                          # 分析参考代码、官方评分代码、绘图脚本
```

## 三个交付问题对应的位置

1. benchmark、抽题规则、测试场景和真实题目示例：[`docs/01-benchmark-and-scenarios.md`](docs/01-benchmark-and-scenarios.md)
2. ZZY 分支的 31 种 prompt 策略、可测性分类和实际 prompt：[`docs/02-prompt-strategies.md`](docs/02-prompt-strategies.md)
3. 两个免费模型的采集结果、评分、异常、原始输出示例和图表：[`docs/03-results-and-outputs.md`](docs/03-results-and-outputs.md)

复现口径、运行命令、数据限制和快照校验值见 [`docs/04-reproduction-and-limitations.md`](docs/04-reproduction-and-limitations.md)。完整 200 道题在 [`data/questions.json`](data/questions.json)，完整场景输入在 [`data/scenarios.jsonl`](data/scenarios.jsonl)，原始模型响应快照在 [`data/raw_responses_20261021T231742+0800.jsonl`](data/raw_responses_20261021T231742+0800.jsonl)。

## 图表

- [`position_accuracy_interim.png`](figures/position_accuracy_interim.png)：前、中、后位置的官方首行准确率。
- [`strategy_accuracy_interim.png`](figures/strategy_accuracy_interim.png)：主要 prompt 策略的准确率。
- [`output_tokens_accuracy_interim.png`](figures/output_tokens_accuracy_interim.png)：输出长度与准确率的描述性关系。

重新绘图：

```bash
cd experiments/lost-in-the-middle
python src/plot_results.py \
  --input derived/interim_analysis_20261021T231742.json \
  --out figures
```

大文件采用 Git LFS；本次只提交快照，不提交 API key、运行锁、进程号和后台日志。
