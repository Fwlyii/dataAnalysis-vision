# 数据下载与当前统计口径

[← 项目首页](../README.md#data) · [字段字典](data_dictionary.md) · [复算](../docs/reproducibility.md) · [来源与伦理](../docs/collection-and-ai-use.md)

| 目录 | 内容 |
|---|---|
| `raw/` | 各实验原始材料，保持源字节；外层名称按实验整理 |
| `processed/` | 分实验规范表、题目/提示、修复事件和统一匿名特征 |
| `quality/` | 唯一性、缺失值、排除和评分适用范围 |
| `inventory/` | 原始字节、文件来源和处理产物的校验清单 |
| `data_dictionary.md` | 字段含义、类型、单位、来源和缺失策略 |

原统一表 `processed/all_records.csv.gz` 保存 248,586 条物理响应：推理 74,400、文档问答 74,800、代码生成 90,210、文档位置 3,600、历史代码修复 5,576。补充反馈的 24,600 条另存于[补充批次统一表](../reports/code_repair_extension/code-repair-extension-free-full-20261105-3rep-v2/unified-format/)，当前主页面选用 267,610 条。

<a id="download"></a>
## 获取 Git LFS 数据

压缩表、归档和完整响应使用 Git LFS。GitHub 网页或未安装 LFS 的克隆可能只得到以 `version https://git-lfs.github.com/spec/v1` 开头的指针，它不是 CSV/GZIP 数据。

安装 Git LFS 后，在仓库根目录执行：

```bash
git lfs install
git lfs pull --include='data/processed/all_records.csv.gz' --exclude=''
```

这会获取复算原五项实验与科研行数校验所需的统一匿名表。需要完整清洗和来源验证时，下载全部保存材料：

```bash
git lfs pull --include='*' --exclude=''
git lfs fsck
```

获取指定方向时可使用 `git lfs pull --include='data/raw/对应目录/**' --exclude=''`。LFS 按仓库配置的对象地址获取，GitHub 不自动把所有大文件展开到网页下载的 ZIP；建议使用 Git 克隆并保留下载说明。

## 评分、隐私与复现边界

不同评分按 `metric_name` 分别解释，不计算跨任务总体准确率；缺失评分不填 0；评测环境排除不等同模型错误。`record_lineage.csv.gz` 是源键映射，不是网页公开快照。

网站仅加载 `app/data/` 中保存的匿名数据。教师检查数据来源时可查[原始文件清单](inventory/raw_files.json)；处理与校验方式见[复算说明](../docs/reproducibility.md)。目录中的既有清单属于对应保存批次的记录，不能替代当前浏览器页面的筛选计数。
