import { researchContent, renderQuestion, renderCollection, renderCleaning, renderConclusion, bindContent } from './research-content.js';
import { renderHome, mountHome } from './research-home.js';
import { renderFeedbackExtension } from './research-feedback-extension.js';
import { renderCompactFindings } from './research-findings-compact.js';

const $ = (selector, root = document) => root.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
const CHAPTERS=[
 {id:'question',label:'研究问题',title:'同一道任务，怎样让模型做得更好？',intro:'从提示词策略出发，在数学、文档与代码三类任务中比较回答质量和输出开销，再沿任务特性研究证据位置与执行反馈。'},
 {id:'collection',label:'采集设计',title:'四个维度，具体怎样写 Prompt？',intro:'相同题目，替换作答指令，记录每次回答。'},
 {id:'cleaning',label:'数据处理',title:'异名字段，清洗后统一保存',intro:'两类原始来源 → 同义字段映射 → 同一份21列数据。'},
 {id:'findings',label:'核心发现',title:'核心发现',intro:'四个总体规律，三个任务专项。'},
 {id:'conclusion',label:'总结与反思',title:'从实测发现，到五条使用建议',intro:'把研究中的对照结果，转化为选择提示、组织证据和使用反馈的依据。'}
];
const TOPICS=[
 {id:'budget',group:'总体规律',n:'01',name:'Token投入与边际收益',title:'多一些 Token，能多解决多少问题？',intro:'把实际输出开销与任务成功率放在一起，观察对数关系与边际收益的变化。',reading:'先读实测点，再读拟合线。对比前后区间，每增加一份输出预算，成功率带来的变化并不相同。切换模型与题库，查看这种关系的适用范围。',scope:'实际输出Token · 原生评分 · 同条件对照',explore:{chart:'bubble',dataset:'reasoning',task:'gsm8k',prompt:'__core'}},
 {id:'scale',group:'总体规律',n:'02',name:'模型规模与表现',title:'模型更大，收益体现在哪里？',intro:'沿Scaling Law的方向，对照已核实的模型参数规模、任务表现和输出开销。',reading:'把模型规模与同条件表现对应起来。已知参数量保留真实值；未知规模保留为未知。规模效应是固定研究主题，模型代际、训练方式与任务差异也会影响比较。',scope:'已核实参数量 · 同条件表现 · 任务分开统计',explore:{chart:'bubble',dataset:'reasoning',task:'math500',prompt:'DefaultCoT',bubble:'parameters'}},
 {id:'concise',group:'总体规律',n:'03',name:'简洁思考与输出效率',title:'保留分步要求，压缩表达开销。',intro:'从三种提示的同题对照，到17个跨任务分组，检查简洁要求能否在减少Token的同时维持质量。',reading:'Qwen2.5 / GSM8K的简洁分步输出比默认分步少21.5%，得分点估计相近。跨任务17组全部缩短输出，15组得分点估计持平或提高；少数下降结果也保留在图中。',scope:'三策略对照 · 17个模型×任务分组 · 同题比较',explore:{chart:'box',dataset:'reasoning',task:'gsm8k',prompt:'__core'}},
 {id:'limits',group:'总体规律',n:'04',name:'极端限长与输出反弹',title:'限制更紧，输出为什么反而更长？',intro:'同时观察提示中的限制档位、实际返回Token、任务得分与截断，呈现极端约束的反效果。',reading:'词数上限从10压到1，12个模型×题库分组中有9组输出增加。提示中的词数、字母数与接口Token是不同单位，需要沿各自真实条件比较。',scope:'实测限制档位 · 实际输出Token · 截断与评分',explore:{chart:'distribution',dataset:'reasoning',task:'math500',prompt:'CharLimit(10)'}},
 {id:'language',group:'任务专项',n:'05',name:'数学中的中英文对照',title:'相同数学题，换一种作答模板。',intro:'在模型与题库之间切换，观察中文条件下的得分、输出长度和完成情况。',reading:'MATH500上四模型全部缩短输出，三模型提分；Qwen3从58.0%到69.5%。切换到其他题库继续比较，保留结论的任务范围。',scope:'相同英文题目 · 默认与中文模板 · 模型与题库',explore:{chart:'heatmap',dataset:'reasoning',task:'math500',prompt:'__all'}},
 {id:'position',group:'任务专项',n:'06',name:'文档中的证据位置',title:'关键资料的位置，也改变模型差距。',intro:'固定问题、20篇资料和提示，沿九个实测位置观察两条模型曲线。',reading:'相关证据在首位时，Qwen3相对Qwen2.5的优势为16.5个百分点；在末位缩小到2.5个百分点。九位置专项与原三位置提示实验分别保留。',scope:'200道题 · 两模型 · 九个实测位置 · 配对比较',explore:{chart:'position',dataset:'document_qa',task:'document_qa',prompt:'NoCoT'}},
 {id:'feedback',group:'任务专项',n:'07',name:'代码中的执行反馈',title:'给出具体反例，修复才更有方向。',intro:'从通过率曲线进入失败用例和实际代码，观察反馈方式怎样影响每轮修改。',reading:'Qwen3相同初稿通过126 / 164题，四次修改后自查组通过129题、状态反馈130题、具体用例反馈141题。独立采样与多轮反馈修复分别呈现。',scope:'164道题 · 同一初稿 · 四种处理 · 初稿＋四次生成',explore:{panel:'code',view:'sampling'}}
];

