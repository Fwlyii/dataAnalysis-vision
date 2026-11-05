/* Static research evidence. Incomplete or synthetic batches are never published. */
const ARM_INFO = [
  ['resample', '独立重采样', '重新回答同一道题，不接收前一版代码和测试反馈。'],
  ['self_review', '自行检查', '看到前一版代码，按统一指令自行检查，不接收执行结果。'],
  ['pass_fail', '仅通过状态', '在自行检查的基础上，只告知公开测试通过或失败。'],
  ['diagnostic', '语法与运行诊断', '给出实际错误类型、消息和可获得的行列、源码及候选栈信息。'],
  ['counterexample', '单个失败反例', '给出首个公开失败输入、期望结果与实际结果或异常。'],
  ['multi_counterexample', '多反例与测试摘要', '最多给出三个不同的公开失败反例，并报告真实测试计数。'],
];
const FIGURES = [
  ['initial-error-support', 'A', '先看初稿究竟错在哪里', '错误类型只统计真实出现的初始程序。重复初稿增加程序数，不增加独立题目数；没有出现的错误类型不能据此评估其修复效果。'],
  ['strong-endpoints', 'B', '先用强保留测试判断最终质量', '初稿与第五版都接受公开测试和额外保留测试。这里比较当前版本的完整正确性；后续版本可能修复错误，也可能破坏原本正确的代码。'],
  ['public-trajectories', 'C', '再展开五版代码的公开诊断轨迹', '第一版为共享初稿，随后四次按各策略生成。这条曲线仅表示模型可见的公开诊断通过率；强保留测试的结果单独呈现。'],
  ['repair-regression', 'D', '把修复和回退同时摆出来', '初稿错误时能否修复，与初稿正确时是否回退，分母不同。净提升应连同这两个方向一起理解。'],
  ['cost-quality', 'E', '得到的质量，付出了多少 Token', '以实测链路的输入与输出 Token 总量，对照终稿强测试表现。Token 缺失按原始记录披露；多次调用与更多独立题目是不同的统计量。'],
];
const CATEGORY = {
  diagnostic_repair: '执行诊断后的修复',
  semantic_repair: '语义反例后的修复',
  regression: '原本正确，后续版本回退',
  diagnostic_hidden_gap: '公开通过，保留测试仍失败',
};
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
const finite = value => typeof value === 'number' && Number.isFinite(value);
const number = value => finite(value) ? value.toLocaleString('zh-CN') : '未汇总';
const rate = value => finite(value) ? `${(value * 100).toFixed(1)}%` : '未测';
const signed = value => finite(value) ? `${value > 0 ? '+' : ''}${value.toFixed(1)}` : '未测';
const interval = values => Array.isArray(values) && values.length === 2 && values.every(finite)
  ? `[${signed(values[0])}, ${signed(values[1])}]` : '未估计';
const asNumber = value => value === '' || value === null || value === undefined ? null : Number.isFinite(Number(value)) ? Number(value) : null;
const armLabel = (evidence, arm) => evidence.arms.find(row => row.id === arm)?.label || ARM_INFO.find(row => row[0] === arm)?.[1] || arm;
const modelLabel = (evidence, model) => evidence.model_labels?.[model] || model;

function publishable(evidence, manifest) {
  const c = evidence?.coverage;
  if (evidence?.synthetic !== false || evidence.status !== 'complete' || c?.complete !== true) return false;
  if (!finite(c.planned_tasks) || c.planned_tasks <= 0 || c.task_clusters !== c.planned_tasks || c.public_task_clusters !== c.planned_tasks || c.missing_count !== 0) return false;
  if (!finite(c.expected_physical_responses) || c.saved_physical_responses !== c.expected_physical_responses || c.saved_physical_responses !== evidence.saved_physical_responses) return false;
  if (![c.public_cases, c.holdout_cases, evidence.repeats_per_task, evidence.rounds].every(value => finite(value) && value > 0)) return false;
  if (!Array.isArray(evidence.models) || !evidence.models.length || !Array.isArray(evidence.arms) || !Array.isArray(evidence.summary)) return false;
  if (!ARM_INFO.every(([id]) => evidence.arms.some(row => row.id === id))) return false;
  if (!evidence.models.every(model => ARM_INFO.every(([arm]) => evidence.summary.some(row => row.model === model && row.arm === arm && row.task_clusters === c.planned_tasks)))) return false;
  if (!manifest || manifest.synthetic === true || (manifest.batch_id && manifest.batch_id !== evidence.batch_id)) return false;
  const figures = Array.isArray(manifest) ? manifest : manifest.figures;
  return Array.isArray(figures) && FIGURES.every(([id]) => figures.some(row => row.id === id && /^[\w.-]+\.svg$/i.test(row.file || '')));
}

