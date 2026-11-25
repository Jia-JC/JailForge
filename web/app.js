/* JailForge desktop UI logic — no framework, no CDN. */
(() => {
  "use strict";

  const TOKEN = document.querySelector('meta[name="jf-token"]')?.content || "";
  const VERSION = document.querySelector('meta[name="jf-version"]')?.content || "0.1.0";
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const state = {
    meta: null,
    goals: [],
    runs: [],
    model: "mock",
    theme: localStorage.getItem("jf-theme") || "dark",
  };

  const PAGE_META = {
    dashboard: ["概览", "一条可复现的 LLM 越狱评测流水线"],
    single: ["单条测试", "选一个目标、一种攻击和一层防御，立即看结果"],
    batch: ["批量评测", "攻击方法 × 防御配置的 ASR 矩阵"],
    evolve: ["进化攻击", "让遗传算法在防御感知的适应度上搜索"],
    runs: ["结果与报告", "本机历史运行、报告与 CSV"],
    about: ["关于与伦理", "项目边界、局限与链接"],
  };

  const FAMILY_LABEL = {
    semantic: "语义类",
    social: "社会工程",
    structural: "结构类",
    obfuscation: "混淆类",
  };

  document.addEventListener("DOMContentLoaded", init);

  async function init() {
    applyTheme(state.theme);
    bind();
    try {
      const [meta, goals] = await Promise.all([api("/api/meta"), api("/api/goals")]);
      state.meta = meta;
      state.goals = goals;
      renderMeta();
      renderOptions();
      renderGoalChips();
      setModel("mock");
      await loadRuns();
      const initial = new URLSearchParams(window.location.search).get("page");
      navigate(PAGE_META[initial] ? initial : "dashboard");
    } catch (err) {
      modal(
        "无法连接本地服务",
        `<p>${escapeHtml(err.message)}</p><p>请关闭程序后重新启动 <code>JailForge.exe</code>。如果问题持续，查看 <code>results/logs/</code>。</p>`
      );
    }
  }

  /* ------------------------------------------------------------------ */
  /* API                                                                */
  /* ------------------------------------------------------------------ */
  async function api(path, options = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
    if (options.method && options.method !== "GET") headers["X-JF-Token"] = TOKEN;
    const response = await fetch(path, Object.assign({}, options, { headers }));
    const text = await response.text();
    let data = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { error: text };
    }
    if (!response.ok) throw new Error(data.error || `请求失败 (${response.status})`);
    return data;
  }

  const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body) });

  /* ------------------------------------------------------------------ */
  /* Meta / options                                                     */
  /* ------------------------------------------------------------------ */
  function renderMeta() {
    const meta = state.meta;
    $("#stat-goals").textContent = meta.counts.goals;
    $("#stat-attacks").textContent = meta.counts.attacks;
    $("#stat-defenses").textContent = meta.counts.defenses;
    $("#sidebar-version").textContent = `v${meta.version}`;
    $("#about-version").textContent = meta.version;
    $("#results-dir").textContent = meta.results_dir;
    $("#about-results-dir").textContent = meta.results_dir;
    $("#single-goal").value = state.goals[0]?.behavior || "";
    const evoTarget = state.goals.find((goal) => goal.id === "zh-021") || state.goals[0];
    $("#evo-goal").value = evoTarget?.behavior || "";
    if (!meta.model.real_available) {
      const realBtn = $('#model-switch button[data-model="openai_compatible"]');
      realBtn.title = meta.model.reason || "未配置 .env";
      realBtn.classList.add("locked");
    }
  }

  function renderOptions() {
    const attacks = state.meta.attacks;
    const families = {};
    attacks.forEach((attack) => {
      (families[attack.family] ||= []).push(attack);
    });
    const grouped = Object.entries(families)
      .map(
        ([family, list]) =>
          `<optgroup label="${escapeHtml(FAMILY_LABEL[family] || family)}">` +
          list
            .map(
              (attack) =>
                `<option value="${escapeHtml(attack.name)}" title="${escapeHtml(attack.description)}">${escapeHtml(attack.name)}</option>`
            )
            .join("") +
          "</optgroup>"
      )
      .join("");
    $("#single-method").innerHTML = grouped;

    const defenseOptions = state.meta.defenses
      .map((defense) => `<option value="${escapeHtml(defense.name)}">${escapeHtml(defense.label)} · ${escapeHtml(defense.name)}</option>`)
      .join("");
    $("#single-defense").innerHTML = defenseOptions;
    $("#evo-defense").innerHTML = defenseOptions;
    $("#single-defense").value = "layered";
    $("#evo-defense").value = "layered";

    const methodDefaults = new Set(["direct", "role_play", "refusal_suppression", "base64"]);
    $("#batch-methods").innerHTML = attacks
      .map(
        (attack) => `<label class="check">
          <input type="checkbox" value="${escapeHtml(attack.name)}" ${methodDefaults.has(attack.name) ? "checked" : ""}>
          <span class="check-body"><b>${escapeHtml(attack.name)}</b><small>${escapeHtml(attack.description)}</small></span>
        </label>`
      )
      .join("");

    const defenseDefaults = new Set(["none", "filter", "self_defense", "layered"]);
    $("#batch-defenses").innerHTML = state.meta.defenses
      .map(
        (defense) => `<label class="check">
          <input type="checkbox" value="${escapeHtml(defense.name)}" ${defenseDefaults.has(defense.name) ? "checked" : ""}>
          <span class="check-body"><b>${escapeHtml(defense.label)}</b><small>${escapeHtml(defense.description)}</small></span>
        </label>`
      )
      .join("");

    updateBatchEstimate();
  }

  function renderGoalChips() {
    const container = $("#goal-chips");
    container.innerHTML = state.goals
      .slice(0, 8)
      .map(
        (goal) =>
          `<button class="chip" data-goal="${escapeHtml(goal.behavior)}" title="${escapeHtml(goal.behavior)}">${escapeHtml(goal.behavior)}</button>`
      )
      .join("");
  }

  /* ------------------------------------------------------------------ */
  /* Navigation / model / theme                                         */
  /* ------------------------------------------------------------------ */
  function navigate(page) {
    const meta = PAGE_META[page] || PAGE_META.dashboard;
    $("#page-title").textContent = meta[0];
    $("#page-subtitle").textContent = meta[1];
    $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.page === page));
    $$(".page").forEach((section) => section.classList.toggle("active", section.id === `page-${page}`));
    if (page === "runs") loadRuns();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function setModel(model) {
    if (model === "openai_compatible" && !state.meta?.model.real_available) {
      modal(
        "真实 API 尚未配置",
        `<p>当前只启用了离线 Mock。要调用真实模型，请在 <code>JailForge.exe</code> 同目录放入 <code>.env</code>：</p>
         <pre class="code">JAILFORGE_BASE_URL=https://api.deepseek.com/v1
JAILFORGE_MODEL=deepseek-chat
JAILFORGE_API_KEY=sk-...</pre>
         <p>保存后重启程序即可。也可以在“单条测试”里继续使用 Mock 模式。</p>
         <p class="muted tiny">检测到的配置：${escapeHtml(state.meta?.model?.reason || "无")}</p>`
      );
      return;
    }
    state.model = model;
    $$("#model-switch button").forEach((button) => button.classList.toggle("active", button.dataset.model === model));
    const dot = $("#model-dot");
    dot.className = "dot" + (model === "mock" ? "" : " real");
    $("#model-label").textContent = model === "mock" ? "Mock 离线" : state.meta.model.real_model || "真实 API";
    $("#model-detail").textContent = model === "mock" ? "无需 API Key，开箱即用" : "已连接 OpenAI-compatible 接口";
    ["#single-judge", "#batch-judge", "#evo-judge"].forEach((selector) => {
      const select = $(selector);
      if (!select) return;
      const llmOption = select.querySelector('option[value="llm"]');
      if (llmOption) llmOption.disabled = model === "mock";
      if (model === "mock" && select.value === "llm") select.value = "rule";
    });
  }

  function applyTheme(theme) {
    state.theme = theme;
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("jf-theme", theme);
    const use = $("#theme-toggle use");
    if (use) use.setAttribute("href", theme === "dark" ? "#i-sun" : "#i-moon");
  }

  /* ------------------------------------------------------------------ */
  /* Single                                                             */
  /* ------------------------------------------------------------------ */
  async function runSingle() {
    const goal = $("#single-goal").value.trim();
    if (!goal) return toast("请先输入测试目标。", "warn");
    const button = $("#btn-single");
    setBusy(button, true, "运行中…");
    try {
      const data = await post("/api/single", {
        goal,
        method: $("#single-method").value,
        defense: $("#single-defense").value,
        provider: state.model,
        judge: $("#single-judge").value,
      });
      renderSingle(data);
      toast("测试完成", "ok");
    } catch (err) {
      toast(err.message, "err");
    } finally {
      setBusy(button, false);
    }
  }

  function renderSingle(data) {
    $("#single-empty").classList.add("hidden");
    $("#single-output").classList.remove("hidden");
    $("#single-prompt").textContent = data.prompt || "";
    $("#single-response").textContent = data.response || "（空）";
    $("#single-model").textContent = data.model || "";

    const defense = data.defense || {};
    const blockBadge = $("#single-block-badge");
    blockBadge.textContent = defense.blocked ? "已拦截" : "未拦截";
    blockBadge.className = "badge " + (defense.blocked ? "bad" : "ok");
    const scores =
      defense.scores && Object.keys(defense.scores).length
        ? Object.entries(defense.scores)
            .map(([key, value]) => `${key}=${value}`)
            .join(", ")
        : "—";
    $("#single-defense").innerHTML = kvRows([
      ["阶段", defense.stage || "—"],
      ["原因", defense.reason || "—"],
      ["评分", scores],
      ["系统提示", defense.system_prompt ? `${defense.system_prompt.slice(0, 220)}…` : "—"],
    ]);

    const judge = data.judge || {};
    const judgeBadge = $("#single-judge-badge");
    judgeBadge.textContent = judge.success ? "越狱成功" : "未越狱";
    judgeBadge.className = "badge " + (judge.success ? "bad" : "ok");
    $("#single-judge-body").innerHTML =
      kvRows([
        ["评判器", judge.name || "—"],
        ["分数", Number(judge.score ?? 0).toFixed(3)],
        ["置信度", judge.confidence != null ? Number(judge.confidence).toFixed(2) : "—"],
        ["理由", judge.rationale || "—"],
      ]) + `<div class="muted tiny" style="margin-top:10px">耗时 ${Number(data.elapsed_ms || 0).toFixed(0)} ms</div>`;
  }

  /* ------------------------------------------------------------------ */
  /* Batch                                                              */
  /* ------------------------------------------------------------------ */
  async function runBatch() {
    const methods = checkedValues("#batch-methods");
    const defenses = checkedValues("#batch-defenses");
    if (!methods.length) return toast("请至少选择一种攻击方法。", "warn");
    if (!defenses.length) return toast("请至少选择一种防御配置。", "warn");
    const button = $("#btn-batch");
    setBusy(button, true, "评测中…");
    const progress = $("#batch-progress");
    progress.classList.remove("hidden");
    updateProgress("#batch", 0, "正在创建任务…");
    try {
      const job = await post("/api/batch", {
        sample_size: Number($("#batch-size").value),
        methods,
        defenses,
        provider: state.model,
        judge: $("#batch-judge").value,
      });
      pollJob(job.job_id, {
        onProgress: (snapshot) => updateProgress("#batch", snapshot.progress, snapshot.message),
        onDone: (result) => {
          updateProgress("#batch", 1, "完成");
          renderBatch(result);
          setBusy(button, false);
          toast("批量评测完成", "ok");
          loadRuns();
        },
        onError: (message) => {
          setBusy(button, false);
          toast(message, "err");
          progress.classList.add("hidden");
        },
      });
    } catch (err) {
      setBusy(button, false);
      progress.classList.add("hidden");
      toast(err.message, "err");
    }
  }

  function renderBatch(result) {
    const summary = result.summary;
    const overall = summary.overall;
    $("#batch-results").classList.remove("hidden");
    $("#batch-asr").textContent = pct(overall.asr);
    $("#batch-ci").textContent = `95% CI ${pct(overall.asr_ci95?.[0] || 0)}–${pct(overall.asr_ci95?.[1] || 0)}`;
    $("#batch-valid").textContent = `${overall.valid} / ${overall.n}`;
    $("#batch-blocked").textContent = overall.blocked;
    $("#batch-errors").textContent = overall.errors;

    const defenses = Object.keys(summary.by_defense);
    const methods = Object.keys(summary.matrix);
    let html = "<thead><tr><th>攻击方法</th>" + defenses.map((name) => `<th>${escapeHtml(defenseLabel(name))}</th>`).join("") + "</tr></thead><tbody>";
    methods.forEach((method) => {
      const family = state.meta.attacks.find((attack) => attack.name === method)?.family;
      html += `<tr><td><b>${escapeHtml(method)}</b><br><small class="muted">${escapeHtml(FAMILY_LABEL[family] || "")}</small></td>`;
      defenses.forEach((defense) => {
        const value = summary.matrix[method]?.[defense] ?? 0;
        html += `<td class="num ${value > 0 ? "bad" : "ok"}">${pct(value)}</td>`;
      });
      html += "</tr>";
    });
    html += "<tr><td><b>总体 ASR</b></td>";
    defenses.forEach((defense) => {
      html += `<td class="num"><b>${pct(summary.by_defense[defense]?.asr || 0)}</b></td>`;
    });
    html += "</tr></tbody>";
    $("#batch-matrix").innerHTML = html;

    barChart(
      $("#batch-chart"),
      defenses.map(defenseLabel),
      defenses.map((defense) => summary.by_defense[defense]?.asr || 0)
    );

    $("#batch-downloads").innerHTML = Object.entries(result.downloads || {})
      .map(
        ([key, href]) =>
          `<a href="${href}" download><svg class="ico tiny"><use href="#i-download"/></svg>${key === "csv" ? "明细 CSV" : key === "report" ? "Markdown 报告" : "summary.json"}</a>`
      )
      .join("");

    const preview = result.preview || [];
    let table = "<thead><tr><th>目标</th><th>攻击</th><th>防御</th><th>拦截</th><th>越狱</th><th>评分</th></tr></thead><tbody>";
    preview.forEach((row) => {
      table += `<tr>
        <td>${escapeHtml(row.goal_id)}</td>
        <td>${escapeHtml(row.method)}</td>
        <td>${escapeHtml(defenseLabel(row.defense))}</td>
        <td>${row.blocked ? '<span class="badge bad">是</span>' : '<span class="badge soft">否</span>'}</td>
        <td>${row.success ? '<span class="badge bad">是</span>' : '<span class="badge ok">否</span>'}</td>
        <td class="num">${Number(row.judge_score || 0).toFixed(2)}</td>
      </tr>`;
    });
    $("#batch-preview").innerHTML = table + "</tbody>";
  }

  /* ------------------------------------------------------------------ */
  /* Evolution                                                          */
  /* ------------------------------------------------------------------ */
  async function runEvolve() {
    const goal = $("#evo-goal").value.trim();
    if (!goal) return toast("请先输入进化目标。", "warn");
    const button = $("#btn-evolve");
    setBusy(button, true, "进化中…");
    const progress = $("#evo-progress");
    progress.classList.remove("hidden");
    updateProgress("#evo", 0, "正在创建任务…");
    try {
      const job = await post("/api/evolve", {
        goal,
        defense: $("#evo-defense").value,
        generations: Number($("#evo-generations").value),
        population: Number($("#evo-population").value),
        provider: state.model,
        judge: $("#evo-judge").value,
      });
      pollJob(job.job_id, {
        onProgress: (snapshot) => updateProgress("#evo", snapshot.progress, snapshot.message),
        onDone: (result) => {
          updateProgress("#evo", 1, "完成");
          renderEvolve(result);
          setBusy(button, false);
          toast("进化完成", "ok");
          loadRuns();
        },
        onError: (message) => {
          setBusy(button, false);
          toast(message, "err");
          progress.classList.add("hidden");
        },
      });
    } catch (err) {
      setBusy(button, false);
      progress.classList.add("hidden");
      toast(err.message, "err");
    }
  }

  function renderEvolve(result) {
    $("#evo-empty").classList.add("hidden");
    $("#evo-output").classList.remove("hidden");
    $("#evo-best").textContent = Number(result.best_fitness || 0).toFixed(3);
    $("#evo-baseline").textContent = Number(result.baseline_fitness || 0).toFixed(3);
    $("#evo-evals").textContent = result.evaluations ?? "—";
    $("#evo-cache").textContent = result.cache_hits ?? "—";
    const history = result.history || [];
    $("#evo-gens").textContent = `${history.length ? history[history.length - 1].generation : 0}`;
    $("#evo-prompt").textContent = result.best_prompt || "";

    lineChart(
      $("#evo-chart"),
      [
        { name: "最佳", color: "#22d3ee", values: history.map((row) => row.best_fitness) },
        { name: "平均", color: "#a78bfa", values: history.map((row) => row.mean_fitness) },
      ],
      history.map((row) => row.generation)
    );

    let table = "<thead><tr><th>代数</th><th>最佳适应度</th><th>平均适应度</th><th>被拦截比例</th><th>种群</th></tr></thead><tbody>";
    history.forEach((row) => {
      table += `<tr>
        <td class="num">${row.generation}</td>
        <td class="num">${Number(row.best_fitness).toFixed(3)}</td>
        <td class="num">${Number(row.mean_fitness).toFixed(3)}</td>
        <td class="num">${pct(row.blocked_ratio)}</td>
        <td class="num">${row.population}</td>
      </tr>`;
    });
    $("#evo-history").innerHTML = table + "</tbody>";
  }

  /* ------------------------------------------------------------------ */
  /* Jobs                                                               */
  /* ------------------------------------------------------------------ */
  function pollJob(jobId, handlers) {
    const tick = async () => {
      try {
        const snapshot = await api(`/api/jobs/${jobId}`);
        if (snapshot.status === "queued" || snapshot.status === "running") {
          handlers.onProgress?.(snapshot);
          setTimeout(tick, 800);
        } else if (snapshot.status === "done") {
          handlers.onDone?.(snapshot.result, snapshot);
        } else {
          handlers.onError?.(snapshot.error || "任务失败");
        }
      } catch (err) {
        handlers.onError?.(err.message);
      }
    };
    tick();
  }

  /* ------------------------------------------------------------------ */
  /* Runs                                                               */
  /* ------------------------------------------------------------------ */
  async function loadRuns() {
    try {
      state.runs = await api("/api/runs");
    } catch (err) {
      toast(err.message, "err");
      return;
    }
    const recent = $("#recent-runs");
    const all = $("#runs-list");
    if (!state.runs.length) {
      const empty = '<div class="empty small">还没有运行记录，先做一次批量评测吧。</div>';
      if (recent) recent.innerHTML = empty;
      if (all) all.innerHTML = empty;
      return;
    }
    if (recent) recent.innerHTML = state.runs.slice(0, 4).map(runItem).join("");
    if (all) all.innerHTML = state.runs.map(runItem).join("");
  }

  function runItem(run) {
    return `<div class="run-item">
      <div class="run-main">
        <div class="run-title">${escapeHtml(run.model || "未知模型")} <span class="badge soft">${escapeHtml(run.provider || "")}</span></div>
        <div class="run-meta">${escapeHtml(run.timestamp || "")} · ${run.n} trials · 成功 ${run.success}</div>
      </div>
      <div class="run-asr">${pct(run.asr)}</div>
      <div class="run-links">
        <a href="${run.downloads.report}" download>报告</a>
        <a href="${run.downloads.csv}" download>CSV</a>
      </div>
    </div>`;
  }

  /* ------------------------------------------------------------------ */
  /* Charts                                                             */
  /* ------------------------------------------------------------------ */
  function barChart(container, labels, values) {
    if (!container) return;
    if (!labels.length) {
      container.innerHTML = '<div class="empty small">没有可展示的数据。</div>';
      return;
    }
    const width = 720;
    const height = 320;
    const left = 58;
    const right = 22;
    const top = 28;
    const bottom = 76;
    const plotW = width - left - right;
    const plotH = height - top - bottom;
    const max = Math.max(0.05, ...values) * 1.2;
    const slot = plotW / labels.length;
    const barW = Math.min(58, slot * 0.55);
    const gradientId = `bar-grad-${Math.random().toString(36).slice(2, 8)}`;
    let svg = `<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI, Microsoft YaHei, sans-serif">
      <defs><linearGradient id="${gradientId}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#67e8f9"/><stop offset="0.55" stop-color="#818cf8"/><stop offset="1" stop-color="#f472b6"/>
      </linearGradient></defs>`;
    for (let i = 0; i <= 4; i += 1) {
      const y = top + (plotH * i) / 4;
      const value = (max * (4 - i)) / 4;
      svg += `<line x1="${left}" y1="${y}" x2="${left + plotW}" y2="${y}" stroke="rgba(148,163,184,0.16)"/>`;
      svg += `<text x="${left - 8}" y="${y + 4}" font-size="10" fill="#93a3ba" text-anchor="end">${(value * 100).toFixed(0)}%</text>`;
    }
    labels.forEach((label, index) => {
      const value = values[index];
      const x = left + slot * index + (slot - barW) / 2;
      const barH = (plotH * value) / max;
      const y = top + plotH - barH;
      svg += `<rect x="${x}" y="${y}" width="${barW}" height="${Math.max(1, barH)}" rx="5" fill="url(#${gradientId})" opacity="0.9"/>`;
      svg += `<text x="${x + barW / 2}" y="${Math.max(top + 10, y - 6)}" font-size="10" fill="#e7eef9" text-anchor="middle">${pct(value)}</text>`;
      const text = String(label).length > 8 ? `${String(label).slice(0, 7)}…` : String(label);
      svg += `<text x="${x + barW / 2}" y="${top + plotH + 16}" font-size="10" fill="#93a3ba" text-anchor="end" transform="rotate(-25 ${x + barW / 2} ${top + plotH + 16})">${escapeHtml(text)}</text>`;
    });
    svg += `<line x1="${left}" y1="${top + plotH}" x2="${left + plotW}" y2="${top + plotH}" stroke="rgba(148,163,184,0.3)"/></svg>`;
    container.innerHTML = svg;
  }

  function lineChart(container, series, labels) {
    if (!container) return;
    if (!series.length || !labels.length) {
      container.innerHTML = '<div class="empty small">没有可展示的数据。</div>';
      return;
    }
    const width = 720;
    const height = 320;
    const left = 58;
    const right = 22;
    const top = 34;
    const bottom = 46;
    const plotW = width - left - right;
    const plotH = height - top - bottom;
    const allValues = series.flatMap((item) => item.values.map(Number));
    const max = Math.max(0.1, ...allValues) * 1.12;
    const min = Math.min(0, ...allValues);
    const span = max - min || 1;
    const xAt = (index) => left + (labels.length === 1 ? plotW / 2 : (plotW * index) / (labels.length - 1));
    const yAt = (value) => top + plotH * (1 - (value - min) / span);

    let svg = `<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI, Microsoft YaHei, sans-serif">`;
    for (let i = 0; i <= 4; i += 1) {
      const y = top + (plotH * i) / 4;
      const value = max - (span * i) / 4;
      svg += `<line x1="${left}" y1="${y}" x2="${left + plotW}" y2="${y}" stroke="rgba(148,163,184,0.16)"/>`;
      svg += `<text x="${left - 8}" y="${y + 4}" font-size="10" fill="#93a3ba" text-anchor="end">${value.toFixed(2)}</text>`;
    }
    series.forEach((item) => {
      const points = item.values.map((value, index) => `${xAt(index)},${yAt(Number(value))}`).join(" ");
      svg += `<polyline points="${points}" fill="none" stroke="${item.color}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>`;
      item.values.forEach((value, index) => {
        svg += `<circle cx="${xAt(index)}" cy="${yAt(Number(value))}" r="3.4" fill="${item.color}"/>`;
      });
    });
    labels.forEach((label, index) => {
      svg += `<text x="${xAt(index)}" y="${top + plotH + 18}" font-size="10" fill="#93a3ba" text-anchor="middle">${escapeHtml(label)}</text>`;
    });
    series.forEach((item, index) => {
      const x = left + index * 100;
      svg += `<rect x="${x}" y="8" width="10" height="3" rx="1.5" fill="${item.color}"/>`;
      svg += `<text x="${x + 15}" y="12" font-size="10" fill="#93a3ba">${escapeHtml(item.name)}</text>`;
    });
    svg += `<line x1="${left}" y1="${top + plotH}" x2="${left + plotW}" y2="${top + plotH}" stroke="rgba(148,163,184,0.3)"/></svg>`;
    container.innerHTML = svg;
  }

  /* ------------------------------------------------------------------ */
  /* UI helpers                                                         */
  /* ------------------------------------------------------------------ */
  function bind() {
    $$(".nav-item").forEach((item) => item.addEventListener("click", () => navigate(item.dataset.page)));
    $$("[data-goto]").forEach((button) => button.addEventListener("click", () => navigate(button.dataset.goto)));
    $("#model-switch").addEventListener("click", (event) => {
      const button = event.target.closest("button[data-model]");
      if (button) setModel(button.dataset.model);
    });
    $("#theme-toggle").addEventListener("click", () => applyTheme(state.theme === "dark" ? "light" : "dark"));
    $("#btn-single").addEventListener("click", runSingle);
    $("#btn-batch").addEventListener("click", runBatch);
    $("#btn-evolve").addEventListener("click", runEvolve);
    ["#btn-refresh-runs", "#btn-refresh-runs-2"].forEach((selector) => {
      const button = $(selector);
      if (button) button.addEventListener("click", loadRuns);
    });
    $("#btn-quit").addEventListener("click", quitApp);
    $("#modal-close").addEventListener("click", closeModal);
    $("#modal").addEventListener("click", (event) => {
      if (event.target === $("#modal")) closeModal();
    });
    $("#goal-chips").addEventListener("click", (event) => {
      const chip = event.target.closest("[data-goal]");
      if (chip) {
        $("#single-goal").value = chip.dataset.goal;
        toast("已填入目标", "ok");
      }
    });
    document.addEventListener("click", (event) => {
      const button = event.target.closest("[data-copy-target]");
      if (button) {
        const target = document.getElementById(button.dataset.copyTarget);
        copyText(target?.textContent || "");
      }
    });

    $("#batch-size").addEventListener("input", () => {
      $("#batch-size-label").textContent = $("#batch-size").value;
      updateBatchEstimate();
    });
    $("#batch-methods").addEventListener("change", updateBatchEstimate);
    $("#batch-defenses").addEventListener("change", updateBatchEstimate);
    $("#evo-generations").addEventListener("input", () => {
      $("#evo-gen-label").textContent = $("#evo-generations").value;
    });
    $("#evo-population").addEventListener("input", () => {
      $("#evo-pop-label").textContent = $("#evo-population").value;
    });

    document.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        const active = $(".page.active")?.id;
        if (active === "page-single") runSingle();
        if (active === "page-batch") runBatch();
        if (active === "page-evolve") runEvolve();
      }
    });
  }

  function updateBatchEstimate() {
    const size = Number($("#batch-size")?.value || 0);
    const methods = checkedValues("#batch-methods").length;
    const defenses = checkedValues("#batch-defenses").length;
    $("#batch-estimate").textContent = `约 ${size * methods * defenses} 次生成`;
  }

  function checkedValues(selector) {
    return $$(`${selector} input[type="checkbox"]:checked`).map((input) => input.value);
  }

  function setBusy(button, busy, label) {
    if (!button) return;
    if (busy) {
      if (!button.dataset.label) button.dataset.label = button.innerHTML;
      button.disabled = true;
      button.innerHTML = `<span class="spinner"></span>${escapeHtml(label || "处理中…")}`;
    } else {
      button.disabled = false;
      if (button.dataset.label) {
        button.innerHTML = button.dataset.label;
        delete button.dataset.label;
      }
    }
  }

  function updateProgress(prefix, value, message) {
    const percent = Math.round(Math.max(0, Math.min(1, value)) * 100);
    const pctEl = $(`${prefix}-progress-pct`);
    const barEl = $(`${prefix}-progress-bar`);
    const textEl = $(`${prefix}-progress-text`);
    if (pctEl) pctEl.textContent = `${percent}%`;
    if (barEl) barEl.style.width = `${percent}%`;
    if (textEl) textEl.textContent = message || "";
  }

  function defenseLabel(name) {
    return state.meta?.defenses?.find((defense) => defense.name === name)?.label || name;
  }

  function pct(value) {
    return `${(Number(value || 0) * 100).toFixed(1)}%`;
  }

  function kvRows(rows) {
    return `<div class="kv">${rows
      .map(
        ([key, value]) =>
          `<div class="kv-row"><span class="k">${escapeHtml(key)}</span><span class="v">${escapeHtml(value)}</span></div>`
      )
      .join("")}</div>`;
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character];
    });
  }

  function toast(message, type = "ok") {
    const container = $("#toasts");
    const item = document.createElement("div");
    item.className = `toast ${type}`;
    item.textContent = message;
    container.appendChild(item);
    setTimeout(() => {
      item.style.opacity = "0";
      item.style.transform = "translateY(6px)";
      item.style.transition = "all 0.25s ease";
      setTimeout(() => item.remove(), 260);
    }, 3800);
  }

  function modal(title, html) {
    $("#modal-title").textContent = title;
    $("#modal-body").innerHTML = html;
    $("#modal").classList.remove("hidden");
  }

  function closeModal() {
    $("#modal").classList.add("hidden");
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      toast("已复制到剪贴板", "ok");
    } catch {
      const area = document.createElement("textarea");
      area.value = text;
      document.body.appendChild(area);
      area.select();
      try {
        document.execCommand("copy");
        toast("已复制到剪贴板", "ok");
      } catch {
        toast("复制失败，请手动选择文本", "err");
      }
      area.remove();
    }
  }

  async function quitApp() {
    if (!window.confirm("确定退出 JailForge 吗？本地服务会关闭。")) return;
    try {
      await post("/api/shutdown", {});
    } catch {
      /* server may close before responding */
    }
    $("#quit-screen").classList.remove("hidden");
  }
})();
