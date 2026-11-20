/* 知微 · 页面脚本（无第三方依赖）
   读取 data/ 下保存的研究快照：summary.json、research-charts.json、research-content.json、code-feedback-extension.json。
   独立预览版通过 window.__ZW_DATA__ 内嵌同样结构的数据。所有数值都来自这些文件，脚本只做汇总与绘图。 */
(function () {
  'use strict';

  /* ================= 0. 词表与配色 ================= */
  /* 参数为官方公开规格的展示层补充，不回写冻结快照。
     MoE 的 params 为骨干参数；接口别名不等于逐条响应的权重版本确认。
     来源和组成差异见 docs/model-spec-sources.md。 */
  const MODELS = [
    { id: 'qwen', name: 'Qwen2.5 7B', short: 'Qwen2.5', color: '#6749e2', params: '7.61B', active: null, version: 'Qwen2.5-7B-Instruct' },
    { id: 'qwen3', name: 'Qwen3 8B', short: 'Qwen3', color: '#e07227', params: '8.2B', active: null, version: 'Qwen3-8B' },
    { id: 'deepseek', name: 'DeepSeek Flash', short: 'DeepSeek', color: '#32a67d', params: '552B', active: '8–16B', version: 'DeepSeek-V4.1-Flash-1017' },
    { id: 'hy4', name: 'HY4 preview', short: 'HY4', color: '#bc1e72', params: '770B', active: '49B', version: 'Hy4 preview' },
  ];
  const MODEL = Object.fromEntries(MODELS.map(m => [m.id, m]));
  const paramLabel = m => (m.active ? `${m.params} 骨干，激活 ${m.active}` : `${m.params} 稠密`);
  const paramNote = m => m.id === 'deepseek'
    ? `官方公开规格：骨干 ${m.params}，预填充激活 8B／生成激活 16B；另有 196B Engram，不计入骨干。`
    : m.active ? `官方公开规格：骨干 ${m.params}，每 token 激活 ${m.active}，不含 MTP。` : `${m.version}：稠密模型，${m.params} 参数`;
  /* 代码生成上“简洁分步 − 默认分步”的 95% 区间（百分点）。研究快照只保存了各策略相对“只给答案”的区间，
     这里由 runtime/code-features.js 的逐条记录（193 题 × 5 次采样）按题聚类 bootstrap 5,000 次算出，
     方法与快照一致；复算脚本见 scripts/analysis/derive_concise_ci.py。 */
  const CODE_CONCISE_CI = { deepseek: [0.41, 5.60], qwen: [-2.28, 1.04], qwen3: [-0.73, 3.94] };
  function modelId(name) {
    const s = String(name || '').toLowerCase();
    if (s.includes('deepseek')) return 'deepseek';
    if (s.includes('hy4') || s.includes('hunyuan')) return 'hy4';
    if (s.includes('qwen3')) return 'qwen3';
    if (s.includes('qwen')) return 'qwen';
    return s;
  }
  const TASKS = [
    { id: 'gsm8k', name: 'GSM8K', desc: '算术应用题' },
    { id: 'math500', name: 'MATH500', desc: '竞赛数学' },
    { id: 'mmlu', name: 'MMLU-Pro', desc: '选择题' },
  ];
  const TASK = Object.fromEntries(TASKS.map(t => [t.id, t]));
  const taskId = name => { const s = String(name).toLowerCase(); return s.includes('gsm') ? 'gsm8k' : s.includes('math') ? 'math500' : s.includes('mmlu') ? 'mmlu' : s; };
  const FAMILIES = [
    { id: 'reasoning', name: '回答组织', prompts: ['NoCoT', 'DefaultCoT', 'BeConcise', 'StepLimit(1)', 'StepLimit(2)', 'StepLimit(5)'] },
    { id: 'language', name: '语言模板', prompts: ['ChineseCoT', 'ChineseCoT(10)', 'ChineseCoT(50)', 'ChineseCoT(100)', 'ChineseCoT(500)'] },
    { id: 'length', name: '长度预算', prompts: ['WordLimit(1)', 'WordLimit(5)', 'WordLimit(10)', 'WordLimit(15)', 'WordLimit(25)', 'WordLimit(50)', 'WordLimit(100)', 'CharLimit(10)', 'CharLimit(50)', 'CharLimit(100)', 'CharLimit(500)', 'TokenLimit(10)', 'TokenLimit(50)', 'TokenLimit(100)', 'TokenLimit(500)'] },
    { id: 'format', name: '表达格式', prompts: ['BulletPoints', 'AbbreviateWords', 'NoProperGrammar', 'NoSpaces', 'OnlyNumbers'] },
  ];
  const SHORT = { NoCoT: '只给答案', DefaultCoT: '默认分步', BeConcise: '简洁分步', ChineseCoT: '中文作答', BulletPoints: '项目符号', AbbreviateWords: '缩写单词', NoProperGrammar: '简化语法', NoSpaces: '移除空格', OnlyNumbers: '数字算式' };
  function shortLabel(id) {
    if (SHORT[id]) return SHORT[id];
    const m = /^(\w+)\((\d+)\)$/.exec(id);
    if (!m) return id;
    return ({ StepLimit: '≤' + m[2] + ' 步', ChineseCoT: '中文 ' + m[2], WordLimit: '词数 ' + m[2], CharLimit: '字母 ' + m[2], TokenLimit: 'Token ' + m[2] })[m[1]] || id;
  }
  const ARMS = [
    { id: 'resample', name: '独立重采样', color: '#7d8096', desc: '重新回答同一题，看不到上一版代码，也没有测试反馈。' },
    { id: 'self_review', name: '自行检查', color: '#aa7e1a', desc: '看到上一版代码，按统一指令自查，不接收执行结果。' },
    { id: 'pass_fail', name: '仅通过状态', color: '#3b9ce5', desc: '在自查基础上，只告知公开测试通过还是失败。' },
    { id: 'diagnostic', name: '错误定位诊断', color: '#6749e2', desc: '给出实际错误类型、错误信息、行列与源码行。' },
    { id: 'counterexample', name: '单个失败反例', color: '#bc1e72', desc: '给出第一个失败输入、期望结果与实际输出。' },
    { id: 'multi_counterexample', name: '多个失败反例', color: '#32a67d', desc: '最多三个不同的失败反例，并附真实测试计数。' },
  ];
  const ARM = Object.fromEntries(ARMS.map(a => [a.id, a]));
  const GOOD = '#34b27a', BAD = '#e5534b', INK = '#eef0f8', INK3 = '#8b90aa', PLATE = '#111530';
  const ACC = '#8b7dff', TRACK = 'rgba(255,255,255,.07)', MUTED = '#4a4e66', GRIDC = 'rgba(255,255,255,.08)', BANDC = 'rgba(255,255,255,.22)';

  /* 颜色：OKLCH → sRGB；顺序色为苏木紫单色阶，发散色为紫—橙（PuOr） */
  function oklch(L, C, hue) {
    const a = C * Math.cos(hue * Math.PI / 180), b = C * Math.sin(hue * Math.PI / 180);
    const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3, m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3, s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3;
    const rgb = [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s, -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s];
    return '#' + rgb.map(v => { v = Math.max(0, Math.min(1, v)); v = v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055; return Math.round(v * 255).toString(16).padStart(2, '0'); }).join('');
  }
  /* 深色底上：数值越大越亮 */
  const seqL = t => 0.25 + 0.62 * t;
  function seq(t) { t = Math.max(0, Math.min(1, t)); return oklch(seqL(t), 0.05 + 0.12 * Math.sin(Math.PI * Math.min(1, t * 0.85)), 292 - 10 * t); }
  const seqText = t => (seqL(Math.max(0, Math.min(1, t))) > 0.56 ? PLATE : '#ffffff');
  function div(v) { v = Math.max(-1, Math.min(1, v)); const a = Math.abs(v); return v >= 0 ? oklch(0.29 + 0.5 * a, 0.012 + 0.15 * a, 292) : oklch(0.29 + 0.5 * a, 0.012 + 0.14 * a, 55); }
  const divText = v => (0.29 + 0.5 * Math.min(1, Math.abs(v)) > 0.56 ? PLATE : '#ffffff');

  /* ================= 1. 工具 ================= */
  const $ = (sel, root = document) => root.querySelector(sel);
  const NS = 'http://www.w3.org/2000/svg';
  const XLINK = 'http://www.w3.org/1999/xlink';
  const reduceMotion = !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
  function h(tag, props, ...kids) {
    const n = document.createElement(tag);
    if (props) for (const [k, v] of Object.entries(props)) {
      if (v == null || v === false) continue;
      if (k === 'class') n.className = v;
      else if (k === 'text') n.textContent = v;
      else if (k.startsWith('on') && typeof v === 'function') n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat(Infinity)) { if (kid == null || kid === false) continue; n.append(kid.nodeType ? kid : document.createTextNode(String(kid))); }
    return n;
  }
  function s(tag, attrs, parent) {
    const n = document.createElementNS(NS, tag);
    if (attrs) for (const [k, v] of Object.entries(attrs)) { if (v == null) continue; if (k === 'text') n.textContent = v; else n.setAttribute(k, v); }
    if (parent) parent.appendChild(n);
    return n;
  }
  function text(parent, x, y, str, attrs) {
    const a = { x: r1(x), y: r1(y), ...attrs, text: str };
    const fill = a.fill; delete a.fill;
    const t = s('text', a, parent);
    if (fill) t.style.fill = fill;
    return t;
  }
  /* 让标签留在绘图区内：测量宽度后整体平移 */
  function fitText(t, minX, maxX) {
    try {
      const w = t.getComputedTextLength(), anchor = t.getAttribute('text-anchor') || 'start', x = +t.getAttribute('x');
      let left = anchor === 'end' ? x - w : anchor === 'middle' ? x - w / 2 : x;
      if (left + w > maxX) left = maxX - w;
      if (left < minX) left = minX;
      t.setAttribute('x', r1(anchor === 'end' ? left + w : anchor === 'middle' ? left + w / 2 : left));
    } catch (err) { /* 未渲染时无法测量 */ }
    return t;
  }
  const r1 = v => (typeof v === 'number' ? Math.round(v * 10) / 10 : v);
  const fmt = (v, d = 0) => (Number.isFinite(v) ? v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }) : '—');
  const pct = (v, d = 1) => (Number.isFinite(v) ? fmt(v, d) + '%' : '—');
  function signed(v, d = 1) { if (!Number.isFinite(v)) return '—'; const r = Number(v.toFixed(d)); return r === 0 ? '±' + fmt(0, d) : (r > 0 ? '+' : '−') + fmt(Math.abs(r), d); }
  const ci = (lo, hi, d = 1) => `[${signed(lo, d)}, ${signed(hi, d)}]`;
  function linear(d0, d1, a, b) { const f = v => a + (v - d0) / (d1 - d0 || 1) * (b - a); f.invert = p => d0 + (p - a) / (b - a || 1) * (d1 - d0); f.d = [d0, d1]; return f; }
  function logScale(d0, d1, a, b) { const l0 = Math.log(d0), l1 = Math.log(d1); const f = v => a + (Math.log(v) - l0) / (l1 - l0) * (b - a); f.d = [d0, d1]; return f; }
  function ticks(min, max, count = 5) {
    const span = max - min; if (!(span > 0)) return [min];
    const raw = span / count, mag = 10 ** Math.floor(Math.log10(raw)), e = raw / mag;
    const step = (e >= 7.5 ? 10 : e >= 3.5 ? 5 : e >= 1.5 ? 2 : 1) * mag;
    const out = [];
    for (let v = Math.ceil(min / step - 1e-9) * step; v <= max + step * 1e-6; v += step) out.push(+v.toFixed(10));
    return out;
  }
  function niceRange(min, max, count = 5) { const t = ticks(min, max, count); const step = t.length > 1 ? t[1] - t[0] : 1; return [Math.floor(min / step + 1e-9) * step, Math.ceil(max / step - 1e-9) * step]; }
  const linePath = pts => pts.map((p, i) => (i ? 'L' : 'M') + r1(p[0]) + ',' + r1(p[1])).join('');
  const bandPath = pts => linePath(pts.map(p => [p[0], p[2]])) + pts.slice().reverse().map(p => 'L' + r1(p[0]) + ',' + r1(p[1])).join('') + 'Z';
  function hbar(x0, x1, y, hgt, r = 4) { // 水平条，数据端圆角、基线端方角
    const dir = x1 >= x0 ? 1 : -1, len = Math.abs(x1 - x0), rr = Math.min(r, len, hgt / 2);
    if (len < 0.5) return '';
    const xe = x1 - dir * rr;
    return `M${r1(x0)},${r1(y)}H${r1(xe)}Q${r1(x1)},${r1(y)} ${r1(x1)},${r1(y + rr)}V${r1(y + hgt - rr)}Q${r1(x1)},${r1(y + hgt)} ${r1(xe)},${r1(y + hgt)}H${r1(x0)}Z`;
  }
  function vbar(x, w, yb, yt, r = 4) { // 竖直条，顶端圆角、基线端方角
    const len = Math.abs(yb - yt), rr = Math.min(r, len, w / 2);
    if (len < 0.5) return '';
    return `M${r1(x)},${r1(yb)}V${r1(yt + rr)}Q${r1(x)},${r1(yt)} ${r1(x + rr)},${r1(yt)}H${r1(x + w - rr)}Q${r1(x + w)},${r1(yt)} ${r1(x + w)},${r1(yt + rr)}V${r1(yb)}Z`;
  }
  const SHAPES = {
    circle: (x, y, r) => `M${r1(x - r)},${r1(y)}a${r},${r} 0 1,0 ${2 * r},0a${r},${r} 0 1,0 ${-2 * r},0`,
    square: (x, y, r) => { const q = r * 0.88; return `M${r1(x - q)},${r1(y - q)}h${r1(2 * q)}v${r1(2 * q)}h${r1(-2 * q)}Z`; },
    diamond: (x, y, r) => { const q = r * 1.25; return `M${r1(x)},${r1(y - q)}L${r1(x + q)},${r1(y)}L${r1(x)},${r1(y + q)}L${r1(x - q)},${r1(y)}Z`; },
    triangle: (x, y, r) => { const q = r * 1.25; return `M${r1(x)},${r1(y - q)}L${r1(x + q * 0.95)},${r1(y + q * 0.72)}L${r1(x - q * 0.95)},${r1(y + q * 0.72)}Z`; },
  };

  /* 提示框：数值在前、名称在后，全部用 textContent 写入 */
  const Tip = {
    el: null,
    show(x, y, content) {
      const el = this.el; if (!el) return;
      el.replaceChildren();
      if (content.title) el.append(h('div', { class: 'tip-title', text: content.title }));
      for (const r of content.rows || []) {
        const key = r.color ? h('span', { class: r.dot ? 'swatch-dot' : 'swatch-line', style: r.dot ? `background:${r.color}` : `color:${r.color}` }) : null;
        el.append(h('div', { class: 'tip-row' }, key, h('span', { text: r.label }), h('span', { class: 'tip-value', text: r.value })));
      }
      if (content.note) el.append(h('div', { class: 'tip-note', text: content.note }));
      el.hidden = false;
      const w = el.offsetWidth, ht = el.offsetHeight, pad = 14;
      let left = x + pad, top = y + pad;
      if (left + w > innerWidth - 8) left = x - w - pad;
      if (top + ht > innerHeight - 8) top = y - ht - pad;
      el.style.left = Math.max(8, left) + 'px';
      el.style.top = Math.max(8, top) + 'px';
    },
    at(node, content) { const r = node.getBoundingClientRect(); this.show(r.left + r.width / 2, r.top + r.height / 2, content); },
    hide() { if (this.el) this.el.hidden = true; },
  };
  function bindTip(node, getContent, onActivate) {
    node.addEventListener('pointerenter', e => Tip.show(e.clientX, e.clientY, getContent()));
    node.addEventListener('pointermove', e => Tip.show(e.clientX, e.clientY, getContent()));
    node.addEventListener('pointerleave', () => Tip.hide());
    node.addEventListener('focus', () => Tip.at(node, getContent()));
    node.addEventListener('blur', () => Tip.hide());
    if (onActivate) {
      node.addEventListener('click', onActivate);
      node.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onActivate(e); } });
    }
  }

  /* 图表外框：按容器宽度绘制，宽度变化时重绘；切换状态时按 key 补间 */
  function chart(host, opts) {
    const c = { host, prev: new Map(), next: new Map(), animate: false, W: 0, H: 0, lastW: 0, lastH: 0 };
    if (opts.fill) host.classList.add('fill');
    c.render = (animate = false) => {
      const W = Math.round(host.clientWidth);
      if (!W) return;
      const fillH = opts.fill ? Math.round(host.clientHeight) : 0;
      c.fill = fillH > 80;
      c.lastW = W; c.lastH = fillH; c.W = W; c.animate = animate && !reduceMotion; c.next = new Map();
      c.H = c.fill ? fillH : (typeof opts.height === 'function' ? opts.height(W) : opts.height);
      const svg = s('svg', { viewBox: `0 0 ${W} ${c.H}`, width: W, height: c.H, role: 'img', 'aria-label': typeof opts.label === 'function' ? opts.label() : opts.label });
      c.svg = svg;
      host.replaceChildren(svg);
      opts.draw(svg, c);
      c.prev = c.next;
      if (opts.after) opts.after(c);
    };
    let timer;
    if ('ResizeObserver' in window) new ResizeObserver(() => {
      const W = Math.round(host.clientWidth), Hh = opts.fill ? Math.round(host.clientHeight) : 0;
      if (!W || (Math.abs(W - c.lastW) < 2 && Math.abs(Hh - c.lastH) < 2)) return;
      clearTimeout(timer); timer = setTimeout(() => c.render(false), c.lastW ? 80 : 0);
    }).observe(host);
    c.render(false);
    return c;
  }
  /* 行式图表在面板里按可用高度分配行高 */
  const rowsH = (c, n, used, def, min = 18) => (c.fill ? Math.max(min, Math.min(def * 2, (c.H - used) / n)) : def);
  function tween(dur, step) {
    const t0 = performance.now();
    /* 帧时间戳可能早于 t0，进度先夹到 [0, 1]，避免第一帧外推出负值 */
    const frame = now => { const p = Math.max(0, Math.min(1, (now - t0) / dur)); step(1 - (1 - p) ** 3); if (p < 1) requestAnimationFrame(frame); };
    requestAnimationFrame(frame);
  }
  function keyed(c, node, key, attrs) {
    const prev = c.animate ? c.prev.get(key) : null;
    c.next.set(key, attrs);
    const nums = prev && !Array.isArray(prev) ? Object.keys(attrs).filter(k => typeof attrs[k] === 'number' && typeof prev[k] === 'number' && prev[k] !== attrs[k]) : [];
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, nums.includes(k) ? prev[k] : (typeof v === 'number' ? r1(v) : v));
    if (nums.length) tween(560, e => { for (const k of nums) node.setAttribute(k, r1(prev[k] + (attrs[k] - prev[k]) * e)); });
    return node;
  }
  function keyedPath(c, node, key, pts, build) {
    const prev = c.animate ? c.prev.get(key) : null;
    c.next.set(key, pts);
    if (!Array.isArray(prev) || prev.length !== pts.length) { node.setAttribute('d', build(pts)); return node; }
    node.setAttribute('d', build(prev));
    tween(560, e => node.setAttribute('d', build(pts.map((p, i) => p.map((v, j) => prev[i][j] + (v - prev[i][j]) * e)))));
    return node;
  }
  function axisY(svg, y, tks, x0, x1, fmtTick = v => fmt(v)) {
    const g = s('g', null, svg);
    for (const v of tks) { s('line', { class: 'grid', x1: x0, x2: x1, y1: r1(y(v)), y2: r1(y(v)) }, g); text(g, x0 - 8, y(v) + 4, fmtTick(v), { class: 'tick', 'text-anchor': 'end' }); }
    return g;
  }
  function axisX(svg, x, tks, y0, fmtTick = v => fmt(v), grid) {
    const g = s('g', null, svg);
    for (const v of tks) { if (grid) s('line', { class: 'grid', x1: r1(x(v)), x2: r1(x(v)), y1: grid[0], y2: grid[1] }, g); text(g, x(v), y0 + 17, fmtTick(v), { class: 'tick', 'text-anchor': 'middle' }); }
    return g;
  }
  function segmented(host, options, value, onChange) {
    host.replaceChildren();
    const buttons = options.map(o => {
      const b = h('button', { type: 'button', 'aria-pressed': String(o.id === value) }, o.color ? h('span', { class: 'swatch-dot', style: `background:${o.color}` }) : null, o.label);
      b.addEventListener('click', () => { if (b.getAttribute('aria-pressed') === 'true') return; buttons.forEach(x => x.setAttribute('aria-pressed', String(x === b))); onChange(o.id); });
      return b;
    });
    host.append(...buttons);
    return { set(id) { buttons.forEach((b, i) => b.setAttribute('aria-pressed', String(options[i].id === id))); } };
  }
  function tableBlock(caption, cols, rows) {
    return h('div', { class: 'table-wrap', tabindex: '0', role: 'region', 'aria-label': caption },
      h('table', { class: 'data-table' }, h('caption', { text: caption }),
        h('thead', null, h('tr', null, cols.map(c => h('th', { scope: 'col', text: c })))),
        h('tbody', null, rows.map(r => h('tr', null, r.map((v, i) => (i ? h('td', { text: String(v) }) : h('th', { scope: 'row', text: String(v) }))))))));
  }
  /* 每张图都有“数据表”：在同一个对话框里打开，与图同步 */
  function openTable(t) {
    const dlg = $('#table-dialog'); if (!dlg) return;
    $('#table-dialog-title').textContent = t.caption;
    $('#table-dialog-body').replaceChildren(tableBlock(t.caption, t.cols, t.rows));
    if (!dlg.open) { if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', ''); }
  }
  function attachTable(plate, build) {
    let tools = plate.querySelector('.panel-tools');
    if (!tools) { tools = h('div', { class: 'panel-tools' }); plate.append(tools); }
    const btn = h('button', { class: 'icon-btn', type: 'button', title: '数据表', 'aria-label': '查看数据表', text: '表' });
    let open = false;
    btn.addEventListener('click', () => { open = true; openTable(build()); });
    const dlg = $('#table-dialog'); if (dlg) dlg.addEventListener('close', () => { open = false; });
    tools.append(btn);
    return () => { if (open && dlg && dlg.open) openTable(build()); };
  }
  function legendRow(items) {
    return h('div', { class: 'chart-legend' }, items.map(it => {
      let key;
      if (it.shape) { const sv = s('svg', { viewBox: '0 0 14 14', width: 14, height: 14, 'aria-hidden': 'true' }); s('path', { d: SHAPES[it.shape](7, 7, 4.6), fill: it.hollow ? PLATE : (it.color || INK3), stroke: it.color || INK3, 'stroke-width': 1.6 }, sv); key = sv; }
      else if (it.line) key = h('span', { class: 'swatch-line', style: `color:${it.color}` });
      else key = h('span', { class: 'swatch-dot', style: `background:${it.color}` });
      return h('span', { class: 'legend-item' }, key, it.label);
    }));
  }
  const famOf = id => FAMILIES.find(f => f.prompts.includes(id));

  /* ================= 2. 数据 ================= */
  async function loadRaw() {
    if (window.__ZW_DATA__) return window.__ZW_DATA__;
    const get = async path => { const r = await fetch(path); if (!r.ok) throw new Error(path + ' 读取失败（HTTP ' + r.status + '）'); return r.json(); };
    const [summary, charts, content, feedback] = await Promise.all(['data/summary.json', 'data/research-charts.json', 'data/research-content.json', 'data/code-feedback-extension.json'].map(get));
    return { summary, charts, content, feedback };
  }
  function buildModel(raw) {
    const rows = id => ((raw.charts.charts || []).find(c => c.id === id) || {}).data || [];
    const grid = {};
    for (const c of raw.summary.cells) {
      if (c.dataset !== 'reasoning') continue;
      ((grid[c.model] ||= {})[c.task] ||= {})[c.prompt] = { score: c.scores[0] / c.n * 100, tokens: c.token_n ? c.tokens / c.token_n : NaN, trunc: c.truncated / c.n * 100, unresolved: c.unresolved / c.n * 100, n: c.n };
    }
    const prompts = Object.fromEntries((raw.content.prompts || []).map(p => [p.id, p]));
    const comps = (raw.summary.comparisons && raw.summary.comparisons.reasoning) || [];
    const ev = raw.feedback.evidence;
    const records = raw.content.experiments.filter(e => e.id !== 'code_repair').reduce((a, e) => a + e.records, 0) + ev.saved_physical_responses;
    return { raw, rows, grid, prompts, comps, content: raw.content, fb: raw.feedback, ev, records };
  }
  const cell = (M, model, task, prompt) => (((M.grid[model] || {})[task] || {})[prompt]) || {};

  /* ================= 3. 首屏：提示策略切片 ================= */
  function renderSpecimen(M) {
    const stage = $('#specimen-stage');
    const order = FAMILIES.flatMap(f => f.prompts.map(id => ({ id, fam: f })));
    const C = 340, RINGS = [[92, 134], [138, 180], [184, 226]], RL = 236, RF = 296, RT = 334;
    const GAP_TOP = 22, GAP_FAM = 3, SEC = (360 - GAP_TOP - GAP_FAM * (FAMILIES.length - 1)) / order.length;
    let a = GAP_TOP / 2; const famRange = {};
    order.forEach((p, i) => {
      if (i && order[i - 1].fam !== p.fam) a += GAP_FAM;
      p.a0 = a; p.a1 = a + SEC; p.mid = a + SEC / 2; a += SEC;
      (famRange[p.fam.id] ||= [p.a0, p.a1])[1] = p.a1;
    });
    const P = (r, deg) => { const t = deg * Math.PI / 180; return [C + r * Math.sin(t), C - r * Math.cos(t)]; };
    const arcPath = (ra, rb, a0, a1) => { const [x0, y0] = P(rb, a0), [x1, y1] = P(rb, a1), [x2, y2] = P(ra, a1), [x3, y3] = P(ra, a0); return `M${r1(x0)} ${r1(y0)}A${rb} ${rb} 0 0 1 ${r1(x1)} ${r1(y1)}L${r1(x2)} ${r1(y2)}A${ra} ${ra} 0 0 0 ${r1(x3)} ${r1(y3)}Z`; };
    const lineArc = (r, a0, a1, rev) => { const [x0, y0] = P(r, rev ? a1 : a0), [x1, y1] = P(r, rev ? a0 : a1); return `M${r1(x0)} ${r1(y0)}A${r} ${r} 0 ${a1 - a0 > 180 ? 1 : 0} ${rev ? 0 : 1} ${r1(x1)} ${r1(y1)}`; };

    const svg = s('svg', { viewBox: '0 0 680 680', role: 'img', tabindex: '0', 'aria-label': '提示策略切片：31 种提示策略在三个题库上的规则评分。左右方向键切换提示。' });
    const defs = s('defs', null, svg);
    const grad = s('radialGradient', { id: 'spec-disc' }, defs);
    s('stop', { offset: '0.62', 'stop-color': '#171c3e' }, grad);
    s('stop', { offset: '1', 'stop-color': '#0b0f26' }, grad);
    s('circle', { cx: C, cy: C, r: RT, fill: 'url(#spec-disc)' }, svg);
    s('circle', { class: 'spec-ring', cx: C, cy: C, r: RT, fill: 'none', stroke: 'rgba(255,255,255,.18)', 'stroke-width': 1 }, svg);
    const gt = s('g', { stroke: 'rgba(255,255,255,.24)', 'stroke-width': 1 }, svg);
    for (let d = 0; d < 360; d += 3) {
      const len = d % 90 === 0 ? 13 : d % 15 === 0 ? 8 : 4, [x0, y0] = P(RT, d), [x1, y1] = P(RT - len, d);
      s('line', { x1: r1(x0), y1: r1(y0), x2: r1(x1), y2: r1(y1) }, gt);
    }
    const gSec = s('g', null, svg);
    const cells = [];
    order.forEach((p, i) => RINGS.forEach(([ra, rb], j) => {
      const path = s('path', { class: 'sector', d: arcPath(ra, rb, p.a0, p.a1), fill: '#1b1e38', stroke: '#14172d', 'stroke-width': 1.6, 'data-i': i, 'data-j': j }, gSec);
      cells.push({ path, i, j });
    }));
    const outline = s('path', { fill: 'none', stroke: INK, 'stroke-width': 2, 'pointer-events': 'none', 'stroke-linejoin': 'round' }, svg);
    RINGS.forEach(([ra, rb], j) => text(svg, C, C - (ra + rb) / 2 + 4, TASKS[j].name, { class: 'spec-ring-label', 'text-anchor': 'middle' }));
    const labels = order.map(p => {
      const [x, y] = P(RL, p.mid), right = p.mid < 180;
      return text(svg, x, y, shortLabel(p.id), { class: 'spec-label', 'text-anchor': right ? 'start' : 'end', 'dominant-baseline': 'central', transform: `rotate(${r1(right ? p.mid - 90 : p.mid + 90)} ${r1(x)} ${r1(y)})` });
    });
    FAMILIES.forEach(f => {
      const [a0, a1] = famRange[f.id], mid = (a0 + a1) / 2, bottom = mid > 90 && mid < 270;
      s('path', { d: lineArc(RF, a0 + 0.5, a1 - 0.5, false), fill: 'none', stroke: INK, 'stroke-width': 1.2 }, svg);
      for (const e of [a0 + 0.5, a1 - 0.5]) { const [x0, y0] = P(RF - 6, e), [x1, y1] = P(RF, e); s('line', { x1: r1(x0), y1: r1(y0), x2: r1(x1), y2: r1(y1), stroke: INK, 'stroke-width': 1.2 }, svg); }
      const id = 'spec-fam-' + f.id;
      s('path', { id, d: lineArc(bottom ? RF + 17 : RF + 8, a0, a1, bottom), fill: 'none' }, defs);
      const tx = s('text', { class: 'spec-family', 'text-anchor': 'middle' }, svg);
      const tp = s('textPath', { href: '#' + id, startOffset: '50%', text: f.name }, tx);
      tp.setAttributeNS(XLINK, 'xlink:href', '#' + id);
    });
    const ro = s('g', { class: 'spec-readout', 'text-anchor': 'middle' }, svg);
    const roModel = text(ro, C, C - 46, '', { class: 'ro-model' });
    const roTitle = text(ro, C, C - 20, '', { class: 'ro-title' });
    const roId = text(ro, C, C - 1, '', { class: 'ro-id' });
    const roRows = TASKS.map((tk, j) => ({ key: text(ro, C - 52, C + 23 + j * 18, tk.name, { class: 'ro-key', 'text-anchor': 'start' }), val: text(ro, C + 52, C + 23 + j * 18, '', { class: 'ro-val', 'text-anchor': 'end' }) }));
    stage.replaceChildren(svg);
    const instr = h('p', { class: 'spec-instruction', 'aria-live': 'polite' });
    const mobileRo = h('p', { class: 'spec-mobile' });
    $('#specimen-legend').after(mobileRo, instr);

    let model = 'qwen', pinned = order.findIndex(p => p.id === 'DefaultCoT'), hover = -1;
    const score = (i, j) => cell(M, model, TASKS[j].id, order[i].id).score;
    function paint(stagger) {
      for (const c of cells) {
        const v = score(c.i, c.j);
        c.path.style.transitionDelay = stagger ? Math.round(order[c.i].mid / 360 * 760 + c.j * 70) + 'ms' : '0ms';
        c.path.style.fill = Number.isFinite(v) ? seq(v / 100) : '#1b1e38';
      }
    }
    function show() {
      const i = hover >= 0 ? hover : pinned, p = order[i];
      roModel.textContent = MODEL[model].name;
      roTitle.textContent = (M.prompts[p.id] && M.prompts[p.id].label) || shortLabel(p.id);
      roId.textContent = p.id;
      roRows.forEach((r, j) => { r.val.textContent = pct(score(i, j)); });
      outline.setAttribute('d', arcPath(RINGS[0][0] - 1, RINGS[2][1] + 1, p.a0, p.a1));
      labels.forEach((l, k) => l.classList.toggle('is-active', k === i));
      mobileRo.replaceChildren(h('b', { text: roTitle.textContent }), ' ', ...TASKS.map((tk, j) => h('span', null, tk.name + ' ', h('strong', { text: pct(score(i, j)) }))));
      const ins = M.prompts[p.id] && M.prompts[p.id].instruction;
      instr.replaceChildren('实际发送的指令：', h('q', { text: ins || p.id }));
    }
    gSec.addEventListener('pointerover', e => { const i = e.target.dataset && e.target.dataset.i; if (i != null) { hover = +i; show(); } });
    gSec.addEventListener('pointerleave', () => { hover = -1; show(); });
    gSec.addEventListener('click', e => { const i = e.target.dataset && e.target.dataset.i; if (i != null) { pinned = +i; hover = -1; show(); } });
    svg.addEventListener('keydown', e => {
      const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
      if (step) { e.preventDefault(); pinned = (pinned + step + order.length) % order.length; hover = -1; show(); }
      else if (e.key === 'Home' || e.key === 'End') { e.preventDefault(); pinned = e.key === 'Home' ? 0 : order.length - 1; hover = -1; show(); }
    });

    let refreshTable = () => {};
    segmented($('#specimen-models'), MODELS.map(m => ({ id: m.id, label: m.name, color: m.color })), model, id => { model = id; paint(false); show(); refreshTable(); });

    const legend = $('#specimen-legend');
    const stops = [0, 0.25, 0.5, 0.75, 1].map(t => `${seq(t)} ${t * 100}%`).join(',');
    const toggle = h('button', { class: 'table-toggle', type: 'button', 'aria-expanded': 'false', text: '数据表' });
    legend.replaceChildren(h('span', { text: '规则评分' }), h('div', null, h('div', { class: 'ramp', style: `background:linear-gradient(90deg,${stops})` }), h('div', { class: 'ramp-ticks' }, ['0%', '25%', '50%', '75%', '100%'].map(v => h('span', { text: v })))), toggle);
    const specTable = () => ({ caption: `${MODEL[model].name}：31 种提示的规则评分（%），每格 200 题`, cols: ['提示策略', 'ID', 'GSM8K', 'MATH500', 'MMLU-Pro'], rows: order.map((p, i) => [(M.prompts[p.id] && M.prompts[p.id].label) || p.id, p.id, ...TASKS.map((t, j) => fmt(score(i, j), 1))]) });
    let open = false;
    refreshTable = () => { if (open && $('#table-dialog') && $('#table-dialog').open) openTable(specTable()); };
    toggle.addEventListener('click', () => { open = true; openTable(specTable()); });
    if ($('#table-dialog')) $('#table-dialog').addEventListener('close', () => { open = false; });

    show();
    if (reduceMotion) paint(false); else requestAnimationFrame(() => requestAnimationFrame(() => paint(true)));
  }

  /* ================= 4. 受测模型 ================= */
  function renderTasks() {
    const host = $('#model-roster'); if (!host) return;
    host.replaceChildren(...MODELS.map(m => h('li', { class: 'model-tag' }, h('span', { class: 'swatch-dot', style: `background:${m.color}` }), h('b', { text: m.name }), h('small', { text: paramLabel(m), title: paramNote(m) }))));
  }

  /* ================= 5. 实验设计：五组实验与策略矩阵 ================= */
  const EXP_NAMES = {
    reasoning: ['数学与选择题', '600 题 × 4 模型 × 31 策略'],
    document_qa: ['文档问答', '200 题 × 2 模型 × 187 条件'],
    code_generation: ['代码生成', '194 题 × 3 模型 × 31 策略 × 5 次'],
    document_positions: ['文档证据位置', '200 题 × 2 模型 × 9 个位置'],
  };
  function experiments(M) {
    const ev = M.ev;
    const exps = M.content.experiments.filter(e => EXP_NAMES[e.id]).map(e => ({ name: EXP_NAMES[e.id][0], formula: EXP_NAMES[e.id][1], records: e.records, bench: e.benchmarks }));
    exps.push({ name: '代码执行反馈', formula: `${ev.planned_tasks} 题 × ${ev.models.length} 模型 × ${ev.repeats_per_task} 初稿 ×（1＋${ev.arms.length}反馈×${ev.rounds - 1}次修订）`, records: ev.saved_physical_responses, bench: 'HumanEval+ ' + ev.benchmark_version });
    return exps;
  }
  function renderLedger(M) {
    const exps = experiments(M);
    document.querySelectorAll('[data-bind="allRecords"]').forEach(n => { n.textContent = fmt(M.records); n.dataset.count = M.records; });
    const title = $('#ledger-title'); if (title) title.textContent = `${exps.length} 组实验，选用 ${fmt(M.records)} 份回答`;
    if (title) title.title = '本页用完整补充批次替代旧 Mini 修复批；旧 5,576 份仍保存在研究仓库，累计物理回答为 273,186 份。';
    chart($('#chart-ledger'), {
      fill: true,
      label: '各组实验的模型回答数量',
      height: W => exps.length * (W < 400 ? 62 : 54) + 30,
      draw(svg, c) {
        /* 窄屏：名称与设计式各占一行，条形另起一行，文字不压条形 */
        const narrow = c.W < 400, rh = rowsH(c, exps.length, 30, narrow ? 62 : 54, narrow ? 58 : 36), lw = narrow ? 0 : Math.min(232, c.W * 0.44);
        const x = linear(0, 100000, lw, c.W - 64);
        for (const v of [0, 25000, 50000, 75000, 100000]) { s('line', { class: 'grid', x1: r1(x(v)), x2: r1(x(v)), y1: 20, y2: c.H - 4 }, svg); text(svg, x(v), 12, v ? fmt(v / 1000) + 'K' : '0', { class: 'tick', 'text-anchor': v ? 'middle' : 'start' }); }
        exps.forEach((e, i) => {
          const y = 24 + i * rh, by = narrow ? y + 34 : y + rh / 2 - 8;
          text(svg, 0, narrow ? y + 12 : y + rh / 2 - 3, e.name, { class: 'label-strong' });
          text(svg, 0, narrow ? y + 27 : y + rh / 2 + 13, e.formula, { class: 'label-muted' });
          s('path', { d: hbar(x(0), x(e.records), by, narrow ? 12 : 16), fill: ACC }, svg);
          text(svg, x(e.records) + 8, by + (narrow ? 10.5 : 12.5), fmt(e.records), { class: 'value' });
        });
      },
    });
    attachTable($('#plate-ledger'), () => ({ caption: '各组实验的设计与回答数', cols: ['实验', '设计', '题库', '回答数'], rows: exps.map(e => [e.name, e.formula, e.bench, fmt(e.records)]) }));
  }

  function renderCatalog(M) {
    const host = $('#strategy-matrix'), detail = $('#strategy-detail'); if (!host || !detail) return;
    let current = 'DefaultCoT';
    const chips = new Map();
    host.replaceChildren(...FAMILIES.map(f => h('div', { class: 'family family-' + f.id },
      h('p', { class: 'family-name' }, h('b', { text: f.name }), h('span', { text: f.prompts.length + ' 种' })),
      h('div', { class: 'chips' }, f.prompts.map(id => {
        const b = h('button', { type: 'button', class: 'chip-btn', 'aria-pressed': String(id === current), text: shortLabel(id) });
        const pick = () => { if (current === id) return; current = id; chips.forEach((x, k) => x.setAttribute('aria-pressed', String(k === id))); show(); };
        b.addEventListener('mouseenter', pick); b.addEventListener('focus', pick); b.addEventListener('click', pick);
        chips.set(id, b);
        return b;
      })))));
    /* 选中策略的得分表：4 个模型 × 3 个题库，颜色与首屏切片同一色阶；小字为相对“默认分步”的差 */
    const head = h('div', { class: 'sd-head' }), ins = h('p', { class: 'sd-ins', lang: 'en' });
    const grid = h('div', { class: 'sd-grid', role: 'table', 'aria-label': '该策略的规则评分（%）与相对默认分步的差（百分点）' });
    const cells = new Map();
    grid.append(h('div', { class: 'sd-access-row', role: 'row' }, h('span', { class: 'sd-corner', role: 'columnheader', text: '规则评分' }), ...TASKS.map(t => h('span', { class: 'sd-col', role: 'columnheader', text: t.name }))));
    MODELS.forEach(m => {
      const row = h('div', { class: 'sd-access-row', role: 'row' }, h('span', { class: 'sd-row', role: 'rowheader' }, h('i', { class: 'swatch-dot', style: `background:${m.color}` }), m.short));
      TASKS.forEach(t => {
        const val = h('b'), dl = h('small'), box = h('span', { class: 'sd-cell', role: 'cell' }, val, dl);
        cells.set(m.id + '|' + t.id, { box, val, dl });
        row.append(box);
      });
      grid.append(row);
    });
    const rampStops = [0, 0.25, 0.5, 0.75, 1].map(t => `${seq(t)} ${t * 100}%`).join(',');
    const legend = h('div', { class: 'sd-legend' }, h('span', { text: '越亮得分越高；小字为相对默认分步的差（pp）' }),
      h('div', null, h('div', { class: 'ramp', style: `background:linear-gradient(90deg,${rampStops})` }), h('div', { class: 'ramp-ticks' }, ['0%', '50%', '100%'].map(t => h('span', { text: t })))));
    /* 12 格的汇总：相对默认分步的平均变化与升降格数，讲解时一眼看出这条策略的总体方向 */
    const sum = h('div', { class: 'sd-sum', 'aria-live': 'polite' });
    /* 12 格分布条：每行一个题库，每个点一个模型；基线显示得分，其余显示相对默认分步的差 */
    const strip = h('div', { class: 'chart sd-strip' });
    detail.replaceChildren(h('div', { class: 'sd-top' }, head, ins, sum, strip, legend), grid);
    const cellsOf = () => { const ds = []; MODELS.forEach(m => TASKS.forEach(t => { const v = cell(M, m.id, t.id, current).score, b = cell(M, m.id, t.id, 'DefaultCoT').score; if (Number.isFinite(v) && Number.isFinite(b)) ds.push({ m, t, v, d: v - b }); })); return ds; };
    const stripChart = chart(strip, {
      fill: true,
      label: () => (current === 'DefaultCoT' ? '默认分步：12 格规则评分的分布' : `${shortLabel(current)}：12 格相对默认分步的变化`),
      height: 100,
      draw(svg, c) {
        const ds = cellsOf(), base = current === 'DefaultCoT'; if (!ds.length) return;
        const lw = 70, L = lw, R = c.W - 12, top = 6, rh = Math.max(16, (c.H - 26) / TASKS.length), B = top + rh * TASKS.length;
        let d0 = 0, d1 = 100;
        if (!base) { const D = Math.max(5, Math.ceil(Math.max(...ds.map(o => Math.abs(o.d))) / 5) * 5); d0 = -D; d1 = D; }
        const x = linear(d0, d1, L + 6, R - 6);
        TASKS.forEach((t, j) => { const cy = top + j * rh + rh / 2; text(svg, 0, cy + 4, t.name, { class: 'tick' }); s('line', { class: 'grid', x1: L, x2: R, y1: r1(cy), y2: r1(cy) }, svg); });
        const mid = base ? 50 : 0;
        s('line', { class: base ? 'grid' : 'zero', x1: r1(x(mid)), x2: r1(x(mid)), y1: top, y2: B }, svg);
        [d0, mid, d1].forEach(v => text(svg, x(v), B + 15, base ? v + '%' : signed(v, 0), { class: 'tick', 'text-anchor': 'middle' }));
        ds.forEach(o => {
          const cy = top + TASKS.indexOf(o.t) * rh + rh / 2 + (MODELS.indexOf(o.m) - 1.5) * Math.min(3, rh / 8);
          keyed(c, s('circle', { r: 5, fill: o.m.color, stroke: PLATE, 'stroke-width': 1.5 }, svg), o.m.id + o.t.id, { cx: x(base ? o.v : o.d), cy });
        });
      },
    });
    function summary() {
      const ds = cellsOf();
      if (!ds.length) { sum.replaceChildren(); return; }
      const where = x => `${x.m.short} · ${x.t.name}`;
      if (current === 'DefaultCoT') {
        const avg = ds.reduce((a, x) => a + x.v, 0) / ds.length;
        sum.replaceChildren(h('p', { class: 'sd-sum-k' }, h('b', { text: pct(avg) }), h('span', { text: `${ds.length} 格平均规则评分` })),
          h('p', { class: 'sd-sum-l', text: `基线：其余 ${FAMILIES.reduce((a, f) => a + f.prompts.length, 0) - 1} 种策略都与它比较` }));
        return;
      }
      const up = ds.filter(x => x.d > 0.05), down = ds.filter(x => x.d < -0.05), flat = ds.length - up.length - down.length;
      const avg = ds.reduce((a, x) => a + x.d, 0) / ds.length;
      const best = ds.reduce((a, b) => (b.d > a.d ? b : a)), worst = ds.reduce((a, b) => (b.d < a.d ? b : a));
      sum.replaceChildren(
        h('p', { class: 'sd-sum-k' }, h('b', { text: signed(avg) + ' pp' }), h('span', { text: '相对默认分步的平均变化' })),
        h('p', { class: 'sd-sum-l', text: `${ds.length} 格中 ${up.length} 格提高、${down.length} 格下降` + (flat ? `、${flat} 格持平` : '') }),
        h('p', { class: 'sd-sum-l is-x' }, '提高最多 ', up.length ? h('b', { text: `${where(best)} ${signed(best.d)}` }) : h('b', { text: '没有一格提高' })),
        h('p', { class: 'sd-sum-l is-x' }, '下降最多 ', down.length ? h('b', { text: `${where(worst)} ${signed(worst.d)}` }) : h('b', { text: '没有一格下降' })));
    }
    function show() {
      const p = M.prompts[current] || {}, fam = famOf(current);
      head.replaceChildren(h('b', { text: p.label || shortLabel(current) }), h('code', { text: current }), h('span', { class: 'sd-fam', text: fam ? fam.name : '' }));
      ins.textContent = p.instruction || '';
      summary();
      stripChart.render(true);
      MODELS.forEach(m => TASKS.forEach(t => {
        const { box, val, dl } = cells.get(m.id + '|' + t.id);
        const v = cell(M, m.id, t.id, current).score, b = cell(M, m.id, t.id, 'DefaultCoT').score;
        const ok = Number.isFinite(v);
        box.style.background = ok ? `color-mix(in oklab, ${seq(v / 100)} 52%, transparent)` : TRACK;
        val.textContent = ok ? fmt(v, 1) : '—';
        dl.textContent = !ok ? '未测' : current === 'DefaultCoT' ? '基线' : Number.isFinite(b) ? signed(v - b) : '';
        box.setAttribute('aria-label', `${m.name} · ${t.name}：${ok ? pct(v) : '未测'}`);
      }));
    }
    show();
  }

  /* ================= 6. 第 3 章：字段映射 ================= */
  function renderMapping(M) {
    const d = M.content.cleaning;
    const fields = ['output_tokens', 'input_tokens', 'finish_reason', 'model_id'].map(id => d.fields.find(f => f.id === id)).filter(Boolean);
    const keys = ['model_id', 'benchmark', 'input_tokens', 'output_tokens', 'finish_reason', 'metric_name', 'metric_value', 'document_count', 'evidence_position'];
    const srcVal = (src, id) => (id === 'model_id' && src === 'document_qa' ? 'Qwen/Qwen2.5-7B-Instruct' : d.records[src][id]);
    let current = fields[0].id;
    /* 映射框下的一句话规则（完整说明在悬停提示里） */
    const RULE_SHORT = { output_tokens: '两种来源都转成整数，缺失保留 null', input_tokens: '统一为整数，输入与输出分两列', finish_reason: 'length 与 stop 分开，空值不补成正常结束', model_id: '不同写法的模型名映射到同一标识' };
    /* 中文与西文之间补一个空格 */
    const spaced = t => String(t || '').replace(/([\u4e00-\u9fff])([A-Za-z0-9])/g, '$1 $2').replace(/([A-Za-z0-9])([\u4e00-\u9fff])/g, '$1 $2');
    /* 长值在下划线、连字符、点号后允许换行（<wbr>，复制出的文字不变），不用省略号截断 */
    const wbr = t => { const out = []; String(t).split(/([_.\-/])/).forEach((p, k) => { if (k % 2) out[out.length - 1] += p; else { if (out.length) out.push(h('wbr')); out.push(p); } }); return out; };
    const show = v => (v === null || v === undefined ? h('span', { class: 'null', text: 'null' }) : wbr(v));
    const arrow = () => h('div', { class: 'map-arrow', 'aria-hidden': 'true' }, (() => { const sv = s('svg', { viewBox: '0 0 24 24' }); s('path', { d: 'M3 12h17m-6-6 6 6-6 6' }, sv); return sv; })());
    function draw() {
      const f = fields.find(x => x.id === current);
      const srcRows = src => fields.map(x => {
        let key;
        if (src === 'reasoning') key = h('span', { class: 'k' }, h('b', { text: x.reasoningKey }));
        else { const parts = x.documentKey.split('.'), leaf = parts.pop(); key = h('span', { class: 'k' }, parts.length ? h('i', { text: parts.join('.') + '.' }) : null, h('b', { text: leaf })); }
        return h('div', { class: 'src-row' + (x.id === current ? ' is-on' : '') }, key, h('span', { class: 'v', text: JSON.stringify(srcVal(src, x.id)) }));
      });
      $('#mapping-grid').replaceChildren(
        h('div', { class: 'map-col' }, h('p', { class: 'map-col-title', text: 'A　两种来源' }),
          h('div', { class: 'src-block' }, h('h4', { text: '推理实验：源表格的中文列' }), srcRows('reasoning')),
          h('div', { class: 'src-block' }, h('h4', { text: '文档问答：API 返回的 JSON 路径' }), srcRows('document_qa'))),
        arrow(),
        h('div', { class: 'map-col' }, h('p', { class: 'map-col-title', text: 'B　映射与转换' }),
          h('div', { class: 'rule-box' },
            h('div', { class: 'target' }, h('code', { text: f.id }), h('span', { text: f.type })),
            h('pre', null, h('code', { text: f.code })),
            h('p', { class: 'rule-text', title: spaced(f.rule), text: RULE_SHORT[f.id] || spaced(f.rule) }))),
        arrow(),
        h('div', { class: 'map-col' }, h('p', { class: 'map-col-title', text: 'C　统一记录（9 个关键字段）' }),
          h('div', { class: 'table-wrap' }, h('table', { class: 'unified-table' },
            h('colgroup', null, h('col', { class: 'c-key' }), h('col'), h('col')),
            h('thead', null, h('tr', null, h('th', { scope: 'col', text: '统一字段' }), h('th', { scope: 'col', text: '推理记录' }), h('th', { scope: 'col', text: '文档记录' }))),
            h('tbody', null, keys.map(k => h('tr', { class: k === current ? 'is-on' : null }, h('th', { scope: 'row', title: k }, wbr(k)), h('td', { title: String(d.records.reasoning[k]) }, show(d.records.reasoning[k])), h('td', { title: String(d.records.document_qa[k]) }, show(d.records.document_qa[k])))))))));
      document.querySelectorAll('#schema-groups code').forEach(c => c.classList.toggle('is-on', c.dataset.field === current));
    }
    segmented($('#field-picker'), fields.map(f => ({ id: f.id, label: f.name.replace(/([一-鿿])([A-Za-z])/g, '$1 $2') })), current, id => { current = id; draw(); });
    const groups = [['标识与来源', d.headers.slice(0, 7)], ['Token 与耗时', d.headers.slice(7, 10)], ['结束状态', d.headers.slice(10, 12)], ['任务评分', d.headers.slice(12, 15)], ['资料位置', d.headers.slice(15, 17)], ['代码修复', d.headers.slice(17)]];
    const mapped = new Set(fields.map(f => f.id));
    $('#schema-groups').replaceChildren(...groups.map(([name, list]) => h('div', { class: 'schema-group' }, h('h4', null, name, h('span', { text: `（${list.length}）` })), h('div', null, list.map(k => h('code', { 'data-field': k, class: mapped.has(k) ? 'is-mapped' : null, text: k }))))));
    /* 清洗规则只放一个示例，完整说明放在悬停提示里 */
    const RULE_EG = { '统一字段与类型': '输出词元数 → output_tokens', '保留真实缺失': '空单元格 → null，不补 0', '区分评分含义': 'metric_name 区分评分口径', '保持物理计数': '共享初稿只计 1 次' };
    $('#rule-list').replaceChildren(...d.rules.map(r => h('li', { title: r.text }, h('h4', { text: r.title }), h('p', null, h('code', { text: RULE_EG[r.title] || r.text })))));
    const note = $('#unified-note');
    if (note) note.replaceChildren(
      h('span', null, h('b', { 'data-bind': 'allRecords', text: fmt(M.records) }), '份本页选用回答'),
      h('span', null, h('b', { text: String(d.headers.length) }), '列统一字段'),
      h('span', null, h('b', { text: fmt(M.content.excludedRecords || 0) }), '条环境排除，评分留空'));
    if (note) note.title = '原 248,586 行和新补充 24,600 行分开保存；本页排除历史 Mini 修复批 5,576 行，未拼接覆盖原统一表。';
    draw();
  }

  /* ================= 7. 图版 I：Token 投入与边际收益 ================= */
  function plateBudget(M) {
    const data = { gsm8k: M.rows('budget-log-gsm8k'), math500: M.rows('budget-log-math500'), mmlu: M.rows('budget-log-mmlu') };
    const fit = rows => {
      const xs = rows.map(r => Math.log(r.mean_tokens)), ys = rows.map(r => r.score_pct), n = rows.length;
      const mx = xs.reduce((a, b) => a + b, 0) / n, my = ys.reduce((a, b) => a + b, 0) / n;
      const b = xs.reduce((a, x, i) => a + (x - mx) * (ys[i] - my), 0) / xs.reduce((a, x) => a + (x - mx) ** 2, 0), a0 = my - b * mx;
      const r2 = 1 - ys.reduce((a, y, i) => a + (y - a0 - b * xs[i]) ** 2, 0) / ys.reduce((a, y) => a + (y - my) ** 2, 0);
      return { a: a0, b, r2 };
    };
    const fits = Object.fromEntries(Object.entries(data).map(([k, v]) => [k, fit(v)]));
    { const kpi = $('#plate-budget .kpi'); if (kpi) kpi.textContent = 'R² = ' + TASKS.map(t => fits[t.id].r2.toFixed(2)).join(' / '); }
    let task = 'gsm8k', axis = 'linear';
    const level = r => +/\((\d+)\)/.exec(r.prompt)[1];
    const c = chart($('#chart-budget'), {
      fill: true,
      label: () => `${TASK[task].name}：七档词数上限下的实际输出 Token 与规则评分`,
      height: W => Math.max(280, Math.min(400, W * 0.56)),
      draw(svg, c) {
        const rows = data[task], F = fits[task];
        const L = 52, R = c.W - 20, T = 30, B = c.H - 44;
        const maxT = Math.max(...rows.map(r => r.mean_tokens));
        const x = axis === 'log' ? logScale(1, 200, L, R) : linear(0, niceRange(0, maxT, 4)[1], L, R);
        const y = linear(0, 100, B, T);
        axisY(svg, y, [0, 25, 50, 75, 100], L, R, v => v + '%');
        const xt = axis === 'log' ? [1, 2, 5, 10, 20, 50, 100, 200] : ticks(0, x.d[1], 4);
        axisX(svg, x, xt, B, v => fmt(v));
        s('line', { class: 'axis', x1: L, x2: R, y1: B, y2: B }, svg);
        text(svg, (L + R) / 2, c.H - 6, axis === 'log' ? '实际平均输出 Token（对数刻度）' : '实际平均输出 Token', { class: 'axis-title', 'text-anchor': 'middle' });
        text(svg, L - 44, T - 16, '规则评分', { class: 'axis-title' });
        const lo = Math.min(...rows.map(r => r.mean_tokens)), hi = maxT;
        const pts = Array.from({ length: 60 }, (_, i) => { const t = lo * (hi / lo) ** (i / 59); return [x(t), y(F.a + F.b * Math.log(t))]; });
        keyedPath(c, s('path', { fill: 'none', stroke: '#6749e2', 'stroke-width': 2, 'stroke-opacity': 0.55, 'stroke-linecap': 'round' }, svg), 'fit', pts, linePath);
        text(svg, L + 14, T + 12, `对数拟合 R² = ${F.r2.toFixed(3)}`, { class: 'label-strong' });
        text(svg, L + 14, T + 30, 'SR = a + b·ln(Token)', { class: 'label-muted', 'font-size': 11.5 });
        /* 起点标签放在最左三个点的上方，避开坐标轴与拟合线 */
        const lowTop = Math.min(...rows.slice(0, 3).map(r => y(r.score_pct)));
        rows.forEach((r, i) => {
          const cx = x(r.mean_tokens), cy = y(r.score_pct);
          keyed(c, s('circle', { fill: '#6749e2', stroke: PLATE, 'stroke-width': 2 }, svg), 'p' + i, { cx, cy, r: 5.5 });
          if (i === 0) fitText(text(svg, cx - 4, Math.max(T + 46, lowTop - 14), `上限 ${level(r)} 词：${pct(r.score_pct)}`, { class: 'label-muted halo', 'font-size': 11.5 }), L + 2, R);
          if (i === rows.length - 1) fitText(text(svg, cx - 12, cy - 12, `上限 ${level(r)} 词：${pct(r.score_pct)}`, { class: 'label-muted halo', 'text-anchor': 'end', 'font-size': 11.5 }), L, R);
          const hit = s('circle', { class: 'hit', cx: r1(cx), cy: r1(cy), r: 13, tabindex: 0, role: 'img', 'aria-label': `词数上限 ${level(r)}，平均 ${fmt(r.mean_tokens, 1)} Token，得分 ${pct(r.score_pct)}` }, svg);
          bindTip(hit, () => ({ title: `词数上限 ${level(r)}`, rows: [{ label: '规则评分', value: pct(r.score_pct) }, { label: '平均输出', value: fmt(r.mean_tokens, 1) + ' Token' }, { label: '无法解析', value: pct(r.unresolved_pct) }], note: `Qwen2.5 7B · ${TASK[task].name} · ${fmt(r.questions)} 题` }));
        });
      },
    });
    const r2rows = M.rows('budget-fit-comparison');
    const heat = chart($('#chart-budget-r2'), {
      label: '四模型三题库对数拟合 R²',
      height: 188,
      draw(svg, c) {
        const lw = 92, cw = (c.W - lw) / 3, rh = 36, top = 22;
        TASKS.forEach((t, j) => text(svg, lw + cw * j + cw / 2, 14, t.name, { class: 'tick', 'text-anchor': 'middle' }));
        MODELS.forEach((m, i) => {
          const y0 = top + i * rh;
          text(svg, 0, y0 + rh / 2 + 4, m.short, { class: m.id === 'qwen' ? 'label-strong' : 'label-muted' });
          TASKS.forEach((t, j) => {
            const row = r2rows.find(r => modelId(r.row) === m.id && taskId(r.column) === t.id);
            const v = row ? row.value / 100 : NaN, x0 = lw + cw * j;
            const live = m.id === 'qwen', sel = live && t.id === task;
            const rect = s('rect', { class: live ? 'cell' : null, x: r1(x0 + 1), y: r1(y0 + 1), width: r1(cw - 2), height: rh - 2, rx: 4, fill: Number.isFinite(v) ? seq(v) : TRACK, stroke: sel ? INK : 'none', 'stroke-width': sel ? 2 : 0, tabindex: live ? 0 : null, role: live ? 'button' : null, 'aria-label': `${m.name} ${t.name} R² ${fmt(v, 2)}` }, svg);
            text(svg, x0 + cw / 2, y0 + rh / 2 + 4, fmt(v, 2), { 'text-anchor': 'middle', fill: seqText(v), 'font-size': 12.5, 'font-weight': sel ? 600 : 400, 'pointer-events': 'none' });
            bindTip(rect, () => ({ title: `${m.name} · ${t.name}`, rows: [{ label: '对数拟合 R²', value: fmt(v, 3) }], note: live ? '点击切换左图' : '左图只有 Qwen2.5 的逐档数据' }), live ? () => setTask(t.id) : null);
          });
        });
      },
    });
    const seg = segmented($('#budget-task'), TASKS.map(t => ({ id: t.id, label: t.name })), task, id => setTask(id, true));
    segmented($('#budget-axis'), [{ id: 'linear', label: '线性横轴' }, { id: 'log', label: '对数横轴' }], axis, id => { axis = id; c.render(true); });
    const refresh = attachTable($('#plate-budget'), () => ({ caption: `Qwen2.5 7B · ${TASK[task].name}：七档词数上限`, cols: ['词数上限', '平均输出 Token', '规则评分', '无法解析'], rows: data[task].map(r => [level(r), fmt(r.mean_tokens, 1), pct(r.score_pct), pct(r.unresolved_pct)]) }));
    function finding() {
      const rows = data[task], F = fits[task], at = n => rows.find(r => level(r) === n);
      const a = at(1), b = at(15), c50 = at(50), d = at(100);
      const g1 = (b.score_pct - a.score_pct) / (b.mean_tokens - a.mean_tokens), g2 = (d.score_pct - c50.score_pct) / (d.mean_tokens - c50.mean_tokens);
      let t = `七档实测点的对数拟合 R² = ${F.r2.toFixed(3)}。`;
      if (task === 'mmlu') {
        const w5 = at(5);
        t += `选择题只写 1 个词时直接给出选项，得分 ${pct(a.score_pct)}；放宽到 5 词反而降到 ${pct(w5.score_pct)}，其中 ${pct(w5.unresolved_pct)} 的回答无法解析。对数关系在这里只是粗略描述，三个题库中拟合最弱。`;
      } else {
        t += `从 1 词放宽到 15 词，平均输出多 ${fmt(b.mean_tokens - a.mean_tokens, 1)} 个 Token，得分提高 ${fmt(b.score_pct - a.score_pct, 1)} 个百分点；从 50 词放宽到 100 词，输出多 ${fmt(d.mean_tokens - c50.mean_tokens, 1)} 个 Token，得分提高 ${fmt(d.score_pct - c50.score_pct, 1)} 个百分点。每个 Token 换来的提分约从 ${fmt(g1, 2)} 降到 ${fmt(g2, 2)} 个百分点。`;
      }
      $('#budget-finding').textContent = t;
    }
    function setTask(id, fromSeg) { task = id; if (!fromSeg) seg.set(id); c.render(true); heat.render(false); finding(); refresh(); }
    finding();
  }

  /* ================= 8. 图版 II：模型规模与任务表现 ================= */
  function plateScale(M) {
    const SERIES = [{ id: '直接回答', label: '只给答案', shape: 'circle', hollow: true }, { id: '分步回答', label: '默认分步', shape: 'circle' }, { id: '简洁分步', label: '简洁分步', shape: 'diamond' }];
    let task = 'gsm8k';
    const get = (t, m, sid) => { const r = M.rows('scale-models-' + t).find(x => modelId(x.category) === m && x.series === sid); return r ? r.value : NaN; };
    $('#chart-scale').before(legendRow(SERIES.map(sr => ({ shape: sr.shape, hollow: sr.hollow, label: sr.label }))));
    const c = chart($('#chart-scale'), {
      fill: true,
      label: () => `${TASK[task].name}：四个模型在三种回答组织下的规则评分`,
      height: W => (W < 560 ? 4 * 58 + 52 : 4 * 54 + 52),
      draw(svg, c) {
        const narrow = c.W < 560, lw = narrow ? 92 : 168, L = lw + 12, R = c.W - 70, top = 16, rh = rowsH(c, 4, 58, narrow ? 58 : 54, 30);
        const x = linear(0, 100, L, R), B = top + rh * 4, compact = rh < 34;
        for (const v of [0, 25, 50, 75, 100]) { s('line', { class: 'grid', x1: r1(x(v)), x2: r1(x(v)), y1: top, y2: B }, svg); text(svg, x(v), B + 17, v + '%', { class: 'tick', 'text-anchor': 'middle' }); }
        /* 高度不够时，轴标题放到刻度行右端，避免与刻度重叠 */
        if (c.H - B >= 40) text(svg, (L + R) / 2, Math.min(c.H - 3, B + 36), '规则评分', { class: 'axis-title', 'text-anchor': 'middle' });
        else text(svg, R + 22, B + 17, '规则评分', { class: 'axis-title' });
        MODELS.forEach((m, i) => {
          const cy = top + i * rh + rh / 2;
          if (compact) { /* 行高不够两行时：名称与参数并排，激活参数留在提示与数据表里 */
            const t = s('text', { x: 0, y: r1(cy + 4) }, svg);
            s('tspan', { class: 'label-strong', text: narrow ? m.short : m.name }, t);
            s('tspan', { class: 'label-muted', dx: 6, text: m.params + (m.active ? ' 骨干' : ' 稠密') }, t);
          } else {
            text(svg, 0, cy - 2, narrow ? m.short : m.name, { class: 'label-strong' });
            text(svg, 0, cy + 15, narrow ? m.params : paramLabel(m), { class: 'label-muted' });
          }
          const vals = SERIES.map(sr => get(task, m.id, sr.id));
          const lo = Math.min(...vals), hi = Math.max(...vals);
          keyed(c, s('line', { stroke: m.color, 'stroke-width': 2, 'stroke-opacity': 0.4, 'stroke-linecap': 'round' }, svg), 'l' + m.id, { x1: x(lo), x2: x(hi), y1: cy, y2: cy });
          SERIES.forEach((sr, k) => {
            const v = vals[k], px = x(v);
            const node = s('path', { fill: sr.hollow ? PLATE : m.color, stroke: m.color, 'stroke-width': 2 }, svg);
            keyedPath(c, node, 'm' + m.id + k, [[px, cy]], p => SHAPES[sr.shape](p[0][0], p[0][1], 5.5));
          });
          text(svg, x(hi) + 12, cy + 4, pct(get(task, m.id, '分步回答')), { class: 'value' });
          const hit = s('rect', { class: 'row-hit', x: 0, y: r1(cy - rh / 2 + 2), width: c.W, height: rh - 4, rx: 8, tabindex: 0, role: 'img', 'aria-label': `${m.name}：` + SERIES.map((sr, k) => `${sr.label} ${pct(vals[k])}`).join('，') }, svg);
          svg.insertBefore(hit, svg.firstChild);
          bindTip(hit, () => ({ title: `${m.name} · ${TASK[task].name}`, rows: SERIES.map((sr, k) => ({ label: sr.label, value: pct(vals[k]), color: m.color, dot: true })), note: paramNote(m) }));
        });
        text(svg, R + 12, Math.max(13, top - 4), '默认分步', { class: 'label-muted' });
      },
    });
    const refresh = attachTable($('#plate-scale'), () => ({ caption: `${TASK[task].name}：三种回答组织的规则评分（%）；MoE 为骨干参数`, cols: ['模型', '参数规模', '每 token 激活', ...SERIES.map(s2 => s2.label)], rows: MODELS.map(m => [m.name, m.params, m.active || m.params, ...SERIES.map(sr => fmt(get(task, m.id, sr.id), 1))]) }));
    function finding() {
      const dc = MODELS.map(m => ({ m, v: get(task, m.id, '分步回答'), n: get(task, m.id, '直接回答'), c: get(task, m.id, '简洁分步') }));
      const best = dc.reduce((a, b) => (b.v > a.v ? b : a)), worst = dc.reduce((a, b) => (b.v < a.v ? b : a));
      const gap = dc.reduce((a, b) => (b.v - b.n > a.v - a.n ? b : a));
      let t = `默认分步时，${best.m.name} 最高（${pct(best.v)}），${worst.m.name} 最低（${pct(worst.v)}）。从只给答案到默认分步，${gap.m.name} 变化最大：${pct(gap.n)} → ${pct(gap.v)}。`;
      if (task === 'math500') { const q3 = dc.find(x => x.m.id === 'qwen3'); t += `Qwen3 改用简洁分步，从 ${pct(q3.v)} 升到 ${pct(q3.c)}。`; }
      // 规模：两款 MoE（552B / 770B）对两款约 8B 稠密模型
      const big = dc.filter(x => x.m.active), dense = dc.filter(x => !x.m.active);
      const bigLow = big.reduce((a, b) => (b.v < a.v ? b : a)), denseHigh = dense.reduce((a, b) => (b.v > a.v ? b : a));
      const lead = bigLow.v - denseHigh.v;
      if (lead >= 3) t += `两款 MoE 大模型都比约 8B 的稠密模型高 ${fmt(lead, 1)} pp 以上`;
      else if (lead > -3) t += `骨干 ${bigLow.m.params} 的 ${bigLow.m.name} 与 ${denseHigh.m.params} 的 ${denseHigh.m.name} 只差 ${fmt(Math.abs(lead), 1)} pp`;
      else t += `${denseHigh.m.name} 反而高于 ${bigLow.m.name}`;
      const ds = MODEL.deepseek, hy = MODEL.hy4, vDs = get(task, 'deepseek', '分步回答'), vHy = get(task, 'hy4', '分步回答');
      t += vDs > vHy ? `；参数更少的 ${ds.short}（${ds.params}）高于 ${hy.short}（${hy.params}）。` : '。';
      t += '四个模型架构与代际不同，排序不能只归因于参数量。';
      $('#scale-finding').textContent = t;
      const kpi = $('#plate-scale .kpi'); if (kpi) kpi.textContent = `默认分步：最高与最低差 ${fmt(best.v - worst.v, 1)} pp`;
    }
    segmented($('#scale-task'), TASKS.map(t => ({ id: t.id, label: t.name })), task, id => { task = id; c.render(true); finding(); refresh(); });
    finding();
  }

  /* ================= 9. 图版 III：简洁思考 ================= */
  function plateConcise(M) {
    /* 区间：数学与选择题、文档问答取研究快照中的按题配对 bootstrap；代码生成取 CODE_CONCISE_CI（同法由逐条记录计算） */
    const docComps = ((M.raw.summary.comparisons || {}).document_qa || []).filter(x => x.scope === 'paired_prompts' && x.metric === 'final_contains' && x.first === 'BeConcise' && x.second === 'DefaultCoT');
    const pts = M.rows('concise-cross-task').map(r => {
      const mid = modelId(r.model), t = taskId(r.task);
      const shape = r.group === '文档问答' ? 'square' : r.group === '代码生成' ? 'triangle' : 'circle';
      const tname = TASK[t] ? TASK[t].name : r.group === '文档问答' ? '文档问答' : '代码生成';
      let lo = null, hi = null, how = '';
      if (TASK[t]) { const comp = M.comps.find(x => x.first === 'BeConcise' && x.second === 'DefaultCoT' && x.model_id === mid && x.benchmark === t); if (comp) { lo = comp.ci_low_pp; hi = comp.ci_high_pp; how = '按题配对 bootstrap，200 题'; } }
      else if (shape === 'square') { const comp = docComps.find(x => x.model_id === mid); if (comp) { lo = comp.ci_low_pp; hi = comp.ci_high_pp; how = `按题配对 bootstrap，${fmt(comp.independent_questions)} 题`; } }
      else if (CODE_CONCISE_CI[mid]) { [lo, hi] = CODE_CONCISE_CI[mid]; how = '按题聚类 bootstrap，193 题 × 5 次采样'; }
      return { ...r, mid, tname, shape, lo, hi, how };
    });
    $('#chart-concise').before(legendRow([...MODELS.map(m => ({ color: m.color, label: m.short })), { shape: 'circle', label: '数学/选择题' }, { shape: 'square', label: '文档问答' }, { shape: 'triangle', label: '代码生成' }]));
    chart($('#chart-concise'), {
      fill: true,
      label: '17 组模型与任务：输出减少比例与得分变化',
      height: W => Math.max(300, Math.min(420, W * 0.6)),
      draw(svg, c) {
        const L = 46, R = c.W - 16, T = 22, B = c.H - 42;
        const x = linear(0, 60, L, R), y = linear(-6, 18, B, T);
        axisY(svg, y, [-5, 0, 5, 10, 15], L, R, v => signed(v, 0));
        axisX(svg, x, [0, 10, 20, 30, 40, 50, 60], B, v => v + '%', [T, B]);
        s('line', { class: 'zero', x1: L, x2: R, y1: r1(y(0)), y2: r1(y(0)) }, svg);
        s('rect', { x: L, y: T, width: R - L, height: r1(y(0) - T), fill: ACC, 'fill-opacity': 0.07 }, svg);
        text(svg, R - 4, T + 14, '省 Token，得分不降', { class: 'label-muted', 'text-anchor': 'end', 'font-size': 11.5 });
        text(svg, (L + R) / 2, c.H - 4, '输出 Token 减少（相对默认分步）', { class: 'axis-title', 'text-anchor': 'middle' });
        text(svg, L - 40, T - 8, '得分变化（百分点）', { class: 'axis-title' });
        for (const p of pts) if (p.lo != null) s('line', { x1: r1(x(p.saving)), x2: r1(x(p.saving)), y1: r1(y(p.lo)), y2: r1(y(p.hi)), stroke: MODEL[p.mid].color, 'stroke-width': 1.5, 'stroke-opacity': 0.45 }, svg);
        for (const p of pts) {
          const px = x(p.saving), py = y(p.delta), col = MODEL[p.mid].color;
          s('path', { d: SHAPES[p.shape](px, py, 5.5), fill: col, stroke: PLATE, 'stroke-width': 2 }, svg);
          const hit = s('circle', { class: 'hit', cx: r1(px), cy: r1(py), r: 12, tabindex: 0, role: 'img', 'aria-label': `${MODEL[p.mid].name} ${p.tname}：输出减少 ${fmt(p.saving, 1)}%，得分变化 ${signed(p.delta)}` }, svg);
          bindTip(hit, () => ({ title: `${MODEL[p.mid].name} · ${p.tname}`, rows: [{ label: '输出减少', value: fmt(p.saving, 1) + '%' }, { label: '得分变化', value: signed(p.delta) + ' pp' }].concat(p.lo != null ? [{ label: '95% 区间', value: ci(p.lo, p.hi) }] : []), note: p.how }));
        }
        /* 注记带描边底色，压在区间竖线上也能读清 */
        const hero = pts.find(p => p.mid === 'qwen' && taskId(p.task) === 'gsm8k');
        if (hero) {
          const hx = x(hero.saving), hy = y(hero.delta), ly = Math.min(B - 6, Math.max(y(-4.2), y(-1) + 17));
          const lab = fitText(text(svg, hx + 34, ly, `Qwen2.5 · GSM8K：Token −${fmt(hero.saving, 1)}%，得分 ${signed(hero.delta)}`, { class: 'label-strong halo' }), L + 4, R - 4);
          s('path', { d: `M${r1(hx)},${r1(hy + 8)}L${r1(Math.max(+lab.getAttribute('x'), hx))},${r1(ly - 13)}`, stroke: INK3, 'stroke-width': 1, fill: 'none' }, svg);
        }
        const top = pts.reduce((a, b) => (b.delta > a.delta ? b : a));
        fitText(text(svg, x(top.saving) + 10, y(top.delta) + 4, `${MODEL[top.mid].short} · ${top.tname} ${signed(top.delta)}`, { class: 'label-muted halo' }), L, R);
      },
    });
    const base = M.rows('concise-baseline');
    const mini = chart($('#chart-concise-mini'), {
      label: 'Qwen2.5 7B GSM8K 三种回答组织的得分与输出 Token',
      height: 236,
      draw(svg, c) {
        const lw = 66, R = c.W - 52;
        const panel = (y0, title, key, max, unit, dfmt) => {
          text(svg, 0, y0, title, { class: 'label-muted', 'font-size': 11.5 });
          const x = linear(0, max, lw, R);
          base.forEach((r, i) => {
            const by = y0 + 12 + i * 28;
            text(svg, 0, by + 12, SHORT[r.prompt] || r.prompt, { 'font-size': 12 });
            s('rect', { x: lw, y: by, width: R - lw, height: 16, fill: TRACK, rx: 3 }, svg);
            s('path', { d: hbar(lw, x(r[key]), by, 16), fill: '#6749e2', 'fill-opacity': r.prompt === 'BeConcise' ? 1 : 0.5 }, svg);
            text(svg, x(r[key]) + 6, by + 12.5, dfmt(r[key]) + unit, { class: 'value', 'font-size': 12 });
          });
        };
        panel(12, '规则评分（0–100%）', 'score_pct', 100, '%', v => fmt(v, 1));
        panel(132, '平均输出 Token（0–300）', 'mean_tokens', 300, '', v => fmt(v, 1));
      },
    });
    void mini;
    attachTable($('#plate-concise'), () => ({ caption: '“简洁分步”相对“默认分步”：17 组配对', cols: ['模型', '任务', '输出减少', '得分变化（pp）', '95% 区间'], rows: pts.map(p => [MODEL[p.mid].name, p.tname, fmt(p.saving, 1) + '%', signed(p.delta), p.lo != null ? ci(p.lo, p.hi) : '—']) }));
    const neg = pts.filter(p => p.delta < 0), keep = pts.length - neg.length, shorter = pts.filter(p => p.saving > 0).length;
    const cross = pts.filter(p => p.lo != null && p.lo <= 0 && p.hi >= 0).length;
    const sv = pts.map(p => p.saving);
    const b0 = base.find(r => r.prompt === 'DefaultCoT'), b1 = base.find(r => r.prompt === 'BeConcise');
    const nums = ['两', '三', '四', '五'];
    $('#concise-finding').textContent = `${pts.length} 组${shorter === pts.length ? '输出全部缩短' : `中 ${shorter} 组输出缩短`}，幅度 ${fmt(Math.min(...sv), 1)}%–${fmt(Math.max(...sv), 1)}%；${keep} 组得分点估计持平或提高。` + (neg.length ? `下降的${nums[neg.length - 2] || ' ' + neg.length + ' '}组是 ` + neg.map(p => `${MODEL[p.mid].short} · ${p.tname}（${signed(p.delta)}${p.lo != null ? '，区间 ' + ci(p.lo, p.hi) : ''}）`).join('与 ') + '。' : '') + `Qwen2.5 在 GSM8K 上平均输出从 ${fmt(b0.mean_tokens, 1)} 降到 ${fmt(b1.mean_tokens, 1)} Token，得分 ${pct(b0.score_pct)} → ${pct(b1.score_pct)}。${cross} 组区间跨过 0：点估计持平不等于已证明等效。`;
    const kpi = $('#plate-concise .kpi'); if (kpi) kpi.textContent = `${shorter}/${pts.length} 省 Token，${keep}/${pts.length} 不降分`;
  }

  /* ================= 10. 图版 IV：极端限长与输出反弹 ================= */
  function plateLimits(M) {
    const rows = M.rows('limits-rebound-ratios').map(r => { const [mn, tn] = r.label.split(' / '); return { ...r, mid: modelId(mn), tid: taskId(tn) }; });
    let sel = rows.findIndex(r => r.mid === 'deepseek' && r.tid === 'math500'); if (sel < 0) sel = 0;
    const bars = chart($('#chart-limits'), {
      fill: true,
      label: '字母上限从 100 收紧到 10 时，实际输出的倍数',
      height: W => rows.length * (W < 520 ? 42 : 30) + 52,
      draw(svg, c) {
        /* 矮屏时行高可压到 11px，字号与条宽随之收紧，12 行始终放得下 */
        const narrow = c.W < 520, lw = narrow ? 0 : Math.min(190, c.W * 0.4), L = lw + 8, R = c.W - 44, top = 26;
        const rh = c.fill ? Math.max(11, Math.min((narrow ? 42 : 30) * 2, (c.H - 48) / rows.length)) : (narrow ? 42 : 30), compact = !narrow && rh < 18;
        const fs = compact ? { style: 'font-size:11px' } : {};
        const x = logScale(0.1, 10, L, R), x1 = x(1);
        for (const v of narrow ? [0.1, 0.5, 1, 2, 10] : [0.1, 0.25, 0.5, 1, 2, 4, 10]) { s('line', { class: v === 1 ? 'zero' : 'grid', x1: r1(x(v)), x2: r1(x(v)), y1: top - 6, y2: top + rows.length * rh }, svg); text(svg, x(v), 14, '×' + v, { class: 'tick', 'text-anchor': 'middle' }); }
        rows.forEach((r, i) => {
          const y0 = top + i * rh, m = MODEL[r.mid], bh = Math.max(5, Math.min(14, rh - 6)), by = narrow ? y0 + 20 : y0 + (rh - 2 - bh) / 2;
          const hit = s('rect', { class: 'row-hit' + (i === sel ? ' is-selected' : ''), x: 0, y: y0, width: c.W, height: Math.max(1, rh - 2), rx: 6, tabindex: 0, role: 'img', 'aria-label': `${m.name} ${TASK[r.tid].name}：${fmt(r.tokens_at_100_letters, 1)} → ${fmt(r.tokens_at_10_letters, 1)} Token，${fmt(r.ratio, 2)} 倍` }, svg);
          s('circle', { cx: 6, cy: r1(narrow ? y0 + 10 : y0 + rh / 2 - 1), r: compact ? 3.2 : 4, fill: m.color }, svg);
          text(svg, 16, narrow ? y0 + 14 : y0 + rh / 2 + (compact ? 2.5 : 3), `${m.short} · ${TASK[r.tid].name}`, { class: i === sel ? 'label-strong' : null, ...fs });
          s('path', { d: hbar(x1, x(r.ratio), by, bh), fill: m.color }, svg);
          const right = r.ratio >= 1;
          text(svg, right ? x(r.ratio) + 6 : x1 + 6, by + bh / 2 + 4, '×' + fmt(r.ratio, r.ratio < 1 ? 2 : 1), { class: 'value', ...fs });
          bindTip(hit, () => ({ title: `${m.name} · ${TASK[r.tid].name}`, rows: [{ label: '字母上限 100', value: fmt(r.tokens_at_100_letters, 1) + ' Token' }, { label: '字母上限 10', value: fmt(r.tokens_at_10_letters, 1) + ' Token' }, { label: '倍数', value: '×' + fmt(r.ratio, 2) }], note: '倍数 = 上限 10 时 ÷ 上限 100 时的平均输出，每格 200 题' }));
        });
        text(svg, x1 + 6, c.H - 6, '更长', { class: 'label-muted', 'font-size': 11.5 });
        text(svg, x1 - 6, c.H - 6, '更短', { class: 'label-muted', 'font-size': 11.5, 'text-anchor': 'end' });
      },
    });
    const FAMS = [{ key: 'WordLimit', name: '词数上限', unit: '词', levels: [1, 5, 10, 15, 25, 50, 100] }, { key: 'CharLimit', name: '字母上限', unit: '字母', levels: [10, 50, 100, 500] }, { key: 'TokenLimit', name: 'Token 上限', unit: 'Token', levels: [10, 50, 100, 500] }];
    const host = $('#chart-limits-detail');
    const minis = FAMS.map(f => { const div2 = h('div', { class: 'chart' }); host.append(div2); return { f, el: div2 }; });
    let charts = [];
    function detail() {
      const r = rows[sel], m = MODEL[r.mid];
      $('#limits-detail-title').textContent = `${m.name} 在 ${TASK[r.tid].name} 上：三类上限下的实际输出`;
      charts = minis.map((mm, k) => mm.chart ? (mm.chart.render(true), mm.chart) : (mm.chart = chart(mm.el, {
        label: () => `${FAMS[k].name}：实际平均输出 Token`,
        height: 190,
        draw(svg, c) {
          const rr = rows[sel], mod = MODEL[rr.mid], f = FAMS[k];
          const ser = f.levels.map(n => ({ ...cell(M, rr.mid, rr.tid, `${f.key}(${n})`), level: n }));
          const ym = niceRange(0, Math.max(...FAMS.flatMap(ff => ff.levels.map(n => cell(M, rr.mid, rr.tid, `${ff.key}(${n})`).tokens))), 4)[1];
          const L = 40, R = c.W - 10, T = 22, B = c.H - 36;
          const x = logScale(f.levels[0], f.levels[f.levels.length - 1], L + 6, R - 6), y = linear(0, ym, B, T);
          text(svg, 0, 12, f.name, { class: 'label-strong', 'font-size': 12.5 });
          axisY(svg, y, ticks(0, ym, 3), L, R, v => fmt(v));
          (f.key === 'WordLimit' ? [1, 10, 100] : [10, 100, 500]).forEach(n => text(svg, x(n), B + 16, n, { class: 'tick', 'text-anchor': 'middle' }));
          text(svg, (L + R) / 2, c.H - 4, `上限（${f.unit}）`, { class: 'axis-title', 'text-anchor': 'middle', 'font-size': 11 });
          if (f.key === 'TokenLimit') { s('line', { x1: r1(x(f.levels[0])), y1: r1(y(Math.min(f.levels[0], ym))), x2: r1(x(Math.min(ym, f.levels[f.levels.length - 1]))), y2: r1(y(Math.min(ym, f.levels[f.levels.length - 1]))), stroke: INK3, 'stroke-width': 1, 'stroke-opacity': 0.6 }, svg); text(svg, x(Math.min(ym, 500)) - 4, y(Math.min(ym, 500)) - 6, '上限线', { class: 'label-muted', 'font-size': 10.5, 'text-anchor': 'end' }); }
          const p = ser.map(q => [x(q.level), y(q.tokens)]);
          keyedPath(c, s('path', { fill: 'none', stroke: mod.color, 'stroke-width': 2, 'stroke-linejoin': 'round' }, svg), 'line', p, linePath);
          ser.forEach((q, i) => {
            keyed(c, s('circle', { fill: mod.color, stroke: PLATE, 'stroke-width': 2 }, svg), 'c' + i, { cx: p[i][0], cy: p[i][1], r: 4.5 });
            const hit = s('circle', { class: 'hit', cx: r1(p[i][0]), cy: r1(p[i][1]), r: 12, tabindex: 0, role: 'img', 'aria-label': `${f.name} ${q.level}：${fmt(q.tokens, 1)} Token` }, svg);
            bindTip(hit, () => ({ title: `${f.name} ${q.level} ${f.unit}`, rows: [{ label: '实际平均输出', value: fmt(q.tokens, 1) + ' Token' }, { label: '规则评分', value: pct(q.score) }, { label: '截断率', value: pct(q.trunc) }], note: `${mod.name} · ${TASK[rr.tid].name} · 200 题` }));
          });
        },
      })));
      void charts;
      refresh();
    }
    const refresh = attachTable($('#plate-limits'), () => {
      const r = rows[sel];
      return { caption: `字母上限 100 → 10 时的输出倍数（${rows.length} 组，每格 200 题）`, cols: ['模型 · 题库', '上限 100 字母（Token）', '上限 10 字母（Token）', '倍数'], rows: rows.map(x => [`${MODEL[x.mid].name} · ${TASK[x.tid].name}`, fmt(x.tokens_at_100_letters, 1), fmt(x.tokens_at_10_letters, 1), '×' + fmt(x.ratio, 2)]) };
    });
    detail();
    const up = rows.filter(r => r.ratio > 1), ds = rows.find(r => r.mid === 'deepseek' && r.tid === 'math500'), dsg = rows.find(r => r.mid === 'deepseek' && r.tid === 'gsm8k');
    const shrink = rows.filter(r => r.ratio < 1).map(r => MODEL[r.mid].short);
    const shrinkModels = [...new Set(shrink)];
    $('#limits-finding').textContent = `${rows.length} 组中有 ${up.length} 组在限制收紧后输出变长。DeepSeek Flash 在 MATH500 上，字母上限 100 时平均输出 ${fmt(ds.tokens_at_100_letters, 1)} Token，上限 10 时达到 ${fmt(ds.tokens_at_10_letters, 1)} Token，约 ${fmt(ds.ratio, 1)} 倍；GSM8K 上为 ${fmt(dsg.ratio, 1)} 倍。只有 ${shrinkModels.join('、')} 的 ${shrink.length} 组按指令缩短。分析报告另记录 Qwen3 在 Token 上限 10 的提示下，三个题库共 600 条回答全部超过 10 个 Token。提示里的长度要求只是软约束，实际输出需要单独测量。`;
    const kpi = $('#plate-limits .kpi'); if (kpi) kpi.textContent = `${up.length}/${rows.length} 组反弹，最高 ×${fmt(Math.max(...rows.map(r => r.ratio)), 1)}`;
  }

  /* ================= 11. 图版 V：数学中的中文作答模板 ================= */
  function plateLanguage(M) {
    const data = M.rows('language-cost-quality');
    const METRICS = [
      { id: 'score', label: '规则评分', a: 'default_score_pct', b: 'chinese_score_pct', unit: '%', domain: () => [0, 100], f: v => pct(v), d: v => signed(v) + ' pp' },
      { id: 'tokens', label: '平均输出 Token', a: 'default_tokens', b: 'chinese_tokens', unit: '', domain: () => [0, 600], f: v => fmt(v, 1), d: v => signed(v, 1) },
      { id: 'trunc', label: '截断率', a: 'default_truncation_pct', b: 'chinese_truncation_pct', unit: '%', domain: () => [0, 40], f: v => pct(v), d: v => signed(v) + ' pp' },
    ];
    let metric = 'score', task = 'math500';
    const row = (m, t) => data.find(r => r.model === m && r.task === t);
    $('#chart-language').before(legendRow([{ shape: 'circle', hollow: true, label: '默认分步' }, { shape: 'circle', label: '中文作答' }]));
    const c = chart($('#chart-language'), {
      fill: true,
      label: () => `${TASK[task].name}：默认分步与中文作答的${METRICS.find(m => m.id === metric).label}`,
      height: W => (W < 560 ? 4 * 56 + 50 : 4 * 52 + 50),
      draw(svg, c) {
        const mt = METRICS.find(m => m.id === metric), narrow = c.W < 560;
        const lw = narrow ? 76 : 120, L = lw + 10, R = c.W - (narrow ? 96 : 130), top = 14, rh = rowsH(c, 4, 50, narrow ? 56 : 52, 30), B = top + rh * 4;
        /* 横轴按当前数据取范围：点图不必从 0 起，差异才看得清 */
        const vals = MODELS.flatMap(m => { const r = row(m.id, task); return r ? [r[mt.a], r[mt.b]] : []; });
        let [d0, d1] = mt.id === 'score' ? niceRange(Math.max(0, Math.min(...vals) - 8), Math.min(100, Math.max(...vals) + 8), 4) : [0, niceRange(0, Math.max(...vals) * 1.12, 4)[1]];
        if (!(d1 > d0)) d1 = d0 + (mt.unit === '%' ? 10 : 100);
        const x = linear(d0, d1, L, R);
        for (const v of ticks(d0, d1, 4)) { s('line', { class: 'grid', x1: r1(x(v)), x2: r1(x(v)), y1: top, y2: B }, svg); text(svg, x(v), B + 18, mt.unit === '%' ? v + '%' : fmt(v), { class: 'tick', 'text-anchor': 'middle' }); }
        const title = mt.label + (mt.unit === '%' ? '（%）' : '');
        if (c.H - B >= 36) text(svg, (L + R) / 2, c.H - 4, title, { class: 'axis-title', 'text-anchor': 'middle' });
        else text(svg, R + 22, B + 18, title, { class: 'axis-title' });
        const dot = Math.max(5.5, Math.min(8, rh * 0.1));
        MODELS.forEach((m, i) => {
          const r = row(m.id, task); if (!r) return;
          const cy = top + i * rh + rh / 2, va = r[mt.a], vb = r[mt.b];
          text(svg, 0, cy + 4, narrow ? m.short : m.name, { class: 'label-strong' });
          keyed(c, s('line', { stroke: m.color, 'stroke-width': 3, 'stroke-linecap': 'round' }, svg), 'l' + m.id, { x1: x(va), x2: x(vb), y1: cy, y2: cy });
          keyed(c, s('circle', { fill: PLATE, stroke: m.color, 'stroke-width': 2 }, svg), 'a' + m.id, { cx: x(va), cy, r: dot });
          keyed(c, s('circle', { fill: m.color, stroke: PLATE, 'stroke-width': 2 }, svg), 'b' + m.id, { cx: x(vb), cy, r: dot + 1 });
          text(svg, R + 14, cy - 2, mt.f(vb), { class: 'value' });
          text(svg, R + 14, cy + 15, mt.d(vb - va), { class: 'label-muted' });
          const hit = s('rect', { class: 'row-hit', x: 0, y: r1(cy - rh / 2 + 2), width: c.W, height: rh - 4, rx: 8, tabindex: 0, role: 'img', 'aria-label': `${m.name}：${mt.label} ${mt.f(va)} → ${mt.f(vb)}` }, svg);
          svg.insertBefore(hit, svg.firstChild);
          bindTip(hit, () => ({ title: `${m.name} · ${TASK[task].name}`, rows: [{ label: '规则评分', value: `${pct(r.default_score_pct)} → ${pct(r.chinese_score_pct)}` }, { label: '平均输出', value: `${fmt(r.default_tokens, 0)} → ${fmt(r.chinese_tokens, 0)}` }, { label: '截断率', value: `${pct(r.default_truncation_pct)} → ${pct(r.chinese_truncation_pct)}` }], note: '默认分步 → 中文作答，每格 200 题' }));
        });
      },
    });
    const mat = chart($('#chart-language-matrix'), {
      label: '中文减默认的得分差：四模型 × 三题库',
      height: 188,
      draw(svg, c) {
        const lw = 70, cw = (c.W - lw) / 3, rh = 36, top = 22;
        TASKS.forEach((t, j) => {
          const x0 = lw + cw * j, sel = t.id === task;
          text(svg, x0 + cw / 2, 14, t.name, { class: sel ? 'label-strong' : 'tick', 'text-anchor': 'middle', 'font-size': 11.5 });
          const col = s('rect', { class: 'cell', x: r1(x0), y: top - 2, width: r1(cw), height: rh * 4 + 4, rx: 6, fill: 'transparent', 'pointer-events': 'all', stroke: sel ? INK : 'transparent', 'stroke-width': 2, tabindex: 0, role: 'button', 'aria-pressed': String(sel), 'aria-label': `切换到 ${t.name}` }, svg);
          bindTip(col, () => ({ title: t.name, rows: MODELS.map(m => { const r = row(m.id, t.id); return { label: m.short, value: signed(r.score_difference_pp) + ' pp', color: m.color, dot: true }; }), note: '点击切换左图' }), () => { task = t.id; tseg.set(task); c2render(); });
        });
        MODELS.forEach((m, i) => {
          const y0 = top + i * rh;
          text(svg, 0, y0 + rh / 2 + 4, m.short, { class: 'label-muted', 'font-size': 12 });
          TASKS.forEach((t, j) => {
            const r = row(m.id, t.id), v = r.score_difference_pp, x0 = lw + cw * j;
            s('rect', { x: r1(x0 + 3), y: r1(y0 + 1), width: r1(cw - 6), height: rh - 2, rx: 4, fill: div(v / 12), 'pointer-events': 'none' }, svg);
            text(svg, x0 + cw / 2, y0 + rh / 2 + 4, signed(v), { 'text-anchor': 'middle', fill: divText(v / 12), 'font-size': 12.5, 'pointer-events': 'none' });
          });
        });
      },
    });
    function c2render() { c.render(true); mat.render(false); finding(); refresh(); }
    segmented($('#language-metric'), METRICS.map(m => ({ id: m.id, label: m.label })), metric, id => { metric = id; c.render(true); refresh(); });
    const tseg = segmented($('#language-task'), TASKS.map(t => ({ id: t.id, label: t.name })), task, id => { task = id; c2render(); });
    const refresh = attachTable($('#plate-language'), () => ({ caption: `${TASK[task].name}：默认分步与中文作答`, cols: ['模型', '评分（默认 → 中文）', '输出 Token', '截断率', '得分差'], rows: MODELS.map(m => { const r = row(m.id, task); return [m.name, `${pct(r.default_score_pct)} → ${pct(r.chinese_score_pct)}`, `${fmt(r.default_tokens, 1)} → ${fmt(r.chinese_tokens, 1)}`, `${pct(r.default_truncation_pct)} → ${pct(r.chinese_truncation_pct)}`, signed(r.score_difference_pp)]; }) }));
    function finding() {
      const rs = MODELS.map(m => ({ m, r: row(m.id, task) }));
      const up = rs.filter(x => x.r.score_difference_pp > 0.05), shorter = rs.filter(x => x.r.chinese_tokens < x.r.default_tokens);
      const deltas = rs.map(x => x.r.score_difference_pp), saves = rs.map(x => x.r.token_saving_pct);
      const gsm = MODELS.map(m => row(m.id, 'gsm8k').score_difference_pp), gsmDown = gsm.filter(v => v < 0).length;
      let t = `${TASK[task].name} 上，${up.length} 个模型提分，${shorter.length} 个模型缩短输出（减少 ${fmt(Math.min(...saves), 1)}%–${fmt(Math.max(...saves), 1)}%）。`;
      if (up.length) {
        const best = up.reduce((a, b) => (b.r.score_difference_pp > a.r.score_difference_pp ? b : a));
        t += `提分最多的是 ${best.m.name}：${pct(best.r.default_score_pct)} → ${pct(best.r.chinese_score_pct)}（${signed(best.r.score_difference_pp)}），输出 ${fmt(best.r.default_tokens, 0)} → ${fmt(best.r.chinese_tokens, 0)} Token，截断率 ${pct(best.r.default_truncation_pct)} → ${pct(best.r.chinese_truncation_pct)}。`;
        t += `同一模板在 GSM8K 上让 ${gsmDown} 个模型略降（${signed(Math.max(...gsm))} 至 ${signed(Math.min(...gsm))} pp），收益有任务边界。`;
      } else {
        t += `得分变化在 ${signed(Math.min(...deltas))} 至 ${signed(Math.max(...deltas))} 个百分点之间：中文模板在这里只省 Token，不提分。`;
      }
      $('#language-finding').textContent = t;
      const top1 = rs.reduce((a, b) => (b.r.score_difference_pp > a.r.score_difference_pp ? b : a));
      const kpi = $('#plate-language .kpi'); if (kpi) kpi.textContent = up.length ? `提分最多：${top1.m.short} ${signed(top1.r.score_difference_pp)} pp` : `${TASK[task].name} 上没有模型提分`;
    }
    finding();
  }

  /* ================= 12. 图版 VI：文档中的证据位置 ================= */
  function platePosition(M) {
    const prof = M.rows('position-nine-profile'), diff = M.rows('position-model-advantage');
    const series = MODELS.filter(m => prof.some(r => modelId(r.series) === m.id)).map(m => ({ m, pts: prof.filter(r => modelId(r.series) === m.id).sort((a, b) => a.x - b.x) }));
    const xs = series[0].pts.map(p => p.x);
    let hoverX = null;
    const charts = [];
    const legendHost = legendRow(series.map(sr => ({ line: true, color: sr.m.color, label: sr.m.name })).concat([{ color: BANDC, label: '95% 区间' }]));
    $('#chart-position').before(legendHost);
    function crossFor(c) { if (!c.cross) return; if (hoverX == null) { c.cross.setAttribute('visibility', 'hidden'); return; } c.cross.setAttribute('visibility', 'visible'); c.cross.setAttribute('x1', r1(c.x(hoverX))); c.cross.setAttribute('x2', r1(c.x(hoverX))); }
    function setHover(xv, evt) {
      hoverX = xv; charts.forEach(crossFor);
      if (xv == null) { Tip.hide(); return; }
      const d = diff.find(r => r.x === xv);
      const content = { title: `相关资料在第 ${xv} 位`, rows: series.map(sr => { const p = sr.pts.find(q => q.x === xv); return { label: sr.m.name, value: `${pct(p.y)}　${ci(p.low, p.high).replace(/[+±]/g, '')}`, color: sr.m.color }; }).concat(d ? [{ label: 'Qwen3 − Qwen2.5', value: `${signed(d.y)} pp　${ci(d.low, d.high)}` }] : []), note: '方括号为 95% 配对区间' };
      if (evt && evt.clientX != null) Tip.show(evt.clientX, evt.clientY, content); else Tip.at(charts[0].svg, content);
    }
    function overlay(svg, c, L, R, T, B) {
      c.cross = s('line', { class: 'crosshair', x1: 0, x2: 0, y1: T, y2: B, visibility: 'hidden' }, svg);
      const ov = s('rect', { x: L - 10, y: T, width: R - L + 20, height: B - T, fill: 'transparent', tabindex: 0, role: 'img', 'aria-label': '悬停或用左右方向键读取每个位置的数值' }, svg);
      const nearest = px => xs.reduce((a, b) => (Math.abs(c.x(b) - px) < Math.abs(c.x(a) - px) ? b : a));
      ov.addEventListener('pointermove', e => { const r = svg.getBoundingClientRect(); setHover(nearest((e.clientX - r.left) * (c.W / r.width)), e); });
      ov.addEventListener('pointerleave', () => setHover(null));
      ov.addEventListener('blur', () => setHover(null));
      ov.addEventListener('keydown', e => { const k = { ArrowRight: 1, ArrowLeft: -1 }[e.key]; if (!k) return; e.preventDefault(); const i = hoverX == null ? (k > 0 ? 0 : xs.length - 1) : Math.max(0, Math.min(xs.length - 1, xs.indexOf(hoverX) + k)); setHover(xs[i]); });
      ov.addEventListener('focus', () => setHover(hoverX == null ? xs[0] : hoverX));
    }
    charts.push(chart($('#chart-position'), {
      fill: true,
      label: '两个模型在九个证据位置上的最终答案包含率',
      height: W => Math.max(260, Math.min(340, W * 0.34)),
      draw(svg, c) {
        const L = 52, R = c.W - 108, T = 30, B = c.H - 28;
        const x = linear(1, 20, L, R), y = linear(40, 80, B, T); c.x = x;
        axisY(svg, y, [40, 50, 60, 70, 80], L, R, v => v + '%');
        xs.forEach(v => s('line', { class: 'grid', x1: r1(x(v)), x2: r1(x(v)), y1: T, y2: B }, svg));
        s('line', { class: 'axis', x1: L, x2: R, y1: B, y2: B }, svg);
        text(svg, L - 46, T - 16, '最终答案包含率', { class: 'axis-title', 'font-size': 11.5 });
        series.forEach(sr => s('path', { d: bandPath(sr.pts.map(p => [x(p.x), y(p.low), y(p.high)])), fill: sr.m.color, 'fill-opacity': 0.1 }, svg));
        const ends = [];
        series.forEach(sr => {
          s('path', { d: linePath(sr.pts.map(p => [x(p.x), y(p.y)])), fill: 'none', stroke: sr.m.color, 'stroke-width': 2, 'stroke-linejoin': 'round' }, svg);
          sr.pts.forEach(p => s('circle', { cx: r1(x(p.x)), cy: r1(y(p.y)), r: 4.5, fill: sr.m.color, stroke: PLATE, 'stroke-width': 2 }, svg));
          const a = sr.pts[0], z = sr.pts[sr.pts.length - 1];
          ends.push({ y: y(z.y), x: x(z.x), label: `${sr.m.short} ${pct(z.y)}` });
          text(svg, x(a.x) + 8, y(a.y) + (a.y > 60 ? -10 : 18), pct(a.y), { class: 'value', 'font-size': 12 });
        });
        /* 末端标签相距太近时上下错开 */
        ends.sort((p, q) => p.y - q.y);
        for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 15) { const mid = (ends[i].y + ends[i - 1].y) / 2; ends[i - 1].y = mid - 7.5; ends[i].y = mid + 7.5; }
        ends.forEach(e => text(svg, e.x + 10, e.y + 4, e.label, { class: 'label-strong', 'font-size': 12 }));
        overlay(svg, c, L, R, T, B);
      },
    }));
    charts.push(chart($('#chart-position-diff'), {
      fill: true,
      label: 'Qwen3 减 Qwen2.5 的同题差值与 95% 区间',
      height: W => Math.max(214, Math.min(264, W * 0.26)),
      draw(svg, c) {
        const L = 52, R = c.W - 108, T = 26, B = c.H - 40;
        const x = linear(1, 20, L, R), y = linear(-5, 25, B, T); c.x = x;
        axisY(svg, y, [-5, 0, 5, 10, 15, 20, 25], L, R, v => signed(v, 0));
        s('line', { class: 'zero', x1: L, x2: R, y1: r1(y(0)), y2: r1(y(0)) }, svg);
        xs.forEach(v => text(svg, x(v), B + 17, v, { class: 'tick', 'text-anchor': 'middle' }));
        text(svg, (L + R) / 2, c.H - 4, '相关资料在 20 篇中的位置（实测 9 处）', { class: 'axis-title', 'text-anchor': 'middle' });
        text(svg, L - 46, T - 14, 'Qwen3 − Qwen2.5（百分点）', { class: 'axis-title', 'font-size': 11.5 });
        diff.forEach((d, i) => {
          const px = x(d.x), crosses = d.low <= 0;
          s('line', { x1: r1(px), x2: r1(px), y1: r1(y(d.low)), y2: r1(y(d.high)), stroke: INK, 'stroke-width': 1.5, 'stroke-opacity': crosses ? 0.35 : 0.7 }, svg);
          for (const v of [d.low, d.high]) s('line', { x1: r1(px - 4), x2: r1(px + 4), y1: r1(y(v)), y2: r1(y(v)), stroke: INK, 'stroke-width': 1.5, 'stroke-opacity': crosses ? 0.35 : 0.7 }, svg);
          s('circle', { cx: r1(px), cy: r1(y(d.y)), r: 4.5, fill: crosses ? PLATE : INK, stroke: INK, 'stroke-width': 2 }, svg);
          if (i === 0 || i === diff.length - 1) text(svg, px + 9, y(d.y) + 4, signed(d.y), { class: 'value', 'font-size': 12 });
        });
        overlay(svg, c, L, R, T, B);
      },
    }));
    attachTable($('#plate-position'), () => ({ caption: '九个位置的最终答案包含率与模型差值（%，方括号为 95% 区间）', cols: ['位置', ...series.map(sr => sr.m.name), 'Qwen3 − Qwen2.5'], rows: xs.map(v => { const d = diff.find(r => r.x === v); return [v, ...series.map(sr => { const p = sr.pts.find(q => q.x === v); return `${fmt(p.y, 1)} [${fmt(p.low, 1)}, ${fmt(p.high, 1)}]`; }), d ? `${signed(d.y)} ${ci(d.low, d.high)}` : '—']; }) }));
    const first = diff[0], last = diff[diff.length - 1], q3 = series.find(sr => sr.m.id === 'qwen3'), q25 = series.find(sr => sr.m.id === 'qwen');
    const rest = q3.pts.slice(1).map(p => p.y), q25v = q25.pts.map(p => p.y);
    $('#position-finding').textContent = `首位时 Qwen3 领先 ${fmt(first.y, 1)} 个百分点（95% 区间 ${ci(first.low, first.high)}），末位只领先 ${fmt(last.y, 1)}（${ci(last.low, last.high)}，区间含 0）。Qwen3 在首位达到 ${pct(q3.pts[0].y)}，其余八个位置在 ${pct(Math.min(...rest))}–${pct(Math.max(...rest))} 之间；Qwen2.5 在 ${pct(Math.min(...q25v))}–${pct(Math.max(...q25v))} 之间，看不出首位优势。模型差距取决于证据放在哪里。`;
    const kpiP = $('#plate-position .kpi'); if (kpiP) kpiP.textContent = `领先 ${signed(first.y)} → ${signed(last.y)} pp`;
  }

  /* ================= 13. 第 5 章：代码反馈 ================= */
  function renderFeedback(M) {
    const ev = M.ev, c0 = ev.coverage, acc = ev.request_accounting || {};
    const models = ev.models;
    const mLabel = id => (/qwen3/i.test(id) ? MODEL.qwen3.name : MODEL.qwen.name);
    const mColor = id => MODEL[modelId(id)].color;
    const state = { model: models.find(m => /qwen3/i.test(m)) || models[0], metric: 'strong', focus: 'counterexample', baseline: 'self_review' };
    const sum = (m, arm) => ev.summary.find(r => r.model === m && r.arm === arm);
    const curve = (m, arm, metric) => (metric === 'strong' ? ev.strong_curves : ev.public_curves).filter(r => r.model === m && r.arm === arm).sort((a, b) => a.round - b.round);
    function contrast(m, arm, base) {
      const d = ev.contrasts.find(r => r.model === m && r.arm === arm && r.baseline === base);
      if (d) return d;
      const r = ev.contrasts.find(x => x.model === m && x.arm === base && x.baseline === arm);
      return r ? { ...r, arm, baseline: base, delta_pp: -r.delta_pp, ci_low_pp: -r.ci_high_pp, ci_high_pp: -r.ci_low_pp, arm_wins: r.baseline_wins, baseline_wins: r.arm_wins } : null;
    }
    const g = ev.generation_settings || {};
    $('#feedback-ledger').replaceChildren(...[
      ['独立编程题', fmt(c0.planned_tasks), 'HumanEval+ ' + ev.benchmark_version],
      ['每题每模型初稿', fmt(ev.repeats_per_task) + ' 份', '六条策略共享同一初稿'],
      ['模型 × 策略', `${models.length} × ${ev.arms.length}`, `温度 ${g.temperature}，Qwen3 非思考模式`],
      ['每条链', fmt(ev.rounds) + ' 个版本', '初稿 + 4 次修改'],
      ['有效模型响应', fmt(ev.saved_physical_responses), `HTTP 尝试 ${fmt(acc.http_attempts)}，含重试 ${fmt(acc.transport_retries)}`],
      ['公开测试输入', fmt(c0.public_cases), '模型可见，反馈只来自这里'],
      ['保留测试输入', fmt(c0.holdout_cases), '模型不可见，只用于判定'],
    ].map(([k, v, note]) => h('div', null, h('dt', { text: k }), h('dd', null, v, h('small', { text: note })))));

    const legendButtons = ARMS.map(a => {
      const b = h('button', { type: 'button', 'aria-pressed': String(a.id === state.focus) }, h('span', { class: 'arm-key', style: `border-color:${a.color};--c:${a.color}` }), h('strong', { text: a.name }), h('small', { text: a.desc }));
      b.addEventListener('click', () => setFocus(state.focus === a.id ? null : a.id));
      return h('li', null, b);
    });
    $('#arm-legend').replaceChildren(...legendButtons);
    const dimOf = arm => (state.focus && state.focus !== arm ? ' dim' : '');

    const traj = chart($('#chart-trajectory'), {
      fill: true,
      label: () => `${mLabel(state.model)}：六种策略五个版本的${state.metric === 'strong' ? '完整测试' : '公开诊断'}通过率`,
      height: W => Math.max(250, Math.min(300, W * 0.56)),
      draw(svg, c) {
        const L = 44, R = c.W - 18, T = 14, B = c.H - 40;
        const all = ARMS.flatMap(a => curve(state.model, a.id, state.metric).map(r => r.rate * 100));
        const [lo, hi] = niceRange(Math.min(...all) - 1.5, Math.max(...all) + 1.5, 4);
        const x = linear(0, ev.rounds - 1, L + 10, R - 10), y = linear(lo, hi, B, T);
        axisY(svg, y, ticks(lo, hi, 4), L, R, v => v + '%');
        for (let r = 0; r < ev.rounds; r++) text(svg, x(r), B + 17, r ? '第 ' + (r + 1) + ' 版' : '初稿', { class: 'tick', 'text-anchor': 'middle' });
        s('line', { class: 'axis', x1: L, x2: R, y1: B, y2: B }, svg);
        text(svg, (L + R) / 2, c.H - 5, '版本（纵轴截取 ' + lo + '–' + hi + '%）', { class: 'axis-title', 'text-anchor': 'middle' });
        const order = ARMS.slice().sort((a, b) => (a.id === state.focus) - (b.id === state.focus));
        for (const a of order) {
          const pts = curve(state.model, a.id, state.metric).map(r => [x(r.round), y(r.rate * 100)]);
          const g2 = s('g', { class: 'fade' + dimOf(a.id) }, svg);
          keyedPath(c, s('path', { fill: 'none', stroke: a.color, 'stroke-width': a.id === state.focus ? 3 : 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, g2), 'l' + a.id, pts, linePath);
          const e = pts[pts.length - 1];
          keyed(c, s('circle', { fill: a.color, stroke: PLATE, 'stroke-width': 2 }, g2), 'e' + a.id, { cx: e[0], cy: e[1], r: a.id === state.focus ? 5.5 : 4 });
        }
        { const r0 = curve(state.model, ARMS[0].id, state.metric)[0]; if (r0) text(svg, x(0) + 10, Math.min(B - 8, y(r0.rate * 100) + 22), `共享初稿 ${pct(r0.rate * 100)}`, { class: 'label-muted halo' }); }
        if (state.focus) { const e = curve(state.model, state.focus, state.metric).slice(-1)[0]; fitText(text(svg, x(ev.rounds - 1) - 8, y(e.rate * 100) - 12, `${ARM[state.focus].name} ${pct(e.rate * 100)}`, { class: 'label-strong', 'text-anchor': 'end', 'font-size': 12 }), L, R); }
        const cross = s('line', { class: 'crosshair', y1: T, y2: B, visibility: 'hidden' }, svg);
        const ov = s('rect', { x: L, y: T, width: R - L, height: B - T, fill: 'transparent', tabindex: 0, role: 'img', 'aria-label': '悬停或用方向键读取每个版本的六条通过率' }, svg);
        let cur = null;
        const at = (rd, e) => {
          cur = rd; cross.setAttribute('visibility', 'visible'); cross.setAttribute('x1', r1(x(rd))); cross.setAttribute('x2', r1(x(rd)));
          const rowsT = ARMS.map(a => ({ a, r: curve(state.model, a.id, state.metric)[rd] })).sort((p, q) => q.r.rate - p.r.rate);
          const content = { title: (rd ? '第 ' + (rd + 1) + ' 版' : '共享初稿') + '：' + (state.metric === 'strong' ? '完整测试' : '公开诊断'), rows: rowsT.map(({ a, r }) => ({ label: a.name, value: `${pct(r.rate * 100)}（${r.passed_programs}/${r.programs}）`, color: a.color })) };
          if (e && e.clientX != null) Tip.show(e.clientX, e.clientY, content); else Tip.at(cross, content);
        };
        ov.addEventListener('pointermove', e => { const b = svg.getBoundingClientRect(); const px = (e.clientX - b.left) * (c.W / b.width); at(Math.max(0, Math.min(ev.rounds - 1, Math.round(x.invert(px)))), e); });
        ov.addEventListener('pointerleave', () => { cross.setAttribute('visibility', 'hidden'); Tip.hide(); });
        ov.addEventListener('blur', () => { cross.setAttribute('visibility', 'hidden'); Tip.hide(); });
        ov.addEventListener('keydown', e => { const k = { ArrowRight: 1, ArrowLeft: -1 }[e.key]; if (!k) return; e.preventDefault(); at(cur == null ? 0 : Math.max(0, Math.min(ev.rounds - 1, cur + k))); });
      },
    });

    const ends = chart($('#chart-endpoints'), {
      fill: true,
      label: () => `${mLabel(state.model)}：初稿与终稿的完整测试通过率`,
      height: ARMS.length * 34 + 44,
      draw(svg, c) {
        const rows = ARMS.map(a => ({ a, r: sum(state.model, a.id) }));
        const vals = rows.flatMap(({ r }) => [r.initial_rate, r.final_ci[0], r.final_ci[1]].map(v => v * 100));
        const [lo, hi] = niceRange(Math.min(...vals) - 2, Math.max(...vals) + 2, 4);
        const narrow = c.W < 430, lw = narrow ? 84 : 98, L = lw + 6, R = c.W - (narrow ? 58 : 140), T = 26, rh = rowsH(c, ARMS.length, 48, 34, 22), B = T + rh * ARMS.length;
        const x = linear(lo, hi, L, R);
        for (const v of ticks(lo, hi, 4)) { s('line', { class: 'grid', x1: r1(x(v)), x2: r1(x(v)), y1: T, y2: B }, svg); text(svg, x(v), B + 16, v + '%', { class: 'tick', 'text-anchor': 'middle' }); }
        /* 图例用符号表示：空心初稿、实心第 5 版、细线区间 */
        s('circle', { cx: L + 5, cy: 9, r: 4, fill: PLATE, stroke: INK3, 'stroke-width': 1.6 }, svg);
        text(svg, L + 14, 13, '初稿', { class: 'axis-title', 'font-size': 11.5 });
        s('circle', { cx: L + 52, cy: 9, r: 4.5, fill: INK, stroke: PLATE, 'stroke-width': 1.5 }, svg);
        text(svg, L + 61, 13, '第 5 版', { class: 'axis-title', 'font-size': 11.5 });
        s('line', { x1: L + 108, x2: L + 124, y1: 9, y2: 9, stroke: INK3, 'stroke-width': 1.5 }, svg);
        text(svg, L + 130, 13, '95% 区间', { class: 'axis-title', 'font-size': 11.5 });
        text(svg, c.W, B + 16, narrow ? '通过率' : '完整测试通过率', { class: 'axis-title', 'text-anchor': 'end', 'font-size': 11.5 });
        rows.forEach(({ a, r }, i) => {
          const cy = T + i * rh + rh / 2, g2 = s('g', { class: 'fade' + dimOf(a.id) }, svg);
          text(svg, 0, cy + 4, a.name, { 'font-size': 12.5, class: a.id === state.focus ? 'label-strong' : dimOf(a.id) ? 'label-muted' : null });
          keyed(c, s('line', { stroke: a.color, 'stroke-width': 1.5 }, g2), 'ci' + a.id, { x1: x(r.final_ci[0] * 100), x2: x(r.final_ci[1] * 100), y1: cy, y2: cy });
          keyed(c, s('line', { stroke: a.color, 'stroke-width': 3, 'stroke-opacity': 0.5 }, g2), 'mv' + a.id, { x1: x(r.initial_rate * 100), x2: x(r.final_rate * 100), y1: cy, y2: cy });
          keyed(c, s('circle', { fill: PLATE, stroke: INK3, 'stroke-width': 1.6 }, g2), 'i' + a.id, { cx: x(r.initial_rate * 100), cy, r: 4.5 });
          keyed(c, s('circle', { fill: a.color, stroke: PLATE, 'stroke-width': 2 }, g2), 'f' + a.id, { cx: x(r.final_rate * 100), cy, r: 6 });
          text(g2, R + 10, cy + 4, narrow ? pct(r.final_rate * 100) : `${pct(r.final_rate * 100)}（${r.final_success}/${r.programs}）`, { class: 'value', 'font-size': 12 });
          const hit = s('rect', { class: 'row-hit', x: 0, y: r1(cy - rh / 2 + 1), width: c.W, height: rh - 2, rx: 6, tabindex: 0, role: 'img', 'aria-label': `${a.name}：初稿 ${pct(r.initial_rate * 100)}，终稿 ${pct(r.final_rate * 100)}` }, svg);
          svg.insertBefore(hit, svg.firstChild);
          bindTip(hit, () => ({ title: a.name, rows: [{ label: '共享初稿', value: `${pct(r.initial_rate * 100)}（${r.initial_success}/${r.programs}）` }, { label: '第 5 版', value: `${pct(r.final_rate * 100)}（${r.final_success}/${r.programs}）`, color: a.color, dot: true }, { label: '终稿 95% 区间', value: `${pct(r.final_ci[0] * 100)} – ${pct(r.final_ci[1] * 100)}` }, { label: '净变化', value: signed(r.net_gain_pp, 2) + ' pp' }], note: '点击在所有图中突出这一策略' }), () => setFocus(state.focus === a.id ? null : a.id));
        });
      },
    });

    const rep = chart($('#chart-repair'), {
      fill: true,
      label: () => `${mLabel(state.model)}：初错后修复与初对后回退的程序数`,
      height: ARMS.length * 32 + 72,
      draw(svg, c) {
        const rows = ARMS.map(a => ({ a, r: sum(state.model, a.id) }));
        const max = niceRange(0, Math.max(...rows.flatMap(({ r }) => [r.repaired, r.regressed])), 3)[1];
        const narrow = c.W < 430, lw = narrow ? 84 : 98, mid = lw + (c.W - lw) * 0.38, half = Math.min(mid - lw - 26, c.W - mid - 40);
        const T = 30, rh = rowsH(c, ARMS.length, 68, 32, 20), bh = Math.min(15, rh - 7), B = T + rh * ARMS.length;
        const xr = v => mid + v / max * half, xl = v => mid - v / max * half * (mid - lw - 26) / half;
        const r0 = rows[0].r;
        text(svg, mid - 8, 13, `回退（初对 ${r0.initial_correct} 份）`, { class: 'label-muted', 'text-anchor': 'end', 'font-size': 11.5 });
        text(svg, mid + 8, 13, `修复（初错 ${r0.initial_failures} 份）`, { class: 'label-muted', 'font-size': 11.5 });
        s('line', { class: 'axis', x1: r1(mid), x2: r1(mid), y1: T - 6, y2: B }, svg);
        for (const v of ticks(0, max, 3)) { text(svg, xr(v), B + 15, fmt(v), { class: 'tick', 'text-anchor': 'middle' }); if (v) text(svg, xl(v), B + 15, fmt(v), { class: 'tick', 'text-anchor': 'middle' }); }
        text(svg, mid, Math.min(c.H - 4, B + 32), '程序数', { class: 'axis-title', 'text-anchor': 'middle' });
        rows.forEach(({ a, r }, i) => {
          const y0 = T + i * rh, g2 = s('g', { class: 'fade' + dimOf(a.id) }, svg);
          text(svg, 0, y0 + rh / 2 + 4, a.name, { 'font-size': 12.5, class: a.id === state.focus ? 'label-strong' : dimOf(a.id) ? 'label-muted' : null });
          const pr = s('path', { fill: GOOD }, g2), pl = s('path', { fill: BAD, 'fill-opacity': 0.85 }, g2);
          keyed(c, pr, 'r' + a.id, { d: hbar(mid, xr(r.repaired), y0 + (rh - bh) / 2, bh) || 'M0,0' });
          keyed(c, pl, 'g' + a.id, { d: hbar(mid, xl(r.regressed), y0 + (rh - bh) / 2, bh) || 'M0,0' });
          text(g2, xr(r.repaired) + 6, y0 + rh / 2 + 4, fmt(r.repaired), { class: 'value', 'font-size': 12 });
          text(g2, xl(r.regressed) - 6, y0 + rh / 2 + 4, fmt(r.regressed), { class: 'value', 'font-size': 12, 'text-anchor': 'end' });
          const hit = s('rect', { class: 'row-hit', x: 0, y: y0 + 1, width: c.W, height: rh - 2, rx: 6, tabindex: 0, role: 'img', 'aria-label': `${a.name}：修复 ${r.repaired}，回退 ${r.regressed}` }, svg);
          svg.insertBefore(hit, svg.firstChild);
          bindTip(hit, () => ({ title: a.name, rows: [{ label: '初错后修复', value: `${r.repaired} / ${r.initial_failures}（${pct(r.repair_rate * 100)}）`, color: GOOD, dot: true }, { label: '初对后回退', value: `${r.regressed} / ${r.initial_correct}（${pct(r.regression_rate * 100)}）`, color: BAD, dot: true }], note: '修复与回退的分母不同，分别计算' }), () => setFocus(state.focus === a.id ? null : a.id));
        });
      },
    });

    const cost = chart($('#chart-cost'), {
      fill: true,
      label: () => `${mLabel(state.model)}：整链 Token 与终稿通过率`,
      height: W => Math.max(250, Math.min(300, W * 0.56)),
      draw(svg, c) {
        const rows = ARMS.map(a => ({ a, r: sum(state.model, a.id) }));
        const allTok = ev.summary.map(r => r.mean_chain_total_tokens);
        const xmax = niceRange(0, Math.max(...allTok), 4)[1];
        const vals = rows.map(({ r }) => r.final_rate * 100);
        const [lo, hi] = niceRange(Math.min(...vals) - 2, Math.max(...vals) + 2, 4);
        const L = 44, R = c.W - 16, T = 14, B = c.H - 40;
        const x = linear(0, xmax, L, R), y = linear(lo, hi, B, T);
        axisY(svg, y, ticks(lo, hi, 4), L, R, v => v + '%');
        axisX(svg, x, ticks(0, xmax, 4), B, v => (v ? fmt(v / 1000) + 'K' : '0'), [T, B]);
        s('line', { class: 'axis', x1: L, x2: R, y1: B, y2: B }, svg);
        text(svg, (L + R) / 2, c.H - 3, '五版链路的平均 Token（输入 + 输出）', { class: 'axis-title', 'text-anchor': 'middle', 'font-size': 11.5 });
        const order = rows.slice().sort((p, q) => (p.a.id === state.focus) - (q.a.id === state.focus));
        for (const { a, r } of order) {
          const px = x(r.mean_chain_total_tokens), py = y(r.final_rate * 100), g2 = s('g', { class: 'fade' + dimOf(a.id) }, svg);
          keyed(c, s('circle', { fill: a.color, stroke: PLATE, 'stroke-width': 2 }, g2), 'p' + a.id, { cx: px, cy: py, r: a.id === state.focus ? 7 : 5.5 });
          if (a.id === state.focus || a.id === 'resample') fitText(text(svg, px + (px > (L + R) / 2 ? -10 : 10), py - 11, a.name, { class: a.id === state.focus ? 'label-strong' : 'label-muted', 'font-size': 12, 'text-anchor': px > (L + R) / 2 ? 'end' : 'start' }), L, R);
          const hit = s('circle', { class: 'hit', cx: r1(px), cy: r1(py), r: 13, tabindex: 0, role: 'img', 'aria-label': `${a.name}：平均 ${fmt(r.mean_chain_total_tokens, 0)} Token，终稿 ${pct(r.final_rate * 100)}` }, svg);
          bindTip(hit, () => ({ title: a.name, rows: [{ label: '终稿完整通过', value: pct(r.final_rate * 100) }, { label: '整链平均 Token', value: fmt(r.mean_chain_total_tokens, 0) }, { label: '其中输出', value: fmt(r.mean_chain_output_tokens, 0) }], note: '点击在所有图中突出这一策略' }), () => setFocus(state.focus === a.id ? null : a.id));
        }
      },
    });

    const errs = chart($('#chart-errors'), {
      fill: true,
      label: () => `${mLabel(state.model)}：初稿在公开测试中的结果分布`,
      height: 6 * 28 + 10,
      draw(svg, c) {
        const NAMES = { pass: '通过公开测试', output_mismatch: '输出不符', runtime: '运行时异常', timeout: '超时', load: '加载失败', syntax: '语法错误' };
        const rows = Object.keys(NAMES).map(k => ({ k, n: (ev.initial_error_support.find(r => r.model === state.model && r.error_kind === k) || {}).initial_programs || 0 }));
        const total = rows.reduce((a, r) => a + r.n, 0), lw = 96, R = c.W - 100, rh = rowsH(c, rows.length, 10, 28, 22);
        const x = linear(0, niceRange(0, Math.max(...rows.map(r => r.n)), 4)[1], lw, R);
        rows.forEach((r, i) => {
          const y0 = 4 + i * rh;
          text(svg, 0, y0 + 15, NAMES[r.k], { 'font-size': 12.5, class: r.k === 'output_mismatch' ? 'label-strong' : null });
          s('rect', { x: lw, y: y0 + 4, width: R - lw, height: 15, rx: 3, fill: TRACK }, svg);
          s('path', { d: hbar(lw, x(r.n), y0 + 4, 15) || 'M0,0', fill: r.k === 'pass' ? MUTED : ACC }, svg);
          text(svg, Math.max(x(r.n), lw) + 6, y0 + 16, `${fmt(r.n)}（${pct(r.n / total * 100)}）`, { class: 'value', 'font-size': 12 });
        });
        const fail = total - rows[0].n, om = rows.find(r => r.k === 'output_mismatch').n;
        $('#error-note').textContent = `${mLabel(state.model)} 共 ${fmt(total)} 份初稿（${c0.planned_tasks} 题 × ${ev.repeats_per_task}）。公开测试失败的 ${fmt(fail)} 份中，${pct(om / fail * 100)} 是能运行但结果不对；会崩溃、能给出错误位置的情况很少，所以只靠报错诊断的线索有限。`;
      },
    });

    // 配对比较
    const pickHost = $('#contrast-pickers');
    const selA = h('select', { id: 'contrast-arm', 'aria-label': '比较的策略' }, ARMS.map(a => h('option', { value: a.id, text: a.name })));
    const selB = h('select', { id: 'contrast-base', 'aria-label': '对照策略' }, ARMS.map(a => h('option', { value: a.id, text: a.name })));
    pickHost.replaceChildren(selA, h('span', { text: '相对' }), selB);
    selA.addEventListener('change', () => { setFocus(selA.value); });
    selB.addEventListener('change', () => { state.baseline = selB.value; drawContrast(); });
    /* 刻度范围取全部比较（含反向）的最大区间，左右对称：切换策略时刻度不跳动，负值也不会出界 */
    const cspan = Math.ceil((Math.max(...ev.contrasts.flatMap(r => [Math.abs(r.ci_low_pp), Math.abs(r.ci_high_pp)])) + 1) / 5) * 5;
    function drawContrast() {
      const arm = state.focus || 'counterexample';
      if (state.baseline === arm) state.baseline = arm === 'self_review' ? 'resample' : 'self_review';
      selA.value = arm; selB.value = state.baseline;
      const d = contrast(state.model, arm, state.baseline), body = $('#contrast-body');
      if (!d) { body.replaceChildren(h('p', { text: '这一组没有保存配对比较。' })); return; }
      const kind = d.ci_low_pp > 0 ? 'is-pos' : d.ci_high_pp < 0 ? 'is-neg' : 'is-null';
      const verdict = kind === 'is-pos' ? '区间高于 0' : kind === 'is-neg' ? '区间低于 0' : '区间含 0，差异不稳定';
      const sv = s('svg', { viewBox: '0 0 320 54', width: '100%', height: 54, role: 'img', 'aria-label': `差值 ${signed(d.delta_pp, 2)}，区间 ${ci(d.ci_low_pp, d.ci_high_pp, 2)}` });
      const x = linear(-cspan, cspan, 10, 310);
      for (const v of ticks(-cspan, cspan, 6)) { s('line', { class: v ? 'grid' : 'zero', x1: r1(x(v)), x2: r1(x(v)), y1: 6, y2: 30, stroke: v ? GRIDC : INK3 }, sv); text(sv, x(v), 46, signed(v, 0), { class: 'tick', 'text-anchor': 'middle', fill: INK3, 'font-size': 11 }); }
      s('line', { x1: r1(x(d.ci_low_pp)), x2: r1(x(d.ci_high_pp)), y1: 18, y2: 18, stroke: ARM[arm].color, 'stroke-width': 2.5, 'stroke-linecap': 'round' }, sv);
      s('circle', { cx: r1(x(d.delta_pp)), cy: 18, r: 6, fill: ARM[arm].color, stroke: PLATE, 'stroke-width': 2 }, sv);
      body.replaceChildren(
        h('p', { class: 'contrast-delta' }, signed(d.delta_pp, 1), h('small', { text: '个百分点' })),
        h('div', null, h('p', { class: 'contrast-ci', text: `95% 区间 ${ci(d.ci_low_pp, d.ci_high_pp)}` }), h('span', { class: 'contrast-verdict ' + kind, text: verdict })),
        h('div', { class: 'contrast-scale' }, sv),
        h('p', { class: 'contrast-wins', title: `${d.paired_programs} 对同题程序，按 ${c0.planned_tasks} 道题聚类；未做多重比较校正` }, `${d.paired_programs} 对程序：前者独对 `, h('b', { text: String(d.arm_wins) }), '，后者独对 ', h('b', { text: String(d.baseline_wins) }), `，相同 ${d.ties}`));
    }

    function renderAll(animate) {
      traj.render(animate); ends.render(animate); rep.render(animate); cost.render(animate); errs.render(false);
      drawContrast();
      $('#traj-reading').textContent = state.metric === 'strong' ? '完整通过＝公开诊断与保留测试同时通过；保留输入不交给模型。第 1 版为六种反馈共享的初稿。' : '公开诊断：模型能看到的测试，反馈只来自这里。公开通过率比强测高，差距就是公开测试漏掉的错误。';
      $('#repair-reading').textContent = '右侧绿色为初稿错、终稿对的程序数，左侧红色为初稿对、终稿错的程序数。最终净提升同时受两者影响。';
      $('#fb-focus-note').textContent = state.focus ? `正在突出：${ARM[state.focus].name}。再次点击可取消。` : '点击上方策略或图中任一行，在所有图中突出它。';
      legendButtons.forEach((li, i) => li.firstChild.setAttribute('aria-pressed', String(ARMS[i].id === state.focus)));
      refreshTables.forEach(f => f());
      const kc = contrast(state.model, 'counterexample', 'self_review'), kpi = $('#plate-trajectory .kpi');
      if (kpi && kc) kpi.textContent = `${mLabel(state.model)}：单个反例比自查 ${signed(kc.delta_pp)} pp`;
    }
    function setFocus(id) { state.focus = id; renderAll(false); }
    segmented($('#fb-model'), models.map(m => ({ id: m, label: mLabel(m), color: mColor(m) })), state.model, id => { state.model = id; renderAll(true); });
    segmented($('#fb-metric'), [{ id: 'strong', label: '完整测试' }, { id: 'public', label: '公开诊断' }], state.metric, id => { state.metric = id; renderAll(true); });
    const refreshTables = [
      attachTable($('#plate-trajectory'), () => ({ caption: `${mLabel(state.model)}：${state.metric === 'strong' ? '完整测试' : '公开诊断'}通过率（%）`, cols: ['策略', ...Array.from({ length: ev.rounds }, (_, r) => (r ? '第 ' + (r + 1) + ' 版' : '初稿'))], rows: ARMS.map(a => [a.name, ...curve(state.model, a.id, state.metric).map(r => fmt(r.rate * 100, 1))]) })),
      attachTable($('#plate-endpoints'), () => ({ caption: `${mLabel(state.model)}：初稿与终稿完整通过`, cols: ['策略', '初稿', '终稿', '终稿 95% 区间', '净变化（pp）'], rows: ARMS.map(a => { const r = sum(state.model, a.id); return [a.name, `${r.initial_success}/${r.programs}`, `${r.final_success}/${r.programs}（${pct(r.final_rate * 100)}）`, `${pct(r.final_ci[0] * 100)} – ${pct(r.final_ci[1] * 100)}`, `${signed(r.net_gain_pp, 2)} ${ci(r.net_gain_ci_pp[0], r.net_gain_ci_pp[1], 2)}`]; }) })),
      attachTable($('#plate-repair'), () => ({ caption: `${mLabel(state.model)}：修复与回退`, cols: ['策略', '初错后修复', '修复率', '初对后回退', '回退率'], rows: ARMS.map(a => { const r = sum(state.model, a.id); return [a.name, `${r.repaired}/${r.initial_failures}`, pct(r.repair_rate * 100), `${r.regressed}/${r.initial_correct}`, pct(r.regression_rate * 100)]; }) })),
      attachTable($('#plate-cost'), () => ({ caption: `${mLabel(state.model)}：整链 Token 与终稿通过率`, cols: ['策略', '整链平均 Token', '其中输入', '其中输出', '终稿通过率'], rows: ARMS.map(a => { const r = sum(state.model, a.id); return [a.name, fmt(r.mean_chain_total_tokens, 0), fmt(r.mean_chain_input_tokens, 0), fmt(r.mean_chain_output_tokens, 0), pct(r.final_rate * 100)]; }) })),
    ];
    renderAll(false);

    // 章节结论（两模型分别报告）
    const q3 = models.find(m => /qwen3/i.test(m)), q25 = models.find(m => !/qwen3/i.test(m));
    const k3 = contrast(q3, 'counterexample', 'self_review'), k25 = contrast(q25, 'counterexample', 'self_review');
    const s3 = sum(q3, 'counterexample'), r3 = sum(q3, 'self_review');
    const mm3 = contrast(q3, 'multi_counterexample', 'counterexample'), mm25 = contrast(q25, 'multi_counterexample', 'counterexample');
    const tokUp = m => (sum(m, 'multi_counterexample').mean_chain_total_tokens / sum(m, 'counterexample').mean_chain_total_tokens - 1) * 100;
    $('#feedback-finding').textContent = `${mLabel(q3)} 收到单个失败反例时，终稿完整通过 ${s3.final_success}/${s3.programs}（${pct(s3.final_rate * 100)}），自行检查为 ${r3.final_success}/${r3.programs}（${pct(r3.final_rate * 100)}），配对差 ${signed(k3.delta_pp)} 个百分点，95% 区间 ${ci(k3.ci_low_pp, k3.ci_high_pp)}。${mLabel(q25)} 的同一比较只有 ${signed(k25.delta_pp)}（${ci(k25.ci_low_pp, k25.ci_high_pp)}），区间含 0，收益依赖模型。多个反例相对单个反例在两个模型上分别为 ${signed(mm3.delta_pp)} 与 ${signed(mm25.delta_pp)} 个百分点，区间都含 0，整链 Token 却多出 ${fmt(tokUp(q3), 1)}% 与 ${fmt(tokUp(q25), 1)}%。`;
    $('#feedback-scope').textContent = `结论限于两个 7–8B 模型、HumanEval+ 的 ${c0.planned_tasks} 道题、温度 ${g.temperature} 与当前反馈协议。区间按题目聚类 bootstrap（${fmt(ev.bootstrap.resamples)} 次），重复初稿不增加独立题目数。`;
    renderCases(M, mLabel);
  }

  function renderCases(M, mLabel) {
    const ex = M.ev.examples || [];
    const ORDER = [['diagnostic_repair', '诊断后修复'], ['semantic_repair', '反例后修复'], ['regression', '自查后回退'], ['diagnostic_hidden_gap', '公开通过，保留失败']];
    const cases = ORDER.map(([k, label]) => ({ k, label, e: ex.find(x => x.category === k) })).filter(x => x.e);
    const icon = ok => { const sv = s('svg', { viewBox: '0 0 16 16', 'aria-hidden': 'true' }); s('path', { d: ok ? 'M3.5 8.5l3 3 6-7' : 'M4.5 4.5l7 7m0-7-7 7' }, sv); return sv; };
    const chip = (ok, label) => h('span', { class: 'status ' + (ok ? 'ok' : 'no') }, icon(ok), label);
    const pub = p => chip(p.passed === true, `${p.passed ? '通过' : '失败'} ${p.passed_cases}/${p.total_cases}`);
    function excerpt(raw) {
      const prefix = 'Diagnostic test feedback:\n';
      if (raw.startsWith(prefix)) {
        try {
          const rep = JSON.parse(raw.slice(prefix.length).split('\n\n')[0]);
          const proj = { diagnostic_status: rep.diagnostic_status };
          if (rep.diagnostic) { proj.diagnostic = {}; for (const key of ['error_type', 'error_message', 'line', 'column', 'source_line']) if (key in rep.diagnostic) proj.diagnostic[key] = rep.diagnostic[key]; }
          else if (Array.isArray(rep.failures) && rep.failures.length) { proj.failures = rep.failures.slice(0, 2).map(f => ({ input: f.input, expected: f.expected, actual: f.actual })); if (rep.failures.length > 2) proj.failures.push('…另 ' + (rep.failures.length - 2) + ' 条'); }
          return { label: rep.diagnostic ? '当步收到的诊断（原字段摘录）' : rep.failures ? '当步收到的失败反例（摘录）' : '当步收到的诊断', body: JSON.stringify(proj, null, 2) };
        } catch (err) { /* fall through */ }
      }
      const cut = raw.indexOf(' Return the complete implementation');
      return { label: '当步收到的指令（无执行反馈）', body: cut > 0 ? raw.slice(0, cut) : raw };
    }
    function why(c) {
      const e = c.e, f = e.before_public.first_failure || (e.before_public.failures || [])[0] || {};
      if (c.k === 'diagnostic_repair') return `上一版在加载阶段抛出 ${f.error_type}（第 ${f.line} 行），${e.before_public.total_cases} 条公开测试一条都没能运行。诊断给出错误类型、行列和出错的源码行，下一版改写了这一行的查找方式，公开与完整测试都转为通过。`;
      if (c.k === 'semantic_repair') return `代码能运行但结果不对：输入 ${f.input}，期望 ${f.expected}，实际 ${f.actual}。反例说明题目只比较出现过哪些字符、不计次数，模型把 sorted 改成 set，${e.after_public.total_cases} 条公开测试和完整测试都转为通过。`;
      if (c.k === 'regression') return `上一版已经通过 ${e.before_public.total_cases} 条公开测试和完整测试。自查后模型给编码与解码都加了 if ch.isalpha() 过滤，公开测试仍是 ${e.after_public.passed_cases}/${e.after_public.total_cases}，完整测试却判定失败。只看公开测试，这类回退看不出来。`;
      return `公开测试 ${e.before_public.total_cases} 条一直全部通过，诊断反馈只能回复 PASS，模型保持代码不变，完整测试仍判定失败。公开测试覆盖不到的错误，反馈也无从提示。`;
    }
    let cur = 0;
    const tabs = cases.map((c, i) => {
      const b = h('button', { type: 'button', role: 'tab', id: 'case-tab-' + i, 'aria-selected': String(i === cur), 'aria-controls': 'case-panel', tabindex: i === cur ? '0' : '-1', text: c.label });
      b.addEventListener('click', () => select(i));
      b.addEventListener('keydown', e => { const k = { ArrowRight: 1, ArrowLeft: -1 }[e.key]; if (k) { e.preventDefault(); select((cur + k + cases.length) % cases.length); tabs[cur].focus(); } });
      return b;
    });
    $('#case-tabs').replaceChildren(...tabs);
    function select(i) {
      cur = i; tabs.forEach((b, j) => { b.setAttribute('aria-selected', String(j === i)); b.setAttribute('tabindex', j === i ? '0' : '-1'); });
      const c = cases[i], e = c.e, ex2 = excerpt(e.actual_feedback || '');
      const lines = (e.diff || '').split('\n').filter((l, k, arr) => !(k === arr.length - 1 && l === ''));
      const diffPre = h('pre', null, (e.diff ? lines : (e.before_code || '').split('\n')).map(l => h('span', { class: !e.diff ? null : l.startsWith('+++') || l.startsWith('---') ? 'd-meta' : l.startsWith('@@') ? 'd-hunk' : l.startsWith('+') ? 'd-add' : l.startsWith('-') ? 'd-del' : null, text: l || ' ' })));
      const panel = $('#case-panel');
      panel.setAttribute('aria-labelledby', 'case-tab-' + i);
      panel.replaceChildren(
        h('div', { class: 'case-head' }, h('h4', { text: { diagnostic_repair: '诊断指出加载错误，代码随即修好', semantic_repair: '失败反例澄清题意，代码随即修好', regression: '公开测试仍通过，强测却回退了', diagnostic_hidden_gap: '公开测试全过，诊断无从下手' }[c.k] }),
          h('p', { class: 'case-meta', text: `${mLabel(e.model)}　${ARM[e.arm].name}　匿名题 ${e.anonymous_task}　第 ${e.before_round + 1} 版 → 第 ${e.after_round + 1} 版` })),
        h('p', { class: 'case-why', text: why(c) }),
        h('div', { class: 'case-grid' },
          h('div', { class: 'code-block' }, h('h5', { text: ex2.label }), h('pre', null, ex2.body.split('\n').map(l => h('span', { text: l || ' ' })))),
          h('div', { class: 'code-block' }, h('h5', { text: e.diff ? '代码的实际变化（完整 diff）' : '代码没有改变（当前实现）' }), diffPre)),
        h('div', { class: 'outcomes' },
          h('div', null, h('span', { text: '公开测试' }), pub(e.before_public), h('span', { class: 'arrow', text: '→' }), pub(e.after_public)),
          h('div', null, h('span', { text: '完整测试' }), chip(e.before_strong_pass, e.before_strong_pass ? '通过' : '失败'), h('span', { class: 'arrow', text: '→' }), chip(e.after_strong_pass, e.after_strong_pass ? '通过' : '失败'))));
    }
    if (cases.length) select(0);
  }

  /* ================= 14. 结论：五条发现与使用建议 ================= */
  function renderConclusion(M) {
    const base = M.rows('concise-baseline'), b0 = base.find(r => r.prompt === 'DefaultCoT'), b1 = base.find(r => r.prompt === 'BeConcise');
    const hero = M.rows('concise-cross-task').find(p => modelId(p.model) === 'qwen' && taskId(p.task) === 'gsm8k');
    const lang = M.rows('language-cost-quality').find(r => r.model === 'qwen3' && r.task === 'math500');
    const adv = M.rows('position-model-advantage');
    const lim = M.rows('limits-rebound-ratios').find(r => /DeepSeek/.test(r.label) && /MATH500/.test(r.label));
    const ev = M.ev, q3 = ev.models.find(m => /qwen3/i.test(m));
    const k3 = ev.contrasts.find(r => r.model === q3 && r.arm === 'counterexample' && r.baseline === 'self_review');
    const items = [
      { kind: '低维', t: '保留步骤，只要求简洁', k: '−' + fmt(hero ? hero.saving : 0, 1) + '%', unit: 'Token', sub: `Qwen2.5 · GSM8K 得分 ${pct(b0.score_pct)} → ${pct(b1.score_pct)}`, q: 'Think step by step, but be concise.', page: 0, plate: 'III' },
      { kind: '低维', t: '数学题可以用中文作答', k: signed(lang.score_difference_pp), unit: 'pp', sub: `Qwen3 · MATH500 ${pct(lang.default_score_pct)} → ${pct(lang.chinese_score_pct)}`, q: 'Respond in Chinese.', page: 1, plate: 'V' },
      { kind: '多维', t: '关键资料放在第一篇', k: `${fmt(adv[0].y, 1)} → ${fmt(adv[adv.length - 1].y, 1)}`, unit: 'pp', sub: 'Qwen3 的领先幅度：首位 → 末位', q: '把最相关的文档排在资料首位', page: 1, plate: 'VI' },
      { kind: '多维', t: '修代码时给出失败用例', k: signed(k3.delta_pp), unit: 'pp', sub: `Qwen3 · 相对自行检查 ${ci(k3.ci_low_pp, k3.ci_high_pp)}`, q: 'choose_num(13, 12)：期望 −1，实际 12', page: 2, plate: 'VII' },
      { kind: '异常', t: '长度限制不要压得过紧', k: '×' + fmt(lim.ratio, 1), unit: '输出', sub: `DeepSeek · MATH500 ${fmt(lim.tokens_at_100_letters, 0)} → ${fmt(lim.tokens_at_10_letters, 0)} Token`, q: 'Keep the key steps; be concise.', page: 0, plate: 'IV' },
    ];
    /* 每张结论卡附一张缩略图：只保留讲解时需要指着看的那一点 */
    const Q25 = MODEL.qwen.color, Q3 = MODEL.qwen3.color;
    const langRows = MODELS.map(m => M.rows('language-cost-quality').find(r => r.model === m.id && r.task === 'math500')).filter(Boolean);
    const q3curve = arm => ev.strong_curves.filter(r => r.model === q3 && r.arm === arm).sort((a, b) => a.round - b.round);
    const minis = [
      { label: `Qwen2.5 · GSM8K：默认分步 ${fmt(b0.mean_tokens, 0)} Token、${pct(b0.score_pct)}；简洁分步 ${fmt(b1.mean_tokens, 0)} Token、${pct(b1.score_pct)}`,
        draw(svg, c) {
          const groups = [
            { title: '平均输出 Token', max: niceRange(0, b0.mean_tokens, 4)[1], f: v => fmt(v, 0), bars: [['默认分步', b0.mean_tokens, MUTED], ['简洁分步', b1.mean_tokens, Q25]] },
            { title: '规则评分', max: 100, f: v => pct(v), bars: [['默认分步', b0.score_pct, MUTED], ['简洁分步', b1.score_pct, Q25]] },
          ];
          /* 行高随卡片高度铺满，条宽同比例加粗，五张卡的缩略图高度一致 */
          const n = 6, rh = c.H / n, lw = 62, vw = 46, x0 = lw, x1 = c.W - vw, bh = Math.max(10, Math.min(18, rh * 0.3));
          let y = 0;
          groups.forEach(g => {
            text(svg, 0, y + rh - 8, g.title, { class: 'axis-title', 'font-size': 11 }); y += rh;
            g.bars.forEach(([label, v, color]) => {
              text(svg, 0, y + rh / 2 + 4, label, { 'font-size': 11.5, class: color === MUTED ? 'label-muted' : 'label-strong' });
              s('rect', { x: x0, y: r1(y + (rh - bh) / 2), width: r1(x1 - x0), height: bh, rx: bh / 2, fill: TRACK }, svg);
              s('path', { d: hbar(x0, x0 + (x1 - x0) * v / g.max, y + (rh - bh) / 2, bh), fill: color }, svg);
              text(svg, c.W, y + rh / 2 + 4, g.f(v), { class: 'value', 'font-size': 11.5, 'text-anchor': 'end' });
              y += rh;
            });
          });
        } },
      { label: 'MATH500：四个模型从默认分步（空心）到中文作答（实心）的规则评分',
        draw(svg, c) {
          const lw = 62, vw = 44, x = linear(50, 80, lw + 6, c.W - vw - 6);
          const rh = (c.H - 28) / langRows.length, T = 4, B = T + rh * langRows.length, rd = Math.max(4.5, Math.min(7, rh * 0.075));
          for (const v of [50, 60, 70, 80]) { s('line', { class: 'grid', x1: r1(x(v)), x2: r1(x(v)), y1: T, y2: B }, svg); text(svg, x(v), B + 15, v + '%', { class: 'tick', 'text-anchor': 'middle', 'font-size': 10.5 }); }
          langRows.forEach((r, i) => {
            const m = MODEL[r.model], cy = T + i * rh + rh / 2, a = x(r.default_score_pct), z = x(r.chinese_score_pct);
            text(svg, 0, cy + 4, m.short, { 'font-size': 11.5, class: r.model === 'qwen3' ? 'label-strong' : 'label-muted' });
            s('line', { x1: r1(a), x2: r1(z), y1: r1(cy), y2: r1(cy), stroke: m.color, 'stroke-width': rd > 5.5 ? 4 : 3, 'stroke-opacity': 0.55, 'stroke-linecap': 'round' }, svg);
            s('circle', { cx: r1(a), cy: r1(cy), r: r1(rd), fill: PLATE, stroke: m.color, 'stroke-width': 1.8 }, svg);
            s('circle', { cx: r1(z), cy: r1(cy), r: r1(rd + 1), fill: m.color, stroke: PLATE, 'stroke-width': 1.5 }, svg);
            text(svg, c.W, cy + 4, signed(r.score_difference_pp), { class: r.model === 'qwen3' ? 'value' : 'label-muted', 'font-size': 11.5, 'text-anchor': 'end' });
          });
        } },
      { label: `Qwen3 相对 Qwen2.5 的领先：九个证据位置，首位 ${signed(adv[0].y)}，末位 ${signed(adv[adv.length - 1].y)} 个百分点`,
        draw(svg, c) {
          const n = adv.length, T = 22, B = c.H - 22, gap = Math.max(4, Math.min(10, c.W / 40));
          const bw = Math.min(24, (c.W - 28 - gap * (n - 1)) / n), tot = bw * n + gap * (n - 1), x0 = (c.W - tot) / 2;
          const y = linear(0, 20, B, T);
          [5, 10, 15, 20].forEach(v => s('line', { class: 'grid', x1: r1(x0 - 4), x2: r1(x0 + tot + 4), y1: r1(y(v)), y2: r1(y(v)) }, svg));
          adv.forEach((d, i) => {
            const px = x0 + i * (bw + gap), hi = i === 0 || i === n - 1;
            s('path', { d: vbar(px, bw, B, y(Math.max(0, d.y))), fill: hi ? Q3 : MUTED }, svg);
            if (hi) text(svg, px + bw / 2, y(d.y) - 7, signed(d.y), { class: 'value', 'font-size': 12, 'text-anchor': 'middle' });
          });
          s('line', { class: 'zero', x1: r1(x0 - 4), x2: r1(x0 + tot + 4), y1: r1(B), y2: r1(B) }, svg);
          text(svg, x0 + bw / 2, B + 15, '首位', { class: 'tick', 'text-anchor': 'middle' });
          text(svg, x0 + tot - bw / 2, B + 15, '末位', { class: 'tick', 'text-anchor': 'middle' });
          text(svg, x0 + tot / 2, B + 15, '资料位置', { class: 'axis-title', 'text-anchor': 'middle', 'font-size': 10.5 });
        } },
      { label: 'Qwen3 · 完整测试：六种反馈从初稿到第 5 版的通过率，突出自行检查与单个失败反例',
        draw(svg, c) {
          const lines = ARMS.map(a => ({ a, pts: q3curve(a.id) })).filter(o => o.pts.length);
          const vals = lines.flatMap(o => o.pts.map(p => p.rate * 100));
          const [lo, hi] = niceRange(Math.min(...vals) - 1, Math.max(...vals) + 1, 3);
          const L = 6, R = c.W - 46, T = 12, B = c.H - 22, x = linear(0, 4, L, R), y = linear(lo, hi, B, T);
          ticks(lo, hi, 3).forEach(v => { s('line', { class: 'grid', x1: L, x2: R, y1: r1(y(v)), y2: r1(y(v)) }, svg); });
          const key = id => id === 'counterexample' || id === 'self_review';
          lines.sort((p, q) => key(p.a.id) - key(q.a.id)).forEach(({ a, pts }) => {
            const on = key(a.id);
            s('path', { d: linePath(pts.map(p => [x(p.round), y(p.rate * 100)])), fill: 'none', stroke: on ? a.color : MUTED, 'stroke-width': on ? 2.5 : 1.5, 'stroke-opacity': on ? 1 : 0.7, 'stroke-linejoin': 'round' }, svg);
            if (on) { const z = pts[pts.length - 1]; s('circle', { cx: r1(x(z.round)), cy: r1(y(z.rate * 100)), r: 4.5, fill: a.color, stroke: PLATE, 'stroke-width': 1.5 }, svg); text(svg, R + 8, y(z.rate * 100) + 4, pct(z.rate * 100), { class: 'value', 'font-size': 11.5 }); }
          });
          text(svg, L, B + 15, '初稿', { class: 'tick' });
          text(svg, R, B + 15, '第 5 版', { class: 'tick', 'text-anchor': 'end' });
        } },
      { label: `DeepSeek · MATH500：字母上限 100 时平均 ${fmt(lim.tokens_at_100_letters, 0)} Token，上限 10 时 ${fmt(lim.tokens_at_10_letters, 0)} Token`,
        draw(svg, c) {
          const vals = [['上限 100 字母', lim.tokens_at_100_letters, MUTED], ['上限 10 字母', lim.tokens_at_10_letters, MODEL.deepseek.color]];
          const T = 24, B = c.H - 22, bw = Math.min(64, c.W * 0.26), y = linear(0, niceRange(0, lim.tokens_at_10_letters, 4)[1], B, T);
          vals.forEach(([label, v, color], i) => {
            const cx = c.W * (i ? 0.72 : 0.28);
            s('path', { d: vbar(cx - bw / 2, bw, B, y(v), 6), fill: color }, svg);
            text(svg, cx, y(v) - 8, fmt(v, 0), { class: 'value', 'font-size': 13, 'text-anchor': 'middle' });
            text(svg, cx, B + 15, label, { class: 'tick', 'text-anchor': 'middle' });
          });
          s('line', { class: 'zero', x1: 0, x2: c.W, y1: r1(B), y2: r1(B) }, svg);
          text(svg, 0, 14, '平均输出 Token', { class: 'axis-title' });
        } },
    ];
    $('#advice-list').replaceChildren(...items.map((it, i) => h('li', { class: 'advice-card' + (it.kind === '异常' ? ' is-anomaly' : ''), 'data-anim': '', style: `--d:${i + 2}` },
      h('p', { class: 'ac-kind', text: it.kind }),
      h('p', { class: 'ac-num' }, h('b', { text: it.k }), h('small', { text: it.unit })),
      h('h3', { text: it.t }),
      h('p', { class: 'ac-sub', text: it.sub }),
      h('div', { class: 'chart ac-viz', id: 'ac-viz-' + i }),
      h('p', { class: 'ac-q' }, h('code', { lang: /^[A-Za-z]/.test(it.q) ? 'en' : null, text: it.q })),
      h('a', { class: 'ac-link', href: '#s4', 'data-page': String(it.page), text: '查看图版 ' + it.plate }))));
    minis.forEach((mi, i) => chart($('#ac-viz-' + i), { fill: true, height: 150, label: mi.label, draw: mi.draw }));
    const limits = [['覆盖范围', '4 个模型、6 个公开题库'], ['自动评分', '规则评分不等于人工判分'], ['统计方法', '区间未做多重比较校正'], ['长度单位', '长度上限只是软指令'], ['规模效应', '4 个模型、架构不同，不作拟合'], ['代码测试', '通过测试不等于完全正确'], ['因果', '相关不等于因果']];
    $('#limit-list').replaceChildren(...limits.map(([k, v]) => h('li', null, h('b', { text: k }), h('span', { text: v }))));
  }

  /* ================= 15. 放映：导航、翻页与入场动画 ================= */
  function countUp(el) {
    const target = +el.dataset.count; if (!Number.isFinite(target)) return;
    if (reduceMotion) { el.textContent = fmt(target); return; }
    const t0 = performance.now(), dur = 1300;
    const step = now => { const p = Math.max(0, Math.min(1, (now - t0) / dur)), e = 1 - (1 - p) ** 3; el.textContent = fmt(Math.round(target * e)); if (p < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }
  function animateIn(scope) {
    if (!scope || reduceMotion) return;
    scope.querySelectorAll('.chart > svg').forEach((svg, i) => {
      if (!svg.getBoundingClientRect().width) return;
      svg.classList.remove('wipe'); void svg.getBoundingClientRect();
      svg.style.animationDelay = (240 + i * 110) + 'ms';
      svg.classList.add('wipe');
    });
    scope.querySelectorAll('[data-count]').forEach(countUp);
  }
  /* ================= 14b. 景深：视野刻度环、微尘、取景框 ================= */
  const Depth = { dust: [], reticle: null, vf: null, target: null, active: null, wide: () => matchMedia('(min-width: 1181px) and (min-height: 701px)').matches };
  function seeded(a) { return () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  function initDepth() {
    const bd = $('.backdrop'); if (!bd) return;
    /* 视野刻度环：同心圆、180 道刻度、留出中心的十字线 */
    const ret = s('svg', { class: 'reticle', viewBox: '-1 -1 2 2', width: 2, height: 2 });
    const g = s('g', null, ret);
    [0.36, 0.6, 0.84, 1].forEach((r, i) => s('circle', { r: r * 520, fill: 'none', stroke: '#fff', 'stroke-opacity': i === 3 ? 0.2 : 0.11, 'stroke-width': 1.2, 'stroke-dasharray': i === 1 ? '2 7' : null }, g));
    let d = '';
    for (let i = 0; i < 180; i++) {
      const a = i / 180 * Math.PI * 2, len = i % 15 === 0 ? 26 : i % 5 === 0 ? 13 : 6;
      d += `M${r1(Math.cos(a) * (520 - len))},${r1(Math.sin(a) * (520 - len))}L${r1(Math.cos(a) * 520)},${r1(Math.sin(a) * 520)}`;
    }
    s('path', { d, stroke: '#fff', 'stroke-opacity': 0.24, 'stroke-width': 1.2, fill: 'none' }, g);
    s('path', { d: 'M-760,0H-230M230,0H760M0,-760V-230M0,230V760', stroke: '#fff', 'stroke-opacity': 0.1, 'stroke-width': 1.2 }, g);
    ret.style.overflow = 'visible';
    bd.append(h('div', { class: 'ret-wrap' }, ret)); Depth.reticle = ret;
    /* 两层微尘：近的一层更大、视差更快 */
    const rnd = seeded(11);
    [[170, 0.7, 0.32], [60, 1.5, 0.45]].forEach(([n, rmax, omax], k) => {
      const dv = s('svg', { class: 'dust d' + (k + 1), viewBox: '0 0 1600 1500', preserveAspectRatio: 'xMidYMid slice' });
      for (let i = 0; i < n; i++) s('circle', { cx: r1(rnd() * 1600), cy: r1(rnd() * 1500), r: r1(0.35 + rnd() * rmax), fill: k ? '#cfd6ff' : '#ffffff', 'fill-opacity': r1(0.1 + rnd() * omax) }, dv);
      bd.append(dv); Depth.dust.push(dv);
    });
    /* 取景框 */
    const vf = h('div', { class: 'viewfinder', 'aria-hidden': 'true' }, h('i'), h('i'), h('i'), h('i'));
    document.body.append(vf); Depth.vf = vf;
    let timer;
    document.addEventListener('pointerover', e => {
      if (e.pointerType === 'touch' || !Depth.wide()) return;
      const t = e.target.closest('[data-focus], .panel:not(.is-bare), .advice-card');
      if (!t || t === Depth.target || t.closest('[inert]') || !t.closest('.screen.is-in')) return;
      clearTimeout(timer); timer = setTimeout(() => focusOn(t), 120);
    });
    addEventListener('resize', () => { clearTimeout(timer); timer = setTimeout(() => { if (Depth.active) placeReticle(Depth.active); if (Depth.target) focusOn(Depth.target, 'quiet'); }, 150); });
  }
  /* 不受入场位移影响的文档坐标 */
  function docRect(el) {
    let x = 0, y = 0, n = el;
    while (n) { x += n.offsetLeft + (n !== el ? n.clientLeft : 0); y += n.offsetTop + (n !== el ? n.clientTop : 0); n = n.offsetParent; }
    return { x, y, w: el.offsetWidth, h: el.offsetHeight };
  }
  function focusOn(el, mode) {
    const vf = Depth.vf; if (!vf || !el) return;
    if (!Depth.wide()) { vf.classList.remove('is-on'); return; }
    const g = docRect(el); if (!g.w) return;
    Depth.target = el;
    const set = () => { vf.style.transform = `translate(${g.x}px, ${g.y}px)`; vf.style.width = g.w + 'px'; vf.style.height = g.h + 'px'; };
    if (mode === 'snap' || mode === 'quiet' || !vf.classList.contains('is-on')) {
      vf.classList.add('no-move'); if (mode !== 'quiet') vf.classList.add('is-focusing');
      set(); void vf.offsetWidth; vf.classList.remove('no-move');
      requestAnimationFrame(() => requestAnimationFrame(() => vf.classList.remove('is-focusing')));
    } else set();
    vf.classList.add('is-on');
  }
  function keyOf(sc) {
    if (sc.id === 's4') { const pg = sc.querySelector('.page.is-active'); return pg && (pg.querySelector('[data-key]') || pg.querySelector('.panel')); }
    return sc.querySelector('[data-key]');
  }
  /* 刻度环移到这一屏主展品的中心，每屏转过一个角度 */
  function placeReticle(sc) {
    const ret = Depth.reticle, key = keyOf(sc); if (!ret || !key) return;
    const g = docRect(key), top = docRect(sc).y;
    const cx = g.x + g.w / 2, cy = g.y - top + g.h / 2, size = Math.max(560, Math.min(1500, Math.max(g.w, g.h) * 1.35));
    const i = Array.from(document.querySelectorAll('[data-screen]')).indexOf(sc);
    ret.style.setProperty('--rx', r1(cx) + 'px'); ret.style.setProperty('--ry', r1(cy) + 'px');
    ret.style.setProperty('--rr', (i * 38) + 'deg'); ret.style.setProperty('--rs', r1(size / 1040 * 2) / 2);
  }
  function activate(sc) {
    if (Depth.active === sc) return;
    Depth.active = sc;
    placeReticle(sc);
    const key = keyOf(sc);
    if (key) focusOn(key, 'snap');
  }
  function depthFrame(screens) {
    const vh = innerHeight, y = scrollY, wide = Depth.wide();
    Depth.dust.forEach((d, k) => { d.style.transform = wide ? `translate3d(0, ${r1(-Math.min(y * (k ? 0.1 : 0.045), 600))}px, 0)` : ''; });
    screens.forEach(sc => { const r = sc.getBoundingClientRect(); const p = (r.top + Math.min(r.height, vh) / 2 - vh / 2) / vh; sc.style.setProperty('--p', Math.round(Math.max(-1.5, Math.min(1.5, p)) * 100) / 100); });
  }
  function placeNavInd(link) {
    const ind = $('.nav-ind'); if (!ind || !link) return;
    ind.style.transform = `translateX(${link.offsetLeft}px)`; ind.style.width = link.offsetWidth + 'px';
  }

  let goPage = () => {};
  function initDeck() {
    const screens = Array.from(document.querySelectorAll('[data-screen]'));
    const links = Array.from(document.querySelectorAll('.deck-nav a'));
    const bar = document.querySelector('.read-progress span');
    const tabs = Array.from(document.querySelectorAll('.pager-tabs [data-page]'));
    const pages = Array.from(document.querySelectorAll('.page'));
    let cur = 0;
    goPage = (i, focus) => {
      i = (i + pages.length) % pages.length;
      pages.forEach((p, k) => { p.classList.toggle('is-active', k === i); p.classList.toggle('is-before', k < i); p.setAttribute('aria-hidden', String(k !== i)); p.inert = k !== i; });
      tabs.forEach((t, k) => { t.setAttribute('aria-selected', String(k === i)); t.tabIndex = k === i ? 0 : -1; });
      const changed = i !== cur; cur = i;
      if (changed) { animateIn(pages[i]); const k = pages[i].querySelector('[data-key]'); if (k && Depth.active && Depth.active.id === 's4') { focusOn(k, 'snap'); placeReticle(Depth.active); } }
      if (focus) tabs[i].focus();
    };
    pages.forEach((p, k) => { p.inert = k !== 0; p.setAttribute('aria-hidden', String(k !== 0)); });
    tabs.forEach((t, k) => {
      t.addEventListener('click', () => goPage(k));
      t.addEventListener('keydown', e => { const d = { ArrowRight: 1, ArrowLeft: -1 }[e.key]; if (d) { e.preventDefault(); goPage(cur + d, true); } });
    });
    document.querySelectorAll('[data-pager]').forEach(b => b.addEventListener('click', () => goPage(cur + Number(b.dataset.pager))));
    let ticking = false;
    const update = () => {
      ticking = false;
      const y = scrollY + innerHeight * 0.4;
      let idx = 0;
      screens.forEach((sc, i) => { if (sc.offsetTop <= y) idx = i; });
      links.forEach((a, i) => a.classList.toggle('is-active', i === idx));
      if (lastIdx !== idx) { lastIdx = idx; placeNavInd(links[idx]); activate(screens[idx]); }
      const max = document.documentElement.scrollHeight - innerHeight;
      if (bar) bar.style.transform = `scaleX(${max > 0 ? Math.min(1, scrollY / max) : 0})`;
      depthFrame(screens);
    };
    let lastIdx = -1;
    addEventListener('resize', () => { const a = links[Math.max(0, lastIdx)]; placeNavInd(a); });
    addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } Tip.hide(); }, { passive: true });
    update();
    const findings = $('#s4');
    addEventListener('keydown', e => {
      if (!findings || e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
      const d = { ArrowRight: 1, ArrowLeft: -1 }[e.key]; if (!d) return;
      const a = document.activeElement; if (a && a !== document.body && !a.closest('.pager-tabs')) return;
      const r = findings.getBoundingClientRect(); if (r.top > innerHeight * 0.5 || r.bottom < innerHeight * 0.5) return;
      e.preventDefault(); goPage(cur + d);
    });
    if ('IntersectionObserver' in window && !reduceMotion) {
      const io = new IntersectionObserver(entries => entries.forEach(en => {
        const sc = en.target;
        if (en.intersectionRatio >= 0.25 && !sc.classList.contains('is-in')) { sc.classList.add('is-in'); animateIn(sc.id === 's4' ? pages[cur] : sc); }
        else if (en.intersectionRatio === 0) sc.classList.remove('is-in');
      }), { threshold: [0, 0.25] });
      screens.forEach(sc => io.observe(sc));
    } else screens.forEach(sc => sc.classList.add('is-in'));
    document.addEventListener('click', e => { const a = e.target.closest('a[data-page]'); if (a) goPage(Number(a.dataset.page)); });
  }
  function initUI() {
    /* 全屏放映：浏览器允许时才显示按钮 */
    const pb = $('#present-btn');
    if (pb && document.fullscreenEnabled && document.documentElement.requestFullscreen) {
      pb.hidden = false;
      const sync = () => { const on = !!document.fullscreenElement; pb.textContent = on ? '退出全屏' : '全屏放映'; pb.setAttribute('aria-pressed', String(on)); };
      pb.addEventListener('click', () => { if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen().catch(() => {}); });
      document.addEventListener('fullscreenchange', sync);
      sync();
    }
    document.querySelectorAll('.note-btn').forEach(b => b.addEventListener('click', () => {
      const panel = b.closest('.panel'), open = !panel.classList.contains('note-open');
      document.querySelectorAll('.panel.note-open').forEach(x => { x.classList.remove('note-open'); const nb = x.querySelector('.note-btn'); if (nb) nb.setAttribute('aria-expanded', 'false'); });
      panel.classList.toggle('note-open', open); b.setAttribute('aria-expanded', String(open));
    }));
    document.querySelectorAll('[data-tabs]').forEach(group => {
      const btns = Array.from(group.querySelectorAll('[data-pane]'));
      btns.forEach(b => b.addEventListener('click', () => {
        btns.forEach(x => x.setAttribute('aria-selected', String(x === b)));
        const panel = group.closest('.panel');
        panel.querySelectorAll('.pane').forEach(p => { const on = p.id === b.dataset.pane; p.classList.toggle('is-active', on); p.inert = !on; });
        animateIn(document.getElementById(b.dataset.pane));
      }));
    });
    document.querySelectorAll('.pane:not(.is-active)').forEach(p => { p.inert = true; });
    const drawer = $('#case-drawer'), openBtn = $('#open-cases');
    if (drawer && openBtn) {
      drawer.inert = true;
      const close = () => { drawer.classList.remove('is-open'); drawer.setAttribute('aria-hidden', 'true'); drawer.inert = true; openBtn.focus(); };
      openBtn.addEventListener('click', () => { drawer.classList.add('is-open'); drawer.setAttribute('aria-hidden', 'false'); drawer.inert = false; const c = drawer.querySelector('.drawer-close'); if (c) c.focus(); });
      drawer.querySelectorAll('[data-close]').forEach(b => b.addEventListener('click', close));
      addEventListener('keydown', e => { if (e.key === 'Escape' && drawer.classList.contains('is-open')) close(); });
    }
    const dlg = $('#table-dialog');
    if (dlg) dlg.querySelectorAll('[data-close]').forEach(b => b.addEventListener('click', () => dlg.close()));
  }

  /* ================= 16. 启动 ================= */
  async function init() {
    const legacy = new URLSearchParams(location.search);
    const chapter = legacy.get('chapter');
    if (chapter === 'atlas' || location.hash === '#landscape') {
      const target = new URL('legacy.html', location.href);
      target.search = location.search;
      target.searchParams.set('chapter', 'atlas');
      location.replace(target.href);
      return;
    }
    const section = {home:'s1', question:'s1', collection:'s2', cleaning:'s3', findings:'s4', conclusion:'s5'}[chapter];
    if (section && !location.hash) history.replaceState(null, '', location.pathname + location.search + '#' + section);
    Tip.el = $('#tooltip');
    initUI();
    let M;
    try { M = buildModel(await loadRaw()); }
    catch (err) {
      const box = h('section', { class: 'screen error-screen', role: 'alert' }, h('h2', { text: '图表数据没有读到' }), h('p', { text: `${err.message}。请在项目根目录运行 python3 app/launch.py，再用它打开的地址访问本页；直接双击 HTML 文件时，浏览器会阻止读取本地数据。` }));
      $('#main').prepend(box);
      return;
    }
    const steps = [renderSpecimen, renderTasks, renderLedger, renderCatalog, renderMapping, plateBudget, plateScale, plateConcise, plateLimits, plateLanguage, platePosition, renderFeedback, renderConclusion];
    for (const fn of steps) {
      try { fn(M); } catch (err) { console.error('[知微] ' + fn.name + ' 绘制失败', err); }
    }
    initDepth();
    initDeck();
    document.addEventListener('zhiwei:enter', event => {
      const target = document.getElementById(event.detail.id);
      if (!target) return;
      target.classList.add('is-in');
      animateIn(target.id === 's4' ? target.querySelector('.page.is-active') : target);
      activate(target);
    });
    if (chapter === 'findings') {
      const page = {language:1, position:1, feedback:2}[legacy.get('topic')];
      if (page !== undefined) document.querySelector(`.pager-tabs [data-page="${page}"]`)?.click();
    }
    if (location.hash) { const t = document.querySelector(location.hash); if (t) setTimeout(() => t.scrollIntoView(), 60); }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
