# 当前前端测试

- `browser/`：从当前源码发现路由，检查真实页面和交互。
- `fixtures/`：源码/研究保护清单、已验收科学对照及31项导出基线；不包含录像或截图库。
- `run.py`：临时启动本地静态服务，执行检查并关闭该服务。
- `package.json` / `package-lock.json`：仅测试使用的锁定依赖，不进入网页运行包。

在仓库根目录运行：

```bash
npm ci --prefix tests
npm run browser:install --prefix tests
python3 tests/run.py
python3 tests/run.py --full
```

当前机器已有Chromium时自动使用 `/snap/bin/chromium`；其他机器使用安装的Playwright浏览器，也可指定 `CHROMIUM_PATH`。测试默认不录制视频、不保存截图，临时结果写入忽略的 `artifacts/qa/`。完整维护说明见 `docs/web-checks.md`。

科学对照仍保留逐条件记录与源指纹，不能为了通过检查直接改写保护哈希或导出基线。大量旧优化产物可从Git历史查询，不是当前测试依赖。
