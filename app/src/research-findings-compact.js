import { renderOceanOverview } from './research-ocean-summary.js';
import { renderFeedbackCompact } from './research-feedback-extension.js';

const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const n=(value,digits=1)=>Number(value).toFixed(digits).replace(/\.0$/,'');
const rows=(catalog,id)=>catalog.charts.find(chart=>chart.id===id)?.data||[];
const txt=(x,y,value,attrs='')=>`<text x="${x}" y="${y}" ${attrs}>${esc(value)}</text>`;
const ln=(x1,y1,x2,y2,attrs='')=>`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" ${attrs}/>`;
const studyStyle='<style>.compact-study-plot text{font-family:"PingFang SC","Microsoft YaHei",sans-serif;font-size:15px;fill:#f5fbff;font-variant-numeric:tabular-nums}.compact-study-plot .compact-tick,.compact-study-plot .compact-legend{font-size:14px;fill:#d2e5ed}.compact-study-plot .compact-grid{stroke:#66869577;stroke-width:1}.compact-study-plot .compact-axis{stroke:#d1e9f4;stroke-width:1.2}.compact-study-plot .compact-value{font-size:15px;font-weight:600}</style>';
const modelLabel=name=>({'DeepSeek Flash':'DeepSeek','HY4 preview':'HY4','Qwen2.5 7B':'Qwen2.5','Qwen3 8B':'Qwen3'}[name]||name);

function languagePanel(catalog){
  const data=rows(catalog,'language-math-score'),tokenRows=rows(catalog,'language-math-tokens');
  const models=[...new Set(data.map(row=>row.category))];
  const left=68,right=625,top=46,bottom=242,sy=v=>bottom-v/100*(bottom-top);
  let plot=txt(22,26,'规则评分')+`<rect x="357" y="12" width="15" height="11" fill="#76ccff"/>`+txt(381,23,'默认模板','class="compact-legend"')+`<rect x="492" y="12" width="15" height="11" fill="#61e6d3"/>`+txt(516,23,'中文模板','class="compact-legend"');
  for(const tick of [0,25,50,75,100])plot+=ln(left,sy(tick),right,sy(tick),'class="compact-grid"')+txt(left-12,sy(tick)+5,tick+'%','text-anchor="end" class="compact-tick"');
  plot+=ln(left,bottom,right,bottom,'class="compact-axis"');
  models.forEach((model,i)=>{
    const center=left+(right-left)/models.length*(i+.5);
    ['默认模板','中文模板'].forEach((series,j)=>{
      const value=data.find(row=>row.category===model&&row.series===series)?.value;
      const x=center+(j?4:-44),y=sy(value),color=j?'#61e6d3':'#76ccff';
      plot+=`<rect class="compact-language-bar" data-model="${esc(model)}" data-series="${esc(series)}" data-score="${value}" data-value="${value}" x="${x}" y="${y}" width="40" height="${bottom-y}" rx="2" fill="${color}" fill-opacity=".82" stroke="${color}"/>`;
      plot+=txt(x+20,y-9,n(value)+'%','text-anchor="middle" class="compact-value"');
    });
    plot+=txt(center,269,modelLabel(model),'text-anchor="middle" class="compact-tick"');
  });
  const tokenCells=models.map(model=>{
    const before=tokenRows.find(row=>row.category===model&&row.series==='默认模板')?.value;
    const after=tokenRows.find(row=>row.category===model&&row.series==='中文模板')?.value;
    return `<div data-token-model="${esc(model)}" data-token-before="${before}" data-token-after="${after}"><span>${esc(modelLabel(model))}</span><strong>−${n((1-after/before)*100)}%</strong></div>`;
  }).join('');
  return `<section class="compact-task-panel optical-panel theme-cyan" id="finding-language" data-topic="language" aria-labelledby="compact-language-title"><header><h3 id="compact-language-title">数学 · 中文作答模板</h3><p>MATH500 · 相同英文题目 · 默认分步与中文模板</p></header><div class="compact-plot-region" tabindex="0" role="region" aria-label="四模型数学模板对照，窄屏可横向滚动"><svg class="compact-language-plot compact-study-plot" data-source-chart="language-math-score" viewBox="0 0 660 290" width="660" height="290" role="img" aria-labelledby="compact-language-svg-title compact-language-svg-desc"><title id="compact-language-svg-title">MATH500四模型默认与中文作答模板评分</title><desc id="compact-language-svg-desc">蓝色默认模板，绿色中文模板，评分纵轴从0到100%；四个模型的全部八个观测值均保留。</desc>${studyStyle}${plot}</svg></div><div class="compact-token-heading"><span>平均输出 Token 的变化</span><span>中文模板相对默认模板</span></div><div class="compact-token-grid" data-source-chart="language-math-tokens">${tokenCells}</div><p class="compact-study-conclusion">四模型输出都更短，三模型评分提高；Qwen3 为 58.0% → 69.5%。</p><p class="compact-study-scope">这是作答模板对照；图中未测量模型内部的思考语言。</p></section>`;
}

