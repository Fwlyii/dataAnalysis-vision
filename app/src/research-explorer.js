import {
  CORE, MODEL_IDS, METRIC_LABELS, TASK_LABELS, initialState, esc, fmt,
  pct, promptName as legacyPromptName, selectCells, aggregate, selectedMetric, csvString,
} from './model.js';
import * as charts from './charts.js';

/** A mountable controller around the original, SVG-rendered research charts.
 * It owns no research scores: conditions and anonymous rows come from the same
 * frozen snapshots used by the original Chinese exploration system.
 */
export const EXPLORER_CHARTS = {
  model:'模型柱图', radar:'模型雷达图', heatmap:'提示策略热力图',
  bubble:'规模与输出开销气泡图', radial:'分组环形柱图', position:'资料位置曲线',
  box:'Token分布箱线图', parallel:'多指标平行坐标', distribution:'结束状态分布',
  behavior:'提示约束与输出形态', timeline:'HTTP请求时间线', tree:'HTTP重试路径树', flow:'评分分歧流图',
};
const NOTES={
  model:'比较当前模型在相同任务和提示下的保存评分；点柱形可查看对应记录。',
  radar:'前三轴比较三个任务或三个证据位置，后两轴为完整率与提取可用率；共用0–100%量纲。',
  heatmap:'每格对应模型与提示条件，色深表示当前评分；点选可追溯相同条件的匿名记录。',
  bubble:'开销视图展示全部31策略；参数视图只展示已核实参数量。两个相近规模不足以独立建立规模定律。',
  radial:'八种核心策略采用相同的0–100%半径刻度，也可切换为便于精确比较的分组柱形。',
  position:'这里保留原10/20篇资料的三位置实验；九位置专项在主发现页展示。线只连接实测位置。',
  box:'箱体为Q1–Q3，中线为中位数，须位于1.5 IQR范围内；离群数保留在提示中。',
  parallel:'每条线为一个模型×核心提示组合；评分、Token、截断和复核率分别保留原单位。',
  distribution:'截断、完整且命中、完整未命中三类互斥；统计与下方记录使用同一筛选集合。',
  behavior:'规则描述的是可见输出形式。点选“提示类别×输出形态”后联动结束状态与匿名记录。',
  timeline:'只展示真实HTTP请求及重试，按匿名编号取当前范围前12个有重试日志的运行。',
  tree:'树枝表示HTTP状态的重试前缀，不代表模型收到测试反馈后修改代码。',
  flow:'相同回答采用不同评分口径时的分歧；流宽为响应数。',
};
const STYLE_LABELS={empty:'空输出',explicit_step_markers:'显式步骤',bullet_list:'列表',multiline_unmarked:'多行未标记',singleline:'单行输出'};
const FAMILY_LABELS={answer_only:'直接回答',step_by_step_requested:'分步要求',concise_steps_requested:'简洁分步',bullet_format:'列表格式',numeric_format:'仅数字',space_format:'去空格',grammar_format:'语法扰动',abbreviation_format:'缩写格式',word_budget:'词数约束',character_budget:'字符约束',token_budget:'Token约束',step_budget:'步骤数约束',chinese_language:'中文输出',chinese_character_budget:'中文字符约束',unknown:'其他'};
const RESULT_LABELS={request_failed:'请求失败',truncated:'输出截断',extraction_unresolved:'答案提取未解析',scored_source:'完整且有源评分'};
const DOC_CHARTS=new Set(['position','timeline','tree','flow']);
function displayPrompt(p){
  const direct={__all:'全部31策略',__core:'核心8策略',__main:'常规19策略',AbbreviateWords:'尽量缩写词语',ChineseCoT:'中文作答',NoProperGrammar:'非标准语法',NoSpaces:'去除空格',OnlyNumbers:'仅数字与公式',BulletPoints:'项目符号'};
  if(direct[p])return direct[p];
  const m=String(p).match(/^(WordLimit|CharLimit|TokenLimit|StepLimit|ChineseCoT)\((\d+)\)$/);
  if(m)return {WordLimit:m[2]+'词上限',CharLimit:m[2]+'字母上限',TokenLimit:m[2]+' Token上限',StepLimit:m[2]+'步上限',ChineseCoT:'中文'+m[2]+'字符上限'}[m[1]];
  return legacyPromptName(p);
}
const scriptLoads=new Map();
let instance=null,rowsPromise=null,allRows=[],byId=new Map(),mountSerial=0,codeModulePromise=null;

