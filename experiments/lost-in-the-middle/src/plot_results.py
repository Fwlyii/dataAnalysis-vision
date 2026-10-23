#!/usr/bin/env python3
"""Final figures and source tables; no API access or local staging dependency."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODELS = ['Qwen/Qwen2.5-7B-Instruct', 'Qwen/Qwen3-8B']
LABELS = ['Qwen2.5-7B', 'Qwen3-8B']
COLORS = ['#0072B2', '#D55E00']
MARKERS = ['o', '^']
POS = ['front', 'middle', 'back']


def cluster_ci(g, metric):
    means = g.groupby('question_id')[metric].mean().to_numpy()
    rng = np.random.default_rng(91)
    draws = means[rng.integers(0, len(means), (5000, len(means)))].mean(axis=1)
    low, high = np.quantile(draws, [.025, .975])
    return dict(accuracy=means.mean()*100, low=low*100, high=high*100,
                records=len(g), questions=len(means))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=ROOT/'derived/analysis.json')
    parser.add_argument('--scores', type=Path, default=ROOT/'derived/scores.csv')
    parser.add_argument('--out', type=Path, default=ROOT/'figures')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    tables = args.out/'source_data'
    tables.mkdir(exist_ok=True)
    info = json.loads(args.input.read_text())
    scores = pd.read_csv(args.scores)
    english = scores[(scores.task_type == 'document_qa') & (scores.scope == 'main_comparison')]
    assert len(scores) == 74800 and len(english) == 45600
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9,
                         'svg.fonttype': 'none', 'pdf.fonttype': 42,
                         'axes.spines.top': False, 'axes.spines.right': False})

    def save(fig, name, caption, frame, layout=True):
        fig.text(.02, .015, caption, fontsize=8, va='bottom')
        if layout:
            fig.tight_layout(rect=(0, .08, 1, .98))
        fig.canvas.draw()
        for ext in ['png', 'svg', 'pdf']:
            fig.savefig(args.out/f'{name}.{ext}', dpi=300)
        frame.to_csv(tables/f'{name}.csv', index=False, lineterminator='\n')
        plt.close(fig)

    # Four dimensions, split into two panels rather than a 3D chart.
    frame = pd.DataFrame([dict(model=m, documents=n, position=p, **cluster_ci(g, 'paper_firstline'))
                          for (m,n,p),g in english.groupby(['model','document_count','position_label'])])
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), sharey=True)
    for ax, docs in zip(axes, [10,20]):
        for i, model in enumerate(MODELS):
            g = frame[(frame.model==model)&(frame.documents==docs)].set_index('position').loc[POS]
            ax.errorbar(np.arange(3)+(i-.5)*.14, g.accuracy,
                        yerr=[g.accuracy-g.low,g.high-g.accuracy], fmt=MARKERS[i], color=COLORS[i], capsize=3, label=LABELS[i])
        ax.set(title=f'{docs} documents', xticks=range(3), xticklabels=['Front','Middle','Back'], ylim=(0,100), xlabel='Evidence position')
        ax.grid(axis='y',alpha=.2)
    axes[0].set_ylabel('Official first-line accuracy (%)')
    axes[1].legend(frameon=False,loc='lower right')
    save(fig,'01_position_model_length',
         'English19; 3,800 answers/cell, 200 question clusters. 95% cluster bootstrap CI (5,000 draws; seed 91).', frame)

    frame = pd.DataFrame([r for r in info['paired_positions'] if r['scope']=='english19' and r['documents']=='pooled'])
    fig, axes = plt.subplots(1,3,figsize=(11,4),sharey=True)
    for ax, metric, title in zip(axes,['paper_firstline','strict_final_em','final_contains'],['Paper first-line','Strict final answer','Final answer contains']):
        for i, model in enumerate(MODELS):
            for j, comp in enumerate(['front-middle','back-middle']):
                r=frame[(frame.model==model)&(frame.metric==metric)&(frame.comparison==comp)].iloc[0]
                low,high=r.cluster_bootstrap_95ci_pp
                ax.errorbar(r.difference_pp,j+(i-.5)*.18,xerr=[[r.difference_pp-low],[high-r.difference_pp]],
                            fmt=MARKERS[i],color=COLORS[i],capsize=3,label=LABELS[i] if j==0 else None)
        ax.axvline(0,color='gray',linestyle='--',linewidth=.8)
        ax.set(title=title,xlabel='Difference (percentage points)',yticks=[0,1],
               yticklabels=['Front - Middle','Back - Middle'],xlim=(-4,11),ylim=(-.5,1.5))
    axes[2].legend(frameon=False,loc='upper right')
    save(fig,'02_paired_position_metrics',
         '7,600 pairs/comparison, 200 questions. 95% cluster bootstrap CI; exploratory, no multiple-comparison correction.', frame)

    strategies=pd.DataFrame(info['strategies'])
    selected=strategies[strategies.scope=='main_comparison']
    names=list(selected.groupby('strategy').final_contains.mean().sort_values(ascending=False).index)
    frame=pd.DataFrame([dict(model=m,prompt=p,**cluster_ci(g,'final_contains'))
                        for (m,p),g in english.groupby(['model','prompt_id'])])
    fig,axes=plt.subplots(1,2,figsize=(10,7),sharex=True,sharey=True)
    for i,(ax,model) in enumerate(zip(axes,MODELS)):
        g=frame[frame.model==model].set_index('prompt').loc[names]
        ax.errorbar(g.accuracy,range(len(names)),xerr=[g.accuracy-g.low,g.high-g.accuracy],fmt=MARKERS[i],color=COLORS[i],capsize=2)
        ax.set(title=LABELS[i],xlim=(0,100),xlabel='Final-answer contains accuracy (%)',yticks=range(len(names)),yticklabels=names)
        ax.grid(axis='x',alpha=.2)
    axes[0].invert_yaxis()
    save(fig,'03_strategy_accuracy',
         'English19; 1,200 answers/strategy/model; 200 questions. 95% cluster bootstrap CI. Ranks are descriptive.',frame)

    fig,ax=plt.subplots(figsize=(8,5))
    for i,model in enumerate(MODELS):
        g=selected[selected.model==model]
        ax.scatter(g.mean_output_tokens,g.final_contains*100,color=COLORS[i],marker=MARKERS[i],label=LABELS[i])
        for _,r in g[g.strategy.isin(['NoCoT','DefaultCoT'])].iterrows():
            offset=(5,-18) if r.strategy=='NoCoT' and i==0 else (5,9)
            ax.annotate(r.strategy,(r.mean_output_tokens,r.final_contains*100),xytext=offset,
                        textcoords='offset points',fontsize=8,arrowprops=dict(arrowstyle='-',color=COLORS[i],lw=.6))
    ax.set(xlabel='Mean output tokens',ylabel='Final-answer contains accuracy (%)',ylim=(0,100))
    ax.grid(alpha=.2)
    ax.legend(frameon=False,loc='lower right')
    save(fig,'04_tokens_accuracy',
         '38 strategy/model means; 1,200 answers each. English19 only. Descriptive association, not a causal effect.',selected)

    frame=english.groupby(['model','document_count','prompt_id','position_label']).agg(
        accuracy=('final_contains','mean'),records=('question_id','size')).reset_index()
    fig,axes=plt.subplots(2,2,figsize=(11,10),sharex=True,sharey=True)
    for i,model in enumerate(MODELS):
        for j,docs in enumerate([10,20]):
            ax=axes[i,j]
            g=frame[(frame.model==model)&(frame.document_count==docs)]
            matrix=g.pivot(index='prompt_id',columns='position_label',values='accuracy').loc[names,POS]*100
            mesh=ax.pcolormesh(matrix.to_numpy(),cmap='cividis',vmin=0,vmax=100,edgecolors='white',linewidth=.5)
            for row in range(len(names)):
                for col in range(3):
                    ax.text(col+.5,row+.5,f'{matrix.iloc[row,col]:.0f}',ha='center',va='center',fontsize=7)
            ax.set(xticks=np.arange(3)+.5,xticklabels=['Front','Middle','Back'],
                   yticks=np.arange(len(names))+.5,yticklabels=names,title=f'{LABELS[i]} / {docs} documents')
    axes[0,0].invert_yaxis()
    fig.tight_layout(rect=(0,.08,.87,.98))
    cax=fig.add_axes([.89,.22,.018,.52])
    fig.colorbar(mesh,cax=cax,label='Final-answer contains accuracy (%)')
    save(fig,'05_prompt_position_heatmap',
         'English19; 200 answers/cell. Panels share the same 0-100% scale. Descriptive cell means.',frame,layout=False)

    frame=strategies.copy()
    frame['truncation_percent']=frame.truncated/frame.n*100
    names_all=list(frame.groupby('strategy').truncation_percent.max().sort_values(ascending=False).index)
    fig,axes=plt.subplots(1,2,figsize=(10,9),sharex=True,sharey=True)
    for i,(ax,model) in enumerate(zip(axes,MODELS)):
        g=frame[frame.model==model].set_index('strategy').loc[names_all]
        ax.barh(range(len(g)),g.truncation_percent,color=COLORS[i])
        ax.set(title=LABELS[i],yticks=range(len(g)),yticklabels=names_all,xlabel='Truncated answers (%)',xlim=(0,40))
        ax.grid(axis='x',alpha=.2)
    axes[0].invert_yaxis()
    save(fig,'06_truncation_all_strategies',
         'All 31 strategies; 1,200 answers/strategy/model. Truncated = API finish_reason length. Descriptive counts.',frame)
    print('Exported six figures (PNG/SVG/PDF) and six source tables.')


if __name__=='__main__':
    main()