function positionPanel(catalog){
  const data=rows(catalog,'position-nine-profile'),deltas=rows(catalog,'position-model-advantage');
  const series=[...new Set(data.map(row=>row.series))],positions=[...new Set(data.map(row=>row.x))].sort((a,b)=>a-b);
  const left=68,right=618,top=46,bottom=242,sx=value=>left+(value-1)/19*(right-left),sy=value=>bottom-(value-40)/40*(bottom-top);
  let plot=txt(19,26,'答案命中率');
  series.forEach((name,i)=>{
    const color=i?'#61e6d3':'#76ccff',x=325+i*155;
    plot+=ln(x,18,x+20,18,`stroke="${color}" stroke-width="2.5"${i?' stroke-dasharray="5 3"':''}`)+txt(x+28,23,modelLabel(name),'class="compact-legend"');
  });
  for(const tick of [40,50,60,70,80])plot+=ln(left,sy(tick),right,sy(tick),'class="compact-grid"')+txt(left-12,sy(tick)+5,tick+'%','text-anchor="end" class="compact-tick"');
  plot+=ln(left,bottom,right,bottom,'class="compact-axis"');
  positions.forEach(position=>plot+=txt(sx(position),269,n(position,0),'text-anchor="middle" class="compact-tick"'));
  series.forEach((name,i)=>{
    const points=data.filter(row=>row.series===name).sort((a,b)=>a.x-b.x),color=i?'#61e6d3':'#76ccff';
    points.forEach(row=>{
      const x=sx(row.x),y=sy(row.y);
      plot+=`<g class="compact-position-ci" data-series="${esc(name)}" data-position="${row.x}" data-low="${row.low}" data-high="${row.high}" opacity=".36">${ln(x,sy(row.low),x,sy(row.high),`stroke="${color}" stroke-width="1.4"`)}${ln(x-3,sy(row.low),x+3,sy(row.low),`stroke="${color}"`)}${ln(x-3,sy(row.high),x+3,sy(row.high),`stroke="${color}"`)}</g>`;
    });
    plot+=`<path d="${points.map((row,index)=>(index?'L':'M')+sx(row.x)+','+sy(row.y)).join(' ')}" fill="none" stroke="${color}" stroke-width="2.6"${i?' stroke-dasharray="6 4"':''}/>`;
    points.forEach((row,j)=>{
      const x=sx(row.x),y=sy(row.y),attrs=`class="compact-position-point" data-series="${esc(name)}" data-position="${row.x}" data-score="${row.y}" data-low="${row.low}" data-high="${row.high}"`;
      plot+=i?`<path ${attrs} d="M${x},${y-5}L${x+5},${y}L${x},${y+5}L${x-5},${y}Z" fill="#042735" stroke="${color}" stroke-width="2"/>`:`<circle ${attrs} cx="${x}" cy="${y}" r="4.5" fill="#042735" stroke="${color}" stroke-width="2"/>`;
      if(j===0||j===points.length-1)plot+=txt(x+(j===0?9:-9),y+(i?-12:21),n(row.y)+'%',`text-anchor="${j===0?'start':'end'}" class="compact-value" fill="${color}"`);
    });
  });
  const first=deltas.find(row=>row.x===1),last=deltas.find(row=>row.x===20);
  const difference=(label,row)=>`<div data-position-contrast="${row.x}" data-delta="${row.y}" data-low="${row.low}" data-high="${row.high}"><span>${label} · 模型差</span><strong>${n(row.y)}<small> pp</small></strong><p>95% CI [${n(row.low)}, ${n(row.high)}]</p></div>`;
  return `<section class="compact-task-panel optical-panel theme-purple" id="finding-position" data-topic="position" aria-labelledby="compact-position-title"><header><h3 id="compact-position-title">文档 · 关键证据的位置</h3><p>NaturalQuestions-Open · 200题 · 20篇资料 · 九个位置</p></header><div class="compact-plot-region" tabindex="0" role="region" aria-label="九位置文档命中率与区间，窄屏可横向滚动"><svg class="compact-position-plot compact-study-plot" data-source-chart="position-nine-profile" viewBox="0 0 660 290" width="660" height="290" role="img" aria-labelledby="compact-position-svg-title compact-position-svg-desc"><title id="compact-position-svg-title">两个模型在九个实际证据位置上的答案命中率</title><desc id="compact-position-svg-desc">横轴位置1、3、5、8、10、13、15、18和20，纵轴40%到80%，每个实测点保留原95%区间，点之间按实际位置线性连接。</desc>${studyStyle}${plot}</svg></div><div class="compact-position-deltas" data-source-chart="position-model-advantage">${difference('首位',first)}${difference('末位',last)}</div><p class="compact-study-conclusion">证据移到末位，模型差距缩小；末位差值区间包含 0。</p><p class="compact-study-scope">相关资料位置是实测变量，曲线不补造中间位置。</p></section>`;
}

export function renderCompactFindings(catalog,publication){
  const overview=renderOceanOverview(catalog,Boolean(publication),{includeTasks:false,markTopics:true});
  const feedback=publication?renderFeedbackCompact(publication.evidence,publication.figures,publication.legacyEvidence):'';
  const fallback=catalog.charts.find(chart=>chart.id==='feedback-rounds-qwen3');
  return `<div class="findings-long-page compact-findings"><section class="findings-part compact-general-part" aria-label="四个总体规律">${overview}</section><section class="findings-part compact-task-part" aria-labelledby="compact-task-studies-title"><header class="compact-part-heading"><h2 id="compact-task-studies-title">任务专项：语言与证据位置</h2><p>固定题目与资料，观察作答模板和证据组织带来的变化。</p></header><div class="compact-task-grid">${languagePanel(catalog)}${positionPanel(catalog)}</div><section class="compact-feedback-chapter" id="finding-feedback" data-topic="feedback" aria-label="代码中的执行反馈">${feedback||`<h2>代码中的执行反馈</h2><p>历史 Mini 批次；完整强测补充批次尚未发布。</p>${fallback?`<img src="${esc(fallback.file)}" alt="${esc(fallback.title)}" width="${fallback.width}" height="${fallback.height}">`:''}`}</section></section></div>`;
}
