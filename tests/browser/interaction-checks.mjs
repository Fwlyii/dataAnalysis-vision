import {baseURL,chromiumPath,screenshot} from './helpers.mjs';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {writeFile,mkdir} from 'node:fs/promises';
import {routes,root} from './inventory.mjs';
import {fingerprints as collect} from './source-fingerprints.mjs';
const require=createRequire(resolve('tests/package.json'));
const {chromium}=require('playwright-core');
const browser=await chromium.launch({executablePath:chromiumPath,args:['--no-sandbox','--disable-dev-shm-usage']});
const results=[],errors=[],fingerprints=await collect();
const check=(name,passed,detail={})=>{results.push({name,passed:!!passed,detail});if(!passed)console.error('FAIL',name,JSON.stringify(detail));};
const base=new URL("",baseURL).href;
const visible=s=>document.querySelector(s)?.getClientRects().length>0;
async function page(width=1440,motion='no-preference'){const p=await browser.newPage({viewport:{width,height:width===1920?1080:900},reducedMotion:motion});p.on('pageerror',e=>errors.push({url:p.url(),message:e.message}));return p;}
async function open(p,url){const u=new URL(url,base);u.searchParams.set('__interaction',String(Date.now()));await p.goto(u.href,{waitUntil:'networkidle'});await p.evaluate(()=>document.fonts.ready);await p.waitForTimeout(760);await p.waitForFunction(()=>[...document.querySelectorAll('#library-main,#library-side')].filter(e=>e.getClientRects().length).every(e=>!!e.querySelector('.chart-empty')||e.querySelector('svg')&&(!window.echarts?.getInstanceByDom(e)||window.echarts.getInstanceByDom(e).getZr().animation.isFinished())));if(url.includes('codeView=tokens'))await p.waitForFunction(()=>document.querySelector('#code-vega-scatter svg')&&document.querySelector('#code-linked-errors svg'));}
async function shot(p,name){await screenshot(p,{path:resolve(root,'after',name+'.png')});}
const signature=()=>{const root=document.querySelector('.deck-panel.is-active')||document.querySelector('#stage');return [...root.querySelectorAll('svg')].filter(s=>!s.parentElement.closest('svg')&&s.getBoundingClientRect().width>=150).map(s=>s.outerHTML).join('\n');};
try{
 for(const width of [1440,1920]){
  const p=await page(width);
  for(const route of routes){
   console.log('route',width,route.key);await open(p,route.url);
   const state=await p.evaluate(()=>LensInteractions.inspect());
   const region=route.section?'.deck-panel.is-active':'#stage';
   if(route.key==='deck-gateway'){
    await p.locator('.ix-home-help summary').click();check(route.key+' '+width+' usage guide opens',await p.locator('.ix-home-help').getAttribute('open')!==null);await shot(p,'gateway-guide-'+width);continue;
   }
   if(['question','collection','cleaning'].includes(route.section)){check(route.key+' '+width+' custom card/step module',await p.locator(region+' .ix-card-hit').count()===(route.section==='question'?3:route.section==='collection'?5:4));continue;}
   const bar=p.locator(region+' .ix-reading');
   check(route.key+' '+width+' one view-specific interaction scene',await bar.count()===1&&state.key&&state.sceneCounts[state.key]>0,{state});
   if(await bar.count()!==1)continue;
   await p.mouse.move(0,0);await p.waitForTimeout(80);const before=await p.evaluate(signature),url=p.url();
   await bar.locator('[data-ix-guide]').click();
   const expanded=await bar.locator('.ix-guide-body').isVisible();
   check(route.key+' '+width+' guide opens and describes this view',expanded&&(await bar.locator('.ix-guide-body').innerText()).length>30);
   await bar.locator('[data-ix-guide]').click();
   await bar.locator('[data-ix-focus]').click();
   check(route.key+' '+width+' focus highlights one original chart',await p.locator('.ix-focus-target').count()===1&&await p.evaluate(()=>LensInteractions.inspect().focus));
   await p.keyboard.press('Escape');await p.mouse.move(0,0);await p.waitForTimeout(500);
   check(route.key+' '+width+' Escape restores focus, original SVG and URL unchanged',!(await p.evaluate(()=>LensInteractions.inspect().focus))&&await p.evaluate(signature)===before&&p.url()===url&&await bar.locator('[data-ix-focus]').evaluate(e=>e===document.activeElement));
   if(await p.evaluate(signature)!==before){await writeFile(resolve(root,'iterations',route.key+'-'+width+'-before.svg.txt'),before);await writeFile(resolve(root,'iterations',route.key+'-'+width+'-after.svg.txt'),await p.evaluate(signature));}
   const layout=await bar.evaluate(e=>{const b=e.getBoundingClientRect();const title=e.querySelector('strong').getBoundingClientRect();return{left:b.left,right:b.right,titleWidth:title.width,overflow:document.documentElement.scrollWidth>innerWidth,controls:[...e.querySelectorAll('button')].map(b=>{const r=b.getBoundingClientRect();return {x:r.x,right:r.right,w:r.width,h:r.height};})};});
   check(route.key+' '+width+' interaction bar aligns without clipping',!layout.overflow&&layout.left>=0&&layout.right<=width+1&&layout.controls.every(r=>r.w>40&&r.h>=34&&r.x>=layout.left&&r.right<=layout.right),layout);
  }
  console.log('view interactions '+width+' complete');
  // New interactions are exercised with the keyboard and their actual native navigation.
  await open(p,'index.html?intro=0#question');
  const links=['concise','position','repair'];
  for(let i=0;i<3;i++){
   const hit=p.locator('#question .ix-card-hit').nth(i);await hit.focus();await p.keyboard.press('Enter');
   check('question '+width+' keyboard expands exactly one direction '+i,await p.locator('#question .ix-selected').count()===1&&await hit.getAttribute('aria-expanded')==='true');
   const alignment=await p.locator('#question .question-points').evaluate(el=>[...el.children].map(c=>c.querySelector('.point-icon').getBoundingClientRect().top));
   check('question '+width+' selected card keeps icons aligned '+i,Math.max(...alignment)-Math.min(...alignment)<1,alignment);
   await p.keyboard.press('Tab');check('question '+width+' expanded action follows its card in Tab order '+i,await p.locator('#question .ix-dimension-detail:not([hidden]) a').evaluate(e=>e===document.activeElement));const href=await p.locator('#question .ix-dimension-detail:not([hidden]) a').getAttribute('href');check('question '+width+' correct discovery target '+i,href.includes('finding='+links[i]),href);
  }
  await shot(p,'question-selected-'+width);
  await p.locator('#question .ix-dimension-detail:not([hidden]) a').click();await p.waitForTimeout(900);
  check('question '+width+' real link enters feedback finding',await p.locator('.finding-nav [aria-current=page]').getAttribute('data-chapter')==='repair');
  await open(p,'index.html?intro=0#collection');
  const counts=['74,400','74,800','90,210','3,600','5,576'];
  for(let i=0;i<5;i++){
   await p.locator('#collection .ix-card-hit').nth(i).click();
   check('collection '+width+' experiment '+i+' exact saved scope',await p.locator('.ix-experiment-detail').isVisible()&&(await p.locator('.ix-experiment-meta>strong').innerText())===counts[i]&&await p.locator('#collection .ix-selected').count()===1);
  }
  await shot(p,'collection-selected-'+width);await p.locator('#collection .ix-card-hit').nth(4).click();check('collection '+width+' second click collapses',!(await p.locator('.ix-experiment-detail').isVisible()));
  await open(p,'index.html?intro=0#cleaning');
  const original=await p.locator('.schema-preview').innerText();
  for(let i=0;i<4;i++){
   await p.locator('#cleaning .ix-card-hit').nth(i).focus();await p.keyboard.press('Enter');
   check('pipeline '+width+' step '+i+' highlights actual fields without changing sample',await p.locator('.ix-key-selected').count()>0&&await p.locator('.schema-preview').innerText()===original&&await p.locator('#cleaning .ix-selected').count()===1);
  }
  await shot(p,'pipeline-selected-'+width);await p.locator('#cleaning .ix-card-hit').nth(3).click();check('pipeline '+width+' clears field emphasis',await p.locator('.ix-key-selected').count()===0);
  await p.close();
 }
 // Inspect real running effects during a native control switch, not just a CSS class.
 const p=await page();await open(p,'index.html?intro=0#landscape');
 const transition=await p.evaluate(async()=>{const before=LensInteractions.inspect().transitions;document.querySelector('[data-overview-view="heatmap"]').click();await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));return{before,after:LensInteractions.inspect(),animations:document.getAnimations().map(a=>({playState:a.playState,frames:a.effect?.getKeyframes?.()}))};});
 check('actual Motion mini scene plays on scientific view switch',transition.after.transitions>transition.before&&transition.after.driver==='motion-mini'&&transition.after.running>0&&transition.animations.some(a=>a.playState==='running'&&a.frames.length>=2),transition);
 await p.waitForTimeout(850);check('scene settles, no new continuous animation remains',await p.evaluate(()=>LensInteractions.inspect().running===0&&!LensInteractions.inspect().scheduled));
 check('completed effects restore original inline layout properties',await p.evaluate(()=>[...document.querySelectorAll('.panel-header,.ix-reading,.overview-plot')].every(e=>['transform','clip-path','opacity','scale'].every(k=>!e.style.getPropertyValue(k)))));
 const plot=p.locator('.overview-plot');await plot.click({position:{x:30,y:30}});check('real chart pointer click produces an external optical feedback ring',await p.locator('.ix-click-mark').count()===1);await p.waitForTimeout(650);check('click feedback removes its transient node',await p.locator('.ix-click-mark').count()===0);
 for(const key of ['concise','language','position','repair','limits']){
  await open(p,'index.html?intro=0&finding='+key+'#findings');await p.locator('.export-menu summary').click();check(key+' export menu remains clickable',await p.locator('#download-svg').isVisible());
 }
 await open(p,'explore.html#budget');await p.locator('[data-action="publication-method"]').click();await p.waitForTimeout(150);
 check('native detail panel receives a visible sliding entry',await p.locator('#inspector').isVisible()&&await p.evaluate(()=>LensInteractions.inspect().running>0));
 await p.keyboard.press('Escape');check('native detail still closes with Escape',!(await p.locator('#inspector').isVisible()));
 // Rapid tab changes must leave just one usable bar and no accumulation of running effects.
 for(let i=0;i<4;i++)for(const id of ['code-mode','demo-mode','position-mode','explore-mode','overview-mode'])await p.locator('#'+id).click();
 await p.waitForTimeout(900);check('20 rapid native mode changes leave one settled usable scene',await p.locator('#stage .ix-reading').count()===1&&await p.evaluate(()=>LensInteractions.inspect().running===0));
 await p.locator('[data-ix-focus]').click();await p.locator('#code-mode').click();await p.waitForTimeout(900);check('changing views exits old focus cleanly',await p.locator('.ix-focus-target').count()===0&&!(await p.evaluate(()=>LensInteractions.inspect().focus)));
 // New scenes cancel immediately when hidden.
 const hidden=await p.evaluate(async()=>{document.querySelector('[data-code-view="errors"]').click();await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));const before=LensInteractions.inspect();Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));const after=LensInteractions.inspect();delete document.hidden;return {before,after};});
 check('hiding page cancels new effects and scheduled frames',hidden.before.running>0&&hidden.after.running===0&&!hidden.after.scheduled,hidden);
 // Full cleanup leaves native research controls usable, including after new render.
 const disposed=await p.evaluate(()=>{LensInteractions.dispose();return LensInteractions.inspect();});
 check('dispose releases observers, effects and pending frame',disposed.suspended&&disposed.running===0&&!disposed.scheduled,disposed);await p.locator('[data-code-view="prompts"]').click();await p.waitForTimeout(350);check('research remains usable after enhancement disposal',await p.locator('[data-code-view="prompts"][aria-current="page"]').count()===1);
 await p.close();
 for(const motion of ['reduce','no-preference']){
  const fallback=await page(1440,motion);await fallback.route('**/motion-mini-14.9.0.min.js',route=>route.fulfill({status:200,contentType:'text/javascript',body:'/* deliberately unavailable animation driver */'}));
  await open(fallback,'explore.html?mode=explore&chart=heatmap');await fallback.locator('[data-ix-guide]').click();const s=await fallback.evaluate(()=>LensInteractions.inspect());
  check('animation library unavailable '+motion+' retains controls and readable graph',await fallback.locator('.ix-guide-body').isVisible()&&await fallback.locator('#library-main svg').count()>0&&(motion==='reduce'?s.running===0:s.driver==='web-animations'),s);await fallback.close();
 }
 for(const width of [320,390,768]){
  const narrow=await page(width,'reduce');
  for(const route of ['index.html?intro=0#question','index.html?intro=0#collection','index.html?intro=0#cleaning','index.html?intro=0#landscape','index.html?intro=0&finding=concise#findings','explore.html?mode=explore&chart=heatmap','explore.html?codeView=tokens#code']){
   await open(narrow,route);const guide=narrow.locator('.deck-panel.is-active [data-ix-guide],#stage [data-ix-guide]');if(await guide.count())await guide.click();else await narrow.locator('.deck-panel.is-active .ix-card-hit').first().click();
   const state=await narrow.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,running:LensInteractions.inspect().running,panels:[...document.querySelectorAll('.ix-reading,.ix-experiment-detail,.ix-pipeline-info')].filter(e=>e.getClientRects().length).map(e=>{const b=e.getBoundingClientRect();return{x:b.x,right:b.right,scroll:e.scrollWidth,client:e.clientWidth};})}));
   check('narrow '+width+' '+route+' new interaction stays accessible without motion or overflow',!state.overflow&&state.running===0&&state.panels.every(e=>e.x>=0&&e.right<=width+1&&e.scroll<=e.client+1),state);
  }await narrow.close();
 }
 check('no uncaught errors in new interaction checks',errors.length===0,errors);
} catch(e){check('interaction verification completes',false,{message:e.stack});console.error(e.stack);}
finally{await browser.close();await writeFile(resolve(root,'after/interaction-checks.json'),JSON.stringify({fingerprints,results},null,2)+'\n');}
console.log(JSON.stringify({checks:results.length,passed:results.filter(r=>r.passed).length,failures:results.filter(r=>!r.passed).map(r=>r.name)}));if(results.some(r=>!r.passed))process.exitCode=1;
