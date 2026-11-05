/* LENS · 知微. All imagery is calculated live; no video, image sequence or scene bitmap. */
(() => {
  'use strict';
  const DURATION = 5950, SEEN = 'lens.intro.seen.v1', SEED = 0x4c454e53;
  const clamp = x => Math.max(0, Math.min(1, x));
  const ramp = (t, a, b) => clamp((t - a) / (b - a));
  const smooth = x => { x = clamp(x); return x * x * (3 - 2 * x); };
  const out = x => 1 - (1 - clamp(x)) ** 3;
  const mix = (a, b, x) => a + (b - a) * x;
  function random(seed) { return () => { seed |= 0; seed = seed + 0x6d2b79f5 | 0; let x = Math.imul(seed ^ seed >>> 15, 1 | seed); x ^= x + Math.imul(x ^ x >>> 7, 61 | x); return ((x ^ x >>> 14) >>> 0) / 4294967296; }; }
  const bezier = (a, b, c, d, p) => (1-p)**3*a + 3*(1-p)**2*p*b + 3*(1-p)*p*p*c + p**3*d;
  const svgNS = 'http://www.w3.org/2000/svg';
  const $ = (selector, root = document) => root.querySelector(selector);
  // The page frame and live intro share the same reviewed CSS palette.
  const paletteStyle=getComputedStyle(document.documentElement);
  const token=(name,fallback)=>paletteStyle.getPropertyValue(name).trim()||fallback;
  const rgb=hex=>[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)).join(',');
  const theme={bg:rgb(token('--intro-bg','#071e30')),ink:token('--intro-ink','#f4f1e9'),ice:rgb(token('--intro-ice','#f2dcc7')),accent:rgb(token('--intro-accent','#dfa17c')),muted:rgb(token('--intro-muted','#a9bdc9'))};


  function sceneMarkup() {
    const symbols = [
      ['简洁作答','<path d="M13 9h66M13 19h54M13 29h36M13 39h24"/><path d="m69 27 7 7 14-17" stroke="var(--intro-accent)"/>'],
      ['中文数学','<path d="M16 15h27M29 9v29M17 28l12-13 13 13M58 12l23 23M81 12 58 35M58 39h25"/>'],
      ['限长反弹','<path d="m11 33 16-6 16 3 15-19 15 4 15-9"/><path d="M11 43h77M11 7v36" opacity=".4"/>'],
      ['资料位置','<path d="M13 13h74M13 26h74M13 39h74" opacity=".4"/><circle cx="29" cy="13" r="4"/><circle cx="50" cy="26" r="4"/><circle cx="72" cy="39" r="4"/>'],
      ['反馈修复','<path d="m25 13-11 13 11 13m50-26 11 13-11 13M56 9 44 42"/><path d="m78 5 8 0 0 8" stroke="var(--intro-accent)"/>']
    ];
    return `<div class="intro-atmosphere"><canvas class="intro-canvas" aria-hidden="true"></canvas></div>
      <div class="intro-optics" aria-hidden="true"><svg viewBox="0 0 600 600">
        <defs><radialGradient id="intro-glass"><stop offset="0" stop-color="var(--intro-ice)" stop-opacity=".02"/><stop offset=".8" stop-color="var(--intro-accent)" stop-opacity=".03"/><stop offset="1" stop-color="var(--intro-ice)" stop-opacity=".12"/></radialGradient></defs>
        <circle cx="300" cy="300" r="222" fill="url(#intro-glass)" stroke="var(--intro-accent)" stroke-opacity=".12"/>
        <g class="intro-ticks"></g>
        <circle class="intro-ring fine" cx="300" cy="300" r="270" pathLength="1"/>
        <circle class="intro-ring" cx="300" cy="300" r="245" pathLength="1"/>
        <circle class="intro-ring fine" cx="300" cy="300" r="232" pathLength="1"/>
        <circle class="intro-ring" cx="300" cy="300" r="218" pathLength="1"/>
        <circle class="intro-ring fine" cx="300" cy="300" r="184" pathLength="1"/>
        <g class="intro-arcs"><path class="intro-arc" d="M65 300a235 235 0 0 1 161-223" pathLength="1"/><path class="intro-arc" d="M535 300a235 235 0 0 1-161 223" pathLength="1"/><path class="intro-arc" d="M162 439a196 196 0 0 1-51-101" pathLength="1"/></g>
        <path d="M282 300h12m12 0h12m-18-18v12m0 12v12" stroke="var(--intro-ice)" stroke-width=".7" opacity=".55"/>
        <line class="intro-scan" x1="116" x2="484" y1="300" y2="300" stroke="var(--intro-accent)" stroke-width=".8" opacity=".2"/>
      </svg></div>
      <div class="intro-signals" aria-hidden="true">${symbols.map(([label, drawing]) => `<div class="intro-signal"><svg viewBox="0 0 100 52">${drawing}</svg><span>${label}</span></div>`).join('')}</div>
      <div class="intro-titles" aria-hidden="true"><span class="intro-mark">LENS<span class="intro-period">.</span></span><span class="intro-name">知微</span><span class="intro-subtitle">大模型行为洞察与可视交互分析系统</span><span class="intro-tagline">从数据中，发现智能的行为规律。</span></div>
      <h2 class="intro-sr" id="intro-accessible-title">LENS · 知微开场</h2><p class="intro-sr">大模型行为洞察与可视交互分析系统。可随时跳过进入系统。</p>
      <button class="intro-skip" type="button">跳过片头<svg viewBox="0 0 14 14" aria-hidden="true"><path d="m3 2 5 5-5 5m7-10v10"/></svg></button>
      <div class="intro-progress" aria-hidden="true"><i></i></div>`;
  }

  class ParticleSystem {
    constructor(canvas) {
      this.canvas = canvas; this.ctx = canvas.getContext('2d', {alpha: true});
      if (!this.ctx) throw new Error('Canvas 2D unavailable');
      this.lastPoints = []; this.resize();
    }
    resize() {
      this.w = innerWidth; this.h = innerHeight; this.small = this.w <= 560;
      const budget = this.small ? 750000 : 2000000;
      this.dpr = Math.min(devicePixelRatio || 1, this.small ? 1.5 : 1.75, Math.sqrt(budget / (this.w * this.h)));
      this.canvas.width = Math.round(this.w * this.dpr); this.canvas.height = Math.round(this.h * this.dpr);
      this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
      this.cx = this.w * .5; this.cy = this.h * .43;
      this.size = Math.min(Math.min(this.w, this.h) * .68, 440);
      const rng = random(SEED);
      this.particles = Array.from({length: this.small ? 92 : 176}, (_, i) => ({
        x: (rng() * 2 - 1) * this.w * .85, y: (rng() * 2 - 1) * this.h * .65,
        z: .3 + rng() * 2.7, side: i % 2 ? -1 : 1, angle: i / (this.small ? 92 : 176) * Math.PI * 2,
        phase: rng() * Math.PI * 2, size: .45 + rng() * 1.35, delay: rng() * .32
      }));
      this.count = this.particles.length;
      this.signature = JSON.stringify(this.particles.slice(0, 3));
    }
    point(p, t) {
      const driftX = p.x + Math.sin(t * .33 + p.phase) * 24 * p.z;
      const driftY = p.y + Math.cos(t * .25 + p.phase) * 13 * p.z;
      const k = 1 / (.8 + p.z * .42);
      const startX = this.cx + driftX * k, startY = this.cy + driftY * k;
      const turn = p.angle + Math.min(t, 3) * .04;
      const endX = this.cx + Math.cos(turn) * this.size * .365;
      const endY = this.cy + Math.sin(turn) * this.size * .365 * .95;
      const flow = smooth(ramp(t, .72 + p.delay, 2.65 + p.delay * .4));
      const x = bezier(startX, this.cx + p.side * this.w * .40, this.cx - p.side * this.size * .13, endX, flow);
      const y = bezier(startY, this.cy + Math.sin(p.phase) * this.h * .42, this.cy - Math.cos(p.phase) * this.size * .7, endY, flow);
      const collapse = smooth(ramp(t, 3.45, 4.15));
      return {x: mix(x, this.cx, collapse), y: mix(y, this.cy, collapse), depth: k};
    }
    draw(t) {
      const c = this.ctx, wake = smooth(ramp(t, 0, .8));
      c.clearRect(0, 0, this.w, this.h);
      c.fillStyle = `rgba(${theme.bg},${(1-wake)*.96})`; c.fillRect(0, 0, this.w, this.h);
      const grid = smooth(ramp(t, .3, 1.5)) * (1 - ramp(t, 4.5, 5.2));
      c.strokeStyle = `rgba(${theme.muted},${grid*.10})`; c.lineWidth = .6;
      c.beginPath();
      for (let i = -6; i <= 6; i++) { c.moveTo(this.cx + i * 16, this.cy); c.lineTo(this.cx + i * this.w * .22, this.h); }
      for (let i = 1; i <= 8; i++) { const y = this.cy + (i/8)**2 * (this.h-this.cy); c.moveTo(0,y); c.lineTo(this.w,y); }
      c.stroke();
      // Revealed portions of the same cubic flow field make the two streams legible.
      const streams=Math.sin(ramp(t,.82,3.12)*Math.PI);
      if(streams>0) for(const side of [-1,1]) for(let lane=0;lane<4;lane++) {
        const tip=smooth(ramp(t,.82+lane*.09,2.62+lane*.05));
        const a=[this.cx+side*this.w*.62,this.cy+(lane-1.5)*this.h*.22];
        const b=[this.cx+side*this.w*.28,this.cy+(lane%2?1:-1)*this.size*.7];
        const d=[this.cx+side*Math.cos((lane-1.5)*.48)*this.size*.365,this.cy+Math.sin((lane-1.5)*.48)*this.size*.365];
        const e=[this.cx-side*this.size*.12,this.cy+(lane-1.5)*this.size*.32];
        c.strokeStyle=`rgba(${theme.accent},${streams*.13})`;c.lineWidth=.65;c.beginPath();
        for(let step=0;step<=28;step++){const u=tip*step/28,x=bezier(a[0],b[0],e[0],d[0],u),y=bezier(a[1],b[1],e[1],d[1],u);if(!step)c.moveTo(x,y);else c.lineTo(x,y);}
        c.stroke();
      }
      const points = [], visibility = (.2 + wake*.8) * (1 - smooth(ramp(t, 4.05, 4.7)));
      for (let i = 0; i < this.count; i++) {
        const p = this.particles[i], q = this.point(p,t), radius = p.size * q.depth;
        const alpha = Math.min(.85, (.22 + q.depth*.42) * visibility);
        if (t > .75 && t < 3.65) {
          const tail = this.point(p, Math.max(0,t-.065));
          c.strokeStyle = `rgba(${theme.accent},${alpha*.5})`; c.lineWidth = Math.max(.35,radius*.4);
          c.beginPath(); c.moveTo(tail.x,tail.y); c.lineTo(q.x,q.y); c.stroke();
        }
        if (i % 8 === 0) {
          const glow = c.createRadialGradient(q.x,q.y,0,q.x,q.y,radius*9);
          glow.addColorStop(0,`rgba(${theme.accent},${alpha*.24})`); glow.addColorStop(1,`rgba(${theme.accent},0)`);
          c.fillStyle = glow; c.fillRect(q.x-radius*9,q.y-radius*9,radius*18,radius*18);
        }
        c.fillStyle = `rgba(${i%3===0?theme.ice:theme.accent},${alpha})`;
        c.beginPath(); c.arc(q.x,q.y,Math.max(.4,radius),0,Math.PI*2); c.fill();
        points.push(q);
      }
      const network = Math.sin(ramp(t,1.1,3.0)*Math.PI) * .16;
      c.strokeStyle = `rgba(${theme.muted},${network})`; c.lineWidth = .5; c.beginPath();
      for (let i=0;i<points.length-1;i+=4) {
        const a=points[i],b=points[i+1]; if (Math.hypot(a.x-b.x,a.y-b.y)>this.size*.3) continue;
        c.moveTo(a.x,a.y);c.lineTo(b.x,b.y);
      }
      c.stroke(); this.lastPoints = points.slice(0,3).map(p=>({x:+p.x.toFixed(2),y:+p.y.toFixed(2)}));
      const focus = Math.sin(ramp(t,2.45,3.35)*Math.PI)*.35 + Math.sin(ramp(t,3.8,4.5)*Math.PI)*.22;
      if (focus>0) {
        const glow=c.createRadialGradient(this.cx,this.cy,0,this.cx,this.cy,this.size*.55);
        glow.addColorStop(0,`rgba(${theme.ice},${focus})`);glow.addColorStop(.08,`rgba(${theme.accent},${focus*.42})`);glow.addColorStop(1,`rgba(${theme.accent},0)`);
        c.fillStyle=glow;c.fillRect(this.cx-this.size,this.cy-this.size,this.size*2,this.size*2);
      }
      const beam=Math.sin(ramp(t,2.67,3.34)*Math.PI);
      if (beam>0) {
        c.save();c.translate(this.cx,this.cy);c.rotate(-.12);
        const length=this.w*.6, g=c.createLinearGradient(-length,0,length,0);
        g.addColorStop(0,`rgba(${theme.accent},0)`);g.addColorStop(.5,`rgba(${theme.ice},${beam*.65})`);g.addColorStop(1,`rgba(${theme.accent},0)`);
        c.strokeStyle=g;c.lineWidth=1;c.beginPath();c.moveTo(-length,0);c.lineTo(length,0);c.stroke();c.restore();
      }
    }
    clear() { this.ctx.clearRect(0,0,this.w,this.h); }
  }

  class LensScene {
    constructor(root) {
      this.root=$('.intro-optics',root);this.rings=[...root.querySelectorAll('.intro-ring,.intro-arc')];
      this.arcs=$('.intro-arcs',root);this.ticks=$('.intro-ticks',root);this.scan=$('.intro-scan',root);
      for(let i=0;i<96;i++) {
        const a=i/96*Math.PI*2,r1=i%8===0?253:258,r2=265;
        const line=document.createElementNS(svgNS,'line');line.classList.add('intro-tick');
        for(const [key,value] of Object.entries({x1:300+Math.cos(a)*r1,y1:300+Math.sin(a)*r1,x2:300+Math.cos(a)*r2,y2:300+Math.sin(a)*r2}))line.setAttribute(key,value.toFixed(2));
        this.ticks.append(line);
      }
    }
    draw(t,zoom=1) {
      const form=out(ramp(t,1.55,2.95)),brand=smooth(ramp(t,3.8,4.35)),flight=ramp(t,5.06,5.9);
      this.root.style.opacity=(form*(1-brand*.88)*(1-flight)+Math.sin(flight*Math.PI)*.8)*(1-ramp(t,5.72,5.94));
      this.root.style.transform=`translate(-50%,-50%) perspective(1100px) rotateX(${12*(1-flight)}deg) rotateY(${-14*(1-flight)}deg) rotateZ(${-12+flight*12}deg) scale(${zoom})`;
      this.rings.forEach((ring,i)=>{const p=out(ramp(t,1.55+i*.075,2.48+i*.06));ring.style.strokeDasharray='1';ring.style.strokeDashoffset=1-p;});
      this.ticks.style.opacity=out(ramp(t,1.95,2.85));
      this.arcs.setAttribute('transform',`rotate(${mix(-32,12,out(ramp(t,1.8,3)))},300,300)`);
      this.scan.setAttribute('transform',`translate(0,${mix(-165,165,ramp(t,2.3,3.1))})`);
    }
  }

  class TitleReveal {
    constructor(root) { this.word=$('.intro-mark',root);this.name=$('.intro-name',root);this.subtitle=$('.intro-subtitle',root);this.tagline=$('.intro-tagline',root); }
    reset() { this.word.removeAttribute('style'); }
    draw(t,flight) {
      const p=out(ramp(t,3.98,4.34));
      if(!flight) { this.word.style.opacity=p;this.word.style.clipPath=`inset(0 ${(1-p)*100}% 0 0)`;this.word.style.transform=`translateY(${(1-p)*12}px)`;this.word.style.letterSpacing=`${mix(.035,-.055,p)}em`; }
      for(const [el,a,b] of [[this.name,4.15,4.52],[this.subtitle,4.35,4.7],[this.tagline,4.52,4.85]]) {
        const k=out(ramp(t,a,b));el.style.opacity=k*(1-smooth(ramp(t,5,5.25)));el.style.transform=`translateY(${(1-k)*9}px)`;
      }
    }
  }

  class PageTransition {
    constructor(root,word) { this.root=root;this.word=word;this.atmosphere=$('.intro-atmosphere',root);this.reset(); }
    reset() { this.first=null;this.last=null;this.targets=[];this.saved=[];this.controls=[];this.landing=null;this.driver='native-timeline';this.atmosphere.style.maskImage='';this.atmosphere.style.webkitMaskImage=''; }
    prepare() {
      this.gateway=window.LensGateway?.active()||false;
      const target=$(this.gateway?'.gate-brand-mark':'.research-home-mark');if(!target)throw new Error('Header brand unavailable');
      this.first=this.word.getBoundingClientRect();this.last=target.getBoundingClientRect();
      this.finalInk=getComputedStyle(target).color.match(/[\d.]+/g).slice(0,3).map(Number);
      if(!this.first.width||!this.last.width)throw new Error('Brand geometry unavailable');
      this.landing=$(this.gateway?'#gate-brand':'#research-home-label');this.landing.classList.add('intro-target-hidden');
      this.saved.push([this.word,this.word.getAttribute('style')]);
      Object.assign(this.word.style,{position:'fixed',left:'0',top:'0',transformOrigin:'0 0',clipPath:'none',opacity:'1',letterSpacing:'-.055em'});
      this.targets=[...document.querySelectorAll(this.gateway?'.topbar,.gate-heading,.gate-foot':'.chapter-rail,.deck-panel.is-active .panel-inner')].filter(el=>el.getClientRects().length);
      for(const el of this.targets){
        this.saved.push([el,el.getAttribute('style')]);el.classList.add('intro-arrival');
        if(window.LensMotion?.animate){this.controls.push(window.LensMotion.animate(el,{opacity:[0,1],transform:['translateY(10px)','translateY(0px)']},{duration:1,autoplay:false,ease:[.16,1,.3,1]}));this.driver='motion-mini';}
      }
    }
    draw(t,size) {
      if(t<5.06)return 1;
      if(!this.first)this.prepare();
      const p=ramp(t,5.06,5.93),base=size*.365,reach=Math.hypot(innerWidth,innerHeight)*1.05;
      const radius=p<.25?base*out(p/.25):mix(base,reach,((p-.25)/.75)**2.5);
      const mask=`radial-gradient(circle at 50% 43%,transparent ${Math.max(0,radius-2)}px,#000 ${radius+2}px)`;
      this.atmosphere.style.maskImage=mask;this.atmosphere.style.webkitMaskImage=mask;
      const k=smooth(ramp(t,5.12,5.82)),x=mix(this.first.left,this.last.left,k),y=mix(this.first.top,this.last.top,k);
      const scale=mix(1,this.last.width/this.first.width,k);
      this.word.style.transform=`translate3d(${x}px,${y}px,0) scale(${scale})`;
      const tone=ramp(t,5.35,5.84),start=[1,3,5].map(i=>parseInt(theme.ink.slice(i,i+2),16));
      this.word.style.color=`rgb(${start.map((v,i)=>Math.round(mix(v,this.finalInk[i],tone))).join(',')})`;
      this.word.style.opacity=1-ramp(t,5.84,5.94);
      if(t>=5.84)this.landing.classList.remove('intro-target-hidden');
      this.targets.forEach((el,i)=>{const p=ramp(t,5.28+i*.075,5.75+i*.055);if(this.controls[i])this.controls[i].time=p;else{const a=out(p);el.style.opacity=a;el.style.transform=`translateY(${(1-a)*10}px)`;}});
      return this.gateway?1:Math.max(1,radius/base);
    }
    clean() { this.controls.forEach(control=>control.cancel());this.landing?.classList.remove('intro-target-hidden');for(const [el,style] of this.saved){if(style===null)el.removeAttribute('style');else el.setAttribute('style',style);el.classList.remove('intro-arrival');}this.reset(); }
  }

  class IntroController {
    constructor() {
      this.root=document.createElement('section');this.root.id='lens-intro';this.root.hidden=true;
      this.root.setAttribute('role','dialog');this.root.setAttribute('aria-modal','true');this.root.setAttribute('aria-labelledby','intro-accessible-title');this.root.tabIndex=-1;
      this.root.innerHTML=sceneMarkup();document.body.append(this.root);
      this.particles=null;this.lens=null;this.title=null;this.transition=null;
      this.preference=matchMedia('(prefers-reduced-motion: reduce)');this.running=false;this.raf=0;this.watchdog=0;this.elapsed=0;this.history=[];this.frames=[];this.drawCosts=[];this.resizePending=false;
      $('.intro-skip',this.root).addEventListener('click',()=>this.finish('skip'));
      $('#intro-replay')?.addEventListener('click',()=>this.play('replay'));
      document.addEventListener('keydown',e=>{if(!this.running)return;if(e.key==='Escape'){e.preventDefault();this.finish('escape');}else if(e.key==='Tab'){e.preventDefault();$('.intro-skip',this.root).focus();}},true);
      document.addEventListener('visibilitychange',()=>{if(document.hidden)this.finish('hidden');});
      const preferenceChanged=()=>{const button=$('#intro-replay');if(button){button.disabled=this.preference.matches;button.title=this.preference.matches?'系统已启用减少动态效果':'重播开场';}if(this.preference.matches)this.finish('reduced-motion');};
      this.preference.addEventListener('change',preferenceChanged);preferenceChanged();
      for(const event of ['hashchange','popstate','pagehide'])addEventListener(event,()=>this.finish('navigation'));
      addEventListener('resize',()=>{if(this.running&&this.elapsed>=5060)this.finish('resize-transfer');else this.resizePending=true;},{passive:true});
    }
    play(reason='replay') {
      try{return this.begin(reason);}catch(error){this.error=String(error?.message||error);this.finish('error');window.LensGateway?.endIntro('error');this.root.hidden=true;document.documentElement.classList.remove('intro-pending','intro-active');return false;}
    }
    begin(reason) {
      if(this.preference.matches||document.hidden)return false;
      if(!CSS.supports('mask-image','radial-gradient(black,transparent)')&&!CSS.supports('-webkit-mask-image','radial-gradient(black,transparent)'))return false;
      if(this.running)this.finish('restart',false);
      this.error=null;
      window.LensGateway?.prepareIntro(this.root);
      if(!this.particles){this.particles=new ParticleSystem($('.intro-canvas',this.root));this.lens=new LensScene(this.root);this.title=new TitleReveal(this.root);this.transition=new PageTransition(this.root,this.title.word);}
      else this.particles.resize();
      this.resizePending=false;this.title.reset();this.transition.reset();this.savedFocus=document.activeElement;
      this.frames=[];this.drawCosts=[];this.lastDraw=0;this.elapsed=0;this.start=performance.now();this.reason=reason;
      document.documentElement.classList.add('intro-active');document.documentElement.classList.remove('intro-pending');
      this.root.hidden=false;this.running=true;this.inerted=[];
      window.LensGateway?.beginIntro(this.root);
      window.LensMotionUI?.settle();
      for(const el of document.body.children){if(el===this.root||['SCRIPT','STYLE','LINK'].includes(el.tagName)||el.inert)continue;el.inert=true;el.setAttribute('data-intro-inert','');this.inerted.push(el);}
      this.root.focus({preventScroll:true});this.render(0);
      this.watchdog=setTimeout(()=>this.finish('watchdog'),7500);
      this.raf=requestAnimationFrame(now=>this.tick(now));return true;
    }
    tick(now) {
      if(!this.running)return;
      try {
        this.elapsed=now-this.start;
        if(this.elapsed>=DURATION){this.render(DURATION/1000);this.finish('complete');return;}
        const interval=this.particles.small?1000/30:0;
        if(!this.lastDraw||now-this.lastDraw>=interval-1){
          if(this.resizePending){this.particles.resize();this.resizePending=false;}
          if(this.lastDraw)this.frames.push(now-this.lastDraw);
          const before=performance.now();this.render(this.elapsed/1000);this.drawCosts.push(performance.now()-before);this.lastDraw=now;
          if(this.drawCosts.length===30&&this.drawCosts.reduce((a,b)=>a+b,0)/30>9)this.particles.count=Math.floor(this.particles.count*.7);
        }
        this.raf=requestAnimationFrame(time=>this.tick(time));
      } catch(error) { this.error=String(error?.message||error);this.finish('error'); }
    }
    render(t) {
      this.particles.draw(t);this.title.draw(t,!!this.transition.first);
      const zoom=this.transition.draw(t,this.particles.size);this.lens.draw(t,zoom);
      this.root.style.setProperty('--lens-size',this.particles.size+'px');
      const signals=$('.intro-signals',this.root),appear=out(ramp(t,3.02,3.34)),fold=smooth(ramp(t,3.66,4.08));
      signals.style.opacity=appear*(1-fold);signals.style.transform=`translateY(${-fold*this.particles.h*.19}px) scale(${1-fold*.91})`;
      this.root.querySelectorAll('.intro-signal').forEach((el,i)=>{el.style.opacity=out(ramp(t,3.02+i*.045,3.28+i*.045));el.style.transform=`translateY(${(1-appear)*8}px)`;});
      window.LensGateway?.drawIntro(t,this.particles.size);
      $('.intro-progress i',this.root).style.transform=`scaleX(${clamp(t/(DURATION/1000))})`;
      $('.intro-progress',this.root).style.opacity=1-ramp(t,5.1,5.5);
      this.root.dataset.phase=t<.8?'awakening':t<1.8?'flow':t<3?'lens':t<4?'insights':t<5.06?'brand':'transfer';
    }
    finish(reason='skip',focus=true) {
      if(!this.running)return;
      this.running=false;cancelAnimationFrame(this.raf);this.raf=0;clearTimeout(this.watchdog);this.watchdog=0;
      const first=this.transition.first?.toJSON(),last=this.transition.last?.toJSON(),driver=this.transition.driver,pixels=this.particles.canvas.width*this.particles.canvas.height;
      this.transition.clean();window.LensGateway?.endIntro(reason);this.root.hidden=true;this.particles.clear();
      for(const el of this.inerted){el.inert=false;el.removeAttribute('data-intro-inert');}this.inerted=[];
      document.documentElement.classList.remove('intro-active','intro-pending');
      const sorted=[...this.drawCosts].sort((a,b)=>a-b),intervals=[...this.frames].sort((a,b)=>a-b);
      this.history.push({reason,startedBy:this.reason,elapsed:Math.round(performance.now()-this.start),draws:this.drawCosts.length,averageFPS:this.frames.length?1000/(this.frames.reduce((a,b)=>a+b,0)/this.frames.length):0,p95Frame:intervals[Math.floor(intervals.length*.95)]||0,p95Draw:sorted[Math.floor(sorted.length*.95)]||0,particles:this.particles.count,canvasPixels:pixels,error:this.error||null,first,last,driver});
      // Release the backing store after the finite animation, including skipped runs.
      this.particles.canvas.width=1;this.particles.canvas.height=1;
      if(this.history.length>12)this.history.shift();
      if(focus&&!document.hidden){const target=this.reason==='replay'&&this.savedFocus?.isConnected?this.savedFocus:($('#presentation')||$('#research'));target?.focus({preventScroll:true});}
      document.dispatchEvent(new CustomEvent('lens:intro-finished',{detail:{reason}}));
    }
    inspect() { return {running:this.running,raf:this.raf,elapsed:this.elapsed,duration:DURATION,phase:this.root.dataset.phase||'idle',particles:this.particles?.count||0,dpr:this.particles?.dpr||0,canvasPixels:this.particles?this.particles.canvas.width*this.particles.canvas.height:0,seed:SEED,signature:this.particles?.signature||null,points:this.particles?.lastPoints||[],first:this.transition?.first?.toJSON()||null,last:this.transition?.last?.toJSON()||null,driver:this.transition?.driver||null,history:[...this.history],error:this.error||null}; }
  }

  try {
    const controller=new IntroController();
    window.LensIntro={play:()=>controller.play('replay'),skip:()=>controller.finish('skip'),inspect:()=>controller.inspect()};
    clearTimeout(window.__lensIntroBootTimer);
    try{sessionStorage.setItem(SEEN,'1');}catch{}
    const boot=window.__lensIntroRequest;
    if(boot?.play&&(boot.mode==='1'||document.documentElement.classList.contains('intro-pending'))){if(!controller.play(boot.mode==='1'?'forced':'first-visit'))document.documentElement.classList.remove('intro-pending');}
    else document.documentElement.classList.remove('intro-pending');
  } catch(error) {
    document.documentElement.classList.remove('intro-pending','intro-active');
    const root=$('#lens-intro');if(root)root.hidden=true;
    document.querySelectorAll('[data-intro-inert]').forEach(el=>{el.inert=false;el.removeAttribute('data-intro-inert');});
    window.LensIntro={play:()=>false,skip:()=>{},inspect:()=>({running:false,raf:0,error:String(error?.message||error),history:[]})};
  }
})();
