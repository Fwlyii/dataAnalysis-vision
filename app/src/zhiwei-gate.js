(() => {
  'use strict';
  const gate = document.querySelector('#gateway');
  if (!gate) return;
  const main = document.querySelector('#main');
  const preference = matchMedia('(prefers-reduced-motion: reduce)');
  const links = [...gate.querySelectorAll('.zw-orb-link')];
  const skip = gate.querySelector('.zw-gate-skip');
  const replay = gate.querySelector('.zw-gate-replay');
  const status = gate.querySelector('.zw-gate-status');
  const orbits = gate.querySelector('.zw-gate-orbits');
  const footer = gate.querySelector('.zw-gate-footer');
  const canvas = gate.querySelector('canvas');
  const context = canvas.getContext('2d');
  const ticks = gate.querySelector('.zw-optic-ticks');
  let previous = /^#s[1-5]$/.test(location.hash) ? location.hash : '#s1';
  let introTimer = 0, frame = 0, lastFrame = 0, introElapsed = 0, lastTime = 0;
  let token = 0, flight = null, flightAnimation = null, pointerFrame = 0;
  let width = 0, height = 0, particles = [];
  let focusOnArrival = false;
  let destination = previous;
  for (let index = 0; index < 96; index++) {
    const angle = index / 96 * Math.PI * 2;
    const length = index % 8 === 0 ? 11 : index % 4 === 0 ? 6 : 3;
    const tick = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    tick.setAttribute('d', `M${Math.cos(angle) * (210 - length)} ${Math.sin(angle) * (210 - length)}L${Math.cos(angle) * 210} ${Math.sin(angle) * 210}`);
    ticks.append(tick);
  }
  function section(hash) {
    return /^#s[1-5]$/.test(hash) ? document.getElementById(hash.slice(1)) : null;
  }
  function cancelFlight() {
    token++;
    flightAnimation?.cancel();
    flight?.remove();
    flightAnimation = null;
    flight = null;
    gate.removeAttribute('aria-busy');
  }
  function finishIntro() {
    clearTimeout(introTimer);
    gate.dataset.phase = 'idle';
    skip.hidden = true;
    replay.disabled = false;
    orbits.inert = false;
    footer.inert = false;
    status.textContent = '请选择一个光球，进入对应研究板块。';
    if (focusOnArrival || document.activeElement === skip) links[0].focus({preventScroll: true});
    focusOnArrival = false;
  }
  function playIntro(focus) {
    if (preference.matches) { finishIntro(); return; }
    clearTimeout(introTimer);
    gate.dataset.phase = 'idle';
    void gate.offsetWidth;
    gate.dataset.phase = 'intro';
    introElapsed = 0;
    focusOnArrival = focus;
    skip.hidden = false;
    replay.disabled = true;
    orbits.inert = true;
    footer.inert = true;
    if (focus) skip.focus({preventScroll: true});
    status.textContent = '正在聚焦研究现场，可以跳过开场。';
    introTimer = setTimeout(finishIntro, 3400);
  }
  function resizeField() {
    width = gate.clientWidth;
    height = gate.clientHeight;
    const ratio = Math.min(devicePixelRatio || 1, 1.75);
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    context?.setTransform(ratio, 0, 0, ratio, 0, 0);
    particles = Array.from({length: width < 700 ? 65 : 140}, (_, index) => ({
      x: ((index * 373 + 137) % 997) / 997 * width,
      y: ((index * 211 + 53) % 991) / 991 * height,
      phase: index * 2.39996,
      radius: index % 9 === 0 ? 1.1 : .55
    }));
    drawField(performance.now());
  }
  function drawField(time) {
    if (!context) return;
    context.clearRect(0, 0, width, height);
    const scene = gate.querySelector('.zw-gate-scene');
    const centerX = width * .5;
    const centerY = scene.offsetTop + (width <= 700 ? 105 : scene.clientHeight * .453);
    const focus = gate.dataset.phase === 'intro' ? Math.sin(Math.min(1, introElapsed / 2700) * Math.PI) : 0;
    for (const particle of particles) {
      const drift = preference.matches ? 0 : time * .00012;
      const restX = particle.x + Math.sin(drift + particle.phase) * 12;
      const restY = particle.y + Math.cos(drift * .7 + particle.phase) * 9;
      const targetX = centerX + Math.cos(particle.phase) * Math.min(width * .14, 175);
      const targetY = centerY + Math.sin(particle.phase) * Math.min(width * .14, 175);
      const currentX = restX + (targetX - restX) * focus;
      const currentY = restY + (targetY - restY) * focus;
      context.fillStyle = particle.radius > 1 ? '#cecaff99' : '#b8c4ed55';
      context.beginPath();
      context.arc(currentX, currentY, particle.radius, 0, Math.PI * 2);
      context.fill();
    }
  }
  function animate(time) {
    frame = 0;
    if (gate.hidden || document.hidden || preference.matches) return;
    if (lastTime && gate.dataset.phase === 'intro') introElapsed += Math.min(time - lastTime, 80);
    lastTime = time;
    if (time - lastFrame > 32) { drawField(time); lastFrame = time; }
    frame = requestAnimationFrame(animate);
  }
  function syncMotion() {
    cancelAnimationFrame(frame);
    frame = 0;
    lastTime = 0;
    gate.dataset.paused = String(document.hidden);
    if (!gate.hidden && !document.hidden && !preference.matches) frame = requestAnimationFrame(animate);
    else if (!gate.hidden) drawField(performance.now());
  }
  function open(play = false, focus = false) {
    cancelFlight();
    if (section(location.hash)) previous = location.hash;
    gate.hidden = false;
    main.inert = true;
    document.documentElement.classList.add('zw-gate-open');
    gate.scrollTop = 0;
    resizeField();
    if (play) playIntro(focus);
    else { focusOnArrival = focus; finishIntro(); }
    syncMotion();
  }
  function close() {
    clearTimeout(introTimer);
    gate.hidden = true;
    main.inert = false;
    document.documentElement.classList.remove('zw-gate-open');
    cancelAnimationFrame(frame);
    cancelAnimationFrame(pointerFrame);
    frame = 0;
    skip.hidden = true;
    gate.removeAttribute('aria-busy');
  }
  function arrive(hash, push = true) {
    previous = hash;
    if (push && location.hash !== hash) history.pushState(null, '', hash);
    close();
    const target = section(hash);
    target.scrollIntoView({behavior: 'instant', block: 'start'});
    const heading = target.querySelector('h1, h2');
    heading.tabIndex = -1;
    heading.focus({preventScroll: true});
    document.dispatchEvent(new CustomEvent('zhiwei:enter', {detail: {id: target.id}}));
  }
  async function enter(hash, origin) {
    if (!section(hash) || gate.dataset.phase === 'entering') return;
    clearTimeout(introTimer);
    skip.hidden = true;
    cancelFlight();
    const currentToken = token;
    gate.dataset.phase = 'entering';
    destination = hash;
    gate.setAttribute('aria-busy', 'true');
    status.textContent = '正在进入' + section(hash).querySelector('h1, h2').textContent;
    if (preference.matches || !Element.prototype.animate) { arrive(hash); return; }
    const rect = (origin?.querySelector('.zw-orb') || origin || gate).getBoundingClientRect();
    const centerX = rect.left + rect.width / 2, centerY = rect.top + rect.height / 2;
    flight = document.createElement('div');
    flight.className = 'zw-gate-flight';
    flight.style.setProperty('--tone', origin ? getComputedStyle(origin).getPropertyValue('--tone') || '173,162,255' : '173,162,255');
    flight.style.setProperty('--flight-x', centerX + 'px');
    flight.style.setProperty('--flight-y', centerY + 'px');
    document.body.append(flight);
    const cover = Math.hypot(Math.max(centerX, innerWidth - centerX), Math.max(centerY, innerHeight - centerY));
    try {
      flightAnimation = flight.animate([{clipPath: `circle(0px at ${centerX}px ${centerY}px)`}, {clipPath: `circle(${cover}px at ${centerX}px ${centerY}px)`}], {duration: 520, easing: 'cubic-bezier(.22,1,.36,1)', fill: 'forwards'});
      await flightAnimation.finished;
      if (currentToken !== token) return;
      arrive(hash);
      flightAnimation = flight.animate([{opacity: 1}, {opacity: 0}], {duration: 420, easing: 'ease-out', fill: 'forwards'});
      await flightAnimation.finished;
    } catch (error) {
      if (currentToken === token) arrive(hash);
    } finally {
      if (currentToken === token) cancelFlight();
    }
  }
  links.forEach((link, index) => {
    link.addEventListener('click', event => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      enter(link.hash, link);
    });
    link.addEventListener('keydown', event => {
      const direction = {ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1}[event.key];
      if (!direction && event.key !== 'Home' && event.key !== 'End') return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? 4 : (index + direction + 5) % 5;
      links[next].focus();
    });
    link.addEventListener('pointermove', event => {
      if (event.pointerType !== 'mouse' || preference.matches || gate.dataset.phase !== 'idle') return;
      cancelAnimationFrame(pointerFrame);
      const rect = link.getBoundingClientRect();
      pointerFrame = requestAnimationFrame(() => {
        link.style.setProperty('--orb-px', ((event.clientX - rect.left - rect.width / 2) * .08) + 'px');
        link.style.setProperty('--orb-py', ((event.clientY - rect.top - rect.height / 2) * .08) + 'px');
      });
    });
    link.addEventListener('pointerleave', () => {
      cancelAnimationFrame(pointerFrame);
      link.style.removeProperty('--orb-px');
      link.style.removeProperty('--orb-py');
    });
  });
  document.addEventListener('click', event => {
    const anchor = event.target.closest('a');
    if (!anchor || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (anchor.matches('.brand')) {
      event.preventDefault();
      if (location.hash !== '#gateway') history.pushState(null, '', '#gateway');
      open(false, true);
    } else if (!gate.hidden && anchor.matches('.deck-nav a, .zw-gate-start, .skip-link')) {
      event.preventDefault();
      cancelFlight();
      arrive(anchor.hash === '#main' ? '#s1' : anchor.hash);
    }
  });
  skip.addEventListener('click', finishIntro);
  replay.addEventListener('click', () => playIntro(true));
  addEventListener('keydown', event => {
    if (gate.hidden || event.key !== 'Escape') return;
    event.preventDefault();
    if (gate.dataset.phase === 'intro') finishIntro();
    else { cancelFlight(); arrive(previous); }
  });
  addEventListener('hashchange', () => {
    if (location.hash === '#gateway' || (!location.hash && !new URLSearchParams(location.search).has('chapter'))) open(false, true);
    else if (section(location.hash)) {
      cancelFlight();
      if (!gate.hidden) arrive(location.hash, false);
      previous = location.hash;
    }
  });
  addEventListener('resize', () => { if (!gate.hidden) resizeField(); }, {passive: true});
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && gate.dataset.phase === 'intro') finishIntro();
    syncMotion();
  });
  preference.addEventListener('change', () => {
    if (preference.matches && gate.dataset.phase === 'intro') finishIntro();
    if (preference.matches && gate.dataset.phase === 'entering') { cancelFlight(); arrive(destination); }
    syncMotion();
  });
  addEventListener('pagehide', () => { cancelFlight(); cancelAnimationFrame(frame); });
  addEventListener('pageshow', () => {
    if (!gate.hidden && gate.dataset.phase === 'entering') finishIntro();
    syncMotion();
  });
  if (location.hash === '#gateway' || (!location.hash && !new URLSearchParams(location.search).has('chapter'))) open(!preference.matches);
})();
