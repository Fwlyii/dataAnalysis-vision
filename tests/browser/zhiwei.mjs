/** Current Zhiwei presentation: BASE_URL=http://127.0.0.1:8770/ node tests/browser/zhiwei.mjs. */
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {existsSync} from 'node:fs';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';

const require = createRequire(resolve('tests/package.json'));
const {chromium} = require('playwright-core');
const AxeBuilder = require('@axe-core/playwright').default;
const base = process.env.BASE_URL || 'http://127.0.0.1:8770/';
const out = resolve(process.env.ZHIWEI_QA_DIR || 'artifacts/qa/zhiwei');
await mkdir(resolve(out, 'screenshots'), {recursive:true});
const chrome = process.env.CHROMIUM_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const browser = await chromium.launch({headless:true, executablePath:existsSync(chrome) ? chrome : undefined, args:['--no-sandbox']});
const context = await browser.newContext({viewport:{width:1440,height:900}, reducedMotion:'reduce'});
const page = await context.newPage();
page.setDefaultTimeout(12000);
const results = [], errors = [], missing = [], requestFailures = [], screenshots = [], accessibility = [], layouts = [];
function observe(p) {
  p.on('pageerror', error => errors.push({type:'pageerror', message:error.message, url:p.url()}));
  p.on('console', message => {if(message.type()==='error') errors.push({type:'console', message:message.text(), url:p.url()});});
  p.on('response', response => {if(response.status()>=400) missing.push({url:response.url(), status:response.status()});});
  p.on('requestfailed', request => {if(request.failure()?.errorText!=='net::ERR_ABORTED') requestFailures.push({url:request.url(), error:request.failure()?.errorText});});
}
observe(page);
function assert(value, message) {if(!value) throw new Error(message);}
function record(name, pass, detail) {
  results.push({name, pass, detail});
  if(!pass) console.error('FAIL', name, JSON.stringify(detail));
}
async function test(name, action) {
  try {record(name, true, await action()); return true;}
  catch(error) {record(name, false, {error:error.message}); return false;}
}
const numbers = text => (String(text).replace(/[−–]/g,'-').replaceAll(',','').match(/[+-]?\d+(?:\.\d+)?/g)||[]).map(Number);
const closeTo = (actual, expected, label, tolerance=.051) => assert(Number.isFinite(actual) && Math.abs(actual-expected)<=tolerance, `${label}: ${actual} != ${expected}`);
const chart = (catalog, id) => {const row=catalog.charts.find(x=>x.id===id); assert(row, 'Missing scientific chart '+id); return row.data;};
const modelId = name => /qwen3/i.test(name) ? 'qwen3' : /qwen/i.test(name) ? 'qwen' : /deepseek/i.test(name) ? 'deepseek' : 'hy4';
const modelName = id => ({qwen:'Qwen2.5 7B', qwen3:'Qwen3 8B', deepseek:'DeepSeek Flash', hy4:'HY4 preview'}[id]);
const taskName = id => ({gsm8k:'GSM8K', math500:'MATH500', mmlu:'MMLU-Pro'}[id]);
const armName = (e,id) => e.arms.find(x=>x.id===id)?.label || id;