function getContrast(evidence, model, arm, baseline) {
  const direct = evidence.contrasts?.find(row => row.model === model && row.arm === arm && row.baseline === baseline);
  if (direct) return direct;
  const reverse = evidence.contrasts?.find(row => row.model === model && row.arm === baseline && row.baseline === arm);
  return reverse ? {...reverse, arm, baseline, delta_pp: finite(reverse.delta_pp) ? -reverse.delta_pp : null,
    ci_low_pp: finite(reverse.ci_high_pp) ? -reverse.ci_high_pp : null,
    ci_high_pp: finite(reverse.ci_low_pp) ? -reverse.ci_low_pp : null,
    arm_wins: reverse.baseline_wins, baseline_wins: reverse.arm_wins} : null;
}

function contrastReading(row) {
  if (!row || ![row.delta_pp, row.ci_low_pp, row.ci_high_pp].every(finite)) return '当前比较没有可用的配对区间。';
  if (row.ci_low_pp > 0) return '区间整体高于 0，本批题目中支持正向差异。';
  if (row.ci_high_pp < 0) return '区间整体低于 0，本批题目中支持负向差异。';
  return '区间包含 0，尚不能认定存在稳定提升。';
}

function renderTakeaways(evidence) {
  const models=evidence.models.map(model=>{
    const single=evidence.summary.find(row=>row.model===model&&row.arm==='counterexample');
    const self=evidence.summary.find(row=>row.model===model&&row.arm==='self_review');
    const comparison=getContrast(evidence,model,'counterexample','self_review');
    if(!single||!self||!comparison||![comparison.delta_pp,comparison.ci_low_pp,comparison.ci_high_pp].every(finite))return '';
    return `<article><h4>${esc(modelLabel(evidence,model))}</h4><p class="fex-takeaway-value">${rate(single.final_rate)}<span>单反例 / ${rate(self.final_rate)} 自查</span></p><p>终稿完整通过 ${number(single.final_success)} / ${number(single.programs)}，自行检查 ${number(self.final_success)} / ${number(self.programs)}。</p><p>配对差 ${signed(comparison.delta_pp)} 个百分点，95%区间 [${signed(comparison.ci_low_pp)}, ${signed(comparison.ci_high_pp)}]。${contrastReading(comparison)}</p></article>`;
  }).join('');
  const multi=evidence.models.map(model=>getContrast(evidence,model,'multi_counterexample','counterexample'));
  const noStableExtra=multi.every(row=>row&&finite(row.ci_low_pp)&&finite(row.ci_high_pp)&&row.ci_low_pp<=0&&row.ci_high_pp>=0);
  return `<section class="fex-takeaways" aria-label="补充实验的主要发现">${models}</section>${noStableExtra?'<p class="fex-takeaway-note">两模型中，多反例相对单反例的配对区间都包含 0；本轮尚未观察到稳定的额外收益。以下继续拆解错误类型、修改轨迹与 Token 代价。</p>':''}`;
}

function renderDesign(evidence) {
  const c = evidence.coverage;
  const repeats = c.repeats_per_task ?? evidence.repeats_per_task;
  const initials = finite(repeats) ? c.planned_tasks * evidence.models.length * repeats : null;
  const accounting = evidence.request_accounting;
  const attempts = accounting?.http_attempts;
  const g=evidence.generation_settings||{},x=evidence.execution_settings||{};
  const settings=[];
  if(finite(g.temperature)&&finite(g.top_p)&&finite(g.max_tokens))settings.push(`两模型统一采用温度 ${g.temperature}、top_p ${g.top_p}，单次输出上限 ${number(g.max_tokens)} Token`);
  if(g.qwen3_enable_thinking===false)settings.push('Qwen3采用非思考模式');
  if(finite(x.memory_limit_mb)&&finite(x.holdout_timeout_s))settings.push(`每程序内存上限 ${number(x.memory_limit_mb)} MB，完整验证墙钟上限 ${number(x.holdout_timeout_s)} 秒`);
  const settingsNote=settings.length?`<p class="fex-source">${settings.map(esc).join('；')}。</p>`:'';
  return `<header class="fex-heading"><p class="fex-kicker">代码执行反馈 · 扩展实验</p><h3>同样的执行反馈，在不同模型上收益不同。</h3><p class="fex-lead">单个失败反例相对自行检查的收益，先按模型分别看。通过率使用公开与保留测试的联合判定，区间按题目聚类；以下比较为预设探索分析。</p></header>${renderTakeaways(evidence)}
  <section class="fex-section fex-design" aria-label="实验设计与样本规模">
    <div class="fex-ledger"><div><strong>${number(c.planned_tasks)}</strong><span>独立编程题</span></div><div><strong>${number(repeats)}</strong><span>每题、每模型独立初稿</span></div><div><strong>${number(evidence.models.length)} × ${number(evidence.arms.length)}</strong><span>模型 × 修复策略</span></div><div><strong>${number(c.saved_physical_responses)}</strong><span>实际保存的有效模型响应</span></div></div>
    <p class="fex-method">共 ${number(initials)} 份独立初稿；同一初稿分到六条策略链，各自再生成 ${number(evidence.rounds - 1)} 版。统计独立单位仍为 ${number(c.planned_tasks)} 道题，不能把重复初稿、修复版本或测试输入当成更多独立题目。</p>
    <p class="fex-source">${finite(attempts) ? `实际 HTTP 请求尝试 ${number(attempts)} 次${finite(accounting.transport_retries) ? `，其中重试请求 ${number(accounting.transport_retries)} 次` : ''}。` : '有效模型响应与含重试的 API 请求尝试分开计数；本快照未汇总后者。'} 批次：<code>${esc(evidence.batch_id)}</code>。</p>
    ${settingsNote}<div class="fex-splits"><article><span class="fex-split-label">模型能看到的诊断</span><h4>公开基础测试</h4><p><strong>${number(c.public_cases)}</strong> 条输入，合计覆盖全部题目。各版代码接受公开诊断，反馈仅来自这一部分。</p></article><article><span class="fex-split-label">模型看不到的验证</span><h4>额外强保留测试</h4><p><strong>${number(c.holdout_cases)}</strong> 条与公开输入分离的去重输入，合计覆盖全部题目。初稿与终稿为主要强测端点${evidence.strong_trajectory_task_clusters > 0 ? '，中间版本的离线强复测另图报告' : ''}；保留结果不进入反馈。</p></article></div>
    <p class="fex-source">输入数量为全题库合计，实际执行数量按逐程序记录保留。强测试成功要求当前代码同时通过公开与保留两部分；已确认失败的代码即使未扫描所有输入，也不能记为通过。</p>
    <p class="fex-source">实际逐例执行以 <code>cases_checked</code> 为准。语法或加载失败会阻断整个测试组，原记录中的失败、阻断与未执行标签有重叠，分别解释。</p>
  </section>
  <section class="fex-section" aria-label="六种反馈条件"><div class="fex-section-heading"><span class="fex-index">01</span><div><h4>六条策略链，控制反馈究竟带来了什么</h4><p>从独立重做、自行检查，走向执行状态、诊断与具体反例。六种条件共享同一初稿，按题目配对比较。</p></div></div><ol class="fex-arms">${ARM_INFO.map(([id, label, text], index) => `<li><span class="fex-arm-number">${index + 1}</span><div><h5>${esc(armLabel(evidence, id) || label)}</h5><p>${esc(text)}</p></div></li>`).join('')}</ol></section>`;
}

