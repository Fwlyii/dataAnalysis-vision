# 原始数据与输入

| 文件 | 内容 |
|---|---|
| `raw_responses.jsonl.gz` | 全部 74,800 条原始 API 记录，含实际 request、完整 response、模型、时间、用量和输入哈希 |
| `scenarios.jsonl.gz` | 37,400 个场景定义；两模型共用，合计 74,800 次回答 |
| `attempt_log.jsonl.gz` | 请求尝试日志；用于追查重试、HTTP 状态和运行异常 |
| `CHECKSUMS.json` | 上述压缩文件及采集器结果、复核队列的 SHA-256、解压哈希和字节数 |
| `questions.json` | 200 道独立题、官方答案和 gold 资料元数据 |
| `zzy_prompts.json` | 31 条 ZZY 策略原文 |
| `prompt_examples.txt` | 前三道题的完整 prompt；省略号版本只在说明文档中使用 |
| `model_output_preview.txt` | 首题 31 策略 × 两模型的原始输出预览；其中评分是采集器旧口径，最终评分请读 derived/scores.csv |
| `manifest.json` | 原样保留的采集协议、参数、提交与抽样指纹 |
| `dataset_sources.json` | 官方数据文件固定 URL 和 SHA-256 |
| `model_probes.json` | 两模型实际连通性探测，未计入实验次数 |
| `pricing_at_collection.json` | 采集当次免费价格条目快照，不代表以后仍免费 |
| `data_dictionary.tsv` | 原始字段和最终评分字段说明 |

JSONL 是每行一个 JSON 对象；pandas 可直接读取 `.gz`，例如 `pd.read_json(path, lines=True)`。不需要先把大文件全部解压到仓库。原始文件的解压字节与本地采集日志一致；回答原文未做语义修正。

`manifest.json` 中的 `grading` 是采集时的协议；它的全文包含指标不等于论文的首行指标。此次交付额外保留官方首行、严格最终答案、最终答案包含和全文包含四个指标，见 `derived/README.md`。旧路径和密钥来源描述仅为历史元数据，离线分析无需这些路径或密钥。

队列的 `messages.jsonl` 可由场景和原始响应重建，不重复提交；PID、运行锁、后台文本日志和本地依赖缓存留在 `ccfa-workfiles/`，以免把运行状态混入最终数据。复核队列已保留，但尚未全部人工复核。
