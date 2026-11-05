/** Actual-browser checks for the rebuilt Chinese research shell.
 * Run from repository root: BASE_URL=http://127.0.0.1:8771/ node tests/browser/reconstruction.mjs
 * Reuses existing locked browser dependencies; never rewrites scientific fixtures.
 */
import { createRequire } from 'node:module';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { execFileSync } from 'node:child_process';

const require=createRequire(resolve('tests/package.json'));
const {chromium}=require('playwright-core');
const AxeBuilder=require('@axe-core/playwright').default;
const base=process.env.BASE_URL||'http://127.0.0.1:8771/';
const executablePath=process.env.CHROMIUM_PATH||('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome');
const out=resolve('artifacts/qa/reconstruction');
const outputs=process.env.RECON_PREVIEW_DIR?resolve(process.env.RECON_PREVIEW_DIR):resolve(out,'screenshots');
await mkdir(out,{recursive:true});await mkdir(out+'/downloads',{recursive:true});await mkdir(outputs,{recursive:true});
const results=[],errors=[],failedResources=[],screenshots=[],accessibility=[],downloadRetries=[];
const browser=await chromium.launch({headless:true,executablePath:existsSync(executablePath)?executablePath:undefined,args:['--no-sandbox']});
const context=await browser.newContext({viewport:{width:1440,height:1100},acceptDownloads:true,reducedMotion:'reduce'});
const page=await context.newPage();
page.on('pageerror',e=>errors.push(e.message));
page.on('response',r=>{if(r.status()>=400&&!r.url().endsWith('favicon.ico'))failedResources.push({url:r.url(),status:r.status()});});
const check=(name,passed,detail)=>{results.push({name,passed,detail});if(!passed)console.error('FAIL',name,JSON.stringify(detail));};
async function test(name,fn){try{const detail=await fn();check(name,true,detail);}catch(e){check(name,false,{error:e.message});}}
async function open(query='?chapter=question'){
  for(let attempt=0;attempt<3;attempt++){
    try{
      await page.goto(new URL(query,base).href,{waitUntil:'domcontentloaded'});
      await page.locator('#main-content h1').waitFor();
      await page.waitForFunction(()=>!document.querySelector('.initial-loading')&&document.querySelectorAll('#chapter-nav a').length===5);
      return;
    }catch(e){if(attempt===2)throw e;await page.waitForTimeout(300);}
  }
}
async function figureReady(id){
  await page.waitForFunction(id=>{
    const fig=document.querySelector('.main-figure');return fig?.dataset.chartId===id&&fig.querySelector('#primary-figure svg');
  },id);
}
function parseCSV(text){
  text=text.replace(/^\uFEFF/,'');const rows=[];let row=[],value='',quoted=false;
  for(let i=0;i<text.length;i++){
    const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){value+='"';i++;}else quoted=!quoted;}
    else if(c===','&&!quoted){row.push(value);value='';}
    else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(value);if(row.some(v=>v!==''))rows.push(row);row=[];value='';}
    else value+=c;
  }
  if(value||row.length){row.push(value);rows.push(row);}return rows;
}
async function saveDownload(locator,name){
  for(let attempt=0;attempt<2;attempt++){
    try{const pending=page.waitForEvent('download',{timeout:6000});pending.catch(()=>{});await locator.click();const download=await pending;const path=resolve(out,'downloads',name);await download.saveAs(path);await page.waitForTimeout(100);return {download,path,text:await readFile(path,'utf8')};}
    catch(e){if(attempt===1)throw e;downloadRetries.push(name);await page.waitForTimeout(250);}
  }
}
async function axe(name){const a=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();accessibility.push({name,violations:a.violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))});check(name+' axe',a.violations.length===0,accessibility.at(-1));}
async function screenshot(name,filename){await page.waitForFunction(()=>!document.querySelector('#research-toast.visible'));await page.evaluate(()=>window.scrollTo(0,0));await page.waitForTimeout(100);const path=resolve(outputs,filename);await page.screenshot({path});screenshots.push({name,path});}

