import {baseURL,chromiumPath,screenshot} from './helpers.mjs';
import {createRequire} from 'node:module';
import {mkdir,readFile,writeFile,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
import {routes,root} from './inventory.mjs';
const require=createRequire(resolve('tests/package.json'));
const {chromium}=require('playwright-core');
const AxeBuilder=require('@axe-core/playwright').default;
const out=resolve(root,'after'),base=process.env.SITE_URL||new URL("",baseURL).href;
await mkdir(out,{recursive:true});
const downloadsPath=resolve('artifacts/qa/downloads');
const browser=await chromium.launch({executablePath:chromiumPath,headless:true,downloadsPath,args:['--no-sandbox','--disable-dev-shm-usage']});
const context=await browser.newContext({viewport:{width:1440,height:900},deviceScaleFactor:1,reducedMotion:'reduce',acceptDownloads:true});
const page=await context.newPage(),results=[],errors=[],failed=[],fonts=[],overlays=[];
const {fingerprints:collectFingerprints}=await import('./source-fingerprints.mjs');const fingerprints=await collectFingerprints();
page.on('pageerror',e=>errors.push({url:page.url(),error:e.message}));
page.on('requestfailed',r=>failed.push({url:r.url(),error:r.failure()?.errorText}));
const check=(name,passed,detail)=>{results.push({name,passed,detail});if(!passed)console.error('FAIL',name,JSON.stringify(detail));};
async function open(route){const url=new URL(route,base);url.searchParams.set('__check',Date.now()+'');await page.goto(url.href,{waitUntil:'networkidle'});await page.evaluate(()=>document.fonts.ready);}
async function auditAxe(label){const r=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();overlays.push({label,violations:r.violations,incomplete:r.incomplete});check(label+' accessibility',!r.violations.some(v=>['serious','critical'].includes(v.impact)),r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.length})));}
async function downloadClick(selector,file){const event=page.waitForEvent('download');await page.locator(selector).click();const d=await event;await d.saveAs(resolve(out,file));return readFile(resolve(out,file),'utf8');}
try{
 await page.setViewportSize({width:1440,height:1000});await open('explore.html?mode=explore&chart=model');
 await page.locator('#task-select').selectOption('math500');await page.locator('#prompt-select').selectOption('NoCoT');await page.locator('#shared-model').selectOption('qwen');
 check('Shared filters write URL',page.url().includes('task=math500')&&page.url().includes('prompt=NoCoT')&&page.url().includes('models=qwen'),page.url());
 await page.reload({waitUntil:'networkidle'});check('Shared filters survive refresh',await page.locator('#task-select').inputValue()==='math500'&&await page.locator('#shared-model').inputValue()==='qwen');
 const exported=await downloadClick('[data-action="export-chart"]','library-chart.svg');check('Interactive chart SVG download',exported.includes('<svg')&&exported.length>1000);
 await auditAxe('model-chart desktop');
 for(const [id,title] of [['overview-mode','简洁推理'],['position-mode','资料位置'],['code-mode','独立采样'],['demo-mode','输出长度'],['explore-mode','模型柱图']]){await page.locator('#'+id).click();check('Primary mode '+id,(await page.locator('main h1').innerText()).includes(title));}
 await open('explore.html#budget');await page.locator('[data-action="publication-method"]').click();
 check('Statistics dialog opens and receives focus',await page.locator('#inspector').isVisible()&&await page.locator('#close-inspector').evaluate(el=>el===document.activeElement));
 await screenshot(page,{path:resolve(out,'dialog-method-desktop.png')});await auditAxe('method dialog');
 await page.keyboard.press('Escape');check('Escape closes dialog and restores focus',!(await page.locator('#inspector').isVisible())&&await page.locator('[data-action="publication-method"]').evaluate(el=>el===document.activeElement));
 await open('explore.html#position');const cell=page.locator('#publication-root [data-pub-prompt]').first();await cell.click();
 await page.locator('#inspector tbody tr').first().waitFor();
 check('Position cell opens exactly 400 matching responses',(await page.locator('#inspector .subline').innerText()).includes('400'));
 const csv=await downloadClick('[data-action="export-records"]','position-cohort.csv');check('Selected cohort CSV retains 400 rows',csv.trim().split(/\r?\n/).length===401);
 await page.locator('#inspector [data-record]').first().click();check('Anonymous record detail remains available',(await page.locator('#inspector').innerText()).includes('匿名题号'));
 await page.setViewportSize({width:390,height:844});await screenshot(page,{path:resolve(out,'dialog-record-mobile.png')});await auditAxe('record detail phone');await page.keyboard.press('Escape');
 await page.setViewportSize({width:1440,height:1000});await cell.click();await page.locator('#inspector tbody tr').first().waitFor();await page.locator('[data-action="explore-selection"]').click();
 check('Position-to-exploration preserves cohort',(await page.locator('.figure-note').allTextContents()).join(' ').includes('400')&&page.url().includes('dataset=document_qa'),page.url());
 await page.reload({waitUntil:'networkidle'});check('Linked cohort survives refresh',(await page.locator('.figure-note').allTextContents()).join(' ').includes('400'));
 await open('explore.html?codeView=sampling#code');await page.waitForFunction(()=>document.querySelector('#code-play')?.disabled===false);
 await page.locator('#code-sample-step').fill('2');await page.locator('#code-sample-step').dispatchEvent('input');check('Code sample step and URL update',(await page.locator('#code-sample-label').innerText()).includes('2 / 5')&&page.url().includes('codeStep=2'));
 await page.locator('#code-play').click();await page.waitForFunction(()=>document.querySelector('#code-sample-step')?.value==='5',null,{timeout:12000});check('Code playback reaches actual fifth sample',(await page.locator('#code-sample-label').innerText()).includes('5 / 5'));
 await page.locator('[data-code-action="method"]').click();check('Code method dialog preserves study scope',(await page.locator('#inspector').innerText()).includes('90,210'));const summary=await downloadClick('[data-code-action="export-summary"]','code-summary.csv');check('Code statistics CSV download',summary.replace(/^\uFEFF/,'').startsWith('model,prompt')&&summary.trim().split(/\r?\n/).length===4);await page.keyboard.press('Escape');
 await open('explore.html?codeView=tokens#code');await page.locator('.code-numeric-filter summary').click();await page.locator('#code-range-form [name=xmax]').fill('250');await page.locator('#code-range-form button[type=submit]').click();check('Numeric brush remains linked to URL',page.url().includes('codeBrush=0%2C250%2C0%2C100'),page.url());
 await page.locator('.code-numeric-filter summary').click();await page.locator('#code-reset-range').click();check('Clearing numeric brush restores all conditions',!page.url().includes('codeBrush='));
 await auditAxe('code tokens');
 await open('explore.html?codeView=errors#code');await page.locator('#code-study-error').selectOption('assertion_failure');check('Code error selector updates state',page.url().includes('codeError=assertion_failure'));await page.locator('[data-code-action="records"]').first().click();await page.locator('#inspector [data-code-record]').first().waitFor();await page.locator('#inspector [data-code-record]').first().click();check('Code scoring record detail preserved',(await page.locator('#inspector').innerText()).includes('相同条件的 5 次独立结果'));await page.keyboard.press('Escape');
 await open('explore.html?mode=explore&chart=behavior');await page.locator('#behavior-records').waitFor();await page.locator('#keyboard-family').focus();check('Keyboard cohort controls reveal on focus',await page.locator('#behavior-keyboard').evaluate(el=>el.getBoundingClientRect().width>100));await page.locator('#keyboard-records').click();await page.locator('#inspector tbody tr').first().waitFor();check('Behavior cohort records work',await page.locator('#inspector tbody tr').count()>0);await page.keyboard.press('Escape');
 await page.setViewportSize({width:390,height:844});await auditAxe('behavior phone');
 await open('explore.html?mode=explore&chart=model');await page.locator('.story-home').click();await page.locator('#gate-title').waitFor();await page.locator('.topbar-actions a').click();await page.locator('#library-main svg').waitFor();check('Home-library round trip',page.url().includes('mode=explore'));await auditAxe('library phone');
 await page.emulateMedia({reducedMotion:'no-preference'});await page.locator('#position-mode').click();const motion=await page.evaluate(()=>({actual:document.getAnimations().filter(a=>a.playState==='running').length,...window.LensSiteUI.inspect()}));check('Library has real normal-mode motion',motion.actual>0&&motion.played>0,motion);await page.waitForTimeout(750);check('Library animations settle',await page.evaluate(()=>window.LensSiteUI.inspect().running===0));
 await page.locator('#overview-mode').click();await page.emulateMedia({reducedMotion:'reduce'});await page.waitForTimeout(60);check('Changing motion preference stops animations',await page.evaluate(()=>window.LensSiteUI.inspect().running===0&&document.getAnimations().every(a=>a.playState!=='running')));
 await page.locator('#code-mode').click();await page.waitForTimeout(100);check('Reduced-motion library content remains visible',await page.locator('main h1').isVisible()&&await page.evaluate(()=>window.LensSiteUI.inspect().running===0));
 await page.emulateMedia({reducedMotion:'no-preference'});await page.evaluate(()=>{for(let i=0;i<15;i++)document.querySelector(['#overview-mode','#position-mode','#code-mode','#demo-mode','#explore-mode'][i%5]).click();});await page.waitForTimeout(900);check('Rapid library navigation releases animations',await page.evaluate(()=>window.LensSiteUI.inspect().running===0));
 check('No uncaught browser errors',!errors.length,errors);check('No failed resources',!failed.length,failed);
}catch(error){check('Unexpected test exception',false,error.stack);}
finally{await writeFile(resolve(out,'library-interactions.json'),JSON.stringify({matrix:{routes:routes.map(r=>r.key),viewports:[320,390,768,1440]},fingerprints,results,fonts,errors,failedRequests:failed},null,2)+'\n');await writeFile(resolve(out,'library-accessibility.json'),JSON.stringify(overlays,null,2)+'\n');await browser.close();}
console.log(JSON.stringify({checks:results.length,passed:results.filter(r=>r.passed).length,failed:results.filter(r=>!r.passed).map(r=>({name:r.name,detail:r.detail}))}));
if(results.some(r=>!r.passed))process.exitCode=1;
