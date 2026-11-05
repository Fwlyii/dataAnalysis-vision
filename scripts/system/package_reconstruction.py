"""Package the runnable research website and editable figure sources; stdlib only."""
import argparse
import ast
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTENSION_REPORTS = Path('reports/code_repair_extension')
EXTENSION_TABLES = (
    'summary.csv', 'public-curves.csv', 'strong-curves.csv', 'strong-endpoints.csv',
    'contrasts.csv', 'planned-endpoint-bounds.csv', 'planned-contrast-bounds.csv',
    'initial-error-support.csv',
)
LEGACY_TABLES = (
    'legacy-vs-strong-summary.csv', 'legacy-vs-strong-curves.csv', 'strong-contrasts.csv',
    'execution-accounting.json', 'reverse-change-audit.json', 'reverse-change-audit.csv',
)
SECRET = re.compile(rb'(?:sk-[A-Za-z0-9_-]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')

LAUNCHER = '''"""启动知微展示系统：python3 启动系统.py [--port 8770]。"""
import argparse
import functools
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

p = argparse.ArgumentParser(description="启动知微研究展示系统")
p.add_argument("--port", type=int, default=8770)
p.add_argument("--no-open", action="store_true")
args = p.parse_args()
handler = functools.partial(SimpleHTTPRequestHandler, directory=str(Path(__file__).resolve().parent / "网站"))
try:
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
except OSError:
    p.exit(1, "端口无法使用，请用 --port 指定其他端口。\\n")
url = f"http://127.0.0.1:{args.port}"
print("知微研究展示系统：" + url, flush=True)
print("Ctrl+C 停止。全部图表读取本地保存结果。", flush=True)
if not args.no_open:
    threading.Timer(.4, lambda: webbrowser.open(url)).start()
try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    server.server_close()
'''

REBUILD = '''"""从随包冻结统计重新绘制SVG并更新网站；Python标准库即可。"""
import csv
import importlib.util
import io
import json
import shutil
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parent
source = root / "科研源图"
spec = importlib.util.spec_from_file_location("research_atlas", source / "scripts/figures/build_research_atlas.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.build()
shutil.copytree(source / "app/assets/research", root / "网站/assets/research", dirs_exist_ok=True)
catalog_path = source / "app/data/research-charts.json"
shutil.copy2(catalog_path, root / "网站/data/research-charts.json")
catalog = json.loads(catalog_path.read_text())
with zipfile.ZipFile(root / "网站/assets/research-svg.zip", "w", zipfile.ZIP_DEFLATED) as archive:
    archive.write(catalog_path, "图表目录与数值.json")
    for chart in catalog["charts"]:
        archive.write(source / "app" / chart["file"], chart["id"] + ".svg")
        rows = chart["data"]
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        archive.writestr(chart["id"] + ".csv", "\\ufeff" + buffer.getvalue())
print("37张图稿及数值图包已更新，刷新网站即可。")
'''

EXTENSION_REBUILD = '''"""从匿名聚合结果重绘代码反馈图；不读取请求，不执行候选，不调用模型。"""
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parent
source = root / "代码反馈源图"
current = source / "reports/current"
legacy = source / "reports/legacy"
subprocess.run([sys.executable, "-m", "experiments.code_repair_v2.src.analyze",
                "--figures-only", str(current / "app-evidence.json"),
                "--output", str(current)], cwd=source, check=True)
subprocess.run([sys.executable, "experiments/code_repair_v2/analysis/redraw_legacy.py",
                "--report", str(legacy), "--output", str(legacy)], cwd=source, check=True)
assets = root / "网站/assets/research-extension"
assets.mkdir(parents=True, exist_ok=True)
(assets / "legacy").mkdir(exist_ok=True)
new_figures = json.loads((current / "figure-manifest.json").read_text(encoding="utf-8"))["figures"]
old_figures = json.loads((legacy / "figure-manifest.json").read_text(encoding="utf-8"))["figures"]
for figure in new_figures:
    shutil.copy2(current / figure["file"], assets / figure["file"])
for figure in old_figures:
    shutil.copy2(legacy / figure["file"], assets / "legacy" / figure["file"])
bundle = root / "网站/assets/research-feedback-svg.zip"
current_files = ["app-evidence.json", "figure-manifest.json", "summary.csv", "public-curves.csv",
                 "strong-curves.csv", "strong-endpoints.csv", "contrasts.csv",
                 "planned-endpoint-bounds.csv", "planned-contrast-bounds.csv", "initial-error-support.csv"]
legacy_files = ["strong-checks.json", "figure-manifest.json", "legacy-vs-strong-summary.csv",
                "legacy-vs-strong-curves.csv", "strong-contrasts.csv", "execution-accounting.json",
                "reverse-change-audit.json", "reverse-change-audit.csv"]
with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
    for directory, prefix, names in [
        (current, "current", current_files + [f["file"] for f in new_figures]),
        (legacy, "legacy", legacy_files + [f["file"] for f in old_figures])]:
        for name in names:
            path = directory / name
            if path.is_file():
                archive.write(path, prefix + "/" + path.name)
shutil.copy2(bundle, root.parent / "知微代码反馈SVG图包.zip")
print(f"代码反馈图已更新：{len(new_figures)}张新批图 + {len(old_figures)}张历史复核图。刷新网站即可。")
print("只重绘冻结统计；若重新研究数据，请回原仓库核验并重新发布完整快照。")
'''

