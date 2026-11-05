import {baseURL,chromiumPath,screenshot} from './helpers.mjs';
import {readFile,writeFile,readdir} from 'node:fs/promises';
import {resolve} from 'node:path';
export const root=resolve('artifacts/qa');
const source=await readFile('app/src/app.js','utf8');
const library=[...source.match(/const library = \{([\s\S]*?)\n\};/)[1].matchAll(/(\w+): "([^"]+)"/g)].map(m=>({key:m[1],label:m[2]}));
const codeSource=await readFile('app/src/code-study.js','utf8');
const codeViews=[...codeSource.match(/const VIEWS = \{([\s\S]*?)\};/)[1].matchAll(/(\w+):/g)].map(m=>m[1]);
const count=[...source.match(/const chapters = \[(.*?)\];/)[1].matchAll(/"[^"]+"/g)].length;
const data=JSON.parse(await readFile('app/data/narrative-evidence.json','utf8'));
export const routes=[
 {key:"deck-gateway",family:"deck",section:"gateway",url:"index.html?intro=0#gateway"},
 ...['question','collection','cleaning'].map(section=>({key:'deck-'+section,family:'deck',section,url:'index.html?intro=0#'+section})),
 ...Object.entries(data.directions).flatMap(([direction,config])=>config.models.flatMap(model=>['curve','heatmap'].map(view=>({key:`landscape-${direction}-${model}-${view}`,family:'landscape',section:'landscape',direction,model,view,url:`index.html?intro=0&overviewTask=${direction}&overviewModel=${model}&overviewView=${view}#landscape` })))),
 ...['baseline','cross'].map(view=>({key:'story-concise-'+view,family:'story',section:'findings',finding:'concise',view,url:`index.html?intro=0&finding=concise&view=${view}#findings`})),
 ...['math500','gsm8k','mmlu'].map(task=>({key:'story-language-'+task,family:'story',section:'findings',finding:'language',task,url:`index.html?intro=0&finding=language&task=${task}#findings`})),
 ...['deepseek','hy4','qwen','qwen3'].flatMap(model=>['math500','gsm8k','mmlu'].flatMap(task=>['WordLimit','CharLimit','TokenLimit'].map(limit=>({key:`story-limits-${model}-${task}-${limit}`,family:'story',section:'findings',finding:'limits',model,task,limit,url:`index.html?intro=0&finding=limits&model=${model}&task=${task}&family=${limit}#findings`})))),
 {key:'story-position',family:'story',section:'findings',finding:'position',url:'index.html?intro=0&finding=position#findings'},
 ...['qwen','qwen3'].map(model=>({key:'story-repair-'+model,family:'story',section:'findings',finding:'repair',model,url:`index.html?intro=0&finding=repair&repairModel=${model}#findings`})),
 {key:'efficiency',family:'publication',url:'explore.html#budget'},
 {key:'efficiency-prompts',family:'publication',url:'explore.html?view=prompts#budget'},
 {key:'position-matrix',family:'publication',url:'explore.html#position'},
 {key:'position-profile',family:'publication',url:'explore.html?figure=profile#position'},
 ...codeViews.map(key=>({key:'code-'+key,family:'code',url:'explore.html?codeView='+key+'#code'})),
 ...Array.from({length:count},(_,n)=>({key:'discovery-'+(n+1),family:'discovery',url:'explore.html#case-'+(n+1)})),
 ...library.map(({key,label})=>({key:'chart-'+key,label,chart:key,family:'library',url:'explore.html?mode=explore&chart='+key+(['position','timeline','tree','flow'].includes(key)?'&dataset=document_qa':'')+'#case-1'})),
 {key:'chart-flow-empty',family:'library',chart:'flow',empty:true,url:'explore.html?mode=explore&chart=flow&dataset=reasoning#case-1'}
];
export function inspectRoute(route){
 const visible=el=>!!el?.getClientRects().length;
 const deck=!!route.section,panel=deck?document.querySelector('.deck-panel.is-active'):document.querySelector('#stage');
 const title=panel?.querySelector(deck?'h1,h2':'h1')?.textContent.trim();
 let selected=true;
 if(deck){
  selected=document.body.dataset.section===route.section&&visible(panel)&&document.querySelectorAll('.deck-panel:not([hidden])').length===1;
  if(route.finding)selected&&=document.querySelector('.finding-nav [aria-current="page"]')?.dataset.chapter===route.finding&&!!document.querySelector('#plot svg');
  if(route.family==='landscape')selected&&=document.querySelector('[data-overview-direction][aria-pressed="true"]')?.dataset.overviewDirection===route.direction&&document.querySelector('[data-overview-model][aria-pressed="true"]')?.dataset.overviewModel===route.model&&document.querySelector('[data-overview-view][aria-pressed="true"]')?.dataset.overviewView===route.view;
 }else if(route.family==='library')selected=document.querySelector('#library-chart')?.value===route.chart;
 else if(route.family==='code')selected=!!document.querySelector(`[data-code-view="${route.key.slice(5)}"][aria-current="page"]`);
 else if(route.family==='discovery')selected=!!document.querySelector(`#chapter-nav [data-chapter="${Number(route.key.split('-')[1])-1}"][aria-current="page"]`);
 const checks=route.finding==='limits'?[["model",route.model],["task",route.task],["family",route.limit]]:route.finding==='language'?[["task",route.task]]:route.finding==='concise'?[["view",route.view]]:route.finding==='repair'?[["repair-model",route.model]]:[];
 for(const [name,value] of checks)selected&&=!!document.querySelector(`[data-${name}="${value}"][aria-pressed="true"]`);
 const nav=document.querySelector(deck?(route.section==='gateway'?'.topbar':'.research-actions'):'.research-nav');
 const navItems=[...nav.querySelectorAll('a,button')].map(el=>{const r=el.getBoundingClientRect();return{x:r.left,right:r.right,bottom:r.bottom,text:el.textContent.trim(),scrollable:nav.scrollWidth>nav.clientWidth&&/auto|scroll/.test(getComputedStyle(nav).overflowX)};});
 return{title,section:document.body.dataset.section||null,width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,selectedViewMatches:!!selected,svg:panel.querySelectorAll('svg').length,empty:!!panel.querySelector('.chart-empty'),background:getComputedStyle(document.body).backgroundColor,accent:getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(),artReady:!!document.querySelector('.wordmark-logo strong')&&getComputedStyle(document.querySelector('.wordmark-logo strong')).opacity==='1',nav:navItems,activeScroll:deck?{width:panel.clientWidth,content:panel.scrollWidth}:null,invalidValues:!!panel.querySelector('svg')&&(/\bNaN\b|Infinity/.test(panel.querySelector('svg').outerHTML))};
}
if(process.argv[1]===new URL(import.meta.url).pathname){
 const documents=(await readdir('app/dist')).filter(n=>n.endsWith('.html')).sort();if(documents.join(',')!=='explore.html,index.html')throw Error('Classify new HTML first');
 const result={baseCommit:'926c936a3571153eb855571b9ab7768e65c1c1f0',businessBase:'35f7318e45561da07c75eaf65374e4107004d5ec',previousVisualCommit:'926c936a3571153eb855571b9ab7768e65c1c1f0',entryDocuments:['index.html','explore.html'],routeCount:routes.length,routes,viewports:[1366,1440,1600,1920,2560],overlays:['collection-prompts','field-definitions','landscape-keyboard-cell','real-example','figure-data','method-scope','publication-method','condition-records','anonymous-record-detail','code-method','code-scoring-detail'],excluded:['PDF, CSV and SVG exports are downloads, not additional app pages'],discovery:'Latest deck sections, every landscape direction/model/view, all 36 limit combinations, all five findings, library source chart keys and code view enums.'};
 await writeFile(resolve(root,'site-inventory.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({routes:routes.length,charts:library.length}));
}
