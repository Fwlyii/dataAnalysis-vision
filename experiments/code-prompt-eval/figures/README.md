# 最终图表与源数据

六组图均基于新版沙箱评分，提供300 DPI PNG、文字可编辑SVG、嵌入字体PDF和同名源CSV。图中使用英文标签，便于跨系统渲染。

| 图 | 目的 | 统计口径 |
|---|---|---|
| `01_model_pass_at_k` | 比较三模型Pass@1、Pass@3、Pass@5 | 194题 × 31 Prompt；任务聚类bootstrap 95% CI |
| `02_sampling_saturation` | 展示1到5次独立采样的累计成功与边际新增 | 顺序累计曲线；不是多轮反馈修复 |
| `03_prompt_pass_at_1` | 比较31条Prompt在三个模型上的Pass@1 | 每点194个任务单元；任务聚类CI |
| `04_prompt_sampling_gain` | 展示各Prompt从Pass@1到Pass@5的百分点收益 | 描述性热力图，共享色标 |
| `05_error_categories` | 比较三个模型的主要失败类型 | 分母为可评回答；环境排除不计入模型错误 |
| `06_tokens_and_pass_at_1` | 比较Prompt平均Token用量与Pass@1 | 93个Prompt-模型均值；只解释为关联 |

每张图的数值位于 `source_data/`。比例图从0起；Prompt排序为描述性展示。模型颜色采用色盲友好的Okabe-Ito配色，并用不同点形补充区分。

重新生成：

```bash
python experiments/code-prompt-eval/src/plot_results.py
```
