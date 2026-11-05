"""Build the Chinese research SVG atlas from frozen summaries (standard library only)."""
from pathlib import Path
import csv
import html
import json
import math
import re
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'app/assets/research'
CATALOG = ROOT / 'app/data/research-charts.json'
PALETTE = {'paper':'#042735','ink':'#f5fbff','muted':'#b5d1de','grid':'#315361','teal':'#61e6d3','clay':'#ff967f','blue':'#76ccff','gold':'#f4cf84','violet':'#d6c3ff'}
COLORS = [PALETTE[k] for k in ['teal','clay','blue','gold','violet']]
MODELS = {'deepseek':'DeepSeek Flash','hy4':'HY4 preview','qwen':'Qwen2.5 7B','qwen3':'Qwen3 8B','Qwen2.5-7B':'Qwen2.5 7B','Qwen3-8B':'Qwen3 8B','Qwen/Qwen2.5-7B-Instruct':'Qwen2.5 7B','Qwen/Qwen3-8B':'Qwen3 8B'}
TASKS = {'gsm8k':'GSM8K','math500':'MATH500','mmlu':'MMLU-Pro','document_qa':'文档问答','CodePromptEval':'代码生成'}
ARMS = {'resample':'独立重采样','self_review':'自行检查','pass_fail':'仅通过状态','counterexample':'具体失败反例'}
P = PALETTE
charts = []

def read_csv(name):
    with (ROOT/name).open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    for row in rows:
        for k,v in row.items():
            try:
                if v is not None and v!='': row[k]=float(v)
            except (ValueError,TypeError): pass
    return rows

def jread(name): return json.loads((ROOT/name).read_text())
def esc(v): return html.escape(str(v),quote=True)
def fmt(v,d=1):
    if v is None:return '—'
    return f'{v:,.{d}f}'.rstrip('0').rstrip('.') if d else f'{v:,.0f}'
def nice_ticks(lo,hi):
    raw=(hi-lo)/4
    power=10**math.floor(math.log10(raw)) if raw>0 else 1
    fraction=raw/power
    step=next(v for v in [1,2,2.5,5,10] if v>=fraction)*power
    first=math.ceil(lo/step)*step
    return [round(first+i*step,8) for i in range(int((hi-first)/step)+1)]
def short_prompt(p):
    names={'DefaultCoT':'分步回答','NoCoT':'直接回答','BeConcise':'简洁分步','ChineseCoT':'中文模板','BulletPoints':'项目符号','NoSpaces':'无空格','OnlyNumbers':'仅数字','NoProperGrammar':'简化语法','AbbreviateWords':'单词缩写'}
    if p in names:return names[p]
    for prefix,label in [('WordLimit','词数'),('CharLimit','字母'),('TokenLimit','Token'),('StepLimit','步数'),('ChineseCoT','中文限字')]:
        if p.startswith(prefix+'('):return f'{label} {p.split("(")[1].rstrip(")")}'
    return p

