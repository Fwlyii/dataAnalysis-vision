# GitHub Pages 发布

仓库：<https://github.com/Fwlyii/data-analysis-frontrefine>，发布分支 `main`。

预览：<https://fwlyii.github.io/data-analysis-frontrefine/>。

推送 main 后，`.github/workflows/pages.yml` 用 Python 构建 `app/dist`，校验科学与源码保护契约，并实际运行当前93状态浏览器检查，然后上传静态产物并发布。只有对应提交的工作流成功，网站才完成更新；刷新不会跳过构建和部署过程。

常用入口：

- `?intro=1`：强制查看开场，仍尊重系统“减少动态效果”。
- `?intro=0`：直接看首页。
- `explore.html?mode=explore#case-1`：图表库。

站点当前使用静态研究快照，没有常驻后端。页面字体、图标、图表库脚本全部随站点发布。仓库不再保存审查录像和历史设计截图；现用素材及许可证继续随源码保留，测试临时结果不提交。

详细更新和检查要求见 [视觉优化流程](visual-refinement-workflow.md)。
