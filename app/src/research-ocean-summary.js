// These overview figures use the same frozen catalog rows as the full SVGs below.
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const n=(v,d=1)=>Number(v).toFixed(d).replace(/\.0$/,'');
const text=(x,y,t,extra='')=>`<text x="${x}" y="${y}" ${extra}>${esc(t)}</text>`;
const line=(x1,y1,x2,y2,extra='')=>`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" ${extra}/>`;
const svg=(label,body)=>`<svg viewBox="0 0 660 245" role="img" aria-label="${esc(label)}" class="ocean-summary-plot">${body}</svg>`;
const rows=(catalog,id)=>catalog.charts.find(c=>c.id===id)?.data||[];

function budget(catalog){
  const r=rows(catalog,'budget-log-gsm8k');
  const mx=r.reduce((s,p)=>s+Math.log(p.mean_tokens),0)/r.length, my=r.reduce((s,p)=>s+p.score_pct,0)/r.length;
  const b=r.reduce((s,p)=>s+(Math.log(p.mean_tokens)-mx)*(p.score_pct-my),0)/r.reduce((s,p)=>s+(Math.log(p.mean_tokens)-mx)**2,0),a=my-b*mx;
  const r2=1-r.reduce((s,p)=>s+(p.score_pct-a-b*Math.log(p.mean_tokens))**2,0)/r.reduce((s,p)=>s+(p.score_pct-my)**2,0);
  const sx=v=>60+v/80*390,sy=v=>184-v/100*145;
  let body=text(41,24,'规则评分')+text(255,232,'实际平均输出 Token','text-anchor="middle"');
  for(const y of [0,25,50,75,100])body+=line(60,sy(y),450,sy(y),'class="grid"')+text(49,sy(y)+5,y+'%','text-anchor="end" class="tick"');
  for(const x of [0,20,40,60,80])body+=text(sx(x),207,x,'text-anchor="middle" class="tick"');
  body+=line(60,184,450,184,'class="axis"');
  const min=Math.min(...r.map(p=>p.mean_tokens)),max=Math.max(...r.map(p=>p.mean_tokens));
  body+=`<path class="fit" d="${Array.from({length:101},(_,i)=>{const x=min+(max-min)*i/100;return (i?'L':'M')+sx(x)+','+sy(a+b*Math.log(x));}).join(' ')}"/>`;
  r.forEach((p,i)=>{body+=`<circle cx="${sx(p.mean_tokens)}" cy="${sy(p.score_pct)}" r="5.5" class="observation"/>`;if(i===3||i===r.length-1)body+=text(sx(p.mean_tokens)+9,sy(p.score_pct)+(i===3?24:-10),n(p.score_pct)+'%','class="coral"');});
  body+=`<circle cx="492" cy="62" r="5" class="observation"/>`+text(509,67,'实测结果')+line(482,96,503,96,'class="fit"')+text(509,101,'对数拟合');
  body+=text(484,153,'R² = '+r2.toFixed(3),'class="formula"')+text(484,180,'7档真实限制','class="tick"');
  return svg('GSM8K七档词数限制的实际Token与规则评分，实测点与对数拟合',body);
}
function scale(catalog){
  const modelNames=['Qwen2.5 7B','Qwen3 8B','HY4 preview','DeepSeek Flash'];
  const tasks=[['gsm8k','GSM8K'],['math500','MATH500'],['mmlu','MMLU-Pro']];
  const series=tasks.map(([id])=>rows(catalog,'scale-models-'+id).filter(r=>r.series==='分步回答'));
  const maxima=series.map(rs=>Math.max(...rs.map(r=>r.value)));
  return `<div class="ocean-scale-table"><table aria-label="四模型在默认分步提示下的三题库规则评分"><thead><tr><th>模型</th>${tasks.map(([,t])=>`<th>${t}</th>`).join('')}</tr></thead><tbody>${modelNames.map((m,i)=>`<tr><th class="model-${i}">${m}</th>${series.map((rs,j)=>{const v=rs.find(r=>r.category===m)?.value;return `<td>${v===maxima[j]?'<strong>':''}${n(v)}%${v===maxima[j]?'</strong>':''}</td>`;}).join('')}</tr>`).join('')}</tbody></table><p>已知参数：7.61B / 8.2B；其余规模未公开。</p></div>`;
}
function concise(catalog){
  const r=rows(catalog,'concise-baseline'),a=r.find(p=>p.prompt==='DefaultCoT'),b=r.find(p=>p.prompt==='BeConcise');
  let body='';
  for(const [idx,key,max,unit,label] of [[0,'mean_tokens',300,'','输出 Token'],[1,'score_pct',100,'%','规则评分']]){
    const left=idx?389:60,right=idx?613:280,top=53,bottom=185;
    const sy=v=>bottom-v/max*(bottom-top);
    body+=text(left,29,label);
    for(const y of [0,max/2,max])body+=line(left,sy(y),right,sy(y),'class="grid"')+text(left-8,sy(y)+5,n(y)+unit,'text-anchor="end" class="tick"');
    body+=line(left,bottom,right,bottom,'class="axis"');
    [a,b].forEach((p,i)=>{const x=left+29+i*112,y=sy(p[key]);body+=`<rect x="${x}" y="${y}" width="65" height="${bottom-y}" fill="url(#ocean-bar-${i?'teal':'blue'})" stroke="${i?'#83ebd6':'#92d9ff'}"/>`+text(x+32.5,y-9,n(p[key])+unit,'text-anchor="middle" class="value"')+text(x+32.5,211,i?'简洁分步':'默认分步','text-anchor="middle" class="tick"');});
  }
  body+=text(173,239,'Token −'+n((1-b.mean_tokens/a.mean_tokens)*100)+'%','text-anchor="middle" class="mint"')+text(501,239,n(a.score_pct)+'% → '+n(b.score_pct)+'%','text-anchor="middle" class="mint"');
  return svg('默认分步与简洁分步的输出Token和规则评分对照，两图均从零起算',body);
}
function limits(catalog){
  const r=rows(catalog,'limits-rebound-main'),points=[100,50,10].map(v=>r.find(p=>p.x===v));
  const sy=v=>185-v/600*145;
  let body=text(49,24,'实际输出 Token');
  for(const y of [0,200,400,600])body+=line(60,sy(y),620,sy(y),'class="grid"')+text(48,sy(y)+5,y,'text-anchor="end" class="tick"');
  body+=line(60,185,620,185,'class="axis"');
  points.forEach((p,i)=>{const x=102+i*183,y=sy(p.y);body+=`<rect x="${x}" y="${y}" width="91" height="${185-y}" fill="url(#ocean-bar-gold)" stroke="#f4cf84"/>`+text(x+45.5,y-10,n(p.y,0),'text-anchor="middle" class="value"')+text(x+45.5,211,'上限 '+p.x,'text-anchor="middle" class="tick"');});
  body+=text(344,239,'字母上限 100 → 10，实际输出约 '+n(points[2].y/points[0].y)+' 倍','text-anchor="middle" class="gold"');
  return svg('DeepSeek MATH500三档字母限制，限制更紧时输出反弹',body);
}
export function renderOceanOverview(catalog,feedbackPublished,options={}){
  const cards=[
    ['cyan','(a) Token投入与边际收益','Qwen2.5 / GSM8K / 每条件200题',budget(catalog),'输出增加，边际收益逐渐放缓'],
    ['teal','(b) 模型规模与任务表现','DefaultCoT / 每题库200题',scale(catalog),'模型有任务差异，规模效应需更多尺度验证'],
    ['purple','(c) 简洁思考：压缩Token，保持质量','Qwen2.5 / GSM8K',concise(catalog),'17组输出全部缩短，15组评分点估计持平或提高'],
    ['gold','(d) 过紧限制触发输出反弹','DeepSeek / MATH500 · 三档示例',limits(catalog),'提示中的上限，并不等于实际输出长度']
  ];
  const ids=['budget','scale','concise','limits'],sources=['budget-log-gsm8k','scale-known-parameters','concise-baseline','limits-rebound-main'];
  const taskOverview=options.includeTasks===false?'':`<div class="finding-group ocean-task-overview"><h2>回到具体任务<span>三项专项，沿任务特性继续追问</span></h2><ol><li><span>01 / 数学</span><h3>中英文作答模板</h3><p>MATH500：四模型更短，三模型提分。</p></li><li><span>02 / 文档</span><h3>关键证据的位置</h3><p>九个实测位置，观察模型差距如何改变。</p></li><li><span>03 / 代码</span><h3>执行反馈与修复</h3><p>${feedbackPublished?'六种反馈，三份初稿，完整保留测试。':'从相同初稿出发，观察反馈后的真实修改。'}</p></li></ol></div>`;
  return `<section class="topic-overview ocean-overview" aria-label="四个总体规律"><svg class="ocean-defs" aria-hidden="true"><defs>${[['blue','#8acbff','#39759c'],['teal','#83ebd6','#298a84'],['gold','#f4cf84','#997b3b']].map(([id,a,b])=>`<linearGradient id="ocean-bar-${id}" x2=".3" y2="1"><stop stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient>`).join('')}</defs></svg><div class="finding-group ocean-general"><h2 class="ocean-visually-hidden">总体规律</h2><ol>${cards.map(([theme,title,scope,chart,result],index)=>`<li class="ocean-card optical-panel theme-${theme}" ${options.markTopics?`id="finding-${ids[index]}" data-topic="${ids[index]}" data-source-chart="${sources[index]}"`:''} tabindex="0" aria-label="${esc(title)}，图形可横向滚动"><header><h3>${title}</h3><p>${scope}</p></header>${chart}<p class="ocean-result"><span>结果</span>${result}</p></li>`).join('')}</ol></div>${taskOverview}</section>`;
}