try{
  await open();
  const catalog=await page.evaluate(async()=>{const r=await fetch('data/research-charts.json');return r.json();});
  const content=await page.evaluate(async()=>{const m=await import('./src/research-content.js');return m.researchContent;});
  check('catalogue has four general and three task-specific themes',catalog.charts.length>=28&&new Set(catalog.charts.map(c=>c.topic)).size===7,{charts:catalog.charts.length});
  await test('downloadable SVG archive contains every catalogue figure',async()=>{
    const response=await page.request.get(new URL('assets/research-svg.zip',base).href);if(!response.ok())throw Error('SVG archive HTTP '+response.status());
    const file=resolve(out,'downloads','research-svg.zip');await writeFile(file,await response.body());
    const names=JSON.parse(execFileSync('python3',['-c','import zipfile,json,sys; print(json.dumps(zipfile.ZipFile(sys.argv[1]).namelist()))',file],{encoding:'utf8'}));
    for(const c of catalog.charts)if(!names.some(n=>n.endsWith('/'+c.id+'.svg')||n===c.id+'.svg'))throw Error('Archive misses '+c.id);
    return {entries:names.length,svgFigures:catalog.charts.length};
  });
  await test('five Chinese chapter entry points',async()=>{
    const chapters=[['question','rc-question'],['collection','rc-collection'],['cleaning','rc-cleaning'],['findings','topic-overview'],['conclusion','rc-conclusion']];
    for(const [chapter,css]of chapters){await open('?chapter='+chapter);await page.locator('.'+css).waitFor();if(!await page.locator('#main-content h1').innerText())throw Error(chapter+' missing title');}
    return chapters.map(([id])=>id);
  });
  await open('?chapter=question');
  await test('three tasks reveal real, distinct examples',async()=>{
    const titles=[];for(const task of content.question.tasks){await page.locator('[data-rc-task="'+task.id+'"]').click();await page.locator('[data-rc-task="'+task.id+'"][aria-pressed="true"]').waitFor();titles.push(await page.locator('.rc-task-example h3').innerText());}
    if(new Set(titles).size!==3)throw Error('Task examples were not distinct');return titles;
  });
  await axe('question desktop');
  await open('?chapter=collection');
  await test('31 strategies and all four dimension filters',async()=>{
    await page.locator('.rc-prompt-catalog > summary').click();
    if(await page.locator('.rc-prompt-item').count()!==31)throw Error('Complete catalogue is not31');
    const counts={};for(const dim of content.dimensions){await page.locator('.rc-prompt-filters [data-rc-dimension="'+dim.id+'"]').click();const actual=await page.locator('.rc-prompt-item').count(),expected=content.prompts.filter(p=>p.dimensions.includes(dim.id)).length;if(actual!==expected)throw Error(dim.id+': '+actual+' != '+expected);counts[dim.id]=actual;}
    await page.locator('.rc-prompt-filters [data-rc-dimension="all"]').click();if(await page.locator('.rc-prompt-item').count()!==31)throw Error('All reset failed');return counts;
  });
  await test('experiment record counts sum to248586',async()=>{const total=content.experiments.reduce((a,r)=>a+r.records,0);if(total!==248586)throw Error('Unexpected total '+total);return total;});
  await axe('collection desktop');
  await open('?chapter=cleaning');
  await test('four fields map red source names into saved unified rows',async()=>{
    const mapped=[];for(const field of content.cleaning.fields){await page.locator('.rc-mapping-toolbar [data-rc-field="'+field.id+'"]').click();await page.locator('[data-rc-cleaning][data-field="'+field.id+'"]').waitFor();if((await page.locator('.rc-source-fragment .rc-field-token.is-active').count())!==2)throw Error(field.id+' lacks two active source mappings');if(await page.locator('.rc-saved-table tr.is-active').count()!==1)throw Error(field.id+' no saved field highlight');const color=await page.locator('.rc-field-token.is-active').first().evaluate(e=>getComputedStyle(e).color);mapped.push({field:field.id,color});}return mapped;
  });
  await test('saved CSV and JSON views retain selected record and field',async()=>{
    await page.locator('[data-rc-saved-source]').selectOption('document_qa');await page.locator('[data-rc-cleaning][data-source="document_qa"]').waitFor();
    await page.locator('[data-rc-saved-view="json"]').click();await page.locator('.rc-saved-json').waitFor();const text=await page.locator('.rc-saved-json').innerText();if(!text.includes('output_tokens'))throw Error('JSON view misses canonical field');
    await page.locator('[data-rc-saved-view="csv"]').click();await page.locator('.rc-saved-table').waitFor();return {source:await page.locator('[data-rc-cleaning]').getAttribute('data-source')};
  });
  await test('cleaning CSV is the two actual saved example records',async()=>{
    const d=await saveDownload(page.locator('[data-rc-download="cleaning"]'),'cleaning.csv'),rows=parseCSV(d.text);if(rows.length!==3)throw Error('Expected header plus2 rows, got '+rows.length);const h=rows[0];for(const [i,row]of Object.values(content.cleaning.records).entries()){for(const key of ['record_id','output_tokens','input_tokens']){const ix=h.indexOf(key);if(ix>=0&&String(row[key]??'')!==rows[i+1][ix])throw Error('Saved value mismatch '+key);}}return {rows:rows.length-1,columns:h.length};
  });
  await screenshot('cleaning','预览_数据处理.png');
  await axe('cleaning desktop');
  const topics=['budget','scale','concise','limits','language','position','feedback'];
  for(const topic of topics){
    await open('?chapter=findings&topic='+topic);
    for(const c of catalog.charts.filter(c=>c.topic===topic)){
      await test('figure '+c.id+' renders actualSVG and restores URL',async()=>{
        await page.locator('#research-figure-select').selectOption(c.id);await figureReady(c.id);
        const dimensions=await page.locator('#primary-figure svg').evaluate(el=>({viewBox:el.getAttribute('viewBox'),texts:el.querySelectorAll('text').length,hasTitle:!!el.querySelector('title')}));
        if(!dimensions.hasTitle||dimensions.texts<5)throw Error('Incomplete SVG');if(new URL(page.url()).searchParams.get('figure')!==c.id)throw Error('URL lost selected figure');return dimensions;
      });
      await test('figure '+c.id+' SVG and numericCSV downloads',async()=>{
        const s=await saveDownload(page.locator('.main-figure [data-root-action="svg"]'),c.id+'.svg');
        const xml=await page.evaluate(svg=>{const d=new DOMParser().parseFromString(svg,'image/svg+xml');return{valid:!d.querySelector('parsererror'),tag:d.documentElement.localName};},s.text);if(!xml.valid||xml.tag!=='svg')throw Error('Downloaded SVG is not valid XML');
        const d=await saveDownload(page.locator('.main-figure [data-root-action="csv"]'),c.id+'.csv'),rows=parseCSV(d.text),keys=Object.keys(c.data[0]);if(rows.length!==c.data.length+1)throw Error('Numeric CSV rows disagree with source');
        if(JSON.stringify(rows[0])!==JSON.stringify(keys))throw Error('CSV headers disagree with source');
        for(let i=0;i<c.data.length;i++){for(let j=0;j<keys.length;j++){const v=c.data[i][keys[j]],actual=rows[i+1][j];if(typeof v==='number'?Math.abs(Number(actual)-v)>1e-9:String(v??'')!==actual)throw Error('CSV value mismatch '+keys[j]);}}
        return {xml:xml.valid,csvRows:rows.length-1,bytes:s.text.length};
      });
    }
    if(topic==='budget'){
      await page.locator('#research-figure-select').selectOption('budget-log-gsm8k');await figureReady('budget-log-gsm8k');await screenshot('budget','预览_核心发现.png');await axe('budget desktop');
    }
    if(topic==='feedback'){
      await page.locator('#research-figure-select').selectOption('feedback-rounds-qwen3');await figureReady('feedback-rounds-qwen3');await screenshot('feedback','预览_代码反馈.png');
    }
  }
  await test('figure route refresh restores topic and selected chart',async()=>{
    const before=page.url();await page.reload({waitUntil:'domcontentloaded'});await figureReady('feedback-rounds-qwen3');if(page.url()!==before)throw Error('Refresh rewrote route');return before;
  });
  await test('browser Back restores the selected research figure',async()=>{const before=page.url();await page.locator('[data-root-action="atlas"]').click();await page.locator('.catalog-tools').waitFor();await page.goBack();await figureReady('feedback-rounds-qwen3');if(page.url()!==before)throw Error('Back lost research route');return before;});
  await axe('feedback desktop');
  await open('?chapter=findings&topic=position');await figureReady('position-nine-profile');
  await test('position special records match3600 physical observations and200-question cohorts',async()=>{
    await page.locator('.main-figure [data-root-action="special-records"]').click();await page.locator('.rs-dialog[open] .rs-summary strong').first().waitFor();
    const count=async()=>Number((await page.locator('.rs-summary > div:nth-child(1) strong').innerText()).replaceAll(',',''));
    if(await count()!==3600)throw Error('Nine-position snapshot is not3600 records');
    await page.locator('#rs-model').selectOption('qwen3');await page.locator('#rs-position').selectOption('1');
    if(await count()!==200)throw Error('Position cohort is not200');
    if(!(await page.locator('.rs-summary').innerText()).includes('142/200'))throw Error('Qwen3 first-position score is not142/200');
    const d=await saveDownload(page.locator('[data-rs-export]'),'position-cohort.csv'),rows=parseCSV(d.text),score=rows[0].indexOf('score');
    if(rows.length!==201||rows.slice(1).reduce((sum,row)=>sum+Number(row[score]),0)!==142)throw Error('Position CSV does not match current cohort');
    await page.locator('#rs-position').selectOption('20');if(!(await page.locator('.rs-summary').innerText()).includes('118/200'))throw Error('Tail cohort mismatch');
    await page.keyboard.press('Escape');return {physical:3600,cohort:200,firstPassed:142,lastPassed:118};
  });
  await open('?chapter=findings&topic=feedback&figure=feedback-rounds-qwen3');await figureReady('feedback-rounds-qwen3');
  await test('feedback special records preserve164/141 final and164/126 shared-seed cohorts',async()=>{
    await page.locator('.main-figure [data-root-action="special-records"]').click();await page.locator('.rs-dialog[open] .rs-summary strong').first().waitFor();
    if(await page.locator('#rs-model').inputValue()!=='qwen3')throw Error('Main figure did not preserve model');
    await page.locator('#rs-feedback').selectOption('counterexample');await page.locator('#rs-round').selectOption('4');
    if(!(await page.locator('.rs-summary').innerText()).includes('141/164'))throw Error('Counterexample final is not141/164');
    const d=await saveDownload(page.locator('[data-rs-export]'),'feedback-round4.csv'),rows=parseCSV(d.text),score=rows[0].indexOf('score');
    if(rows.length!==165||rows.slice(1).reduce((sum,row)=>sum+Number(row[score]),0)!==141)throw Error('Final feedback CSV mismatch');
    await page.locator('#rs-round').selectOption('0');if(!(await page.locator('.rs-summary').innerText()).includes('126/164'))throw Error('Shared seed is not126/164');
    if(await page.locator('#rs-feedback').inputValue()!=='seed')throw Error('Seed was duplicated across feedback arms');
    await page.locator('[data-rs-reset]').click();if(Number((await page.locator('.rs-summary > div:nth-child(1) strong').innerText()).replaceAll(',',''))!==5576)throw Error('Full repair snapshot not5576 physical records');
    await page.keyboard.press('Escape');return {physical:5576,final:141,seed:126,tasks:164};
  });
  await open('?chapter=atlas');
  await test('atlas filters all seven groups and restores URL',async()=>{
    if(await page.locator('.support-figure').count()!==catalog.charts.length)throw Error('Complete atlas count mismatch');
    const counts={};for(const topic of topics){await page.locator('[data-atlas-filter="'+topic+'"]').click();const actual=await page.locator('.support-figure').count(),expected=catalog.charts.filter(c=>c.topic===topic).length;if(actual!==expected)throw Error(topic+' atlas count mismatch');counts[topic]=actual;}
    await page.reload({waitUntil:'domcontentloaded'});await page.locator('[data-atlas-filter="feedback"][aria-pressed="true"]').waitFor();return counts;
  });
  await test('figure zoom dialog opens and Escape closes it',async()=>{await page.locator('.support-preview').first().click();await page.locator('#figure-dialog[open] .figure-canvas > svg').waitFor();await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.querySelector('#figure-dialog').open);return true;});
  await test('legacy13-chart exploration mounts inside new shell',async()=>{
    await page.locator('[data-root-action="explore"]').click();await page.locator('[data-x-field="chart"]').waitFor({timeout:30000});await page.locator('.r-explorer-chart svg').first().waitFor({timeout:30000});const options=await page.locator('[data-x-field="chart"] option').count();if(options!==13)throw Error('Expected13 actual chart types');return {options};
  });
  for(const width of [390,768,1440]){
    await page.setViewportSize({width,height:width===390?844:1100});
    for(const query of ['?chapter=question','?chapter=collection','?chapter=cleaning','?chapter=findings&topic=budget','?chapter=atlas']){
      await open(query);if(query.includes('topic='))await page.locator('#primary-figure svg').waitFor();
      await test(width+' shell no horizontal overflow '+query,async()=>{const state=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth}));if(state.scroll>state.width+1||state.body>state.width+1)throw Error(JSON.stringify(state));return state;});
    }
  }
  await page.setViewportSize({width:390,height:844});await open('?chapter=cleaning');await axe('cleaning phone');
  await open('?chapter=findings&topic=budget');await figureReady('budget-log-gsm8k');await axe('budget phone');
  await page.setViewportSize({width:1440,height:1100});await open('?chapter=findings&topic=budget');await figureReady('budget-log-gsm8k');
}catch(e){check('unexpected runner failure',false,{error:e.stack});}
finally{
  await browser.close();
  check('no uncaught page errors',errors.length===0,errors);
  check('no missing actual resources',failedResources.length===0,failedResources);
  const report={baseURL:base,checks:results.length,passed:results.filter(r=>r.passed).length,failed:results.filter(r=>!r.passed),errors,failedResources,downloadRetries,accessibility,screenshots,results};
  await writeFile(resolve(out,'report.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify({checks:report.checks,passed:report.passed,failed:report.failed.length,errors:errors.length,report:resolve(out,'report.json')}));
  if(report.failed.length)process.exitCode=1;
}