function renderFigure(manifest, id, prefix) {
  const figure = (Array.isArray(manifest) ? manifest : manifest.figures).find(row => row.id === id);
  const [, letter, title, caption] = FIGURES.find(row => row[0] === id);
  return `<figure class="fex-figure"><figcaption><span class="fex-figure-letter">${letter}</span><div><h4>${esc(title)}</h4><p>${esc(caption)}</p></div></figcaption><div class="fex-plot" tabindex="0" role="region" aria-label="${esc(title)}，窄屏可水平滚动"><img src="${esc(prefix + figure.file)}" alt="${esc(figure.title || title)}" width="1200" loading="lazy" decoding="async"></div></figure>`;
}

function renderStrongTrajectory(evidence, manifest, prefix) {
  const figure = (Array.isArray(manifest) ? manifest : manifest.figures).find(row => row.id === 'strong-trajectories');
  const count = evidence.strong_trajectory_task_clusters;
  if (!figure || !/^[\w.-]+\.svg$/i.test(figure.file || '') || !finite(count) || count <= 0 || !evidence.strong_curves?.length) return '';
  const all = evidence.strong_trajectory_complete === true && count === evidence.coverage.planned_tasks;
  return `<figure class="fex-figure"><figcaption><span class="fex-figure-letter">C+</span><div><h4>用离线强测验证五版轨迹</h4><p>${all ? `全部 ${number(count)} 道计划题均已完成五版强测。` : `本图仅包含 ${number(count)} / ${number(evidence.coverage.planned_tasks)} 道五版强测齐全的题，属于完整配对子队列，不能当成全题库结果。`} 每道入图题目的全部模型、初稿、策略和版本均有强测判定；这些结果不进入模型反馈。</p></div></figcaption><div class="fex-plot" tabindex="0" role="region" aria-label="五版强测试轨迹，窄屏可水平滚动"><img src="${esc(prefix + figure.file)}" alt="${esc(figure.title || '强保留测试的五版轨迹')}" width="1200" loading="lazy" decoding="async"></div></figure>`;
}

