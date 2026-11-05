# 当前系统检查

```bash
python3 scripts/system/check_web_snapshot.py
python3 scripts/system/check_visual_coverage.py
npm ci --prefix tests
npm run browser:install --prefix tests
python3 tests/run.py
python3 scripts/system/check_visual_coverage.py --browser-report artifacts/qa/after/smoke.json
python3 tests/run.py --full
```

浏览网站不需要npm。Node和Playwright仅用于开发与发布检查，依赖锁定在 `tests/package-lock.json`。

发布前实际检查93状态、五章入口、方向/实验/流程选择、每页导览与聚焦、原开场交接、图表库13图、代码4视图、空状态和真实导出。`--full`追加五种电脑宽度、逐项交互、详情、筛选、键盘、触摸、故障降级及清理测试。

当前保护清单校验1,100原有文件；184个已验收科学状态包含188个图形的结构、样式及像素一致性记录，并保留31个实际导出对照。清理前后的网页运行产物另行按SHA-256比较，确保目录整理没有改动页面。

测试默认不保存截图或视频。临时JSON、CSV、SVG输出在 `artifacts/qa/`，不进入Git；如需一次性截图，使用 `QA_SCREENSHOTS=1`。原有导航可访问名称与可见文案的少量不一致已在此前检查中记录，不能将自动检查当作完整无障碍认证。