async function ready(p=page) {
  await p.locator('#specimen-stage svg').waitFor();
  await p.waitForFunction(()=>document.querySelectorAll('#case-tabs button').length===4 && document.querySelectorAll('#advice-list > li').length===5);
  await p.evaluate(()=>document.fonts.ready);
  assert(await p.locator('.error-screen').count()===0, 'Data loading error is visible');
}
async function section(id) {
  await page.locator('.deck-nav a[href="#'+id+'"]').click();
  await page.waitForFunction(id=>document.querySelector('.deck-nav a.is-active')?.getAttribute('href')==='#'+id, id);
}
async function findings(id) {
  await section('s4');
  await page.locator('#tab-'+id).click();
  await page.waitForFunction(id=>document.querySelector('#tab-'+id)?.getAttribute('aria-selected')==='true' && !document.querySelector('#page-'+id)?.inert, id);
}
async function tableFor(plate) {
  await page.locator('#'+plate).getByRole('button', {name:'查看数据表', exact:true}).click();
  await page.locator('#table-dialog[open]').waitFor();
  try {
    return await page.locator('#table-dialog').evaluate(dialog=>({
      title:dialog.querySelector('h3').textContent,
      headers:Array.from(dialog.querySelectorAll('thead th'), n=>n.textContent.trim()),
      rows:Array.from(dialog.querySelectorAll('tbody tr'), tr=>Array.from(tr.children, td=>td.textContent.trim())),
    }));
  } finally {
    await page.locator('#table-dialog [data-close]').click();
    await page.locator('#table-dialog').waitFor({state:'hidden'});
  }
}
async function screenshot(name) {
  const path=resolve(out,'screenshots',name+'.png');
  await page.screenshot({path}); screenshots.push({name,path});
}
async function scanAccessibility(name) {
  const report=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  const violations=report.violations.map(v=>({id:v.id, impact:v.impact, description:v.description,
    nodes:v.nodes.map(n=>({target:n.target, summary:n.failureSummary}))}));
  accessibility.push({name, violations});
  // Existing approved colors may need a separate visual decision. Preserve their
  // evidence as advisory findings; structurally critical failures remain a gate.
  const critical=violations.filter(v=>v.impact==='critical');
  assert(critical.length===0, 'Critical accessibility findings: '+critical.map(v=>v.id).join(', '));
  return {violations:violations.length, critical:critical.length, advisory:violations.filter(v=>v.impact!=='critical').map(v=>v.id)};
}

