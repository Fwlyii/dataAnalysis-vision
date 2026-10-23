# 31条Prompt策略

提示词来自《How Well do LLMs Compress Their Own Chain-of-Thought?》的31种压缩策略，并适配到Python函数生成。适配原则是：格式、语言和长度限制只约束代码块前的可选推理，最终Python代码不受字数、字符、空格或语言限制。否则 `OnlyNumbers`、`NoSpaces`、`WordLimit(1)` 等策略会直接使合法Python不可写，测到的只是格式冲突。

| 类别 | 数量 | Prompt |
|---|---:|---|
| 基线与常见推理 | 4 | NoCoT、DefaultCoT、BeConcise、BulletPoints |
| 格式压力 | 4 | OnlyNumbers、NoSpaces、NoProperGrammar、AbbreviateWords |
| 单词限制 | 7 | WordLimit(1/5/10/15/25/50/100) |
| 字符限制 | 4 | CharLimit(10/50/100/500) |
| Token限制 | 4 | TokenLimit(10/50/100/500) |
| 步骤限制 | 3 | StepLimit(1/2/5) |
| 中文推理 | 5 | ChineseCoT及10/50/100/500字符版本 |

完整原文和适配文本见 `data/prompts.json`。

## Prompt示例

NoCoT：

```text
Do not provide any reasoning or explanation before the code.
```

DefaultCoT：

```text
Think step by step and write the reasoning before the code.
```

TokenLimit(10)：

```text
If you provide reasoning before the code, use at most 10 tokens. The code does not count toward this limit.
```

统一尾部要求模型以一个Python代码块结束回答，并明确禁止把推理格式限制施加到代码。所有模型使用相同Prompt文本和顺序随机种子。

## 解释边界

- 这是将数学推理压缩策略迁移到代码生成后的实验，不是原论文的直接复现。
- 显式CoT只指可见的代码前说明；三个配置均关闭供应商thinking模式。
- 格式压力策略可能影响代码块遵循和提取率，这本身是结果的一部分。
- 31策略比较属于探索性多重比较。报告给出按题聚类区间，但不把描述性排名写成确定的“最优Prompt”。