EXTENSION_GUIDE = '''

五、可选的代码反馈补充批次
本包另含已通过完整性检查的代码反馈补充批次；原37张图与原统计保持独立。
补充内容直接放在“核心发现”的代码反馈部分，仍是静态长页，没有新增按钮或跳页。
六张新批SVG分别展示强测试端点、公开五版轨迹、修复与回退、Token代价、初始错误支持数、强测试五版轨迹；历史Mini→完整强测另有一张图，单独解释。
独立图包：知微代码反馈SVG图包.zip。原知微科研SVG图包.zip仍为37张原图。
代码反馈源图/仅含匿名聚合结果、公开CSV与标准库绘图代码，不含凭证、原始请求、逐程序评测、隐藏答案或oracle。
重绘：python3 重建代码反馈图.py
该命令更新随包网站内的SVG和独立补充图包，不调用模型，不重新评测代码，不改原37张图。
新的研究采集、完整强测和统计复算应回原Git仓库进行，不能把图稿重绘当作重新完成实验。
有效模型响应、含重试的HTTP尝试和独立题目数分别阅读；95%配对区间含0时不宣称稳定提升。
'''


def public_file(path):
    """Read only an explicitly allowed public file; never discover raw run files."""
    if not path.is_file() or path.is_symlink():
        raise SystemExit('补充交付缺少普通文件：' + str(path))
    if SECRET.search(path.read_bytes()):
        raise SystemExit('补充公开文件疑似包含凭证，停止打包：' + path.name)
    return path


def figure_entries(manifest, expected_count):
    figures = manifest.get('figures')
    if manifest.get('synthetic') is not False or not isinstance(figures, list) or len(figures) != expected_count:
        raise SystemExit('补充图目录必须来自完整真实批次，且图数与发布约定一致。')
    names = [row.get('file', '') for row in figures]
    if len(set(names)) != len(names) or any(not re.fullmatch(r'[\w.-]+\.svg', name) for name in names):
        raise SystemExit('补充图目录含重复或无效SVG文件名。')
    return figures