function renderResults(evidence) {
  return `<section class="fex-section" aria-label="按模型的终稿结果"><div class="fex-section-heading"><span class="fex-index">03</span><div><h4>把每个模型的结果分别说清楚</h4><p>每格分母为该模型的题目数 × 独立初稿数；初稿由六条策略共享。净变化的区间以题目为簇，保留同题的重复初稿和配对关系。</p></div></div>${evidence.models.map(model => {
    const rows = evidence.summary.filter(row => row.model === model);
    const initialChanges=rows[0]?.initial_public_recheck_changes;
    const finalChanges=rows.every(row=>finite(row.final_public_recheck_changes))?rows.reduce((sum,row)=>sum+row.final_public_recheck_changes,0):null;
    const rechecks=finite(initialChanges)&&finite(finalChanges)?`<p class="fex-source">原公开测试在完整复测中的判定变化：共同初稿 ${number(initialChanges)} 份，六组终稿合计 ${number(finalChanges)} 份；共同初稿只计一次。</p>`:'';
    const comparisons = [['counterexample', 'self_review'], ['diagnostic', 'counterexample'], ['multi_counterexample', 'counterexample']]
      .map(([arm, baseline]) => ({arm, baseline, row:getContrast(evidence, model, arm, baseline)})).filter(item => item.row);
    return `<article class="fex-model"><h5>${esc(modelLabel(evidence, model))}</h5><div class="fex-table-wrap" tabindex="0" role="region" aria-label="模型结果表，窄屏可水平滚动"><table class="fex-results-table"><caption>${esc(modelLabel(evidence, model))}：各策略当前终稿的强测试结果</caption><thead><tr><th scope="col">策略</th><th scope="col">初稿通过</th><th scope="col">终稿通过</th><th scope="col">净变化 / 百分点<br><span>95% 配对区间</span></th><th scope="col">初错修复</th><th scope="col">初对回退</th><th scope="col">公开通过<br>保留失败</th></tr></thead><tbody>${rows.map(row => `<tr><th scope="row">${esc(armLabel(evidence, row.arm))}</th><td>${number(row.initial_success)} / ${number(row.programs)}<small>${rate(row.initial_rate)}</small></td><td>${number(row.final_success)} / ${number(row.programs)}<small>${rate(row.final_rate)}</small></td><td>${signed(row.net_gain_pp)}<small>${interval(row.net_gain_ci_pp)}</small></td><td>${number(row.repaired)} / ${number(row.initial_failures)}<small>${rate(row.repair_rate)}</small></td><td>${number(row.regressed)} / ${number(row.initial_correct)}<small>${rate(row.regression_rate)}</small></td><td>${number(row.final_public_pass_hidden_fail)}<small>已确认的终稿数</small></td></tr>`).join('')}</tbody></table></div>${rechecks}${comparisons.length ? `<div class="fex-comparisons">${comparisons.map(({arm, baseline, row}) => `<div class="fex-comparison"><h6>${esc(armLabel(evidence, arm))} 相对 ${esc(armLabel(evidence, baseline))}</h6><p class="fex-effect">${signed(row.delta_pp)} <span>个百分点</span><small>95% CI ${interval([row.ci_low_pp, row.ci_high_pp])}</small></p><p>${contrastReading(row)}</p></div>`).join('')}</div>` : ''}</article>`;
  }).join('')}<p class="fex-source">“公开通过、保留失败”只计模型当时看到的公开诊断通过、保留测试已确认失败的终稿；复测中的公开判定变化单独列出。区间采用按题目分簇的配对 Bootstrap。上述两两比较属于探索性比较，未作多重比较校正；区间包含 0 时，不宣称稳定提升。不同模型的差异分别解释。</p></section>`;
}

function publicOutcome(report) {
  if (!report) return '未测';
  const status = report.passed === true ? '通过' : report.passed === false ? '失败' : '未知';
  const checked = finite(report.cases_checked) ? `；实测 ${number(report.cases_checked)} / ${number(report.total_cases)} 条` : '';
  const scan = report.scan_complete === false ? '；未完成全扫描' : '';
  return status + checked + scan;
}
function strongOutcome(value) { return value === true ? '通过' : value === false ? '失败' : '未做强测'; }

const COMPACT_ARMS = [
  ['resample','独立重采样','#b5c7d0'],['self_review','自行检查','#f4cf84'],
  ['pass_fail','仅通过状态','#76ccff'],['diagnostic','错误定位诊断','#d6c3ff'],
  ['counterexample','单个失败反例','#ff967f'],['multi_counterexample','多个失败反例','#61e6d3'],
];

