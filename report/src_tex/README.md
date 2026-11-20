# 课程报告 LaTeX 源码

主文件为 `tjumain.tex`。正文保留六个一级部分（实验目的、小组分工、项目介绍、实验过程、实验结论、实验体会），附录 A 至 G 集中收纳数据字典、提示策略与实验配置、关键代码清单、系统界面与多视图截图、工程目录与依赖映射、统计结果全表及课程评分对照。

## 编译方式

需要安装 TeX Live（含 `xelatex`、`xdvipdfmx`、`ctex`、`xecjk`、`fandol`、`newtx` 等宏包）。在 `report/src_tex/` 目录下运行：

```sh
sh build.sh
```

脚本将编译三遍以刷新目录、图表索引与交叉引用，最终输出至 `report/课程报告.pdf`。