function loadScript(src, ready) {
  if(ready())return Promise.resolve();
  if(!scriptLoads.has(src))scriptLoads.set(src,new Promise((resolve,reject)=>{
    const el=document.createElement('script');el.src=src;el.async=true;
    el.onload=()=>ready()?resolve():reject(new Error('本地图表数据没有完成加载。'));
    el.onerror=()=>reject(new Error('本地资源未找到，请重新构建并启动系统。'));
    document.head.append(el);
  }).catch(e=>{scriptLoads.delete(src);throw e;}));
  return scriptLoads.get(src);
}
export async function loadExplorerRows(){
  if(!rowsPromise)rowsPromise=(async()=>{
    await loadScript('runtime/features.js?v='+encodeURIComponent(window.COURSE_FEATURE_VERSION||'1'),()=>!!window.COURSE_FEATURES);
    const p=window.COURSE_FEATURES,labels=window.COURSE_METHOD_FEATURES;
    const lookup=new Map((labels?.rows||[]).map(row=>[row[0],Object.fromEntries(labels.fields.map((key,i)=>[key,row[i]]))]));
    allRows=p.rows.map(row=>Object.assign(Object.fromEntries(p.fields.map((key,i)=>[key,row[i]])),lookup.get(row[0])||{}));
    byId=new Map(allRows.map(r=>[r.id,r]));return allRows;
  })().catch(e=>{rowsPromise=null;throw e;});
  return rowsPromise;
}
function matches(r,q,data){
  return (!q.dataset||r.dataset===q.dataset)&&(!q.model||r.model===q.model)&&(!q.models||q.models.includes(r.model))&&
    (!q.task||q.task==='all'||r.task===q.task)&&(!q.prompt||q.prompt===r.prompt)&&
    (!q.documents||q.documents==='all'||r.documents===+q.documents)&&(!q.position||q.position==='all'||r.position===q.position)&&
    (!q.outputStyle||r.output_style===q.outputStyle)&&(!q.promptFamily||r.prompt_family===q.promptFamily)&&
    (!q.status||r.result_state===q.status)&&(!q.record||r.id===q.record)&&
    (q.tokenLo==null||r.tokens>=q.tokenLo)&&(q.tokenHi==null||r.tokens<q.tokenHi)&&
    (!q.scope||q.scope==='__all'||q.scope===r.prompt||(q.scope==='__core'&&CORE.includes(r.prompt))||
      (q.scope==='__main'&&data.cells.some(c=>c.dataset===r.dataset&&c.prompt===r.prompt&&c.scope==='main_comparison')));
}
function name(data,id){return data.models.find(m=>m.id===id)?.name||id;}
function download(filename,text,type){
  const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1500);
}
function validState(data,options){
  const p=new URLSearchParams(location.search),read=(key,fallback)=>p.get('x'+key)||fallback;
  const state={...initialState(),...options};
  state.panel=read('Panel',options.panel||'library');state.panel=state.panel==='code'?'code':'library';
  state.chart=read('Chart',options.chart||'model');if(!EXPLORER_CHARTS[state.chart])state.chart='model';
  state.dataset=read('Dataset',options.dataset||'reasoning');if(!['reasoning','document_qa'].includes(state.dataset))state.dataset='reasoning';
  state.task=read('Task',options.task||(state.dataset==='reasoning'?'gsm8k':'document_qa'));
  if(!['gsm8k','math500','mmlu','all','document_qa','closedbook_control'].includes(state.task))state.task='gsm8k';
  state.prompt=read('Prompt',options.prompt||'DefaultCoT');
  if(!data.prompts.some(r=>r.id===state.prompt)&&!['__core','__all','__main'].includes(state.prompt))state.prompt='DefaultCoT';
  const available=state.dataset==='document_qa'?['qwen','qwen3']:MODEL_IDS;
  state.models=read('Models',(options.models||available).join(',')).split(',').filter(m=>available.includes(m));if(!state.models.length)state.models=available;
  state.documents=read('Documents',options.documents||'all');if(!['all','10','20'].includes(String(state.documents)))state.documents='all';
  state.position=read('Position',options.position||'all');if(!['all','front','middle','back','none'].includes(state.position))state.position='all';
  state.metric=Math.min(3,Math.max(0,+read('Metric',options.metric||0)||0));
  state.heatScope=read('HeatScope',options.heatScope||'core');state.heatScope=state.heatScope==='all'?'all':'core';
  state.bubble=read('Bubble',options.bubble||'tokens');state.bubble=state.bubble==='parameters'?'parameters':'tokens';
  state.radial=read('Radial',options.radial||'radial');state.radial=state.radial==='bars'?'bars':'radial';
  return normalize(state);
}
function normalize(s){
  if(DOC_CHARTS.has(s.chart)&&s.dataset!=='document_qa'){
    s.dataset='document_qa';s.task='document_qa';s.models=['qwen','qwen3'];s.documents='all';s.position='all';
  }
  if(s.dataset==='document_qa'){
    s.models=s.models.filter(m=>['qwen','qwen3'].includes(m));if(!s.models.length)s.models=['qwen','qwen3'];
    if(!['all','document_qa','closedbook_control'].includes(s.task))s.task='document_qa';
  }else if(!['all','gsm8k','math500','mmlu'].includes(s.task)){s.task='gsm8k';}
  return s;
}
function effectiveState(i){
  const s={...i.state};
  if(['parallel','radial'].includes(s.chart))s.prompt='__core';
  if(s.chart==='heatmap')s.prompt=s.heatScope==='all'?'__all':'__core';
  if(s.chart==='bubble'&&s.bubble!=='parameters')s.prompt='__all';
  if(s.chart==='bubble'&&s.bubble==='parameters')s.models=s.models.filter(m=>i.data.models.find(v=>v.id===m)?.parameters_b!=null);
  if(s.chart==='radar'){s.task=s.dataset==='reasoning'?'all':'document_qa';s.position='all';}
  if(s.chart==='position'){s.task='document_qa';s.position='all';}
  return s;
}
function currentQuery(i,overrides={}){
  const s=effectiveState(i);
  return {dataset:s.dataset,task:s.task,models:s.models,scope:s.prompt,documents:s.documents,position:s.position,...overrides};
}
function sync(i){
  const p=new URLSearchParams(location.search),s=i.state;
  const pairs={Panel:s.panel||'library',Chart:s.chart,Dataset:s.dataset,Task:s.task,Prompt:s.prompt,Models:s.models.join(','),Documents:s.documents,Position:s.position,Metric:s.metric,HeatScope:s.heatScope,Bubble:s.bubble,Radial:s.radial};
  for(const [key,value]of Object.entries(pairs))p.set('x'+key,value);
  history.replaceState(history.state,'',location.pathname+'?'+p+location.hash);
  i.options.onState?.({...s,models:[...s.models]});
}
function select(label,field,items,value,disabled=false){return `<label>${label}<select data-x-field="${field}" ${disabled?'disabled':''}>${items.map(([k,t])=>`<option value="${esc(k)}" ${String(k)===String(value)?'selected':''}>${esc(t)}</option>`).join('')}</select></label>`;}
function say(i,text){i.options.notify?.(text);const el=i.root.querySelector('.r-explorer-message');if(el)el.textContent=text;}
function panelTabs(i){return `<nav class="r-explorer-panel-tabs" aria-label="深度探索类型"><button type="button" data-x-panel="library" aria-current="${i.state.panel!=='code'?'page':'false'}">13类交互图表</button><button type="button" data-x-panel="code" aria-current="${i.state.panel==='code'?'page':'false'}">代码独立生成 · 4个视图</button></nav>`;}
function wirePanelTabs(i){i.root.querySelectorAll('[data-x-panel]').forEach(b=>b.onclick=()=>{i.state.panel=b.dataset.xPanel;sync(i);render(i);});}
function renderShell(i){
  const s=i.state,available=s.dataset==='document_qa'?['qwen','qwen3']:MODEL_IDS,taskOptions=s.dataset==='reasoning'?[['gsm8k','GSM8K 算术应用题'],['math500','MATH500 竞赛数学'],['mmlu','MMLU-Pro 选择题'],['all','三类任务并列']]:[['document_qa','带资料问答'],['closedbook_control','无资料对照'],['all','问答及对照']];
  const fixedPrompt=['radial','parallel','heatmap'].includes(s.chart)||(s.chart==='bubble'&&s.bubble==='tokens');
  const plots=`<div class="r-explorer-chart-scroll"><div id="${i.main}" class="r-explorer-chart ${s.chart==='radial'&&s.radial==='radial'?'r-explorer-radial':''}" role="img" aria-label="${EXPLORER_CHARTS[s.chart]}"></div></div>`;
  i.root.innerHTML=`<div class="r-explorer-heading"><div><h3>把问题继续问下去</h3><p>13类SVG图表，沿用早期中文图表版的匿名研究快照。</p></div><span class="r-explorer-count" aria-live="polite"></span></div>
    ${panelTabs(i)}<div class="r-explorer-controls">
      ${select('图表','chart',Object.entries(EXPLORER_CHARTS),s.chart)}
      ${select('实验数据','dataset',[['reasoning','推理与提示策略'],['document_qa','文档问答']],s.dataset)}
      ${select('任务','task',taskOptions,s.task)}
      ${select('模型','model',[['__all','全部可用模型'],...available.map(m=>[m,name(i.data,m)])],s.models.length===1?s.models[0]:'__all')}
      ${select('提示策略','prompt',[...i.data.prompts.map(p=>[p.id,displayPrompt(p.id)]),['__core','核心8策略'],['__all','全部31策略'],...(s.dataset==='document_qa'?[['__main','常规19策略']]:[])],s.prompt,fixedPrompt)}
      ${s.dataset==='document_qa'?select('评分口径','metric',METRIC_LABELS.map((x,j)=>[j,x]),s.metric)+select('资料篇数','documents',[['all','10与20篇'],['10','10篇'],['20','20篇']],s.documents)+select('证据位置','position',[['all','全部实测位置'],['front','前部'],['middle','中部'],['back','尾部'],['none','无资料']],s.position):''}
      ${s.chart==='heatmap'?select('策略范围','heatScope',[['core','核心8策略'],['all','全部31策略']],s.heatScope):''}
      ${s.chart==='bubble'?select('横轴','bubble',[['tokens','平均输出Token'],['parameters','已核实参数量']],s.bubble):''}
      ${s.chart==='radial'?select('图形布局','radial',[['radial','分组环形柱'],['bars','展开为柱形']],s.radial):''}
    </div>
    <div class="r-explorer-tools"><button type="button" data-x-action="records">查看当前条件记录</button><button type="button" data-x-action="svg">导出当前SVG</button><button type="button" data-x-action="csv">导出当前记录CSV</button><button type="button" data-x-action="reset">重置筛选</button></div>
    <p class="r-explorer-note">${NOTES[s.chart]}</p>
    ${fixedPrompt?'<p class="r-explorer-scope-note">当前图形按策略范围整体比较，记录与导出同步采用图中范围。</p>':''}
    <figure class="r-explorer-figure">${plots}${['distribution','behavior'].includes(s.chart)?`<div class="r-explorer-chart-scroll"><div id="${i.side}" class="r-explorer-chart r-explorer-side" role="img" aria-label="联动状态分布"></div></div>`:''}<figcaption class="r-explorer-caption"></figcaption></figure>
    ${s.chart==='behavior'?`<div class="r-explorer-behavior"><label>提示类别<select data-x-behavior="family"><option value="">全部类别</option></select></label><label>可见输出形态<select data-x-behavior="style"><option value="">全部形态</option>${Object.entries(STYLE_LABELS).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></label><button type="button" data-x-action="behavior-apply">应用类别与形态</button><button type="button" data-x-action="behavior-clear">清除点选</button><span class="r-explorer-behavior-count" aria-live="polite"></span></div>`:''}
    <p class="r-explorer-message" role="status" aria-live="polite"></p><section class="r-explorer-records" hidden aria-label="当前条件的匿名记录"></section>`;
  wirePanelTabs(i);
  i.root.querySelectorAll('[data-x-field]').forEach(el=>el.addEventListener('change',()=>change(i,el.dataset.xField,el.value)));
  i.root.querySelectorAll('[data-x-action]').forEach(el=>el.addEventListener('click',()=>action(i,el.dataset.xAction)));
}
async function action(i,a){
  if(instance!==i)return;
  if(a==='reset'){i.state={...initialState(),chart:'model',heatScope:'core'};i.behavior=null;sync(i);return render(i);}
  if(a==='svg')return exportExplorerSvg();
  if(a==='behavior-clear'){i.behavior=null;return renderBehavior(i,i.epoch);}
  if(a==='behavior-apply'){
    const family=i.root.querySelector('[data-x-behavior="family"]').value,style=i.root.querySelector('[data-x-behavior="style"]').value;
    i.behavior=family||style?{family,style}:null;return renderBehavior(i,i.epoch);
  }
  try{
    const rows=await selectedRows(i);if(instance!==i)return;
    if(a==='csv'){exportRows(i,rows);say(i,`已导出当前集合的${fmt(rows.length)}条匿名记录。`);}
    if(a==='records')openRows(i,rows,'当前图形条件的匿名记录');
  }catch(e){say(i,e.message);}
}
function change(i,key,value){
  const s=i.state;
  if(key==='model')s.models=value==='__all'?(s.dataset==='document_qa'?['qwen','qwen3']:[...MODEL_IDS]):[value];
  else if(key==='metric')s.metric=+value;
  else{s[key]=value;if(key==='dataset'){s.task=value==='reasoning'?'gsm8k':'document_qa';s.models=value==='reasoning'?[...MODEL_IDS]:['qwen','qwen3'];s.position='all';s.documents='all';if(value==='reasoning'&&DOC_CHARTS.has(s.chart))s.chart='model';}}
  normalize(s);i.behavior=null;sync(i);render(i);
}
async function render(i){
  if(instance!==i)return;
  i.epoch++;const epoch=i.epoch;charts.disposeCharts();
  if(i.codeModule)i.codeModule.disposeCodeStudy();
  if(i.state.panel==='code')return renderCodePanel(i,epoch);
  renderShell(i);
  const s=effectiveState(i),agg=aggregate(selectCells(i.data,s),selectedMetric(s));
  i.root.querySelector('.r-explorer-count').textContent=fmt(agg.n)+'次响应';
  i.root.querySelector('.r-explorer-caption').textContent=`${s.dataset==='reasoning'?'推理实验':'文档问答'} · ${TASK_LABELS[s.task]||'全部任务'} · ${displayPrompt(s.prompt)} · ${fmt(agg.n)}次响应 / ${fmt(agg.questions)}道题 · 当前保存评分`;
  const pick=meta=>{
    const query=currentQuery(i,{...(meta.model?{model:meta.model}:{}),...(meta.prompt&&!meta.prompt.startsWith('__')?{scope:meta.prompt}:{}),...(meta.documents?{documents:meta.documents}:{}),...(meta.position?{position:meta.position}:{}),...(meta.task?{task:meta.task}:{})});
    openQuery(i,query,'图中点选条件');
  };
  try{
    await loadScript('assets/vendor/echarts.min.js',()=>!!window.echarts?.init);
    if(instance!==i||epoch!==i.epoch)return;
    const id=i.main;
    if(s.chart==='model')charts.modelBars(id,i.data,s,pick);
    if(s.chart==='radar')charts.radar(id,i.data,s,pick);
    if(s.chart==='heatmap')charts.heatmap(id,i.data,s,pick);
    if(s.chart==='bubble')charts.bubble(id,i.data,s,pick);
    if(s.chart==='radial')charts.radial(id,i.data,s,pick);
    if(s.chart==='position')charts.positionLines(id,i.data,s,pick);
    if(s.chart==='parallel')charts.parallel(id,i.data,s);
    if(s.chart==='flow')charts.disagreement(id,i.data,s);
    if(s.chart==='behavior')await renderBehavior(i,epoch);
    if(['box','distribution','timeline','tree'].includes(s.chart)){
      const rows=await selectedRows(i);if(instance!==i||epoch!==i.epoch)return;
      i.records=rows;i.recordPage=0;i.recordTitle='当前范围的匿名记录';
      if(s.chart==='box')await charts.boxplot(id,i.data,s,rows,pick);
      if(s.chart==='distribution')charts.distribution(id,i.side,i.data,s,rows);
      if(s.chart==='timeline')charts.retryTimeline(id,i.data,rows,record=>openRecord(i,record));
      if(s.chart==='tree')charts.retryTree(id,i.data,rows,record=>openRecord(i,record));
    }
  }catch(e){if(instance===i&&epoch===i.epoch){charts.emptyChart(i.main,'图表暂时未能打开',e.message);say(i,e.message);}}
}
async function selectedRows(i,query=null){
  const all=await loadExplorerRows();const q=query||currentQuery(i);
  let rs=all.filter(r=>matches(r,q,i.data));
  if(!query&&i.state.chart==='behavior'&&i.behavior)rs=rs.filter(r=>(!i.behavior.family||r.prompt_family===i.behavior.family)&&(!i.behavior.style||r.output_style===i.behavior.style));
  return rs;
}
async function renderBehavior(i,epoch){
  const rows=await selectedRows(i,currentQuery(i));if(instance!==i||epoch!==i.epoch)return;
  const families=[...new Set(rows.map(r=>r.prompt_family))].filter(Boolean).sort(),styles=Object.keys(STYLE_LABELS);
  if(!families.length){charts.emptyChart(i.main,'当前范围没有输出形态标签','请重新构建匿名特征快照。');return;}
  const main=i.root.querySelector('#'+i.main);main.style.minHeight=Math.max(450,families.length*37+160)+'px';
  const cells=[];
  for(let j=0;j<families.length;j++){const group=rows.filter(r=>r.prompt_family===families[j]);for(let k=0;k<styles.length;k++){const n=group.filter(r=>r.output_style===styles[k]).length;cells.push({value:[k,j,group.length?n/group.length*100:0],n,total:group.length,meta:{family:families[j],style:styles[k]}});}}
  charts.behaviorMatrix(i.main,families.map(k=>FAMILY_LABELS[k]||k),styles.map(k=>STYLE_LABELS[k]),cells,i.behavior,q=>{i.behavior=q;renderBehavior(i,i.epoch);});
  const subset=i.behavior?rows.filter(r=>(!i.behavior.family||r.prompt_family===i.behavior.family)&&(!i.behavior.style||r.output_style===i.behavior.style)):rows;
  charts.behaviorStates(i.side,Object.keys(RESULT_LABELS).map(k=>({key:k,label:RESULT_LABELS[k],n:subset.filter(r=>r.result_state===k).length})),subset.length,meta=>openRows(i,subset.filter(r=>r.result_state===meta.status),RESULT_LABELS[meta.status]));
  const family=i.root.querySelector('[data-x-behavior="family"]');family.innerHTML='<option value="">全部类别</option>'+families.map(k=>`<option value="${k}">${esc(FAMILY_LABELS[k]||k)}</option>`).join('');family.value=i.behavior?.family||'';
  i.root.querySelector('[data-x-behavior="style"]').value=i.behavior?.style||'';
  i.root.querySelector('.r-explorer-behavior-count').textContent=`当前点选${fmt(subset.length)}次响应`;
}
async function openQuery(i,q,title){
  say(i,'正在读取对应匿名记录…');
  try{const rows=await selectedRows(i,q);if(instance!==i)return;i.recordMetric=Number.isInteger(q.metric)?q.metric:i.state.metric;openRows(i,rows,title);say(i,'');}catch(e){say(i,e.message);}
}
function openRows(i,rows,title){
  if(!Number.isInteger(i.recordMetric))i.recordMetric=i.state.metric;
  i.records=rows;i.recordPage=0;i.recordTitle=title;drawRecords(i);
  const panel=i.root.querySelector('.r-explorer-records');panel.hidden=false;panel.scrollIntoView({behavior:'smooth',block:'nearest'});
}
function drawRecords(i){
  const panel=i.root.querySelector('.r-explorer-records'),rows=i.records,metric=rows[0]?.dataset==='document_qa'?(i.recordMetric??i.state.metric):0;
  const pages=Math.max(1,Math.ceil(rows.length/20));i.recordPage=Math.max(0,Math.min(i.recordPage,pages-1));
  const scored=rows.filter(r=>Number.isFinite(r.scores[metric])),rate=scored.length?scored.reduce((a,r)=>a+r.scores[metric],0)/scored.length:NaN;
  const tokens=rows.filter(r=>Number.isFinite(r.tokens)),mean=tokens.length?tokens.reduce((a,r)=>a+r.tokens,0)/tokens.length:NaN;
  panel.hidden=false;panel.innerHTML=`<div class="r-explorer-record-heading"><div><h4 tabindex="-1">${esc(i.recordTitle)}</h4><p>${fmt(rows.length)}次响应 / ${fmt(new Set(rows.map(r=>r.question)).size)}道题 · ${pct(rate)} · 平均${fmt(mean,1)} Token</p></div><button type="button" data-x-close-records>收起记录</button></div><div class="r-explorer-table-wrap"><table><thead><tr><th>匿名记录</th><th>题号</th><th>模型</th><th>评分</th><th>Token</th><th>状态</th></tr></thead><tbody>${rows.slice(i.recordPage*20,(i.recordPage+1)*20).map(r=>`<tr><td><button type="button" data-x-record="${r.id}">${esc(r.id)}</button></td><td>${esc(r.question)}</td><td>${esc(name(i.data,r.model))}</td><td>${r.scores[metric]??'未评分'}</td><td>${fmt(r.tokens)}</td><td>${r.truncated?'截断':'完整'}</td></tr>`).join('')||'<tr><td colspan="6">当前条件没有匹配记录，可清除筛选后继续。</td></tr>'}</tbody></table></div><div class="r-explorer-record-tools"><button type="button" data-x-record-export>导出这${fmt(rows.length)}条CSV</button><button type="button" data-x-page="${i.recordPage-1}" ${i.recordPage===0?'disabled':''}>上一页</button><span>第${i.recordPage+1} / ${pages}页</span><button type="button" data-x-page="${i.recordPage+1}" ${i.recordPage===pages-1?'disabled':''}>下一页</button></div>`;
  panel.querySelector('[data-x-close-records]').onclick=()=>{panel.hidden=true;i.root.querySelector('[data-x-action="records"]').focus();};
  panel.querySelector('[data-x-record-export]').onclick=()=>exportRows(i,rows);
  panel.querySelectorAll('[data-x-page]').forEach(b=>b.onclick=()=>{i.recordPage=+b.dataset.xPage;drawRecords(i);});
  panel.querySelectorAll('[data-x-record]').forEach(b=>b.onclick=()=>openRecord(i,b.dataset.xRecord));
  panel.querySelector('h4').focus({preventScroll:true});
}
function openRecord(i,id){
  const r=byId.get(id);if(!r)return;
  const panel=i.root.querySelector('.r-explorer-records'),seq=i.data.attempts?.[id];panel.hidden=false;
  const facts=[['匿名题号',r.question],['模型',name(i.data,r.model)],['任务',TASK_LABELS[r.task]||r.task],['提示',displayPrompt(r.prompt)],['资料篇数',r.documents||'不适用'],['证据位置',{front:'前部',middle:'中部',back:'尾部',none:'无资料'}[r.position]||r.position],['输出Token',fmt(r.tokens)],['结束原因',r.finish||'未记录'],['可见形态',STYLE_LABELS[r.output_style]||'未记录'],['提示类别',FAMILY_LABELS[r.prompt_family]||'未记录']];
  panel.innerHTML=`<div class="r-explorer-record-heading"><h4 tabindex="-1">匿名记录 ${esc(id)}</h4><button type="button" data-x-back-records>返回记录列表</button></div><dl class="r-explorer-facts">${facts.map(([k,v])=>`<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl><p>这里只展示保存的匿名特征，记录不含原始问题、回答全文或个人信息。</p>${seq?`<h5>真实HTTP请求序列</h5><ol class="r-explorer-requests">${seq.map(a=>`<li>第${a.attempt}次 · HTTP ${a.http_status??'未记录'} · ${fmt(a.latency_seconds,2)}秒<br><small>${esc(a.started_at)}</small></li>`).join('')}</ol>`:''}`;
  panel.querySelector('[data-x-back-records]').onclick=()=>drawRecords(i);panel.querySelector('h4').focus({preventScroll:true});panel.scrollIntoView({behavior:'smooth',block:'nearest'});
}
function exportRows(i,rows){
  const fields=['id','question','dataset','model','task','prompt','documents','position','scores','tokens','truncated','unresolved','review','finish','latency','attempts','prompt_family','output_style','result_state'];
  download('知微-匿名记录-'+i.state.chart+'.csv',csvString([fields,...rows.map(r=>fields.map(k=>Array.isArray(r[k])?JSON.stringify(r[k]):r[k]))]),'text/csv;charset=utf-8');
}
export function exportExplorerSvg(){
  const i=instance;if(!i)return false;
  if(i.state.panel==='code'){i.root.querySelector('[data-code-action="svg"]')?.click();return true;}
  const svgs=[...i.root.querySelectorAll('.r-explorer-chart')].map(el=>el.querySelector('svg')).filter(Boolean);
  if(!svgs.length){say(i,'图形还在加载，请稍后导出。');return false;}
  const main=i.root.querySelector('#'+i.main);
  if(main?.dataset.renderer==='plotly'){charts.exportChart(i.main);return true;}
  let y=68,body='';const width=Math.max(1000,...svgs.map(svg=>+svg.getAttribute('width')||svg.viewBox.baseVal.width||900));
  for(const svg of svgs){
    const c=svg.cloneNode(true),v=c.getAttribute('viewBox')?.split(/[ ,]+/).map(Number);let w=+c.getAttribute('width')||v?.[2]||900,h=+c.getAttribute('height')||v?.[3]||500;
    c.setAttribute('x','0');c.setAttribute('y',String(y));c.setAttribute('width',String(width));c.setAttribute('height',String(h*width/w));if(!v)c.setAttribute('viewBox',`0 0 ${w} ${h}`);
    body+=new XMLSerializer().serializeToString(c);y+=h*width/w+15;
  }
  const title=EXPLORER_CHARTS[i.state.chart],caption=i.root.querySelector('.r-explorer-caption').textContent;
  const out=`<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 ${width} ${y+88}" width="${width}" height="${y+88}"><title>${esc(title)}</title><style>text{font-family:'Songti SC','Microsoft YaHei','Noto Sans CJK SC',serif}.radial-label{font-size:13px;fill:#142b3d}</style><rect width="100%" height="100%" fill="#fff"/><text x="32" y="37" font-size="24" font-weight="700" fill="#142b3d">${esc(title)}</text>${body}<text x="32" y="${y+28}" font-size="13" fill="#526174">${esc(caption)}</text><text x="32" y="${y+53}" font-size="12" fill="#526174">来源：冻结匿名研究快照；图形导出保留当前条件与SVG矢量元素。</text></svg>`;
  download('知微-'+title+'.svg',out,'image/svg+xml;charset=utf-8');say(i,'已导出当前条件的SVG矢量图。');return true;
}

function syncCode(i){
  const p=new URLSearchParams(location.search);
  for(const key of [...p.keys()])if(key.startsWith('xCode'))p.delete(key);
  for(const [key,value]of i.codeModule.codeQuery(i.codeState))p.set('x'+key[0].toUpperCase()+key.slice(1),value);
  history.replaceState(history.state,'',location.pathname+'?'+p+location.hash);
}
async function renderCodePanel(i,epoch){
  i.root.innerHTML=`<div class="r-explorer-heading"><div><h3>代码独立生成研究</h3><p>五次回答之间没有历史和测试反馈，与主发现中的多轮代码修复分别解释。</p></div></div>${panelTabs(i)}<div class="r-explorer-code" aria-live="polite">正在打开代码研究快照…</div><section class="r-explorer-code-inspector" hidden aria-label="代码评分详情"><div class="r-code-inspector-tools"><button type="button" data-x-close-code>收起详情</button></div><div id="inspector-body"></div></section><p class="r-explorer-message" role="status"></p>`;
  wirePanelTabs(i);
  try{
    await loadScript('runtime/code-data.js',()=>!!window.COURSE_CODE);
    await loadScript('assets/vendor/echarts.min.js',()=>!!window.echarts?.init);
    if(!codeModulePromise)codeModulePromise=import('./code-study.js');
    const code=await codeModulePromise;if(instance!==i||epoch!==i.epoch)return;i.codeModule=code;
    if(!i.codeState){
      const params=new URLSearchParams();
      for(const [key,value]of new URLSearchParams(location.search))if(key.startsWith('xCode'))params.set(key[1].toLowerCase()+key.slice(2),value);
      i.codeState=code.codeRoute(params);
    }
    const mount=i.root.querySelector('.r-explorer-code');
    const redraw=next=>{i.codeState=next;syncCode(i);code.disposeCodeStudy();draw();};
    const openInspector=(title,body)=>{
      const p=i.root.querySelector('.r-explorer-code-inspector');p.hidden=false;
      p.querySelector('#inspector-body').innerHTML=`<h3 tabindex="-1">${esc(title)}</h3>${body}`;
      p.querySelector('h3').focus({preventScroll:true});p.scrollIntoView({behavior:'smooth',block:'nearest'});
    };
    const draw=()=>code.renderCodeStudy(i.codeState,{root:mount,openInspector,download,onChange:redraw,onState:(next,options)=>{i.codeState=next;if(options?.url!==false)syncCode(i);}});
    i.root.querySelector('[data-x-close-code]').onclick=()=>{i.root.querySelector('.r-explorer-code-inspector').hidden=true;mount.querySelector('h1')?.focus();};
    draw();syncCode(i);
  }catch(e){if(instance===i&&epoch===i.epoch)i.root.querySelector('.r-explorer-code').innerHTML=`<p>${esc(e.message)} 请重新构建系统后再试。</p>`;}
}

/** Mount a single explorer. URL fields use an x-prefix; unrelated host state stays intact. */
export async function mountExplorer(container,options={}){
  disposeExplorer();
  const root=typeof container==='string'?document.querySelector(container):container;
  if(!root)throw new Error('没有找到探索区域。');
  await loadScript('runtime/summary.js',()=>!!window.COURSE_SUMMARY);
  const serial=++mountSerial,i={root,options,data:window.COURSE_SUMMARY,state:validState(window.COURSE_SUMMARY,options),main:'research-explorer-main-'+serial,side:'research-explorer-side-'+serial,epoch:0,records:[],recordPage:0,recordTitle:'匿名记录',behavior:null};
  instance=i;root.classList.add('r-explorer');document.body.classList.add('research-explorer-active');sync(i);await render(i);
  return {getState:()=>({...i.state,models:[...i.state.models]}),setState:async patch=>{if(instance!==i)return;Object.assign(i.state,patch);normalize(i.state);i.behavior=null;sync(i);await render(i);},showRecords:filter=>showRecords(filter),exportSvg:exportExplorerSvg,dispose:disposeExplorer};
}
/** Open rows for a research condition without changing host navigation. */
export async function showRecords(filter={}){
  const i=instance;if(!i)return false;
  if(filter.dataset&&!['reasoning','document_qa'].includes(filter.dataset)){say(i,'当前记录库覆盖原推理与文档问答；该专项请使用主题页对应的统计CSV或案例。');return false;}
  const q={...currentQuery(i),...filter};if(filter.dataset&&filter.dataset!==i.state.dataset){q.task=filter.task||(filter.dataset==='document_qa'?'document_qa':null);if(!filter.models)delete q.models;if(!filter.position)q.position='all';if(!filter.documents)q.documents='all';}if(filter.model)delete q.models;if(filter.prompt){q.scope=filter.prompt;delete q.prompt;}
  await openQuery(i,q,filter.title||'研究条件的匿名记录');return true;
}
export function disposeExplorer(){
  if(instance){instance.epoch++;instance.codeModule?.disposeCodeStudy();instance.root.innerHTML='';instance=null;charts.disposeCharts();document.body.classList.remove('research-explorer-active');}
}