function compactEndpointFigure(evidence, figures, prefix) {
  const figure=(Array.isArray(figures)?figures:figures.figures).find(row=>row.id==='strong-endpoints');
  const extentValues=evidence.summary.flatMap(row=>[row.initial_rate,row.final_rate,...(Array.isArray(row.final_ci)?row.final_ci:[])]).filter(finite);
  const axisMinimum=extentValues.length?Math.max(0,Math.floor((Math.min(...extentValues)*100-5)/10)*10):0;
  const axisMaximum=extentValues.length?Math.min(100,Math.ceil((Math.max(...extentValues)*100+5)/10)*10):100;
  const text=(x,y,value,size=13,fill='#f5fbff',anchor='start',weight=400)=>`<text x="${x}" y="${y}" font-size="${size}" fill="${fill}" text-anchor="${anchor}" font-weight="${weight}">${esc(value)}</text>`;
  const line=(x1,y1,x2,y2,color='#315361',width=1)=>`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" stroke-width="${width}"/>`;
  const circle=(x,y,r,fill,stroke)=>`<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}" stroke="${stroke}" stroke-width="1.6"/>`;
  const panels=evidence.models.map((model,index)=>{
    const offset=index*550,x=v=>offset+153+(v*100-axisMinimum)/(axisMaximum-axisMinimum||1)*242;
    let body=text(offset+18,29,modelLabel(evidence,model),18,'#f5fbff','start',600);
    for(let tick=axisMinimum;tick<=axisMaximum;tick+=10)body+=line(x(tick/100),58,x(tick/100),236)+text(x(tick/100),49,tick+'%',11,'#b5d1de','middle');
    COMPACT_ARMS.forEach(([arm,label,color],i)=>{
      const row=evidence.summary.find(row=>row.model===model&&row.arm===arm);if(!row)return;
      const y=78+i*29;
      body+=`<g data-model="${esc(model)}" data-arm="${arm}" data-initial-rate="${row.initial_rate}" data-final-rate="${row.final_rate}" data-final-ci-low="${row.final_ci?.[0]??''}" data-final-ci-high="${row.final_ci?.[1]??''}">`;
      body+=text(offset+18,y+4,label,13);
      if(finite(row.initial_rate)&&finite(row.final_rate))body+=line(x(row.initial_rate),y,x(row.final_rate),y,color,2.2)+circle(x(row.initial_rate),y,4,'#042735','#b5d1de')+circle(x(row.final_rate),y,4.5,color,color);
      if(Array.isArray(row.final_ci)&&row.final_ci.length===2&&row.final_ci.every(finite)){
        const [low,high]=row.final_ci;body+=line(x(low),y,x(high),y,color,1.3)+line(x(low),y-4,x(low),y+4,color,1.3)+line(x(high),y-4,x(high),y+4,color,1.3);
      }
      body+=text(offset+529,y+4,`${number(row.final_success)}/${number(row.programs)} · ${rate(row.final_rate)}`,13,color,'end',500);
      body+='</g>';
    });
    return body;
  }).join('');
  return `<figure class="fex-compact-figure" data-source-svg="${esc(prefix+figure.file)}"><div class="fex-compact-plot" tabindex="0" role="region" aria-label="双模型终稿图，窄屏可横向滚动"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 278" width="1100" height="278" role="img" aria-labelledby="fex-compact-chart-title fex-compact-chart-desc" data-fex-figure="strong-endpoints" data-axis-min="${axisMinimum}" data-axis-max="${axisMaximum}" data-source-svg="${esc(prefix+figure.file)}"><title id="fex-compact-chart-title">两模型、六种反馈的终稿完整测试通过率</title><desc id="fex-compact-chart-desc">每组492份程序，来自164道独立题与每题三份初稿。空心点为共同初稿，实心点为第四次后续生成；横线为终稿95%按题目聚类区间。完整通过要求公开与保留测试同时通过。两模型共用显式截取的横轴${axisMinimum}到${axisMaximum}%，覆盖全部初稿、终稿与置信区间。</desc><style>text{font-family:"PingFang SC","Microsoft YaHei",sans-serif;font-variant-numeric:tabular-nums}</style><rect width="1100" height="278" rx="8" fill="#042735"/>${panels}${text(18,265,`空心＝共同初稿 · 实心＝终稿 · 横线＝95%按题目聚类区间；横轴截取${axisMinimum}–${axisMaximum}%。`,11,'#b5d1de')}${text(1082,265,'HumanEval+ Full v0.1.10',11,'#b5d1de','end')}</svg></div></figure>`;
}

function compactModelContrasts(evidence) {
  return evidence.models.map(model=>{
    const single=evidence.summary.find(row=>row.model===model&&row.arm==='counterexample');
    const multi=evidence.summary.find(row=>row.model===model&&row.arm==='multi_counterexample');
    const self=evidence.summary.find(row=>row.model===model&&row.arm==='self_review');
    const main=getContrast(evidence,model,'counterexample','self_review');
    const extra=getContrast(evidence,model,'multi_counterexample','counterexample');
    if(!single||!multi||!self||!main||!extra)return '';
    const cost=finite(single.mean_chain_total_tokens)&&single.mean_chain_total_tokens>0&&finite(multi.mean_chain_total_tokens)?100*(multi.mean_chain_total_tokens/single.mean_chain_total_tokens-1):null;
    const ci=values=>values.every(finite)?`[${values.map(value=>`${value>0?'+':''}${value.toFixed(2)}`).join(', ')}]`:'未测';
    const delta=finite(main.delta_pp)?`${main.delta_pp>0?'+':''}${main.delta_pp.toFixed(2)}`:'未测';
    const stable=main.ci_low_pp>0?'本批支持正向差异':'区间含0，差异尚不明确';
    const extraReading=extra.ci_low_pp<=0&&extra.ci_high_pp>=0?'区间含0，未见稳定额外收益':contrastReading(extra);
    return `<article class="fex-compact-comparison" data-model="${esc(model)}"><h4>${esc(modelLabel(evidence,model))}</h4><p class="fex-compact-main-effect"><strong>${delta}<span> pp</span></strong><span>单反例相对自查 · 95% CI ${ci([main.ci_low_pp,main.ci_high_pp])}</span></p><p>${stable}；${rate(single.final_rate)} 对 ${rate(self.final_rate)}。</p><p class="fex-compact-cost">多反例相对单反例：95% CI ${ci([extra.ci_low_pp,extra.ci_high_pp])} pp，${extraReading}；整链 Token ${finite(cost)?`${cost>0?'+':''}${cost.toFixed(2)}%`:'未测'}。</p></article>`;
  }).join('');
}

