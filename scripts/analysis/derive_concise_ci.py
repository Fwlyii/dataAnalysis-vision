"""复算图版 III 中代码生成三点的 95% 区间（“简洁分步 − 默认分步”，百分点）。

研究快照只保存了各策略相对“只给答案”的区间，因此这里由逐条记录重新计算：
每题 5 次采样先按题汇总，再按题目聚类 bootstrap 5,000 次，取 2.5% 与 97.5% 分位，
做法与 runtime/code-data.js 中原有的区间一致（同样排除环境排除记录与被剔除的 T149）。

用法（在“知微可视化系统”目录）：
    python3 scripts/analysis/derive_concise_ci.py app/runtime/code-features.js
输出可直接替换 app/src/zhiwei.js 里的 CODE_CONCISE_CI。只用 Python 标准库。
"""
import json
import random
import sys
from pathlib import Path
from collections import defaultdict

PREFIX = 'window.COURSE_CODE_FEATURES='


def load(path):
    text = open(path, encoding='utf-8').read()
    if text.startswith(PREFIX):  # 还原后的浏览器脚本：{schema_version, fields, rows}
        data = json.loads(text[len(PREFIX):].rstrip().rstrip(';'))
        return dict(zip(data['fields'], map(list, zip(*data['rows']))))
    data = json.loads(text)  # 资源包里的列式存储：{fields, row_count, columns}
    return data['columns']


def main(path, draws=5000, seed=91):
    col = load(path)
    agg = defaultdict(lambda: [0, 0])  # (模型, 策略, 题目) -> [通过次数, 有效采样数]
    for i in range(len(col['question'])):
        if col['environment_excluded'][i] or col['question'][i] == 'T149':
            continue
        cell = agg[(col['model'][i], col['prompt'][i], col['question'][i])]
        cell[0] += int(col['passed'][i])
        cell[1] += 1
    out = {}
    for model in sorted({m for (m, _, _) in agg}):
        qs = sorted({q for (m, p, q) in agg if m == model and p in ('BeConcise', 'DefaultCoT')})
        a = [agg[(model, 'BeConcise', q)] for q in qs]
        b = [agg[(model, 'DefaultCoT', q)] for q in qs]
        point = sum(x[0] for x in a) / sum(x[1] for x in a) - sum(x[0] for x in b) / sum(x[1] for x in b)
        rng = random.Random(seed)
        diffs = []
        for _ in range(draws):
            idx = [rng.randrange(len(qs)) for _ in qs]
            diffs.append(sum(a[k][0] for k in idx) / sum(a[k][1] for k in idx) - sum(b[k][0] for k in idx) / sum(b[k][1] for k in idx))
        diffs.sort()
        lo, hi = diffs[int(0.025 * draws)] * 100, diffs[int(0.975 * draws) - 1] * 100
        out[model] = [round(lo, 2), round(hi, 2)]
        print(f'{model}: {point * 100:+.2f} pp, 95% [{lo:+.2f}, {hi:+.2f}], {len(qs)} 题')
    print('const CODE_CONCISE_CI = ' + json.dumps(out) + ';')


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2]
    default = next((root / directory / 'runtime/code-features.js'
                    for directory in ('app', '网站')
                    if (root / directory / 'runtime/code-features.js').is_file()),
                   root / 'app/runtime/code-features.js')
    main(sys.argv[1] if len(sys.argv) > 1 else default)
