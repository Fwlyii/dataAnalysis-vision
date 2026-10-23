# CodePromptEval 221 道题清洗报告

生成日期：2026-10-22

## 最终结论

- 原始任务数：**221 道**
- 技术上可运行（官方参考实现通过测试）：**196 道**
- 技术上不可运行：**25 道**（23 道参考测试失败，2 道测试模板缺少目标函数）
- 语义上不建议使用：**2 道**（虽能运行，但题目描述与官方断言存在已确认的不一致）
- **推荐用于正式实验：194 道**

这里的“可运行”不是静态猜测：每道题都使用官方下载的固定项目、对应 Python 3.7–3.11 环境，并实际执行了官方参考实现与测试。

## 各难度层级

| 层级 | 总数 | 技术可运行 | 推荐使用 |
|---|---:|---:|---:|
| class_runnable | 54 | 51 | 51 |
| file_runnable | 67 | 58 | 58 |
| plib_runnable | 19 | 13 | 13 |
| project_runnable | 23 | 21 | 21 |
| self_contained | 33 | 32 | 30 |
| slib_runnable | 25 | 21 | 21 |

## 数据文件

- `benchmark_audit.csv`：221 道完整审计结果及错误详情。
- `benchmark_runnable_tasks.csv`：196 道技术可运行任务。
- `benchmark_recommended_tasks.csv`：194 道推荐任务。
- `benchmark_excluded_tasks.csv`：27 道不建议纳入正式实验的任务及原因。
- `CodePromptEval_recommended_194_tasks.csv`：可直接作为实验输入的推荐数据集，共 6208 行（194×32 个原始组合）；运行 31 个 prompt 时仍由现有配置排除未使用组合。

## 排除任务

| task_id | 项目 | 函数 | 类型 | 原因 |
|---|---|---|---|---|
| `62ece4992e6aefcf4aabbd8b` | awsteiner/o2sclpy | `force_string` | reference_test_failed | 1 error in 0.14s |
| `62ece4982e6aefcf4aabbd66` | burgerbecky/makeprojects | `was_processed` | semantic_mismatch | 题目描述要求展开绝对路径，但官方测试期待保留原始字符串，题意与断言不一致 |
| `62b8c517e0d34b282c18122e` | champax/pysolbase | `extostr` | reference_test_failed | Exception: Result not True!!! |
| `62ece4992e6aefcf4aabbd78` | cloudmesh/cloudmesh-common | `is_local` | reference_test_failed | AttributeError: 'NoneType' object has no attribute 'loader' |
| `62ece4982e6aefcf4aabbd75` | commandline/flashbake | `addignored` | reference_test_failed | 1 failed in 0.02s |
| `62b43425903eeb48555d3ea1` | cpburnz/python-sql-parameters | `_create_in_regex` | invalid_test_template | 测试模板中找不到与任务同名的目标函数，无法可靠替换并自动评分 |
| `62b43426903eeb48555d3ea2` | cpburnz/python-sql-parameters | `_create_converter` | invalid_test_template | 测试模板中找不到与任务同名的目标函数，无法可靠替换并自动评分 |
| `62ece4992e6aefcf4aabbd84` | gopad/gopad-python | `is_ipv4` | reference_test_failed | 21 errors in 0.21s |
| `6306292152e177c0ba469f0d` | jaywink/federation | `identify_request` | reference_test_failed | ImportError: failed to find libmagic.  Check your installation |
| `6306292652e177c0ba469f34` | jaywink/federation | `fetch_content_type` | reference_test_failed | Exception: Result not True!!! |
| `6306298b52e177c0ba469fdc` | jaywink/federation | `xml_children_as_dict` | reference_test_failed | ImportError: failed to find libmagic.  Check your installation |
| `6306299052e177c0ba469fe8` | jaywink/federation | `check_sender_and_entity_handle_match` | reference_test_failed | ImportError: failed to find libmagic.  Check your installation |
| `62b8b59feb7e40a82d2d1291` | pexip/os-zope | `_getTargetClass` | reference_test_failed | ModuleNotFoundError: No module named 'zope.interface' |
| `62b8b4b9eb7e40a82d2d1134` | pexip/os-zope | `namesAndDescriptions` | reference_test_failed | ModuleNotFoundError: No module named 'zope.interface' |
| `62b8b3d5eb7e40a82d2d1110` | pexip/os-zope | `_c_optimizations_available` | reference_test_failed | Exception: Result not True!!! |
| `62e4fb4d85ea9864308902e7` | pre-commit/pre-commit | `normalize_cmd` | reference_test_failed | Exception: Result not True!!! |
| `62b869eab4d922cb0e688cbf` | rak-n-rok/Krake | `generate_default_observer_schema` | reference_test_failed | ModuleNotFoundError: No module named 'factories.kubernetes' |
| `6306092e73426c38ae68ad11` | redhat-openstack/infrared | `merge_extra_vars` | reference_test_failed | FileNotFoundError: [Errno 2] No such file or directory: 'some_var_file.yml' |
| `6306093273426c38ae68ad15` | redhat-openstack/infrared | `_run_playbook` | reference_test_failed | Exception: Result not True!!! |
| `62ece4982e6aefcf4aabbd67` | santoshphilip/eppy | `vertex3tuple` | semantic_mismatch | 题目对首个顶点的前驱边界描述易导向索引 0，但官方实现/测试使用 Python 索引 -1，语义有歧义 |
| `62b463163879012d194814a6` | scieloorg/packtools | `files_list_from_zipfile` | reference_test_failed | FileNotFoundError: [Errno 2] No such file or directory: '/private/var/folders/77/z4jy32y155n2w719j_y89xpr0000gn/T/codeprompteval-benchmark-audit/projects/62b463163879012d194814a6/scieloorg---packtools/var/folders/77/z4jy |
| `62ece4992e6aefcf4aabbd87` | scrolltech/apphelpers | `build_app_logger` | reference_test_failed | 1 failed in 0.05s |
| `62b438b666fea644fe22cc78` | witten/borgmatic | `parse_arguments` | reference_test_failed | ModuleNotFoundError: No module named 'config' |
| `62b438a266fea644fe22cc2e` | witten/borgmatic | `parse_arguments` | reference_test_failed | Exception: Result not True!!! |
| `62b438a266fea644fe22cc2c` | witten/borgmatic | `make_parsers` | reference_test_failed | Exception: Result not True!!! |
| `62ece4992e6aefcf4aabbd7b` | witten/borgmatic | `write_configuration` | reference_test_failed | 1 failed in 0.16s |
| `62ece4992e6aefcf4aabbd8a` | witten/borgmatic | `load_configurations` | reference_test_failed | 1 error in 1.08s |

## 口径说明

- 参考测试失败包含缺少系统动态库、项目依赖/路径问题、测试夹具缺失，以及参考实现与断言不一致等情况；为保证公平，这些题当前统一不计入正式实验。
- 196 是“当前已准备环境下能够真实执行并通过”的数量；194 是进一步剔除两道已知语义异常题后的保守推荐数量。
- 下载的项目源码和官方断言未被修改；仅修复了压缩包中指向作者电脑的失效 Python 链接，并在临时镜像中兼容原测试写死的路径。