function compactFeedbackExcerpt(example) {
  const raw=typeof example.actual_feedback==='string'?example.actual_feedback:'';
  const prefix='Diagnostic test feedback:\n';
  if(raw.startsWith(prefix)){
    try {
      const report=JSON.parse(raw.slice(prefix.length).split('\n\n')[0]);
      const projection={diagnostic_status:report.diagnostic_status};
      if(report.diagnostic){
        projection.diagnostic={};
        for(const key of ['error_type','error_message','line','column','source_line'])if(Object.hasOwn(report.diagnostic,key))projection.diagnostic[key]=report.diagnostic[key];
      }else if(Array.isArray(report.failures)&&report.failures.length){
        const first={};for(const key of ['input','expected','actual'])if(Object.hasOwn(report.failures[0],key))first[key]=report.failures[0][key];
        projection.failures=[first];
      }
      return {kind:report.diagnostic?'diagnostic-projection':'failure-projection',text:JSON.stringify(projection,null,2),label:report.diagnostic?'实际诊断摘录 · 原字段原值':'首个公开反例摘录 · 输入、期望与实际输出'};
    }catch{}
  }
  const commonEnd=raw.indexOf(' Return the complete implementation');
  return {kind:'literal-prefix',text:commonEnd>=0?raw.slice(0,commonEnd):raw,label:'实际指令摘录 · 无执行反馈'};
}

function compactCases(evidence) {
  const all=Array.isArray(evidence.examples)?evidence.examples:[];
  const repair=all.find(row=>row.category==='semantic_repair'&&row.before_strong_pass===false&&row.after_strong_pass===true)||all.find(row=>row.category==='diagnostic_repair'&&row.before_strong_pass===false&&row.after_strong_pass===true);
  const regression=all.find(row=>row.category==='regression'&&row.before_strong_pass===true&&row.after_strong_pass===false);
  const selected=[repair,regression].filter(Boolean);
  return `<section class="fex-compact-case-section" aria-label="执行反馈的真实修复与隐蔽回退"><header class="fex-compact-case-heading"><h3>真实修改：既看修复，也看隐蔽回退</h3><p>${number(selected.length)} 个已知相邻版本案例；反馈字段取自当步原文，代码差异完整保留。</p></header><div class="fex-compact-cases">${selected.map((example,index)=>{
    const excerpt=compactFeedbackExcerpt(example);
    const hasDiff=typeof example.diff==='string'&&example.diff.length>0;
    return `<article class="fex-case fex-compact-case" data-case-category="${esc(example.category)}" data-case-task="${esc(example.anonymous_task||'')}" data-replicate="${example.replicate}" data-before-round="${example.before_round}" data-after-round="${example.after_round}"><header><div><h4>${example.category==='regression'?'公开测试仍过，完整强测却回退':example.category==='semantic_repair'?'具体反例澄清语义，代码得到修复':'诊断定位错误，代码得到修复'}</h4><p>${esc(modelLabel(evidence,example.model))} · ${esc(armLabel(evidence,example.arm))} · ${esc(example.anonymous_task||'匿名题目')} · 版本 ${number(example.before_round+1)} → ${number(example.after_round+1)}</p></div></header><div class="fex-compact-trace"><div class="fex-code-block fex-feedback" data-feedback-excerpt="${excerpt.kind}" data-feedback-source="actual_feedback"><h5>${excerpt.label}</h5><pre><code>${esc(excerpt.text)}</code></pre></div><div class="fex-code-block fex-diff" data-case-code="${hasDiff?'full-diff':'unchanged-code'}"><h5>${hasDiff?'代码的实际变化 · 完整 diff':'代码未改变 · 实际实现'}</h5><pre><code>${esc(hasDiff?example.diff:example.before_code)}</code></pre></div></div><dl class="fex-compact-outcomes"><div><dt>公开测试 · 前 → 后</dt><dd>${esc(publicOutcome(example.before_public))} → ${esc(publicOutcome(example.after_public))}</dd></div><div><dt>完整强测 · 前 → 后</dt><dd>${strongOutcome(example.before_strong_pass)} → ${strongOutcome(example.after_strong_pass)}</dd></div></dl></article>`;
  }).join('')}</div><p class="fex-compact-case-note">案例解释机制，不代表平均效果。完整反馈、前后代码、其余案例及原七张补充图均保留在图册与发布快照；总体效果以上方同题配对统计为准。</p></section>`;
}

