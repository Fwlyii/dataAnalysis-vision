# 不同模型与Prompt解决Python代码问题的能力差异

本目录是代码生成方向的完整实验交付，研究问题是：**不同大模型在31种提示策略下解决Python函数级任务的正确率、重复采样收益和错误原因有何差异。**

## 1. Benchmark与实验规模

实验使用CodePromptEval的Python任务。原始221题经参考实现实跑与语义审计后，保留194题，覆盖34个真实开源项目。完整筛选原因见 [`docs/00-benchmark-cleaning.md`](docs/00-benchmark-cleaning.md)。

每个模型对每个“题目 × Prompt”条件独立采样5次：

```text
194题 × 31 Prompt × 5次 × 3模型 = 90,210条回答
```

三个模型为DeepSeek Flash、Qwen2.5-7B-Instruct和Qwen3-8B。31条Prompt来自《How Well do LLMs Compress Their Own Chain-of-Thought?》，并适配到代码任务：推理长度与格式限制只作用于代码前的可选说明，不限制Python代码本身。三模型统一使用temperature 0.2、top_p 1、最多2,048输出tokens并关闭thinking模式。

## 2. 最终评分口径

第一次测试发现旧评分器会把类方法缩进和普通import误记成模型错误，本交付已全部改用 `target-function-ast-v2`：用AST提取目标函数，补齐参考签名信息，并在禁止网络、仅允许临时目录写入的macOS沙箱中执行官方测试。原始模型回答未修改。

194题中有1题的参考实现无法稳定通过统一预检。为公平比较，该题在三个模型中统一标记为环境排除，共465条，不进入模型性能分母；正式结果基于193个共同可评任务。

## 3. 主要结果

| 模型 | Pass@1 | Pass@3 | Pass@5 |
|---|---:|---:|---:|
| DeepSeek Flash | 30.22% | 33.73% | 34.97% |
| Qwen2.5-7B-Instruct | 22.59% | 26.04% | 27.34% |
| Qwen3-8B | 22.09% | 26.36% | 28.01% |

![三个模型的Pass@k](figures/01_model_pass_at_k.png)

核心观察：

- DeepSeek在Pass@1/3/5上均高于两个Qwen模型；按题聚类bootstrap后，差异区间不跨0。
- Qwen2.5与Qwen3之间的Pass@1/3/5配对差异区间均跨0，不能认定存在稳定优劣。
- 五次独立采样确实增加“至少一次成功”的比例，但收益快速饱和；第5次采样的累计边际提升仅为0.47、0.60、0.79个百分点。
- Prompt影响高度依赖模型。`DefaultCoT` 相对 `NoCoT` 的Pass@1差异在DeepSeek为−3.11个百分点、Qwen2.5为+1.04个百分点、Qwen3为+14.30个百分点。
- 极端格式压力会使模型不给出可提取的Python函数。例如Qwen2.5在 `NoProperGrammar` 下提取错误率为94.5%，Qwen3在 `OnlyNumbers` 下为78.7%。
- 输出更长不等于更正确；token数与正确率的关系只能作描述性观察。

完整数值、区间和解释见 [`docs/03-results-and-outputs.md`](docs/03-results-and-outputs.md)。这里的5次是独立单轮请求，不是根据测试反馈修复代码的Multi-turn对话。

## 4. 目录内容

| 目录 | 内容 |
|---|---|
| [`data/`](data/) | 194题、31条Prompt、90,210条原始回答、模型配置、采集元数据和校验和 |
| [`derived/`](derived/) | 90,210条新版评分、Pass@k、聚类置信区间、Prompt比较、错误率和饱和分析 |
| [`docs/`](docs/) | Benchmark清洗、实验设计、Prompt策略、最终结论、限制及18条完整输出示例 |
| [`figures/`](figures/) | 六组PNG/SVG/PDF图及每张图的源CSV |
| [`src/`](src/) | 采集、沙箱评分、离线分析、绘图、样例导出和完整性校验脚本 |

## 5. 离线复算

大型压缩数据由Git LFS保存。克隆仓库后执行：

```bash
git lfs install
git lfs pull
python -m pip install -r experiments/code-prompt-eval/requirements.txt
python experiments/code-prompt-eval/src/verify_delivery.py
python experiments/code-prompt-eval/src/analyze.py --pass-k 1 3 5
python experiments/code-prompt-eval/src/summarize.py
python experiments/code-prompt-eval/src/plot_results.py
```

离线复算不需要模型API Key。重新运行90,210次模型请求才需要在环境变量中配置各供应商Key；交付文件不包含真实密钥。

## 6. 文档导航

- [`docs/00-benchmark-cleaning.md`](docs/00-benchmark-cleaning.md)：221题如何筛为194题
- [`docs/01-benchmark-and-design.md`](docs/01-benchmark-and-design.md)：Benchmark、规模与研究问题
- [`docs/02-prompt-strategies.md`](docs/02-prompt-strategies.md)：31条Prompt的来源和代码适配
- [`docs/03-results-and-outputs.md`](docs/03-results-and-outputs.md)：最终统计结果与可报告结论
- [`docs/04-reproduction-and-limitations.md`](docs/04-reproduction-and-limitations.md)：评分修正、复算方式与限制
- [`docs/05-output-examples.md`](docs/05-output-examples.md)：18条完整模型输出和自动测试结果

## 7. 来源与解释限制

- CodePromptEval：<https://github.com/icetlab/CodePromptEval>
- CoderEval：<https://github.com/CoderEval/CoderEval>
- Prompt来源论文：*How Well do LLMs Compress Their Own Chain-of-Thought?*（arXiv:2503.01141）

本结果只代表当前可执行Python子集、当前云端模型版本和本实验Prompt适配。单元测试通过不等于代码在所有输入下正确；31条Prompt的排名也没有进行多重比较校正，不应扩展成普遍的“最佳Prompt”。
