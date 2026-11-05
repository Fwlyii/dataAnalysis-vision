"""Build the static Chinese research app using the Python standard library."""
import base64
import csv
import gzip
import hashlib
import importlib.util
import json
import re
import shutil
import io
import zipfile
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'project.json').is_file())
APP=ROOT/'app'


def _module(source, namespace, dependency=None):
    if dependency:
        source=re.sub(r'import\s*\{([\s\S]*?)\}\s*from\s*[\'"]\./model.js[\'"];?',lambda m:'const {'+m.group(1)+'} = '+dependency+';',source,count=1)
    for stem,ns in [('libraries','_libraries'),('code-interactions','_codeInteractions')]:
        source=re.sub(r'import\s*\*\s*as\s*(\w+)\s*from\s*[\'\"]\./'+stem+r'.js[\'\"];?',lambda m:'const '+m.group(1)+' = '+ns+';',source)
    names=re.findall(r'export\s+(?:async\s+)?(?:function|const|let|class)\s+(\w+)',source)
    source=re.sub(r'\bexport\s+','',source)
    return f'const {namespace} = (() => {{\n{source}\nreturn {{{",".join(names)}}};\n}})();\n'


def build():
    # Research figures are generated from frozen aggregate tables with stdlib only.
    atlas_spec=importlib.util.spec_from_file_location('research_atlas',ROOT/'scripts/figures/build_research_atlas.py')
    atlas_module=importlib.util.module_from_spec(atlas_spec)
    atlas_spec.loader.exec_module(atlas_module)
    atlas_module.build()
    chart_catalog=json.loads((APP/'data/research-charts.json').read_text())
    with zipfile.ZipFile(APP/'assets/research-svg.zip','w',zipfile.ZIP_DEFLATED) as archive:
        archive.write(APP/'data/research-charts.json','图表目录与数值.json')
        archive.writestr('使用说明.txt','知微科研图册\n\n全部图表为可编辑SVG，文字、坐标和真实数据均保留。每图配有数值CSV；条件、单位和来源请随图保留。页面动画与整体切换可独立美化。\n')
        for chart in chart_catalog['charts']:
            archive.write(APP/chart['file'],Path(chart['file']).name)
            values=chart.get('data') or []
            if values:
                buffer=io.StringIO(newline='')
                writer=csv.DictWriter(buffer,fieldnames=list(values[0]))
                writer.writeheader();writer.writerows(values)
                archive.writestr(chart['id']+'.csv','\ufeff'+buffer.getvalue())
    spec=importlib.util.spec_from_file_location('demo_evidence',ROOT/'scripts/system/build_demo_evidence.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    evidence=module.build()
    vendor_meta=json.loads((APP/'assets/vendor/visualization-libraries.json').read_text())
    for package in vendor_meta['packages']:
        path=APP/'assets/vendor'/package['file']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=package['sha256']:
            raise ValueError('Local visualization dependency changed: '+package['file'])
        if not (APP/'assets/vendor'/package['license_file']).is_file():
            raise ValueError('Missing visualization dependency license.')
    runtime=APP/'runtime'
    runtime.mkdir(exist_ok=True)
    summary=json.loads((APP/'data/summary.json').read_text())
    logos={p.name:'data:image/svg+xml;base64,'+base64.b64encode(p.read_bytes()).decode() for p in sorted((APP/'assets/logos').glob('*.svg'))}
    runtime.joinpath('summary.js').write_text('window.COURSE_SUMMARY='+json.dumps(summary,ensure_ascii=False,separators=(',',':'))+';\nwindow.COURSE_EVIDENCE='+json.dumps(evidence,ensure_ascii=False,separators=(',',':'))+';\nwindow.COURSE_LOGOS='+json.dumps(logos)+';\n')
    features=gzip.decompress((APP/'data/features.json.gz').read_bytes()).decode()
    research=json.loads((APP/'data/research-evidence.json').read_text())
    figdir=ROOT/'reports/figures/publication'
    figures=json.loads((figdir/'figure-metadata.json').read_text())
    figure_keys=figures.get('figures') or [p.stem for p in sorted(figdir.glob('*.svg'))]
    figures['figures']={key:(figdir/(key+'.svg')).read_text() for key in figure_keys}
    runtime.joinpath('publication.js').write_text('window.COURSE_RESEARCH='+json.dumps(research,ensure_ascii=False,separators=(',',':'))+';\nwindow.COURSE_PUBLICATION='+json.dumps(figures,ensure_ascii=False,separators=(',',':'))+';\n')
    method_path=APP/'data/method-evidence.json'
    method_features=APP/'data/method-features.json.gz'
    if method_path.exists():
        runtime.joinpath('summary.js').write_text(runtime.joinpath('summary.js').read_text()+'window.COURSE_METHODS='+method_path.read_text().rstrip()+';\n')
    method_script=''
    if method_features.exists():
        method_script='window.COURSE_METHOD_FEATURES='+gzip.decompress(method_features.read_bytes()).decode().rstrip()+';\n'
    runtime.joinpath('features.js').write_text('window.COURSE_FEATURES='+features.rstrip()+';\n'+method_script)
    runtime.joinpath('summary.js').write_text(runtime.joinpath('summary.js').read_text()+'window.COURSE_FEATURE_VERSION='+json.dumps(hashlib.sha256(runtime.joinpath('features.js').read_bytes()).hexdigest()[:12])+';\n')
    code_path=APP/'data/code-evidence.json'
    code={}
    if code_path.exists():
        code=json.loads(code_path.read_text())
        code['scatter_spec']=json.loads((APP/'data/code-scatter.vl.json').read_text())
        code_figures=ROOT/'reports/figures/code_generation'
        code_meta=json.loads((code_figures/'figure-metadata.json').read_text())
        if code_meta['source_evidence_sha256']!=hashlib.sha256(code_path.read_bytes()).hexdigest():
            raise ValueError('Code figure evidence changed; rebuild with scripts/figures/plot_code_generation.py.')
        code['figures']={key:(code_figures/filename).read_text() for key,filename in code_meta['figures'].items()}
        packed_code=(APP/'data/code-features.json.gz').read_bytes()
        if hashlib.sha256(packed_code).hexdigest()!=code['features_sha256']:
            raise ValueError('Code scores and evidence belong to different snapshots.')
        code_features=gzip.decompress(packed_code).decode()
        runtime.joinpath('code-features.js').write_text('window.COURSE_CODE_FEATURES='+code_features.rstrip()+';\n')
        code['feature_version']=hashlib.sha256(runtime.joinpath('code-features.js').read_bytes()).hexdigest()[:12]
    runtime.joinpath('code-data.js').write_text('window.COURSE_CODE='+json.dumps(code,ensure_ascii=False,separators=(',',':'))+';\n')
    bundle=_module((APP/'src/libraries.js').read_text(),'_libraries')
    bundle+=_module((APP/'src/model.js').read_text(),'_model')
    bundle+=_module((APP/'src/charts.js').read_text(),'_charts','_model')
    bundle+=_module((APP/'src/code-interactions.js').read_text(),'_codeInteractions','_model')
    bundle+=_module((APP/'src/code-study.js').read_text(),'_codeStudy','_model')
    main=(APP/'src/app.js').read_text()
    main=re.sub(r'import\s*\{([\s\S]*?)\}\s*from\s*[\'"]\./model.js[\'"];?',lambda m:'const {'+m.group(1)+'} = _model;',main,count=1)
    main=re.sub(r'import\s*\*\s*as\s*charts\s*from\s*[\'"]\./charts.js[\'"];?','const charts = _charts;',main,count=1)
    main=re.sub(r'import\s*\*\s*as\s*codeStudy\s*from\s*[\'\"]\./code-study.js[\'\"];?','const codeStudy = _codeStudy;',main,count=1)
    runtime.joinpath('app.js').write_text('(()=>{\n"use strict";\n'+bundle+main+'\n})();\n')
    story=json.loads((APP/'data/story-evidence.json').read_text())
    story['figures']={p.stem:p.read_text() for p in sorted((APP/'assets/story').glob('*.svg'))}
    runtime.joinpath('story-data.js').write_text('window.LENS_STORY='+json.dumps(story,ensure_ascii=False,separators=(',',':'))+';\n')
    shutil.copy2(APP/'src/story.js',runtime/'story.js')
    shutil.copy2(APP/'src/story-charts.js',runtime/'story-charts.js')
    narrative=json.loads((APP/'data/narrative-evidence.json').read_text())
    positions={'begin':'Position 1','start':'Position 1','front':'Position 1','middle':'Position 10','end':'Position 20','last':'Position 20','back':'Position 20'}
    document_profiles=[]
    for row in summary['cells']:
        if row['dataset']=='document_qa' and row['task']=='document_qa' and row['documents']==20:
            document_profiles.append({'model':row['model'],'task':positions[row['position']],
                'prompt':row['prompt'],'questions':row['questions'],
                'score_pct':100*row['scores'][2]/row['n'],
                'mean_tokens':row['tokens']/row['token_n']})
    with (ROOT/'reports/code_generation/conditions.csv').open(encoding='utf-8-sig') as stream:
        code_profiles=[{'model':row['model'],'task':'CodePromptEval','prompt':row['prompt'],
            'questions':int(row['questions']),'score_pct':100*float(row['pass_1']),
            'mean_tokens':float(row['mean_output_tokens'])}
            for row in csv.DictReader(stream) if row['prompt']!='__all']
    narrative['profiles_by_direction']={'reasoning':narrative['profiles'],
        'document_qa':document_profiles,'code_generation':code_profiles}
    for direction,config in narrative['directions'].items():
        for model in config['models']:
            for task in config['groups']:
                rows=[r for r in narrative['profiles_by_direction'][direction] if r['model']==model and r['task']==task]
                if len(rows)!=31 or len({r['prompt'] for r in rows})!=31:
                    raise ValueError(f'Incomplete narrative profiles: {direction}/{model}/{task}')
    (APP/'data/narrative-evidence.json').write_text(json.dumps(narrative,ensure_ascii=False,separators=(',',':'))+'\n')
    narrative['figures']={p.stem:p.read_text() for p in sorted((APP/'assets/narrative').glob('*.svg'))}
    runtime.joinpath('narrative-data.js').write_text('window.LENS_NARRATIVE='+json.dumps(narrative,ensure_ascii=False,separators=(',',':'))+';\n')
    shutil.copy2(APP/'src/narrative.js',runtime/'narrative.js')
    for name in ['intro.js','refinement.js','gateway.js','interaction.js']:
        shutil.copy2(APP/'src'/name,runtime/name)
    index=APP/'explore.html'
    markup=index.read_text()
    for asset in ['styles.css','refinement.css','content-layout.css','palette.css','interaction.css','runtime/refinement.js','runtime/interaction.js','runtime/summary.js','runtime/publication.js','runtime/code-data.js','runtime/app.js']:
        digest=hashlib.sha256((APP/asset).read_bytes()).hexdigest()[:12]
        markup=re.sub(r'([\"\"])'+re.escape(asset)+r'(?:\?v=[a-f0-9]+)?([\"\"])',lambda m:m.group(1)+asset+'?v='+digest+m.group(2),markup)
    index.write_text(markup)
    story_index=APP/'index.html'
    markup=story_index.read_text()
    for asset in ['story.css','refinement.css','content-layout.css','palette.css','interaction.css','intro.css','gateway.css','runtime/gateway.js','runtime/intro.js','runtime/refinement.js','runtime/interaction.js','runtime/story-data.js','runtime/story.js','runtime/story-charts.js','runtime/narrative-data.js','runtime/narrative.js']:
        digest=hashlib.sha256((APP/asset).read_bytes()).hexdigest()[:12]
        markup=re.sub(r'([\"\"])'+re.escape(asset)+r'(?:\?v=[^\"\']+)?([\"\"])',lambda m:m.group(1)+asset+'?v='+digest+m.group(2),markup)
    story_index.write_text(markup)
    dist=APP/'dist'
    if dist.exists():shutil.rmtree(dist)
    dist.mkdir()
    for name in ['index.html','explore.html','styles.css','story.css','refinement.css','content-layout.css','palette.css','interaction.css','intro.css','gateway.css']:
        shutil.copy2(APP/name,dist/name)
    for name in ['assets','runtime']:
        shutil.copytree(APP/name,dist/name,dirs_exist_ok=True)
    shutil.copytree(APP/'src',dist/'src',dirs_exist_ok=True)
    for name in ['research.css','research-content.css','research-explorer.css','research-home.css','research-feedback-extension.css','research-ocean.css','research-content-ocean.css','research-findings-compact.css']:
        shutil.copy2(APP/name,dist/name)
    (dist/'data').mkdir(exist_ok=True)
    for name in ['summary.json','demo-evidence.json','research-charts.json','research-content.json']:
        shutil.copy2(APP/'data'/name,dist/'data'/name)
    for name in ['special-records.json.gz']:
        if (APP/'data'/name).exists():shutil.copy2(APP/'data'/name,dist/'data'/name)
    supplement=APP/'data/code-feedback-extension.json'
    if supplement.exists():
        publication=json.loads(supplement.read_text())
        measured=publication.get('evidence') or {}
        if measured.get('synthetic') is not False or measured.get('status')!='complete' or measured.get('coverage',{}).get('complete') is not True or measured.get('strong_trajectory_complete') is not True:
            raise ValueError('Code feedback supplement is not a fully measured real batch')
        for chart in publication['figures']:
            if not (dist/'assets/research-extension'/chart['file']).is_file():raise ValueError('Missing supplementary SVG')
        shutil.copy2(supplement,dist/'data'/supplement.name)
        # Keep the protected 37-figure archive intact; the measured extension
        # has its own SVG/CSV pack and an anonymous provenance snapshot.
        feedback_archive=APP/'assets/research-feedback-svg.zip'
        with zipfile.ZipFile(feedback_archive,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.write(supplement,'补充实验证据与图表目录.json')
            archive.writestr('使用说明.txt','代码执行反馈补充实验\n六组反馈、三份独立初稿及完整保留测试。\n新批次与历史Mini复核分别解释，不能合并独立样本。\n全部SVG可编辑；请保留坐标、区间、分母、资源预算与测试口径。\n')
            for path in sorted((APP/'assets/research-extension').rglob('*')):
                if path.is_file() and path.suffix in {'.svg','.csv'}:
                    archive.write(path,str(path.relative_to(APP/'assets/research-extension')))
        shutil.copy2(feedback_archive,dist/'assets'/feedback_archive.name)
    for name in ['findings.md','README.md']:
        shutil.copy2(ROOT/'reports/baseline'/name,dist/'data'/f'analysis-{name}')
    shutil.copy2(ROOT/'data/processed/data_dictionary.tsv',dist/'data/data_dictionary.tsv')
    shutil.copy2(ROOT/'docs/assignment/数据分析和可视化-题目2.pdf',dist/'data/course-assignment.pdf')
    shutil.copy2(ROOT/'docs/assignment/数据分析和可视化-题目2.pdf',APP/'data/course-assignment.pdf')
    for name in ['chart-coverage.md','demo-guide.md','insight-audit.md']:
        path=ROOT/'docs'/name
        if path.exists():shutil.copy2(path,dist/'data'/name)
    # A live preview may retain the previous ES modules. Version local imports
    # and the entry stylesheet/script together so a refresh cannot mix shells.
    modules={p.name:hashlib.sha256(p.read_bytes()).hexdigest()[:12] for p in (dist/'src').glob('*.js')}
    for path in (dist/'src').glob('*.js'):
        source=path.read_text()
        source=re.sub(r'([\'\"])(\./([\w.-]+\.js))(?:\?v=[a-f0-9]+)?\1',
            lambda m:m.group(1)+m.group(2)+'?v='+modules[m.group(3)]+m.group(1) if m.group(3) in modules else m.group(0),source)
        path.write_text(source)
    markup=(dist/'index.html').read_text()
    markup=re.sub(r'<meta name="code-feedback-extension"[^>]*>\s*','',markup)
    if supplement.exists():
        supplement_sha=hashlib.sha256(supplement.read_bytes()).hexdigest()[:12]
        markup=markup.replace('</head>',f'<meta name="code-feedback-extension" content="data/code-feedback-extension.json?v={supplement_sha}">\n</head>')
    for asset in ['research.css','research-content.css','research-explorer.css','research-home.css','research-feedback-extension.css','research-ocean.css','research-content-ocean.css','research-findings-compact.css','src/research.js']:
        digest=hashlib.sha256((dist/asset).read_bytes()).hexdigest()[:12]
        markup=re.sub(r'([\'\"])'+re.escape(asset)+r'(?:\?v=[a-f0-9]+)?([\'\"])',
            lambda m:m.group(1)+asset+'?v='+digest+m.group(2),markup)
    (dist/'index.html').write_text(markup)
    print('知微研究系统已构建：app/dist（请通过本地HTTP服务打开）。')
    return dist


if __name__=='__main__':build()
