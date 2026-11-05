/* LENS interaction scenes. Existing controllers exclusively own research state and SVGs. */
(() => {
  'use strict';
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const preference = matchMedia('(prefers-reduced-motion: reduce)');
  const deck = $('.deck');
  const active = new Map(), observers = [], listeners = [];
  let frame = 0, running = true, focused = null, returnFocus = null;
  let lastKey = '', transitions = 0, gestures = 0, driver = 'none';
  const counts = {}, initialized = new WeakSet();
  const on = (target, event, fn, options) => {
    target.addEventListener(event, fn, options);
    listeners.push(() => target.removeEventListener(event, fn, options));
  };
  const own = (tag, className, text = '') => {
    const node = document.createElement(tag);
    node.dataset.ixOwned = '';
    node.className = className;
    node.textContent = text;
    return node;
  };
  const click = (node, handler) => {
    node.onclick = handler;
  };
  const scenes = {
    landscape: ['iris', '比较研究条件', '切换任务、模型与趋势／矩阵，在同一研究范围内比较真实结果。', '矩阵中的格子可以点击；选中后，下方显示该条件的实测数值。'],
    concise: ['compare', '配对阅读', '在配对示例与 17 组复现之间切换，先比较评分，再查看实际输出。', '展开真实案例或数据表，核对同一组结果；SVG 与 CSV 导出保留原口径。'],
    language: ['slide', '切换任务对照', '用任务按钮切换 MATH500、GSM8K 与 MMLU-Pro，比较不同模型。', '展开真实案例，查看两种提示的原有匿名回答对照。'],
    position: ['scan', '移动证据位置', '拖动位置滑块，逐一查看九个实际测量位置；区间可以单独开关。', '这里的九位置专项实验与图表库的三位置实验分别展示。'],
    repair: ['rise', '沿修复版本阅读', '切换模型，拖动版本滑块，或播放已有的四轮反馈修复结果。', '这是多轮修复；图表库的五次独立采样属于另一项实验。'],
    limits: ['split', '对照请求与输出', '切换模型、任务与长度单位，比较请求限制和实际返回 token。', '字数、字符数与 token 不是同一个单位；展开表格查看原有测量。'],
    efficiency: ['compare', '查看配对证据', '点击条形或评分点，打开对应模型与任务的配对证据。', '在跨任务证据与 31 种提示之间切换，继续点击提示点查看匿名记录。'],
    'efficiency-prompts': ['scan', '展开提示空间', '切换模型，点击提示点，查看该任务下的实际匿名记录。', '三个任务的 token 横轴独立；不能把横向位置直接当成跨任务开销排名。'],
    'position-matrix': ['matrix', '逐格追踪位置', '切换评分口径，点击矩阵数字，查看对应模型、提示和位置的匿名记录。', '这里比较前、中、后三处，不能作为展示页九位置专项实验的替代。'],
    'position-profile': ['scan', '比较三处实测位置', '切换提示条件与评分口径，对照前、中、后的实测曲线和区间。', '只连接已有的三个实测位置；点击原有记录入口继续核对。'],
    'code-sampling': ['rise', '播放独立采样收益', '点击播放，或拖动 k 滑块，逐步揭示 Pass@1 至 Pass@5。', '点击条件或评分记录继续核对；这五次生成相互独立，不是反馈修复。'],
    'code-prompts': ['matrix', '逐格比较提示', '切换模型、提示范围与 Pass 指标，点击原有条件入口查看证据。', '所有比较沿用相同的 193 道共同可评题，不混入环境排除记录。'],
    'code-errors': ['split', '从错误回到记录', '切换模型、提示范围和错误类别，点击原有图形元素查看对应记录。', '错误类别以现有评分记录为准；环境排除与有效评分分别保留。'],
    'code-tokens': ['iris', '框选并联动', '在散点区域拖动框选；右侧错误率、条件数和记录入口随同一集合更新。', '双击或清除框选可以复位；精确范围表单也能完成选择。'],
    'discovery-1': ['rise', '比较模型输出', '切换模型或点击图表中的已有数据入口，查看原有输出长度对照。', '使用上方发现标签逐项切换，当前筛选与原有导出保持有效。'],
    'discovery-2': ['matrix', '比较提示策略', '切换模型，点击原有策略或条件入口，查看对应匿名记录。', '各任务采用各自的评分口径，不能合并成统一能力分数。'],
    'discovery-3': ['iris', '查看效率折衷', '沿图中的实际条件比较评分与输出开销，点击已有数据入口深入核对。', '输出 token 是返回长度；探索性关系不等同于因果结论。'],
    'discovery-4': ['scan', '对照资料位置', '使用本页已有条件与图表入口，比较文档问答的实测位置效应。', '保留当前实验的文档数与评分口径，不套用九位置专项结果。'],
    'discovery-5': ['split', '检查异常与缺失', '点击已有异常记录入口，核对截断、提取失败与评分状态。', '缺失值保持缺失，异常记录与现有来源说明一起展示。'],
    'chart-model': ['rise', '从模型进入记录', '选择任务、提示和模型，点击柱形打开对应筛选记录。', '详情中的匿名编号可以继续点击；导出沿用当前筛选。'],
    'chart-radar': ['iris', '比较多个维度', '切换模型与提示范围，对照原有雷达维度；点击已有条件进入记录。', '不同轴的含义以原图为准，不把它们重新合成为总分。'],
    'chart-heatmap': ['matrix', '逐格查看条件', '切换核心／全部提示，点击热力格查看对应模型与提示的记录。', '矩阵可在图内滚动；顶部模型、任务和提示筛选继续生效。'],
    'chart-bubble': ['iris', '从气泡查看条件', '切换横轴、模型和提示条件，点击气泡打开对应匿名记录。', '气泡编码与坐标含义沿用原图，交互反馈不改变数值或尺寸语义。'],
    'chart-radial': ['fan', '环形与展开对照', '使用布局控件在环形与展开之间切换，点击已有扇区或条形查看记录。', '切换只改变原有展示方式，当前模型与提示条件继续保留。'],
    'chart-position': ['scan', '沿位置比较', '在带资料问答数据中切换模型与评分，点击原有数据入口查看记录。', '当前视图使用原有三位置数据；没有对应数据时保持原有空状态。'],
    'chart-box': ['curtain', '缩放输出分布', '拖动图表缩放，双击复位；点击箱体或图例定位对应记录。', '也可使用“查看筛选记录”；缩放不改变原始四分位数与须。'],
    'chart-parallel': ['scan', '对照多维条件', '使用模型、任务和提示筛选，沿原有平行坐标比较多个测量维度。', '原图支持的轴与数据入口继续保留；筛选后可导出当前图形。'],
    'chart-distribution': ['split', '并排核对分布', '切换条件，对照输出长度分布与结束状态；点击原有记录入口核对。', '两个图面沿用同一原有筛选范围，不添加新的统计口径。'],
    'chart-behavior': ['split', '选择行为并联动', '点击左侧行为类别，右侧输出状态与记录范围随当前选择更新。', '下方键盘筛选提供同等操作；可清除点选并查看匿名记录。'],
    'chart-timeline': ['scan', '沿请求时间检查', '在带资料问答数据中查看请求序列，点击实际事件打开匿名记录。', '请求重试与代码反馈修复不是同一过程；保持原事件含义。'],
    'chart-tree': ['branch', '展开请求路径', '沿现有请求树查看分支，点击原有路径或记录入口继续检查。', '节点来自真实请求记录；没有记录的分支不会补造事件。'],
    'chart-flow': ['scan', '沿真实路径查看', '切换到带资料问答，使用已有筛选查看原有流程与路径。', '无适用数据时保留明确空状态，可以切换数据集继续探索。'],
  };
  const graphSelector = '#plot,.overview-plot,.publication-frame,.plot-surface,.plot-card';
  function context() {
    if (deck) {
      const section = document.body.dataset.section;
      const root = $('.deck-panel.is-active');
      const key = section === 'findings' ? $('.finding-nav [aria-current="page"]')?.dataset.chapter : section;
      return {key, root, scene: scenes[key]};
    }
    const mode = $('.research-nav [aria-current="page"]')?.id;
    let key;
    if (mode === 'explore-mode') key = 'chart-' + $('#library-chart')?.value;
    else if (mode === 'code-mode') key = 'code-' + $('[data-code-view][aria-current="page"]')?.dataset.codeView;
    else if (mode === 'demo-mode') key = 'discovery-' + (Number($('#chapter-nav [aria-current="page"]')?.dataset.chapter) + 1);
    else if (mode === 'position-mode') key = $('#research-position-view')?.value === 'matrix' ? 'position-matrix' : 'position-profile';
    else key = $('[data-efficiency-view="prompts"]')?.getAttribute('aria-pressed') === 'true' ? 'efficiency-prompts' : 'efficiency';
    return {key, root: $('#stage'), scene: scenes[key]};
  }
  function stop() {
    for (const [control, item] of active) { clearTimeout(item.timer); try { control.cancel(); } catch {} item.reset(); }
    active.clear();
    $$('.ix-click-mark').forEach(e => e.remove());
  }
  function animate(node, values, delay = 0, duration = .48) {
    if (!node || preference.matches || document.hidden || !running || document.documentElement.matches('.intro-pending,.intro-active')) return;
    for (const [previous, item] of active) {
      if (item.node !== node) continue;
      clearTimeout(item.timer); try { previous.cancel(); } catch {} item.reset(); active.delete(previous);
    }
    const styles = Object.keys(values).map(key => {
      const property = key.replace(/[A-Z]/g, letter => '-' + letter.toLowerCase());
      return [property, node.style.getPropertyValue(property), node.style.getPropertyPriority(property)];
    });
    const reset = () => {
      for (const [property, value, priority] of styles) {
        if (value) node.style.setProperty(property, value, priority);
        else node.style.removeProperty(property);
      }
    };
    let control;
    const cleanup = () => {
      if (!active.has(control)) return;
      clearTimeout(active.get(control).timer); active.delete(control);
      try { control.cancel(); } catch {}
      reset();
    };
    try {
      if (window.LensMotion?.animate) {
        driver = 'motion-mini';
        control = window.LensMotion.animate(node, values, {duration, delay, ease: [.22, 1, .36, 1]});
      } else {
        driver = 'web-animations';
        control = node.animate(values, {duration: duration * 1000, delay: delay * 1000, easing: 'cubic-bezier(.22,1,.36,1)', fill: 'both'});
      }
      active.set(control, {node, reset, timer: setTimeout(cleanup, (duration + delay) * 1000 + 80)});
      const completion = control.finished || control;
      if (completion?.then) completion.then(cleanup, cleanup);
    } catch { reset(); /* Static content and native controls stay usable without an animation driver. */ }
  }
  function reveal(node, style, delay = 0) {
    const values = {opacity: [0, 1]};
    if (style === 'iris') values.clipPath = ['circle(22% at 50% 50%)', 'circle(145% at 50% 50%)'];
    else if (style === 'scan') values.clipPath = ['inset(0 95% 0 0)', 'inset(0 0% 0 0)'];
    else if (style === 'matrix' || style === 'curtain') values.clipPath = ['inset(0 0 90% 0)', 'inset(0 0 0% 0)'];
    else if (style === 'fan') values.transform = ['translateY(12px) rotate(-1deg)', 'translateY(0px) rotate(0deg)'];
    else if (style === 'slide' || style === 'compare') values.transform = ['translateX(22px)', 'translateX(0px)'];
    else if (style === 'branch') values.transform = ['translate(-16px,12px)', 'translate(0px,0px)'];
    else values.transform = ['translateY(18px)', 'translateY(0px)'];
    animate(node, values, delay);
  }
  function leaveFocus(restore = true) {
    focused?.classList.remove('ix-focus-target'); focused = null;
    document.body.classList.remove('ix-focus-on');
    $$('[data-ix-focus]').forEach(b => { b.setAttribute('aria-pressed', 'false'); b.lastChild.textContent = '聚焦图表'; });
    if (restore && returnFocus?.isConnected) returnFocus.focus({preventScroll: true});
    returnFocus = null;
  }
  function focusPlot(button, root) {
    if (focused) return leaveFocus();
    stop();
    const target = $(graphSelector, root);
    if (!target) return;
    focused = target; returnFocus = button;
    target.classList.add('ix-focus-target'); document.body.classList.add('ix-focus-on');
    button.setAttribute('aria-pressed', 'true'); button.lastChild.textContent = '退出聚焦 · Esc';
    animate(target, {boxShadow: ['0 0 0 1px #67899b00', '0 0 0 2px #67899bb3,0 18px 45px #071e3020']}, 0, .3);
  }
  function toolbar(root, key, scene) {
    if (!scene || !root) return;
    let bar = $('.ix-reading', root);
    if (bar?.dataset.scene === key) return;
    bar?.remove();
    bar = own('section', 'ix-reading'); bar.dataset.scene = key;
    bar.setAttribute('aria-label', scene[1] + ' · 交互导览');
    const head = own('div', 'ix-reading-head');
    const label = own('div', 'ix-reading-label');
    label.append(own('span', 'ix-optic'), own('strong', '', scene[1]));
    const actions = own('div', 'ix-reading-actions');
    const guide = own('button', 'ix-guide-toggle'); guide.type = 'button';
    guide.dataset.ixGuide = ''; guide.setAttribute('aria-expanded', 'false');
    const guideId = 'ix-guide-' + key;
    guide.setAttribute('aria-controls', guideId);
    guide.append(own('span', '', '操作导览'), own('span', 'ix-chevron', '⌄'));
    const focus = own('button', 'ix-focus-toggle'); focus.type = 'button'; focus.dataset.ixFocus = '';
    focus.setAttribute('aria-pressed', 'false'); focus.append(own('span', 'ix-focus-glyph'), document.createTextNode('聚焦图表'));
    actions.append(guide, focus); head.append(label, actions);
    const body = own('div', 'ix-guide-body'); body.id = guideId; body.hidden = true;
    body.append(own('p', '', scene[2]), own('p', 'ix-guide-note', scene[3]));
    bar.append(head, body);
    const anchor = $('.figure-sheet,.overview-plot,.publication-frame,.metric-grid,.plot-surface,.plot-card', root);
    if (!anchor) return;
    // A full-width sibling preserves every original scientific viewport width and export subtree.
    const figureTools = $('.figure-toolbar', root);
    if (figureTools) figureTools.insertBefore(bar, $('.export-menu', figureTools));
    else anchor.before(bar);
    click(guide, () => {
      const open = body.hidden; body.hidden = !open;
      guide.setAttribute('aria-expanded', String(open));
      if (open) reveal(body, 'rise');
      gestures++;
    });
    click(focus, () => { focusPlot(focus, root); gestures++; });
  }
  const questionTargets = ['concise', 'position', 'repair'];
  function cardButton(card, label, id, fn) {
    const button = own('button', 'ix-card-hit'); button.type = 'button';
    button.setAttribute('aria-label', label); button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-controls', id);
    card.prepend(button); click(button, fn);
    return button;
  }
  function questionCards() {
    const cards = $$('#question .question-points>li');
    cards.forEach((card, i) => {
      if (initialized.has(card)) return; initialized.add(card);
      const panel = own('div', 'ix-dimension-detail'); panel.id = 'ix-dimension-' + i; panel.hidden = true;
      const a = own('a', 'ix-text-link', '进入对应发现 ↗');
      a.href = 'index.html?intro=0&finding=' + questionTargets[i] + '#findings';
      panel.append(a); card.append(panel);
      cardButton(card, '展开 ' + $('strong', card).textContent + ' 研究方向', panel.id, () => {
        const opening = panel.hidden;
        cards.forEach(c => {
          c.classList.remove('ix-selected'); $('.ix-dimension-detail', c).hidden = true;
          $('.ix-card-hit', c)?.setAttribute('aria-expanded', 'false');
        });
        panel.hidden = !opening; card.classList.toggle('ix-selected', opening);
        $('.ix-card-hit', card).setAttribute('aria-expanded', String(opening));
        if (opening) reveal(panel, 'rise', 0);
        gestures++;
      });
    });
  }
  function gatewayHelp() {
    const footer = $('#gateway .gate-foot');
    if (!footer || initialized.has(footer)) return;
    initialized.add(footer);
    const help = own('details', 'ix-home-help');
    help.append(own('summary', '', '探索指引'));
    const content = own('div', '');
    content.append(own('strong', '', '选择一条研究路径'), own('p', '', '点击光球进入章节。方向卡、实验卡和流程节点均可展开；图表上方可打开操作导览或聚焦阅读。'), own('p', '', 'Tab 选择入口，Enter 进入；研究章节可用左右方向键切换。'));
    help.append(content); footer.insertBefore(help, $('.gate-hint', footer));
  }
  function collectionCards() {
    const ledger = $('#collection .task-ledger');
    if (!ledger || initialized.has(ledger)) return; initialized.add(ledger);
    const D = window.LENS_NARRATIVE;
    const descriptions = [
      ['Reasoning & choice', '4 models · GSM8K / MATH500 / MMLU-Pro', D.counts.reasoning, 'Same questions and generation settings; compare 31 prompt strategies within each task.', 'overviewTask=reasoning&overviewModel=qwen&overviewView=curve#landscape'],
      ['Document QA', '2 models · 200 questions', D.counts.document_qa, 'Compare document conditions within this study. The nine-position special study remains separate.', 'overviewTask=document_qa&overviewModel=qwen&overviewView=heatmap#landscape'],
      ['Code generation', '3 models · 194 tasks · 5 independent samples', D.counts.code_generation, '193 common tasks enter scoring. Independent sampling is separate from feedback repair.', 'overviewTask=code_generation&overviewModel=qwen&overviewView=curve#landscape'],
      ['Evidence position', '2 models × 9 positions', D.counts.document_positions, 'The special position study uses the existing nine measured positions and its own research evidence.', 'finding=position#findings'],
      ['Feedback repair', '2 models × 4 strategies × 4 feedback rounds', D.counts.code_repair, 'Follow the existing repair versions. The shared initial draft is counted once.', 'finding=repair#findings'],
    ];
    const detail = own('section', 'ix-experiment-detail'); detail.id = 'ix-experiment-detail'; detail.hidden = true;
    detail.setAttribute('aria-label', 'Selected experiment design');
    ledger.after(detail);
    const cards = [...$$('.task-row', ledger), ...$$('#collection .special-studies>div')];
    cards.forEach((card, i) => {
      cardButton(card, '展开 ' + descriptions[i][0] + ' 实验设计', detail.id, () => {
        const open = !card.classList.contains('ix-selected');
        cards.forEach(c => {c.classList.remove('ix-selected'); $('.ix-card-hit', c).setAttribute('aria-expanded', 'false');});
        detail.replaceChildren(); detail.hidden = !open;
        if (open) {
          card.classList.add('ix-selected'); $('.ix-card-hit', card).setAttribute('aria-expanded', 'true');
          const [name, scope, count, note, target] = descriptions[i];
          const copy = own('div', '');
          copy.append(own('span', 'ix-eyebrow', 'EXPERIMENT DESIGN'), own('h3', '', name), own('p', '', scope), own('p', 'ix-detail-note', note));
          const meta = own('div', 'ix-experiment-meta');
          meta.append(own('strong', '', Number(count).toLocaleString('en-US')), own('span', '', 'saved responses'));
          const link = own('a', 'ix-text-link', '查看对应研究 ↗'); link.href = 'index.html?intro=0&' + target;
          meta.append(link); detail.append(copy, meta); reveal(detail, 'compare');
        }
        gestures++;
      });
    });
  }
  function pipeline() {
    const list = $('#cleaning .cleaning-steps');
    if (!list || initialized.has(list)) return; initialized.add(list);
    const info = own('section', 'ix-pipeline-info'); info.id = 'ix-pipeline-info'; info.hidden = true;
    info.setAttribute('aria-label', 'Selected data processing stage');
    $('#cleaning .schema-preview').before(info);
    const stages = [
      ['Freeze & join', 'Keep source files unchanged. Stable anonymous keys connect the saved response to its condition.', ['record_id']],
      ['Normalize', 'Inspect normalized model, benchmark and prompt fields without merging task-specific metrics.', ['model_id', 'benchmark', 'prompt_id']],
      ['Keep missingness distinct', 'Inspect stop reason, truncation and the saved metric. A missing or excluded result does not become zero.', ['finish_reason', 'is_truncated', 'metric_name', 'metric_value']],
      ['Anonymize & derive', 'This is the existing public anonymous example. No raw answer or private identity is introduced.', ['record_id', 'output_tokens']],
    ];
    const steps = $$(':scope>li', list);
    steps.forEach((step, i) => cardButton(step, '查看 ' + stages[i][0] + ' 处理阶段', info.id, () => {
      const open = !step.classList.contains('ix-selected');
      steps.forEach(s => {s.classList.remove('ix-selected'); $('.ix-card-hit', s).setAttribute('aria-expanded', 'false');});
      $$('#cleaning .schema-key').forEach(k => k.classList.remove('ix-key-selected'));
      info.hidden = !open; info.replaceChildren();
      if (open) {
        step.classList.add('ix-selected'); $('.ix-card-hit', step).setAttribute('aria-expanded', 'true');
        info.append(own('strong', '', stages[i][0]), own('p', '', stages[i][1]));
        $$('#cleaning .schema-key').forEach(k => {if (stages[i][2].includes(k.textContent.replaceAll('"', ''))) k.classList.add('ix-key-selected');});
        reveal(info, 'rise');
      }
      gestures++;
    }));
  }
  function playScene() {
    frame = 0;
    if (!running || document.hidden) return;
    window.LensMotionUI?.settle(); window.LensSiteUI?.settle(); stop();
    const {root, key, scene} = context();
    gatewayHelp();
    if (!root || key === 'gateway') {lastKey = key; return;}
    if (focused && (!focused.isConnected || lastKey !== key)) leaveFocus(false);
    questionCards(); collectionCards(); pipeline();
    toolbar(root, key, scene);
    root.dataset.ixScene = key || '';
    if (key !== lastKey) leaveFocus(false);
    lastKey = key; counts[key] = (counts[key] || 0) + 1; transitions++;
    if (inspector && !inspector.hidden) {reveal(inspector, 'slide'); return;}
    // Own additions may wake the older enhancement. Settle it after its observer runs.
    queueMicrotask(() => {
      window.LensMotionUI?.settle(); window.LensSiteUI?.settle();
      if (!running || document.hidden) return;
      const header = $('.panel-header,.question-copy h1,.research-heading,.page-header', root);
      reveal(header, 'rise');
      if (key === 'question') {
        $$('.question-points>li', root).forEach((card, i) => animate(card, {opacity: [0, 1], transform: [`translate(${(i - 1) * 14}px,20px)`, 'translate(0px,0px)']}, i * .055));
      } else if (key === 'collection') {
        reveal($('.experiment-flow', root), 'scan', .04);
        $$('.task-row,.special-studies>div', root).forEach((c, i) => reveal(c, 'rise', Math.min(i * .045, .16)));
      } else if (key === 'cleaning') {
        reveal($('.schema-block', root), 'slide', .025);
        $$('.cleaning-steps>li', root).forEach((c, i) => reveal(c, 'rise', i * .045));
      } else {
        const graphs = $$(graphSelector, root).filter(e => !e.parentElement.closest(graphSelector));
        graphs.forEach((g, i) => reveal(g, scene?.[0] || 'rise', Math.min(i * .05, .12)));
        if (scene?.[0] === 'split') {
          $$('.plot-content.dual>div', root).slice(0, 2).forEach((g, i) => animate(g, {opacity: [0, 1], transform: [`translateX(${i ? 14 : -14}px)`, 'translateX(0px)']}, .08 + i * .05));
        }
        reveal($('.ix-reading', root), 'rise', .045);
      }
    });
  }
  function schedule() {
    if (!running || frame) return;
    frame = requestAnimationFrame(playScene);
  }
  function observe(node, options, fn = schedule) {
    if (!node) return;
    const observer = new MutationObserver(records => {
      if (records.every(r => r.type === 'childList' && [...r.addedNodes, ...r.removedNodes].every(n => n.nodeType === 1 && n.hasAttribute('data-ix-owned')))) return;
      fn(records);
    });
    observer.observe(node, options); observers.push(observer);
  }
  observe(document.body, {attributes: true, attributeFilter: ['data-section']});
  if (deck) {
    observe($('#research'), {childList: true});
    observe($('.overview-plot'), {childList: true});
  } else observe($('#stage'), {childList: true});
  const inspector = $('#inspector');
  observe(inspector, {attributes: true, attributeFilter: ['hidden']}, () => {
    if (!inspector.hidden) { leaveFocus(false); reveal(inspector, 'slide', 0); }
  });
  on(document, 'click', event => {
    const element = event.target instanceof Element ? event.target : null;
    if (!element || element.closest('#gateway,#lens-intro')) return;
    const control = element.closest('button,summary');
    if (control && !control.disabled && !control.closest('svg')) {
      gestures++;
      animate(control, {scale: [1, .97, 1]}, 0, .24);
    }
    const graph = element.closest('#plot,.overview-plot,.publication-svg,#library-main,#library-side,#code-vega-scatter,#code-linked-errors');
    if (graph && !preference.matches && !document.hidden && event.detail > 0) {
      const mark = own('span', 'ix-click-mark');
      mark.style.left = event.clientX + 'px'; mark.style.top = event.clientY + 'px';
      mark.setAttribute('aria-hidden', 'true'); document.body.append(mark);
      animate(mark, {opacity: [.8, 0], transform: ['translate(-50%,-50%) scale(.5)', 'translate(-50%,-50%) scale(1.7)']}, 0, .36);
      setTimeout(() => mark.remove(), 440);
    }
  });
  on(document, 'change', event => {
    if (event.target.matches('select,input[type="checkbox"]')) {
      gestures++; schedule();
    }
  });
  on(document, 'toggle', event => {
    const detail = event.target;
    if (detail instanceof HTMLDetailsElement && detail.open && !detail.closest('#gateway')) {
      reveal($(':scope>div,:scope>.data-scroll,:scope>.answer', detail), 'rise', 0);
    }
  }, true);
  on(document, 'keydown', event => {if (event.key === 'Escape') leaveFocus();});
  on(document, 'visibilitychange', () => {
    if (document.hidden) {stop(); if (frame) cancelAnimationFrame(frame); frame = 0;}
  });
  on(preference, 'change', () => {stop(); window.LensMotionUI?.settle(); window.LensSiteUI?.settle();});
  function suspend() {
    running = false; stop(); leaveFocus(false);
    if (frame) cancelAnimationFrame(frame); frame = 0;
    observers.forEach(o => o.disconnect());
    $$('[data-ix-owned]').forEach(node => {node.onclick = null;});
    listeners.splice(0).forEach(remove => remove());
  }
  on(window, 'pagehide', suspend);
  const restore = event => {if (event.persisted) location.reload();};
  window.addEventListener('pageshow', restore);
  window.LensInteractions = {
    inspect: () => ({version: 1, key: context().key, running: active.size, scheduled: !!frame, transitions, gestures, driver, reducedMotion: preference.matches, focus: !!focused, sceneCounts: {...counts}, scenes: Object.keys(scenes), suspended: !running}),
    settle: stop,
    dispose: () => {suspend(); window.removeEventListener('pageshow', restore);},
  };
  schedule();
})();
