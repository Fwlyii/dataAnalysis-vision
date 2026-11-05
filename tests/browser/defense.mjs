/** Compact defense and complete evidence archive: BASE_URL=http://127.0.0.1:8771/ node tests/browser/defense.mjs. */
import {createRequire} from 'node:module';
import {mkdir,writeFile} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import {resolve} from 'node:path';
import {execFileSync} from 'node:child_process';

const require=createRequire(resolve('tests/package.json'));
const {chromium}=require('playwright-core');
const AxeBuilder=require('@axe-core/playwright').default;
const base=process.env.BASE_URL||'http://127.0.0.1:8771/';
const out=resolve('artifacts/qa/defense');
const screenshotsOut=process.env.DEFENSE_PREVIEW_DIR?resolve(process.env.DEFENSE_PREVIEW_DIR):resolve(out,'screenshots');
await mkdir(out,{recursive:true});await mkdir(screenshotsOut,{recursive:true});await mkdir(resolve(out,'screenshots'),{recursive:true});
const chrome=process.env.CHROMIUM_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const browser=await chromium.launch({headless:true,executablePath:existsSync(chrome)?chrome:undefined,args:['--no-sandbox']});
const context=await browser.newContext({viewport:{width:1440,height:900},reducedMotion:'reduce',acceptDownloads:true});
const page=await context.newPage();
const checks=[],errors=[],missing=[],screenshots=[],accessibility=[];
const topics=['budget','scale','concise','limits','language','position','feedback'];
const chapters=['question','collection','cleaning','findings','conclusion'];
page.on('pageerror',error=>errors.push(error.message));
page.on('response',response=>{if(response.status()>=400&&!response.url().endsWith('favicon.ico'))missing.push({url:response.url(),status:response.status()});});
function assert(value,message){if(!value)throw Error(message);}
function sameNumber(actual,expected,message){assert(actual!==null&&actual!==undefined&&actual!==''&&Number.isFinite(Number(actual))&&Math.abs(Number(actual)-expected)<1e-10,message);}
const signed2=value=>`${value>0?'+':''}${value.toFixed(2)}`;
const interval2=values=>`[${values.map(signed2).join(',')}]`;
function contrast(evidence,model,arm,baseline){
  const direct=evidence.contrasts.find(row=>row.model===model&&row.arm===arm&&row.baseline===baseline);if(direct)return direct;
  const reverse=evidence.contrasts.find(row=>row.model===model&&row.arm===baseline&&row.baseline===arm);assert(reverse,'Missing paired contrast '+model+'/'+arm+'/'+baseline);
  return {...reverse,delta_pp:-reverse.delta_pp,ci_low_pp:-reverse.ci_high_pp,ci_high_pp:-reverse.ci_low_pp};
}
function record(name,pass,detail){checks.push({name,pass,detail});if(!pass)console.error('FAIL',name,JSON.stringify(detail));}
async function test(name,action){try{record(name,true,await action());}catch(error){record(name,false,{error:error.message});}}
async function ready(){await page.waitForFunction(()=>document.body.dataset.view&&document.querySelector('#main-content h1')&&!document.querySelector('.initial-loading'));}
async function open(query=''){await page.goto(new URL(query,base).href,{waitUntil:'domcontentloaded'});await ready();}
async function imagesReady(root='#main-content'){
  const images=page.locator(root+' img');
  for(let i=0;i<await images.count();i++){await images.nth(i).scrollIntoViewIfNeeded();await images.nth(i).evaluate(image=>image.decode());}
}
async function shot(name,file,{fullPage=false,target=null,artifact=false}={}){
  if(target){await imagesReady(target);await page.locator(target).evaluate(element=>window.scrollTo({top:element.getBoundingClientRect().top+scrollY-(document.querySelector('.site-header')?.getBoundingClientRect().height||0)-28,behavior:'instant'}));}
  else {await imagesReady();await page.evaluate(()=>window.scrollTo(0,0));}
  await page.evaluate(()=>document.fonts.ready);const path=resolve(artifact?resolve(out,'screenshots'):screenshotsOut,file);await page.screenshot({path,fullPage});screenshots.push({name,path});
}
async function axe(name){const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();const findings=result.violations.map(item=>({id:item.id,impact:item.impact,nodes:item.nodes.map(node=>({target:node.target,summary:node.failureSummary}))}));accessibility.push({name,violations:findings});record(name+' accessibility',findings.length===0,findings);}
async function assertChrome(){
  assert(await page.locator('.research-rail,aside[aria-label="当前研究路径"],.page-footer,#page-progress,.scene-next,.scene-previous').count()===0,'Old navigation remains in DOM');
  assert(await page.locator('#chapter-nav a').count()===5,'Chapter nav count differs');
  assert(await page.locator('.site-header a').count()===6,'Header has unrelated links');
  assert(await page.locator('#main-content a,#main-content button,#main-content select,#main-content details').count()===0,'Body exposes unnecessary actions or hidden disclosure');
}
try{
  await open();
  const catalog=await page.evaluate(async()=>await(await fetch('data/research-charts.json')).json());
  const supplement=await page.evaluate(async()=>{const path=document.querySelector('meta[name="code-feedback-extension"]')?.content;return path?await(await fetch(path)).json():null;});
  const content=await page.evaluate(async()=>await import('./src/research-content.js').then(module=>module.researchContent));
  await test('root opens exactly five orb links without chapter chrome or footer',async()=>{
    assert(await page.locator('.rh-orb:visible').count()===5,'Home does not expose exactly5 orbs');assert(!await page.locator('.site-header').isVisible(),'Chapter chrome appears on home');assert(await page.locator('.page-footer,#page-progress').count()===0,'Footer still exists');
    const visibleLinks=await page.locator('a:visible').evaluateAll(links=>links.filter(link=>{const b=link.getBoundingClientRect();return b.bottom>0&&b.right>0&&b.top<innerHeight&&b.left<innerWidth;}).map(link=>link.textContent.trim()));assert(visibleLinks.length===5,'Home exposes extra links');return visibleLinks;
  });
  await test('five orbs enter five chapters and brand restores home',async()=>{
    for(const chapter of chapters){await page.locator('[data-home-chapter="'+chapter+'"]').click();await page.waitForFunction(chapter=>document.body.dataset.chapter===chapter,chapter);await assertChrome();await page.locator('[data-home-link]').click();await page.locator('.rh-orb').first().waitFor();}return chapters;
  });
  await test('home and cleaning survive Back and refresh',async()=>{
    await page.locator('[data-home-chapter="cleaning"]').click();await page.locator('.rc-cleaning-figure').waitFor();const before=page.url();await page.reload();await page.locator('.rc-cleaning-figure').waitFor();assert(page.url()===before,'Refresh lost cleaning route');await page.goBack();await page.locator('.research-home').waitFor();await page.reload();await page.locator('.research-home').waitFor();return true;
  });
  await open('?chapter=question');
  await test('question directly shows three task examples without controls',async()=>{assert(await page.locator('.rc-task-example:visible').count()===3,'Tasks hidden behind tabs');await assertChrome();return await page.locator('.rc-task-example h3').allTextContents();});
  await open('?chapter=collection');
  await test('collection directly shows four dimensions,31 strategies and five experiments',async()=>{
    assert(await page.locator('.rc-dimension').count()===4,'Dimension count mismatch');assert(await page.locator('.rc-prompt-item:visible').count()===31,'Catalogue is not fully visible');assert(await page.locator('.rc-experiment-table tbody tr').count()===5,'Experiment count mismatch');await assertChrome();assert(content.totalRecords===248586,'Record total changed');return {dimensions:4,prompts:31,records:content.totalRecords};
  });
  await open('?chapter=cleaning');
  await test('cleaning is a static A/B/C/D figure without buttons, selects, links or disclosure',async()=>{
    await assertChrome();for(const selector of ['.rc-panel-a','.rc-panel-b','.rc-panel-c','.rc-storage-summary'])assert(await page.locator(selector).isVisible(),'Missing panel '+selector);assert(await page.locator('[data-rc-source]').count()===2,'Sources missing');assert(await page.locator('[data-rc-mapping]').count()===4,'Four mappings missing');return {sources:2,mappings:4,panels:4};
  });
  await test('all four source-name mappings are simultaneously visible and marked red',async()=>{
    for(const source of ['reasoning','document_qa']){const marks=page.locator('[data-rc-source="'+source+'"] .rc-field-token');assert(await marks.count()===4,'Four red source fields missing for '+source);const colors=await marks.evaluateAll(nodes=>nodes.map(node=>getComputedStyle(node).color));assert(colors.every(color=>{const [r,g,b]=color.match(/[0-9.]+/g).map(Number);return r>g*1.5&&r>b*1.2;}),'Source fields are not visually red: '+source);}
    for(const field of content.cleaning.fields){const mapping=page.locator('[data-rc-mapping="'+field.id+'"]');assert(await mapping.isVisible(),'Mapping is hidden: '+field.id);const text=await mapping.innerText();assert(text.includes(field.id),'Canonical field missing '+field.id);assert(text.includes(field.reasoningKey)&&text.includes(field.documentKey.split('.').at(-1)),'Source names missing '+field.id);const sourceText=await page.locator('[data-rc-source="document_qa"]').textContent();assert(sourceText.includes(field.documentKey),'Full API path missing '+field.id);}
    return content.cleaning.fields.map(field=>field.id);
  });
  await test('both unified records simultaneously match all nine saved keys',async()=>{
    const keys=['model_id','benchmark','input_tokens','output_tokens','finish_reason','metric_name','metric_value','document_count','evidence_position'];assert(await page.locator('.rc-combined-records [data-rc-record]').count()===2,'Two record columns missing');assert(await page.locator('[data-rc-saved-field]').count()===9,'Saved key count differs');
    for(const key of keys)for(const source of ['reasoning','document_qa']){const cell=page.locator('[data-rc-saved-field="'+key+'"] [data-source="'+source+'"]');assert(await cell.isVisible(),'Saved value hidden '+source+'/'+key);assert((await cell.innerText()).trim()===String(content.cleaning.records[source][key]),'Saved value differs '+source+'/'+key);}
    const storage=await page.locator('.rc-storage-summary').innerText();assert(storage.includes('all_records.csv.gz')&&storage.includes('21'),'Saved file/format not disclosed');return {keys:9,records:2};
  });
  await shot('static cleaning figure','滚动版_数据处理Figure.png',{fullPage:true});
  await open('?chapter=findings');
  await test('findings is one continuous article with four general and three task sections',async()=>{
    assert(await page.locator('.findings-long-page').count()===1,'Continuous findings article missing');const parts=page.locator('.findings-part');assert(await parts.count()===2,'General/specific grouping differs');assert(await parts.nth(0).locator('[data-topic]').count()===4&&await parts.nth(1).locator('[data-topic]').count()===3,'4+3 sections differ');assert(JSON.stringify(await page.locator('[data-topic]').evaluateAll(nodes=>nodes.map(node=>node.dataset.topic)))===JSON.stringify(topics),'Theme order changed');assert(await page.locator('.section-intro h1').innerText()==='核心发现','Compact heading differs');await assertChrome();return topics;
  });
  await test('compact findings fits four desktop screens using native evidence graphics',async()=>{
    await page.evaluate(()=>document.fonts.ready);const before=page.url(),height=await page.evaluate(()=>document.documentElement.scrollHeight);assert(height<=4000,'Compact findings exceeds four desktop screens: '+height);assert(await page.locator('.findings-long-page img[src*="assets/research/"]').count()===0,'Full atlas is still inserted into the defense page');assert(await page.locator('.findings-long-page .ocean-summary-plot').count()===3,'Three native general plots missing');assert(await page.locator('.ocean-scale-table tbody tr').count()===4,'Four-model comparison table missing');assert(page.url()===before,'Reading changed route');await assertChrome();return {viewport:{width:1440,height:900},height,maximum:4000,generalNativePlots:3,modelRows:4};
  });
  await test('compact mathematics and document graphics retain their real evidence and conditions',async()=>{
    const math=page.locator('.compact-language-plot'),position=page.locator('.compact-position-plot');assert(await math.count()===1&&await position.count()===1,'Task SVGs missing');
    for(const [plot,id] of [[math,'language-math-score'],[position,'position-nine-profile']]){assert(await plot.getAttribute('data-source-chart')===id,'Task source chart differs: '+id);assert(await plot.getAttribute('role')==='img','Task chart lacks image role');assert((await plot.locator('title').textContent()).trim()&&(await plot.locator('desc').textContent()).trim(),'Task chart lacks title/description');}
    const mathRows=catalog.charts.find(row=>row.id==='language-math-score').data;assert(await math.locator('.compact-language-bar').count()===mathRows.length,'Mathematics bar count differs');for(const row of mathRows){const bar=math.locator(`.compact-language-bar[data-model="${row.category}"][data-series="${row.series}"]`);assert(await bar.count()===1,'Mathematics comparison missing');sameNumber(await bar.getAttribute('data-score'),row.value,'Mathematics score changed');}
    const tokenRows=catalog.charts.find(row=>row.id==='language-math-tokens').data;assert(await page.locator('[data-token-model]').count()===4,'Four Token comparisons missing');for(const model of [...new Set(tokenRows.map(row=>row.category))]){const cell=page.locator(`[data-token-model="${model}"]`);for(const [attribute,series] of [['data-token-before','默认模板'],['data-token-after','中文模板']])sameNumber(await cell.getAttribute(attribute),tokenRows.find(row=>row.category===model&&row.series===series).value,'Mathematics Token comparison changed');}
    const positionRows=catalog.charts.find(row=>row.id==='position-nine-profile').data;assert(await position.locator('.compact-position-point').count()===positionRows.length,'Nine-position observations missing');for(const row of positionRows){const point=position.locator(`.compact-position-point[data-series="${row.series}"][data-position="${row.x}"]`);assert(await point.count()===1,'Position point missing');for(const [attribute,value] of [['data-score',row.y],['data-low',row.low],['data-high',row.high]])sameNumber(await point.getAttribute(attribute),value,'Position observation/interval changed');}
    const deltas=catalog.charts.find(row=>row.id==='position-model-advantage').data;for(const at of [1,20]){const row=deltas.find(row=>row.x===at),block=page.locator(`[data-position-contrast="${at}"]`);for(const [attribute,value] of [['data-delta',row.y],['data-low',row.low],['data-high',row.high]])sameNumber(await block.getAttribute(attribute),value,'Position paired contrast changed');}
    const mathText=await page.locator('#finding-language').textContent(),positionText=await page.locator('#finding-position').textContent();assert(mathText.includes('MATH500'),'Mathematics condition lost');assert(positionText.includes('200')&&positionText.includes('20')&&positionText.includes('九'),'Document sample/position conditions lost');return {mathComparisons:8,tokenComparisons:4,positionObservations:18,pairedPositionContrasts:2};
  });
  if(supplement){
    await test('compact feedback renders both models and all six measured endpoint conditions',async()=>{
      const e=supplement.evidence;assert(e.synthetic===false&&e.status==='complete'&&e.coverage.complete===true&&e.strong_trajectory_complete===true,'Supplement is not fully measured');
      assert(e.task_clusters===e.planned_tasks&&e.strong_trajectory_task_clusters===e.planned_tasks,'Independent task coverage differs');
      const svg=page.locator('.feedback-compact svg[data-fex-figure="strong-endpoints"]');assert(await svg.count()===1,'Native endpoint chart missing');assert(await svg.getAttribute('data-source-svg')==='assets/research-extension/01-strong-endpoints.svg','Endpoint source lost');assert(await svg.locator('g[data-model][data-arm]').count()===e.models.length*e.arms.length,'Endpoint matrix incomplete');const axisMin=Number(await svg.getAttribute('data-axis-min')),axisMax=Number(await svg.getAttribute('data-axis-max'));assert(axisMin<axisMax,'Endpoint axis domain missing');if(axisMin>0||axisMax<100)assert((await svg.locator('desc').textContent()).includes('截取'),'Truncated endpoint axis is not disclosed');
      for(const row of e.summary){const mark=svg.locator(`g[data-model="${row.model}"][data-arm="${row.arm}"]`);assert(await mark.count()===1,'Endpoint missing '+row.model+'/'+row.arm);for(const [attribute,value] of [['data-initial-rate',row.initial_rate],['data-final-rate',row.final_rate],['data-final-ci-low',row.final_ci[0]],['data-final-ci-high',row.final_ci[1]]])sameNumber(await mark.getAttribute(attribute),value,'Endpoint value changed '+attribute);const visible=await mark.textContent();assert(visible.includes(row.final_success+'/'+row.programs)&&visible.includes((row.final_rate*100).toFixed(1)+'%'),'Endpoint counts/rate are absent');}
      assert(e.summary.every(row=>[row.initial_rate,row.final_rate,...row.final_ci].every(value=>value*100>=axisMin-1e-10&&value*100<=axisMax+1e-10)),'Endpoint/interval outside declared axis');
      await assertChrome();return {tasks:e.task_clusters,repeats:e.repeats_per_task,responses:e.saved_physical_responses,modelArms:e.summary.length};
    });
    await test('compact feedback quotes the paired model differences and additional Token cost exactly',async()=>{
      const e=supplement.evidence;assert(await page.locator('.fex-compact-comparison').count()===e.models.length,'Model contrast blocks missing');
      for(const model of e.models){const block=page.locator(`.fex-compact-comparison[data-model="${model}"]`),text=(await block.innerText()).replace(/\s/g,'');const single=contrast(e,model,'counterexample','self_review'),extra=contrast(e,model,'multi_counterexample','counterexample');assert(text.includes(signed2(single.delta_pp))&&text.includes(interval2([single.ci_low_pp,single.ci_high_pp])),'Single/self paired contrast changed');assert(text.includes(interval2([extra.ci_low_pp,extra.ci_high_pp])),'Multiple/single interval changed');const one=e.summary.find(row=>row.model===model&&row.arm==='counterexample'),multi=e.summary.find(row=>row.model===model&&row.arm==='multi_counterexample'),cost=100*(multi.mean_chain_total_tokens/one.mean_chain_total_tokens-1);assert(text.includes(cost.toFixed(2)+'%'),'Additional Token cost changed');if(extra.ci_low_pp<=0&&extra.ci_high_pp>=0)assert(text.includes('区间含0'),'Uncertain extra benefit hidden');}
      return {models:e.models.length,comparisonsPerModel:2,additionalCost:'measured whole-chain Token'};
    });
    await test('compact repair and regression cases preserve actual feedback excerpts and complete diffs',async()=>{
      const e=supplement.evidence,cases=page.locator('.feedback-compact .fex-compact-case');assert(await cases.count()===2,'Compact defense must show repair and regression');
      for(const category of ['semantic_repair','regression']){const node=page.locator(`.feedback-compact .fex-compact-case[data-case-category="${category}"]`);assert(await node.count()===1,'Case category missing '+category);const task=await node.getAttribute('data-case-task'),replicate=Number(await node.getAttribute('data-replicate')),before=Number(await node.getAttribute('data-before-round')),after=Number(await node.getAttribute('data-after-round'));const example=e.examples.find(row=>row.category===category&&row.anonymous_task===task&&row.replicate===replicate&&row.before_round===before&&row.after_round===after);assert(example,'Case is absent from published saved evidence');assert(await node.locator('[data-case-code="full-diff"] code').textContent()===example.diff,'Actual code diff changed');
        const excerpt=node.locator('[data-feedback-excerpt]'),kind=await excerpt.getAttribute('data-feedback-excerpt'),displayed=await excerpt.locator('code').textContent();
        if(category==='semantic_repair'){assert(kind==='failure-projection','Repair feedback is not an explicit source excerpt');const prefix='Diagnostic test feedback:\n';assert(example.actual_feedback.startsWith(prefix),'Original diagnostic feedback missing');const report=JSON.parse(example.actual_feedback.slice(prefix.length).split('\n\n')[0]),first=report.failures[0];assert(JSON.stringify(JSON.parse(displayed))===JSON.stringify({diagnostic_status:report.diagnostic_status,failures:[{input:first.input,expected:first.expected,actual:first.actual}]}),'Failure projection changed source fields');assert(example.before_strong_pass===false&&example.after_strong_pass===true,'Repair is not an observed adjacent strong transition');}
        else{assert(kind==='literal-prefix','Self-review excerpt must quote the actual instruction');const end=example.actual_feedback.indexOf(' Return the complete implementation'),expected=end>=0?example.actual_feedback.slice(0,end):example.actual_feedback;assert(displayed===expected&&example.actual_feedback.startsWith(displayed),'Self-review instruction excerpt changed');assert(example.before_strong_pass===true&&example.after_strong_pass===false,'Regression is not an observed adjacent strong transition');}
      }
      return {cases:2,categories:['semantic_repair','regression'],feedback:'source field projection or literal prefix',code:'full saved diff'};
    });
  }
  await test('PageDown scrolls without changing chapter or hiding findings',async()=>{
    await page.evaluate(()=>window.scrollTo(0,0));await page.locator('#main-content h1').click();const before=page.url();await page.keyboard.press('PageDown');await page.waitForFunction(()=>scrollY>200);assert(page.url()===before,'Native scrolling changed route');assert(await page.locator('[data-topic]').count()===7,'Scroll replaced article content');return true;
  });
  await test('left and right arrow keys never navigate chapters',async()=>{
    for(const chapter of ['question','cleaning','findings','conclusion']){await open('?chapter='+chapter);await page.locator('#main-content h1').click();const before=page.url();await page.keyboard.press('ArrowRight');await page.keyboard.press('ArrowLeft');await page.waitForTimeout(60);assert(page.url()===before,'Arrow key changed '+chapter+' route');}return true;
  });
  await test('legacy topic URLs preserve the complete seven-theme compact presentation',async()=>{
    for(const topic of ['budget','position','feedback']){await open('?chapter=findings&topic='+topic);assert(await page.locator('[data-topic]').count()===7,'Legacy URL cut the presentation: '+topic);assert(await page.locator('.section-intro h1').innerText()==='核心发现','Legacy topic replaced chapter heading');await assertChrome();}return true;
  });
  await open('?chapter=findings');await shot('compact findings first screen','滚动版_发现结构.png');await shot('complete compact findings','紧凑版_核心发现.png',{fullPage:true});await shot('budget graph in compact presentation','滚动版_核心发现.png',{target:'#finding-budget'});assert(page.url().endsWith('?chapter=findings'),'Figure screenshot altered route');
  if(supplement){await shot('compact measured feedback endpoints','补充版_代码反馈结构.png',{target:'.fex-compact-result-section'});await shot('compact paired model comparisons','补充版_代码反馈结论.png',{target:'.fex-compact-contrasts'});await shot('real repair and regression excerpts','补充版_真实修复案例.png',{target:'.fex-compact-case-section'});}
  for(const width of [1440,1000,768,390]){
    await page.setViewportSize({width,height:width===390?844:900});
    for(const chapter of ['home',...chapters]){
      await open(chapter==='home'?'':'?chapter='+chapter);
      await test(width+' no whole-page horizontal overflow '+chapter,async()=>{const dimensions=await page.evaluate(()=>({viewport:innerWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth}));assert(dimensions.scroll<=dimensions.viewport+1&&dimensions.body<=dimensions.viewport+1,JSON.stringify(dimensions));return dimensions;});
      await axe(width+' '+chapter);
    }
  }
  await open('?chapter=cleaning');await shot('static cleaning phone','静态清洗Figure_手机.png',{fullPage:true,artifact:true});
  await open('?chapter=findings');await shot('compact presentation phone','长页核心发现_手机.png',{fullPage:true,artifact:true});
  await page.setViewportSize({width:1440,height:900});await open('?chapter=atlas');
  await test('separate archive retains37 editable plots and13 interactive chart types',async()=>{
    assert(await page.locator('.atlas-grid [data-chart-id]').count()===37,'Archive missing figures');await page.locator('[data-x-field="chart"]').waitFor({timeout:30000});assert(await page.locator('[data-x-field="chart"] option').count()===13,'Legacy13 chart types missing');const archive=await page.request.get(new URL('assets/research-svg.zip',base).href);assert(archive.ok(),'SVG archive missing');return {figures:37,interactiveTypes:13};
  });
  await test('the complete archive preserves and decodes all original37 plus seven measured SVGs',async()=>{
    const plots=page.locator('.atlas-grid [data-chart-id]'),actual=await plots.evaluateAll(nodes=>nodes.map(node=>node.dataset.chartId));assert(actual.length===37&&new Set(actual).size===37,'Not37 unique original plots');assert(catalog.charts.every(chart=>actual.includes(chart.id)),'Original catalogue figure absent');const expected=37+(supplement?7:0);assert(await page.locator('.atlas-grid img,.atlas-feedback-host .fex-figure img').count()===expected,'Complete archive image count differs');await imagesReady('.atlas-grid');if(supplement)await imagesReady('.atlas-feedback-host');const loaded=await page.locator('.atlas-grid img,.atlas-feedback-host .fex-figure img').evaluateAll(images=>images.every(image=>image.complete&&image.naturalWidth>0));assert(loaded,'Archive SVG did not decode');return {original:37,supplement:supplement?7:0,total:expected};
  });
  if(supplement){
    await test('archive feedback preserves all six conditions and separate historical recheck',async()=>{
      const e=supplement.evidence,host=page.locator('.atlas-feedback-host');assert(await host.locator('.feedback-extension').count()===1&&await host.locator('.fex-arms li').count()===6,'Complete six-arm evidence missing from archive');assert(await host.locator('.fex-figure img').count()===7,'Six new and one historical plots missing');assert(await host.locator('.fex-results-table tbody tr').count()===e.models.length*e.arms.length,'Archive result matrix differs');assert(supplement.legacyEvidence.checks.complete===true&&supplement.legacyEvidence.summary.length===8,'Historical recheck lost');return {modelRows:e.summary.length,newFigures:supplement.figures.length,legacyFigures:supplement.legacyEvidence.figures.length};
    });
    await test('archive cases retain every saved before and after program and exact feedback',async()=>{
      const cases=page.locator('.atlas-feedback-host .fex-case');assert(await cases.count()===supplement.evidence.examples.length,'Archive case count differs');for(const [index,example] of supplement.evidence.examples.entries()){const blocks=cases.nth(index).locator('.fex-code-block code');assert(await blocks.nth(0).textContent()===example.before_code,'Archive before code changed');assert(await blocks.nth(2).textContent()===example.after_code,'Archive after code changed');if(typeof example.actual_feedback==='string')assert(await blocks.nth(1).textContent()===example.actual_feedback,'Archive feedback changed');if(example.diff)assert(await blocks.nth(3).textContent()===example.diff,'Archive full diff changed');assert(typeof example.before_strong_pass==='boolean'&&typeof example.after_strong_pass==='boolean','Case intermediate strong result missing');}assert(supplement.evidence.examples.every(row=>!Object.hasOwn(row,'task_id')&&!Object.hasOwn(row,'record_ids')&&typeof row.anonymous_task==='string'),'Raw identifier field exposed');return {cases:await cases.count(),unobserved:supplement.evidence.missing_example_categories||[]};
    });
    await test('supplementary editable SVG pack remains independently available',async()=>{const response=await page.request.get(new URL('assets/research-feedback-svg.zip',base).href);assert(response.ok(),'Supplementary SVG pack missing');return {new:supplement.figures.length,legacy:supplement.legacyEvidence.figures.length};});
    await shot('complete evidence archive receipt','图册_完整44图收据.png',{target:'.catalog-tools'});
  }
  await test('archive retains all four independent-code interactive views',async()=>{
    await page.locator('[data-x-panel="code"]').click();await page.locator('[data-code-view]').first().waitFor({timeout:30000});const views=await page.locator('[data-code-view]').evaluateAll(nodes=>nodes.map(node=>node.dataset.codeView));assert(JSON.stringify(views)===JSON.stringify(['sampling','prompts','errors','tokens']),'Four code views differ');for(const view of views){await page.locator(`[data-code-view="${view}"]`).click();assert(await page.locator(`[data-code-view="${view}"]`).getAttribute('aria-current')==='page','Code view did not activate '+view);assert(await page.locator('#code-publication svg').count()>0,'Code view figure missing '+view);}return views;
  });
  await test('scientific protection remains intact',async()=>execFileSync('python3',['scripts/system/check_reconstruction.py'],{encoding:'utf8'}).trim());
}catch(error){record('unexpected runner failure',false,{error:error.stack});}
finally{
  await browser.close();record('no uncaught browser errors',errors.length===0,errors);record('no missing resources',missing.length===0,missing);
  const report={baseURL:base,checks:checks.length,passed:checks.filter(check=>check.pass).length,failed:checks.filter(check=>!check.pass),errors,missing,accessibility,screenshots,results:checks};await writeFile(resolve(out,'report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({checks:report.checks,passed:report.passed,failed:report.failed.length,report:resolve(out,'report.json')}));if(report.failed.length)process.exitCode=1;
}
