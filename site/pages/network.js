(function () {
  "use strict";
  const DATA = JSON.parse(document.getElementById("network-data").textContent);
  const $ = (s, r = document) => r.querySelector(s);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = n => typeof n === "number" ? n.toLocaleString("zh-CN") : String(n ?? "");
  const LAYERS = ["trait", "gene", "population"];
  const LAYER_NAME = { trait: "表型", gene: "基因层", population: "种群" };
  const LAYER_CLASS = { trait: "layer-trait", gene: "layer-gene", population: "layer-population" };
  const NATURE = { causal: ["因果", "brand"], associational: ["相关", "gold"], structural: ["结构", "info"], descriptive: ["描述", ""], unknown: ["未判定", ""] };
  const REVIEW = { pending_review: ["待复核", "amber"], auto_validated: ["自动校验", "ok"], model_verified: ["模型复核", "brand"], expert_approved: ["专家通过", "ok"], rejected: ["已驳回", "clay"] };
  const KIND = { gene: "基因", qtl: "QTL", qtn: "QTN", trait: "表型", population: "种群" };
  const CONF = { A: ["A 共识", "ok"], B: ["B 支持", "gold"], C: ["C 存疑", "amber"] };
  const PACKAGE = { complete: ["完整", "ok"], partial: ["部分缺失", "amber"], unverified: ["未验证", ""], not_submitted: ["未提交", "clay"] };
  const EDGE_ORDER = { "表型—基因": 0, "基因—种群": 1, "表型—种群": 2 };

  const state = { mode: "paper", paper: (DATA.papers || [])[0] ? DATA.papers[0].id : null, q: "", pair: "all", edge: null, node: null };

  // Review decisions stay in this browser until the reviewer exports them; the export is what `bdc review apply`
  // consumes.  localStorage is unavailable in some file:// contexts, hence the in-memory fallback.
  const REVIEW_KEY = "pdf2jsonl.review-decisions.v1";
  const REVIEWER_KEY = "pdf2jsonl.reviewer.v1";
  const memoryStore = {};
  const store = {
    get(key) { try { return localStorage.getItem(key); } catch { return memoryStore[key] || null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch { memoryStore[key] = value; } },
  };
  function loadDecisions() {
    try { const value = JSON.parse(store.get(REVIEW_KEY) || "{}"); return value && typeof value === "object" ? value : {}; }
    catch { return {}; }
  }
  function loadReviewer() { return store.get(REVIEWER_KEY) || ""; }
  state.decisions = loadDecisions();
  state.reviewer = loadReviewer();
  const DECISION = {
    expert_approved: ["通过", "ok"],
    rejected: ["驳回", "clay"],
    pending_review: ["退回补证", "amber"],
  };

  function kindLabel(t) { return KIND[t] || t || "实体"; }
  function typed(label, type, layer) {
    return `<span class="ent ${LAYER_CLASS[layer] || ""}">${esc(label)}<em>${esc(kindLabel(type))}</em></span>`;
  }
  function paperById(id) { return (DATA.papers || []).find(p => p.id === id) || null; }
  function currentPaper() { return paperById(state.paper); }
  function edgeById(id) { return (DATA.edges || []).find(e => e.id === id) || null; }
  function nodeById(id) { return (DATA.nodes || []).find(n => n.id === id) || null; }
  function edgesOfPaper(p) { return (p && p.edges) || []; }
  function reviewOf(e) { return [...new Set((e.evidence || []).map(x => x.review_status).filter(Boolean))]; }
  function natureTag(nature) { const [label, tone] = NATURE[nature] || NATURE.unknown; return `<span class="tag ${tone}">${esc(label)}</span>`; }
  function reviewTag(status) { const [label, tone] = REVIEW[status] || [status || "未标记", ""]; return `<span class="tag ${tone}">${esc(label)}</span>`; }
  function pairTag(pair) { return `<span class="tag">${esc(pair || "关系")}</span>`; }
  function confidenceTag(confidence) {
    if (!confidence) return "";
    const [label, tone] = CONF[confidence] || [confidence, ""];
    return `<span class="tag ${tone}" title="${esc(confidence)}">${esc(label)}</span>`;
  }
  function chainTag(edge) {
    const applicable = (edge.evidence || []).some(ev => (ev.chain || {}).applicable !== false);
    if (!applicable) return `<span class="tag">背景/假设陈述</span>`;
    if (edge.chain_complete) return `<span class="tag ok">证据链完整</span>`;
    const missing = (edge.chain_missing || []).join("；");
    return `<span class="tag amber" title="${esc(missing)}">证据链不完整</span>`;
  }
  function confidenceBasis(edge) {
    const basis = edge.confidence_basis || [];
    return basis.length ? `<div class="xs muted" style="margin-top:6px">置信依据：${esc(basis.join("；"))}</div>` : "";
  }

  function edgeMatches(e) {
    if (state.pair !== "all" && e.pair !== state.pair) return false;
    if (!state.q) return true;
    const text = [e.subject_label, e.predicate, e.object_label, e.predicate_code,
      ...(e.evidence || []).flatMap(x => [x.paper_title, x.paper_doi, x.paper_year])].join(" ").toLowerCase();
    return text.includes(state.q);
  }

  function visiblePaperEdges() { return edgesOfPaper(currentPaper()).filter(edgeMatches); }
  function visibleNetworkEdges() { return (DATA.edges || []).filter(edgeMatches); }

  // ------------------------------------------------------------------ shell / mode / meta
  function renderMode() {
    document.querySelectorAll("[data-mode]").forEach(btn => btn.setAttribute("aria-selected", String(btn.dataset.mode === state.mode)));
    $("#paper-view").hidden = state.mode !== "paper";
    $("#network-view").hidden = state.mode !== "network";
    $("#q").placeholder = state.mode === "paper" ? "在这篇论文里搜性状、基因、QTL/QTN 或种群…" : "搜索所有论文的性状、基因、QTL/QTN、种群或论文…";
  }
  function renderMeta() {
    const host = $("#net-meta");
    if (state.mode === "paper") {
      const p = currentPaper();
      if (!p) { host.innerHTML = `<span>还没有可查看的论文。</span>`; return; }
      const hidden = Object.values(p.hidden || {}).reduce((a, b) => a + b, 0);
      const pkg = p.package || {};
      host.innerHTML = `<span><b>${fmt((p.edges || []).length)}</b> 条三元关系</span>
        <span><b>${fmt((p.edges || []).reduce((n, e) => n + (e.evidence_count || 0), 0))}</b> 条证据</span>
        <span><b>${fmt(p.records || 0)}</b> 条记录</span>
        <span>文章包 <span class="tag ${(PACKAGE[pkg.status] || ["", ""])[1]}">${esc((PACKAGE[pkg.status] || [pkg.status || "未评估", ""])[0])}</span></span>
        <span class="${hidden ? "hidden-n" : "muted"}">隐去 <b>${fmt(hidden)}</b> 条其他关系</span>`;
      $("#net-sub").textContent = `${(p.edges || []).length} 条关系`;
    } else {
      const s = DATA.summary || {};
      const conf = s.confidence || {};
      host.innerHTML = `<span><b>${fmt(s.papers || 0)}</b> 篇论文</span>
        <span><b>${fmt(s.edges || 0)}</b> 条关系</span>
        <span><b>${fmt(s.nodes || 0)}</b> 个节点</span>
        <span><b>${fmt(s.evidence || 0)}</b> 条证据</span>
        <span>置信 A ${fmt(conf.A || 0)} · B ${fmt(conf.B || 0)} · C ${fmt(conf.C || 0)}</span>
        <span class="${s.conflicts ? "hidden-n" : "muted"}">冲突 <b>${fmt(s.conflicts || 0)}</b> 条 · 隐去 <b>${fmt(s.hidden || 0)}</b> 条其他关系</span>`;
      $("#net-sub").textContent = s.edges ? `${s.edges} 条 · ${s.evidence} 条证据` : "";
    }
  }
  function renderChips() {
    const edges = state.mode === "paper" ? edgesOfPaper(currentPaper()) : (DATA.edges || []);
    const counts = {};
    edges.forEach(e => { counts[e.pair] = (counts[e.pair] || 0) + 1; });
    const chips = [`<button type="button" class="chip" data-pair="all" aria-pressed="${state.pair === "all"}">全部 <span class="n">${edges.length}</span></button>`];
    Object.keys(counts).sort((a, b) => (EDGE_ORDER[a] ?? 9) - (EDGE_ORDER[b] ?? 9)).forEach(pair => {
      chips.push(`<button type="button" class="chip" data-pair="${esc(pair)}" aria-pressed="${state.pair === pair}">${esc(pair)} <span class="n">${counts[pair]}</span></button>`);
    });
    $("#pair-chips").innerHTML = chips.join("");
    $("#pair-chips").querySelectorAll("[data-pair]").forEach(btn => btn.addEventListener("click", () => {
      state.pair = btn.dataset.pair; state.edge = null; state.node = null; renderAll();
    }));
  }

  // ------------------------------------------------------------------ human review queue
  function saveReviewDecision(recordId, status, note) {
    state.decisions[recordId] = {
      status, note: String(note || "").trim(), reviewer: state.reviewer || "未署名",
      decided_at: new Date().toISOString(),
    };
    store.set(REVIEW_KEY, JSON.stringify(state.decisions));
  }
  function decisionOf(id) { return state.decisions[id] || null; }
  function reviewItemHTML(item) {
    const decision = decisionOf(item.record_id);
    const decisionLabel = decision ? (DECISION[decision.status] || [decision.status, ""]) : null;
    const qc = (item.qc_failure_codes || []).map(c => `<span class="tag" title="${esc(c)}">${esc(c)}</span>`).join("");
    return `<div class="review-item" data-review-item="${esc(item.record_id)}">
      <div class="rmeta"><span class="tag amber">待复核</span><span class="tag">${esc(item.kind_label)}</span><span class="tag ${item.in_scope ? "info" : ""}">${item.in_scope ? "三元关系" : "其他关系"}</span>${item.section ? `<span class="tag">${esc(item.section)}</span>` : ""}${item.page != null ? `<span class="tag">p.${esc(item.page)}</span>` : ""}${item.table_figure ? `<span class="tag gold">${esc(item.table_figure)}</span>` : ""}${qc}</div>
      <div class="rtext">${esc(item.text || "（记录没有摘要文本）")}</div>
      ${item.quote ? `<blockquote>${esc(item.quote)}</blockquote>` : ""}
      <div class="review-actions">
        <button type="button" class="btn sm ${decision && decision.status === "expert_approved" ? "primary" : ""}" data-decide="expert_approved" data-rec="${esc(item.record_id)}">通过</button>
        <button type="button" class="btn sm ${decision && decision.status === "rejected" ? "primary" : ""}" data-decide="rejected" data-rec="${esc(item.record_id)}">驳回</button>
        <button type="button" class="btn sm ${decision && decision.status === "pending_review" ? "primary" : ""}" data-decide="pending_review" data-rec="${esc(item.record_id)}">退回补证</button>
        <input class="review-note" data-note="${esc(item.record_id)}" value="${esc(decision ? decision.note : "")}" placeholder="复核意见（驳回 / 退回补证必填）">
      </div>
      <div class="review-decision ${decision ? decision.status : ""}" data-decision="${esc(item.record_id)}">${decision ? `本地记录：${esc(decisionLabel[0])} · ${esc(decision.reviewer)}${decision.note ? " · " + esc(decision.note) : ""}` : ""}</div>
    </div>`;
  }
  function reviewHTML(p) {
    const queue = p.review_queue || [];
    const decided = queue.filter(item => decisionOf(item.record_id)).length;
    return `<div class="review-box" id="review-box">
      <div class="review-head">
        <b>待复核队列</b><span class="tag amber">${queue.length} 条待复核</span>${decided ? `<span class="tag ok">本地已记录 ${decided} 条</span>` : ""}
        <span class="spacer"></span>
        <div class="reviewer-bar"><label>复核人 <input data-reviewer value="${esc(state.reviewer)}" placeholder="姓名"></label><button type="button" class="btn sm primary" data-review-export="${esc(p.id)}">导出复核决定</button></div>
      </div>
      <div class="review-hint">决定先保存在本机浏览器，页面上的“待复核”计数不会立即变化；点“导出复核决定”下载 JSON，由后端执行 <code>bdc review apply 记录文件 决定文件 --out 输出目录</code>，重新生成后状态才会写入记录。通过 / 驳回 / 退回补证分别写入记录级 review_status。</div>
      ${queue.length ? `<div class="review-list">${queue.map(reviewItemHTML).join("")}</div>` : `<div class="review-empty">这篇论文没有待复核记录。</div>`}
    </div>`;
  }
  function exportReview(p) {
    const queue = p.review_queue || [];
    const decisions = queue.map(item => decisionOf(item.record_id)).filter(Boolean);
    if (!decisions.length) { window.alert("还没有本地复核决定。"); return; }
    if (!String(state.reviewer || "").trim()) { window.alert("请先填写复核人姓名。"); const input = $("[data-reviewer]"); if (input) input.focus(); return; }
    const invalid = queue.filter(item => {
      const d = decisionOf(item.record_id);
      return d && d.status !== "expert_approved" && !String(d.note || "").trim();
    });
    if (invalid.length) { window.alert("驳回 / 退回补证的记录必须填写复核意见。"); return; }
    const payload = {
      review_format: 1,
      reviewer: { name: state.reviewer.trim(), role: "expert" },
      created_at: new Date().toISOString(),
      paper: { id: p.id, title: p.title, doi: p.doi, run_id: p.run_id },
      decisions: queue.map(item => {
        const d = decisionOf(item.record_id);
        return d ? { record_id: item.record_id, status: d.status, note: d.note } : null;
      }).filter(Boolean),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${String(p.title || "paper").slice(0, 40).replace(/[^\w\u4e00-\u9fa5-]+/g, "_")}.review_decisions.json`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function renderReviewModal() {
    const p = currentPaper();
    if (!p) return;
    const queue = p.review_queue || [];
    const decided = queue.filter(item => decisionOf(item.record_id)).length;
    $("#review-modal-title").textContent = "人工复核";
    $("#review-modal-sub").textContent = `${p.title || ""} · ${queue.length} 条待复核${decided ? ` · 本地已记录 ${decided} 条` : ""}`;
    $("#review-modal-body").innerHTML = reviewHTML(p);
  }
  function openReview() {
    const p = currentPaper();
    if (!p) return;
    renderReviewModal();
    $("#review-modal").hidden = false;
    document.body.classList.add("modal-open");
    setTimeout(() => $("[data-close-review]").focus(), 0);
  }
  function closeReview() {
    const modal = $("#review-modal");
    if (modal) modal.hidden = true;
    document.body.classList.remove("modal-open");
  }
  function handleReviewClick(ev) {
    if (ev.target.closest("[data-close-review]")) { closeReview(); return; }
    const decide = ev.target.closest("[data-decide]");
    if (decide) {
      const item = decide.closest("[data-review-item]");
      const recordId = decide.dataset.rec;
      const status = decide.dataset.decide;
      const noteInput = item ? item.querySelector("[data-note]") : null;
      const note = noteInput ? noteInput.value : "";
      if (status !== "expert_approved" && !String(note || "").trim()) {
        window.alert("驳回 / 退回补证需要填写复核意见。");
        if (noteInput) noteInput.focus();
        return;
      }
      saveReviewDecision(recordId, status, note);
      renderReviewModal();
      return;
    }
    const exportBtn = ev.target.closest("[data-review-export]");
    if (exportBtn) { const p = currentPaper(); if (p) exportReview(p); }
  }

  // ------------------------------------------------------------------ paper mode
  function renderPaperList() {
    const host = $("#paper-list");
    const papers = DATA.papers || [];
    $("#paper-count").textContent = `${papers.length} 篇`;
    if (!papers.length) { host.innerHTML = `<div class="empty" style="padding:20px 10px"><p>还没有运行记录。</p></div>`; return; }
    host.innerHTML = papers.map(p => {
      const hidden = Object.values(p.hidden || {}).reduce((a, b) => a + b, 0);
      const pkg = p.package || {};
      const pkgStatus = PACKAGE[pkg.status] || [pkg.status || "未评估", ""];
      return `<button type="button" class="paper-item" data-paper="${esc(p.id)}" aria-selected="${state.paper === p.id}">
        <b>${esc(p.title || "未命名论文")}</b>
        <span class="m">${p.year ? esc(p.year) : ""}${p.doi ? `<span class="mono">${esc(p.doi)}</span>` : ""}<span>${fmt((p.edges || []).length)} 条关系</span>${hidden ? `<span style="color:var(--amber)">隐去 ${hidden}</span>` : ""}</span>
        <span class="badges"><span class="tag ${pkgStatus[1]}">文章包 ${esc(pkgStatus[0])}</span>${p.pending ? `<span class="tag amber">${p.pending} 待复核</span>` : ""}</span>
      </button>`;
    }).join("");
    host.querySelectorAll("[data-paper]").forEach(btn => btn.addEventListener("click", () => {
      state.paper = btn.dataset.paper; state.edge = null; state.node = null; closeReview(); renderAll();
    }));
  }

  function packageHTML(p) {
    const pkg = p.package || {};
    const status = PACKAGE[pkg.status] || [pkg.status || "未评估", ""];
    const figures = pkg.figures || {};
    const tables = pkg.tables || {};
    const supp = pkg.supplement || {};
    const main = pkg.main_text || {};
    const cell = (k, v) => `<div class="pkg-cell"><div class="k">${esc(k)}</div><div class="v">${v}</div></div>`;
    const figCount = (figures.cited || []).length + (figures.supplement_cited || []).length;
    const figFound = (figures.detected || []).length + (figures.supplement_detected || []).length;
    const tabCount = (tables.cited || []).length + (tables.supplement_cited || []).length;
    const tabFound = (tables.detected || []).length + (tables.supplement_detected || []).length;
    return `<div class="pkg">
      <div class="pkg-head"><b>文章包</b><span class="tag ${status[1]}">${esc(status[0])}</span>${(p.supplements || []).length ? `<span class="tag info">${esc(p.supplements.join("、"))}</span>` : `<span class="tag">无 Supplement</span>`}</div>
      <div class="pkg-grid">
        ${cell("正文", main.present ? `${fmt(main.page_count)} 页 · ${fmt(main.text_pages)} 页有文本` : "未提供")}
        ${cell("图", figCount ? `引用 ${figCount} · 检出 ${figFound}` : "未引用")}
        ${cell("表", tabCount ? `引用 ${tabCount} · 检出 ${tabFound}` : "未引用")}
        ${cell("Supplement", (supp.parts || []).length ? (supp.parts || []).map(x => `${x.part} · ${fmt(x.text_pages)}/${fmt(x.page_count)} 页有文本`).join("<br>") : "未提供")}
        ${cell("数据/代码", (pkg.data_code || {}).status === "present" ? "已检测到声明" : "未检测到（建议项）")}
        ${cell("引用/许可", (pkg.license || {}).status === "present" ? ((pkg.license || {}).values || []).join("、") : "未检测到（建议项）")}
      </div>
      ${(pkg.missing || []).length ? `<ul class="pkg-notes" style="color:var(--amber)">${pkg.missing.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
      ${(pkg.notes || []).length ? `<ul class="pkg-notes">${pkg.notes.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    </div>`;
  }

  const STAT_LABEL = { lod_score: "LOD", pve_percent: "PVE", p_value: "P 值", confidence_interval: "95% CI", effect_estimate: "效应", effect_direction: "方向", sample_size: "样本", environment_count: "环境", population_type: "群体类型", chromosome: "染色体", locus_interval_start_bp: "区间起", locus_interval_end_bp: "区间止", genome_assembly: "参考基因组", relation_evidence_type: "证据类型", claim_strength: "结论强度", validation_status: "验证" };
  const VALUE_LABEL = {
    validation_status: { candidate: "候选", experiment_reported: "已报验证实验" },
    claim_strength: { associational: "相关", structural: "结构", descriptive: "描述", causal_supported: "因果（有验证）", causal_expression_supported: "因果（表达支持）", causal_statistical_only: "因果（仅统计）", causal_unverified: "因果（未验证）" },
    effect_direction: { increase: "增加", decrease: "降低", increased: "增加", decreased: "降低", up: "上调", down: "下调" },
    relation_evidence_type: { statistical_mapping: "统计定位", expression_support: "表达支持", functional_validation: "功能验证", genetic_interaction: "遗传互作", biochemical_assay: "生化实验", localization_imaging: "定位成像", pharmacological_perturbation: "药理扰动" },
  };
  function statValue(key, value) { const map = VALUE_LABEL[key]; return map && map[value] ? map[value] : value; }
  function statsHTML(stats) {
    const rows = [];
    for (const [key, label] of Object.entries(STAT_LABEL)) {
      let v = (stats || {})[key];
      if (v == null || v === "" || (Array.isArray(v) && !v.length)) continue;
      if (key === "pve_percent" && typeof v === "number") v = `${v}%`;
      else if (key === "pve_percent" && typeof v === "string" && !v.includes("%")) v = `${v}%`;
      if (key === "effect_estimate" && stats.effect_unit) v = `${v} ${stats.effect_unit}`;
      if (key === "locus_interval_start_bp" || key === "locus_interval_end_bp") v = `${v} bp`;
      v = statValue(key, v);
      rows.push(`<div class="stat"><div class="k">${esc(label)}</div><div class="v">${esc(v)}</div></div>`);
    }
    return rows.length ? `<div class="stats">${rows.join("")}</div>` : "";
  }
  function locatorHTML(node) {
    const tags = [];
    if (node.section) tags.push(`<span class="tag">${esc(node.section)}</span>`);
    if (node.page != null) tags.push(`<span class="tag">p.${esc(node.page)}</span>`);
    if (node.table_figure) tags.push(`<span class="tag gold">${esc(node.table_figure)}</span>`);
    if (node.part) tags.push(`<span class="tag info">${esc(node.part)}</span>`);
    return `<div class="locator">${tags.join("") || `<span class="tag amber">段落/图表未定位</span>`}</div>`;
  }
  function nodeCard(node) {
    if (!node) return "";
    return `<div class="chain-node">
      <div class="chain-top"><span class="tag brand">${esc(node.kind_label || "记录")}</span>${node.role ? `<span class="tag">${esc(node.role)}</span>` : ""}</div>
      <div class="chain-text">${esc(node.text || "")}</div>
      ${node.quote && node.quote !== node.text ? `<blockquote>${esc(node.quote)}</blockquote>` : ""}
      ${locatorHTML(node)}
      ${statsHTML(node.stats || {})}
    </div>`;
  }
  function methodsHTML(dataNode) {
    const methods = (dataNode.children || []).filter(c => c.link_role === "method");
    if (!methods.length) return `<div class="chain-missing">这个结果未链接到实验/方法记录。</div>`;
    return `<div class="chain-methods">${methods.map(m => `<div class="chain-method">
      <div class="mh"><span class="tag brand">实验/方法</span><span class="mt">${esc(m.method_name || m.text || "方法记录")}</span>${m.software ? `<span class="tag">${esc(m.software)}</span>` : ""}</div>
      ${m.quote ? `<div class="mq">${esc(m.quote)}</div>` : ""}
      ${(m.materials || []).length ? `<div class="mq">材料：${esc((m.materials || []).join("、"))}</div>` : ""}
      ${(m.treatment || []).length ? `<div class="mq">处理：${esc((m.treatment || []).join("、"))}</div>` : ""}
      ${(m.indicators || []).length ? `<div class="mq">指标：${esc((m.indicators || []).join("、"))}</div>` : ""}
      ${locatorHTML(m)}
    </div>`).join("")}</div>`;
  }
  function chainHTML(ev) {
    const chain = ev.chain;
    if (!chain || !chain.anchor) {
      return `<div class="chain"><div class="chain-step"><div class="step-k">原文证据</div><div class="chain-node"><blockquote>${esc(ev.quote || "无引文")}</blockquote>${locatorHTML(ev)}${statsHTML(ev.stats || {})}</div></div></div>`;
    }
    const anchor = chain.anchor;
    const dataNodes = (chain.nodes || []).filter(n => n.depth === 1 && n.link_role === "evidence");
    const directMethods = (chain.nodes || []).filter(n => n.depth === 1 && n.link_role === "method");
    const missing = (chain.missing || []).filter(Boolean);
    return `<div class="chain">
      <div class="chain-step"><div class="step-k">结论 / 关系</div>${nodeCard(anchor)}</div>
      <div class="chain-down">↓ 依据</div>
      ${dataNodes.length ? dataNodes.map(d => `<div class="chain-step"><div class="step-k">数据 / 结果</div>${nodeCard(d)}${methodsHTML(d)}</div>`).join("") : `<div class="chain-missing">未链接到数据/结果记录。</div>`}
      ${directMethods.length ? `<div class="chain-step"><div class="step-k">直接关联的实验 / 方法</div>${directMethods.map(nodeCard).join("")}</div>` : ""}
      ${(chain.complete || chain.applicable === false) ? "" : `<div class="chain-missing">${esc(missing.join("；") || "证据链不完整")}</div>`}
    </div>`;
  }
  function relCard(edge) {
    const hedges = [...new Set((edge.evidence || []).map(ev => ev.hedge).filter(Boolean))];
    return `<article class="rel-card">
      <div class="rel-card-head">
        <div class="rel-line">${typed(edge.subject_label, edge.subject_type, edge.subject_layer)}<span class="pred">— ${esc(edge.predicate)} —</span>${typed(edge.object_label, edge.object_type, edge.object_layer)}</div>
        <div class="rel-badges">${pairTag(edge.pair)}${natureTag(edge.relation_nature)}${edge.predicate_code ? `<span class="tag">${esc(edge.predicate_code)}</span>` : `<span class="tag amber">谓语未编码</span>`}${(edge.evidence || []).some(ev => ev.assertion_mode === "hedged") ? `<span class="tag amber">限定表述</span>` : ""}${hedges.map(h => `<span class="tag">“${esc(h)}”</span>`).join("")}${confidenceTag(edge.confidence)}${chainTag(edge)}</div>
        ${confidenceBasis(edge)}
      </div>
      <div class="chain-wrap">${(edge.evidence || []).map((ev, i) => `${i ? `<div style="border-top:1px dashed var(--line);margin:12px 0"></div>` : ""}${chainHTML(ev)}`).join("")}</div>
    </article>`;
  }
  function renderPaperView() {
    const host = $("#paper-main");
    const p = currentPaper();
    if (!p) { host.innerHTML = `<div class="card empty-paper"><div class="empty"><h3>选择一篇论文</h3><p>左侧列出当前有运行记录的论文。</p></div></div>`; return; }
    const edges = visiblePaperEdges();
    const hidden = p.hidden || {};
    const hiddenTotal = Object.values(hidden).reduce((a, b) => a + b, 0);
    host.innerHTML = `<div class="card">
      <div class="paper-head">
        <div class="rel-badges" style="margin:0 0 8px"><span class="tag brand">论文</span>${p.pending ? `<button type="button" class="btn sm amber" data-open-review>人工复核（${p.pending}）</button>` : `<span class="tag ok">无待复核</span>`}${p.source_complete === true ? `<span class="tag ok">来源完整</span>` : p.source_complete === false ? `<span class="tag amber">来源不完整</span>` : `<span class="tag">来源状态未报告</span>`}</div>
        <h2>${esc(p.title || "未命名论文")}</h2>
        <div class="meta">${p.year ? `<span>${esc(p.year)}</span>` : ""}${p.doi ? `<span class="mono">${esc(p.doi)}</span>` : ""}<span>${fmt(p.records)} 条记录</span><span>${fmt(edges.length)} / ${fmt((p.edges || []).length)} 条三元关系</span></div>
      </div>
      <div class="paper-body">
        ${packageHTML(p)}
        <div class="section-head plain" style="margin-bottom:12px"><h3 class="sub" style="margin:0">三元关系与证据链</h3><p class="small muted" style="margin-top:4px">只保留表型—基因—种群；每条关系从结论走到结果，再走到实验/方法。缺少链接时直接标出。</p></div>
        ${edges.length ? edges.map(relCard).join("") : `<div class="empty"><h3>没有匹配的三元关系</h3><p>这篇论文的三元关系可能被关键词或类型筛选掉了；也可以展开全库大网查看。</p></div>`}
        <details class="paper-hidden" ${hiddenTotal ? "" : "hidden"}>
          <summary>本篇隐去的其他关系（${hiddenTotal} 条）</summary>
          <div class="body">${Object.entries(hidden).map(([k, v]) => `${esc(k)}：${v} 条`).join("<br>")}${(p.hidden_samples || []).map(s => `<br>示例：${esc(s.subject)} — ${esc(s.predicate || "")} — ${esc(s.object)}`).join("")}</div>
        </details>
      </div>
    </div>`;
  }

  // ------------------------------------------------------------------ network mode
  function renderNet() {
    const svg = $("#net");
    const edges = visibleNetworkEdges();
    const ids = new Set();
    edges.forEach(e => { ids.add(e.subject); ids.add(e.object); });
    const nodes = (DATA.nodes || []).filter(n => ids.has(n.id));
    const W = 1200, H = 640;
    const lanes = { trait: 180, gene: 600, population: 1020 };
    const positions = {};
    const byLayer = { trait: [], gene: [], population: [] };
    nodes.forEach(n => { if (byLayer[n.layer]) byLayer[n.layer].push(n); });
    const top = 120, bottom = 570;
    LAYERS.forEach(layer => {
      const list = byLayer[layer].slice().sort((a, b) => (b.degree - a.degree) || String(a.label).localeCompare(String(b.label), "zh-CN"));
      list.forEach((n, i) => {
        const y = top + (bottom - top) * (i + 1) / (list.length + 1);
        positions[n.id] = { x: lanes[layer], y, r: Math.min(20, 10 + Math.min(n.degree || 0, 8) * 1.2) };
      });
    });
    const laneTitle = { trait: "表型", gene: "基因层 · 含 QTL / QTN", population: "种群" };
    let out = `<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#78827c"/></marker></defs>`;
    LAYERS.forEach(layer => {
      out += `<rect class="lane" x="${lanes[layer] - 150}" y="78" width="300" height="512" rx="18"/>`;
      out += `<text class="lane-title" x="${lanes[layer]}" y="52" text-anchor="middle">${esc(laneTitle[layer])}</text>`;
      if (!byLayer[layer].length) out += `<text class="lane-empty" x="${lanes[layer]}" y="340" text-anchor="middle">暂无节点</text>`;
    });
    edges.forEach(e => {
      const a = positions[e.subject], b = positions[e.object];
      if (!a || !b) return;
      const mx = (a.x + b.x) / 2;
      const path = `M ${a.x} ${a.y} C ${mx} ${a.y}, ${mx} ${b.y}, ${b.x} ${b.y}`;
      const nature = e.relation_nature || "unknown";
      const width = 1.5 + Math.min(e.evidence_count || 1, 5) * 0.55;
      const cls = ["edge", `nature-${nature}`, e.predicate_code ? "" : "unencoded", state.edge === e.id ? "sel" : "", state.node && e.subject !== state.node && e.object !== state.node ? "dim" : ""].filter(Boolean).join(" ");
      out += `<path class="${cls}" d="${path}" data-edge="${esc(e.id)}" stroke-width="${width}" marker-end="url(#arrow)"><title>${esc(e.subject_label)} — ${esc(e.predicate)} — ${esc(e.object_label)} · ${fmt(e.evidence_count)} 条证据</title></path>`;
      if (e.evidence_count > 1) {
        const x = (a.x + b.x) / 2, y = (a.y + b.y) / 2;
        out += `<g class="edge-badge" data-edge="${esc(e.id)}"><circle class="edge-count-bg" cx="${x}" cy="${y}" r="9"/><text class="edge-count" x="${x}" y="${y + 3.5}" text-anchor="middle">${e.evidence_count}</text></g>`;
      }
    });
    nodes.forEach(n => {
      const p = positions[n.id];
      if (!p) return;
      const right = n.layer === "population";
      const tx = right ? p.x - p.r - 8 : p.x + p.r + 8;
      const anchor = right ? "end" : "start";
      const cls = ["node", LAYER_CLASS[n.layer], state.node === n.id ? "sel" : "", state.node && state.node !== n.id && !edges.some(e => (e.subject === state.node && e.object === n.id) || (e.object === state.node && e.subject === n.id)) ? "dim" : ""].filter(Boolean).join(" ");
      const label = n.label.length > 30 ? n.label.slice(0, 29) + "…" : n.label;
      out += `<g class="${cls}" data-node="${esc(n.id)}" tabindex="0" role="button" aria-label="${esc(n.label)}，${esc(n.kind_label)}">
        <circle class="halo" cx="${p.x}" cy="${p.y}" r="${p.r + 4}"/>
        <circle class="dot" cx="${p.x}" cy="${p.y}" r="${p.r}"/>
        <text class="label" x="${tx}" y="${p.y - 1}" text-anchor="${anchor}">${esc(label)}</text>
        <text class="kind" x="${tx}" y="${p.y + 13}" text-anchor="${anchor}">${esc(n.kind_label)} · ${fmt(n.evidence)} 条</text>
        <title>${esc(n.label)} · ${esc(n.kind_label)} · ${fmt(n.evidence)} 条证据</title>
      </g>`;
    });
    if (!edges.length) out += `<text class="lane-empty" x="600" y="600" text-anchor="middle">没有匹配的三元关系。换一个关键词，或查看下方“未展示的其他关系”。</text>`;
    svg.innerHTML = out;
  }

  function renderEvidence() {
    const host = $("#ev-card");
    const e = state.edge ? edgeById(state.edge) : null;
    if (!e) {
      host.innerHTML = `<div class="ev-head"><div class="ev-pair">证据卡</div><h2 class="ev-title">选择一条关系</h2><p class="small muted" style="margin-top:8px">点左侧网络中的一条边，或下方关系清单中的一行。</p></div><div class="ev-empty">证据卡会显示：论文、完整证据链、原文、章节 / 页码 / 图或表 / 补充材料、统计量、审核状态与来源完整性。</div>`;
      return;
    }
    const reviews = reviewOf(e);
    const head = `<div class="ev-head">
      <div class="ev-pair">${pairTag(e.pair)}${natureTag(e.relation_nature)}${e.predicate_code ? `<span class="tag">${esc(e.predicate_code)}</span>` : `<span class="tag amber">谓语未编码</span>`}${confidenceTag(e.confidence)}${chainTag(e)}</div>
      <h2 class="ev-title">${typed(e.subject_label, e.subject_type, e.subject_layer)} <span class="pred">— ${esc(e.predicate)} —</span> ${typed(e.object_label, e.object_type, e.object_layer)}</h2>
      <div class="ev-badges">${reviews.map(reviewTag).join("")}<span class="tag">${fmt(e.paper_count)} 篇论文</span><span class="tag">${fmt(e.evidence_count)} 条证据</span></div>
      ${confidenceBasis(e)}
    </div>`;
    const body = `<div class="ev-body">${(e.evidence || []).map((ev, i) => `<div class="ev-item">${i ? "" : ""}${chainHTML(ev)}</div>`).join("")}</div>`;
    host.innerHTML = head + body;
  }

  function renderTable() {
    const edges = visibleNetworkEdges();
    const body = $("#rel-table tbody");
    if (!edges.length) {
      body.innerHTML = `<tr><td colspan="7"><div class="empty"><h3>没有匹配的关系</h3><p>试试换一个性状、基因或种群名称；其他关系在本期视图中不展示。</p></div></td></tr>`;
      return;
    }
    body.innerHTML = edges.map(e => {
      const reviews = reviewOf(e);
      return `<tr data-edge="${esc(e.id)}" class="${state.edge === e.id ? "sel" : ""}" tabindex="0">
        <td><div class="rel-line">${typed(e.subject_label, e.subject_type, e.subject_layer)}<span class="pred">— ${esc(e.predicate)} —</span>${typed(e.object_label, e.object_type, e.object_layer)}</div><div class="rel-sub">${esc(e.pair)}${e.predicate_code ? ` · ${esc(e.predicate_code)}` : " · 谓语未编码"}</div></td>
        <td class="num">${fmt(e.evidence_count)}</td>
        <td class="num">${fmt(e.paper_count)}</td>
        <td>${confidenceTag(e.confidence)}</td>
        <td>${chainTag(e)}</td>
        <td>${reviews.length ? reviews.map(reviewTag).join(" ") : `<span class="muted xs">未标记</span>`}</td>
        <td><button type="button" class="btn sm" data-open="${esc(e.id)}">查看证据</button></td>
      </tr>`;
    }).join("");
    body.querySelectorAll("tr[data-edge]").forEach(tr => {
      tr.addEventListener("click", ev => { if (ev.target.closest("[data-open]")) return; selectEdge(tr.dataset.edge, true); });
      tr.addEventListener("keydown", ev => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); selectEdge(tr.dataset.edge, true); } });
    });
    body.querySelectorAll("[data-open]").forEach(btn => btn.addEventListener("click", () => selectEdge(btn.dataset.open, true)));
  }

  function renderHidden() {
    const h = (DATA.summary || {}).hidden_by_reason || {};
    const total = (DATA.summary || {}).hidden || 0;
    $("#hidden-summary").textContent = `本期未展示的其他关系（${total} 条）`;
    const reasons = Object.entries(h).sort((a, b) => b[1] - a[1]);
    const samples = DATA.hidden_samples || [];
    const rows = reasons.map(([k, v]) => `<tr><td>${esc(k)}</td><td class="num">${fmt(v)}</td></tr>`).join("");
    const sampleRows = samples.map(s => `<tr><td>${esc(s.paper || "")}</td><td>${esc(s.subject)} — ${esc(s.predicate || "")} — ${esc(s.object)}</td><td>${esc(s.reason)}</td></tr>`).join("");
    $("#hidden-body").innerHTML = `<p style="margin:0 0 10px">后端仍保留这些关系，只是本视图只展示表型—基因—种群。这里列出被隐藏的条数与原因，避免把“没显示”误以为“没抽取”。</p>
      <table><thead><tr><th>原因</th><th>条数</th></tr></thead><tbody>${rows || `<tr><td colspan="2" class="muted">没有隐藏的关系</td></tr>`}</tbody></table>
      ${sampleRows ? `<p class="xs muted" style="margin:12px 0 6px">示例</p><table><thead><tr><th>论文</th><th>关系</th><th>原因</th></tr></thead><tbody>${sampleRows}</tbody></table>` : ""}`;
    $("#hidden-box").hidden = total === 0;
  }
  function renderPapers() {
    const host = $("#paper-grid");
    const papers = DATA.papers || [];
    if (!papers.length) { host.innerHTML = `<div class="empty"><h3>还没有运行记录</h3><p>先运行一次抽取，再生成这个视图。</p></div>`; return; }
    host.innerHTML = papers.map(p => {
      const pkg = p.package || {};
      const status = PACKAGE[pkg.status] || [pkg.status || "未评估", ""];
      return `<div class="paper">
        <b>${esc(p.title || "未命名论文")}</b>
        <div class="m">${p.year ? `<span>${esc(p.year)}</span>` : ""}${p.doi ? `<span class="mono">${esc(p.doi)}</span>` : ""}<span>${fmt(p.records)} 条记录</span>${p.pending ? `<span class="tag amber">${p.pending} 待复核</span>` : ""}</div>
        <div class="m"><span class="tag ${status[1]}">文章包 ${esc(status[0])}</span>${fmt((p.edges || []).length)} 条三元关系${(p.supplements || []).length ? `<span class="tag info">Supplement ${esc((p.supplements || []).join("、"))}</span>` : ""}</div>
        <div class="links">${p.pdf_url ? `<a class="btn sm" href="${esc(p.pdf_url)}" target="_blank" rel="noopener">打开 PDF</a>` : ""}<button type="button" class="btn sm" data-goto-paper="${esc(p.id)}">逐篇查看</button></div>
      </div>`;
    }).join("");
    host.querySelectorAll("[data-goto-paper]").forEach(btn => btn.addEventListener("click", () => {
      state.paper = btn.dataset.gotoPaper; setMode("paper");
    }));
  }

  // ------------------------------------------------------------------ state / events
  function selectEdge(id, scroll) {
    state.edge = id; state.node = null;
    renderNet(); renderTable(); renderEvidence();
    if (scroll && $("#ev-card").scrollIntoView) $("#ev-card").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
  function selectNode(id) {
    state.node = state.node === id ? null : id; state.edge = null;
    renderNet(); renderTable(); renderEvidence();
  }
  function setMode(mode) {
    closeReview();
    state.mode = mode; state.edge = null; state.node = null;
    if (mode === "network") {
      const first = visibleNetworkEdges()[0];
      if (first) state.edge = first.id;
    }
    renderAll();
  }
  function renderAll() {
    renderMode(); renderMeta(); renderChips();
    if (state.mode === "paper") { renderPaperList(); renderPaperView(); }
    else {
      if (state.edge && !visibleNetworkEdges().some(e => e.id === state.edge)) state.edge = null;
      renderNet(); renderTable(); renderEvidence(); renderHidden(); renderPapers();
    }
  }

  document.querySelectorAll("[data-mode]").forEach(btn => btn.addEventListener("click", () => setMode(btn.dataset.mode)));
  $("#paper-main").addEventListener("click", ev => {
    if (ev.target.closest("[data-open-review]")) { openReview(); }
  });
  $("#review-modal").addEventListener("click", handleReviewClick);
  $("#review-modal").addEventListener("input", ev => {
    if (ev.target.matches("[data-reviewer]")) {
      state.reviewer = ev.target.value;
      store.set(REVIEWER_KEY, state.reviewer);
    }
  });
  document.addEventListener("keydown", ev => {
    if (ev.key === "Escape" && !$("#review-modal").hidden) closeReview();
  });
  $("#net").addEventListener("click", ev => {
    const edgeEl = ev.target.closest("[data-edge]");
    if (edgeEl) { selectEdge(edgeEl.dataset.edge, true); return; }
    const nodeEl = ev.target.closest("[data-node]");
    if (nodeEl) { selectNode(nodeEl.dataset.node); return; }
    state.node = null; state.edge = null; renderNet(); renderTable(); renderEvidence();
  });
  $("#net").addEventListener("keydown", ev => {
    if (ev.key !== "Enter" && ev.key !== " ") return;
    const nodeEl = ev.target.closest("[data-node]");
    if (nodeEl) { ev.preventDefault(); selectNode(nodeEl.dataset.node); }
  });
  let timer = 0;
  $("#q").addEventListener("input", ev => {
    const value = ev.target.value.trim();
    $("#q-clear").hidden = !value;
    clearTimeout(timer);
    timer = setTimeout(() => { state.q = value.toLowerCase(); state.node = null; renderAll(); }, 120);
  });
  $("#q-clear").addEventListener("click", () => { $("#q").value = ""; $("#q-clear").hidden = true; state.q = ""; renderAll(); $("#q").focus(); });

  $("#generated-at").textContent = DATA.generated_at ? new Date(DATA.generated_at).toLocaleString("zh-CN") : "—";
  $("#contract-version").textContent = DATA.contract_version || "—";
  renderAll();
})();