/** Compact defense panels; the original complete renderer below remains available to the atlas. */
export function renderFeedbackCompact(evidence, figures, legacyEvidence, options = {}) {
  if(!publishable(evidence,figures))return '';
  const requestedPrefix=typeof options==='string'?options:options.prefix??figures.prefix??'assets/research-extension/';
  if(typeof requestedPrefix!=='string'||/^[a-z][a-z\d+.-]*:/i.test(requestedPrefix)||/[<>"'\u0000-\u001f]/.test(requestedPrefix))return '';
  const prefix=requestedPrefix.endsWith('/')?requestedPrefix:requestedPrefix+'/';
  const c=evidence.coverage;
  return `<div class="feedback-extension feedback-compact"><section class="fex-compact-result-section" aria-label="六种反馈的两模型完整测试结果"><header class="fex-compact-heading"><h3>代码反馈：收益依赖模型，反例不必越多越好</h3><p>${number(c.planned_tasks)} 题 × ${number(evidence.models.length)} 模型 × ${number(evidence.repeats_per_task)} 份共享初稿 ×（1＋${number(evidence.arms.length)}组×${number(evidence.rounds-1)}次修订）＝ ${number(evidence.saved_physical_responses)} 份物理响应；每模型每组 ${number(c.planned_tasks*evidence.repeats_per_task)} 份程序。</p></header>${compactEndpointFigure(evidence,figures,prefix)}<div class="fex-compact-contrasts">${compactModelContrasts(evidence)}</div><p class="fex-compact-method-note">完整通过＝公开与保留测试同时通过；95%区间按 ${number(c.planned_tasks)} 道题聚类，属于未做多重校正的探索比较。额外保留输入全题库合计 ${number(c.holdout_cases)} 条，不进入模型反馈。</p></section>${compactCases(evidence)}</div>`;
}

function codeBlock(label, code, modifier = '') {
  return `<div class="fex-code-block ${modifier}"><h6>${esc(label)}</h6><pre><code>${esc(code)}</code></pre></div>`;
}

function renderExamples(evidence) {
  const examples = Array.isArray(evidence.examples) ? evidence.examples.filter(row => typeof row.before_code === 'string' && typeof row.after_code === 'string') : [];
  const unavailable=Array.isArray(evidence.missing_example_categories)?evidence.missing_example_categories:[];
  if (!examples.length && !unavailable.length) return '';
  const missingNote=unavailable.length?`<p class="fex-source">本批次按既定规则未找到可展示的以下案例：${unavailable.map(key=>esc(CATEGORY[key]||key)).join('、')}。</p>`:'';
  return `<section class="fex-section fex-cases" aria-label="真实代码修改过程"><div class="fex-section-heading"><span class="fex-index">04</span><div><h4>从实际代码和反馈，追到结果</h4><p>按固定顺序选取具有已知前后评测的相邻版本，展示修复、回退与公开／保留差异。代码和反馈来自实际保存记录，整体效果见上方配对统计。</p></div></div>${missingNote}${examples.map((example, index) => `<article class="fex-case"><header><span class="fex-case-number">案例 ${index + 1}</span><div><h5>${esc(CATEGORY[example.category] || '已保存的代码修改')}</h5><p>${esc(modelLabel(evidence, example.model))} · ${esc(armLabel(evidence, example.arm))} · ${esc(example.anonymous_task || example.task_id || '匿名题目')} · 第 ${finite(example.replicate) ? example.replicate + 1 : '—'} 份初稿 · 版本 ${number(example.before_round + 1)} → ${number(example.after_round + 1)}</p></div></header><div class="fex-trace-grid">${codeBlock('01 · 前一版模型代码', example.before_code)}${codeBlock('02 · 这一步实际收到的反馈', typeof example.actual_feedback === 'string' ? example.actual_feedback : '这条轨迹没有执行反馈文本。', 'fex-feedback')}${codeBlock('03 · 后一版模型代码', example.after_code)}${typeof example.diff === 'string' && example.diff ? codeBlock('04 · 代码的实际变化', example.diff, 'fex-diff') : ''}</div><dl class="fex-case-outcomes"><div><dt>本次修改前 · 公开</dt><dd>${esc(publicOutcome(example.before_public))}</dd></div><div><dt>本次修改后 · 公开</dt><dd>${esc(publicOutcome(example.after_public))}</dd></div><div><dt>本次修改前 / 后 · 强测</dt><dd>${strongOutcome(example.before_strong_pass)} / ${strongOutcome(example.after_strong_pass)}</dd></div><div><dt>整条链初稿 / 终稿 · 强测</dt><dd>${strongOutcome(example.initial_strong_pass)} / ${strongOutcome(example.final_strong_pass)}</dd></div></dl>${typeof example.before_strong_pass==='boolean'&&typeof example.after_strong_pass==='boolean'?'':'<p class="fex-source">该步的中间版本尚未完成强测，按未测保留。</p>'}</article>`).join('')}</section>`;
}

function renderLegacy(legacy, evidence, prefix) {
  if (legacy?.synthetic === true || legacy?.checks?.synthetic === true || legacy?.checks?.complete !== true || !Array.isArray(legacy.summary) || !legacy.summary.length) return '';
  const checks = legacy.checks;
  const publicChanges = asNumber(checks.public_verdict_changes);
  const reverseChanges = asNumber(checks.strong_pass_old_mini_fail);
  const legacyFigures = Array.isArray(legacy.figures) ? legacy.figures : legacy.figures?.synthetic !== true ? legacy.figures?.figures || [] : [];
  const legacyPlots = legacyFigures.filter(row => /^[\w.-]+\.svg$/i.test(row.file || '')).map(row => `<figure class="fex-figure"><figcaption><span class="fex-figure-letter">旧</span><div><h4>${esc(row.title || '旧 Mini 与完整强测试复核')}</h4><p>同一批历史终稿的回顾性复核，单独报告原 Mini 判定与完整强测试判定。</p></div></figcaption><div class="fex-plot" tabindex="0" role="region" aria-label="历史批次强复测图，窄屏可水平滚动"><img src="${esc(prefix + 'legacy/' + row.file)}" alt="${esc(row.title || '历史批次强复测图')}" width="1200" loading="lazy" decoding="async"></div></figure>`).join('');
  const reverseNote = finite(reverseChanges) ? `旧 Mini 未通过、完整强测重执行通过的历史程序共 ${number(reverseChanges)} 份。${reverseChanges > 0 ? '本次记录中的反向变化来自旧超时未复现，代码并未改变，不能解释为新增测试改善了代码质量。' : ''}` : '';
  return `<section class="fex-section fex-legacy" aria-label="旧批次代码的独立强复测"><div class="fex-section-heading"><span class="fex-index">05</span><div><p class="fex-kicker">历史批次 · 单独复核</p><h4>旧 Mini 测试通过的代码，经得住更强测试吗？</h4><p>对同一批已保存的旧代码重新执行完整强测试，未重新生成代码，未把新增保留测试反馈给旧模型。这是回顾性复核，单独呈现，不并入上方新批次。</p></div></div><p class="fex-method">复核 ${number(asNumber(checks.source_records))} 份历史代码，来自 ${number(asNumber(checks.source_initial_programs))} 份独立初稿；额外模型 API 调用为 ${number(asNumber(checks.model_api_calls))}。${finite(asNumber(checks.full_holdout_inputs)) ? `全题库额外保留输入共 ${number(asNumber(checks.full_holdout_inputs))} 条。` : ''}</p>${legacyPlots}<div class="fex-table-wrap" tabindex="0" role="region" aria-label="历史批次复核结果表，窄屏可水平滚动"><table class="fex-legacy-table"><caption>旧批次：相同终稿在 Mini 与完整强测试中的通过数</caption><thead><tr><th scope="col">模型 / 策略</th><th scope="col">题目数</th><th scope="col">原 Mini 终稿通过</th><th scope="col">完整强测终稿通过</th><th scope="col">Mini 通过、强测失败</th></tr></thead><tbody>${legacy.summary.map(row => `<tr><th scope="row">${esc(modelLabel(evidence, row.model))}<small>${esc(armLabel(evidence, row.arm))}</small></th><td>${number(asNumber(row.tasks))}</td><td>${number(asNumber(row.legacy_final_pass))}</td><td>${number(asNumber(row.strong_final_pass))}</td><td>${number(asNumber(row.old_mini_pass_strong_fail))}</td></tr>`).join('')}</tbody></table></div><p class="fex-source">${reverseNote} ${finite(publicChanges) ? `公开测试判定发生变化的历史程序共 ${number(publicChanges)} 份。${publicChanges > 0 ? '存在公开重执行差异，因此总判定变化不能全部归因于新增测试；运行环境及资源执行差异需一并考虑。' : '公开测试判定在这次复核中保持一致。'}` : '公开重执行变化按独立复核记录报告。'} 旧批次的模型、反馈和重复次数沿用原实验，不与新批次合算。</p></section>`;
}

/**
 * Render a complete real batch as one static, scrollable research section.
 * figures: figure-manifest.json; legacyEvidence: {checks, summary, curves?}.
 * options.prefix (or figures.prefix) changes only the local SVG resource path.
 */
export function renderFeedbackExtension(evidence, figures, legacyEvidence, options = {}) {
  if (!publishable(evidence, figures)) return '';
  const requestedPrefix = typeof options === 'string' ? options : options.prefix ?? figures.prefix ?? 'assets/research-extension/';
  if (typeof requestedPrefix !== 'string' || /^[a-z][a-z\d+.-]*:/i.test(requestedPrefix) || /[<>"'\u0000-\u001f]/.test(requestedPrefix)) return '';
  const prefix = requestedPrefix.endsWith('/') ? requestedPrefix : requestedPrefix + '/';
  const trajectory = renderStrongTrajectory(evidence, figures, prefix);
  const plots = FIGURES.map(([id]) => renderFigure(figures, id, prefix) + (id === 'public-trajectories' ? trajectory : '')).join('');
  return `<section class="feedback-extension" aria-label="代码执行反馈扩展实验">${renderDesign(evidence)}<section class="fex-section" aria-label="完整实验图组"><div class="fex-section-heading"><span class="fex-index">02</span><div><h4>${trajectory ? '六' : '五'}张图，连接错误来源、最终质量与修复代价</h4><p>图中的通过率来自实测代码；置信区间按题目聚类估计。先读强测试，再看公开轨迹和机制。</p></div></div>${plots}</section>${renderResults(evidence)}${renderExamples(evidence)}${renderLegacy(legacyEvidence, evidence, prefix)}<footer class="fex-endnote"><p>结论范围：当前模型、完整题库、反馈协议与执行预算。公开诊断、强保留测试、修复成功和曾经通过分别报告；模型间差异、回退及无稳定改善的结果同样保留。</p></footer></section>`;
}
