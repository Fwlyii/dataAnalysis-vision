# 新版评分与分析文件

| 文件 | 用途 |
|---|---|
| `evaluation_*.jsonl.gz` | 三模型各30,070条沙箱功能测试结果，含错误信息与评分版本 |
| `scores.csv.gz` | 90,210条紧凑逐条评分，用于离线分析 |
| `task_prompt_units.csv.gz` | 18,042个模型-题目-Prompt单元及单元Pass@1/3/5 |
| `model_summary.csv` | 三模型总体成功率、Pass@k、任务聚类CI、Token与延迟 |
| `model_pairs.csv` | 模型间Pass@k配对差，按题聚类bootstrap |
| `prompt_summary.csv` | 31 Prompt × 3模型的Pass@k、CI、Token和采样收益 |
| `prompt_vs_nocot.csv` | 各Prompt相对NoCoT的配对差和聚类CI |
| `error_summary.csv` | 三模型总体错误类型分布 |
| `pass_at_k.csv` | 标准无偏Pass@1/3/5，含模型总体与Prompt分组 |
| `turn_success.csv` | 第1至第5个独立样本的单次及累计成功率、边际新增 |
| `turn_stability.csv` | 相邻样本成功/失败转移和McNemar检验 |
| `prompt_reliability.csv` | 始终成功、波动、始终失败的任务-Prompt单元比例 |
| `saturation_summary.csv` | 边际收益低于1个百分点的候选/强饱和判定 |
| `prompt_error_rates.csv` | 模型、Prompt、样本序号和错误类型的明细率 |
| `first_success_turn.csv` | 每个模型-题目-Prompt首次成功出现在哪个样本 |
| `error_transitions.csv` | 相邻独立样本错误类别转移；用于稳定性而非修复因果解释 |
| `summary.json` | 覆盖、环境排除、模型、任务、Prompt和样本完整性 |
| `research_summary.json` | 面向README和图表的紧凑研究汇总 |

`analysis_passed`为空的记录是参考实现在统一沙箱中无法可靠执行的环境排除，不进入模型性能分母。模型错误率只对可评记录计算。旧评分器的 `evaluation_error` 和宽泛 `safety_error` 未混入本目录。

模型、Prompt与采样比较的95%区间以194道题为聚类单位，bootstrap 5,000次、种子91。由于31条Prompt涉及多重比较，Prompt排名与相对NoCoT差异均按探索性结果解释。
