(() => {
  "use strict";
  const D = window.LENS_STORY,
    $ = (s) => document.querySelector(s);
  if (!D) {
    $("#research").innerHTML =
      '<p class="boot-message">Research data could not be loaded.</p>';
    return;
  }
  const esc = (x) =>
    String(x ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const names = {
    deepseek: "DeepSeek",
    hy4: "HY4 preview",
    qwen: "Qwen2.5 7B",
    qwen3: "Qwen3 8B",
  };
  const tasks = { gsm8k: "GSM8K", math500: "MATH500", mmlu: "MMLU-Pro" };
  const order = ["concise", "language", "position", "repair", "limits"];
  const titles = {
    concise: "Concise",
    language: "Chinese math",
    position: "Evidence position",
    repair: "Feedback repair",
    limits: "Length rebound",
  };
  const courseKinds = {
    concise: "LOW-DIMENSION 01",
    language: "LOW-DIMENSION 02",
    position: "MULTIDIMENSIONAL 01",
    repair: "MULTIDIMENSIONAL 02",
    limits: "ANOMALY",
  };
  const headings = {
    concise: "Concise preserves the reasoning gain.",
    language: "Chinese makes complex math finish.",
    position: "Model advantage moves with evidence.",
    repair: "Concrete failures repair code better.",
    limits: "Tighter limits can produce longer outputs.",
  };
  const finding = {
    concise:
      "Across 17 groups, <strong>all used fewer tokens</strong>; 15 did not lose score. Qwen2.5 / GSM8K saved <strong>21.5%</strong>.",
    language:
      "Qwen3 / MATH500: <strong>58.0 → 69.5%</strong>, with <strong>19.5% fewer tokens</strong>.",
    position:
      "Qwen3’s lead narrowed from <strong>16.5 pp</strong> to <strong>2.5 pp</strong>.",
    repair:
      "Qwen3 / Version 5: counterexamples <strong>141/164</strong>; self-review <strong>129/164</strong>.",
    limits:
      "From 10 words to 1, output increased in <strong>9 of 12 groups</strong>.",
  };
  const s = {
    chapter: "concise",
    view: "baseline",
    task: "math500",
    model: "deepseek",
    family: "WordLimit",
    repairModel: "qwen3",
    round: 4,
    position: 0,
    ci: true,
  };
  const positions = [1, 3, 5, 8, 10, 13, 15, 18, 20];
  const armLabels = {
    resample: "Independent resampling",
    self_review: "Self-review",
    pass_fail: "Pass / fail",
    counterexample: "Counterexample",
  };
  let playing = null,
    noticeTimer = null,
    lastRoute = "";
  function hydrate() {
    const p = new URLSearchParams(location.search),
      rawRound = Number(p.get("round") ?? 4);
    Object.assign(s, {
      view: p.get("view") === "cross" ? "cross" : "baseline",
      task: Object.hasOwn(tasks, p.get("task")) ? p.get("task") : "math500",
      model: Object.hasOwn(names, p.get("model")) ? p.get("model") : "deepseek",
      family: ["WordLimit", "CharLimit", "TokenLimit"].includes(p.get("family"))
        ? p.get("family")
        : "WordLimit",
      repairModel: p.get("repairModel") === "qwen" ? "qwen" : "qwen3",
      round: Number.isFinite(rawRound)
        ? Math.max(0, Math.min(4, Math.trunc(rawRound)))
        : 4,
      position: Math.max(0, positions.indexOf(Number(p.get("position") || 1))),
      ci: p.get("ci") !== "0",
    });
  }
  const icon = (name) => {
    const paths = {
      download: "M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5",
      down: "m6 9 6 6 6-6",
      left: "m14 6-6 6 6 6",
      right: "m10 6 6 6-6 6",
      play: "m8 5 11 7-11 7z",
      pause: "M8 5v14M16 5v14",
    };
    return `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]}"/></svg>`;
  };
  const choices = (id, values, value) =>
    `<div class="choice-switch" role="group" aria-label="${id}">${Object.entries(
      values,
    )
      .map(
        ([k, v]) =>
          `<button data-${id}="${k}" aria-pressed="${k === value}">${v}</button>`,
      )
      .join("")}</div>`;
  const control = (label, content) =>
    `<div class="control-block"><span class="control-label">${label}</span>${content}</div>`;
  const figureTitles = {
    concise: "Paired output, same item set",
    language: "Default → Chinese",
    position: "Model × evidence position",
    repair: "Feedback × code version",
    limits: "Requested limit × actual output",
  };
  function controls() {
    switch (s.chapter) {
      case "concise":
        return control(
          "Scope",
          choices(
            "view",
            { baseline: "Paired example", cross: "17 replications" },
            s.view,
          ),
        );
      case "language":
        return control("Benchmark", choices("task", tasks, s.task));
      case "limits":
        return (
          control(
            "Model",
            window.LENS_MODEL_BUTTONS(
              Object.keys(names),
              s.model,
              "data-model",
            ),
          ) +
          control("Benchmark", choices("task", tasks, s.task)) +
          control(
            "Limit",
            choices(
              "family",
              {
                WordLimit: "Words",
                CharLimit: "Letters",
                TokenLimit: "Tokens",
              },
              s.family,
            ),
          )
        );
      case "position":
        return '<p class="control-note">NoCoT · 20 documents · 200 items / point</p>';
      case "repair":
        return control(
          "Model",
          window.LENS_MODEL_BUTTONS(
            ["qwen3", "qwen"],
            s.repairModel,
            "data-repair-model",
          ),
        );
    }
  }
  function figureKey() {
    return {
      concise: s.view === "cross" ? "concise-cross" : "concise-baseline",
      language: "language-" + s.task,
      limits: `limit-${s.model}-${s.task}-${s.family}`,
      position: "position",
      repair: `repair-${s.repairModel}-${s.round}`,
    }[s.chapter];
  }
  function caption() {
    return {
      concise:
        s.view === "cross"
          ? [
              "BeConcise vs DefaultCoT · 17 task groups",
              "Task-specific metrics; no pooled accuracy.",
            ]
          : [
              "Qwen2.5 7B · GSM8K · 200 paired items",
              "Same step-by-step requirement. Means only; no stored item-level interval.",
            ],
      language: [
        `${tasks[s.task]} · 4 models · 200 items / model`,
        s.task === "math500"
          ? "Four models used fewer tokens; three improved. Gold rings mark remaining truncation."
          : "Fewer tokens do not imply a score gain on every task.",
      ],
      limits: [
        `${names[s.model]} · ${tasks[s.task]} · 200 items / level`,
        `Prompted ${s.family === "WordLimit" ? "word" : s.family === "CharLimit" ? "letter" : "token"} limits, not API hard caps.`,
      ],
      position: [
        "Paired questions · 2 models × 9 positions × 200 items",
        "Nine measured positions. Shaded bands show 95% intervals.",
      ],
      repair: [
        "HumanEval+ Mini · 164 tasks · draft + 4 rounds",
        "Current-version pass rate; counterexample band shows 95% interval.",
      ],
    }[s.chapter];
  }
  function scrubber() {
    if (s.chapter === "position")
      return `<div class="point-control"><label for="position">Evidence position</label><input id="position" type="range" min="0" max="8" step="1" value="${s.position}" aria-valuetext="Document ${positions[s.position]}"><output for="position" id="position-label">Doc ${positions[s.position]}</output><label class="interval-control"><input id="ci" type="checkbox" ${s.ci ? "checked" : ""}>95% interval</label></div><div id="point-readout" class="point-readout" aria-live="polite"></div>`;
    if (s.chapter === "repair")
      return `<div class="point-control"><button id="play" class="play-button" aria-label="Play five code versions">${icon("play")}<span>Play versions</span></button><label for="round">Version</label><input id="round" type="range" min="0" max="4" step="1" value="${s.round}" aria-valuetext="${s.round === 0 ? "Initial draft" : `After revision ${s.round}`}"><output id="round-label" for="round">${s.round === 0 ? "Draft" : "Version " + (s.round + 1)}</output></div><div id="point-readout" class="point-readout" aria-live="polite"></div>`;
    return "";
  }
  function excerpt(r, max = 600) {
    if (r.response.length <= max) return r.response;
    return (
      r.response.slice(0, max - 180) +
      "\n[… middle omitted; full response below …]\n" +
      r.response.slice(-180)
    );
  }
  function answer(r, label, prompt, max = 650, chosen = false) {
    return `<article class="answer ${chosen ? "full" : ""}"><header><strong>${esc(label)}</strong><span class="answer-meta">${r.tokens} tokens · ${r.finish === "length" ? "truncated" : r.score == null ? "unscored" : r.score ? "correct" : "incorrect"}</span></header><p class="prompt-text">${esc(prompt)}</p><div class="answer-content" tabindex="0" role="region" aria-label="Model response">${esc(excerpt(r, max)).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")}</div>${r.response.length > max ? `<details><summary>Full original response</summary><div class="answer-content" tabindex="0" role="region" aria-label="Full model response">${esc(r.response)}</div></details>` : ""}</article>`;
  }
  function pairedCase(
    ids,
    question,
    labels,
    prompts,
    explain,
    max = 650,
    context = "",
  ) {
    const [a, b] = ids.map((id) =>
      D.examples.reasoning.find((r) => r.id === id),
    );
    return `<p class="question">${esc(question)}<small>${context || `${names[a.model]} · ${tasks[a.task]} · Same item`}</small></p><div class="prompt-comparison">${answer(a, labels[0], prompts[0], max)}${answer(b, labels[1], prompts[1], max, true)}</div><p class="example-explanation">${explain}</p>`;
  }
  function example() {
    switch (s.chapter) {
      case "concise":
        return pairedCase(
          ["Z006587", "Z006787"],
          "A shop sells 15 kg of meat per hour and operates 10 hours per day. How many days does 750 kg take?",
          ["DefaultCoT · 163 tokens", "BeConcise · 40 tokens"],
          [
            "Think step by step before answering.",
            "Think step by step before answering, but be concise.",
          ],
          "Both answer 5 days. The concise response keeps both calculations and removes the packaging.",
        );
      case "language":
        return pairedCase(
          ["Z049851", "Z054851"],
          "Seven bags hold equal numbers of coins. After finding 53 more, the coins can be divided equally into eight bags, with more than 200 in total. What is the smallest original number?",
          ["DefaultCoT · 800 tokens", "ChineseCoT · 552 tokens"],
          ["Think step by step before answering.", "Respond in Chinese."],
          "The default response truncates at 800 tokens. The Chinese response completes the congruence and answers 203. Original responses are preserved.",
          430,
          "Fixed example · Qwen3 / MATH500",
        );
      case "limits":
        return pairedCase(
          ["Z015804", "Z015404"],
          "How many positive integer divisors does 196 have?",
          ["100-letter limit · 25 tokens", "10-letter limit · 801 tokens"],
          [
            "Only use 100 letters for your answer.",
            "Only use 10 letters for your answer.",
          ],
          "The model computes 9, then keeps negotiating how to write “NINE” in ten letters until truncation.",
          820,
          "Fixed example · DeepSeek / MATH500 / CharLimit",
        );
      case "position": {
        const a = D.examples.positions
          .filter((r) => r.question_alias === "C007")
          .sort((x, y) => x.position - y.position);
        return `<p class="question">Who won the most Gold Glove Awards at shortstop?<small>Qwen2.5 · NoCoT · Same question and documents; only evidence position changes</small></p><div class="position-answers">${a.map((r) => `<article class="position-answer ${r.final_contains ? "" : "wrong"}"><span>Evidence in document ${r.position}</span><blockquote>${esc(r.response)}</blockquote><small>${r.final_contains ? "Ozzie Smith found" : "Reference answer missed"}</small></article>`).join("")}</div><p class="example-explanation">Positions 1 and 20 produce Ozzie Smith; position 10 produces Omar Vizquel. For Qwen2.5, 78/200 questions changed hit status across positions.</p>`;
      }
      case "repair": {
        const r = D.examples.repair[0];
        return `<p class="question">Implement choose_num(x, y): return the largest even number in [x, y], or −1 for an invalid range.<small>Fixed example · Qwen3 / HumanEval 102 · Counterexample, revision 2</small></p><div class="feedback-strip"><strong>Actual failure</strong><code>Input (13, 12)</code><span>Expected −1; received 12</span></div><div class="prompt-comparison"><article class="answer"><header><strong>Before</strong><span class="answer-meta">base and plus failed</span></header><pre class="answer-content code" tabindex="0" aria-label="Code before revision">${esc(r.before_code)}</pre></article><article class="answer full"><header><strong>After</strong><span class="answer-meta">base and plus passed</span></header><pre class="answer-content code" tabindex="0" aria-label="Code after revision">${esc(r.after_code)}</pre></article></div><details class="inline-details"><summary>Full feedback prompt</summary><pre class="answer-content code">${esc(r.feedback)}</pre></details><p class="example-explanation">The draft swaps the boundaries. The counterexample exposes that assumption; revision 2 returns −1 directly when <code>x &gt; y</code>.</p>`;
      }
    }
  }
  function currentRows() {
    switch (s.chapter) {
      case "concise":
        return s.view === "cross"
          ? D.concise.map((r) => ({
              Model: names[r.model] || r.model,
              Task: r.task,
              Token_saving_pct: r.saving,
              Score_delta_pp: r.delta,
            }))
          : D.baseline.map((r) => ({
              Prompt: r.prompt,
              Score_pct: r.score_pct,
              Mean_tokens: r.mean_tokens,
            }));
      case "language":
        return D.chinese
          .filter((r) => r.task === s.task)
          .map((r) => ({
            Model: names[r.model],
            Default_score: r.default_score_pct,
            Chinese_score: r.chinese_score_pct,
            Token_saving_pct: r.token_saving_pct,
            Default_truncation_pct: r.default_truncation_pct,
            Chinese_truncation_pct: r.chinese_truncation_pct,
          }));
      case "limits":
        return D.limits[`${s.model}-${s.task}-${s.family}`].map((r) => ({
          Prompt: r.prompt,
          Mean_tokens: r.mean_tokens,
          Score_pct: r.score_pct,
          Truncated_pct: r.truncated_pct,
        }));
      case "position":
        return D.positions.map((r) => ({
          Model: r.model.split("/")[1],
          Evidence_position: r.position,
          Hits: r.successes,
          Questions: r.questions,
          Hit_rate_pct: 100 * r.rate,
          CI_low_pct: 100 * r.ci_low,
          CI_high_pct: 100 * r.ci_high,
        }));
      case "repair":
        return D.repair[s.repairModel]
          .filter((r) => r.round <= s.round)
          .map((r) => ({
            Feedback: armLabels[r.arm],
            Revision: r.round,
            Version: r.round + 1,
            Passes: r.success,
            Tasks: r.tasks,
            Current_pass_rate_pct: 100 * r.rate,
            Ever_success_pct: 100 * r.ever_success_rate,
          }));
    }
  }
  const fmt = (x) => (typeof x === "number" ? Number(x.toFixed(2)) : x);
  function table() {
    const rows = currentRows();
    return `<div class="data-scroll"><table><thead><tr>${Object.keys(rows[0])
      .map((k) => `<th scope="col">${esc(k)}</th>`)
      .join("")}</tr></thead><tbody>${rows
      .map(
        (r) =>
          `<tr>${Object.values(r)
            .map((v) => `<td>${esc(fmt(v))}</td>`)
            .join("")}</tr>`,
      )
      .join("")}</tbody></table></div>`;
  }
  function methods() {
    const text = {
      concise:
        "Qwen2.5 / GSM8K; prompt strategy → score. Across 200 paired items, DefaultCoT improves on NoCoT by 69.5 pp, paired interval [63.0, 76.0]. Cross-task replication uses each task’s original metric. 15/17 is a point-estimate direction count, not an equivalence test.",
      language:
        "Qwen3 / MATH500; response template → score. ChineseCoT uses “Respond in Chinese.” and also changes the step-by-step wording. The main finding is bounded to MATH500: on GSM8K, all four models lose 0.5–4.5 pp. Output language is not internal reasoning language.",
      position:
        "Model × evidence position → final-answer inclusion. Same 200 questions, 20 documents, NoCoT, paired positions. Qwen3 position 1 vs 10: +9.5 pp, paired interval [4.5, 15.0]. The model gain differs by 14.0 pp between first and last, interval [5.5, 23.0]. Bands are 95% intervals. Model collection dates differ; prompts and generation settings are identical.",
      repair:
        "Feedback strategy × revision → current full-test pass rate. 164 tasks, two models, a shared initial draft, up to four rounds. Independent resampling has no history; the other strategies retain it. Counterexamples use base diagnostics only. Final Qwen3 counterexample vs self-review: +7.32 pp, paired interval [3.05, 12.20]. The shared draft is counted once.",
      limits:
        "Extreme length limits form the anomaly. Each level is the mean of the same 200 items; discrete prompted levels are not interpolated. Word, letter, and token limits are prompt text, not API hard caps. Returned tokens cannot be compared numerically with word or letter budgets.",
    };
    return `<p>${text[s.chapter]}</p><p>Source: frozen experiment-specific collections and topic statistics. <a href="data/course-assignment.pdf" target="_blank" rel="noopener">Course brief</a> · <a href="explore.html?mode=explore#case-1">Full chart library</a>.</p>`;
  }
  function render() {
    if (s.chapter === "language") {
      if (s.task === "math500") {
        headings.language = "Chinese makes complex math finish.";
        finding.language =
          "Qwen3 / MATH500: <strong>58.0 → 69.5%</strong>, with <strong>19.5% fewer tokens</strong>.";
      } else if (s.task === "gsm8k") {
        headings.language = "The gain does not transfer to GSM8K.";
        finding.language =
          "All four models save tokens, but lose <strong>0.5–4.5 pp</strong>.";
      } else {
        headings.language = "In multiple choice, Chinese preserves scores.";
        finding.language = `Qwen3 / MMLU-Pro: <strong>${D.chinese.find((r) => r.model === "qwen3" && r.task === "mmlu").default_score_pct.toFixed(1)} → ${D.chinese.find((r) => r.model === "qwen3" && r.task === "mmlu").chinese_score_pct.toFixed(1)}%</strong>.`;
      }
    }
    if (s.chapter === "repair") {
      const final = D.repair[s.repairModel].filter((r) => r.round === 4),
        a = final.find((r) => r.arm === "counterexample"),
        b = final.find((r) => r.arm === "self_review");
      finding.repair = `${names[s.repairModel]} / Version 5: counterexamples <strong>${a.success}/164</strong>; self-review <strong>${b.success}/164</strong>.`;
    }
    if (s.chapter === "limits") {
      const cfg = {
          WordLimit: {
            loose: "WordLimit(10)",
            tight: "WordLimit(1)",
            label: "10 words → 1",
          },
          CharLimit: {
            loose: "CharLimit(100)",
            tight: "CharLimit(10)",
            label: "100 letters → 10",
          },
          TokenLimit: {
            loose: "TokenLimit(100)",
            tight: "TokenLimit(10)",
            label: "100 tokens → 10",
          },
        }[s.family],
        groups = Object.entries(D.limits).filter(([key]) =>
          key.endsWith(`-${s.family}`),
        ),
        increased = groups.filter(
          ([, rows]) =>
            rows.find((r) => r.prompt === cfg.tight).mean_tokens >
            rows.find((r) => r.prompt === cfg.loose).mean_tokens,
        ).length;
      finding.limits = `${cfg.label}: output increased in <strong>${increased} of ${groups.length} groups</strong>.`;
      headings.limits =
        s.family === "TokenLimit"
          ? "The rebound disappears with token limits."
          : "Tighter limits can produce longer outputs.";
    }
    const active = document.activeElement,
      focusId = $("#research").contains(active) ? active.id : null,
      focusView = active?.dataset?.view;
    stop();
    const cap = caption();
    document.title = `${titles[s.chapter]} — LENS`;
    document.querySelectorAll("[data-chapter]").forEach((a) => {
      if (a.dataset.chapter === s.chapter)
        a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    $("#research").innerHTML =
      `<section class="finding-stage" aria-labelledby="finding-title"><header class="finding-intro"><div><span class="finding-kicker">${courseKinds[s.chapter]}</span><h3 id="finding-title">${headings[s.chapter]}</h3></div><p class="evidence-line">${finding[s.chapter]}</p></header><section class="figure-sheet" aria-label="${titles[s.chapter]} measured results"><div class="figure-toolbar"><div class="figure-heading"><h4>${s.chapter === "concise" && s.view === "cross" ? "17 model–task replications" : figureTitles[s.chapter]}</h4><p>${cap[0]}</p></div><div class="figure-controls">${controls()}</div><details class="export-menu"><summary aria-label="Export figure">Export ${icon("down")}</summary><div class="export-options"><button id="download-svg">SVG figure</button><button id="download-csv">CSV data</button></div></details></div><div class="plot-scroll" role="region" tabindex="0" aria-label="Chart; horizontally scrollable"><div id="plot" class="plot"></div></div>${scrubber()}<div class="figure-caption">${cap[1]}</div></section></section><div class="evidence-drawers"><details id="actual-example" class="evidence-section"><summary><strong>Real example</strong><span>Original prompt and response</span></summary><div class="example-body">${example()}</div></details><section class="support-section" aria-label="Evidence and course mapping"><details id="data-table"><summary>Figure data</summary>${table()}</details><details><summary>Method & scope</summary>${methods()}</details></section></div>`;
    paintPlot();
    bind();
    if (focusId)
      document.getElementById(focusId)?.focus({ preventScroll: true });
    else if (focusView)
      document
        .querySelector(`[data-view="${focusView}"]`)
        ?.focus({ preventScroll: true });
  }
  function paintPlot() {
    const p = $("#plot");
    if (s.chapter === "concise")
      p.innerHTML =
        s.view === "cross"
          ? window.LENS_CHARTS.conciseCross(D)
          : window.LENS_CHARTS.conciseBaseline(D);
    else if (s.chapter === "language")
      p.innerHTML = window.LENS_CHARTS.language(D, s);
    else if (s.chapter === "position")
      p.innerHTML = window.LENS_CHARTS.position(D, s);
    else if (s.chapter === "repair")
      p.innerHTML = window.LENS_CHARTS.repair(D, s);
    else p.innerHTML = window.LENS_CHARTS.limits(D, s);
    p.classList.toggle("show-intervals", s.ci);
    if (s.chapter === "position") positionUpdate();
    if (s.chapter === "repair") repairUpdate();
  }
  function positionUpdate() {
    const p = positions[s.position];
    $("#position-label").textContent = `Doc ${p}`;
    $("#position").setAttribute("aria-valuetext", `Document ${p}`);
    const rs = D.positions.filter((r) => r.position === p),
      q25 = rs.find((r) => r.model.includes("Qwen2.5")),
      q3 = rs.find((r) => r.model.includes("Qwen3"));
    $("#point-readout").textContent =
      `Position ${p}: Qwen3 ${(q3.rate * 100).toFixed(1)}% · Qwen2.5 ${(q25.rate * 100).toFixed(1)}% · Δ ${((q3.rate - q25.rate) * 100).toFixed(1)} pp`;
  }
  function repairUpdate() {
    const r = D.repair[s.repairModel].filter((r) => r.round === s.round),
      a = r.find((r) => r.arm === "counterexample"),
      b = r.find((r) => r.arm === "self_review");
    $("#round-label").textContent =
      s.round === 0 ? "Draft" : `Version ${s.round + 1}`;
    $("#round").value = s.round;
    $("#round").setAttribute(
      "aria-valuetext",
      s.round === 0 ? "Initial draft" : `After revision ${s.round}`,
    );
    const tableScroll = $("#data-table .data-scroll");
    if (tableScroll) tableScroll.outerHTML = table();
    $("#point-readout").textContent =
      `${s.round === 0 ? "Shared draft" : `Revision ${s.round}`}: counterexample ${a.success}/164 · self-review ${b.success}/164`;
  }
  function url() {
    const p = new URLSearchParams();
    p.set("finding", s.chapter);
    if (s.chapter === "concise" && s.view === "cross") p.set("view", s.view);
    if (["language", "limits"].includes(s.chapter)) p.set("task", s.task);
    if (s.chapter === "limits") {
      p.set("model", s.model);
      p.set("family", s.family);
    }
    if (s.chapter === "position") {
      p.set("position", positions[s.position]);
      if (!s.ci) p.set("ci", "0");
    }
    if (s.chapter === "repair") {
      p.set("repairModel", s.repairModel);
      p.set("round", s.round);
    }
    history.replaceState(
      null,
      "",
      location.pathname + "?" + p.toString() + "#findings",
    );
    lastRoute = location.href;
  }
  function download(text, type, name) {
    const blob = new Blob([text], { type }),
      a = document.createElement("a"),
      object = URL.createObjectURL(blob);
    a.href = object;
    a.download = name;
    document.body.append(a);
    a.click();
    a.remove();
    document.querySelectorAll(".export-menu").forEach((d) => (d.open = false));
    setTimeout(() => URL.revokeObjectURL(object), 1000);
    notify("Downloaded " + name);
  }
  function notify(t) {
    clearTimeout(noticeTimer);
    $("#notice").textContent = t;
    $("#notice").hidden = false;
    noticeTimer = setTimeout(() => ($("#notice").hidden = true), 2600);
  }
  function bind() {
    document.querySelectorAll("[data-view]").forEach(
      (b) =>
        (b.onclick = () => {
          s.view = b.dataset.view;
          url();
          render();
        }),
    );
    document.querySelectorAll("[data-task]").forEach(
      (b) =>
        (b.onclick = () => {
          s.task = b.dataset.task;
          url();
          render();
        }),
    );
    document.querySelectorAll("[data-model]").forEach(
      (b) =>
        (b.onclick = () => {
          s.model = b.dataset.model;
          url();
          render();
        }),
    );
    document.querySelectorAll("[data-family]").forEach(
      (b) =>
        (b.onclick = () => {
          s.family = b.dataset.family;
          url();
          render();
        }),
    );
    document.querySelectorAll("[data-repair-model]").forEach(
      (b) =>
        (b.onclick = () => {
          s.repairModel = b.dataset.repairModel;
          url();
          render();
        }),
    );
    if ($("#position"))
      $("#position").oninput = (e) => {
        s.position = Number(e.target.value);
        paintPlot();
        url();
      };
    if ($("#ci"))
      $("#ci").onchange = (e) => {
        s.ci = e.target.checked;
        paintPlot();
        url();
      };
    if ($("#round"))
      $("#round").oninput = (e) => {
        stop();
        s.round = Number(e.target.value);
        paintPlot();
        url();
      };
    if ($("#play"))
      $("#play").onclick = () => {
        if (playing) {
          stop();
          return;
        }
        s.round = 0;
        paintPlot();
        url();
        $("#play").innerHTML = icon("pause") + "<span>Pause</span>";
        $("#play").setAttribute("aria-label", "Pause playback");
        playing = setInterval(
          () => {
            if (s.round === 4) {
              stop();
              return;
            }
            s.round++;
            paintPlot();
            url();
            if (s.round === 4) stop();
          },
          matchMedia("(prefers-reduced-motion: reduce)").matches ? 1800 : 1100,
        );
      };
    $("#download-svg").onclick = () => {
      const svg = $("#plot svg").cloneNode(true),
        box = svg.getAttribute("viewBox").trim().split(/[ ,]+/).map(Number);
      svg.setAttribute("width", box[2] + "pt");
      svg.setAttribute("height", box[3] + "pt");
      download(
        new XMLSerializer().serializeToString(svg),
        "image/svg+xml",
        figureKey() + ".svg",
      );
    };
    $("#download-csv").onclick = () => {
      const a = currentRows(),
        keys = Object.keys(a[0]),
        q = (x) => '"' + String(x).replaceAll('"', '""') + '"';
      download(
        "\ufeff" +
          [
            keys.map(q).join(","),
            ...a.map((r) => keys.map((k) => q(r[k])).join(",")),
          ].join("\r\n"),
        "text/csv;charset=utf-8",
        "lens-" + s.chapter + ".csv",
      );
    };
  }
  function stop() {
    if (playing) clearInterval(playing);
    playing = null;
    if ($("#play")) {
      $("#play").innerHTML = icon("play") + "<span>Play versions</span>";
      $("#play").setAttribute("aria-label", "Play five code versions");
    }
  }
  function route() {
    if (lastRoute === location.href) return;
    lastRoute = location.href;
    hydrate();
    const h = location.hash.slice(1).split("/")[0] || "gateway";
    if (
      [
        "gateway",
        "question",
        "collection",
        "cleaning",
        "landscape",
        "findings",
        "discoveries",
      ].includes(h)
    ) {
      const requested = new URLSearchParams(location.search).get("finding");
      if (order.includes(requested)) s.chapter = requested;
      if (
        !$("#plot") ||
        (["findings", "discoveries"].includes(h) && requested)
      ) {
        if (!order.includes(s.chapter)) s.chapter = "concise";
        render();
      }
      window.LENS_GO_TO(
        ["findings", "discoveries"].includes(h) ? "findings" : h,
        false,
      );
      return;
    }
    let chapter = h;
    if (chapter === "actual-example") chapter = "concise";
    if (chapter === "budget" || chapter === "overview") chapter = "concise";
    if (chapter === "context") chapter = "position";
    if (chapter === "code") chapter = "repair";
    if (!order.includes(chapter)) chapter = "concise";
    s.chapter = chapter;
    render();
    window.LENS_GO_TO("findings", false);
    if (h === "actual-example")
      requestAnimationFrame(() => ($("#actual-example").open = true));
  }
  document.querySelectorAll("[data-chapter]").forEach(
    (button) =>
      (button.onclick = () => {
        s.chapter = button.dataset.chapter;
        url();
        render();
        window.LENS_GO_TO("findings", false);
      }),
  );
  window.addEventListener("hashchange", route);
  window.addEventListener("popstate", route);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stop();
  });
  route();
})();
