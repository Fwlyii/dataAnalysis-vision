import {esc,fmt,pct,csvString} from './model.js';

const MODELS={qwen:'Qwen2.5 7B',qwen3:'Qwen3 8B'};
const ARMS={seed:'共享初稿',resample:'独立重新生成',self_review:'无反馈自查',pass_fail:'通过 / 失败状态',counterexample:'具体失败用例'};
const POSITIONS=[1,3,5,8,10,13,15,18,20];
let snapshotPromise=null,dialog=null,current=null,requestNumber=0,returnFocus=null;

async function loadSnapshot(){
  if(!snapshotPromise)snapshotPromise=(async()=>{
    const response=await fetch('data/special-records.json.gz');
    if(!response.ok)throw new Error('专项匿名快照未找到，请重新构建系统后打开。');
    const bytes=new Uint8Array(await response.arrayBuffer());let text;
    if(bytes[0]===31&&bytes[1]===139){
      if(typeof DecompressionStream==='undefined')throw new Error('此浏览器无法读取压缩快照，请使用新版Chrome、Edge或Safari。');
      text=await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text();
    }else text=new TextDecoder().decode(bytes);
    const data=JSON.parse(text);
    if(data.schema!=='lens-special-records-v1'||data.rows.length!==9176)throw new Error('专项匿名快照版本不一致，请重新构建。');
    data.records=data.rows.map(row=>Object.fromEntries(data.fields.map((key,i)=>[key,row[i]])));
    return data;
  })().catch(error=>{snapshotPromise=null;throw error;});
  return snapshotPromise;
}
function ensureDialog(){
  if(dialog?.isConnected)return dialog;
  dialog=document.createElement('dialog');dialog.className='rs-dialog';dialog.setAttribute('aria-labelledby','rs-title');
  dialog.addEventListener('close',()=>{if(dialog.open)return;requestNumber++;current=null;if(returnFocus?.isConnected)returnFocus.focus();});
  dialog.addEventListener('click',event=>{
    if(event.target===dialog){const b=dialog.getBoundingClientRect();if(event.clientX<b.left||event.clientX>b.right||event.clientY<b.top||event.clientY>b.bottom)dialog.close();}
  });
  document.body.append(dialog);return dialog;
}
function normalizeModel(value){
  if(!value||value==='all'||value==='__all')return 'all';
  const text=String(value).toLowerCase();if(text.includes('qwen3'))return 'qwen3';if(text==='qwen'||text.includes('qwen2.5'))return 'qwen';throw new Error('该模型没有这两个专项的实测记录，请选择Qwen2.5或Qwen3。');
}
function initialFilters(topic,filters){
  const model=normalizeModel(filters.model||filters.model_id);
  if(topic==='position'){
    const raw=filters.position??filters.evidence_position??'all',p=Number(raw);
    if(!['all','__all'].includes(String(raw))&&!POSITIONS.includes(p))throw new Error('九位置专项只包含第1、3、5、8、10、13、15、18、20篇的实测位置。');
    return {model,position:POSITIONS.includes(p)?String(p):'all',feedback:'all',round:'all'};
  }
  const feedback=filters.feedback||filters.feedback_type||filters.arm||'all',round=String(filters.round??filters.revision_round??'all');
  if(feedback!=='all'&&!Object.hasOwn(ARMS,feedback))throw new Error('当前反馈方式不在保存的实测方案中。');
  if(!['all','0','1','2','3','4'].includes(round))throw new Error('修复专项只包含共享初稿和四次后续生成。');
  return {model,position:'all',feedback:Object.hasOwn(ARMS,feedback)?feedback:'all',round:['0','1','2','3','4'].includes(round)?round:'all'};
}
function option(value,label,currentValue){return `<option value="${esc(value)}" ${String(value)===String(currentValue)?'selected':''}>${esc(label)}</option>`;}
function formSelect(key,label,options,value){return `<label for="rs-${key}">${label}<select id="rs-${key}" data-rs-filter="${key}">${options.map(([k,v])=>option(k,v,value)).join('')}</select></label>`;}
function header(topic){return `<header class="rs-header"><div><h2 id="rs-title">${topic==='position'?'九位置专项':'反馈修复专项'} · 匿名记录</h2><p>${topic==='position'?'固定20篇资料、9个实测位置、两模型与200道共同问题。':'164道题、两模型、共享初稿与四次后续生成；只读取保存的数值特征。'}</p></div><button type="button" class="rs-close" data-rs-close aria-label="关闭专项匿名记录">关闭</button></header>`;}
function renderShell(s){
  const f=s.filters;
  dialog.innerHTML=`${header(s.topic)}<div class="rs-content"><form class="rs-filters" aria-label="专项记录筛选">${formSelect('model','模型',[['all','全部模型'],...Object.entries(MODELS)],f.model)}${s.topic==='position'?formSelect('position','证据位置',[['all','全部9位置'],...POSITIONS.map(v=>[String(v),'第'+v+'篇'])],f.position):formSelect('feedback','反馈方式',[['all','全部处理与初稿'],...Object.entries(ARMS)],f.feedback)+formSelect('round','生成阶段',[['all','全部阶段'],['0','初稿（共享）'],...['1','2','3','4'].map(v=>[v,'第'+v+'次后续生成'])],f.round)}<button type="button" data-rs-reset>清除筛选</button></form><p class="rs-method">${s.topic==='position'?'评分口径：提取后的最终答案包含参考答案（final_answer_contains）。20篇资料和同一批200道题固定，九位置分别实测；位置曲线的点不是新增独立问题。':'评分口径：当前版本同时通过诊断与额外测试（base_and_heldout_pass）。328份共享初稿在物理记录中各保存一次，不重复加到四个反馈组；全集的混合评分率不等于最终版本通过率。'}</p><div class="rs-summary" role="status" aria-live="polite"></div><div class="rs-tools"><button type="button" data-rs-export>导出当前集合CSV</button>${s.topic==='feedback'&&s.data.examples?.length?'<button type="button" data-rs-example>查看精选修复案例</button>':''}<span class="rs-source">来源：冻结统一数值表 · 匿名快照共9,176条</span></div><div class="rs-table-wrap" tabindex="0" role="region" aria-label="专项匿名记录表，可横向滚动"><table><thead></thead><tbody></tbody></table></div><div class="rs-pagination"><button type="button" data-rs-page="prev">上一页</button><span></span><button type="button" data-rs-page="next">下一页</button></div><aside class="rs-example" hidden></aside><p class="rs-privacy">记录使用重新编号的P/R匿名ID和再次哈希的题号；不包含原始记录键、原始题号、对话全文、时间戳或凭据。</p></div>`;
  dialog.querySelector('[data-rs-close]').onclick=()=>dialog.close();
  dialog.querySelector('.rs-filters').onsubmit=event=>event.preventDefault();
  dialog.querySelectorAll('[data-rs-filter]').forEach(el=>el.onchange=()=>{
    const key=el.dataset.rsFilter;s.filters[key]=el.value;s.page=0;
    if(s.topic==='feedback'){
      if(key==='round'&&el.value==='0'){s.filters.feedback='seed';dialog.querySelector('#rs-feedback').value='seed';}
      if(key==='feedback'&&el.value==='seed'){s.filters.round='0';dialog.querySelector('#rs-round').value='0';}
      if(key==='feedback'&&!['all','seed'].includes(el.value)&&s.filters.round==='0'){s.filters.round='all';dialog.querySelector('#rs-round').value='all';}
      if(key==='round'&&el.value!=='0'&&s.filters.feedback==='seed'){s.filters.feedback='all';dialog.querySelector('#rs-feedback').value='all';}
    }
    renderRows(s);
  });
  dialog.querySelector('[data-rs-reset]').onclick=()=>{s.filters=initialFilters(s.topic,{});s.page=0;renderShell(s);renderRows(s);dialog.querySelector('#rs-model').focus();};
  dialog.querySelector('[data-rs-export]').onclick=()=>exportRows(s);
  dialog.querySelectorAll('[data-rs-page]').forEach(b=>b.onclick=()=>{s.page+=b.dataset.rsPage==='next'?1:-1;renderRows(s);});
  const example=dialog.querySelector('[data-rs-example]');if(example)example.onclick=()=>renderExample(s);
}
function rowsFor(s){
  const f=s.filters;
  return s.data.records.filter(r=>r.topic===s.topic&&(f.model==='all'||r.model===f.model)&&(s.topic!=='position'||f.position==='all'||r.position===+f.position)&&(s.topic!=='feedback'||((f.feedback==='all'||r.feedback===f.feedback)&&(f.round==='all'||r.round===+f.round))));
}
function renderRows(s){
  if(current!==s)return;
  const rows=s.rows=rowsFor(s),scored=rows.filter(r=>Number.isFinite(r.score)&&!r.excluded),passed=scored.reduce((sum,r)=>sum+r.score,0),tokens=rows.filter(r=>Number.isFinite(r.output_tokens));
  const questions=new Set(rows.map(r=>r.question)).size,pages=Math.max(1,Math.ceil(rows.length/20));s.page=Math.max(0,Math.min(s.page,pages-1));
  const metric=s.topic==='position'?'答案包含率':'当前集合完整通过率';
  dialog.querySelector('.rs-summary').innerHTML=`<div><strong>${fmt(rows.length)}</strong><span>真实响应</span></div><div><strong>${fmt(questions)}</strong><span>不同匿名题目</span></div><div><strong>${pct(scored.length?passed/scored.length:NaN)}</strong><span>${metric} · ${fmt(passed)}/${fmt(scored.length)}</span></div><div><strong>${fmt(tokens.length?tokens.reduce((sum,r)=>sum+r.output_tokens,0)/tokens.length:NaN,1)}</strong><span>平均输出Token</span></div>`;
  const cols=s.topic==='position'?['匿名记录','匿名题号','模型','位置','资料数','评分','输出Token','结束']:['匿名记录','匿名题号','模型','反馈方式','阶段','完整通过','输出Token','结束'];
  dialog.querySelector('thead').innerHTML='<tr>'+cols.map(c=>'<th scope="col">'+c+'</th>').join('')+'</tr>';
  dialog.querySelector('tbody').innerHTML=rows.slice(s.page*20,(s.page+1)*20).map(r=>{
    const cells=[r.id,r.question,MODELS[r.model]||r.model,...(s.topic==='position'?[r.position,r.documents]:[ARMS[r.feedback]||r.feedback,r.round===0?'共享初稿':'修改'+r.round]),r.score==null?'未评分':r.score,fmt(r.output_tokens),r.truncated?'截断':r.finish_reason||'未记录'];
    return '<tr>'+cells.map((v,index)=>`<td${[0,1].includes(index)?' class="rs-mono"':''}>${esc(v)}</td>`).join('')+'</tr>';
  }).join('')||'<tr><td colspan="8">当前条件没有记录，可清除筛选后继续。</td></tr>';
  dialog.querySelector('[data-rs-export]').disabled=!rows.length;
  dialog.querySelector('[data-rs-page="prev"]').disabled=s.page===0;
  dialog.querySelector('[data-rs-page="next"]').disabled=s.page===pages-1;
  dialog.querySelector('.rs-pagination span').textContent=`第${s.page+1} / ${pages}页 · 每页20条`;
}
function exportRows(s){
  const fields=s.data.fields;
  const text=csvString([fields,...s.rows.map(r=>fields.map(key=>r[key]))]);
  const url=URL.createObjectURL(new Blob([text],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='知微-'+(s.topic==='position'?'九位置':'反馈修复')+'-匿名记录.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1500);
}
function renderExample(s){
  const example=s.data.examples[0],host=dialog.querySelector('.rs-example');
  if(!example)return;
  host.hidden=!host.hidden;if(host.hidden)return;
  host.innerHTML=`<h3>${esc(example.title)}</h3><p>${esc(MODELS[example.model])} · 第${example.round}次修改 · 输入 ${esc(example.input)}，期望 ${esc(example.expected)}，修改前得到 ${esc(example.actual)}。</p><div class="rs-code-pair"><div><h4>修改前的关键代码</h4><pre><code>${esc(example.before)}</code></pre></div><div><h4>修改后的关键代码</h4><pre><code>${esc(example.after)}</code></pre></div></div><p>当前修改版本：${example.passed_after?'诊断与额外测试均通过':'尚未完整通过'}。${esc(example.note)}</p>`;
  host.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'nearest'});
}
/** Open a native, keyboard-accessible numeric-record dialog for the two studies.
 * filters accepts model/model_id, position/evidence_position, feedback/arm/
 * feedback_type and round/revision_round. It never broadens a provided cohort.
 */
export async function openSpecialRecords({topic,filters={}}={}){
  if(!['position','feedback'].includes(topic))throw new Error('专项记录主题须为position或feedback。');
  const token=++requestNumber,d=ensureDialog();
  if(!d.open){returnFocus=document.activeElement;d.showModal();}
  d.innerHTML=`${header(topic)}<div class="rs-content"><p role="status">正在读取专项匿名快照…</p></div>`;
  d.querySelector('[data-rs-close]').onclick=()=>d.close();
  try{
    const data=await loadSnapshot();if(token!==requestNumber||!d.open)return null;
    const state=current={topic,filters:initialFilters(topic,filters),page:0,data,rows:[]};
    renderShell(state);renderRows(state);d.querySelector('#rs-model').focus();
    return {count:state.rows.length,close:()=>d.close()};
  }catch(error){
    if(token!==requestNumber||!d.open)return null;
    d.querySelector('.rs-content').innerHTML=`<p class="rs-error" role="alert">${esc(error.message)}</p><button type="button" data-rs-retry>重新读取</button>`;
    d.querySelector('[data-rs-retry]').onclick=()=>openSpecialRecords({topic,filters});return null;
  }
}
export function closeSpecialRecords(){if(dialog?.open)dialog.close();}
