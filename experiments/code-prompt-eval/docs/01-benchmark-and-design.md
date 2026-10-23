# Benchmark与实验设计

## Benchmark

实验使用CodePromptEval的Python函数级任务。该数据基于CoderEval，包含真实开源项目中的函数、签名、依赖、参考实现和测试模板。原始221题先执行官方参考实现：196题在准备好的项目与Python环境中通过；再排除2道题意与断言存在确认不一致的任务，得到194题正式集合。完整审计见 `data/benchmark_audit.csv` 和 `docs/00-benchmark-cleaning.md`。

194题覆盖34个项目。按原数据层级分为：

| 层级 | 题数 |
|---|---:|
| class_runnable | 51 |
| file_runnable | 58 |
| plib_runnable | 13 |
| project_runnable | 21 |
| self_contained | 30 |
| slib_runnable | 21 |

这不是从221题随机抽样，而是按当前可执行性与语义一致性筛选，因此结果代表“可在本环境可靠评分的194题”，不能无条件推广到全部221题。

## 三道示例

`data/task_examples.json`保存三道Standalone示例：`is_none_string`、`paging`、`_dictsum`。它们无需外部项目，适合检查Prompt构造、代码提取和单元测试流程。完整任务文本、依赖和函数签名保存在该文件；全部194题索引见 `data/tasks.csv`。

## 实验规模

每个模型对194题、31条Prompt分别独立生成5次：

```text
194题 × 31 Prompt × 5次 × 3模型 = 90,210条回答
```

每模型30,070条。模型为：

- `deepseek-flash`
- `Qwen/Qwen2.5-7B-Instruct`
- `Qwen/Qwen3-8B`

固定设置为temperature 0.2、top_p 1、最大输出2,048 tokens、关闭thinking。任务上下文固定为函数签名与可用包信息，避免同时改变Prompt策略和代码上下文。

## 研究问题

1. 三个模型的Pass@1、Pass@3、Pass@5是否不同？
2. 五次独立采样的新增成功是否快速趋于零？
3. 31条Prompt如何影响功能正确率、稳定性和Token用量？
4. 不同模型和Prompt的失败类型是否不同？

五次生成互相不可见。累计成功率和Pass@k研究“多抽几个独立答案”的收益，不是多轮反馈修复，也不能写成模型在第2到第5轮学习了前一轮错误。