def extension_inputs(dist, report_override=None):
    """Optional supplement is copied only when the built site actually publishes it."""
    publication_path = dist / 'data/code-feedback-extension.json'
    source_publication = ROOT / 'app/data/code-feedback-extension.json'
    if not publication_path.is_file():
        if source_publication.is_file() or report_override is not None:
            raise SystemExit('补充快照尚未进入构建网站，请先重新运行 build_web_app.py。')
        return None
    publication = json.loads(public_file(publication_path).read_text(encoding='utf-8'))
    evidence = publication.get('evidence') or {}
    coverage = evidence.get('coverage') or {}
    if (evidence.get('schema') != 'course-code-repair-extension-v1' or evidence.get('synthetic') is not False
            or evidence.get('status') != 'complete' or coverage.get('complete') is not True
            or evidence.get('strong_trajectory_complete') is not True or coverage.get('missing_count') != 0):
        raise SystemExit('补充批次或全五版强测尚未完整，禁止打包为正式结果。')
    if source_publication.is_file() and source_publication.read_bytes() != publication_path.read_bytes():
        raise SystemExit('源补充快照与构建网站不一致，请重新构建后打包。')
    batch = evidence.get('batch_id', '')
    if not re.fullmatch(r'[\w.-]+', batch):
        raise SystemExit('补充批次标识无效。')
    report = Path(report_override).resolve() if report_override else ROOT / EXTENSION_REPORTS / batch
    legacy = ROOT / EXTENSION_REPORTS / 'legacy-full-recheck'
    snapshot = public_file(report / 'app-evidence.json')
    if json.loads(snapshot.read_text(encoding='utf-8')) != evidence:
        raise SystemExit('补充聚合报告与网站不是同一快照。')
    current_manifest = json.loads(public_file(report / 'figure-manifest.json').read_text(encoding='utf-8'))
    current_figures = figure_entries(current_manifest, 6)
    if current_manifest.get('batch_id') != batch or publication.get('figures') != current_figures:
        raise SystemExit('补充图目录与网站批次不一致。')
    legacy_evidence = publication.get('legacyEvidence') or {}
    checks = json.loads(public_file(legacy / 'strong-checks.json').read_text(encoding='utf-8'))
    published_checks = legacy_evidence.get('checks') or {}
    if checks.get('complete') is not True or published_checks.get('complete') is not True or any(checks.get(key) != value for key,value in published_checks.items()):
        raise SystemExit('历史强复测不完整或与网站快照不一致。')
    legacy_manifest = json.loads(public_file(legacy / 'figure-manifest.json').read_text(encoding='utf-8'))
    old_figures = figure_entries(legacy_manifest, 1)
    published_old_figures = legacy_evidence.get('figures')
    if isinstance(published_old_figures, dict):
        published_old_figures = published_old_figures.get('figures')
    if published_old_figures != old_figures:
        raise SystemExit('历史复核图目录与网站不一致。')
    public_file(legacy / 'legacy-vs-strong-summary.csv')
    files = [(snapshot, Path('reports/current/app-evidence.json')),
             (report / 'figure-manifest.json', Path('reports/current/figure-manifest.json')),
             (legacy / 'strong-checks.json', Path('reports/legacy/strong-checks.json')),
             (legacy / 'figure-manifest.json', Path('reports/legacy/figure-manifest.json'))]
    files += [(report / name, Path('reports/current') / name) for name in EXTENSION_TABLES]
    files += [(legacy / name, Path('reports/legacy') / name) for name in LEGACY_TABLES if (legacy / name).is_file()]
    for directory, figures, suffix in [(report, current_figures, ''), (legacy, old_figures, 'legacy')]:
        for figure in figures:
            source = public_file(directory / figure['file'])
            built = public_file(dist / 'assets/research-extension' / suffix / figure['file'])
            if hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(built.read_bytes()).digest():
                raise SystemExit('补充SVG与构建网站不一致：' + figure['file'])
            files.append((source, Path('reports/legacy' if suffix else 'reports/current') / figure['file']))
    for relative in [Path('project.json'), Path('experiments/code_repair_v2/src/analyze.py'),
                     Path('experiments/code_repair_v2/analysis/redraw_legacy.py'),
                     Path('experiments/code_repair_v2/ANALYSIS.md'),
                     Path('experiments/code_repair_v2/analysis/README.md')]:
        files.append((ROOT / relative, relative))
    for source, _ in files:
        public_file(source)
    bundle = public_file(dist / 'assets/research-feedback-svg.zip')
    with zipfile.ZipFile(bundle) as archive:
        expected_svgs = {row['file']: report / row['file'] for row in current_figures}
        expected_svgs.update({'legacy/' + row['file']: legacy / row['file'] for row in old_figures})
        archived_svgs = {name for name in archive.namelist() if Path(name).suffix == '.svg'}
        if archived_svgs != set(expected_svgs):
            raise SystemExit('补充图包中的SVG清单与已发布的六张新图、一张旧图不一致。')
        if any(archive.read(name) != source.read_bytes() for name, source in expected_svgs.items()):
            raise SystemExit('补充图包中的SVG与聚合报告版本不一致。')
        for member in archive.infolist():
            name = Path(member.filename)
            if (name.is_absolute() or '..' in name.parts or name.suffix not in {'.svg', '.csv', '.json', '.txt', '.md'}
                    or any(part.startswith('.') for part in name.parts)
                    or re.search(r'(responses|attempts|evaluations|oracle|resource-audit)', name.name, re.I)):
                raise SystemExit('补充图包含非公开结果文件，停止打包：' + member.filename)
            if SECRET.search(archive.read(member)):
                raise SystemExit('补充图包疑似包含凭证，停止打包。')
    return {'batch_id': batch, 'files': files, 'bundle': bundle,
            'new_figures': len(current_figures), 'legacy_figures': len(old_figures)}

