# 前端与科研检查

在仓库根目录运行 `python3 tests/check_presentation.py` 可构建并检查当前展示、历史图册和科研保护；使用临时本地服务，完成后自动关闭。首次运行前安装下述锁定的浏览器依赖。

仅检查课程交付结构和文档跳转，可运行 `python3 scripts/system/check_coursework.py`。完整科研校验需要先取得原统一表，下载方式见[数据说明](../data/DOWNLOAD.md#download)。

当前主展示为Claude「景深」五屏界面，浏览器回归入口是 `browser/zhiwei.mjs`。原 `browser/defense.mjs` 继续验证 `legacy.html` 的历史完整图册与旧展示。

## 当前主界面

在仓库根目录安装锁定依赖并启动服务：

```bash
npm ci --prefix tests
npm run browser:install --prefix tests
python3 app/launch.py --port 8770
```

在另一个终端执行：

```bash
BASE_URL=http://127.0.0.1:8770/ node tests/browser/zhiwei.mjs
BASE_URL=http://127.0.0.1:8770/ node tests/browser/zhiwei-gate.mjs
```

`CHROMIUM_PATH` 可指定本机浏览器。当前套件核对五章导航、三页核心发现、七图版、模型与题库切换、说明/数据表、代码视图、桌面/手机布局和资源错误。结果及截图写入忽略目录 `artifacts/qa/zhiwei/`。

五球入口套件另外核对开场跳过与重播、五球跳转和返回、前进/后退、章节深链接、键盘与触屏、减少动态效果、桌面/平板/手机/矮屏布局及无障碍。结果及截图写入 `artifacts/qa/zhiwei-gate/`。

## 科研与历史兼容

```bash
python3 scripts/system/check_reconstruction.py
BASE_URL=http://127.0.0.1:8770/legacy.html node tests/browser/defense.mjs
```

科研检查覆盖图包与冻结数值、真实记录数量以及1,100项保护文件。`fixtures/research-protection.json` 与科学对照保留原验收指纹；界面更新不重写科研保护哈希。

`run.py`、`browser/smoke.mjs` 和 `browser/reconstruction.mjs` 保留历史路由及布局基线。它们用于对应历史入口的维护，不代表当前主界面的控件或屏数。

代码反馈实验的既有单元测试位于 `test_repair_v2_*.py`，独立于页面测试。测试依赖仅用于验证，不进入网站运行包。当前构建不调用模型API；完整研究复算入口见仓库README。