const topicById = id => TOPICS.find(topic => topic.id === id);
const HIGHLIGHTS = {
  budget: ['输出增加，收益逐渐放缓。', 'Qwen2.5 / GSM8K，七档真实限制的对数拟合 R² = 0.939。', '横轴使用实际输出Token；不同模型与题库分别比较。'],
  scale: ['模型规模与任务表现一起看。', 'Qwen2.5为7.61B，Qwen3为8.2B；未知规模保持缺失。', '模型代际、训练和任务同时影响结果，现有数据支持同条件对照。'],
  concise: ['17组输出全部缩短，15组评分持平或提高。', 'Qwen2.5 / GSM8K：简洁分步节省21.5%输出Token。', '保留推理要求，压缩表达；少数下降分组也完整呈现。'],
  limits: ['约束收得更紧，实际输出可能反弹。', '词数上限从10压到1，12个分组中有9组输出增加。', '词数、字母数和接口Token各按原有单位比较。'],
  language: ['中文模板的优势，在数学任务中显现。', 'MATH500：四模型输出都更短，三模型评分提高。', 'Qwen3从58.0%提高到69.5%；题目仍为同一批英文题。'],
  position: ['证据移到末位，模型优势随之缩小。', 'Qwen3相对Qwen2.5的优势：首位16.5个百分点，末位2.5个百分点。', '固定20篇资料、200道题，九个位置分别实测。'],
  feedback: ['具体失败用例，比笼统自查更有效。', '共同初稿126 / 164题通过；具体反例反馈四次修改后达到141题。', '自行检查129题，状态反馈130题；独立重采样另作对照。']
};
let catalog = {charts:[]};
let feedbackPublication;
let route;
let disposeContent;
let disposeHome;
let disposeExplorer;
let epoch = 0;
let toastTimer;

function readRoute() {
  const params = new URLSearchParams(location.search);
  const hash = location.hash.slice(1);
  let chapter = params.get('chapter') || (CHAPTERS.some(item => item.id === hash) ? hash : 'home');
  if(hash === 'gateway') chapter = 'home';
  if(hash === 'landscape') chapter = 'atlas';
  if(!['home','atlas',...CHAPTERS.map(item => item.id)].includes(chapter)) chapter = 'home';
  const topic = topicById(params.get('topic'))?.id || 'overview';
  return {chapter,topic,filter:params.get('filter') || 'all',figure:params.get('figure') || ''};
}
function routeURL(next) {
  const params = new URLSearchParams();
  if(next.chapter !== 'home') params.set('chapter', next.chapter);
  if(next.chapter === 'atlas' && next.filter && next.filter !== 'all') params.set('filter',next.filter);
  return location.pathname + (params.size ? '?' + params.toString() : '');
}
function go(next, {replace = false} = {}) {
  const value = {chapter:'home',topic:'overview',filter:'all',...next};
  history[replace ? 'replaceState' : 'pushState']({},'',routeURL(value));
  route = readRoute();
  render();
  window.scrollTo({top:0,behavior:'instant'});
}
function notify(message) {
  clearTimeout(toastTimer);
  const toast = $('#research-toast');
  toast.textContent = message;
  toast.classList.add('visible');
  toastTimer = setTimeout(() => toast.classList.remove('visible'),2500);
}
function download(filename, content, type) {
  const url = URL.createObjectURL(new Blob([content], {type}));
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = filename;
  document.body.append(anchor); anchor.click(); anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url),1000);
}
function mainFigure(chart) {
  return `<figure class="main-figure" data-chart-id="${esc(chart.id)}"><div class="figure-canvas" tabindex="0" role="region" aria-label="${esc(chart.title)}，图形可横向滚动"><img class="primary-figure-img" src="${esc(chart.file)}" alt="${esc(chart.title)}" loading="lazy" width="${chart.width}" height="${chart.height}"></div></figure>`;
}
function supportFigure(chart, tools = false) {
  const wide = /landscape|matrix|real-code-case|fit-comparison/.test(chart.id);
  return `<figure class="support-figure${wide ? ' support-wide' : ''}" data-chart-id="${esc(chart.id)}"><img src="${esc(chart.file)}" alt="${esc(chart.title)}" loading="lazy" width="${chart.width}" height="${chart.height}"><figcaption><p>${esc(chart.description || chart.subtitle)}</p>${tools ? `<div class="figure-downloads"><a href="${esc(chart.file)}" download>SVG</a><button data-figure-csv="${esc(chart.id)}">数值CSV</button></div>` : ''}</figcaption></figure>`;
}
function findingsHTML() {
  return renderCompactFindings(catalog, feedbackPublication);
}

