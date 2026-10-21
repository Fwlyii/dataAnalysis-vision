# 4. 复现口径、运行方式和限制

## 论文口径

原论文 [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/html/2307.03172v3) 通过控制资料长度和相关资料位置，观察到相关信息位于开头或结尾时通常更容易被使用，中间位置表现下降。官方评分实现取回答首行，再执行规范化答案子串匹配。本项目把官方评分文件固定保存为 [`src/official_metrics.py`](../src/official_metrics.py) 和 [`src/official_evaluate_qa.py`](../src/official_evaluate_qa.py)。

本项目不是原论文的逐项复刻：模型换成两个免费 Qwen 模型，抽取 200 道题，只使用 10/20 篇资料，并加入 31 种输出策略和统一 `FINAL ANSWER` 格式。因此结论应写成“在课程规模数据上检验论文现象”，不能写成复现论文的具体数值。

## 数据快照校验

[`data/SNAPSHOT.json`](../data/SNAPSHOT.json) 记录了原始日志快照的字节数和 SHA-256：

```text
file: data/raw_responses_20261021T231742+0800.jsonl
bytes: 462947202
sha256: 84f174b75fbd3bd093595f58060a284ee99d22a04d17540b760f459381a7cb8b
```

快照是 append-only 原始日志在完整 JSON 行边界上的前缀。采集器继续写入的暂存目录是 `ccfa-workfiles/experiments/lost-middle-pilot/`，没有纳入提交，以免把运行锁、PID 和正在变化的日志混入交付版本。

## 分析和绘图

当前阶段性评分已经随快照提交。重新生成图表：

```bash
cd experiments/lost-in-the-middle
python src/plot_results.py \
  --input derived/interim_analysis_20261021T231742.json \
  --out figures
```

若要重跑原始快照的评分，需要在 `src/interim_analysis_reference.py` 中把根目录指向本目录，并准备 `numpy`、`pandas` 和官方评分依赖；实际运行时应先复制最终的 `raw_responses.jsonl`，再用快照字节数锁定输入。API key 不写入仓库。

## 结论措辞

推荐报告使用以下表述：

> 在当前阶段性快照中，两个模型都显示出证据位置效应，前置证据相对于中间证据的优势尤其明显；后置证据相对于中间证据的优势尚未在两个模型上稳定出现。因此实验部分复现了“中间位置更容易退化、开头位置更有利”的核心方向，但尚不足以宣称完整复现论文的对称 U 形曲线。

最终采集结束后，应重新生成评分、配对置信区间和三位置完整样本图，再替换“阶段性”表述。不得为了得到 U 形而删掉失败响应、改变题目或调整评分规则。
