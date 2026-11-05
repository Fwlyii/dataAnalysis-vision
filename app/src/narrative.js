(() => {
  "use strict";
  const D = window.LENS_NARRATIVE;
  if (!D) return;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const escape = (x) =>
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
  const number = (x) => Number(x).toLocaleString("en-US");
  const names = {
    qwen: "Qwen2.5 7B",
    qwen3: "Qwen3 8B",
    deepseek: "DeepSeek",
    hy4: "HY4 preview",
  };
  const logos = {
    qwen: "qwen.svg",
    qwen3: "qwen.svg",
    deepseek: "deepseek.svg",
    hy4: "hunyuan.svg",
  };
  const state = { direction: "reasoning", model: "qwen", view: "curve" };
  function hydrateOverview() {
    const params = new URLSearchParams(location.search);
    const direction = params.get("overviewTask");
    if (Object.hasOwn(D.directions, direction)) state.direction = direction;
    const model = params.get("overviewModel");
    if (D.directions[state.direction].models.includes(model))
      state.model = model;
    state.view = params.get("overviewView") === "heatmap" ? "heatmap" : "curve";
  }
  function syncOverview() {
    const params = new URLSearchParams(location.search);
    params.set("overviewTask", state.direction);
    params.set("overviewModel", state.model);
    params.set("overviewView", state.view);
    history.replaceState(
      null,
      "",
      location.pathname + "?" + params + location.hash,
    );
  }
  hydrateOverview();
  const sectionNames = {
    question: "Research Question",
    collection: "Collection Design",
    cleaning: "Data Pipeline",
    landscape: "Data Landscape",
    findings: "Core Findings",
  };
  const directionNames = {
    reasoning: "Reasoning",
    document_qa: "Document QA",
    code_generation: "Code",
  };
  const directionIcons = {
    reasoning: "M4 5h12M4 10h8M4 15h5",
    document_qa: "M4 3h9l3 3v11H4zM13 3v4h4",
    code_generation: "m7 5-4 5 4 5m6-10 4 5-4 5",
  };
  const palette = {
    "#243c52": "#202522",
    "#526779": "#6c706b",
    "#5d6d7c": "#6c706b",
    "#167b7b": "#a34f36",
    "#756193": "#202522",
    "#ac772e": "#a2763c",
    "#af5961": "#a34f36",
    "#e7edf1": "#e5e0d6",
    "#bbc7d0": "#d7d0c4",
    "#aab9c2": "#a5abb2",
    "#a9bcc6": "#c8c5bd",
  };

  const icon = (name) => {
    const paths = {
      target: '<circle cx="10" cy="10" r="6"/><circle cx="10" cy="10" r="2"/>',
      layers: '<path d="m10 3 7 4-7 4-7-4 7-4Zm-7 8 7 4 7-4M3 15l7 4 7-4"/>',
      shield:
        '<path d="M10 2 16 5v5c0 4-2 6-6 8-4-2-6-4-6-8V5l6-3Z"/><path d="m7 10 2 2 4-5"/>',
      branch:
        '<circle cx="5" cy="5" r="2"/><circle cx="15" cy="15" r="2"/><path d="M5 7v3c0 3 10 0 10 3M5 10h10"/>',
      chart: '<path d="M3 17V3M3 17h15M6 13l3-4 3 2 4-6"/>',
    };
    return `<svg viewBox="0 0 20 20" aria-hidden="true">${paths[name] || paths.target}</svg>`;
  };
  const point = (kind, title, text) =>
    `<li><span class="point-icon">${icon(kind)}</span><div><strong>${title}</strong><span>${text}</span></div></li>`;
  window.LENS_ICON = icon;
  window.LENS_MODEL_BUTTONS = (models, current, attribute = "data-model") =>
    `<div class="model-switch" role="group" aria-label="Model">${models.map((k) => `<button ${attribute}="${k}" aria-pressed="${k === current}"><img src="assets/logos/${logos[k]}" alt=""><span>${names[k]}</span></button>`).join("")}</div>`;
  window.LENS_TUNE_SVG = (root) => {
    if (!root) return;
    $$("[style]", root).forEach((el) => {
      let style = el.getAttribute("style");
      Object.entries(palette).forEach(([from, to]) => {
        style = style.replaceAll(from, to).replaceAll(from.toUpperCase(), to);
      });
      el.setAttribute("style", style);
    });
    $$("svg", root).forEach((svg) => {
      svg.removeAttribute("width");
      svg.removeAttribute("height");
    });
  };

  function collection() {
    return `<div class="collection-layout">
      <ul class="key-points design-points">${point("target", "Shared items", "Same questions and generation settings")}${point("branch", "One intervention", "Expression, position, or feedback")}${point("layers", "Separate metrics", "Task scores are never pooled")}</ul>
      <div class="collection-visual">
        <div class="experiment-flow" aria-label="Controlled experiment flow"><div class="flow-node"><span>01</span><strong>Fixed items</strong></div><i>→</i><div class="flow-node focus"><span>31 ×</span><strong>Prompt strategies</strong></div><i>→</i><div class="flow-node"><span>03</span><strong>Task scores</strong></div></div>
        <div class="task-ledger">
          <div class="task-row"><span>A</span><h3>Reasoning & choice</h3><p>4 models · 3 benchmarks</p><strong>${number(D.counts.reasoning)}</strong></div>
          <div class="task-row"><span>B</span><h3>Document QA</h3><p>2 models · 200 questions</p><strong>${number(D.counts.document_qa)}</strong></div>
          <div class="task-row"><span>C</span><h3>Code generation</h3><p>3 models · 194 tasks · 5 samples</p><strong>${number(D.counts.code_generation)}</strong></div>
        </div>
        <div class="special-studies"><div><span class="mini-icon">${icon("target")}</span><strong>Evidence position</strong><span>2 models × 9 positions · ${number(D.counts.document_positions)}</span></div><div><span class="mini-icon">${icon("branch")}</span><strong>Feedback repair</strong><span>2 models × 4 strategies × 4 rounds · ${number(D.counts.code_repair)}</span></div></div>
        <details class="inline-details"><summary>31 prompts & code adaptation</summary><div><p>Code prompts constrain only the optional explanation before the code; the Python function itself is not length-limited.</p>${D.prompts.map((p) => `<p><b>${escape(p.prompt_id)}</b> — ${escape(p.prompt_text)}</p>`).join("")}</div></details>
      </div>
    </div>`;
  }

  function cleaning() {
    const lines = Object.entries(D.sample)
      .map(
        ([key, v]) =>
          `  <span class="schema-key">"${escape(key)}"</span>: <span class="${v === null ? "schema-null" : typeof v === "string" ? "schema-string" : "schema-number"}">${escape(JSON.stringify(v))}</span>`,
      )
      .join(",\n");
    return `<div class="cleaning-layout">
      <div class="schema-block"><div class="schema-label"><span>ONE ANONYMIZED RESPONSE</span><span>Actual values</span></div><pre class="schema-preview" aria-label="JSON example of an anonymized response">{\n${lines}\n}</pre><details class="inline-details"><summary>Field definitions</summary><div>${Object.entries(
        {
          record_id: "Anonymous response identifier",
          model_id: "Normalized model name",
          benchmark: "Benchmark; separate from the metric",
          prompt_id: "Prompt strategy linked to source text",
          output_tokens: "Actual returned output tokens",
          finish_reason: "Saved stop reason",
          is_truncated: "Whether output ended at a length limit",
          metric_name: "Task-specific scoring rule",
          metric_value: "Original score; exclusions remain null",
          timestamp: "Source timestamp when available",
        },
      )
        .map(([k, v]) => `<p><code>${k}</code> — ${v}</p>`)
        .join("")}</div></details></div>
      <div class="cleaning-proof"><ol class="cleaning-steps"><li><strong>Freeze & join</strong><span>Stable keys. Source files unchanged.</span></li><li><strong>Normalize</strong><span>Consistent types. Repeated measures retained.</span></li><li><strong>Keep missingness distinct</strong><span>Truncation, unresolved extraction, environment exclusion.</span></li><li><strong>Anonymize & derive</strong><span>Anonymous keys and condition summaries.</span></li></ol><dl class="quality-ledger"><div><dt>Unified records</dt><dd>${number(D.total)}</dd></div><div><dt>Environment exclusions</dt><dd>${number(D.environment_excluded)}</dd></div></dl><ul class="key-points cleaning-points">${point("shield", "Missing is not zero", "Excluded failures remain null")}${point("layers", "Shared drafts counted once", "Independent sampling stays separate")}</ul></div>
    </div>`;
  }

  function landscape() {
    return `<div class="landscape-controls"><div class="control-block"><span class="control-label">Task</span><div class="task-switch" role="group" aria-label="Landscape task">${Object.entries(
      directionNames,
    )
      .map(
        ([k, v]) =>
          `<button data-overview-direction="${k}" aria-pressed="${k === state.direction}"><svg viewBox="0 0 20 20"><path d="${directionIcons[k]}"/></svg>${v}</button>`,
      )
      .join(
        "",
      )}</div></div><div class="control-block"><span class="control-label">Model</span>${window.LENS_MODEL_BUTTONS(D.directions[state.direction].models, state.model, "data-overview-model")}</div><div class="segmented" role="group" aria-label="Landscape chart"><button data-overview-view="curve" aria-pressed="${state.view === "curve"}">Trend</button><button data-overview-view="heatmap" aria-pressed="${state.view === "heatmap"}">Score matrix</button></div></div><div class="overview-plot"></div><div class="landscape-foot"><p class="overview-reading"></p><span id="landscape-scope"></span></div>`;
  }

  $("#collection-scene").innerHTML = collection();
  $("#cleaning-scene").innerHTML = cleaning();
  $("#landscape-scene").innerHTML = landscape();

  function paintOverview(updateURL = true) {
    const root = $("#landscape-scene");
    const models = D.directions[state.direction].models;
    if (!models.includes(state.model)) state.model = models[0];
    const control = $(".control-block:nth-child(2)", root);
    const old = $(".model-switch", control);
    if (old)
      old.outerHTML = window.LENS_MODEL_BUTTONS(
        models,
        state.model,
        "data-overview-model",
      );
    $$("[data-overview-model]", root).forEach(
      (b) =>
        (b.onclick = () => {
          state.model = b.dataset.overviewModel;
          paintOverview();
        }),
    );
    $$("[data-overview-direction]", root).forEach((b) =>
      b.setAttribute(
        "aria-pressed",
        String(b.dataset.overviewDirection === state.direction),
      ),
    );
    $$("[data-overview-view]", root).forEach((b) =>
      b.setAttribute(
        "aria-pressed",
        String(b.dataset.overviewView === state.view),
      ),
    );
    $(".overview-plot", root).innerHTML = window.LENS_CHARTS.landscape(
      D,
      state,
    );
    $$("[data-profile-prompt]", root).forEach((cell) => {
      const select = () => {
        const row = D.profiles_by_direction[state.direction].find(
          (r) =>
            r.model === state.model &&
            r.task === cell.dataset.profileTask &&
            r.prompt === cell.dataset.profilePrompt,
        );
        $(".overview-reading", root).textContent =
          `${row.prompt} · ${row.task} · ${row.score_pct.toFixed(1)}% · ${row.mean_tokens.toFixed(1)} output tokens · ${row.questions} items`;
        $$("[data-profile-prompt]", root).forEach((c) =>
          c.removeAttribute("aria-pressed"),
        );
        cell.setAttribute("aria-pressed", "true");
      };
      cell.addEventListener("click", select);
      cell.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          select();
        }
      });
    });
    $(".overview-reading", root).setAttribute("aria-live", "polite");
    const positives = D.fits.filter(
      (f) =>
        f.direction === state.direction &&
        f.model === state.model &&
        f.slope > 0,
    ).length;
    const total = D.fits.filter(
      (f) => f.direction === state.direction && f.model === state.model,
    ).length;
    $(".overview-reading", root).textContent =
      state.view === "heatmap"
        ? "Every prompt. Three task-specific views. Select a cell for exact values."
        : state.direction === "reasoning"
          ? `${positives} of ${total} model–benchmark trends are positive; the exceptions matter too.`
          : state.direction === "document_qa"
            ? "The same questions move from beginning to middle to end."
            : "Independent generation here; feedback repair comes later.";
    $("#landscape-scope").textContent =
      state.direction === "reasoning"
        ? "200 items / condition"
        : state.direction === "document_qa"
          ? "20 documents · 200 questions"
          : "193 scored tasks · 5 samples";
    if (updateURL) syncOverview();
  }
  $$("[data-overview-direction]").forEach(
    (b) =>
      (b.onclick = () => {
        state.direction = b.dataset.overviewDirection;
        paintOverview();
      }),
  );
  $$("[data-overview-view]").forEach(
    (b) =>
      (b.onclick = () => {
        state.view = b.dataset.overviewView;
        paintOverview();
      }),
  );
  paintOverview(false);

  const order = Object.keys(sectionNames);
  window.LENS_GO_TO = (section, updateURL = true) => {
    if (!sectionNames[section] && section !== "gateway") section = "gateway";
    document.body.dataset.section = section;
    $$(".deck-panel").forEach((panel) => {
      const active = panel.id === section;
      panel.hidden = !active;
      panel.classList.toggle("is-active", active);
    });
    $$("button[data-section]").forEach((button) => {
      if (button.dataset.section === section)
        button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    $("#section-counter").textContent =
      section === "gateway" ? "NAVIGATION SPACE" : String(order.indexOf(section) + 1).padStart(2, "0") + " / 05";
    document.title = section === "gateway" ? "LENS · 知微之门" : `${sectionNames[section]} — LENS`;
    if (updateURL && location.hash !== "#" + section)
      history.pushState(null, "", "#" + section);
    const active = $("#" + section);
    if (active) active.scrollTop = 0;
    if (section === "landscape" && updateURL) syncOverview();
  };
  $$("button[data-section]").forEach((button) =>
    button.addEventListener("click", () =>
      window.LENS_GO_TO(button.dataset.section),
    ),
  );
  window.LENS_SCROLL_TO = (id) => {
    if (id === "actual-example") {
      $("#actual-example").open = true;
      $("#actual-example").scrollIntoView({ block: "start" });
      return;
    }
    window.LENS_GO_TO(
      ["discoveries", "research"].includes(id) ? "findings" : id,
    );
  };
  window.addEventListener("hashchange", () => {
    const h = location.hash.slice(1);
    if (sectionNames[h] || h === "gateway" || !h) window.LENS_GO_TO(h || "gateway", false);
  });
  window.addEventListener("popstate", () => {
    hydrateOverview();
    paintOverview(false);
    const h = location.hash.slice(1);
    if (sectionNames[h] || h === "gateway" || !h) window.LENS_GO_TO(h || "gateway", false);
  });
  document.addEventListener("keydown", (event) => {
    if (
      document.body.dataset.section === "gateway" ||
      document.documentElement.classList.contains("intro-active") ||
      event.altKey ||
      event.ctrlKey ||
      event.metaKey ||
      event.target.closest(
        '.plot-scroll, .answer-content, .schema-preview, [role="region"], [contenteditable="true"]',
      )
    )
      return;
    if (
      ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)
    )
      return;
    if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
    event.preventDefault();
    const i = order.indexOf(document.body.dataset.section);
    window.LENS_GO_TO(
      order[
        Math.max(0, Math.min(4, i + (event.key === "ArrowRight" ? 1 : -1)))
      ],
    );
  });
  $("#present").onclick = async () => {
    try {
      if (!document.fullscreenElement)
        await document.documentElement.requestFullscreen();
      else await document.exitFullscreen();
    } catch {
      $("#notice").textContent =
        "Fullscreen is unavailable. Use the browser menu.";
      $("#notice").hidden = false;
      setTimeout(() => ($("#notice").hidden = true), 2400);
    }
  };
  const initial = location.hash.slice(1);
  window.LENS_GO_TO(sectionNames[initial] ? initial : "gateway", false);
})();
