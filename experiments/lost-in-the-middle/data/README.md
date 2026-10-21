# 数据文件说明

| 文件 | 内容 | 备注 |
|---|---|---|
| `questions.json` | 200 道抽样题、答案和资料元数据 | 题目级输入 |
| `scenarios.jsonl` | 74,800 个计划场景的 prompt 和位置配置 | Git LFS |
| `raw_responses_20261021T231742+0800.jsonl` | 截至快照已收到的原始模型响应 | 38,912 条；Git LFS；SHA-256 见 `SNAPSHOT.json` |
| `prompt_examples.txt` | 三道示例题的完整资料 prompt | 可直接查看实际输入 |
| `model_output_preview.txt` | 首题各策略的输出预览 | 原文保留 |
| `preview_records.json` | 预览记录的结构化版本 | 便于程序读取 |
| `manifest.json` | 实验参数、模型、上游提交和抽样信息 | 运行协议 |
| `zzy_prompts.json` | 31 条策略原文 | 来自 ZZY 分支整理结果 |
| `dataset_sources.json` | 官方数据 URL 和 SHA-256 | 上游数据指纹 |

`raw_responses_...jsonl` 是 append-only 日志在完整 JSON 行边界上的稳定前缀；正在运行的采集器原始文件不直接提交。`messages.jsonl`、`attempt_log.jsonl`、`background.log`、PID 和锁文件属于运行时队列或日志，无法增加结果复现价值，因此留在本地暂存目录并被根目录 `.gitignore` 忽略。