function atlasHTML() {
  const charts = catalog.charts.filter(chart => route.filter === 'all' || chart.topic === route.filter);
  return `<div class="catalog-tools"><label for="atlas-filter">图稿主题<select id="atlas-filter"><option value="all">全部37张</option>${TOPICS.map(topic => `<option value="${topic.id}" ${route.filter === topic.id ? 'selected' : ''}>${topic.name}</option>`).join('')}</select></label><a href="assets/research-svg.zip" download>下载完整SVG与数值图包</a></div><div class="support-grid atlas-grid">${charts.map(chart => supportFigure(chart,true)).join('')}</div>${feedbackPublication?`<section class="atlas-feedback-host" aria-label="完整代码反馈补充图册">${renderFeedbackExtension(feedbackPublication.evidence,feedbackPublication.figures,feedbackPublication.legacyEvidence)}</section>`:''}<section id="research-explorer-host" class="archive-explorer" aria-label="完整交互图表库"></section>`;
}
function renderNavigation() {
  $('#chapter-nav').innerHTML = CHAPTERS.map((chapter,index) => `<a href="?chapter=${chapter.id}" ${route.chapter === chapter.id ? 'aria-current="page"' : ''}><span class="chapter-number">${String(index + 1).padStart(2,'0')}</span>${chapter.label}</a>`).join('');
}
function appendSupplementContext(main) {
  if(!feedbackPublication) return;
  const e=feedbackPublication.evidence,fmt=value=>Number(value).toLocaleString('zh-CN');
  if(route.chapter === 'collection') $('.rc-collection',main)?.insertAdjacentHTML('beforeend',`<section class="rc-collection-ledger" aria-label="代码反馈补充采集"><div class="rc-section-heading"><h3>代码反馈补充批次</h3></div><p>${fmt(e.planned_tasks)}道题、${fmt(e.models.length)}个模型，各有${fmt(e.repeats_per_task)}份独立初稿。每份初稿在${fmt(e.arms.length)}条策略链中再生成${fmt(e.rounds-1)}版，共保存${fmt(e.saved_physical_responses)}份有效回答。</p><p class="rc-source-note">原五项实验保存${fmt(researchContent.totalRecords)}份回答，本轮补充批次另存；累计${fmt(researchContent.totalRecords+e.saved_physical_responses)}份物理回答。共享初稿只计一次，重复和修复版本保持同题配对关系。</p></section>`);
  const unified=feedbackPublication.unifiedFormat;
  if(route.chapter === 'cleaning' && unified?.complete) $('.rc-storage-summary',main)?.insertAdjacentHTML('beforeend',`<p class="rc-source-note">代码反馈补充批次的${fmt(unified.records)}份物理响应，另存为同样${fmt(unified.fields.length)}列的 <code>unified-records.csv.gz</code>。匿名父版本可追溯；三份独立初稿编号另存 <code>lineage.csv</code>。完整保留测试使用独立评分名称，与原Mini分别统计。</p>`);
}
async function render() {
  const version = ++epoch;
  disposeContent?.(); disposeContent = null;
  disposeHome?.(); disposeHome = null;
  disposeExplorer?.(); disposeExplorer = null;
  document.body.dataset.view = route.chapter === 'home' ? 'home' : 'chapter';
  document.body.dataset.chapter = route.chapter;
  renderNavigation();
  const main = $('#main-content');
  if(route.chapter === 'home') {
    main.innerHTML = renderHome();
    disposeHome = mountHome(main,{onNavigate:chapter => go({chapter})});
    document.title = '知微 · 模型行为研究';
    return;
  }
  const chapter = CHAPTERS.find(item => item.id === route.chapter);
  const title = chapter?.title || '科研图稿与交互图表';
  const intro = chapter?.intro || '完整保留37张科研SVG和原有交互探索。';
  const body = route.chapter === 'question' ? renderQuestion() : route.chapter === 'collection' ? renderCollection() : route.chapter === 'cleaning' ? renderCleaning() : route.chapter === 'conclusion' ? renderConclusion() : route.chapter === 'atlas' ? atlasHTML() : findingsHTML();
  main.innerHTML = `${route.chapter === 'question' ? '' : `<section class="section-intro"><h1>${title}</h1>${intro ? `<p>${intro}</p>` : ''}</section>`}${body}`;
  appendSupplementContext(main);
  document.title = `${chapter?.label || '科研图稿'} · 知微`;
  if(route.chapter === 'question') $('.rc-lead',main)?.remove();
  if(['question','collection','cleaning','conclusion'].includes(route.chapter)) disposeContent = bindContent(main,{notify});
  const filter = $('#atlas-filter');
  if(filter) filter.onchange = () => go({chapter:'atlas',filter:filter.value},{replace:true});
  if(route.chapter === 'atlas') {
    try {
      const {mountExplorer} = await import('./research-explorer.js');
      if(version !== epoch) return;
      const explorer = await mountExplorer($('#research-explorer-host'),{notify});
      if(version === epoch) disposeExplorer = () => explorer?.dispose();
      else explorer?.dispose();
    } catch(error) { if(version === epoch) $('#research-explorer-host').textContent = error.message; }
  }
}
document.addEventListener('click',event => {
  if(event.defaultPrevented) return;
  const anchor = event.target.closest('a');
  if(anchor && anchor.origin === location.origin && anchor.pathname === location.pathname && !anchor.download && !event.metaKey && !event.ctrlKey && !event.shiftKey && event.button === 0) {
    const params = new URLSearchParams(anchor.search);
    if(params.has('chapter') || anchor.hasAttribute('data-home-link')) {
      event.preventDefault(); go({chapter:params.get('chapter') || 'home',topic:params.get('topic') || 'overview'}); return;
    }
  }
  const button = event.target.closest('[data-figure-csv]');
  if(button) {
    const chart = catalog.charts.find(item => item.id === button.dataset.figureCsv);
    if(!chart?.data?.length) return;
    const fields = Object.keys(chart.data[0]);
    const csv = '\ufeff' + [fields,...chart.data.map(row => fields.map(field => row[field]))].map(row => row.map(value => '"'+String(value ?? '').replaceAll('"','""')+'"').join(',')).join('\r\n');
    download(`知微-${chart.id}.csv`,csv,'text/csv;charset=utf-8');
    notify('已导出当前图稿数值');
  }
});
window.addEventListener('popstate',() => {route = readRoute(); render();});
window.addEventListener('pagehide',() => {disposeContent?.();disposeHome?.();disposeExplorer?.();});
async function init() {
  try {
    const response = await fetch('data/research-charts.json');
    if(!response.ok) throw new Error('科研图册未找到，请重新启动系统。');
    catalog = await response.json();
    const supplement = document.querySelector('meta[name="code-feedback-extension"]')?.content;
    if(supplement) {
      const result = await fetch(supplement);
      if(!result.ok) throw new Error('代码反馈补充实验未找到，请重新构建系统。');
      const value = await result.json();
      if(!renderFeedbackExtension(value.evidence,value.figures,value.legacyEvidence)) throw new Error('代码反馈补充实验尚未通过完整性检查。');
      feedbackPublication = value;
    }
    route = readRoute(); await render();
  } catch(error) {
    $('#main-content').innerHTML = `<section class="error-message"><h1>研究内容未能打开</h1><p>${esc(error.message)}</p><button onclick="location.reload()">重新读取</button></section>`;
  }
}
init();
