# GitHub Pages 发布

[← 项目首页](../README.md) · [测试说明](../tests/README.md) · [访问路径](pages-preview.md)

仓库为 <https://github.com/Fwlyii/dataAnalysis-vision>，主分支是 `main`，站点地址为 <https://fwlyii.github.io/dataAnalysis-vision/>。网站是否已经更新，以该提交的部署工作流结果为准。

## 自动检查与发布

推送 `main` 后，[pages.yml](../.github/workflows/pages.yml) 执行课程交付结构和文档链接检查，下载科研校验需要的单个匿名统一表，再运行入口、五屏、历史图册与科研保护检查。验证通过且仓库已启用 Pages 时，上传 `app/dist/` 并发布；尚未启用时跳过发布，保留完整检查结果。

对 `main` 的 Pull Request 运行同样的验证，不部署网站。工作流不再依赖其他仓库或独立旧预览分支。

2026-11-20 整理时，本仓库尚未启用 Pages。需要在线发布时，在仓库 Settings → Pages 选择 **GitHub Actions** 作为来源，然后手动运行工作流或推送 `main`。工作流未成功、Pages 未启用或部署仍在运行时，可使用[本地启动方式](../README.md#quick-start)预览。

验证报告保存在 Actions 的 `coursework-validation` 产物中，包含五球入口、主展示与历史图册结果。

## 发布内容

静态产物包含本地字体、SVG、四份研究快照，以及课程要求、案例报告和答辩 PDF。运行网站不发送模型请求。`app/dist/` 不提交到源码仓库，由工作流从当前源码重新构建。
