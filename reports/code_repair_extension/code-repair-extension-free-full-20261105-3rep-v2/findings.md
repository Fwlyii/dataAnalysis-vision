# 代码反馈补充实验：完整结果

批次 `code-repair-extension-free-full-20261105-3rep-v2`。计划164道独立题，当前公开配对164题、强测试配对164题；每题每模型3份独立初稿。
已保存24600条物理响应，计划24600条。重复初稿与多模型不增加独立题目数。

执行设置：每程序内存上限768 MB，完整保留验证墙钟上限300秒；逐例限时与参考计时按固定协议执行。

生成设置：temperature=0.2，top_p=1，单次输出上限2048 Token；Qwen3额外思考模式关闭。

主指标为第4次后续生成，同时通过公开诊断与强保留测试。独立重采样各次只接收原题，其他策略沿本组历史继续生成。中间轮只测公开诊断时，不能画成强测试曲线。95%区间按题目聚类，保留同题全部模型与重复。

| 模型 | 反馈 | 初稿强测 | 终稿强测 | 终稿95%区间 | 初错修复 | 初对回退 | 总Token |
|---|---|---:|---:|---:|---:|---:|---:|
| Qwen2.5-7B-Instruct | 独立重采样 | 382/492 | 379/492 | [70.5%, 82.9%] | 11/110 | 14/382 | 2184 |
| Qwen2.5-7B-Instruct | 自行检查 | 382/492 | 392/492 | [73.8%, 85.2%] | 18/110 | 8/382 | 5644 |
| Qwen2.5-7B-Instruct | 仅通过状态 | 382/492 | 398/492 | [75.0%, 86.4%] | 17/110 | 1/382 | 5814 |
| Qwen2.5-7B-Instruct | 错误定位诊断 | 382/492 | 401/492 | [75.8%, 86.8%] | 21/110 | 2/382 | 5924 |
| Qwen2.5-7B-Instruct | 单个失败反例 | 382/492 | 401/492 | [76.0%, 86.6%] | 22/110 | 3/382 | 5909 |
| Qwen2.5-7B-Instruct | 多个失败反例 | 382/492 | 399/492 | [75.4%, 86.6%] | 19/110 | 2/382 | 6911 |
| Qwen3-8B | 独立重采样 | 370/492 | 377/492 | [69.9%, 82.7%] | 18/122 | 11/370 | 1837 |
| Qwen3-8B | 自行检查 | 370/492 | 376/492 | [69.9%, 82.5%] | 9/122 | 3/370 | 4431 |
| Qwen3-8B | 仅通过状态 | 370/492 | 395/492 | [74.4%, 85.8%] | 25/122 | 0/370 | 4654 |
| Qwen3-8B | 错误定位诊断 | 370/492 | 409/492 | [77.4%, 88.2%] | 39/122 | 0/370 | 4909 |
| Qwen3-8B | 单个失败反例 | 370/492 | 418/492 | [79.9%, 89.8%] | 48/122 | 0/370 | 4904 |
| Qwen3-8B | 多个失败反例 | 370/492 | 421/492 | [80.5%, 90.2%] | 51/122 | 0/370 | 5671 |

## 反馈相对单反例的配对比较

| 模型 | 反馈 | 配对程序份数 | 赢 / 输 | 差值 pp | 95%区间 pp |
|---|---|---:|---:|---:|---:|
| Qwen2.5-7B-Instruct | 独立重采样 | 492 | 11/33 | -4.47 | [-7.72, -1.42] |
| Qwen2.5-7B-Instruct | 自行检查 | 492 | 7/16 | -1.83 | [-4.07, +0.20] |
| Qwen2.5-7B-Instruct | 仅通过状态 | 492 | 9/12 | -0.61 | [-2.64, +1.22] |
| Qwen2.5-7B-Instruct | 错误定位诊断 | 492 | 6/6 | -0.00 | [-1.63, +1.42] |
| Qwen2.5-7B-Instruct | 多个失败反例 | 492 | 7/9 | -0.41 | [-2.24, +1.22] |
| Qwen3-8B | 独立重采样 | 492 | 10/51 | -8.33 | [-13.21, -3.86] |
| Qwen3-8B | 自行检查 | 492 | 1/43 | -8.54 | [-12.60, -4.88] |
| Qwen3-8B | 仅通过状态 | 492 | 5/28 | -4.67 | [-7.93, -1.63] |
| Qwen3-8B | 错误定位诊断 | 492 | 10/19 | -1.83 | [-4.67, +1.02] |
| Qwen3-8B | 多个失败反例 | 492 | 11/8 | +0.61 | [-1.02, +2.24] |

区间属于预先规定的探索性两两比较，未做多重比较校正；不要把接近零的小差值概括为普遍优势。

## 评测与范围

- 当前成功、历轮曾通过公开测试、首次公开通过即停止分别报告。隐藏结果不参与选择版本。
- 中间停止版本没有强测时，停止策略强测试成功率保持未知，不能借终稿结果补值。
- 全五版强测使用独立严格配对队列：164/164题；公开曲线与强测曲线分别标注。公开已知失败可以确定联合任务失败，未执行的保留输入仍为未测。
- 基础设施中断或不完整评测保持缺失；不按模型成败剔题。完整块监测的分母和缺失记录见integrity.json。
- planned-endpoint-bounds.csv与planned-contrast-bounds.csv保留原计划分母，给未知结果两种极端下的逻辑上下界；这些不是实测失败，也不是置信区间。
- 反馈逐条从父版本public对象重建，隐藏输入和结果不进入构造器；父版本与各组完整历史均核验。
- cases_checked统计实际逐例执行。加载失败时，原failed_cases是整套输入的逻辑失败标签，与blocked_cases、unchecked_cases重叠；特征表另列executed_failed_cases，主通过率按程序计数。
- 例子按可观察的结果规则确定性选择，只用于解释机制，不代表平均效果。不存在的错误或回退类别不编造。
- 置信区间按题目聚类；单题或零分母不能支撑区间推断。

