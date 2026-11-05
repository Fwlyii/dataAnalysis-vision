/* Finite enhancement only. Upstream owns navigation, evidence and chart rendering. */
(() => {
  'use strict';
  const enrich = () => {
    for (const el of document.querySelectorAll('.data-scroll')) {
      el.tabIndex = 0; el.setAttribute('role','region'); el.setAttribute('aria-label','Data table; scroll to inspect all columns');
    }
    for (const el of document.querySelectorAll('.plot-scroll,.overview-plot')) {
      if (!el.previousElementSibling?.classList.contains('scroll-hint')) {
        const hint=document.createElement('p');hint.className='scroll-hint';hint.textContent='↔ Scroll the figure to inspect all values';el.before(hint);
      }
    }
  };
  enrich();
  // Each native route render replaces children; one observer adds access to new tables.
  new MutationObserver(enrich).observe(document.querySelector('.deck')||document.querySelector('#stage'),{childList:true,subtree:true});
  const preference=matchMedia('(prefers-reduced-motion: reduce)'),active=new Set();
  let played=0,sectionTransitions=0;
  const cancel=()=>{for(const a of active)a.cancel();active.clear();};
  const reveal=(el,section=false)=>{
    cancel();
    if(!el||preference.matches||document.hidden||document.documentElement.matches('.intro-active,.intro-pending'))return;
    const a=el.animate([{opacity:0,transform:'translateY(8px)'},{opacity:1,transform:'none'}],{duration:380,easing:'cubic-bezier(.22,1,.36,1)'});
    active.add(a);played++;if(section)sectionTransitions++;
    a.finished.then(()=>active.delete(a),()=>active.delete(a));
  };
  preference.addEventListener('change',cancel);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)cancel();});
  addEventListener('pagehide',cancel);
  const deck=document.querySelector('.deck');
  if(deck){
    new MutationObserver(()=>reveal(document.querySelector('.deck-panel.is-active .panel-inner'),true)).observe(document.body,{attributes:true,attributeFilter:['data-section']});
    const research=document.querySelector('#research');
    if(research)new MutationObserver(()=>{if(document.body.dataset.section==='findings')reveal(document.querySelector('#plot'));}).observe(research,{childList:true});
  }else{
    new MutationObserver(()=>reveal(document.querySelector('#stage>section,#stage>article')||document.querySelector('#stage'))).observe(document.querySelector('#stage'),{childList:true});
  }
  const diagnostics={settle:cancel,inspect:()=>({running:active.size,played,sectionTransitions})};
  if(deck)window.LensMotionUI=diagnostics;else window.LensSiteUI=diagnostics;
})();
