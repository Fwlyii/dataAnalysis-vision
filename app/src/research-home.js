const CHAPTERS = [
  {id:'question',title:'研究问题',caption:'从一个问题出发',planet:'question',icon:'<circle cx="12" cy="12" r="8"/><path d="M9.5 9a2.6 2.6 0 1 1 4.1 2.1c-1.2.7-1.6 1.1-1.6 2.4M12 17h.01"/>'},
  {id:'collection',title:'采集设计',caption:'让对照有据可依',planet:'collection',icon:'<path d="M5 6h14M5 12h14M5 18h14M9 3v6m6 0v6m-6 0v6"/>'},
  {id:'cleaning',title:'数据处理',caption:'把来源连成证据',planet:'cleaning',icon:'<path d="M3 5h6v5H3zm12 9h6v5h-6zM6 10v6h9M15 5h6M18 2v6"/>'},
  {id:'findings',title:'核心发现',caption:'让行为规律显现',planet:'landscape',icon:'<path d="M4 3v17h17M8 15l4-6 4 3 5-7"/><circle cx="12" cy="9" r="1"/><circle cx="16" cy="12" r="1"/>'},
  {id:'conclusion',title:'总结与反思',caption:'回到研究的起点',planet:'findings',icon:'<circle cx="12" cy="11" r="7"/><circle cx="12" cy="11" r="3"/><path d="m17 16 4 5M12 1v2M2 11h2"/>'},
];

/** The original five-orb portal, isolated from the old deck and intro globals. */
export function renderHome(){
  return `<section class="research-home" aria-labelledby="home-title">
    <div class="rh-atmosphere" aria-hidden="true"><img data-home-background src="assets/visual/ocean-optics-v5.png" data-fallback="assets/visual/gateway-atmosphere.webp" alt="" decoding="async" fetchpriority="high"/><svg viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice"><g class="rh-tracks"><ellipse cx="720" cy="460" rx="640" ry="245" transform="rotate(-22 720 460)"/><ellipse cx="720" cy="460" rx="680" ry="280" transform="rotate(25 720 460)"/></g></svg></div>
    <div class="rh-stage">
      <header class="rh-heading"><p>知微之门</p><span>提示、证据与反馈，如何改变模型的回答？</span></header>
      <svg class="rh-orbits" viewBox="0 0 1000 700" aria-hidden="true"><ellipse cx="500" cy="350" rx="480" ry="255" transform="rotate(-18 500 350)"/><ellipse cx="500" cy="350" rx="410" ry="325" transform="rotate(24 500 350)"/></svg>
      <div class="rh-center"><div class="rh-lens" aria-hidden="true"><svg viewBox="0 0 600 600"><circle cx="300" cy="300" r="270" stroke-dasharray="1 14"/><circle cx="300" cy="300" r="245"/><circle cx="300" cy="300" r="232" opacity=".4"/><path d="M110 180a245 245 0 0 1 315-94M490 420a245 245 0 0 1-315 94"/><path d="M300 25v20m0 510v20M25 300h20m510 0h20"/></svg></div><div class="rh-brand"><h1 id="home-title" class="rh-chinese-name">知微</h1><span class="rh-brand-caption">模型行为研究</span></div></div>
      <nav class="rh-navigation" aria-label="五个研究章节">${CHAPTERS.map((chapter,i)=>`<a class="rh-orb rh-orb-${i}" href="?chapter=${chapter.id}" data-home-chapter="${chapter.id}" aria-label="${chapter.title}"><img class="rh-planet" src="assets/visual/planet-${chapter.planet}.webp" width="512" height="512" alt="" decoding="async"/><svg class="rh-rim" viewBox="0 0 160 160" aria-hidden="true"><circle cx="80" cy="80" r="77"/><path d="M23 49a65 65 0 0 1 68-33"/></svg><svg class="rh-orb-icon" viewBox="0 0 24 24" aria-hidden="true">${chapter.icon}</svg><span class="rh-orb-number" aria-hidden="true">${String(i+1).padStart(2,'0')}</span><span class="rh-orb-label">${chapter.title}</span><span class="rh-orb-caption">${chapter.caption}</span></a>`).join('')}</nav>
      <p class="rh-foot">由问题出发，循证据知微。</p>
    </div>
  </section>`;
}

export function mountHome(container,{onNavigate}={}){
  const home=container.matches?.('.research-home')?container:container.querySelector('.research-home');
  if(!home)return ()=>{};
  const links=[...home.querySelectorAll('[data-home-chapter]')];
  const background=home.querySelector('[data-home-background]');
  const fallbackBackground=()=>{
    if(background?.dataset.fallback){background.src=background.dataset.fallback;delete background.dataset.fallback;}
  };
  background?.addEventListener('error',fallbackBackground,{once:true});
  if(background?.complete&&!background.naturalWidth)fallbackBackground();
  const click=event=>{
    const link=event.target.closest('[data-home-chapter]');
    if(!link||!home.contains(link)||event.defaultPrevented||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
    if(typeof onNavigate==='function'){event.preventDefault();onNavigate(link.dataset.homeChapter);}
  };
  const keydown=event=>{
    const link=event.target.closest('[data-home-chapter]');
    if(!link||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].includes(event.key))return;
    event.preventDefault();
    const index=links.indexOf(link),next=event.key==='Home'?0:event.key==='End'?links.length-1:(index+(['ArrowLeft','ArrowUp'].includes(event.key)?links.length-1:1))%links.length;
    links[next].focus();
  };
  home.addEventListener('click',click);home.addEventListener('keydown',keydown);
  return ()=>{home.removeEventListener('click',click);home.removeEventListener('keydown',keydown);background?.removeEventListener('error',fallbackBackground);};
}
