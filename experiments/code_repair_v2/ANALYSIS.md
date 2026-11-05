# 补充实验的离线分析接口

`src/analyze.py`只读取已经保存的响应与评测，不调用模型，不执行候选代码，不修改原来的164题实验。没有真实记录时不会生成结果。

```bash
python3 experiments/code_repair_v2/src/analyze.py --config /绝对路径/config.json
# 监测进行中的真实采集，仅计算完整配对题块
python3 experiments/code_repair_v2/src/analyze.py --config /绝对路径/config.json --partial
```

默认结果写到`reports/code_repair_extension/<batch_id>/`。可用`--run-dir`和`--output`指定其他路径。统计依赖NumPy时更快；缺少NumPy时有标准库回退实现。仓库提供的研究Python运行时可直接运行。

## 输入契约

- 配置：`batch_id`、`run_dir`（或`raw_output`）、`models`、`replicates`（整数或编号列表）、`arms`、`rounds`、`bootstrap.resamples/seed`。
- `plan.json`：冻结`tasks`及`config_sha256`。
- `responses.jsonl`：每个物理请求一次，含`record_id,model,task_id,replicate,arm,round,parent_id,shared_seed_id,request,response,feedback,content,code,usage,finish_reason,config_sha256`。
- `evaluations.jsonl`：每个物理响应对应一次公开诊断评测，至少含`record_id,public,sandboxed`，可附条件字段。
- `holdout-evaluations.jsonl`：相同`record_id`的强保留评测，可覆盖原记录中对应字段。两个文件各自不得重复ID。

`public.complete=false`或缺少布尔`passed`表示未知，不能当失败。联合任务FAIL可以由任一已知失败的公开／保留分支确定；例如同预算控制通过且候选两次复现内存违规时，公开失败足以确定联合FAIL，未执行的保留输入仍明确未知。保留集遇首个真实失败早停时，可以`complete=true,outcome_known=true,passed=false,scan_complete=false`；不得把未执行的输入算成失败。联合PASS必须公开与保留两部分均完成扫描并通过。

主指标只使用初稿和第四次修改后的强保留结果。中间轮的公开诊断通过率单独画图，不补画未经测量的强测试曲线。当实际已保存全轮强测时，另以全模型×全初稿×全反馈×全五版均齐全的共同题目队列产出`strong-curves.csv`及第六张强测轨迹图；完整队列题数明确标注，不能把部分题目写成全部164题。首次公开通过即停止的候选如果未做强评测，该策略的强准确率保持未知。

强测重执行时的公开结果若有变化，原始公开记录仍用于反馈重建、轮次曲线与停止版本选择；重执行结果只用于强测试判定，并单列公开结果变动数。不得让事后重评改写模型当时实际看到的反馈。

## 配对与分母

每道题只有在所有计划模型、独立初稿重复、反馈组和轮次都有完整公开记录时，才进入公开曲线的配对题块。主结果还要求各初稿和终稿的强评测齐全。`--partial`只放宽采集完成度要求，不按成败挑选数据；`coverage.csv`和`integrity.json`逐题记录缺失项。

所有置信区间按题目聚类抽样；同一题的模型和独立初稿重复始终一起抽取。程序份数与独立题数分别报告，不能把164题×3重复称为492个独立样本。修复率和回退率分别按初错／初对分母计算，bootstrap使用簇内计数之和的比值。

所有预先列出的两两比较保存原始赢／输／平数量、差值与区间；这些是未做多重比较校正的探索性区间，报告不自动宣布显著或挑选最好的一组。

同时输出原计划分母下的未知结果上下界：所有未知都取最不利／最有利结果时，准确率和反馈差值分别可能在哪个范围。它们是缺失敏感性的逻辑边界，不是把未知填成实测失败，也不是另一种置信区间。

## 完整性与输出

原诊断字段按阶段解释：`cases_checked`为实际逐例评测数。`load_failed=true`时，语法或加载异常使整组测试无法进入逐例运行；原`failed_cases`保留测试组逻辑失败标签，与`blocked_cases`、`unchecked_cases`重叠。审计单独校验该形状，普通执行仍要求已测数等于通过数加逐例失败数。特征表另存加载标记、阻断、未执行与实际逐例失败数；主通过率和错误支持数始终按程序统计。

`features.csv`按策略展开五版轨迹，六组会复用同一初稿，属于逻辑行。物理计数须按`physical_record_id`去重；独立的`unified-format/unified-records.csv.gz`直接保存唯一物理响应，初稿只出现一次。

分析逐条核验共享初稿、父版本、各组完整历史、Token记账、候选代码hash和沙箱标记。反馈通过`protocol.feedback_message(arm,{public:...})`重建比较，构造器拿不到隐藏结果。

输出包括：完整性与覆盖表、公开五版曲线、强测初稿与终稿、初错修复／初对回退、公开过但保留失败、Token与调用数、初始错误支持数、配对比较、确定性选择的真实代码差异与反馈示例。不存在的示例类别明确列为未观测，不生成假案例。

中文SVG保留真实坐标、条件、分母、区间及来源；匿名`app-evidence.json`不含原始记录键、时间戳或原始题号。`coverage.complete`控制主终稿结果是否齐全，`strong_trajectory_complete`独立标识全轮强测是否齐全；`request_accounting`将有效模型响应、实际HTTP尝试与同一物理请求的额外重试分开，没有尝试日志时保持null。分析不直接改当前展示网页。

轨迹图采用固定显示规则：公开与强测全部点合并取范围，两侧各外扩5个百分点，向整10个百分点取界并限制在0–100%，最小跨度30个百分点；两图共用同一范围并直接标注。六组使用固定颜色、线型和点形；共享初稿只画一个灰色标记。端点主图保持0–100%完整尺度。仅连接五个实测版本，不平滑或插补；区间在主图与结果表中呈现。

案例按固定模型、反馈、题目与初稿顺序选择。修复必须在相邻版本的已知强测中从失败转为通过，回退要求相反转变；诊断案例来自实际收到错误诊断的组，反例案例来自实际收到输入／期望／实际结果的组，并逐字核对原公开反馈。中间版本未知时保持未测，不借整链终稿给某一步贴上修复标签。缺少合格案例的类别在匿名快照和页面中明确记录。生成参数和执行预算随聚合快照保存，真实SVG注明完整基准版本。

`tests/test_repair_v2_analysis.py`只用明确标记的合成夹具验证分母、缺失、早停、公开与隐藏分离等逻辑，不调用模型或执行代码。合成结果被限制在临时`work/`路径，图稿带水印且禁止生成app快照。
