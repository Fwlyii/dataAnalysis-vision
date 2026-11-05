"""Redraw the legacy Mini/Full comparison from aggregate CSV only.

No saved model requests, candidate execution, dataset or credentials are needed.
"""
from pathlib import Path
import argparse
import csv
import sys

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'project.json').is_file())
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from experiments.code_repair_v2.src.analyze import Figure,COLORS,write_json
ARMS=("resample","self_review","pass_fail","counterexample")
LABELS={"resample":"独立重采样","self_review":"自行检查","pass_fail":"仅通过状态","counterexample":"单个失败反例"}


def redraw(report,output=None):
    report=Path(report).resolve();out=Path(output or report).resolve();out.mkdir(parents=True,exist_ok=True)
    with (report/'legacy-vs-strong-summary.csv').open(encoding='utf-8-sig') as handle:
        summary=list(csv.DictReader(handle))
    models=sorted({r['model'] for r in summary})
    if len(summary)!=len(models)*len(ARMS):raise ValueError('Expected every old feedback group for each model')
    if any(int(r['tasks'])!=164 for r in summary):raise ValueError('This finalized comparison requires all164 paired tasks')
    figure=Figure('旧候选重新检验：Mini 与完整保留测试',
        '同一批 164 题、同一份保存代码；公开结果没有改变。空心＝原 Mini，实心＝此次完整强测。',
        184+len(models)*353)
    y=145
    for model in models:
        figure.text(42,y,model.split('/')[-1],23,weight=650)
        for tick in [60,70,80,90,100]:
            figure.text(280+710*(tick-60)/40,y+29,str(tick)+'%',12,color='#526574',anchor='middle')
        y+=58
        for arm in ARMS:
            row=next(r for r in summary if r['model']==model and r['arm']==arm)
            before,after=int(row['legacy_final_pass']),int(row['strong_final_pass'])
            figure.text(50,y+5,LABELS[arm],17)
            for tick in [60,70,80,90,100]:
                x=280+710*(tick-60)/40;figure.line(x,y-18,x,y+18,'#e3e9eb')
            a=280+710*(before/164*100-60)/40;b=280+710*(after/164*100-60)/40
            figure.line(a,y,b,y,COLORS[arm],3);figure.dot(a,y,COLORS[arm],6,True);figure.dot(b,y,COLORS[arm],6)
            figure.text(1150,y+5,f'{before} → {after} / 164',16,COLORS[arm],anchor='end');y+=62
        y+=47
    figure.footer('legacy-full-recheck','事后复核：0 次新模型调用；全部 5,576 物理候选已知。程序级判定与逐例执行数分别记录。')
    figure.save(out/'01-mini-full-final.svg')
    manifest={'batch_id':'legacy-full-recheck','synthetic':False,'complete':True,'figures':[
        {'id':'legacy-mini-full-final','file':'01-mini-full-final.svg','title':'旧 Mini 与完整保留测试终稿对照',
         'data_file':'legacy-vs-strong-summary.csv'}]}
    write_json(out/'figure-manifest.json',manifest)
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();redraw(args.report,args.output)
