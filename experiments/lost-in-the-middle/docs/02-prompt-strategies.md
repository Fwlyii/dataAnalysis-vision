# 2. Prompt 策略和实际输入

本实验完整运行 ZZY 分支中整理出的 31 条策略，原文见 [`data/zzy_prompts.json`](../data/zzy_prompts.json)。所有场景还追加相同的格式要求：

```text
End your response with FINAL ANSWER: <short answer in English>.
```

这个追加要求是本实验的适配项；它和 `BulletPoints`、长度限制等策略可能发生冲突，所以格式遵循需要单独记录，不能把格式成功等同于答题成功。

## 31 条策略的可测性

| 类别 | 策略 | 是否适合主比较 | 说明 |
|---|---|---|---|
| 基础回答 | `NoCoT`、`DefaultCoT`、`BeConcise`、`BulletPoints` | 可以 | 可比较是否要求解释、简洁或列表格式影响资料读取。 |
| 长度约束 | `WordLimit(5/10/15/25/50/100)`、`CharLimit(50/100/500)`、`TokenLimit(50/100/500)` | 可以，但分层 | 可测试输出预算；短预算可能容不下人名、片名或机构名。 |
| 步骤约束 | `StepLimit(1/2/5)` | 可以 | 测试显式步骤数；需要同时看答案是否被挤掉。 |
| 格式压力 | `NoSpaces`、`NoProperGrammar`、`AbbreviateWords` | 不宜直接混入主比较 | 字面形式改变，严格 EM 会把格式损失误当知识损失；适合作为单独压力实验。 |
| 极短预算 | `OnlyNumbers`、`WordLimit(1)`、`CharLimit(10)`、`TokenLimit(10)` | 不宜作为主结论 | 许多正确答案本身超过限制，失败可能来自不可满足约束。 |
| 中文输出 | `ChineseCoT`、`ChineseCoT(10/50/100/500)` | 需要另建评分 | 英文答案的精确匹配不能直接评价中文译名，需要实体别名表和人工复核。 |

主结果图使用 19 个英文、可直接比较的策略；格式压力、极短预算和中文策略保留在原始表中，并在 `strategy_scope` 中标记为需要单独复核。

## 针对示例题的具体 prompt

下面展示示例 1 的实际 prompt 头部。完整的 20 篇资料版本、前中后位置版本和三个示例题的输入都在 [`data/prompt_examples.txt`](../data/prompt_examples.txt)。

### NoCoT

```text
Only give the final answer. Do not give any explanation.
End your response with FINAL ANSWER: <short answer in English>.

Write a high-quality answer for the given question using only the provided search results (some of which might be irrelevant).
...
Question: sequel to a christmas story it runs in the family
Answer:
```

### DefaultCoT

```text
Think step by step before answering.
End your response with FINAL ANSWER: <short answer in English>.

Write a high-quality answer for the given question using only the provided search results (some of which might be irrelevant).
...
Question: sequel to a christmas story it runs in the family
Answer:
```

### WordLimit(25)

```text
Only use 25 words for your answer.
End your response with FINAL ANSWER: <short answer in English>.

Write a high-quality answer for the given question using only the provided search results (some of which might be irrelevant).
...
Question: sequel to a christmas story it runs in the family
Answer:
```

资料段落使用官方 `qa.prompt` 的 `Document [i](Title: ...)` 格式，唯一 gold 文段分别放在第 1/5/10 或第 1/10/20 个位置。所有策略使用 `temperature=0` 和 `max_tokens=800`；Qwen3 使用 `enable_thinking=false`，因此 `DefaultCoT` 只表示可见 prompt 要求，不表示开启服务端隐藏思考模式。

31 种策略现已全部完成：每策略、每模型均有 1,200 条主实验回答。`TokenLimit` 是文本软约束，不是 API 的硬上限；所有策略的 API 上限统一为 800。完整覆盖见 [`derived/coverage.csv`](../derived/coverage.csv)，三道题的三种示例策略在两个模型上的完整输出见 [`05-output-examples.md`](05-output-examples.md)。
