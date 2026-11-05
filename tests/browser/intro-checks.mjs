import {baseURL,chromiumPath,screenshot} from './helpers.mjs';
import{fingerprints as collectFingerprints}from'./source-fingerprints.mjs';const fingerprints=await collectFingerprints();
import {createRequire} from 'node:module';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const require=createRequire(resolve('tests/package.json'));
const {chromium}=require('playwright-core'),AxeBuilder=require('@axe-core/playwright').default;
const out=resolve('artifacts/qa/after');await mkdir(out,{recursive:true});
const browser=await chromium.launch({executablePath:chromiumPath,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
const base=new URL("",baseURL).href,results=[],errors=[],states=[];
const check=(name,passed,detail)=>{results.push({name,passed,detail});if(!passed)console.error('FAIL',name,JSON.stringify(detail));};
async function fresh(width=1440,reducedMotion='no-preference',dpr=1){const context=await browser.newContext({viewport:{width,height:width===1440?900:width===768?1024:width===390?844:740},reducedMotion,deviceScaleFactor:dpr});const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));return{context,page};}
async function replayOpening(page){if(await page.locator('#intro-replay').isVisible())await page.locator('#intro-replay').click();else await page.evaluate(()=>LensIntro.play());}
async function open(page,route='?intro=1'){await page.goto(base+route,{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>!!window.LensIntro);}
async function at(page,time){await page.waitForFunction(time=>LensIntro.inspect().elapsed>=time,time);return page.evaluate(()=>LensIntro.inspect());}
async function clean(page){return page.evaluate(()=>({state:LensIntro.inspect(),hidden:document.querySelector('#lens-intro').hidden,inert:document.querySelectorAll('[data-intro-inert]').length,pending:document.documentElement.matches('.intro-pending,.intro-active'),overflow:document.documentElement.scrollWidth>innerWidth,locked:document.documentElement.classList.contains('intro-active'),svg:!!document.querySelector('#plot svg'),focus:document.activeElement.id,land:!!document.querySelector('.intro-target-hidden'),arrivals:document.querySelectorAll('.intro-arrival').length}));}
async function finished(page){await page.waitForFunction(()=>!LensIntro.inspect().running);return clean(page);}
try{
 for(const width of [1440,768,390,320]){
  const {context,page}=await fresh(width);await open(page);
  const start=await at(page,350);check(width+' auto forced start',start.running&&start.phase==='awakening',start.phase);
  await page.waitForFunction(()=>!!document.querySelector('#plot svg'));check(width+' data initializes beneath running intro',await page.evaluate(()=>LensIntro.inspect().running&&document.querySelector('main').inert));
  const moving=await at(page,1450);check(width+' particles move in real Canvas',JSON.stringify(moving.points)!==JSON.stringify(start.points)&&moving.raf>0,moving.points);
  await at(page,2600);const lens=await page.locator('.intro-optics').evaluate(el=>({opacity:+getComputedStyle(el).opacity,rings:el.querySelectorAll('.intro-ring').length,drawn:[...el.querySelectorAll('.intro-ring')].some(r=>+r.style.strokeDashoffset<.1)}));check(width+' optical rings form continuously',lens.opacity>.5&&lens.rings===5&&lens.drawn,lens);
  await at(page,3400);check(width+' five named abstract research motifs',await page.locator('.intro-signal').count()===5&&await page.locator('.intro-signals').evaluate(el=>+el.style.opacity>.8));
  await at(page,4700);check(width+' native brand and copy',await page.locator('.intro-name').innerText()==='知微'&&await page.locator('.intro-subtitle').innerText()==='大模型行为洞察与可视交互分析系统'&&await page.locator('.intro-titles img,.intro-titles canvas').count()===0);
  const session=await context.newCDPSession(page);await session.send('DOM.enable');await session.send('CSS.enable');const {root}=await session.send('DOM.getDocument'),{nodeId}=await session.send('DOM.querySelector',{nodeId:root.nodeId,selector:'.intro-name'});const font=await session.send('CSS.getPlatformFontsForNode',{nodeId});check(width+' brand actually uses custom native font',font.fonts.length>0&&font.fonts.every(f=>f.isCustomFont&&f.familyName==='LENS Intro'),font.fonts);await session.detach();
  const transfer=await at(page,5450);check(width+' real measured shared-element transition',!!transfer.first&&!!transfer.last&&transfer.first.width>transfer.last.width&&transfer.driver==='motion-mini',transfer);
  check(width+' aperture reveals live system',await page.locator('.intro-atmosphere').evaluate(el=>el.style.maskImage.includes('radial-gradient')));
  const done=await finished(page);states.push({width,done});check(width+' finite completion and cleanup',done.hidden&&done.focus==='presentation'&&!done.inert&&!done.pending&&!done.locked&&!done.land&&!done.arrivals&&done.state.raf===0&&done.state.canvasPixels===1&&done.svg&&!done.overflow,done);
  check(width+' completes around six seconds',done.state.history.at(-1).elapsed>=5900&&done.state.history.at(-1).elapsed<6500,done.state.history.at(-1));
  const draws=done.state.history.at(-1).draws;await page.waitForTimeout(100);check(width+' no continuing particle loop',await page.evaluate(draws=>LensIntro.inspect().history.at(-1).draws===draws&&LensIntro.inspect().raf===0,draws));
  await replayOpening(page);const replay=await page.evaluate(()=>LensIntro.inspect());check(width+' replay resets deterministic composition',replay.running&&replay.signature===start.signature);await page.locator('.intro-skip').click();const skipped=await finished(page);check(width+' skip restores focus and controls',skipped.focus==='intro-replay'&&!skipped.locked&&!skipped.inert&&skipped.svg);
  await context.close();console.log('Intro timeline '+width+'px passed');
 }
 {
  const {context,page}=await fresh();await open(page,'');check('First normal visit auto-plays',await page.evaluate(()=>LensIntro.inspect().running));await page.locator('.intro-skip').click();
  await page.locator('.topbar-actions a').click();await page.waitForLoadState('networkidle');check('Library has no intro module',await page.evaluate(()=>typeof window.LensIntro==='undefined'));
  await page.locator('.story-home').click();await page.waitForLoadState('networkidle');check('Library return does not replay in same session',await page.evaluate(()=>!LensIntro.inspect().running&&LensIntro.inspect().canvasPixels===0));
  await page.reload({waitUntil:'networkidle'});check('Normal refresh retains session decision',await page.evaluate(()=>!LensIntro.inspect().running));
  await open(page,'?intro=1#repair');check('Explicit force overrides session decision and preserves deep link',await page.evaluate(()=>LensIntro.inspect().running&&location.hash==='#repair'&&document.querySelector('[data-chapter="repair"]').getAttribute('aria-current')==='page'));await page.keyboard.press('Escape');
  await open(page,'?intro=0&position=20&ci=1#position');check('Explicit zero skips and retains query state',await page.evaluate(()=>!LensIntro.inspect().running&&document.querySelector('#position').value==='8'&&document.querySelector('#ci').checked));
  const url=page.url();await replayOpening(page);await page.locator('.intro-skip').click();check('Replay does not mutate URL/history',page.url()===url);
  await page.locator('[data-chapter="language"]').click();await page.reload({waitUntil:'networkidle'});check('Latest finding replaceState survives refresh',await page.locator('[data-chapter="language"][aria-current="page"]').count()===1&&page.url().includes('finding=language'));
  await page.locator('.research-home').click();const orb=page.locator('#gate-collection'),rect=await orb.boundingBox();await page.mouse.move(rect.x+rect.width/2,rect.y+rect.height/2);await orb.click();await page.waitForFunction(()=>document.body.dataset.section==='collection');await page.goBack();await page.goBack();check('Latest section pushState restores findings',await page.evaluate(()=>document.body.dataset.section==='findings'));
  await replayOpening(page);await at(page,2500);await page.setViewportSize({width:390,height:844});check('Resize during lens phase adapts canvas',await page.evaluate(()=>LensIntro.inspect().running));await page.locator('.intro-skip').click();check('Resize cleanup restores narrow page',!(await clean(page)).overflow);
  await replayOpening(page);await at(page,5400);await page.setViewportSize({width:768,height:1024});const resizeEnd=await finished(page);check('Resize during transfer safely finishes',resizeEnd.state.history.at(-1).reason==='resize-transfer'&&!resizeEnd.inert&&!resizeEnd.locked);
  await replayOpening(page);await page.emulateMedia({reducedMotion:'reduce'});const preferenceEnd=await finished(page);check('Changed reduced-motion preference cancels immediately',preferenceEnd.state.history.at(-1).reason==='reduced-motion'&&!preferenceEnd.inert&&await page.locator('#intro-replay').isDisabled());
  await page.emulateMedia({reducedMotion:'no-preference'});await page.waitForTimeout(30);check('Preference reset enables replay',await page.locator('#intro-replay').isEnabled());
  for(let i=0;i<8;i++){await replayOpening(page);await page.locator('.intro-skip').click();}
  check('Repeated replay does not duplicate DOM or optical ticks',await page.locator('#lens-intro').count()===1&&await page.locator('.intro-tick').count()===96&&(await clean(page)).state.raf===0);
  await replayOpening(page);await page.keyboard.press('Tab');check('Keyboard remains in accessible skip control',await page.locator('.intro-skip').evaluate(el=>el===document.activeElement));await page.keyboard.press('Escape');
  await replayOpening(page);await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));});const hidden=await finished(page);check('Visibility event cancels work (simulated hidden state)',hidden.state.history.at(-1).reason==='hidden'&&hidden.state.raf===0);await page.evaluate(()=>delete document.hidden);
  await replayOpening(page);await page.evaluate(()=>{location.hash='#limits';});const routed=await finished(page);check('Hash navigation cancels intro and retains router',routed.state.history.at(-1).reason==='navigation'&&await page.locator('[data-model]').count()===4);
  await context.close();
 }
 {
  const {context,page}=await fresh(390,'reduce');await open(page);check('Reduced-motion force request never allocates Canvas',await page.evaluate(()=>!LensIntro.inspect().running&&LensIntro.inspect().canvasPixels===0&&!!document.querySelector('#plot svg')));check('Reduced-motion replay respects preference',await page.evaluate(()=>LensIntro.play()===false));
  const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();check('Reduced-motion system accessibility',!axe.violations.some(v=>['serious','critical'].includes(v.impact)),axe.violations.map(v=>({id:v.id,impact:v.impact})));
  await context.close();
 }
 {
  const {context,page}=await fresh();await open(page);await page.locator('.intro-skip').click();await replayOpening(page);
  const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();check('Active dialog accessibility',!axe.violations.some(v=>['serious','critical'].includes(v.impact)),axe.violations.map(v=>({id:v.id,impact:v.impact})));await page.locator('.intro-skip').click();
  check('Runtime uses no video, image sequence, Lottie or external media',await page.evaluate(()=>!document.querySelector('#lens-intro video,#lens-intro img:not(.orb-planet)')&&[...document.querySelectorAll('#lens-intro img')].every(i=>i.closest('.gate-orb')&&i.alt===''&&i.getAttribute('aria-hidden')==='true'&&/assets\/visual\/planet-(question|collection|cleaning|landscape|findings)\.webp$/.test(i.getAttribute('src')))&&!performance.getEntriesByType('resource').some(r=>/\.(mp4|webm|gif)(\?|$)|lottie/i.test(r.name))));
  await context.close();
 }
 {
  const {context,page}=await fresh();await context.addInitScript(()=>{Object.defineProperty(window,'sessionStorage',{get(){throw new Error('storage denied');}});});await open(page,'');check('Unavailable session storage falls back to usable system',await page.evaluate(()=>!LensIntro.inspect().running&&!!document.querySelector('#plot svg')));await context.close();
 }
 {
  const {context,page}=await fresh();await context.addInitScript(()=>{HTMLCanvasElement.prototype.getContext=()=>null;});await open(page);check('Canvas failure unlocks the real system',await page.evaluate(()=>!LensIntro.inspect().running&&!document.documentElement.matches('.intro-pending,.intro-active')&&!!document.querySelector('#plot svg')&&!document.querySelector('[data-intro-inert]')));await context.close();
 }
 {
  const {context,page}=await fresh();await context.route('**/runtime/intro.js*',route=>route.abort());await page.goto(base+'?intro=1',{waitUntil:'domcontentloaded'});await page.waitForTimeout(1900);check('Missing intro script bootstrap watchdog reveals system',await page.evaluate(()=>!document.documentElement.classList.contains('intro-pending')&&!!document.querySelector('#plot svg')&&getComputedStyle(document.querySelector('main')).visibility==='visible'));await context.close();
 }
 {
  const {context,page}=await fresh();await context.route('**/runtime/intro.js*',async route=>{await new Promise(r=>setTimeout(r,2200));await route.continue();});await open(page,'?intro=1#question');
  check('Explicit force still starts when module arrives after bootstrap watchdog',await page.evaluate(()=>LensIntro.inspect().running));await page.waitForFunction(()=>LensIntro.inspect().history.length>0&&!LensIntro.inspect().running);check('Late forced intro completes into latest native deck',(await clean(page)).state.history.at(-1).reason==='complete'&&await page.locator('#question-title').isVisible());await context.close();
 }
 {
  const {context,page}=await fresh();await context.route('**/runtime/intro.js*',async route=>{await new Promise(r=>setTimeout(r,2200));await route.continue();});await open(page,'#question');check('Late ordinary visit keeps graceful watchdog fallback',await page.evaluate(()=>!LensIntro.inspect().running&&!document.documentElement.classList.contains('intro-pending')&&LensIntro.inspect().canvasPixels===0));await context.close();
 }
 check('No uncaught browser errors',!errors.length,errors);
}catch(error){check('Unexpected test exception',false,error.stack);}
finally{await writeFile(resolve(out,'intro-checks.json'),JSON.stringify({fingerprints,results,states,errors},null,2)+'\n');await browser.close();}
console.log(JSON.stringify({checks:results.length,passed:results.filter(r=>r.passed).length,failed:results.filter(r=>!r.passed).map(r=>({name:r.name,detail:r.detail}))}));
if(results.some(r=>!r.passed))process.exitCode=1;