let source;
try {
  await page.goto(base, {waitUntil:'domcontentloaded'});
  await ready();
  await test('four scientific JSON snapshots match the repository bytes', async()=>{
    source={}; const hashes={};
    for(const name of ['summary','research-charts','research-content','code-feedback-extension']) {
      const response=await context.request.get(new URL('data/'+name+'.json',base).href);
      assert(response.ok(), 'Cannot read '+name);
      const remote=await response.body(), local=await readFile(resolve('app/data',name+'.json'));
      const digest=data=>createHash('sha256').update(data).digest('hex');
      assert(digest(remote)===digest(local), 'Built snapshot differs from canonical source: '+name);
      hashes[name]=digest(remote); source[name]=JSON.parse(remote.toString('utf8'));
    }
    return hashes;
  });
  assert(source?.['code-feedback-extension'], 'Scientific fixtures unavailable');
  const summary=source.summary, catalog=source['research-charts'], content=source['research-content'], ev=source['code-feedback-extension'].evidence;

  await test('five research sections and all seven findings render without loading errors',async()=>{
    assert(await page.locator('.deck-nav a').count()===5, 'Five-section navigation is incomplete');
    for(const id of ['s1','s2','s3','s4','s5']) assert(await page.locator('#'+id+' h1,#'+id+' h2').count()>0, 'Missing heading '+id);
    for(const id of ['budget','scale','concise','limits','language','position','trajectory']) assert(await page.locator('#plate-'+id+' svg').count()>0, 'Missing chart '+id);
    assert(await page.locator('#strategy-matrix button').count()===content.prompts.length && content.prompts.length===31, 'Prompt catalogue is incomplete');
    return {sections:5, findingPlates:7, promptStrategies:content.prompts.length};
  });
  await test('course materials link to the exact submitted PDF bytes',async()=>{
    const materials=[['course-assignment.pdf','guide/数据分析和可视化-题目2.pdf'],['case-report.pdf','report/case_report.pdf'],['defense-slides.pdf','presentation/defense_slides.pdf']];
    for(const [name,local] of materials) {
      const link=page.locator('.course-resources a[href="data/'+name+'"]');
      assert(await link.count()===1 && await link.getAttribute('target')==='_blank','Missing course material link: '+name);
      const response=await context.request.get(new URL('data/'+name,base).href);
      assert(response.ok(),'Course material cannot be downloaded: '+name);
      const delivered=await response.body(), original=await readFile(resolve(local));
      assert(delivered.subarray(0,5).toString()==='%PDF-','Course material is not a PDF: '+name);
      assert(delivered.equals(original),'Delivered course material differs from repository: '+name);
    }
    return {materials:materials.length};
  });
  await test('display ledger distinguishes the five shown experiments from frozen historical records',async()=>{
    const legacy=content.experiments.find(x=>x.id==='code_repair');
    const displayed=content.experiments.filter(x=>x.id!=='code_repair').reduce((total,x)=>total+x.records,0)+ev.saved_physical_responses;
    assert(content.totalRecords===248586 && legacy?.records===5576, 'Historical scope changed');
    assert(displayed===267610, 'Unexpected presentation scope');
    closeTo(numbers(await page.locator('[data-bind="allRecords"]').first().innerText())[0],displayed,'Hero response count',0);
    await section('s2'); const table=await tableFor('plate-ledger');
    assert(table.rows.length===5, 'Display ledger must contain five current experiment groups');
    const rows=table.rows.map(row=>numbers(row.at(-1))[0]);
    assert(rows.reduce((a,b)=>a+b,0)===displayed, 'Ledger rows do not sum to displayed total');
    return {frozenOriginal:content.totalRecords,historicalRepair:legacy.records,newFeedback:ev.saved_physical_responses,displayed};
  });
  await test('shared feedback drafts are counted once in the visible experimental design',async()=>{
    const independent=ev.planned_tasks*ev.models.length*ev.repeats_per_task*(1+ev.arms.length*(ev.rounds-1));
    assert(independent===24600 && independent===ev.saved_physical_responses, 'Feedback response accounting is not the shared-draft design');
    const table=await tableFor('plate-ledger'), row=table.rows.find(r=>r[0].includes('代码执行反馈'));
    assert(row, 'Feedback experiment missing from ledger');
    const formula=row[1].replace(/[（]/g,'(').replace(/[）]/g,')').replace(/[＋]/g,'+').replace(/[xX*]/g,'×').replace(/[^\d()+×.]/g,'');
    const expectedFormula=`${ev.planned_tasks}×${ev.models.length}×${ev.repeats_per_task}×(1+${ev.arms.length}×${ev.rounds-1})`;
    assert(formula===expectedFormula, 'Visible design must show one shared initial draft plus six groups of four revisions: '+row[1]);
    assert(ev.task_clusters===164 && ev.coverage.complete && ev.strong_trajectory_complete && ev.synthetic===false && ev.status==='complete', 'Published feedback evidence is incomplete');
    return {independentTasks:ev.planned_tasks,models:ev.models.length,repeats:ev.repeats_per_task,arms:ev.arms.length,revisions:ev.rounds-1,responses:independent,visibleFormula:row[1]};
  });
  await test('all five navigation links enter their corresponding section and survive refresh',async()=>{
    for(const id of ['s1','s2','s3','s4','s5']) {
      await section(id); assert(new URL(page.url()).hash==='#'+id, 'Navigation lost section '+id);
    }
    await page.reload({waitUntil:'domcontentloaded'}); await ready();
    assert(new URL(page.url()).hash==='#s5', 'Refresh lost selected section');
    await section('s1'); return true;
  });
  await test('model switching updates the complete 31-strategy specimen table from saved results',async()=>{
    await page.locator('#specimen-models button').filter({hasText:'Qwen3 8B'}).click();
    await page.locator('#specimen-legend button').click(); await page.locator('#table-dialog[open]').waitFor();
    let rows;
    try {rows=await page.locator('#table-dialog tbody tr').evaluateAll(nodes=>nodes.map(tr=>Array.from(tr.children,td=>td.textContent.trim())));}
    finally {await page.locator('#table-dialog [data-close]').click();}
    assert(rows.length===31,'Specimen table lost strategies');
    const row=rows.find(x=>x[1]==='DefaultCoT'); assert(row,'DefaultCoT missing');
    for(const [i,task] of ['gsm8k','math500','mmlu'].entries()) {
      const cell=summary.cells.find(c=>c.dataset==='reasoning' && c.model==='qwen3' && c.task===task && c.prompt==='DefaultCoT');
      closeTo(numbers(row[i+2])[0],100*cell.scores[0]/cell.n,'Specimen '+task);
    }
    return {model:'qwen3',strategies:rows.length,defaultScores:row.slice(2)};
  });
  await test('prompt exploration shows actual instructions and same-condition model scores',async()=>{
    await section('s2'); await page.locator('#strategy-matrix button').filter({hasText:'简洁分步'}).click();
    const text=await page.locator('#strategy-detail').innerText();
    assert(text.includes('BeConcise'),'Selected strategy is not identified');
    const prompt=content.prompts.find(p=>p.id==='BeConcise');
    assert(prompt && await page.locator('#strategy-detail .sd-ins').textContent()===prompt.instruction,'Displayed instruction differs from the saved prompt');
    const grid=page.locator('#strategy-detail [role="table"]');
    assert(await grid.getByRole('rowheader').count()===4,'Four-model comparison is incomplete');
    const cells=await grid.getByRole('cell').evaluateAll(nodes=>nodes.map(n=>({label:n.getAttribute('aria-label'),score:n.querySelector('b')?.textContent})));
    assert(cells.length===12,'The four-model, three-task comparison lost conditions');
    for(const mid of ['qwen','qwen3','deepseek','hy4']) {
      for(const task of ['gsm8k','math500','mmlu']) {
        const cell=summary.cells.find(c=>c.dataset==='reasoning' && c.model===mid && c.task===task && c.prompt==='BeConcise');
        const observed=cells.find(c=>c.label?.startsWith(modelName(mid)+' · '+taskName(task)+'：'));
        assert(observed,'Missing labelled strategy condition '+mid+'/'+task);
        closeTo(numbers(observed.score)[0],100*cell.scores[0]/cell.n,'Strategy '+mid+'/'+task);
      }
    }
    return {strategy:'BeConcise',models:4,conditions:cells.length};
  });
  await test('field mapping selection preserves both saved records and the 21-field schema',async()=>{
    await section('s3');
    assert(await page.locator('#schema-groups code').count()===21,'Unified schema is incomplete');
    const buttons=page.locator('#field-picker button'); assert(await buttons.count()===4,'Field mapping options missing');
    for(let i=0;i<4;i++) {
      await buttons.nth(i).click();
      const selected=page.locator('#schema-groups code.is-on'); assert(await selected.count()===1,'Schema field selection is ambiguous');
      const canonical=(await selected.innerText()).trim();
      assert((await page.locator('#mapping-grid').innerText()).includes(canonical),'Mapping and unified schema disagree');
      assert(await page.locator('.unified-table tbody tr').count()===9,'Two nine-key example records are incomplete');
    }
    return {schemaFields:21,exampleKeys:9,mappings:4};
  });
  await test('three finding pages expose four general, two task and one feedback plate',async()=>{
    const required={a:['budget','scale','concise','limits'],b:['language','position'],c:['trajectory']};
    for(const [id,plates] of Object.entries(required)) {
      await findings(id);
      assert(await page.locator('.pager-tabs [aria-selected="true"]').count()===1,'Multiple finding tabs selected');
      for(const plate of plates) assert(await page.locator('#plate-'+plate).isVisible(),'Required plate hidden: '+plate);
      const states=await page.locator('.page').evaluateAll(nodes=>nodes.map(n=>({id:n.id,inert:n.inert,hidden:n.getAttribute('aria-hidden')})));
      assert(states.every(s=>s.inert===(s.id!=='page-'+id) && s.hidden===String(s.id!=='page-'+id)),'Inactive finding pages are not isolated');
    }
    await page.locator('#tab-c').press('ArrowLeft');
    assert(await page.locator('#tab-b').getAttribute('aria-selected')==='true','Keyboard cannot change finding pages');
    await page.getByRole('button',{name:'下一页',exact:true}).click();
    assert(await page.locator('#tab-c').getAttribute('aria-selected')==='true','Finding next-page control failed');
    return required;
  });
  await test('budget task changes show all seven measured points with their original scores and Token means',async()=>{
    await findings('a');
    for(const task of ['gsm8k','math500','mmlu']) {
      await page.locator('#budget-task button').filter({hasText:taskName(task)}).click();
      const expected=chart(catalog,'budget-log-'+task), table=await tableFor('plate-budget');
      assert(table.rows.length===7,'Budget table must retain seven measured conditions');
      for(const row of expected) {
        const limit=Number(/\((\d+)\)/.exec(row.prompt)[1]);
        const saved=table.rows.find(r=>numbers(r[0])[0]===limit); assert(saved,'Budget condition missing: '+limit);
        const headings=table.headers;
        const tokenIndex=headings.findIndex(h=>/Token/i.test(h));
        const scoreIndex=headings.findIndex(h=>/评分/.test(h));
        assert(tokenIndex>=0 && scoreIndex>=0,'Budget table lost units');
        closeTo(numbers(saved[tokenIndex])[0],row.mean_tokens,'Budget Token '+task+'/'+limit);
        closeTo(numbers(saved[scoreIndex])[0],row.score_pct,'Budget score '+task+'/'+limit);
      }
    }
    return {tasks:3,observations:21};
  });
  await test('chart explanations open and close without changing the selected data',async()=>{
    const toggle=page.locator('#plate-budget .note-btn'); await toggle.click();
    assert(await toggle.getAttribute('aria-expanded')==='true','Explanation did not open');
    assert((await page.locator('#budget-finding').innerText()).includes('R²'),'Measured-fit explanation absent');
    await toggle.click(); assert(await toggle.getAttribute('aria-expanded')==='false','Explanation did not close'); return true;
  });
  await test('mathematics table keeps every default/Chinese comparison when task and metric change',async()=>{
    await findings('b');
    const data=chart(catalog,'language-cost-quality');
    for(const task of ['math500','gsm8k','mmlu']) {
      await page.locator('#language-task button').filter({hasText:taskName(task)}).click();
      const table=await tableFor('plate-language'); assert(table.rows.length===4,'Mathematics model comparison missing');
      for(const row of table.rows) {
        const expected=data.find(x=>x.model===modelId(row[0]) && x.task===task); assert(expected,'Unexpected mathematics condition');
        const scores=numbers(row[1]);
        closeTo(scores[0],expected.default_score_pct,'Default mathematics score'); closeTo(scores[1],expected.chinese_score_pct,'Chinese mathematics score');
        const tokens=numbers(row[2]); closeTo(tokens[0],expected.default_tokens,'Default mathematics Token'); closeTo(tokens[1],expected.chinese_tokens,'Chinese mathematics Token');
      }
    }
    await page.locator('#language-metric button').filter({hasText:'平均输出 Token'}).click();
    assert((await page.locator('#chart-language svg').getAttribute('aria-label')).includes('Token'),'Metric selection did not update graph semantics');
    return {tasks:3,modelPairs:12};
  });
  await test('document table preserves nine measured positions, both model intervals and paired differences',async()=>{
    const table=await tableFor('plate-position'), profile=chart(catalog,'position-nine-profile'), deltas=chart(catalog,'position-model-advantage');
    assert(table.rows.length===9,'Nine-position evidence is incomplete');
    for(const row of table.rows) {
      const at=numbers(row[0])[0];
      for(let i=1;i<=2;i++) {
        const expected=profile.find(x=>x.x===at && modelId(x.series)===modelId(table.headers[i])); assert(expected,'Missing document condition');
        const actual=numbers(row[i]);
        for(const [j,key] of ['y','low','high'].entries()) closeTo(actual[j],expected[key],'Document '+at+'/'+key);
      }
      const expected=deltas.find(x=>x.x===at), actual=numbers(row[3]);
      for(const [j,key] of ['y','low','high'].entries()) closeTo(actual[j],expected[key],'Paired document '+at+'/'+key);
    }
    return {positions:9,modelObservations:18,pairedIntervals:9};
  });
  await test('both feedback models retain six complete endpoint conditions and original confidence intervals',async()=>{
    await findings('c'); await page.locator('[data-pane="plate-endpoints"]').click();
    for(const model of ev.models) {
      await page.locator('#fb-model button').filter({hasText:modelName(modelId(model))}).click();
      const table=await tableFor('plate-endpoints'); assert(table.rows.length===ev.arms.length,'Endpoint group missing');
      for(const expected of ev.summary.filter(x=>x.model===model)) {
        const row=table.rows.find(x=>x[0]===armName(ev,expected.arm)); assert(row,'Endpoint arm missing');
        const initial=numbers(row[1]), final=numbers(row[2]), interval=numbers(row[3]);
        assert(initial[0]===expected.initial_success && initial[1]===expected.programs,'Shared initial count changed');
        assert(final[0]===expected.final_success && final[1]===expected.programs,'Final count changed');
        closeTo(final[2],100*expected.final_rate,'Final pass percentage');
        closeTo(interval[0],100*expected.final_ci[0],'Final interval lower'); closeTo(interval[1],100*expected.final_ci[1],'Final interval upper');
      }
    }
    return {models:ev.models.length,groups:ev.models.length*ev.arms.length,programsPerGroup:ev.summary[0].programs};
  });
  await test('public and strong feedback trajectories expose all five saved rounds',async()=>{
    const model=ev.models.find(m=>modelId(m)==='qwen');
    await page.locator('#fb-model button').filter({hasText:modelName('qwen')}).click();
    for(const [index,key] of ['strong_curves','public_curves'].entries()) {
      const button=page.locator('#fb-metric button').nth(index),label=await button.innerText();
      assert(index===0 ? /完整|保留/.test(label) : label.includes('公开'),'Feedback metric control lost its meaning');
      await button.click();
      const table=await tableFor('plate-trajectory'); assert(table.rows.length===6 && table.headers.length===6,'Six-by-five trajectory table is incomplete');
      for(const row of table.rows) {
        const arm=ev.arms.find(a=>a.label===row[0]); assert(arm,'Unknown trajectory arm');
        const expected=ev[key].filter(x=>x.model===model && x.arm===arm.id).sort((a,b)=>a.round-b.round);
        assert(expected.length===5,'Published trajectory is incomplete');
        for(let i=0;i<5;i++) closeTo(numbers(row[i+1])[0],100*expected[i].rate,'Trajectory '+label+'/'+arm.id+'/'+i);
      }
    }
    return {metrics:2,arms:6,rounds:5};
  });
  await test('four code views remain available and repair denominators and chain costs match evidence',async()=>{
    const model=ev.models.find(m=>modelId(m)==='qwen');
    await page.locator('#fb-model button').filter({hasText:modelName('qwen')}).click();
    for(const pane of ['plate-endpoints','plate-repair','plate-cost','plate-errors']) {
      await page.locator('[data-pane="'+pane+'"]').click();
      assert(await page.locator('#'+pane).isVisible(),'Code view is hidden: '+pane);
      assert(await page.locator('#'+pane+' svg').count()>0,'Code view failed to render: '+pane);
      const states=await page.locator('.pane').evaluateAll(nodes=>nodes.map(n=>({id:n.id,inert:n.inert})));
      assert(states.every(x=>x.inert===(x.id!==pane)),'Inactive code views remain interactive');
      if(pane==='plate-repair' || pane==='plate-cost') {
        const table=await tableFor(pane); assert(table.rows.length===6,'Code view lost an arm');
        for(const row of table.rows) {
          const arm=ev.arms.find(a=>a.label===row[0]), expected=ev.summary.find(x=>x.model===model && x.arm===arm.id);
          if(pane==='plate-repair') {
            const repair=numbers(row[1]), regression=numbers(row[3]);
            assert(repair[0]===expected.repaired && repair[1]===expected.initial_failures,'Repair denominator changed');
            assert(regression[0]===expected.regressed && regression[1]===expected.initial_correct,'Regression denominator changed');
          } else closeTo(numbers(row[1])[0],expected.mean_chain_total_tokens,'Whole-chain Token cost',.51);
        }
      }
    }
    return {views:4};
  });
  await test('four real repair cases retain saved identity, complete code changes and measured outcomes',async()=>{
    const labels={diagnostic_repair:'诊断后修复',semantic_repair:'反例后修复',regression:'自查后回退',diagnostic_hidden_gap:'公开通过，保留失败'};
    await page.locator('#open-cases').click(); await page.locator('#case-drawer[aria-hidden="false"]').waitFor();
    try {
      assert(await page.locator('#case-tabs button').count()===4,'Full case collection missing');
      for(const example of ev.examples) {
        await page.locator('#case-tabs').getByRole('tab',{name:labels[example.category],exact:true}).click();
        const meta=await page.locator('#case-panel .case-meta').innerText(); assert(meta.includes(example.anonymous_task),'Case identity changed');
        const observed=await page.locator('#case-panel .code-block').nth(1).locator('pre span').allTextContents();
        const expected=(example.diff || example.before_code || '').replace(/\n$/,'').split('\n');
        assert(observed.map(x=>x.trimEnd()).join('\n')===expected.map(x=>x.trimEnd()).join('\n'),'Code changes were omitted or altered: '+example.category);
        const outcomes=page.locator('#case-panel .outcomes > div');
        const statuses=await outcomes.nth(1).locator('.status').allTextContents();
        assert(statuses[0].trim()===(example.before_strong_pass?'通过':'失败') && statuses[1].trim()===(example.after_strong_pass?'通过':'失败'),'Saved strong-test outcome changed');
      }
    } finally {await page.keyboard.press('Escape');}
    assert(await page.locator('#case-drawer').getAttribute('aria-hidden')==='true','Case drawer failed to close');
    return {cases:ev.examples.length};
  });
  await test('reduced-motion preference disables decorative animation and transition durations',async()=>{
    const state=await page.evaluate(()=>({matches:matchMedia('(prefers-reduced-motion: reduce)').matches,
      styles:Array.from(document.querySelectorAll('[data-anim],.viewfinder,.page,.pane')).map(n=>({animation:getComputedStyle(n).animationDuration,transition:getComputedStyle(n).transitionDuration}))}));
    assert(state.matches,'Reduced-motion emulation unavailable');
    const zero=value=>value.split(',').every(x=>parseFloat(x)===0);
    assert(state.styles.every(x=>zero(x.animation)&&zero(x.transition)),'Reduced motion still animates presentation components');
    return {elementsChecked:state.styles.length};
  });
  await test('existing chapter URLs resolve to the approved presentation sections',async()=>{
    await page.goto(new URL('?chapter=cleaning',base).href,{waitUntil:'domcontentloaded'}); await ready();
    assert(new URL(page.url()).hash==='#s3','Old cleaning URL no longer reaches data processing');
    await page.goto(new URL('?chapter=findings&topic=feedback',base).href,{waitUntil:'domcontentloaded'}); await ready();
    assert(new URL(page.url()).hash==='#s4','Old feedback URL no longer reaches findings');
    assert(await page.locator('#tab-c').getAttribute('aria-selected')==='true','Old feedback URL lost code-feedback selection');
    return {cleaning:'#s3',feedback:'#s4/page-c'};
  });

  for(const viewport of [{width:1440,height:900},{width:1920,height:1080},{width:1280,height:720},{width:390,height:844}]) {
    const label=viewport.width+'x'+viewport.height;
    await test(label+' keeps all five sections and three findings pages within the horizontal viewport',async()=>{
      await page.setViewportSize(viewport); await page.evaluate(()=>document.fonts.ready);
      const measures=[];
      for(const id of ['s1','s2','s3','s4','s5']) {
        await section(id);
        const m=await page.evaluate(id=>({section:id,width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
          rect:(()=>{const r=document.getElementById(id).getBoundingClientRect();return {left:r.left,right:r.right,height:r.height};})()}),id);
        assert(m.scrollWidth<=m.width+2,'Document has horizontal overflow in '+id+': '+m.scrollWidth+'/'+m.width);
        assert(m.rect.left>=-2 && m.rect.right<=m.width+2,'Section exceeds horizontal viewport '+id);
        measures.push(m);
      }
      await section('s1'); await screenshot(label+'-home');
      for(const id of ['a','b','c']) {
        await findings(id);
        const invalid=await page.locator('#page-'+id+' svg').evaluateAll(svgs=>svgs.flatMap(svg=>Array.from(svg.querySelectorAll('[d],[x],[y],[cx],[cy],[x1],[x2],[y1],[y2],[width],[height]')).filter(n=>Array.from(n.attributes).some(a=>['d','x','y','cx','cy','x1','x2','y1','y2','width','height'].includes(a.name)&&/NaN|Infinity|undefined/.test(a.value))).map(n=>n.outerHTML.slice(0,180))));
        assert(invalid.length===0,'Finding contains invalid SVG geometry: '+JSON.stringify(invalid.slice(0,3)));
        const w=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));
        assert(w.scrollWidth<=w.width+2,'Findings '+id+' overflows viewport');
        await screenshot(label+'-findings-'+id);
      }
      layouts.push({viewport,sections:measures}); return {sections:5,findingsPages:3};
    });
  }
  await page.setViewportSize({width:1440,height:900}); await findings('a');
  await test('desktop accessibility scan reports critical blockers and records advisory findings',()=>scanAccessibility('desktop findings'));
  await page.setViewportSize({width:390,height:844}); await section('s1');
  await test('mobile accessibility scan reports critical blockers and records advisory findings',()=>scanAccessibility('mobile home'));
  await test('normal-motion startup also renders complete charts',async()=>{
    const motion=await browser.newContext({viewport:{width:1440,height:900},reducedMotion:'no-preference'});
    try {
      const p=await motion.newPage(); observe(p); await p.goto(base,{waitUntil:'domcontentloaded'}); await ready(p);
      assert(await p.locator('#specimen-stage svg').count()===1,'Normal-motion specimen did not render');
      assert(!await p.evaluate(()=>matchMedia('(prefers-reduced-motion: reduce)').matches),'Motion context did not use default preference');
      return true;
    } finally {await motion.close();}
  });
} catch(error) {
  record('suite setup and completion',false,{error:error.message});
} finally {
  record('no JavaScript rendering or console errors',errors.length===0,errors);
  record('all requested local resources load successfully',missing.length===0&&requestFailures.length===0,{httpErrors:missing,requestFailures});
  const failed=results.filter(x=>!x.pass);
  const report={baseURL:base,checks:results.length,passed:results.length-failed.length,failed,errors,missing,requestFailures,accessibility,layouts,screenshots,results};
  await writeFile(resolve(out,'report.json'),JSON.stringify(report,null,2)+'\n');
  await browser.close();
  console.log(JSON.stringify({checks:report.checks,passed:report.passed,failed:failed.length,advisoryAccessibility:accessibility.reduce((n,r)=>n+r.violations.filter(v=>v.impact!=='critical').length,0),report:resolve(out,'report.json')}));
  if(failed.length) process.exitCode=1;
}