GUIDE = '''知微展示系统 · 研究内容重构版

一、直接运行
解压后在此目录运行：python3 启动系统.py
浏览器地址：http://127.0.0.1:8770
如端口占用：python3 启动系统.py --port 8780
使用Python标准库，不需要npm或模型API。请通过HTTP打开，避免双击网站/index.html。

二、现在包含什么
五章：研究问题 → 采集设计 → 数据处理 → 核心发现 → 总结与反思。
总体四项：Token与质量的log关系、模型规模、简洁表达、限长反弹。
专项三项：数学中英文模板、文档证据位置、代码执行反馈。
首页保留知微五气泡；正文只有五章顶导航，页底前后翻页和左右键跳章均已删除。
核心发现按四组连续图板阅读，桌面约3–4屏：四总体、数学与文档、代码统计、真实修改案例。
主线原生SVG直接读取冻结图册和发布快照，无逐图工具按钮或内跳。
完整37张原图、7张补充图、4个完整案例，以及SVG/CSV导出、13类通用图和4个代码视图保留在 ?chapter=atlas。
清洗演示为一张完整静态Figure：A两来源四字段同时红标，B四组映射，C两条统一记录，D统一保存规则。
没有字段按钮、来源选择框或格式切换；完整21列数据仍保留。
专项9,176条匿名记录来自248,586条物理响应中的对应子集，不额外累计。

三、交给页面美化同学
网站/ 就是可运行的静态前端，src/中保留ES模块源码，可直接编辑后刷新。
网站/index.html、research.css、src/research.js：主框架、五章路由、核心发现长页和图册。
网站/src/research-home.js、research-home.css：原知微五气泡首页。
网站/src/research-content.js、research-content.css：中文章节、四维31策略和清洗演示。
网站/research-ocean.css、research-content-ocean.css：深海光学玻璃v5的全局材质与内容图解。
网站/src/research-ocean-summary.js：由同一冻结目录数值绘制四项总体发现概览。
网站/src/research-findings-compact.js、research-findings-compact.css：3–4屏主线、数学与文档的原生科研图。
网站/assets/visual/ocean-optics-v5.png：从用户参考图提取的干净背景；提示词与来源随素材保留。
网站/src/research-explorer.js、research-explorer.css：13类交互图、4代码视图。
网站/src/research-special-records.js：位置和修复匿名记录。
网站/assets/research/：全部可编辑SVG；网站/data/research-charts.json：目录与实际数值。
网站/runtime/：已生成的冻结数据脚本，页面通过本地HTTP按需读取。
内容与图表交接.md：模块接口及后续美化边界。
docs/design.md、.impeccable/design.json：当前设计规范与组件令牌；docs/design-sources.md：素材来源。

可以继续美化页面切换、布局与动画，不再添加答辩不会使用的按钮或交叉导航。
请保留图形坐标、单位、条件、来源和评分口径；
筛选、记录与导出必须对应同一集合；未知规模保持缺失；独立生成不称为反馈修复轮次。
本版图表已设计配色、直接标注、点线形状与重点数字，可继续使用SVG原图。

四、重新绘制科研图
科研源图/ 保存生成器和它实际读取的冻结统计，编辑其scripts/figures/build_research_atlas.py后运行：
python3 重建科研图册.py
该命令更新网站SVG、目录与图包。它不修改原始研究数据，不重新调用模型。
完整数据分析及采集代码保留在原Git仓库，本包用于展示、页面美化与图形重绘。
'''


