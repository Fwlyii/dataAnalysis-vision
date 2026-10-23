# dataAnalysis-vision

本仓库目前包含两套独立实验交付：

- [`experiments/code-prompt-eval/`](experiments/code-prompt-eval/)：`zyt` 分支的Python函数生成实验。194题、31条Prompt、3模型、每条件5次独立采样，共 **90,210条原始回答**，包含新版沙箱功能评分、Pass@1/3/5、错误原因、六组图和离线复算脚本。
- [`experiments/lost-in-the-middle/`](experiments/lost-in-the-middle/)：`fwl` 分支完成的资料读取实验。200题、31条Prompt、2模型，共 **74,800条原始回答**，结论为部分复现前置证据优势，未稳定复现完整U形。

大型原始数据和评分文件通过Git LFS保存。克隆后执行：

```bash
git lfs install
git lfs pull
```

各实验的口径、限制和复算方法以对应目录README为准。
