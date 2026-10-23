# 最终分析文件

| 文件 | 用途 |
|---|---|
| `analysis.json` | 全部 74,800 条数据的最终自动评分汇总、位置/模型/策略/长度比较和置信区间 |
| `scores.csv` | 每条回答一行；包含四种评分、提取答案、token、截断、scope、时间和 question/scenario ID |
| `position_rates.csv` | NoCoT、core8、english19 的位置准确率，区分模型和资料长度 |
| `paired_positions.csv` | 同题、同模型、同策略、同资料数的位置差，含按题聚类 CI |
| `complete_triples.csv` | 前中后三位置齐全的同组数据汇总；本次最终版已平衡 |
| `length_pairs.csv`、`prompt_pairs.csv`、`model_pairs.csv` | 资料长度、CoT/NoCoT 和模型的配对比较 |
| `strategies.csv`、`truncation_by_strategy.csv`、`control_rates.csv` | 策略统计、截断统计和无资料对照 |
| `coverage.csv` | 所有 374 个实验分组，每组 200 条 |
| `verification.json` | 完整性检查结果：覆盖、唯一性、哈希、模型、标签 |
| `data_profile.json` | 按模型和策略类别剖析列类型、缺失、样本数、分布与相关性；仅作 EDA，不将编码后的类别或重复题的相关性解释为因果 |
| `collection_progress.json` | 采集完成时的原始状态，结束时间 2026-10-22 20:21:16 +08:00 |
| `collector_summary.json` | 采集器旧口径汇总，保留以便溯源 |
| `collector_results.csv.gz` | 采集器完整 74,800 行结果表，含回答全文；旧口径严格匹配和全文包含 |
| `review_queue.jsonl.gz` | 采集器生成的待复核记录，未声称已人工处理 |

## 评分口径

- `paper_firstline`：官方代码对模型首行执行标准答案规范化包含匹配；用于与论文口径对照。对 CoT 首行寒暄或提纲可能不公平。
- `strict_final_em`：最后一个 `FINAL ANSWER:` 后首行与官方别名做规范化严格匹配。可能因回答较长而判错，不能当作人工语义准确率。
- `final_contains`：只在提取到的最终答案片段中执行官方包含匹配。可能把包含正确实体但关系讲错的句子判为正确。
- `full_response_contains`：在全文中做官方包含匹配，容易接受推理途中偶然出现的答案，作为敏感性指标保留。
- 若最终标记为空，仅在标记前是单行且不超过 30 个空白分隔词时恢复该短答案，共 1,472 条。只影响离线提取和最终答案评分，原始输出及论文首行评分不改。

scope 将 31 种策略分成主比较 19 种、格式压力 3 种、极短预算 4 种、中文 5 种。所有记录均保留；中文英文别名、压缩拼写等仍需人工或专用规则，不用混合成功率掩盖评分偏差。

独立单位是 200 道基础题。每个位置比较固定其他条件后配对，再按题目聚类 bootstrap 5,000 次（种子 91）。95% 区间为探索性估计，未做多重比较校正；不能把 74,800 条当成 74,800 个独立样本。CSV 中的 `snapshot_at`/`snapshot_raw_prefix_*` 命名沿用原分析结构，此次对应完整原始文件，而非中途前缀；重算时间会变化，成绩和随机种子固定。
