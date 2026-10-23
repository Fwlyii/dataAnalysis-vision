# 原始数据与输入

| 文件 | 内容 |
|---|---|
| `benchmark_194_tasks.csv.gz` | 清洗后的完整 CodePromptEval 输入，194题 × 原始32组合，共6,208行 |
| `tasks.csv` | 每题一行的194题索引，便于浏览和分组 |
| `task_examples.json` | 三道 Standalone 示例题 |
| `benchmark_audit.csv` | 原始221题的参考实现实跑审计、排除原因和194题推荐标记 |
| `prompts.json` | 31条论文提示词原文及代码任务适配版本 |
| `prompt_examples.txt` | 同一道题在31条策略下的完整最终Prompt |
| `model_profiles.json` | 三模型调用配置及保留的本地配置；不含真实API Key |
| `raw_deepseek-flash.jsonl.gz` | DeepSeek Flash的30,070条完整请求结果 |
| `raw_qwen2.5-7b-instruct-cloud.jsonl.gz` | Qwen2.5-7B-Instruct的30,070条完整请求结果 |
| `raw_qwen3-8b-cloud.jsonl.gz` | Qwen3-8B的30,070条完整请求结果 |
| `manifest.json` | 实验规模、采样方式、模型、生成参数和评分版本 |
| `dataset_sources.json` | Benchmark、论文和提示词来源链接及固定提交 |
| `pricing_at_collection.json` | 采集时价格说明，不代表以后仍保持相同价格 |
| `collection_progress.json` | 三模型起止时间、记录数和Token总量 |
| `data_dictionary.tsv` | 原始响应、评分和任务单元字段定义 |
| `CHECKSUMS.json` | 大型压缩文件的压缩/解压SHA-256和字节数 |

三份原始响应逐行保留完整Prompt、模型输出、提取代码、Token用量、延迟、任务元数据和唯一键。每条记录都是独立单轮请求；`turn_id=1..5`表示同一条件下的五次独立采样，不表示模型看到了上一轮答案或测试反馈。

API Key没有写入任何交付文件。大型`.gz`文件由Git LFS管理；pandas可直接读取，例如：

```python
import pandas as pd
scores = pd.read_csv("experiments/code-prompt-eval/derived/scores.csv.gz")
```
