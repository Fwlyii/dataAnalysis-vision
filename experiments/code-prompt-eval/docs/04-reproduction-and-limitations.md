# 复算、评分修正与限制

## 无需API Key的离线复算

在仓库根目录执行：

```bash
git lfs install
git lfs pull
python -m pip install -r experiments/code-prompt-eval/requirements.txt
python experiments/code-prompt-eval/src/verify_delivery.py
python experiments/code-prompt-eval/src/analyze.py --pass-k 1 3 5
python experiments/code-prompt-eval/src/summarize.py
python experiments/code-prompt-eval/src/plot_results.py
```

这些命令只读取已保存的回答和测试结果，不调用模型API。完整功能测试依赖原CodePromptEval项目、34个项目环境和macOS `sandbox-exec`，因此本仓库把新版逐条评分一并交付，日常复算无需重建项目环境。

## 评分器v2修正

第一次自动测试暴露出两个系统性问题：

1. 类方法的参考代码保留类内缩进，评分器直接 `ast.parse` 时会产生 `IndentationError`，错误地记成模型语法错误。
2. 旧安全规则把 `re`、`json`、`typing` 等普通依赖导入直接记成模型失败。

最终交付不使用旧评分。v2先去除参考函数的外层缩进，以AST提取模型目标函数，把模型给出的顶层导入、常量和辅助定义移入目标函数，并继承参考模板的参数/返回注解和装饰器，再替换到官方测试模板。这避免测试模板缺少 `List`、`Optional` 等类型导入时出现假失败，也不使用会改变 `inspect` 行为的全局延迟注解。参考实现和候选实现都在相同macOS沙箱策略下预检或执行：禁止网络，写入仅允许临时目录。参考实现无法在沙箱中通过的记录标记为环境排除，不进入模型正确率分母。

新版评分文件均含：

```text
sandboxed = true
normalization = target-function-ast-v2
```

原始回答从未修改。旧评分文件不进入本次提交，避免误用。

## 指标

对每个“模型 × 题目 × Prompt”单元有5个独立样本。若其中 `n` 个可评、`c` 个通过，采用标准无偏估计：

```text
Pass@k = 1 - C(n-c, k) / C(n, k)
```

模型与Prompt汇总先在任务-Prompt单元计算，再平均。95%区间按 `task_id` 聚类bootstrap 5,000次，随机种子91，避免把同一题下31个Prompt和5个样本当成完全独立观察。区间为探索性结果，未做多重比较校正。

## 局限

- 194题是可执行性筛选集，不是221题的随机样本。
- 单元测试通过只表示通过现有断言，不保证一般正确性、安全性或代码质量。
- 沙箱会排除必须联网或向临时目录外写入的参考任务；这些记录不算模型失败。
- Prompt限制只约束推理文字，不约束代码，属于针对代码任务的合理适配，但改变了原论文的字面条件。
- 五次是低温度独立采样；只支持Pass@1/3/5，不能推断Pass@10。
- 本实验没有测试反馈后的修复对话，不能把累计成功称为Multi-turn提升。
- 模型由不同供应商托管，推理框架、精度和服务版本可能影响结果；模型ID和采集日期已留档。
- Prompt排名涉及93个模型-Prompt组合，适合描述和提出假设，不宜只凭单次排名宣称普遍最优。
