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
五、代码反馈补充批次
当前主展示的核心发现第三页读取已完成的代码反馈发布快照。
六张补充SVG分别展示强测端点、公开五版轨迹、修复与回退、Token代价、初稿错误支持数、强测五版轨迹；历史Mini→完整强测复核另存一张图。
原37图包与七张代码反馈图包分别保留。独立图包为知微代码反馈SVG图包.zip。
代码反馈源图/ 保存匿名聚合结果、公开CSV、复核摘要和标准库绘图代码。
运行：python3 重建代码反馈图.py
该命令重绘六张补充图、一张历史复核图并更新网站图包，复用冻结统计。
公开测试负责生成模型可见反馈；完整通过要求公开诊断与保留测试同时通过，保留输入不交给模型。区间含0的配对差异按不确定结果解释。
完整研究复算、采集和评测在原Git仓库进行，方法见docs/code-feedback-methods.md。
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

GUIDE = '''知微展示系统 · 景深版

一、运行
解压后在本目录运行：python3 启动系统.py
默认地址：http://127.0.0.1:8770
端口占用时：python3 启动系统.py --port 8780
使用Python标准库与本地保存结果。请通过HTTP访问页面。

二、内容与入口
主展示为五屏：研究问题 → 实验设计 → 数据处理 → 核心发现 → 结论与反思。
核心发现分三页、七图版：总体规律I–IV；数学与文档V–VI；代码执行反馈VII。
顶部导航定位各屏；图版保留模型/题库切换、说明、数据表、悬停读数及键盘操作。
代码页保留两模型、六策略、五版本轨迹、配对比较、四个补充视图和四个真实案例。
浏览器支持时可用“全屏放映”；窄屏与矮屏使用自然滚动。

历史完整图册：网站/legacy.html?chapter=atlas。
原?chapter=atlas地址兼容到这一入口。它保留37张原图、7张补充图、完整案例、13类通用交互图和4个代码视图。

三、源码与研究口径
网站/ 是可运行静态前端，保留HTML、CSS、JavaScript、本地依赖和冻结数据。
网站/index.html：五屏结构、图版、说明与弹窗。
网站/zhiwei.css：当前主界面光场、玻璃、字体、响应式和动态效果。
网站/src/zhiwei.js：读取快照、汇总展示值、绘制原生SVG和联动控制。
网站/runtime/：已生成的离线数据脚本。
网站/assets/research/ 与网站/assets/research-extension/：44张独立科研SVG。
网站/data/research-charts.json：原37图的目录、条件、真实数值和来源。
网站/src/research*.js 与legacy.html：历史完整图册与探索实现。
docs/design.md：当前设计；docs/design-sources.md：素材许可与来源；内容与图表交接.md：接口和研究口径。

主页面选用267,610份物理响应：248,586 − 5,576份历史Mini批次 + 24,600份完整补充批次。
仓库累计273,186份，原CSV与补充CSV各自保存；9,176条专项记录已在原248,586份之中。
补充批次：164题 × 2模型 × 3份初稿 ×（1共享初稿＋6策略×4次修订）＝24,600份物理响应。
字段、评分、分母、区间和来源沿用冻结统计。MoE骨干参数、激活参数与稠密参数按各自公开口径说明。

四、图稿重绘
科研源图/ 保存原37图生成器及实际使用的冻结统计。
运行：python3 重建科研图册.py
它更新网站内SVG、目录和图包，复用已保存统计。
当前主展示的原生SVG由网站/src/zhiwei.js读取同一组快照绘制。
完整采集与统计复算保留在原Git仓库；本包用于运行展示、页面维护与图稿重绘。
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
    for relative in ('index.html', 'src/zhiwei.js'):
        entry = destination / '网站' / relative
        entry.write_text(entry.read_text(encoding='utf-8').replace(
            'python3 app/launch.py', 'python3 启动系统.py'), encoding='utf-8')
    (destination / '启动系统.py').write_text(LAUNCHER, encoding='utf-8')
    (destination / '重建科研图册.py').write_text(REBUILD, encoding='utf-8')
    (destination / '使用与交接.txt').write_text(GUIDE + (EXTENSION_GUIDE if extension else ''), encoding='utf-8')
    (destination / 'README.md').write_text('# 知微 · 景深展示系统\n\n运行 `python3 启动系统.py`，默认在本机8770端口打开。\n\n[使用与交接](使用与交接.txt) · [内容与图表交接](内容与图表交接.md) · [设计说明](docs/design.md) · [素材来源](docs/design-sources.md)\n\n主展示为五屏、核心发现三页七图版。`网站/legacy.html?chapter=atlas` 保留44张独立科研图、完整案例与原探索视图。\n', encoding='utf-8')
    # Keep the designer's token and provenance documents usable in the standalone bundle.
    docs = destination / 'docs'
    docs.mkdir()
    for name in ['design.md', 'design-sources.md', 'reconstruction-handoff.md', 'model-spec-sources.md']:
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
                              ('(model-spec-sources.md)', '(docs/model-spec-sources.md)'),
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
    statistics = destination / 'scripts/analysis/derive_concise_ci.py'
    statistics.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(public_file(ROOT / 'scripts/analysis/derive_concise_ci.py'), statistics)
    report = ROOT / 'artifacts/qa/zhiwei/report.json'
    if not report.is_file():
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
