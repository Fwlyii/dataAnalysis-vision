# 长上下文资料读取实验：最终数据交付

本目录是 `fwl` 分支中题目 2 的资料读取实验。使用 Lost in the Middle 的 NQ-Open 多文档问答数据，把 ZZY 分支的 31 种提示词迁移到资料读取任务，比较资料位置、资料数量、提示词和模型对答题结果的影响。

## 完成状态与规模

采集于 **2026-10-22 20:21:16（北京时间）**结束，全部 **74,800 / 74,800** 条已保存。两个模型分别完成 37,400 条，374 个实验分组各有 200 条；请求输入哈希、返回模型 ID、标签和唯一键核验通过，详见 [`derived/verification.json`](derived/verification.json)。接口成功不等于回答正确，自动评分完成也不代表人工语义复核完成。

| 项目 | 数量或设置 |
|---|---|
| 基础题 | 200 道独立问题；种子 91 抽样 |
| benchmark | 官方 NQ-Open，多文档问答 |
| 资料数量 | 10 篇、20 篇 |
| 正确资料位置 | 前、中、后；1/5/10 或 1/10/20 |
| 提示词 | ZZY 的全部 31 种；每模型、每策略 1,200 次主实验 |
| 模型 | `Qwen/Qwen2.5-7B-Instruct`、`Qwen/Qwen3-8B`；采集时免费，价格留档见 data |
| 场景定义 | 37,200 个主实验设置 + 200 个无资料对照，两个模型共用 |
| 实际回答 | 主实验 74,400 + 对照 400 = 74,800 条 |

每次都是独立单轮请求；没有多轮纠错或外部搜索工具。模型只读取已提供的检索资料，因此本实验衡量的是资料读取与利用，而非实时互联网检索能力。

## 最终结论

按论文官方首行答案包含指标，汇总 19 个英文主比较策略、10/20 篇资料后：

| 模型 | 前置准确率 | 中间准确率 | 后置准确率 | 前 − 中，95% CI | 后 − 中，95% CI |
|---|---:|---:|---:|---:|---:|
| Qwen2.5 | 58.11% | 54.62% | 56.09% | +3.49 pp [0.80, 6.26] | +1.47 pp [-0.62, 3.71] |
| Qwen3 | 67.84% | 60.70% | 59.46% | +7.14 pp [4.71, 9.72] | -1.24 pp [-3.07, 0.61] |

**结论：部分复现位置效应，前置优势较明确；没有在两个模型上稳定复现完整的 U 形。** 不应写成“所有提示词下都中间最差”或“完整复现原论文”。

其他观察：10 篇相对 20 篇的官方首行准确率，Qwen2.5 高 2.26 pp，Qwen3 高 1.74 pp；要求分步骤明显增加输出，但最终答案包含评分的提升区间均跨 0，不能说越长越准；Qwen3 的 NoProperGrammar 有 424/1,200 条截断（35.33%），Qwen2.5 同组为 0/1,200。评分口径、分组差异和异常解释见结果文档。

pp 为百分点。上述位置比较每项有 7,600 对、200 道独立题；区间为按 question_id 聚类重采样 5,000 次、种子 91 的探索性 95% 区间，未做多重比较校正。

## 从哪里开始看

1. [`docs/01-benchmark-and-scenarios.md`](docs/01-benchmark-and-scenarios.md)：用什么 bench、抽多少题、三个题目示例。
2. [`docs/02-prompt-strategies.md`](docs/02-prompt-strategies.md)：ZZY 提示词可测性分类、具体输入、统一格式与限制。
3. [`docs/03-results-and-outputs.md`](docs/03-results-and-outputs.md)：完整结果、论文对照、CoT 和评分差异、作业要求映射。
4. [`docs/04-reproduction-and-limitations.md`](docs/04-reproduction-and-limitations.md)：无需 key 的离线复算、文件校验和数据局限。
5. [`docs/05-output-examples.md`](docs/05-output-examples.md)：三道题 × 三策略 × 两模型的 18 条完整真实输出。
6. [`figures/README.md`](figures/README.md)：六组最终图的用途、变量编码、来源表和统计口径。

## 整洁目录与数据入口

```text
data/       # 官方题目、提示词、37,400 个场景、74,800 条原始回答、请求尝试日志、校验值
derived/    # 最终评分、配对分析、分组覆盖、采集器原始评分和复核队列
docs/       # 实验说明、结论、限制、18 条完整输出
figures/    # 六组 PNG/SVG/PDF；source_data/ 保存每张图的数值
src/        # 可直接运行的离线分析/绘图/打包脚本和历史采集源码
```

详细字段见 [`data/data_dictionary.tsv`](data/data_dictionary.tsv)；文件列表见 [`data/README.md`](data/README.md) 和 [`derived/README.md`](derived/README.md)。历史阶段性文件已由最终版替换；旧版仍可通过提交 `7f4c7ca` 查看。原始 `ccfa-workfiles/` 留在本机，被 Git 忽略。

## 下载与重算

在仓库根目录运行：

```bash
git lfs install
git lfs pull
python -m pip install -r experiments/lost-in-the-middle/requirements.txt
python experiments/lost-in-the-middle/src/verify_delivery.py
python experiments/lost-in-the-middle/src/analyze.py
python experiments/lost-in-the-middle/src/plot_results.py
```

无需 API key，不会再次调用模型。原始回答和场景采用 gzip 无损压缩与 Git LFS；`CHECKSUMS.json` 同时记录压缩文件与解压内容的 SHA-256。`scores.csv` 包含全部 74,800 条最终离线评分；图只按明确的策略分类取子集，未删除格式压力、中文或截断记录。

## 来源与版本记录

- [Lost in the Middle 论文](https://arxiv.org/abs/2307.03172)；[官方仓库](https://github.com/nelson-liu/lost-in-the-middle)，固定提交 `29b8a6d042ce29abccee3db1a73171a107d7e6af`。
- ZZY 参考提交 `4133f88dfe9a9604a2e33098feeb32e8147024b3`；`fwl` 基于 main 的 `d6dc8fe`，未合并 ZZY 数学实验提交。
- `7f4c7ca` 为首次阶段性交付（38,912 条）；本次更新为完整采集和最终自动分析，不沿用旧版进度与异常样本分母。