## 真实案例

### diagnostic_repair：Qwen2.5-7B-Instruct / HumanEval/19

第3份初稿，错误定位诊断，版本2→3。该步强测：失败→通过；整链初稿／终稿：失败／通过。

实际传入的反馈：
```text
Diagnostic test feedback:
{"diagnostic_status": "FAIL", "diagnostic": {"kind": "load", "stage": "load", "error_type": "KeyError", "error_message": "1", "line": 29, "column": 29, "source_line": "sorted_numberals = [str(numeral_map[numeral]) for numeral in sorted_numberals]", "candidate_traceback": [{"filename": "<candidate>", "function": "<module>", "line": 36, "column": 7, "source_line": "print(sort_numbers('three one five'))  # Output: 'one three five'"}, {"filename": "<candidate>", "function": "sort_numbers", "line": 29, "column": 29, "source_line": "    sorted_numberals = [str(numeral_map[numeral]) for numeral in sorted_numberals]"}]}}

Review your previous implementation against the original task. Correct any correctness issue you find; otherwise preserve the working implementation. Return the complete implementation in one Python code block, including required imports. Preserve the specified interface.
```

代码差异：
```diff
--- before.py
+++ after.py
@@ -26,7 +26,7 @@
     # Convert the list of numberal words to their numeric values, sort them, and convert back to numberal words
     sorted_numberals = [numeral_map[numeral] for numeral in numberals]
     sorted_numberals.sort()
-    sorted_numberals = [str(numeral_map[numeral]) for numeral in sorted_numberals]
+    sorted_numberals = [list(numeral_map.keys())[list(numeral_map.values()).index(num)] for num in sorted_numberals]
     
     # Convert the sorted list of numeric values back to a space-delimited string
     return ' '.join(sorted_numberals)
```

### semantic_repair：Qwen2.5-7B-Instruct / HumanEval/54

第2份初稿，多个失败反例，版本1→2。该步强测：失败→通过；整链初稿／终稿：失败／通过。

实际传入的反馈：
```text
Diagnostic test feedback:
{"diagnostic_status": "FAIL", "failures": [{"case_index": 0, "input": "['eabcdzzzz', 'dddzzzzzzzddeddabc']", "expected": "True", "actual": "False", "error_type": "OutputMismatch", "error_message": "Returned output differs from the diagnostic oracle."}, {"case_index": 1, "input": "['abcd', 'dddddddabc']", "expected": "True", "actual": "False", "error_type": "OutputMismatch", "error_message": "Returned output differs from the diagnostic oracle."}, {"case_index": 2, "input": "['dddddddabc', 'abcd']", "expected": "True", "actual": "False", "error_type": "OutputMismatch", "error_message": "Returned output differs from the diagnostic oracle."}], "test_summary": {"total_cases": 7, "passed_cases": 4, "failed_cases": 3, "cases_checked": 7, "blocked_cases": 0, "unchecked_cases": 0}}

Review your previous implementation against the original task. Correct any correctness issue you find; otherwise preserve the working implementation. Return the complete implementation in one Python code block, including required imports. Preserve the specified interface.
```

代码差异：
```diff
--- before.py
+++ after.py
@@ -2,4 +2,4 @@
     """
     Check if two words have the same characters.
     """
-    return sorted(s0) == sorted(s1)
+    return set(s0) == set(s1)
```

### regression：Qwen2.5-7B-Instruct / HumanEval/50

第1份初稿，自行检查，版本1→2。该步强测：通过→失败；整链初稿／终稿：通过／失败。

实际传入的反馈：
```text
Review your previous implementation against the original task. Correct any correctness issue you find; otherwise preserve the working implementation. Return the complete implementation in one Python code block, including required imports. Preserve the specified interface.
```

代码差异：
```diff
--- before.py
+++ after.py
@@ -2,11 +2,10 @@
     """
     returns encoded string by shifting every character by 5 in the alphabet.
     """
-    return "".join([chr(((ord(ch) + 5 - ord("a")) % 26) + ord("a")) for ch in s])
-
+    return "".join([chr(((ord(ch) - ord('a') + 5) % 26) + ord('a')) for ch in s if ch.isalpha()])
 
 def decode_shift(s: str):
     """
     takes as input string encoded with encode_shift function. Returns decoded string.
     """
-    return "".join([chr(((ord(ch) - 5 - ord("a")) % 26) + ord("a")) for ch in s])
+    return "".join([chr(((ord(ch) - ord('a') - 5) % 26) + ord('a')) for ch in s if ch.isalpha()])
```

### diagnostic_hidden_gap：Qwen2.5-7B-Instruct / HumanEval/22

第1份初稿，错误定位诊断，版本4→5。该步强测：失败→失败；整链初稿／终稿：失败／失败。

实际传入的反馈：
```text
Diagnostic test feedback:
{"diagnostic_status": "PASS"}

Review your previous implementation against the original task. Correct any correctness issue you find; otherwise preserve the working implementation. Return the complete implementation in one Python code block, including required imports. Preserve the specified interface.
```

代码差异：
```diff
(代码文本未改变)
```

