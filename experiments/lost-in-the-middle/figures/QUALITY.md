# 最终图表核对记录

- 数据检查：完整 74,800 条；374 分组各 200 条；english19 主实验 45,600 条。列类型、缺失率与分布见 `derived/data_profile.json`。
- 图表契约：Python、定量分面/矩阵；PNG 300 DPI，SVG 保留文字，PDF 使用 TrueType 字体；每图有独立 CSV 源表和 README 图注。
- 程序版面审计：六组图均执行 `visual_qa.audit_layout`，未返回缺字、越界或刻度重叠问题。
- 视觉检查：逐一查看六张 PNG，核对标签、图例、坐标、数据点、区间与色阶；第二轮把热力图统一为最佳平均策略在上、每格标数值，并移动散点 NoCoT 标注避免压点。
- 格式检查：六张 PNG 和六个 SVG 通过 `check_figure.py`；PNG 元数据为 299.9994 DPI（300 DPI 的存储精度）。
- PDF 字体核对：通用检查器对 Type0 父字体给出“可能未嵌入”提示；进一步用 `pdffonts` 和 pypdf 检查所有六个 PDF 的 DescendantFonts/FontDescriptor，均发现内嵌 FontFile2。实际字体为 CID TrueType、embedded=yes，不是缺字体。
- 所有准确率轴从 0 起，模型使用颜色和点形双重编码；分类策略不以折线连接；热力图四面板色标一致，无裁掉失败记录或调整尺度制造 U 形。

本次未更改原始回答。严格 EM、首行匹配、最终包含各有语义偏差，图注已区分；中文和格式压力组的人工语义复核仍未完成。
