# 脚本说明

| 脚本 | 用途 |
|---|---|
| `run_experiment.py` | OpenAI兼容接口采集器，支持模型配置、31 Prompt、独立采样、并发、断点续跑和重试 |
| `evaluate_responses.py` | 函数替换、参考实现预检和沙箱功能测试；完整重评需要原CodePromptEval项目环境 |
| `analyze.py` | 合并压缩原始回答与评分，计算Pass@k、累计成功、稳定性和错误转移 |
| `summarize.py` | 生成模型/Prompt汇总、任务聚类bootstrap区间和配对比较 |
| `plot_results.py` | 生成六组PNG/SVG/PDF图和对应源CSV |
| `export_examples.py` | 固定导出3题 × 2 Prompt × 3模型的18条完整输出示例 |
| `verify_delivery.py` | 校验哈希、记录数、唯一键、模型、题目、Prompt、样本数和评分版本 |

日常离线复算只需 `analyze.py`、`summarize.py`、`plot_results.py` 和 `verify_delivery.py`，不会调用API。`run_experiment.py` 已指向本目录的压缩benchmark、Prompt和模型配置，可在自行配置 `.env` 后重新采集。`evaluate_responses.py` 用于方法溯源；重新执行功能测试仍需从清单固定的CodePromptEval提交准备34个项目环境。