def package(output, extension_report=None):
    dist = ROOT / 'app/dist'
    if not (dist / 'index.html').is_file():
        raise SystemExit('请先运行 python3 scripts/system/build_web_app.py')
    extension = extension_inputs(dist, extension_report)
    output.mkdir(parents=True, exist_ok=True)
    destination = output / '知微展示系统'
    if destination.exists():
        raise SystemExit('目标目录已存在；请保留已有修改并换一个输出目录。')
    destination.mkdir()
    shutil.copytree(dist, destination / '网站')
    (destination / '启动系统.py').write_text(LAUNCHER, encoding='utf-8')
    (destination / '重建科研图册.py').write_text(REBUILD, encoding='utf-8')
    (destination / '使用与交接.txt').write_text(GUIDE + (EXTENSION_GUIDE if extension else ''), encoding='utf-8')
    (destination / 'README.md').write_text('# 知微 · 深海光学玻璃展示系统\n\n运行 `python3 启动系统.py`，默认在本机8770端口打开。\n\n[使用与交接](使用与交接.txt) · [内容与图表交接](内容与图表交接.md) · [设计规范](docs/design.md) · [设计令牌](.impeccable/design.json) · [素材来源](docs/design-sources.md)\n\n网站为本地静态文件；37张原科研SVG与独立代码反馈补充图包分别保留。\n', encoding='utf-8')
    # Keep the designer's token and provenance documents usable in the standalone bundle.
    docs = destination / 'docs'
    docs.mkdir()
    for name in ['design.md', 'design-sources.md', 'reconstruction-handoff.md']:
        shutil.copy2(public_file(ROOT / 'docs' / name), docs / name)
    shutil.copytree(ROOT / 'docs/provenance', docs / 'provenance')
    (destination / '.impeccable').mkdir()
    shutil.copy2(public_file(ROOT / '.impeccable/design.json'), destination / '.impeccable/design.json')
    shutil.copy2(public_file(ROOT / 'experiments/code_repair_v2/ANALYSIS.md'), docs / 'code-feedback-methods.md')
    handoff = (docs / 'reconstruction-handoff.md').read_text(encoding='utf-8')
    handoff = handoff.replace('(../experiments/code_repair_v2/ANALYSIS.md)', '(code-feedback-methods.md)')
    (docs / 'reconstruction-handoff.md').write_text(handoff, encoding='utf-8')
    for original, bundled in [('(design.md)', '(docs/design.md)'),
                              ('(design-sources.md)', '(docs/design-sources.md)'),
                              ('(../.impeccable/design.json)', '(.impeccable/design.json)'),
                              ('(../README.md)', '(README.md)'),
                              ('(code-feedback-methods.md)', '(docs/code-feedback-methods.md)')]:
        handoff = handoff.replace(original, bundled)
    (destination / '内容与图表交接.md').write_text(handoff, encoding='utf-8')
    source_path = Path('scripts/figures/build_research_atlas.py')
    inputs = {source_path}
    for node in ast.walk(ast.parse((ROOT / source_path).read_text())):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {'jread', 'read_csv'}:
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                inputs.add(Path(node.args[0].value))
    for relative in sorted(inputs):
        target = destination / '科研源图' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    catalog = json.loads((ROOT / 'app/data/research-charts.json').read_text())
    (destination / '科研源图/app/data/research-charts.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf-8')
    shutil.copy2(ROOT / 'app/assets/research-svg.zip', output / '知微科研SVG图包.zip')
    if extension:
        for source, relative in extension['files']:
            target = destination / '代码反馈源图' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        (destination / '重建代码反馈图.py').write_text(EXTENSION_REBUILD, encoding='utf-8')
        shutil.copy2(extension['bundle'], output / '知微代码反馈SVG图包.zip')
    shutil.copy2(destination / '使用与交接.txt', output / '重构版_使用与交接.txt')
    report = ROOT / 'artifacts/qa/defense/report.json'
    if not report.is_file():
        report = ROOT / 'artifacts/qa/reconstruction/report.json'
    if report.is_file():
        shutil.copy2(report, destination / '浏览器检查结果.json')
    archive_path = output / '知微展示系统_重构版.zip'
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(destination.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(output))
    print(json.dumps({'website': str(destination), 'archive': str(archive_path), 'figures': len(catalog['charts']),
                      'figure_source_files': len(inputs), 'feedback_extension': None if extension is None else {
                          'batch_id': extension['batch_id'], 'new_figures': extension['new_figures'],
                          'legacy_figures': extension['legacy_figures'], 'public_source_files': len(extension['files'])}}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--extension-report', type=Path,
                        help='已发布补充批次的聚合报告目录；默认按网站 evidence.batch_id 查找')
    args = parser.parse_args()
    package(args.output.resolve(), args.extension_report)
