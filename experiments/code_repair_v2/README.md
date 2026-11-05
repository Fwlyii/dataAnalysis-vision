# 代码执行反馈补充实验

本批次将已有四种反馈扩为六种，使用硅基流动官方价格为0的两款Qwen服务。所有164道HumanEval+ v0.1.10题目纳入，两模型各进行3次独立初稿采样；同一初稿在六组之间配对共享，各组修改4次。计划24,600份物理回答，题目仍是164个独立统计簇，不把重复与模型数量算成额外独立题目。

| 组别 | 模型收到的信息 |
|---|---|
| 独立重采样 | 原题，每次独立生成 |
| 自行检查 | 原题、此前本组代码与对话、通用检查指令 |
| 仅通过状态 | 此前历史、公开诊断PASS/FAIL |
| 语法与运行诊断 | 状态、错误阶段、类型、消息、候选代码定位与精简栈；不额外给测试输入或期望输出 |
| 单个失败反例 | 状态及首个失败的输入、期望、实际输出、异常类型与消息 |
| 多反例与测试摘要 | 最多3个不同失败摘要及真实通过、失败、阻断、未执行计数 |

可加载的程序逐项扫描公开基础输入；语法或加载失败则确认程序失败并记录测试组阻断。逐例执行数使用`cases_checked`。原始`failed_cases`在加载失败时包含整套输入的逻辑失败标签，与`blocked_cases`、`unchecked_cases`重叠，不能相加当成实际执行数；分析另存实际逐例失败数。反馈构造函数只读取`public`并保留当时反馈原文。正常返回但答案错误记为`output_mismatch`，不会把评测器抛断言的位置当成候选程序错误行。

同版本完整版与旧Mini逐题规范、参考解、接口、容差及基础输入一致。保留基础1,570个诊断输入；完整plus排除与公开输入重合及重复后有122,459个输入，仅用于强评测，不进入提示。初稿与终稿为事先确定的主比较；所有中间版本额外进行强评测，用于真实轨迹和基于公开诊断的停止策略分析。

数据源、split与运行时先冻结，164份参考实现在macOS沙箱中全部通过后才能采集。候选执行禁网，不能读取项目、凭据或用户文件。基础设施未知不伪记为失败；触发内存或墙钟上限时，父层在同预算参考控制通过、候选违约复现后才认定资源失败，保留原始记录及复验审计。该操作语义澄清记录在`operational-amendment-1.json`，冻结worker、反馈投影、采样参数与任务矩阵不变。

## 运行

Python环境只需要numpy与psutil。凭据通过环境变量或私有文件读取，不进入配置、请求日志、Git或网页快照。

```bash
python -m experiments.code_repair_v2.src.prepare --config configs/code_repair_extension.json
python -m experiments.code_repair_v2.src.collect --config configs/code_repair_extension.json --credential-file /private/path/key
python -m experiments.code_repair_v2.src.holdout --config configs/code_repair_extension.json --watch --all-rounds --concurrency 4
python -m experiments.code_repair_v2.src.analyze --config configs/code_repair_extension.json
python -m experiments.code_repair_v2.src.normalize --config configs/code_repair_extension.json --output reports/code_repair_extension/code-repair-extension-free-full-20261105-3rep-v2/unified-format
python -m experiments.code_repair_v2.src.publish --source reports/code_repair_extension/code-repair-extension-free-full-20261105-3rep-v2
```

采集与评测支持断点续跑，完整响应和真实评分按记录ID核对。未完整的任务块不会伪称完整配对结果；缺失会单独报告。全部新增运行数据位于配置指定的独立批次，既有受保护科研文件不覆盖。

原批次的5,576份物理代码另用同一强保留集复测，结果单列为`legacy-full-recheck`，不冒充模型当时收到的反馈，也不与新3次采样批次混算。

## 分析与展示

主指标为最终版本同时通过公开诊断与强保留测试。区间按题目聚类，组间共享同题与同初稿的配对关系。原始公开诊断用于反馈核验、原曲线与停止版本选择；强测重执行不能覆写这些历史信息。

同时报告初错修复、初对回退、公开通过但保留失败、Token与调用成本、各错误类型真实支持数、模型与重复差异。静态中文SVG和真实机制案例来自实际保存结果，尚未完成的实验不生成真实网页证据。

`normalize`在完整物理响应、原公开评测及全五版强测齐全后，另存原21字段格式的`unified-records.csv.gz`，不覆盖原统一表。新评分名为`base_and_full_disjoint_holdout_pass_v2`，与旧Mini分开。题号、记录键与父版本键使用批次内稳定伪名；独立初稿编号另存`lineage.csv`，修复轮次使用`revision_round`。字段缺失统计与资产SHA保存在同目录。`publish`只接受完整真实新批次和独立的完整旧批复核，匿名快照、六张新SVG与一张历史复核图进入静态网站。

`scripts/system/finalize_code_feedback.py --config configs/code_repair_extension.json --once`只检查就绪状态，未齐时返回2并给出缺项。使用`--watch --output ../repair_v2/deliveries`后，每30秒等待完整采集和全轮强测，再依次分析、规范化、发布、构建、运行全部检查并生成唯一暂存交付目录；原本地交付目录保持独立。运行状态及各步日志保存在该批次目录。
