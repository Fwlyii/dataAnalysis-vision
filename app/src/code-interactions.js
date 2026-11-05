import {esc, fmt, pct} from './model.js';
import * as libraries from './libraries.js';

let generation=0, cleanups=[], selection=[], snapshotExport=null,stopPlayback=null;
const names={deepseek:'DeepSeek Flash',qwen:'Qwen2.5 7B',qwen3:'Qwen3 8B'};
const errors={assertion_failure:'Assertion failure',attribute_error:'Attribute error',type_error:'Type error',syntax_error:'Syntax error',extraction_error:'Extraction error',dependency_error:'Dependency error',name_error:'Name error',timeout:'Timeout',runtime_error:'Runtime error',file_error:'File error',index_error:'Index error',key_error:'Key error',value_error:'Value error',resource_error:'Resource error'};
const namespace='http://www.w3.org/2000/svg';
export function pause(){stopPlayback?.();document.querySelectorAll(".code-hover-tip").forEach(el=>{el.hidden=true;});}
export function dispose(){generation++;stopPlayback=null;for(const f of cleanups.splice(0))f();document.querySelector('.code-hover-tip')?.remove();snapshotExport=null;}
export function selectedConditions(){return selection.map(r=>({model:r.model,prompt:r.prompt}));}
export function svgSnapshot(){return snapshotExport?.() || null;}
export function playbackControls(step=5){return `<div class="code-playback"><button id="code-play" class="text-action" aria-pressed="false" disabled><svg width="15" height="15" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M6 3.5 16 10 6 16.5Z"/></svg><span>播放</span></button><label for="code-sample-step">独立采样</label><input id="code-sample-step" type="range" min="1" max="5" step="1" value="${step}" aria-valuetext="显示至第 ${step} 次"><output id="code-sample-label" for="code-sample-step">${step} / 5</output><div id="code-sample-values" class="code-sample-values" aria-live="polite"></div></div>`;}
export function tokenTools(brush){return `<span class="code-gesture-note">拖动框选条件 · 双击清除</span><button class="text-action" id="code-clear-brush" ${brush?'':'hidden'}>清除框选</button>`;}
export function numericControls(brush,categories,labels){const b=brush || [0,700,0,100];return `<details class="code-numeric-filter"><summary>精确范围筛选</summary><form id="code-range-form"><label>最少 token<input name="xmin" type="number" min="0" step="any" value="${b[0]}" required></label><label>最多 token<input name="xmax" type="number" min="0" step="any" value="${b[1]}" required></label><label>最低通过率 %<input name="ymin" type="number" min="0" max="100" step="any" value="${b[2]}" required></label><label>最高通过率 %<input name="ymax" type="number" min="0" max="100" step="any" value="${b[3]}" required></label><button class="text-action" type="submit">应用范围</button><button class="text-action" id="code-reset-range" type="button">全部条件</button></form><div class="code-error-keyboard"><label for="code-keyboard-error">错误类型</label><select id="code-keyboard-error" class="form-select form-select-sm">${categories.map(c=>`<option value="${c}">${esc(labels[c] || c)}</option>`).join('')}</select><button class="text-action" id="code-keyboard-error-open">查看错误记录</button></div></details>`;}
function makeTip(){const el=document.createElement('div');el.className='code-hover-tip';el.setAttribute('role','tooltip');el.hidden=true;document.body.append(el);return el;}
function showTip(el,event,html){el.innerHTML=html;el.hidden=false;const box=el.getBoundingClientRect();el.style.left=Math.max(8,Math.min((event?.clientX || 40)+14,window.innerWidth-box.width-12))+'px';el.style.top=Math.max(8,Math.min((event?.clientY || 80)+14,window.innerHeight-box.height-12))+'px';}
function viewText(svg){const clone=svg.cloneNode(true);clone.querySelectorAll('[tabindex]').forEach(e=>e.removeAttribute('tabindex'));clone.setAttribute('xmlns',namespace);return new XMLSerializer().serializeToString(clone);}
export async function enhanceStatic(root){
 const ticket=generation;
 try{const d3=await libraries.load('d3');if(ticket!==generation || !root.isConnected)return;
  const tip=makeTip();const svg=root.querySelector('#code-publication > svg');if(!svg)return;
  const items=d3.select(svg).selectAll('[data-code-model]');
  const focus=model=>{
   items.each(function(){const other=this.dataset.codeModel!==model;d3.select(this).style('opacity',other?.25:1);const hit=this.id.endsWith('-hit');if(hit)d3.select(this).selectAll('path').style('fill',other?'white':'black').style('fill-opacity',other?.7:.001);});
   d3.select(svg).selectAll('[id^="code-trend-"], [id^="code-band-"]').style('opacity',function(){return this.id.endsWith(model)?1:.18;});
  };
  const clear=()=>{tip.hidden=true;items.style('opacity',null);items.filter(function(){return this.id.endsWith('-hit');}).selectAll('path').style('fill',null).style('fill-opacity',null);d3.select(svg).selectAll('[id^="code-trend-"], [id^="code-band-"]').style('opacity',null);};
  items.on('pointerenter.focus',function(event){focus(this.dataset.codeModel);showTip(tip,event,esc(this.dataset.codeLabel || this.getAttribute('aria-label') || ''));}).on('pointermove.focus',function(event){showTip(tip,event,esc(this.dataset.codeLabel || this.getAttribute('aria-label') || ''));}).on('pointerleave.focus',clear).on('focus.focus',function(){focus(this.dataset.codeModel);}).on('blur.focus',clear);
  cleanups.push(()=>{items.on('.focus',null);tip.remove();});
 }catch{ /* The original SVG and record controls remain usable. */ }
}
export async function enhanceSampling(root,state,data,onStep){
 const ticket=generation,svg=root.querySelector('#code-publication > svg');
 if(!svg)return;
 let d3;try{d3=await libraries.load('d3');}catch{return;}
 if(ticket!==generation || !root.isConnected)return;
 const button=root.querySelector('#code-play'),slider=root.querySelector('#code-sample-step'),out=root.querySelector('#code-sample-label'),values=root.querySelector('#code-sample-values');
 const points=[...svg.querySelectorAll('[id^="pass-"]')];const xs=[0,1,2,3,4].map(i=>+(points.find(p=>p.id.endsWith('-'+i))?.querySelector('use')?.getAttribute('x') || 0));
 if(xs.some(x=>!Number.isFinite(x)) || xs[4]<=xs[0])return;
 const clipId='code-reveal-'+ticket;const defs=d3.select(svg).append('defs');const clip=defs.append('clipPath').attr('id',clipId).attr('clipPathUnits','userSpaceOnUse').append('rect').attr('x',xs[0]-8).attr('y',0).attr('height',10000);
 d3.select(svg).selectAll('[id^="code-trend-"], [id^="code-band-"]').attr('clip-path','url(#'+clipId+')');
 let step=state.step || 5, timer=null;
 const stop=()=>{if(timer)clearInterval(timer);timer=null;button.setAttribute('aria-pressed','false');button.querySelector('span').textContent='播放';button.querySelector('svg').innerHTML='<path d="M6 3.5 16 10 6 16.5Z"/>';};
 const draw=(next,animate=true)=>{
  step=next;slider.value=step;slider.setAttribute('aria-valuetext','显示至第 '+step+' 次');out.value=step+' / 5';out.textContent=step+' / 5';
  const width=xs[step-1]-xs[0]+16;clip.interrupt('reveal');
  if(animate && !libraries.reducedMotion())clip.transition('reveal').duration(260).ease(d3.easeCubicOut).attr('width',width);else clip.attr('width',width);
  d3.select(svg).selectAll('[id^="pass-"], [id^="gain-"], [id^="code-lastgain-"]').each(function(){let sample=this.id.startsWith('pass-')?+this.id.split('-').at(-1)+1:this.id.startsWith('gain-')?+this.id.split('-').at(-1):5;const hidden=sample>step;d3.select(this).style('visibility',hidden?'hidden':null).attr('aria-hidden',hidden?'true':null);if(this.hasAttribute('data-code-action'))this.setAttribute('tabindex',hidden?'-1':'0');});
  const ms=state.model==='all'?data.models.map(m=>m.id):[state.model];values.innerHTML=`<span>Pass@${step}</span>`+ms.map(mid=>{const r=data.stats.find(r=>r.model===mid && r.prompt===state.prompt),m=data.models.find(m=>m.id===mid);return `<span title="${esc(m.name)}"><i style="background:${m.color}"></i><span class="visually-hidden">${esc(m.name)}</span><strong>${pct(r.pass[step-1],2)}</strong></span>`;}).join('');
  onStep(step);
 };
 stopPlayback=stop;
 const visibleObserver=new IntersectionObserver(entries=>{if(!entries[0].isIntersecting)stop();});visibleObserver.observe(root.querySelector(".code-playback"));cleanups.push(()=>visibleObserver.disconnect());
 button.disabled=false;button.onclick=()=>{if(timer){stop();return;}if(step===5)draw(1,false);button.setAttribute('aria-pressed','true');button.querySelector('span').textContent='暂停';button.querySelector('svg').innerHTML='<path d="M6 4v12M14 4v12"/>';timer=setInterval(()=>{if(document.hidden){stop();return;}draw(Math.min(5,step+1));if(step===5)stop();},1100);};
 slider.oninput=()=>{stop();draw(+slider.value);};
 const onVisibility=()=>{if(document.hidden)stop();};document.addEventListener('visibilitychange',onVisibility);
 draw(step,false);snapshotExport=()=>{stop();clip.interrupt('reveal').attr('width',xs[step-1]-xs[0]+16);return viewText(svg);};
 cleanups.push(()=>{stop();clip.interrupt('reveal');document.removeEventListener('visibilitychange',onVisibility);});
}
function pointsFor(data,k){return data.stats.filter(r=>r.prompt!=='__all').map(r=>({model:r.model,model_name:names[r.model],prompt:r.prompt,tokens:r.mean_output_tokens,score:r.pass[k-1]*100,extraction:(r.errors.extraction_error || 0)/r.n*100,n:r.n}));}
function selectionFor(data,k,brush){return data.stats.filter(r=>r.prompt!=='__all' && (!brush || (r.mean_output_tokens>=brush[0] && r.mean_output_tokens<=brush[1] && r.pass[k-1]*100>=brush[2] && r.pass[k-1]*100<=brush[3])));}
function compositeSvg(left,right,summary){const w=1600,h=650;return `<svg xmlns="${namespace}" xmlns:xlink="http://www.w3.org/1999/xlink" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><rect width="100%" height="100%" fill="white"/><text x="40" y="35" font-family="Times New Roman" font-size="23" font-weight="bold">Output length, test performance and failure rates</text><svg x="25" y="60" width="970" height="510" viewBox="0 0 ${left.getAttribute('width')} ${left.getAttribute('height')}">${left.innerHTML}</svg><text x="1015" y="83" font-family="Times New Roman" font-size="18" font-weight="bold">Failure rates</text><svg x="1015" y="60" width="560" height="510" viewBox="0 0 ${right.getAttribute('width')} ${right.getAttribute('height')}">${right.innerHTML}</svg><text x="45" y="595" font-family="Times New Roman" font-size="15">${esc(summary)}</text><text x="45" y="624" font-family="Times New Roman" font-size="13" fill="#60606a">Source: code-generation@9dfc592. 193 matched tasks; 5 independent samples. Environment exclusions omitted. Exploratory selection.</text></svg>`;}
export async function enhanceTokens(root,state,data,callbacks){
 const ticket=generation,host=root.querySelector('#code-publication');
 selection=selectionFor(data,state.k,state.brush);
 let vega,vl;try{vega=await libraries.load('vega');vl=await libraries.load('vegaLite');}catch(e){callbacks.onUnavailable(e.message);return;}
 if(ticket!==generation || !root.isConnected)return;
 const nodes=pointsFor(data,state.k), ymax=Math.max(50,Math.ceil(Math.max(...nodes.map(r=>r.score))/10)*10);
 const spec=JSON.parse(JSON.stringify(data.scatter_spec));spec.data={values:nodes};spec.encoding.y.axis.title=`Pass@${state.k} (%)`;spec.encoding.y.scale.domain=[0,ymax];
 if(state.brush)spec.params[0].value={x:state.brush.slice(0,2),y:state.brush.slice(2,4)};
 const scaffold=document.createElement('div');scaffold.className='code-linked-surface';scaffold.innerHTML='<div class="code-scatter-panel"><h2>Output length and test performance</h2><div id="code-vega-scatter"></div></div><div class="code-error-panel"><h2>Failure rates</h2><div id="code-linked-errors" role="img" aria-label="所选条件的错误率，点柱查看对应评分"></div></div><p class="code-linked-summary" id="code-brush-summary" role="status" aria-live="polite"></p>';
 let compiled;try{compiled=vl.compile(spec).spec;}catch(e){callbacks.onUnavailable(e.message);return;}
 host.replaceChildren(scaffold);host.classList.add('code-interactive-host');
 const chart=window.echarts.init(scaffold.querySelector('#code-linked-errors'),null,{renderer:'svg'});
 const tip=makeTip();let pending=null,persistTimer=null,dragStart=null,disposed=false;
 const view=new vega.View(vega.parse(compiled),{renderer:'svg',hover:true}).initialize(scaffold.querySelector('#code-vega-scatter'));
 const refresh=()=>{
  if(disposed)return;selection=selectionFor(data,state.k,state.brush);const n=selection.reduce((a,r)=>a+r.n,0);const mean=n?selection.reduce((a,r)=>a+r.pass[state.k-1],0)/selection.length:0;
  const cats=data.error_categories.map(cat=>({cat,count:selection.reduce((a,r)=>a+(r.errors[cat] || 0),0)})).sort((a,b)=>b.count-a.count);
  const summary=`${selection.length} / 93 个条件 · ${fmt(n)} 条可评回答${n?` · 平均 Pass@${state.k} ${pct(mean,2)}`:''}`;
  scaffold.querySelector('#code-brush-summary').textContent=summary;callbacks.onSelection(selection,state.brush);
  chart.setOption({aria:{enabled:true,description:`${selection.length} 个条件、${n} 条可评回答。`+cats.map(r=>`${errors[r.cat]} ${r.count} 条，${n?(r.count/n*100).toFixed(2):0}%。`).join(' ')},animation:!libraries.reducedMotion(),animationDuration:0,animationDurationUpdate:220,textStyle:{fontFamily:'Times New Roman',color:'#353842',fontSize:12},grid:{left:128,right:20,top:51,bottom:53},xAxis:{type:'value',min:0,max:100,name:'Share of selected responses (%)',nameLocation:'middle',nameGap:30,nameTextStyle:{fontSize:12},axisLabel:{fontSize:11},splitLine:{lineStyle:{color:'#e8e7ed'}}},yAxis:{type:'category',inverse:true,data:cats.map(r=>errors[r.cat]),axisLine:{show:false},axisTick:{show:false},axisLabel:{fontSize:12,color:'#54545b'}},tooltip:{confine:true,backgroundColor:'#fff',borderColor:'#e5e3eb',textStyle:{color:'#252830',fontFamily:'Times New Roman',fontSize:12},formatter:p=>`${esc(errors[cats[p.dataIndex].cat])}<br>${fmt(cats[p.dataIndex].count)} / ${fmt(n)} (${pct(n?cats[p.dataIndex].count/n:0,1)})`},series:[{id:'selected-errors',type:'bar',barMaxWidth:13,data:cats.map(r=>({value:n?r.count/n*100:0,category:r.cat,itemStyle:{color:r.cat==='extraction_error'?'#8958b4':'#a9a1b9'}})),emphasis:{itemStyle:{color:'#65428d'}}}]});
  chart.off('click');chart.on('click',p=>{if(p.data?.category)callbacks.onRecords({conditions:selectedConditions(),error:p.data.category},errors[p.data.category]+' / 框选条件');});
  snapshotExport=()=>{const left=scaffold.querySelector('#code-vega-scatter svg'),right=scaffold.querySelector('#code-linked-errors svg');return left && right?compositeSvg(left,right,summary):null;};
 };
 const schedule=value=>{
  const x=value?.tokens || value?.x,y=value?.score || value?.y;
  state.brush=Array.isArray(x) && Array.isArray(y) && x.length===2 && y.length===2 && x[0]!==x[1] && y[0]!==y[1]?[...x,...y].map(v=>+v.toFixed(6)):null;
  if(pending)cancelAnimationFrame(pending);pending=requestAnimationFrame(()=>{pending=null;refresh();});
  callbacks.onState({...state},false);if(persistTimer)clearTimeout(persistTimer);persistTimer=setTimeout(()=>callbacks.onState({...state},true),140);
 };
 view.addSignalListener('codeBrush',(_,value)=>schedule(value));
 view.addEventListener('pointerdown',event=>{dragStart=[event.clientX,event.clientY];});
 view.addEventListener('pointerup',()=>{if(persistTimer)clearTimeout(persistTimer);queueMicrotask(()=>{if(!disposed)callbacks.onState({...state},true);});});
 view.addEventListener('click',(event,item)=>{const r=item?.datum;if(r?.model && r?.prompt && (!dragStart || Math.hypot(event.clientX-dragStart[0],event.clientY-dragStart[1])<4)){tip.hidden=true;callbacks.onCondition({model:r.model,prompt:r.prompt,k:state.k});}});
 view.addEventListener('pointermove',(event,item)=>{const r=item?.datum;if(r?.model && r?.prompt)showTip(tip,event,`<strong>${esc(r.model_name)}</strong><br>${esc(r.prompt)}<br>${fmt(r.tokens,1)} output tokens · Pass@${state.k} ${fmt(r.score,2)}%<br>Extraction failure ${fmt(r.extraction,1)}%`);else tip.hidden=true;});
 view.addEventListener('pointerout',()=>{tip.hidden=true;});
 cleanups.push(()=>{disposed=true;if(pending)cancelAnimationFrame(pending);if(persistTimer)clearTimeout(persistTimer);view.finalize();chart.dispose();tip.remove();});
 try{await view.runAsync();if(ticket!==generation || !root.isConnected)return;
  scaffold.querySelectorAll('.codeBrush_brush_bg,.codeBrush_brush').forEach(el=>el.setAttribute('aria-label','图表框选范围；也可使用下方精确范围筛选'));
  refresh();}catch(e){callbacks.onUnavailable(e.message);return;}
 const observer=new ResizeObserver(()=>{if(!disposed)chart.resize();});observer.observe(scaffold);cleanups.push(()=>observer.disconnect());
 // Native buttons are available when direct manipulation is inconvenient.
 const svg=scaffold.querySelector('#code-vega-scatter svg');if(svg){svg.setAttribute('role','img');svg.setAttribute('aria-label','93 个模型与提示条件。拖动框选；精确范围筛选提供键盘替代。');}
}
