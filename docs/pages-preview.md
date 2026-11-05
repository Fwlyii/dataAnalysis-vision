# GitHub Pages 分支预览

主站： https://fwlyii.github.io/data-analysis-frontrefine/

图内动态升级预览： https://fwlyii.github.io/data-analysis-frontrefine/preview/chart-motion/

预览图表库： https://fwlyii.github.io/data-analysis-frontrefine/preview/chart-motion/explore.html

主站始终从main构建；预览始终从codex/lens-chart-motion构建。两个版本在同一次Pages部署中上传，分别使用各自完整的静态资源和科研数据，不将预览前端合并到main。

推送main会重新部署两个版本。推送codex/lens-chart-motion先触发Check chart-motion preview；检查成功后，由main上的Pages工作流构建两个版本、分别通过93状态真实浏览器验收，再统一发布。检查失败不会替换线上网站。需要手动重发时，在Actions里选择Deploy visualization to GitHub Pages，并从main运行。

Pages工作流固定检出自己仓库中的main及预览分支，不执行外部PR产物。工作流保留原科研保护和新鲜浏览器门禁。workflow_run由默认分支发起部署，继续使用原github-pages环境。

每个版本各有deployment.json，记录实际发布的分支、提交SHA及时间。临时checkout、浏览器截图和下载文件不进入站点产物。以后修改预览分支前端后正常推送此分支，等Actions成功，再刷新预览链接即可。
