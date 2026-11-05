/* Shared live scene: the five link nodes and the intro's actual optical SVG survive handoff. */
(() => {
  'use strict';
  const root=document.querySelector('#gateway');if(!root)return;
  const $=(s,r=document)=>r.querySelector(s),slots=[...root.querySelectorAll('.gate-slot')];
  const orbs=slots.map(s=>s.querySelector('.gate-orb')),center=$('#gate-center'),art=$('#gate-lens-art');
  const preference=matchMedia('(prefers-reduced-motion: reduce)');
  const clamp=x=>Math.max(0,Math.min(1,x)),ramp=(t,a,b)=>clamp((t-a)/(b-a)),ease=x=>x*x*(3-2*x),mix=(a,b,p)=>a+(b-a)*p;
  let idle=[],borrowed=false,targets=[],introRoot=null,optics=null,lensTarget=null,sceneActive=false,busy=false,epoch=0,flight=null;
  let transferCount=0,lastTransfer=null,lastNavigation=null,driver='none';
  const phase=(name)=>{root.dataset.gatewayPhase=name;};
  const active=()=>document.body.dataset.section==='gateway';
  const cancelIdle=()=>{idle.forEach(a=>a.cancel());idle=[];root.classList.remove('gateway-ready');};
  function animate(el,keyframes,options={}){
    if(window.LensMotion?.animate){driver='motion-mini';return LensMotion.animate(el,keyframes,options);}
    driver='web-animations';return el.animate(keyframes,{duration:(options.duration||.5)*1000,easing:'ease-in-out',iterations:options.repeat===Infinity?Infinity:1,direction:options.repeatType==='reverse'?'alternate':'normal',fill:'both'});
  }
  function sync(){
    cancelIdle();
    if(!active()||document.hidden||preference.matches||borrowed||busy||document.documentElement.matches('.intro-active,.intro-pending'))return;
    root.classList.add('gateway-ready');phase('idle');
    slots.forEach((slot,i)=>{
      if(innerWidth<700){idle.push(animate(orbs[i].querySelector('.orb-rim'),{opacity:[.6,1,.6]},{duration:7+i,repeat:Infinity,ease:'easeInOut'}));return;}
      const sign=i%2?-1:1;
      idle.push(animate(slot,{transform:[`translate3d(0,0,0) rotate(0deg)`,`translate3d(${sign*6}px,-7px,0) rotate(.35deg)`,`translate3d(0,-14px,0) rotate(0deg)`,`translate3d(${-sign*6}px,-7px,0) rotate(-.35deg)`,`translate3d(0,0,0) rotate(0deg)`]},{duration:20+i*3,repeat:Infinity,ease:'linear'}));
    });
  }
  function restoreOrb(i){
    const orb=orbs[i];slots[i].append(orb);orb.classList.remove('in-transit','is-seed');orb.removeAttribute('style');orb.inert=false;
  }
  function restoreAll(){orbs.forEach((_,i)=>restoreOrb(i));borrowed=false;targets=[];}
  function adoptLens(){
    if(!optics)return;
    // Skipping at any frame still leaves a fully formed, usable home lens.
    optics.querySelectorAll('.intro-ring,.intro-arc').forEach(el=>{el.style.strokeDasharray='1';el.style.strokeDashoffset='0';});
    const ticks=$('.intro-ticks',optics);if(ticks)ticks.style.opacity='1';
    optics.removeAttribute('style');optics.classList.add('gate-shared-optic');art.append(optics);
  }
  function prepareIntro(container){
    // Replays reuse the very same LensScene and its 96 ticks, never append a second lens.
    cancelNavigation();cancelIdle();introRoot=container;
    if(optics){optics.classList.remove('gate-shared-optic');optics.removeAttribute('style');container.append(optics);}
    sceneActive=active()&&(!location.hash||location.hash==='#gateway');if(sceneActive)root.scrollTop=0;root.classList.toggle('gateway-handoff',sceneActive);phase(sceneActive?'intro':'idle');
  }
  function beginIntro(container){
    introRoot=container;optics=$('.intro-optics',container);sceneActive=active()&&(!location.hash||location.hash==='#gateway');
    if(!sceneActive)return;
    cancelIdle();
    lensTarget=art.getBoundingClientRect();
    targets=slots.map((slot,i)=>{
      const rect=orbs[i].getBoundingClientRect();return{x:rect.x+rect.width/2,y:rect.y+rect.height/2,w:rect.width,h:rect.height};
    });
    orbs.forEach((orb,i)=>{
      const r=targets[i],tone=getComputedStyle(orb).getPropertyValue('--tone');container.append(orb);orb.style.setProperty('--tone',tone);orb.classList.add('in-transit','is-seed');orb.inert=true;
      Object.assign(orb.style,{position:'fixed',width:r.w+'px',height:r.h+'px',left:'50%',top:'43%',opacity:'0',transform:'translate(-50%,-50%) scale(.025)'});
    });borrowed=true;
  }
  function drawIntro(t,size){
    if(!sceneActive||!borrowed)return;
    const p=ease(ramp(t,5.06,5.95)),gather=ease(ramp(t,3.35,4.08));
    const source={x:innerWidth*.5,y:innerHeight*.43};
    orbs.forEach((orb,i)=>{
      const a=(-90+i*72)*Math.PI/180;
      const small={x:source.x+Math.cos(a)*size*.34,y:source.y+Math.sin(a)*size*.34};
      const initial={x:innerWidth*(.08+(i+.5)*.84/5),y:innerHeight*.65};
      const start={x:mix(initial.x,small.x,gather),y:mix(initial.y,small.y,gather)};
      const target=targets[i],x=mix(start.x,target.x,p),y=mix(start.y,target.y,p);
      orb.style.left=x+'px';orb.style.top=y+'px';orb.style.opacity=String(ramp(t,3.12+i*.055,3.46+i*.055));
      orb.style.transform=`translate(-50%,-50%) scale(${mix(.035,1,p)})`;
      orb.classList.toggle('is-seed',t<5.45+i*.045);
    });
    if(t>=5.06){
      const x=mix(source.x,lensTarget.x+lensTarget.width/2,p),y=mix(source.y,lensTarget.y+lensTarget.height/2,p),w=mix(size,lensTarget.width,p);
      Object.assign(optics.style,{position:'fixed',left:x+'px',top:y+'px',width:w+'px',height:w+'px',opacity:String(mix(.12,1,ramp(t,5.06,5.6))),transform:`translate(-50%,-50%) rotateZ(${mix(-12,0,p)}deg)`});
      // Shift the existing optic gently from the intro's copper to the portal's ice blue.
      const a=[223,161,124],b=[140,219,223];introRoot.style.setProperty('--intro-accent','#'+a.map((v,i)=>Math.round(mix(v,b[i],p)).toString(16).padStart(2,'0')).join(''));
      phase('forming');
    }
  }
  function endIntro(reason){
    if(borrowed){
      lastTransfer={reason,links:orbs.map((a,i)=>({id:a.id,sameNode:a===slots[i].ownerDocument.getElementById(a.id)})),sharedLens:!!optics,targets};
      transferCount++;restoreAll();
    }
    adoptLens();root.classList.remove('gateway-handoff');introRoot?.style.removeProperty('--intro-accent');sceneActive=false;
    phase(active()?'idle':'away');
  }
  function cancelNavigation(){
    epoch++;busy=false;root.removeAttribute('aria-busy');
    if(flight){flight.controls.forEach(a=>a.cancel());restoreOrb(flight.index);flight.layer.remove();flight=null;}
    $('.gate-focus-flash',root)?.removeAttribute('style');
  }
  function navigate(orb){
    if(busy)return;
    if(typeof window.LENS_GO_TO!=='function'){location.hash=orb.dataset.gateRoute;return;}
    const route=orb.dataset.gateRoute,index=orbs.indexOf(orb);
    const go=()=>{
      cancelNavigation();window.LENS_GO_TO(route);
      const heading=$('#'+route+' h1,#'+route+' h2');if(heading){heading.tabIndex=-1;heading.focus({preventScroll:true});}
      lastNavigation={route,href:location.hash,driver};phase('away');
    };
    if(preference.matches){go();return;}
    const r=orb.getBoundingClientRect(),c=center.getBoundingClientRect();cancelIdle();busy=true;root.setAttribute('aria-busy','true');phase('entering');
    $('#gate-status').textContent='正在进入'+$('.orb-title',orb).textContent;
    const tone=getComputedStyle(orb).getPropertyValue('--tone');
    const token=++epoch,layer=document.createElement('div');layer.className='gate-flight-layer';document.body.append(layer);layer.append(orb);orb.style.setProperty('--tone',tone);orb.style.removeProperty('scale');
    orb.classList.add('in-transit');Object.assign(orb.style,{position:'fixed',left:r.x+'px',top:r.y+'px',width:r.width+'px',height:r.height+'px',transform:'none'});
    const dx=c.x+c.width/2-r.x-r.width/2,dy=c.y+c.height/2-r.y-r.height/2;
    const control=animate(orb,{transform:['translate3d(0,0,0) scale(1)',`translate3d(${dx}px,${dy}px,0) scale(.16)`],opacity:[1,.25]},{duration:.66,ease:[.22,1,.36,1]});
    const flash=animate($('.gate-focus-flash'),{opacity:[0,.8,0],transform:['scale(.4)','scale(1.8)']},{duration:.76,ease:'easeOut'});
    flight={index,layer,controls:[control,flash]};
    // Route activation follows the actual Motion completion. A bounded fallback also works if a library promise fails.
    const done=Promise.race([Promise.resolve(control),new Promise(resolve=>setTimeout(resolve,950))]);
    done.then(()=>{if(token===epoch)go();},()=>{if(token===epoch)go();});
  }
  orbs.forEach(orb=>{
    // Static generated glass travels inside the original accessible link node.
    // Native CSS/SVG glass remains the fallback until the real alpha image decodes.
    const planet=orb.querySelector('.orb-planet');
    if(planet){
      const ready=()=>{if(planet.naturalWidth>0)planet.decode().then(()=>orb.classList.add('planet-ready'),()=>{});};
      planet.addEventListener('load',ready,{once:true});
      planet.addEventListener('error',()=>orb.classList.remove('planet-ready'));
      if(planet.complete)ready();
    }
    orb.addEventListener('click',event=>{if(event.defaultPrevented||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;event.preventDefault();navigate(orb);});
    const highlight=()=>{if(!borrowed&&!busy&&!preference.matches){idle[orbs.indexOf(orb)]?.pause();orb.style.scale='1.055';}};
    const clear=()=>{orb.style.removeProperty('scale');if(orb!==document.activeElement&&active()&&!busy&&!borrowed)idle[orbs.indexOf(orb)]?.play();};
    orb.addEventListener('pointerenter',highlight);orb.addEventListener('pointerleave',clear);orb.addEventListener('focus',highlight);orb.addEventListener('blur',clear);
    orb.addEventListener('keydown',event=>{
      const key=event.key;if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].includes(key))return;
      event.preventDefault();const i=orbs.indexOf(orb),next=key==='Home'?0:key==='End'?4:(i+(['ArrowLeft','ArrowUp'].includes(key)?4:1))%5;orbs[next].focus();
    });
  });
  // Deterministic, non-data decorative particles. CSS animates this single SVG group.
  const particles=$('.field-particles',root);for(let i=0;i<38;i++){
    const circle=document.createElementNS('http://www.w3.org/2000/svg','circle');circle.setAttribute('cx',String((i*373+137)%1440));circle.setAttribute('cy',String((i*211+53)%900));circle.setAttribute('r',i%7===0?'1.5':'.8');circle.setAttribute('opacity',String(.2+(i%5)*.12));particles.append(circle);
  }
  new MutationObserver(()=>{if(!active())cancelNavigation();sync();}).observe(document.body,{attributes:true,attributeFilter:['data-section']});
  new MutationObserver(sync).observe(document.documentElement,{attributes:true,attributeFilter:['class']});
  document.addEventListener('lens:intro-finished',sync);
  document.addEventListener('visibilitychange',()=>{if(document.hidden&&busy)cancelNavigation();sync();});
  preference.addEventListener('change',()=>{if(busy)cancelNavigation();sync();});
  addEventListener('resize',()=>{
    if(busy)cancelNavigation();sync();
    if(borrowed){
      lensTarget=art.getBoundingClientRect();
      targets=slots.map(slot=>{const r=slot.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2,w:r.width,h:r.height};});
      orbs.forEach((orb,i)=>{orb.style.width=targets[i].w+'px';orb.style.height=targets[i].h+'px';});
    }
  },{passive:true});
  addEventListener('pagehide',()=>{cancelNavigation();cancelIdle();});
  addEventListener('pageshow',sync);
  window.LensGateway={active,prepareIntro,beginIntro,drawIntro,endIntro,inspect:()=>({active:active(),borrowed,busy,phase:root.dataset.gatewayPhase,idleAnimations:idle.length,driver,transferCount,lastTransfer,lastNavigation,sharedLens:!!art.querySelector('.gate-shared-optic'),links:orbs.map((a,i)=>({route:a.dataset.gateRoute,inSlot:a.parentElement===slots[i]}))})};
  sync();
})();
