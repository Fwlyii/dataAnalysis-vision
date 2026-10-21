# 1. Benchmark、抽题和测试场景

## Benchmark

使用 [Lost in the Middle 官方仓库](https://github.com/nelson-liu/lost-in-the-middle) 的 NQ-Open 多文档问答数据。固定资料文件是 `10_total_documents/nq-open-10_total_documents_gold_at_0.jsonl.gz` 和 `20_total_documents/nq-open-20_total_documents_gold_at_0.jsonl.gz`，各有 2,655 道题。文件地址、SHA-256 和上游提交写在 [`data/dataset_sources.json`](../data/dataset_sources.json)。

从两个文件的共同题目中抽取 200 道基础题：保留种子 91 的首轮 10 题，再从排序后的剩余题目中不放回抽取 190 题。题目和官方接受答案原样保留，不根据模型表现筛题。

每道题生成 2 种资料长度和 3 个证据位置：

| 项目 | 设置 |
|---|---|
| 独立问题 | 200 道 |
| 资料数量 | 10 篇、20 篇 |
| gold 位置 | 前、中、后；10 篇为 1/5/10，20 篇为 1/10/20 |
| prompt 策略 | ZZY 的全部 31 种 |
| 模型 | `Qwen/Qwen2.5-7B-Instruct`、`Qwen/Qwen3-8B` |
| 主实验 | 200 × 2 × 3 × 31 × 2 = 74,400 次 |
| 无资料对照 | 200 × NoCoT × 2 = 400 次 |
| 总计划量 | 74,800 次正式回答 |

位置干预只移动唯一 gold 文段，保留干扰资料的顺序。模型不会看到 `isgold`、检索分数或标准答案，只看到资料标题、正文、问题和 prompt 要求。完整场景输入在 [`data/scenarios.jsonl`](../data/scenarios.jsonl)，题目答案表在 [`data/questions.json`](../data/questions.json)。

## 三个真实测试题目示例

### 示例 1：电影续作

```text
Question: sequel to a christmas story it runs in the family
Accepted answer: My Summer Story
```

任务是从含有多个相似电影名的资料中找出《A Christmas Story》的续作。支持文段是 `My Summer Story` 的介绍，但同一批资料中也有 2003 年的 `It Runs in the Family`，可以制造实体混淆。

### 示例 2：印度联邦院选举

```text
Question: who votes to elect a rajya sabha memmber
Accepted answer: state legislatures
```

该题测试模型能否从政治制度资料中识别选举主体。源题的 `memmber` 拼写保留不改，答案使用官方标签 `state legislatures`。

### 示例 3：美国计量单位

```text
Question: what kind of metric system does the us use
Accepted answers: international units; United States customary units
```

这道题同时适合做异常和标签局限示例：题目写了 `metric system`，官方答案却同时接受 `international units` 和 `United States customary units`，需要在结果中标为语义歧义，不能把一次匹配直接解释成模型真正理解了概念。

## 可交付的数据

`data/questions.json` 保存 200 道抽样题、官方答案和支持文段元数据；`data/scenarios.jsonl` 保存所有 74,800 个计划场景的输入哈希和 prompt 文本；`data/raw_responses_20261021T231742+0800.jsonl` 保存截至快照时已经收到的模型原始响应。每条响应带有 `question_id`、`scenario_id`、模型、策略、资料数量、gold 位置、时间、延迟、输入哈希和 API 返回内容。