class SVG:
    def __init__(self,title,subtitle,source,note='',height=620):
        self.height=height
        self.parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}" role="img" aria-labelledby="chart-title chart-desc"><title id="chart-title">{esc(title)}</title><desc id="chart-desc">{esc(subtitle+"。"+note)}</desc><rect width="1000" height="{height}" fill="{P["paper"]}"/><style>text{{font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif;font-variant-numeric:tabular-nums}}.point{{cursor:default}}.point:hover{{stroke:#142b3d;stroke-width:2.5}}</style>']
        self.text(42,43,title,27,weight=650)
        self.text(42,76,subtitle,15,color=P['muted'])
        self.line(42,96,958,96,P['grid'])
        self.text(42,height-55,note,14,color=P['muted'])
        self.text(42,height-27,'来源：'+source,12.5,color=P['muted'])
    def add(self,s):self.parts.append(s)
    def text(self,x,y,t,size=15,color=None,anchor='start',weight=None,rotate=None):
        transform=f' transform="rotate({rotate} {x} {y})"' if rotate is not None else ''
        self.add(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" fill="{color or P["ink"]}" text-anchor="{anchor}"'+(f' font-weight="{weight}"' if weight else '')+transform+f'>{esc(t)}</text>')
    def line(self,x1,y1,x2,y2,color=None,width=1,dash=None):
        self.add(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{color or P["grid"]}" stroke-width="{width}"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>')
    def rect(self,x,y,w,h,fill,rx=0):
        self.add(f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(0,w):.2f}" height="{max(0,h):.2f}" rx="{rx}" fill="{fill}"/>')
    def dot(self,x,y,r,color,label='',shape=0):
        if shape%3==1:
            self.add(f'<rect class="point" x="{x-r:.2f}" y="{y-r:.2f}" width="{2*r}" height="{2*r}" rx="1" fill="{color}"><title>{esc(label)}</title></rect>')
        elif shape%3==2:
            self.add(f'<path class="point" d="M{x:.2f},{y-r-1:.2f} L{x+r+1:.2f},{y+r:.2f} L{x-r-1:.2f},{y+r:.2f} Z" fill="{color}"><title>{esc(label)}</title></path>')
        else:self.add(f'<circle class="point" cx="{x:.2f}" cy="{y:.2f}" r="{r}" fill="{color}"><title>{esc(label)}</title></circle>')
    def path(self,points,color,width=3,dash=None,fill='none'):
        d=' '.join(('M' if i==0 else 'L')+f'{x:.2f},{y:.2f}' for i,(x,y) in enumerate(points))
        self.add(f'<path d="{d}" fill="{fill}" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>')
    def legend(self,labels,colors=None,y=121):
        colors=colors or COLORS
        x=48
        for i,label in enumerate(labels):
            self.line(x,y-4,x+21,y-4,colors[i%len(colors)],3)
            self.dot(x+10,y-4,3.5,colors[i%len(colors)],shape=i)
            self.text(x+29,y,label,14)
            x+=max(130,32+len(label)*8.5)
    def axes(self,xlabel,ylabel,xmin=0,xmax=100,ymin=0,ymax=100,left=86,right=946,top=160,bottom=474,xticks=None,yticks=None,yfmt=None,xfmt=None):
        self.bounds=(left,right,top,bottom)
        sx=lambda v:left+(v-xmin)/(xmax-xmin or 1)*(right-left)
        sy=lambda v:bottom-(v-ymin)/(ymax-ymin or 1)*(bottom-top)
        xticks=xticks if xticks is not None else nice_ticks(xmin,xmax)
        yticks=yticks if yticks is not None else nice_ticks(ymin,ymax)
        for v in yticks:
            yy=sy(v);self.line(left,yy,right,yy)
            self.text(left-13,yy+5,(yfmt(v) if yfmt else fmt(v)),14,anchor='end',color=P['muted'])
        for v in xticks:
            xx=sx(v);self.line(xx,bottom,xx,bottom+5,P['muted'])
            self.text(xx,bottom+26,(xfmt(v) if xfmt else fmt(v)),14,anchor='middle',color=P['muted'])
        self.line(left,bottom,right,bottom,P['muted'])
        self.text((left+right)/2,bottom+55,xlabel,15,anchor='middle')
        self.text(left,top-20,ylabel,15,color=P['muted'])
        return sx,sy
    def finish(self):return ''.join(self.parts)+'</svg>'

def save(id,topic,title,subtitle,source,description,svg,data,role='support',filters=None):
    DEST.mkdir(parents=True,exist_ok=True)
    (DEST/(id+'.svg')).write_text(svg.finish(),encoding='utf-8')
    charts.append({'id':id,'topic':topic,'title':title,'subtitle':subtitle,'source':source,'description':description,'file':'assets/research/'+id+'.svg','role':role,'filters':filters or {},'width':1000,'height':svg.height,'data':data})

def line_chart(id,topic,title,subtitle,source,series,xlabel,ylabel,note='',role='support',ymax=100,ymin=0,filters=None,percent=True):
    svg=SVG(title,subtitle,source,note)
    svg.legend([s['name'] for s in series])
    xs=[r['x'] for s in series for r in s['data']]
    sx,sy=svg.axes(xlabel,ylabel,min(xs),max(xs),ymin,ymax,xticks=sorted(set(xs)),yfmt=(lambda v:fmt(v)+'%') if percent else None)
    rows=[]
    for si,s in enumerate(series):
        col=COLORS[si%len(COLORS)];data=sorted(s['data'],key=lambda r:r['x'])
        svg.path([(sx(r['x']),sy(r['y'])) for r in data],col,dash='7 5' if si==1 else None)
        for i,r in enumerate(data):
            x,y=sx(r['x']),sy(r['y'])
            if 'low' in r:
                svg.line(x,sy(r['low']),x,sy(r['high']),col,1.6)
                svg.line(x-5,sy(r['low']),x+5,sy(r['low']),col,1.4)
                svg.line(x-5,sy(r['high']),x+5,sy(r['high']),col,1.4)
            svg.dot(x,y,5,col, f'{s["name"]}，{xlabel}={fmt(r["x"])}，{ylabel}={fmt(r["y"])}',si)
            if len(series)<=2 and (len(data)<=7 or i in (0,len(data)-1)):
                dy=(-13 if si==0 else 23)
                svg.text(x,y+dy,fmt(r['y'])+('%' if percent else ''),14,col,anchor='middle',weight=650)
            rows.append({'series':s['name'],**r})
    if id=='feedback-rounds-qwen3':
        final_count=round(series[3]['data'][-1]['y']*164/100)
        self_count=round(series[1]['data'][-1]['y']*164/100)
        svg.text(745,211,f'{final_count} / 164',30,P['gold'],weight=650)
        svg.text(745,237,'具体反例 · 第五版完整通过',14,P['muted'])
        svg.text(745,260,f'比自行检查多通过{final_count-self_count}题',14,P['muted'])
    if id=='position-nine-profile':
        first=series[1]['data'][0]['y']-series[0]['data'][0]['y']
        last=series[1]['data'][-1]['y']-series[0]['data'][-1]['y']
        svg.text(660,212,f'{fmt(first)} → {fmt(last)} pp',27,P['clay'],weight=650)
        svg.text(660,238,'首位到末位，模型优势缩小',14,P['muted'])
    if id=='limits-rebound-main':
        dat={r['x']:r['y'] for r in series[0]['data']}
        svg.text(615,211,f'输出变为约{fmt(dat[10]/dat[100])}倍',27,P['clay'],weight=650)
        svg.text(645,238,'提示字母数：100 → 10',14,P['muted'])
    save(id,topic,title,subtitle,source,note,svg,rows,role,filters)

def paired_bars(id,topic,title,subtitle,source,labels,groups,values,note='',ylabel='规则评分（%）',ymax=100,role='support',filters=None):
    svg=SVG(title,subtitle,source,note);svg.legend(groups)
    n=len(labels);sx,sy=svg.axes('',ylabel,0,n,0,ymax,xticks=[])
    left,right,top,bottom=svg.bounds;groupw=(right-left)/n;barw=min(44,groupw*.72/len(groups))
    rows=[]
    for i,label in enumerate(labels):
        center=left+groupw*(i+.5)
        for j,g in enumerate(groups):
            val=values[j][i];x=center+(j-(len(groups)-1)/2)*(barw+6)-barw/2;y=sy(val)
            svg.rect(x,y,barw,bottom-y,COLORS[j],3)
            svg.text(x+barw/2,y-9,fmt(val),14,COLORS[j],anchor='middle',weight=650)
            rows.append({'category':label,'series':g,'value':val})
        svg.text(center,bottom+29,label,14,anchor='middle')
    save(id,topic,title,subtitle,source,note,svg,rows,role,filters)

def hbars(id,topic,title,subtitle,source,rows,value_key,label_key,note='',role='support',color=None,unit='%',xmin=0,xmax=None):
    rows=list(rows);height=max(620,190+len(rows)*29)
    svg=SVG(title,subtitle,source,note,height)
    left,right,top,bottom=260,900,150,height-110
    vals=[r[value_key] for r in rows];xmax=xmax if xmax is not None else max(vals)*1.16
    sx=lambda v:left+(v-xmin)/(xmax-xmin)*(right-left)
    if xmin<0:svg.line(sx(0),top-5,sx(0),bottom,P['muted'],1.4)
    for k in range(5):
        v=xmin+(xmax-xmin)*k/4;x=sx(v)
        svg.line(x,top-8,x,bottom,P['grid']);svg.text(x,bottom+26,fmt(v)+unit,13,anchor='middle',color=P['muted'])
    for i,r in enumerate(rows):
        y=top+(i+.5)*(bottom-top)/len(rows);v=r[value_key];col=color or (P['teal'] if v>=0 else P['clay'])
        svg.text(left-16,y+5,r[label_key],14,anchor='end')
        svg.rect(min(sx(0),sx(v)),y-8,abs(sx(v)-sx(0)),16,col,4)
        svg.text(sx(v)+(9 if v>=0 else -9),y+5,fmt(v)+unit,14,col,anchor='start' if v>=0 else 'end',weight=650)
    save(id,topic,title,subtitle,source,note,svg,rows,role)

def heatmap(id,topic,title,subtitle,source,row_labels,col_labels,matrix,note='',role='support',diverging=False,format_value=None,filters=None):
    height=max(620,210+len(row_labels)*25)
    svg=SVG(title,subtitle,source,note,height)
    left,right,top,bottom=230,940,162,height-115
    cw=(right-left)/len(col_labels);ch=(bottom-top)/len(row_labels)
    for j,label in enumerate(col_labels):svg.text(left+cw*(j+.5),top-16,label,14,anchor='middle',weight=650)
    maxabs=max(abs(v) for row in matrix for v in row) or 1
    rows=[]
    for i,label in enumerate(row_labels):
        svg.text(left-15,top+ch*(i+.5)+5,label,14,anchor='end')
        for j,v in enumerate(matrix[i]):
            t=abs(v)/maxabs if diverging else max(0,min(1,v/100))
            rgb=(41,123,129) if not diverging or v>=0 else (137,70,66)
            bg=tuple(round(a+(c-a)*(.12+.82*t)) for a,c in zip((5,35,48),rgb))
            color=f'#{bg[0]:02x}{bg[1]:02x}{bg[2]:02x}'
            x,y=left+j*cw,top+i*ch
            svg.rect(x+2,y+2,cw-4,ch-4,color,3)
            val=format_value(v) if format_value else fmt(v)
            svg.text(x+cw/2,y+ch/2+5,val,13.5,P['ink'],anchor='middle',weight=550)
            rows.append({'row':label,'column':col_labels[j],'value':v})
    save(id,topic,title,subtitle,source,note,svg,rows,role,filters)

def scatter(id,topic,title,subtitle,source,rows,xkey,ykey,xlabel,ylabel,note='',role='support',xlim=None,ylim=None,label_key=None):
    svg=SVG(title,subtitle,source,note)
    groups=list(dict.fromkeys(r.get('group','观测') for r in rows))
    svg.legend(groups)
    xs=[r[xkey] for r in rows];ys=[r[ykey] for r in rows]
    xmin,xmax=xlim or (min(0,min(xs)*1.1),max(xs)*1.18 or 1)
    ymin,ymax=ylim or (min(0,min(ys)-2),max(ys)+max(2,(max(ys)-min(ys))*.2))
    sx,sy=svg.axes(xlabel,ylabel,xmin,xmax,ymin,ymax,xticks=sorted(set(xs)) if xkey=='parameters_b' else None,xfmt=(lambda v:fmt(v,2)) if xkey=='parameters_b' else None)
    if ymin<0<ymax:svg.line(sx(xmin),sy(0),sx(xmax),sy(0),P['muted'],1.3,'5 5')
    label_boxes=[]
    point_positions=[(sx(r[xkey]),sy(r[ykey])) for r in rows]
    for i,r in enumerate(rows):
        gi=groups.index(r.get('group','观测'));c=COLORS[gi%len(COLORS)]
        svg.dot(sx(r[xkey]),sy(r[ykey]),6,c,r.get('label','')+f'：{fmt(r[xkey])} / {fmt(r[ykey])}',gi)
        if label_key and len(rows)<=12:
            label=str(r[label_key]);tw=sum(13 if ord(ch)>255 else 7 for ch in label)
            px,py=sx(r[xkey]),sy(r[ykey])
            candidates=[]
            for dy in [-13,24,-34,44,-55,66]:
                for direction in [1,-1]:
                    tx=px+12 if direction==1 else px-12-tw
                    box=(tx,py+dy-14,tx+tw,py+dy+3)
                    outside=max(0,86-box[0])+max(0,box[2]-946)+max(0,160-box[1])+max(0,box[3]-474)
                    overlap=sum(max(0,min(box[2],b[2])-max(box[0],b[0]))*max(0,min(box[3],b[3])-max(box[1],b[1])) for b in label_boxes)
                    hits=sum(box[0]-5<x<box[2]+5 and box[1]-5<y<box[3]+5 for x,y in point_positions)
                    candidates.append((outside*1000+overlap+hits*100+abs(dy)*.05,tx,py+dy,box))
            _,tx,ty,box=min(candidates,key=lambda v:v[0]);label_boxes.append(box)
            if abs(ty-py)>26:svg.line(px,py,tx+(0 if tx>px else tw),ty-5,c,1)
            svg.text(tx,ty,label,13,c)
    save(id,topic,title,subtitle,source,note,svg,rows,role)

def build():
    charts.clear()
    story=jread('app/data/story-evidence.json')
    summary=jread('app/data/summary.json')
    profiles=read_csv('reports/prompt_variants/reasoning-all-prompt-profiles.csv')
    fits=read_csv('reports/story/log-fit-diagnostics.csv')
    concise=read_csv('reports/story/concise-cross-task-points.csv')
    chinese=read_csv('reports/story/chinese-template-comparison.csv')
    position=read_csv('reports/document_positions/position-summary.csv')
    gains=read_csv('reports/document_positions/paired-model-position-contrasts.csv')
    repair=read_csv('reports/code_repair/full/curves.csv')
    repair_summary=read_csv('reports/code_repair/full/summary.csv')
    code=read_csv('reports/code_generation/conditions.csv')
    # 1. Token budgets: actual points plus declared log fit; no interpolated observations.
    for task in ['gsm8k','math500','mmlu']:
        fit=next(r for r in fits if r['model']=='qwen' and r['task']==task and r['scope']=='WordLimit')
        rs=[r for r in profiles if r['model']=='qwen' and r['task']==task and r['prompt'].startswith('WordLimit(')]
        rs.sort(key=lambda r:r['mean_tokens'])
        title=f'Token投入的边际收益：{TASKS[task]}'
        note=f'七档真实词数限制；SR = a + b·ln(Token)，样本内 R² = {fit["in_sample_r2"]:.3f}。'
        svg=SVG(title,'Qwen2.5 · 同一批200题 · 横轴为实际平均输出，不是提示上限','reports/story/log-fit-diagnostics.csv',note)
        svg.legend(['真实观测','对数拟合'],[P['clay'],P['teal']])
        rawmax=max(r['mean_tokens'] for r in rs)
        step=20 if rawmax<=100 else 50 if rawmax<=300 else 100
        xmax=math.ceil(rawmax/step)*step
        sx,sy=svg.axes('平均输出 Token','规则评分（%）',0,xmax,0,100)
        xx=[min(r['mean_tokens'] for r in rs)+(max(r['mean_tokens'] for r in rs)-min(r['mean_tokens'] for r in rs))*i/120 for i in range(121)]
        svg.path([(sx(x),sy(max(0,min(100,fit['intercept']+fit['log_token_slope']*math.log(x))))) for x in xx],P['teal'],3.5)
        for i,r in enumerate(rs):
            svg.dot(sx(r['mean_tokens']),sy(r['score_pct']),6,P['clay'],f'{r["prompt"]}: {r["mean_tokens"]:.3f} Token / {r["score_pct"]:.1f}%')
            if i in [0,3,6]:svg.text(sx(r['mean_tokens'])+10,sy(r['score_pct'])-12,fmt(r['score_pct'])+'%',15,P['clay'],weight=650)
        svg.text(735,183,'先快，后缓',25,P['teal'],weight=650)
        save('budget-log-'+task,'budget',title,'Qwen2.5 · WordLimit七档 · 200题/条件','reports/story/log-fit-diagnostics.csv',note,svg,rs,'main' if task=='gsm8k' else 'support',{'model':'qwen','task':task})
    ms=['deepseek','hy4','qwen','qwen3'];ts=['gsm8k','math500','mmlu']
    mat=[[next(r['in_sample_r2'] for r in fits if r['model']==m and r['task']==t and r['scope']=='WordLimit')*100 for t in ts] for m in ms]
    heatmap('budget-fit-comparison','budget','对数关系并非所有条件都一样','模型 × 题库 · 相同WordLimit七档拟合','reports/story/log-fit-diagnostics.csv',[MODELS[m] for m in ms],[TASKS[t] for t in ts],mat,'颜色越深，样本内拟合度越高；R²不代表因果关系。',format_value=lambda x:f'{x/100:.2f}')
    prompts=[p for p in summary['prompts']]
    if prompts and isinstance(prompts[0],dict):prompts=[p.get('id') or p.get('prompt_id') for p in prompts]
    prompts=[r['prompt'] for r in profiles if r['model']=='qwen' and r['task']=='gsm8k']
    mat=[[next(r['score_pct'] for r in profiles if r['model']=='qwen' and r['task']==t and r['prompt']==p) for t in ts] for p in prompts]
    heatmap('budget-prompt-landscape','budget','31种提示的完整评分全景','Qwen2.5 · 每个单元格200题 · 按题库分别评分','reports/prompt_variants/reasoning-all-prompt-profiles.csv',[short_prompt(p) for p in prompts],[TASKS[t] for t in ts],mat,'完整保留实际策略；每格对应真实条件，没有补造组合。')
    # 2. Scaling: known parameters only; compare task facets rather than fabricate a law.
    known={m['id']:m['parameters_b'] for m in summary['models'] if m.get('parameters_b')}
    rs=[{'model':m,'parameters_b':b,'task':t,'score_pct':next(r['score_pct'] for r in profiles if r['model']==m and r['task']==t and r['prompt']=='DefaultCoT'),'group':TASKS[t],'label':MODELS[m]} for m,b in known.items() for t in ts]
    scatter('scale-known-parameters','scale','模型规模与表现：先看已知参数的真实比较','DefaultCoT · 同题比较 · 参数量单位为十亿（B）','app/data/summary.json; reasoning-all-prompt-profiles.csv',rs,'parameters_b','score_pct','已核实参数量（B）','规则评分（%）','当前仅7.61B与8.2B两个相近规模；代际、训练和任务差异同时存在。','main',(7.3,8.55),(0,100),None)
    for task in ts:
        vals=[[next(r['score_pct'] for r in profiles if r['model']==m and r['task']==task and r['prompt']==p) for m in ms] for p in ['NoCoT','DefaultCoT','BeConcise']]
        paired_bars('scale-models-'+task,'scale',f'模型差异需要放回任务：{TASKS[task]}','同一批200题 · 三种回答组织策略','reports/prompt_variants/reasoning-all-prompt-profiles.csv',[MODELS[m] for m in ms],['直接回答','分步回答','简洁分步'],vals,'同一任务、同一策略内比较；未知参数量的模型不进入参数拟合。',filters={'task':task})
    rs=[{'model':m,'task':t,'tokens':r['mean_tokens'],'score_pct':r['score_pct'],'group':MODELS[m],'label':TASKS[t]} for m in ms for t in ts for r in profiles if r['model']==m and r['task']==t and r['prompt']=='DefaultCoT']
    scatter('scale-performance-cost','scale','更强表现与输出成本一起看','四模型 × 三题库 · DefaultCoT · 每点200题','reports/prompt_variants/reasoning-all-prompt-profiles.csv',rs,'tokens','score_pct','平均输出 Token','规则评分（%）','颜色区分模型；悬停各点查看模型和题库；不混合任务总准确率。',xlim=(0,max(r['tokens'] for r in rs)*1.12),ylim=(0,100))
    # 3. Concise: paired conditions, all 17 cross-task points, and full model/task contrast.
    base=story['baseline'];svg=SVG('保留分步，压缩表达','Qwen2.5 · GSM8K · 同一批200题','app/data/story-evidence.json','分步→简洁分步：输出减少21.5%，得分点估计91.5%→92.0%。')
    for pi,(metric,label,maxv) in enumerate([('score_pct','规则评分（%）',100),('mean_tokens','平均输出 Token',280)]):
        left=80+pi*475;right=left+390;top=174;bottom=460
        svg.text(left,135,label,18,weight=650)
        for k in range(5):
            val=maxv*k/4;y=bottom-(bottom-top)*k/4;svg.line(left,y,right,y);svg.text(left-10,y+5,fmt(val),13,anchor='end',color=P['muted'])
        for i,r in enumerate(base):
            x=left+30+i*125;y=bottom-r[metric]/maxv*(bottom-top)
            svg.rect(x,y,65,bottom-y,COLORS[i],4);svg.text(x+32,y-13,fmt(r[metric]),19,COLORS[i],anchor='middle',weight=650);svg.text(x+32,bottom+29,['直接','分步','简洁分步'][i],14,anchor='middle')
    save('concise-baseline','concise','保留分步，压缩表达','同题三策略 · 分别展示质量与开销','app/data/story-evidence.json','简洁要求在保留较好表现的同时减少输出。',svg,base,'main',{'model':'qwen','task':'gsm8k'})
    rs=[{**r,'group':('数学/选择题' if r['direction']=='Reasoning / MCQA' else '文档问答' if 'Document' in r['direction'] else '代码生成'),'label':MODELS.get(r['model'],r['model'])+' / '+TASKS.get(r['task'],r['task'])} for r in concise]
    scatter('concise-cross-task','concise','17组跨任务对照：输出都缩短','横轴为相对输出减少；纵轴为原任务得分差','reports/story/concise-cross-task-points.csv',rs,'saving','delta','输出 Token 减少（%）','得分变化（百分点）','17组全部缩短输出，15组得分点估计不降；不同任务保留各自指标。',xlim=(0,65),ylim=(-6,12))
    hbars('concise-savings','concise','省下的输出有多大？','全部17个已保存模型×任务配对','reports/story/concise-cross-task-points.csv',sorted(rs,key=lambda r:r['saving'],reverse=True),'saving','label','BeConcise 相对 DefaultCoT；显示完整范围，不只挑选最大收益。')
    mat=[[next(r['delta'] for r in concise if r['model']==m and r['task']==t) for t in ts] for m in ms]
    heatmap('concise-quality-matrix','concise','简洁后的质量变化，逐条件保留','四模型 × 三题库 · 得分差（百分点）','reports/story/concise-cross-task-points.csv',[MODELS[m] for m in ms],[TASKS[t] for t in ts],mat,'绿色表示提高，陶土色表示下降；点估计不等于等效性证明。',diverging=True)
    vals=[[next(r['mean_tokens'] for r in profiles if r['model']==m and r['task']=='math500' and r['prompt']==p) for m in ms] for p in ['DefaultCoT','BeConcise']]
    paired_bars('concise-token-pairs','concise','相同数学题，表达预算可以压缩','MATH500 · 四模型 · 默认与简洁分步','reports/prompt_variants/reasoning-all-prompt-profiles.csv',[MODELS[m] for m in ms],['分步回答','简洁分步'],vals,'每个柱组使用同一批200题。',ylabel='平均输出 Token',ymax=600)
    # 4. Limits: real requested levels, actual tokens and scoring.
    for model,task,family,id,role in [('deepseek','math500','CharLimit','limits-rebound-main','main'),('qwen','gsm8k','WordLimit','limits-word-qwen','support'),('qwen3','math500','WordLimit','limits-word-qwen3','support'),('qwen3','math500','TokenLimit','limits-token-qwen3','support')]:
        rr=[r for r in profiles if r['model']==model and r['task']==task and r['prompt'].startswith(family+'(')]
        rr.sort(key=lambda r:int(r['prompt'].split('(')[1].rstrip(')')))
        ser=[{'name':'实际输出 Token','data':[{'x':int(r['prompt'].split('(')[1].rstrip(')')),'y':r['mean_tokens']} for r in rr]}]
        maxv=math.ceil(max(r['mean_tokens'] for r in rr)/50)*50+50
        line_chart(id,'limits','越严的限制，未必越短',f'{MODELS[model]} · {TASKS[task]} · {family}真实档位','reports/prompt_variants/reasoning-all-prompt-profiles.csv',ser,'提示中的限制数量','平均实际输出 Token','词、字母与Token分别计量；提示限制是指令，非接口硬上限。',role,maxv,percent=False,filters={'model':model,'task':task,'family':family})
    rr=[]
    for m in ms:
        for t in ts:
            pair={p:next(r['mean_tokens'] for r in profiles if r['model']==m and r['task']==t and r['prompt']==p) for p in ['CharLimit(100)','CharLimit(10)']}
            rr.append({'label':MODELS[m]+' / '+TASKS[t],'ratio':pair['CharLimit(10)']/pair['CharLimit(100)'],'tokens_at_100_letters':pair['CharLimit(100)'],'tokens_at_10_letters':pair['CharLimit(10)']})
    hbars('limits-rebound-ratios','limits','从100字母收紧到10字母：反弹在哪里？','四模型 × 三题库 · 实际输出倍数','reports/prompt_variants/reasoning-all-prompt-profiles.csv',sorted(rr,key=lambda r:r['ratio'],reverse=True),'ratio','label','大于1倍表示限制更严时，实际输出反而增加。',unit='×')
    # 5. Language templates: four models, 12 exact contrasts and truncation.
    lang=[r for r in chinese if r['task']=='math500']
    labels=[MODELS[r['model']] for r in lang]
    paired_bars('language-math-score','language','中文作答模板：三模型提分，一模型略降','MATH500 · 四模型 · 默认分步 vs 中文作答模板','reports/story/chinese-template-comparison.csv',labels,['默认模板','中文模板'],[[r['default_score_pct'] for r in lang],[r['chinese_score_pct'] for r in lang]],'题目保持英文；模板对照不等于测量内部思考语言。',role='main',filters={'task':'math500'})
    paired_bars('language-math-tokens','language','四个模型，都缩短了数学作答','MATH500 · 同题200题/条件','reports/story/chinese-template-comparison.csv',labels,['默认模板','中文模板'],[[r['default_tokens'] for r in lang],[r['chinese_tokens'] for r in lang]],'输出开销下降幅度在模型之间不同。',ylabel='平均输出 Token',ymax=600)
    paired_bars('language-truncation','language','更紧凑的表达与完成情况一起看','MATH500 · 输出达到上限的比例','reports/story/chinese-template-comparison.csv',labels,['默认模板','中文模板'],[[r['default_truncation_pct'] for r in lang],[r['chinese_truncation_pct'] for r in lang]],'截断率是观测特征；不能独立证明提分机制。',ylabel='截断比例（%）',ymax=30)
    mat=[[next(r['score_difference_pp'] for r in chinese if r['model']==m and r['task']==t) for t in ts] for m in ms]
    heatmap('language-task-boundary','language','中文模板的收益有任务边界','四模型 × 三题库 · 中文减默认得分','reports/story/chinese-template-comparison.csv',[MODELS[m] for m in ms],[TASKS[t] for t in ts],mat,'MATH500的提分不能直接推广到GSM8K；所有对照保留。',diverging=True)
    rr=[{**r,'group':TASKS[r['task']],'label':MODELS[r['model']]} for r in chinese]
    scatter('language-cost-quality','language','语言模板的质量—开销折衷','每点为一个模型×题库的同题配对','reports/story/chinese-template-comparison.csv',rr,'token_saving_pct','score_difference_pp','输出 Token 减少（%）','得分变化（百分点）','右上表示既省输出又提分；右下保留省输出但评分下降的条件。',xlim=(0,50),ylim=(-6,14))
    # 6. Position profiles with measured intervals and task-native metrics.
    pm=['Qwen/Qwen2.5-7B-Instruct','Qwen/Qwen3-8B']
    rr=[r for r in position if r['metric']=='final_contains']
    series=[{'name':MODELS[m],'data':[{'x':r['position'],'y':100*r['rate'],'low':100*r['ci_low'],'high':100*r['ci_high']} for r in rr if r['model']==m]} for m in pm]
    line_chart('position-nine-profile','position','模型优势随证据位置改变','固定NoCoT · 20篇资料 · 200道相同问题 · 九个实测位置','reports/document_positions/position-summary.csv',series,'关键证据所在文档序号','最终答案包含率（%）','误差线为按题配对的95%区间；线段仅连接实际观测位置。','main',100,35)
    gr=[r for r in gains if r['metric']=='final_contains' and re.match(r'model_gain_at_position\d+$',r['comparison'])]
    series=[{'name':'Qwen3 − Qwen2.5','data':[{'x':int(r['comparison'][-2:]),'y':r['difference_pp'],'low':r['ci_low_pp'],'high':r['ci_high_pp']} for r in gr]}]
    line_chart('position-model-advantage','position','首位领先16.5个百分点，末位只领先2.5','同题模型差值 · 九个实测位置','reports/document_positions/paired-model-position-contrasts.csv',series,'关键证据所在文档序号','模型差值（百分点）','区间保留同题的模型和位置配对；不把平均差异当单题保证。',ymax=30,ymin=-10,percent=False)
    series=[{'name':MODELS[m],'data':[{'x':r['position'],'y':r['mean_output_tokens']} for r in rr if r['model']==m]} for m in pm]
    line_chart('position-output-cost','position','证据移动时，回答开销也可检查','NoCoT · 20篇资料 · 每位置200题','reports/document_positions/position-summary.csv',series,'关键证据所在文档序号','平均输出 Token','与命中率分开展示，避免双轴造成视觉误读。',ymax=math.ceil(max(r['mean_output_tokens'] for r in rr)/10)*10+10,ymin=0,percent=False)
    metrics=['paper_firstline','strict_final_em','final_contains','full_response_contains'];metric_names=['首行包含','最终严格匹配','最终答案包含','全文包含']
    rlabels=[MODELS[m]+' · '+str(p) for m in pm for p in [1,10,20]]
    mat=[[next(r['rate']*100 for r in position if r['model']==m and r['position']==p and r['metric']==met) for met in metrics] for m in pm for p in [1,10,20]]
    heatmap('position-scoring-sensitivity','position','更换评分口径，现象如何变化？','模型 × 首/中/尾位置 × 四种保存评分','reports/document_positions/position-summary.csv',rlabels,metric_names,mat,'四口径分别保留，字符串命中率不等于新的人工语义判分。')
    # 7. Feedback and separate independent-code generation supplements.
    for model,id,role in [('Qwen3-8B','feedback-rounds-qwen3','main'),('Qwen2.5-7B','feedback-rounds-qwen','support')]:
        ss=[{'name':ARMS[a],'data':[{'x':r['round'],'y':100*r['rate']} for r in repair if r['model']==model and r['arm']==a]} for a in ARMS]
        line_chart(id,'feedback','反馈内容，决定修改轮次的收益',f'{MODELS[model]} · 164题 · 初稿和四次修改','reports/code_repair/full/curves.csv',ss,'修改轮次（0＝共同初稿）','完整测试通过率（%）','只连接五个实测版本；独立重采样组不接收历史与反馈。',role,ymax=100,ymin=65)
    rs=[{'model':r['model'],'arm':r['arm'],'tokens':r['mean_all_five_tokens'],'rate':r['final_rate']*100,'group':MODELS[r['model']],'label':ARMS[r['arm']]} for r in repair_summary]
    scatter('feedback-cost-quality','feedback','修复质量与累计调用成本一起比较','两个模型 × 四种方案 · 固定生成到第五版','reports/code_repair/full/summary.csv',rs,'tokens','rate','五版累计输入与输出 Token / 题','第五版完整通过率（%）','完整历史会增加输入开销；同一模型内比较反馈方案。',xlim=(0,max(r['tokens'] for r in rs)*1.18),ylim=(70,92),label_key='label')
    rr=[r for r in repair_summary if r['model']=='Qwen3-8B']
    paired_bars('feedback-repair-regression','feedback','修好了多少，又改坏了多少？','Qwen3 · 初稿到第五版的成功集合变化','reports/code_repair/full/summary.csv',[ARMS[r['arm']] for r in rr],['初错后修好','初对后改坏'],[[r['repaired'] for r in rr],[r['regressed'] for r in rr]],'数量分别统计；最终通过率同时受到修复和回退影响。',ylabel='题目数',ymax=20)
    paired_bars('feedback-stop-budget','feedback','停止时机：真实轨迹回放可节省调用','Qwen3 · 固定五版 vs 首次诊断通过即保留','reports/code_repair/full/summary.csv',[ARMS[r['arm']] for r in rr],['固定五版','停止规则回放'],[[r['mean_all_five_tokens'] for r in rr],[r['stop_policy_mean_tokens'] for r in rr]],'停止结果来自保存轨迹的回放；实验实际仍采满五版。',ylabel='累计输入与输出 Token / 题',ymax=6000)
    allcode=[r for r in code if r['prompt']=='__all']
    ss=[{'name':MODELS[r['model']],'data':[{'x':k,'y':100*r[f'pass_{k}']} for k in range(1,6)]} for r in allcode]
    line_chart('feedback-independent-sampling','feedback','独立生成五次：覆盖收益逐渐减小','代码生成补充 · 193个有效题 · 三模型 · 31策略','reports/code_generation/conditions.csv',ss,'独立样本数 k','Pass@k（%）','这是独立采样，不是模型收到执行反馈后的代码修复。',ymax=45,ymin=0)
    errors=[k.removeprefix('error_count_') for k in allcode[0] if k.startswith('error_count_')]
    en={'assertion_failure':'断言失败','attribute_error':'属性错误','dependency_error':'依赖问题','extraction_error':'代码提取','file_error':'文件问题','index_error':'索引错误','key_error':'键错误','name_error':'名称错误','resource_error':'资源问题','runtime_error':'运行异常','syntax_error':'语法错误','timeout':'超时','type_error':'类型错误','value_error':'取值错误'}
    counts=[sum(r['error_count_'+e] for r in allcode) for e in errors]
    er=[{'label':en[e],'count':v,'error_type':e} for e,v in zip(errors,counts)]
    hbars('feedback-code-errors','feedback','代码失败类型：断言与运行问题有多大？','独立代码生成补充 · 三模型与31策略合计','reports/code_generation/conditions.csv',sorted(er,key=lambda r:r['count'],reverse=True),'count','label','错误类型按源评测保存；环境排除记录单独保留，不填为模型失败。',unit='')
    DEST.mkdir(parents=True,exist_ok=True)
    case=SVG('一个失败输入，暴露了错误的边界假设','Qwen3 · HumanEval/102 · 具体失败反例 · 已保存修改轨迹','reports/code_repair/full/examples.md','第二次收到具体反例后修正；随后同时通过诊断与额外测试。')
    case.rect(42,137,435,235,'#382c32',10)
    case.rect(523,137,435,235,'#123c3e',10)
    case.text(66,175,'初稿：交换区间端点',20,P['clay'],weight=650)
    case.text(547,175,'修改后：按规格处理倒置区间',20,P['teal'],weight=650)
    for i,line in enumerate(['if x > y:','    x, y = y, x']):case.text(70,225+i*33,line,20,P['ink'])
    for i,line in enumerate(['if x > y:','    return -1']):case.text(551,225+i*33,line,20,P['ink'])
    case.text(66,329,'实际返回 12',26,P['clay'],weight=650)
    case.text(547,329,'返回 −1',26,P['teal'],weight=650)
    case.path([(484,255),(516,255)],P['teal'],2.5)
    case.path([(509,248),(516,255),(509,262)],P['teal'],2.5)
    case.text(42,431,'失败输入',16,P['muted'])
    case.text(42,472,'choose_num(13, 12)',31,P['ink'],weight=650)
    case.text(575,431,'题目规定的期望结果',16,P['muted'])
    case.text(575,472,'−1',38,P['teal'],weight=650)
    save('feedback-real-code-case','feedback','一个失败输入，暴露了错误的边界假设','Qwen3 · HumanEval/102 · 实际修改轨迹','reports/code_repair/full/examples.md','初稿额外交换端点；具体反例帮助定位与题目规格不符的处理。',case,[{'stage':'initial','input_x':13,'input_y':12,'expected':-1,'actual':12},{'stage':'revision_2','input_x':13,'input_y':12,'expected':-1,'actual':-1}],filters={'model':'qwen3'})
    CATALOG.write_text(json.dumps({'schema':'zhiwei-research-atlas-v1','generated_at':'2026-11-05','palette':PALETTE,'chart_count':len(charts),'topics':['budget','scale','concise','limits','language','position','feedback'],'charts':charts},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'charts':len(charts),'topics':dict((t,sum(c['topic']==t for c in charts)) for t in ['budget','scale','concise','limits','language','position','feedback']),'catalog':str(CATALOG.relative_to(ROOT))},ensure_ascii=False))

if __name__=='__main__':build()
