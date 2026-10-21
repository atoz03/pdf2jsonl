// pdf2jsonl site kit: shell, language and theme, and the helpers every page shares (inlined by scripts/site_shell.py).
"use strict";
const K = (() => {
  const DATA = JSON.parse(document.getElementById("site-data").textContent);
  const SITE = DATA.site || {};
  const store = { get: k => { try { return localStorage.getItem("pdf2jsonl." + k); } catch { return null; } },
                  set: (k, v) => { try { localStorage.setItem("pdf2jsonl." + k, v); } catch { /* private mode */ } } };
  let lang = store.get("lang") === "en" ? "en" : "zh";
  const T = (zh, en) => (lang === "en" && en != null ? en : zh);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const fmt = n => typeof n === "number" ? n.toLocaleString(lang === "en" ? "en-US" : "zh-CN") : String(n ?? "—");
  const count = (arr, fn) => arr.reduce((n, x) => n + (fn(x) ? 1 : 0), 0);
  const short = v => typeof v === "string" ? v : JSON.stringify(v);
  const clip = (s, n) => { s = String(s ?? ""); return s.length > n ? s.slice(0, n - 1) + "…" : s; };

  // ---------------------------------------------------------------- icons (24px stroke)
  const ICONS = {
    home: "M3 10.5 12 3l9 7.5M5 9.5V21h14V9.5M9.5 21v-6h5v6",
    flow: "M4 5h6v5H4zM14 14h6v5h-6zM7 10v4a2 2 0 0 0 2 2h5M17 14V8a2 2 0 0 0-2-2h-5",
    play: "M7 4.5v15l12-7.5z",
    pause: "M7 5h3.5v14H7zM13.5 5H17v14h-3.5z",
    layers: "M12 3 2.5 8 12 13l9.5-5zM2.5 12.5 12 17.5l9.5-5M2.5 16.5 12 21.5l9.5-5",
    library: "M4 4h4v16H4zM10 4h4v16h-4zM16.5 4.5l3.5 1-3.5 15-3.5-1z",
    import: "M12 3v12M7 10l5 5 5-5M4 15v5h16v-5",
    download: "M12 3v12M7 10l5 5 5-5M4 15v5h16v-5",
    table: "M3 5h18v14H3zM3 10h18M3 14.5h18M9 5v14",
    book: "M4 4.5A1.5 1.5 0 0 1 5.5 3H19v15H5.5A1.5 1.5 0 0 0 4 19.5zM4 19.5A1.5 1.5 0 0 0 5.5 21H19v-3M8 7h7M8 11h5",
    search: "M20 20l-4.6-4.6M17 10.5a6.5 6.5 0 1 1-13 0 6.5 6.5 0 0 1 13 0z",
    github: "M9 19c-4.5 1.4-4.5-2.3-6.3-2.8m12.6 5.6v-3.5a3 3 0 0 0-.9-2.4c2.9-.3 6-1.4 6-6.4a5 5 0 0 0-1.4-3.5 4.6 4.6 0 0 0-.1-3.4s-1.1-.4-3.6 1.3a12.4 12.4 0 0 0-6.5 0C6.3 2.2 5.2 2.6 5.2 2.6a4.6 4.6 0 0 0-.1 3.4 5 5 0 0 0-1.4 3.5c0 5 3.1 6.1 6 6.4a3 3 0 0 0-.9 2.4v3.5",
    sun: "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 1.5v2M12 20.5v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1.5 12h2M20.5 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4",
    moon: "M20.5 14.5A8.5 8.5 0 1 1 9.5 3.5a7 7 0 0 0 11 11z",
    menu: "M4 7h16M4 12h16M4 17h16",
    close: "M6 6l12 12M18 6 6 18",
    arrow: "M5 12h14M13 6l6 6-6 6",
    back: "M19 12H5M11 6l-6 6 6 6",
    check: "M5 12.5l4.5 4.5L19 7.5",
    x: "M7 7l10 10M17 7 7 17",
    alert: "M12 3 2 20.5h20zM12 9.5v5M12 17.5v.5",
    info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v6M12 7.5v.5",
    copy: "M9 9h11v11H9zM5 15H4V4h11v1",
    file: "M6 3h8.5L19 7.5V21H6zM14 3v5h5M9 13h7M9 17h5",
    link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
    graph: "M6 6.5a2.5 2.5 0 1 0 0-.01zM18 5a2.5 2.5 0 1 0 0-.01zM12 19a2.5 2.5 0 1 0 0-.01zM8.3 7.6l2.6 9M15.8 6.3l-6.9 0M16.9 7.4l-3.6 9.3",
    quote: "M5 17c0-5 1.5-8 5-10M14 17c0-5 1.5-8 5-10M5 17h4v-4H5zM14 17h4v-4h-4z",
    wrench: "M14.5 6.5a4 4 0 0 0 5 5L12 19a2.1 2.1 0 0 1-3-3l7.5-7.5a4 4 0 0 0-2-2zM14.5 6.5l3-3",
    shield: "M12 3 4.5 6v6c0 4.5 3.2 7.8 7.5 9 4.3-1.2 7.5-4.5 7.5-9V6zM8.5 12l2.5 2.5 4.5-4.5",
    sparkle: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2 2.2.8-2.2.8L19 22l-.8-2.2-2.2-.8 2.2-.8z",
    tag: "M3 12V4h8l10 10-8 8zM7.5 8a.5.5 0 1 0 0-.01",
    rule: "M4 6h16M4 12h10M4 18h7M17 15l2 2 3.5-3.5",
    clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7.5V12l3 2",
    plus: "M12 5v14M5 12h14",
    leaf: "M5 19c0-8 5-14 15-15-1 10-7 15-15 15zM5 19l7-7",
    external: "M14 4h6v6M20 4l-9 9M18 14v6H4V6h6",
    filter: "M4 5h16l-6 7.5V19l-4 2v-8.5z",
    eye: "M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4.5 20.5c1.2-3.6 4-5.5 7.5-5.5s6.3 1.9 7.5 5.5",
    cpu: "M7 7h10v10H7zM10 10h4v4h-4zM9.5 3v4M14.5 3v4M9.5 17v4M14.5 17v4M3 9.5h4M3 14.5h4M17 9.5h4M17 14.5h4",
  };
  const icon = (name, cls = "i") => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true"><path d="${ICONS[name] || ICONS.file}"/></svg>`;
  const LOGO = `<svg class="logo" viewBox="0 0 36 36" aria-hidden="true"><rect width="36" height="36" rx="10" fill="#0f2a24"/><path d="M12.5 30.5c3.4-6.6 5.6-13.4 6.6-22.5" stroke="#8fd0aa" stroke-width="1.8" fill="none" stroke-linecap="round"/><path d="M15 25.5c-2.6-.6-4.4-2.4-5-5 2.7.3 4.6 2.1 5 5z" fill="#5fae86"/><g fill="#e8b852"><ellipse cx="20.6" cy="8.6" rx="2.1" ry="3.6" transform="rotate(30 20.6 8.6)"/><ellipse cx="16.3" cy="12.2" rx="2.1" ry="3.6" transform="rotate(-32 16.3 12.2)"/><ellipse cx="21.6" cy="14.6" rx="2.1" ry="3.6" transform="rotate(34 21.6 14.6)"/><ellipse cx="15.7" cy="18.2" rx="2" ry="3.4" transform="rotate(-30 15.7 18.2)"/><ellipse cx="20.4" cy="20.6" rx="2" ry="3.3" transform="rotate(36 20.4 20.6)"/></g></svg>`;

  // ---------------------------------------------------------------- pages of the site, in reading order
  const PAGES = [
    { key: "index", href: "index.html", zh: "首页", en: "Home", icon: "home",
      dzh: "从一篇育种论文到可回查的数据：项目全貌", den: "From a breeding paper to traceable data: the whole project" },
    { key: "pipeline", href: "pipeline.html", zh: "管线", en: "Pipeline", icon: "flow",
      dzh: "规范、抽取、核验、组装、校验到下游派生的每一步", den: "Every stage from contract and extraction to checks and downstream outputs" },
    { key: "demo", href: "demo.html", zh: "抽取演示", en: "Walk-through", icon: "play",
      dzh: "一篇合成论文从 PDF 到 JSONL：候选、核验、修复、拒绝与证据链", den: "A synthetic paper from PDF to JSONL: candidates, checks, repairs, a rejection, the evidence chain" },
    { key: "outputs", href: "outputs.html", zh: "下游派生", en: "Outputs", icon: "graph",
      dzh: "同一批记录派生知识图谱、研究流程、语料、问答种子与关系表", den: "One set of records becomes a knowledge graph, a research workflow, a corpus, QA seeds and tables" },
    { key: "papers", href: "papers.html", zh: "论文看板", en: "Papers", icon: "library",
      dzh: "按论文查看 PDF、每次运行的记录、原文证据、语义校验与导出", den: "Every paper with its runs, records, evidence, semantic verification and exports" },
    { key: "importers", href: "importers.html", zh: "存量导入", en: "Importers", icon: "import",
      dzh: "legacy、omics、merged 三种已有格式逐叶映射到同一契约", den: "Three existing formats mapped leaf by leaf into the same contract" },
    { key: "fields", href: "fields.html", zh: "字段目录", en: "Fields", icon: "table",
      dzh: "每个字段的定义、JSON 示例、键角色、服务功能与来源", den: "Every field with its definition, JSON example, key role, functions and origin" },
    { key: "contract", href: "contract.html", zh: "规范", en: "Contract", icon: "book",
      dzh: "功能与键角色、可获得性、记录类型、词表、规则、歧义与版本", den: "Functions and key roles, availability, record kinds, vocabularies, rules, ambiguities and releases" },
  ];
  const pageOf = key => PAGES.find(p => p.key === key);
  const local = (DATA.shell || {}).mode === "local";

  // ---------------------------------------------------------------- shell
  let page = { key: document.body.dataset.page, render: () => {} };
  function header() {
    const links = local
      ? [`<a href="${esc(DATA.shell.self)}" class="active" aria-current="page">${T("论文看板", "Papers")}</a>`,
         ...DATA.shell.links.map(([zh, en, href]) => `<a href="${esc(href)}">${esc(T(zh, en))}</a>`)].join("")
      : PAGES.map(p => `<a href="${p.href}"${p.key === page.key ? ' class="active" aria-current="page"' : ""}>${esc(T(p.zh, p.en))}</a>`).join("");
    const dark = document.documentElement.dataset.theme === "dark";
    return `<div class="wrap">
      <a class="brand" href="${local ? esc(DATA.shell.self) : "index.html"}" aria-label="pdf2jsonl">${LOGO}<span><b>pdf2jsonl</b><small>${T("育种文献数据契约", "breeding-literature records")}</small></span></a>
      <nav class="nav" id="nav" aria-label="${T("站点导航", "Site")}">${links}</nav>
      <div class="top-actions">
        ${SITE.version ? `<span class="ver" title="${T("数据契约版本", "Contract release")}">v${esc(SITE.version)}</span>` : ""}
        <div class="lang" role="group" aria-label="${T("语言", "Language")}"><button type="button" data-lang="zh" aria-pressed="${lang === "zh"}">中</button><button type="button" data-lang="en" aria-pressed="${lang === "en"}">EN</button></div>
        <button type="button" class="icon-btn" id="theme-btn" aria-label="${T("切换深浅色", "Toggle dark mode")}" title="${T("切换深浅色", "Toggle dark mode")}">${icon(dark ? "sun" : "moon")}</button>
        ${SITE.repo ? `<a class="icon-btn" href="${esc(SITE.repo)}" aria-label="GitHub" title="${T("GitHub 仓库", "GitHub repository")}">${icon("github")}</a>` : ""}
        <button type="button" class="icon-btn menu-btn" id="menu-btn" aria-label="${T("菜单", "Menu")}" aria-expanded="false" aria-controls="nav">${icon("menu")}</button>
      </div></div>`;
  }
  function footer() {
    if (local) return `<div class="wrap"><div><a class="brand" href="${esc(DATA.shell.self)}">${LOGO}<span><b>pdf2jsonl</b><small>${T("本地论文看板", "Local paper dashboard")}</small></span></a>
      <p>${T("由 make dashboard 根据仓库内的 PDF 和运行目录生成的快照，不入库。", "A snapshot of the PDFs and run directories in this repository, written by make dashboard; not committed.")}</p></div></div>`;
    const links = keys => keys.map(k => { const p = pageOf(k); return `<a href="${p.href}">${esc(T(p.zh, p.en))}</a>`; }).join("");
    return `<div class="wrap">
      <div><a class="brand" href="index.html">${LOGO}<span><b>pdf2jsonl</b><small>${esc(SITE.name || "")}</small></span></a>
        <p>${T(`由数据契约 ${esc(SITE.version)} 的发布版本与仓库内示例生成（scripts/make_site.py）。示例论文与数据均为合成数据。`,
              `Generated from release ${esc(SITE.version)} of the contract and the checked-in examples by scripts/make_site.py. All example papers and data are synthetic.`)}</p></div>
      <div><h4>${T("了解", "Understand")}</h4>${links(["index", "pipeline", "demo", "outputs"])}</div>
      <div><h4>${T("数据", "Data")}</h4>${links(["papers", "importers"])}</div>
      <div><h4>${T("参考", "Reference")}</h4>${links(["fields", "contract"])}${SITE.repo ? `<a href="${esc(SITE.repo)}">GitHub ↗</a>` : ""}</div>
    </div>`;
  }
  function nextCard() {
    if (local) return "";
    const i = PAGES.findIndex(p => p.key === page.key);
    if (i < 0) return "";
    const next = PAGES[(i + 1) % PAGES.length];
    return `<div class="next wrap"><a href="${next.href}"><span><small>${i + 1 === PAGES.length ? T("回到起点", "Back to the start") : T("下一页", "Next")}</small><b>${esc(T(next.zh, next.en))}</b><span class="d">${esc(T(next.dzh, next.den))}</span></span><span class="go">${icon("arrow")}</span></a></div>`;
  }
  function renderShell() {
    document.documentElement.lang = lang === "en" ? "en" : "zh-CN";
    const top = $("#top"), foot = $("#foot");
    top.className = "top";
    top.innerHTML = header();
    foot.className = "foot";
    foot.innerHTML = footer();
    $("#next-slot")?.remove();
    const slot = document.createElement("div");
    slot.id = "next-slot";
    slot.innerHTML = nextCard();
    $("#main").after(slot);
    $$("[data-lang]", top).forEach(b => b.addEventListener("click", () => setLang(b.dataset.lang)));
    $("#theme-btn").addEventListener("click", () => {
      const t = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = t; store.set("theme", t);
      $("#theme-btn").innerHTML = icon(t === "dark" ? "sun" : "moon");
      document.dispatchEvent(new CustomEvent("themechange"));
    });
    $("#menu-btn").addEventListener("click", () => {
      const open = top.classList.toggle("open");
      $("#menu-btn").setAttribute("aria-expanded", String(open));
      $("#menu-btn").innerHTML = icon(open ? "close" : "menu");
    });
  }
  function setLang(l) {
    if (l === lang) return;
    lang = l === "en" ? "en" : "zh"; store.set("lang", lang);
    renderAll();
  }
  function renderAll() {
    renderShell();
    if (page.title) document.title = typeof page.title === "function" ? page.title() : page.title;
    page.render();
    observe();
  }
  function mount(def) { page = { ...page, ...def }; renderAll(); }

  // ---------------------------------------------------------------- hash state: #a=1&b=2
  const hash = () => Object.fromEntries(new URLSearchParams(location.hash.slice(1)));
  function setHash(params, push = false) {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null && v !== false)).toString();
    const url = location.pathname + location.search + (q ? "#" + q : "");
    try { history[push ? "pushState" : "replaceState"](null, "", url); } catch { /* file:// in some browsers */ }
  }

  // ---------------------------------------------------------------- motion: reveal on scroll, count up
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  let io = null;
  function observe() {
    const els = $$(".reveal:not(.in), [data-count]:not([data-counted])");
    if (!("IntersectionObserver" in window) || reduced()) {
      els.forEach(el => { el.classList.add("in"); if (el.dataset.count) { el.dataset.counted = "1"; el.textContent = fmt(+el.dataset.count); } });
      return;
    }
    io = io || new IntersectionObserver(entries => entries.forEach(e => {
      if (!e.isIntersecting) return;
      const el = e.target; io.unobserve(el);
      el.classList.add("in");
      if (el.dataset.count && !el.dataset.counted) countUp(el);
    }), { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    els.forEach((el, i) => { if (el.classList.contains("reveal")) el.style.transitionDelay = `${Math.min(i % 6, 5) * 50}ms`; io.observe(el); });
  }
  function countUp(el) {
    el.dataset.counted = "1";
    const to = +el.dataset.count, t0 = performance.now(), dur = 900 + Math.min(700, to * 2);
    const step = t => {
      const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      el.textContent = fmt(Math.round(to * e));
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  // ---------------------------------------------------------------- feedback & files
  function toast(text) {
    let n = $("#toast");
    if (!n) { n = document.createElement("div"); n.id = "toast"; n.className = "toast"; n.setAttribute("role", "status"); document.body.append(n); }
    n.textContent = text; n.classList.add("show");
    clearTimeout(toast.t); toast.t = setTimeout(() => n.classList.remove("show"), 2000);
  }
  async function copy(text) {
    try { await navigator.clipboard.writeText(text); toast(T("已复制", "Copied")); }
    catch {
      const n = document.createElement("textarea"); n.value = text; document.body.append(n); n.select();
      const ok = document.execCommand("copy"); n.remove(); toast(ok ? T("已复制", "Copied") : T("请手动复制", "Copy manually"));
    }
  }
  function download(name, value, type = "application/json") {
    const body = typeof value === "string" ? value : JSON.stringify(value, null, 2) + "\n";
    const url = URL.createObjectURL(new Blob([body], { type: type + ";charset=utf-8" }));
    const a = document.createElement("a"); a.href = url; a.download = name; document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const term = (lines, copyText) => `<div class="term"><button type="button" class="copy" data-copy="${esc(copyText ?? lines.filter(l => !l.startsWith("#")).join("\n"))}">${T("复制", "Copy")}</button><pre>${
    lines.map(l => l.startsWith("#") ? `<span class="c">${esc(l)}</span>` : `<span class="p">$ </span>${esc(l)}`).join("\n")}</pre></div>`;
  document.addEventListener("click", e => {
    const c = e.target.closest("[data-copy]");
    if (c) { e.preventDefault(); copy(c.dataset.copy); }
    const top = $("#top");
    if (top && top.classList.contains("open") && e.target.closest(".nav a")) top.classList.remove("open");
  });

  // ---------------------------------------------------------------- dialogs
  function dialog(id, cls = "drawer") {
    let d = document.getElementById(id);
    if (!d) {
      d = document.createElement("dialog"); d.id = id; d.className = cls; document.body.append(d);
      d.addEventListener("click", e => { if (e.target === d) d.close(); });
    }
    return d;
  }
  function openDialog(id, { title, sub = "", body, cls = "drawer", onClose } = {}) {
    const d = dialog(id, cls);
    d.innerHTML = `<div class="dlg-head"><div><h2>${title}</h2>${sub ? `<p>${sub}</p>` : ""}</div><button type="button" class="dlg-close" aria-label="${T("关闭", "Close")}">${icon("close")}</button></div><div class="dlg-body">${body}</div>`;
    $(".dlg-close", d).addEventListener("click", () => d.close());
    d.onclose = onClose || null;
    if (!d.open) d.showModal();
    d.scrollTop = 0;
    return d;
  }

  // ---------------------------------------------------------------- fields: links into the catalog
  // DATA.fields: {path: [definition_zh, availability, type]} on site pages, {path: {definition, …}} on the paper dashboard
  const FIELDS = DATA.fields || {};
  const fieldDef = path => { const f = FIELDS[path]; return !f ? "" : Array.isArray(f) ? f[0] : f.definition || ""; };
  const fieldHref = path => `fields.html#field=${encodeURIComponent(path)}`;
  const fieldTitle = path => FIELDS[path] ? `${path} — ${fieldDef(path)}` : path;
  // The local dashboard has no fields page beside it: a field name there keeps its definition as a title only.
  const fieldLink = (path, label) => !local
    ? `<a class="mono" href="${fieldHref(path)}" title="${esc(fieldTitle(path))}">${esc(label || path)}</a>`
    : `<span class="mono" title="${esc(fieldTitle(path))}">${esc(label || path)}</span>`;
  const av = a => a ? `<span class="badge av-${esc(a)}" title="${esc(({ D: T("直接抽取", "directly extracted"), N: T("标准化", "normalized"), I: T("人工判断", "human judgment"), G: T("后续生成", "generated downstream"), F: T("未来来源", "future source") })[a] || a)}">${esc(a)}</span>` : "";

  // JSON with field-name links. `mark` is a set of field paths to highlight (e.g. what the pipeline added).
  // `wrap` lays every line out as its own block, so long values wrap under their key instead of at column 0.
  function json(v, { mark = null, link = true, wrap = false } = {}) {
    const groups = SITE.groups || ["common", "agent", "skills", "transform", "omics"];
    // a key is a field path itself ("agent.lod_score" in a candidate) or sits under a group object (records, nested candidates)
    const keyHTML = (k, parent) => {
      const path = FIELDS[k] ? k : (groups.includes(parent) ? parent + "." + k : null);
      const q = esc(JSON.stringify(k));
      const hit = mark && (mark.has(path) || mark.has(parent ? parent + "." + k : k));
      const inner = path && link && !local ? `<a class="j-key" href="${fieldHref(path)}" title="${esc(fieldTitle(path))}">${q}</a>`
        : `<span class="j-key"${path && FIELDS[path] ? ` title="${esc(fieldTitle(path))}"` : ""}>${q}</span>`;
      return hit ? `<span class="j-new">${inner}</span>` : inner;
    };
    const walk = (x, ind, parent) => {
      const pad = ind + "  ";
      if (x === null) return '<span class="j-lit">null</span>';
      if (Array.isArray(x)) {
        if (!x.length) return "[]";
        if (x.every(y => typeof y !== "object" || y === null) && JSON.stringify(x).length < 72) return "[" + x.map(y => walk(y, pad, null)).join(", ") + "]";
        return "[\n" + x.map(y => pad + walk(y, pad, null)).join(",\n") + "\n" + ind + "]";
      }
      if (typeof x === "object") {
        const ks = Object.keys(x);
        if (!ks.length) return "{}";
        return "{\n" + ks.map(k => pad + keyHTML(k, parent) + ": " + walk(x[k], pad, k)).join(",\n") + "\n" + ind + "}";
      }
      if (typeof x === "string") return '<span class="j-str">' + esc(JSON.stringify(x)) + "</span>";
      if (typeof x === "number") return '<span class="j-num">' + x + "</span>";
      return '<span class="j-lit">' + x + "</span>";
    };
    const out = walk(v, "", null);
    return !wrap ? out : out.split("\n").map(l => { const n = /^ */.exec(l)[0].length; return `<span class="jl" style="padding-left:${n + 2}ch">${l.slice(n)}</span>`; }).join("");
  }

  // A text with highlighted spans [{start, end, cls, title}] (non-overlapping cuts; the first span covering a cut wins).
  function annotate(text, spans) {
    text = String(text ?? "");
    const cuts = [...new Set([0, text.length, ...spans.flatMap(x => [x.start, x.end])])].filter(n => n >= 0 && n <= text.length).sort((a, b) => a - b);
    let html = "";
    for (let k = 0; k < cuts.length - 1; k++) {
      const [a, b] = [cuts[k], cuts[k + 1]], seg = esc(text.slice(a, b));
      const hit = spans.find(x => x.start <= a && x.end >= b);
      html += hit ? `<span class="sp ${hit.cls}"${hit.title ? ` title="${esc(hit.title)}"` : ""}>${seg}</span>` : seg;
    }
    return html;
  }

  // ---------------------------------------------------------------- records
  const KINDS = {
    claim: ["结论", "Claim", "var(--c1)"], observation: ["论文观测", "Observation", "var(--c3)"], method: ["方法", "Method", "var(--c2)"],
    analysis_result: ["分析结果", "Analysis result", "var(--c7)"], phenotype_observation: ["表型观测", "Phenotype obs.", "var(--c4)"],
    environment_observation: ["环境观测", "Environment obs.", "var(--c6)"], genotype_observation: ["基因型观测", "Genotype obs.", "var(--c5)"],
    asset_manifest: ["资产记录", "Asset", "var(--ink-3)"], tool_spec: ["工具规范", "Tool spec", "var(--c8)"],
  };
  const kindLabel = k => KINDS[k] ? T(KINDS[k][0], KINDS[k][1]) : (k || T("未知", "unknown"));
  const kindColor = k => (KINDS[k] || [])[2] || "var(--ink-3)";
  const kindTag = k => `<span class="tag" style="--k:${kindColor(k)}"><span class="swatch" style="background:var(--k);margin:0;border-radius:50%;width:7px;height:7px"></span>${esc(kindLabel(k))}</span>`;
  const REVIEW = {
    pending_review: ["待复核", "Pending review", "amber"], auto_validated: ["校验通过", "Auto-validated", "ok"],
    model_verified: ["模型核验通过", "Model-verified", "brand"], expert_approved: ["专家通过", "Expert-approved", "brand"], rejected: ["专家否决", "Rejected", "clay"],
  };
  const reviewTag = s => s ? `<span class="tag dot ${(REVIEW[s] || [])[2] || ""}" title="review_status: ${esc(s)}">${esc(REVIEW[s] ? T(REVIEW[s][0], REVIEW[s][1]) : s)}</span>` : "";
  function summary(r) {
    const c = r.common || {}, a = r.agent || {}, s = r.skills || {}, t = r.transform || {}, o = r.omics || {};
    if (a.finding_text) return a.finding_text;
    if (a.result_interpretation || a.breeding_relevance) return a.result_interpretation || a.breeding_relevance;
    if (c.record_kind === "asset_manifest" || c.asset_kind) return `${T("输入资产", "Input asset")} · ${c.asset_format || c.asset_kind || ""} · ${fmt(c.asset_size_bytes ?? 0)} bytes`;
    if (c.measurement_name || c.measurement_value !== undefined) return `${(c.germplasm_names || []).join(" / ")} ${c.environment_code || ""} · ${c.measurement_name || T("观测值", "value")} ${c.measurement_value ?? c.measurement_text ?? ""} ${c.measurement_unit || ""}`.replace(/\s+/g, " ").trim();
    if (s.software_name) return `${s.software_name}${s.software_version ? " " + s.software_version : ""}${s.method_name ? " · " + s.method_name : ""}`;
    if (a.lod_score !== undefined) return `${(c.qtl_names || []).join(" / ")} · LOD ${a.lod_score}`;
    if (a.pve_percent !== undefined) return `${(c.qtl_names || []).join(" / ")} · PVE ${a.pve_percent}%`;
    if (a.effect_estimate !== undefined) return `${(c.qtl_names || []).join(" / ")} · ${T("效应", "effect")} ${a.effect_estimate} ${a.effect_unit || ""}`.trim();
    if (c.variant_id) return `${c.variant_id} · ${c.genotype_call || ""}`;
    if (t.subject_mention) return `${t.subject_mention} → ${t.object_mention || ""}`;
    if (o.omics_type) return `${o.omics_type}${o.log2_fold_change != null ? " · log2FC " + o.log2_fold_change : ""}`;
    if (c.original_value) return `${(c.trait_names || []).join(" / ")} · ${c.original_value} ${c.original_unit || ""}`;
    return s.method_name || c.trait_measurement_protocol || c.source_quote || c.record_id || c.record_kind || "";
  }

  // One record in the drawer: what it says, where it stands in the paper, the JSON with field links.
  // links: [[href, label]] shown as buttons; note: extra HTML above the JSON.
  function recordDrawer(r, { note = "", links = [] } = {}) {
    const c = r.common || {};
    return openDialog("record-dlg", { title: `${esc(kindLabel(c.record_kind))} · ${esc(clip(summary(r), 70))}`, sub: esc(c.record_id || ""),
      body: `<div class="row" style="margin-bottom:14px">${kindTag(c.record_kind)}${reviewTag(c.review_status)}${c.source_page != null ? `<span class="tag">p.${esc(c.source_page)}</span>` : ""}${c.source_section ? `<span class="tag">${esc(c.source_section)}</span>` : ""}${c.source_part && c.source_part !== "main_text" ? `<span class="tag gold">${esc(c.source_part)}</span>` : ""}</div>
        ${c.source_quote ? `<blockquote class="quote">${esc(c.source_quote)}</blockquote>` : ""}${note}
        ${links.length ? `<div class="row" style="margin:14px 0">${links.map(([href, label]) => `<a class="btn sm" href="${esc(href)}">${esc(label)} ${icon("arrow")}</a>`).join("")}</div>` : ""}
        <div class="code-box"><pre class="json">${json(r, { wrap: true })}</pre></div>` });
  }

  // ---------------------------------------------------------------- live property graph (entities, records, statements)
  const TYPE_COLORS = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)", "var(--c5)", "var(--c6)", "var(--c7)", "var(--c8)"];
  function forceGraph(host, graph, { kinds = new Set(["statement", "mention", "link"]), onRecord = null, height = 560 } = {}) {
    const W = Math.max(640, host.clientWidth || 960), H = height;
    const edges = graph.edges.filter(e => kinds.has(e.kind));
    const used = new Set(edges.flatMap(e => [e.s, e.o]));
    const nodes = graph.nodes.filter(n => used.has(n.id)).map((n, i) => ({ ...n, i }));
    const idx = Object.fromEntries(nodes.map((n, i) => [n.id, i]));
    const types = [...new Set(graph.nodes.filter(n => n.kind === "entity").map(n => n.type || "entity"))];
    const color = t => TYPE_COLORS[types.indexOf(t) % TYPE_COLORS.length];
    const deg = {};
    for (const e of edges) { deg[e.s] = (deg[e.s] || 0) + 1; deg[e.o] = (deg[e.o] || 0) + 1; }
    nodes.forEach((n, i) => { const a = i * 2.399; const r = 30 + 8 * Math.sqrt(i); n.x = W / 2 + r * Math.cos(a); n.y = H / 2 + r * Math.sin(a); n.vx = 0; n.vy = 0; });
    const links = edges.map(e => ({ e, a: idx[e.s], b: idx[e.o], len: e.kind === "statement" ? 210 : e.kind === "mention" ? 70 + 6 * Math.min(20, deg[e.o] || 0) : 140 }))
      .filter(l => l.a != null && l.b != null && l.a !== l.b);
    const nbr = nodes.map(() => new Set());
    links.forEach(l => { nbr[l.a].add(l.b); nbr[l.b].add(l.a); });
    const radius = n => n.kind === "entity" ? 9 + Math.min(9, n.mentions || 1) : n.kind === "record" ? 7 : 8;
    const pairs = {};
    const edgeSVG = links.map((l, k) => {
      const key = [l.e.s, l.e.o].sort().join("|") + l.e.kind; l.bend = (pairs[key] = (pairs[key] || 0) + 1);
      const mk = l.e.kind === "statement" ? ' marker-end="url(#fg-arrow)"' : l.e.kind === "link" ? ' marker-end="url(#fg-arrow-l)"' : "";
      return `<path class="fg-e fg-${l.e.kind}" data-k="${k}"${mk}><title>${esc(l.e.s)} — ${esc(l.e.p)} → ${esc(l.e.o)}${l.e.predicate_status ? " · " + esc(l.e.predicate_status) : ""}${l.e.argument_role ? " · " + esc(l.e.argument_role) : ""}</title></path>` +
        (l.e.kind === "statement" ? `<text class="fg-el" data-k="${k}">${esc(l.e.predicate_mention || String(l.e.p).replace(/^bdc:/, ""))}</text>` : "");
    }).join("");
    const nodeSVG = nodes.map((n, i) => {
      const r = radius(n);
      const tip = n.kind === "entity" ? `${n.label || n.id} · ${n.type || "entity"} · ${T("被", "mentioned by ")}${n.mentions || 0}${T(" 条记录提及", " record(s)")}` : n.kind === "record" ? `${kindLabel(n.type)}: ${clip(n.label || n.id, 140)}` : `source · ${n.label || n.id}`;
      const shape = n.kind === "record" ? `<rect x="${-r}" y="${-r}" width="${2 * r}" height="${2 * r}" rx="3" class="fg-rec" style="--k:${kindColor(n.type)}"/>`
        : n.kind === "entity" ? `<circle r="${r}" class="fg-ent" style="fill:${color(n.type || "entity")}"/>` : `<circle r="${r}" class="fg-src"/>`;
      const label = n.kind === "entity" ? `<text class="fg-nl" y="${r + 14}">${esc(clip(n.label || n.id, 28))}</text>` : "";
      return `<g class="fg-n fg-${n.kind}" data-i="${i}" tabindex="${n.kind === "record" ? 0 : -1}"><title>${esc(tip)}</title>${shape}${label}</g>`;
    }).join("");
    host.innerHTML = `<svg class="fg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${T("示例记录的属性图", "Property graph of the example records")}">
      <defs><marker id="fg-arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="var(--brand)"/></marker>
      <marker id="fg-arrow-l" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="var(--gold)"/></marker></defs>
      <g class="fg-edges">${edgeSVG}</g><g class="fg-nodes">${nodeSVG}</g></svg>`;
    const svg = $("svg", host), pathEls = $$(".fg-e", svg), labelEls = $$(".fg-el", svg), nodeEls = $$(".fg-n", svg);
    const labelFor = Object.fromEntries(labelEls.map(t => [t.dataset.k, t]));
    let alpha = 1, raf = 0, drag = null;
    function tick() {
      for (let a = 0; a < nodes.length; a++) for (let b = a + 1; b < nodes.length; b++) {
        const A = nodes[a], B = nodes[b];
        let x = A.x - B.x || .1, y = A.y - B.y || .1; const d2 = x * x + y * y, d = Math.sqrt(d2);
        const f = Math.min(8, 2600 / d2) * alpha; x /= d; y /= d;
        A.vx += x * f; A.vy += y * f; B.vx -= x * f; B.vy -= y * f;
      }
      for (const l of links) {
        const A = nodes[l.a], B = nodes[l.b];
        const x = B.x - A.x, y = B.y - A.y, d = Math.hypot(x, y) || 1, f = (d - l.len) * 0.012 * alpha;
        A.vx += x / d * f; A.vy += y / d * f; B.vx -= x / d * f; B.vy -= y / d * f;
      }
      for (const n of nodes) {
        n.vx += (W / 2 - n.x) * 0.0016 * alpha; n.vy += (H / 2 - n.y) * 0.004 * alpha;
        if (drag && drag.n === n) { n.vx = n.vy = 0; continue; }
        n.vx *= 0.82; n.vy *= 0.82; n.x += n.vx; n.y += n.vy;
        const r = radius(n) + 8; n.x = Math.max(r, Math.min(W - r, n.x)); n.y = Math.max(r, Math.min(H - r - 12, n.y));
      }
    }
    function draw() {
      links.forEach((l, k) => {
        const A = nodes[l.a], B = nodes[l.b];
        const dx = B.x - A.x, dy = B.y - A.y, len = Math.hypot(dx, dy) || 1;
        const bend = l.e.kind === "statement" ? 22 * l.bend : l.e.kind === "link" ? 16 : 0;
        const cx = (A.x + B.x) / 2 - dy / len * bend, cy = (A.y + B.y) / 2 + dx / len * bend;
        const rb = radius(B) + 3, ex = B.x - (B.x - cx) / Math.hypot(B.x - cx, B.y - cy || 1) * rb, ey = B.y - (B.y - cy) / Math.hypot(B.x - cx, B.y - cy || 1) * rb;
        pathEls[k].setAttribute("d", `M${A.x.toFixed(1)} ${A.y.toFixed(1)}Q${cx.toFixed(1)} ${cy.toFixed(1)} ${ex.toFixed(1)} ${ey.toFixed(1)}`);
        const t = labelFor[k];
        if (t) { t.setAttribute("x", ((A.x + B.x) / 2 * .5 + cx * .5).toFixed(1)); t.setAttribute("y", ((A.y + B.y) / 2 * .5 + cy * .5 - 5).toFixed(1)); }
      });
      nodeEls.forEach((g, i) => g.setAttribute("transform", `translate(${nodes[i].x.toFixed(1)} ${nodes[i].y.toFixed(1)})`));
    }
    function loop() { tick(); draw(); alpha *= 0.985; if (alpha > 0.02 || drag) raf = requestAnimationFrame(loop); else raf = 0; }
    function kick(a = 0.5) { alpha = Math.max(alpha, a); if (!raf) raf = requestAnimationFrame(loop); }
    if (reduced()) { for (let k = 0; k < 400; k++) { tick(); alpha *= 0.99; } draw(); } else { draw(); kick(1); }
    const toLocal = ev => { const p = svg.createSVGPoint(); p.x = ev.clientX; p.y = ev.clientY; return p.matrixTransform(svg.getScreenCTM().inverse()); };
    svg.addEventListener("pointerdown", ev => {
      const g = ev.target.closest(".fg-n"); if (!g) return;
      drag = { n: nodes[+g.dataset.i], moved: false, x: ev.clientX, y: ev.clientY }; svg.setPointerCapture(ev.pointerId); kick(0.3);
    });
    svg.addEventListener("pointermove", ev => {
      if (!drag) return;
      if (Math.abs(ev.clientX - drag.x) + Math.abs(ev.clientY - drag.y) > 3) drag.moved = true;
      const p = toLocal(ev); drag.n.x = p.x; drag.n.y = p.y; kick(0.3);
    });
    svg.addEventListener("pointerup", ev => {
      const d = drag; drag = null;
      if (d && !d.moved && d.n.kind === "record" && onRecord) onRecord(d.n.id.replace(/^rec:/, ""));
      try { svg.releasePointerCapture(ev.pointerId); } catch { /* not captured */ }
    });
    svg.addEventListener("keydown", ev => { const g = ev.target.closest(".fg-record"); if (g && ev.key === "Enter" && onRecord) onRecord(nodes[+g.dataset.i].id.replace(/^rec:/, "")); });
    const focus = i => {
      svg.classList.toggle("focus", i != null);
      nodeEls.forEach((g, j) => g.classList.toggle("on", i != null && (j === i || nbr[i].has(j))));
      links.forEach((l, k) => { const on = i != null && (l.a === i || l.b === i); pathEls[k].classList.toggle("on", on); labelFor[k]?.classList.toggle("on", on); });
    };
    svg.addEventListener("pointerover", ev => { const g = ev.target.closest(".fg-n"); if (g) focus(+g.dataset.i); });
    svg.addEventListener("pointerout", ev => { if (ev.target.closest(".fg-n") && !drag) focus(null); });
    return { types, color, shown: { nodes: nodes.length, edges: links.length }, stop: () => cancelAnimationFrame(raf) };
  }

  // ---------------------------------------------------------------- research workflow: stages as columns, record links as edges
  const STAGES = [
    ["background", "研究背景", "Background"], ["research_question", "科学问题", "Question"], ["objective", "研究目标", "Objective"],
    ["hypothesis", "科学假设", "Hypothesis"], ["design", "实验设计", "Design"], ["step", "实验步骤", "Step"],
    ["observation", "观测", "Observation"], ["result", "结果", "Result"], ["conclusion", "结论", "Conclusion"], ["statement", "陈述", "Statement"],
  ];
  const COLUMNS = [["background"], ["research_question", "objective"], ["hypothesis"], ["design", "step"], ["observation", "result"], ["conclusion", "statement"]];
  const EDGE_TYPES = {
    addresses: ["回应", "addresses", "var(--c7)"], tests: ["检验", "tests", "var(--c2)"], method: ["方法", "method", "var(--c1)"],
    evidence: ["依据", "rests on", "var(--c3)"], prerequisite: ["前置", "prerequisite", "var(--c4)"],
  };
  const FLAG_LABEL = {
    HYPOTHESIS_UNTESTED: ["假设未检验", "hypothesis untested"], QUESTION_UNADDRESSED: ["问题未被回应", "question unaddressed"],
    CONCLUSION_WITHOUT_EVIDENCE: ["结论缺少证据", "conclusion without evidence"], RESULT_WITHOUT_METHOD: ["结果缺少方法", "result without method"],
    STEP_WITHOUT_OUTPUT: ["步骤无产出", "step without output"], DEPENDENCY_CYCLE: ["依赖成环", "dependency cycle"], UNRESOLVED_LINK: ["链接未解析", "unresolved link"],
  };
  // evidence-chain audit flags (validation.json argument_structure; the English is the auditor's own help text)
  const AUDIT_FLAG = {
    NO_WARRANT: ["缺推理依据", "no warrant", "没有统计检验、证据类型或关联的方法作为推理依据，需要人工核对", "no warrant in the chain: no statistical test, evidence type or linked method"],
    NO_DATA: ["缺数据", "no data", "有所断言，却既没有陈述也没有关联任何数据（引文、观测、统计量）", "asserts something but neither states nor links any data (quote, observation, statistic)"],
    QUALIFIER_NOT_CAPTURED: ["限定语未保留", "qualifier not captured", "引文对陈述有所保留，但限定措辞没有被记下", "the quote hedges the statement but the qualifier text was not captured"],
    HEDGED_STATEMENT_USED_AS_DATA: ["存疑陈述被用作数据", "hedged statement used as data", "带保留的陈述被当作另一陈述的数据，不确定性会叠加", "a hedged statement is used as data for another statement (uncertainty compounds)"],
    UNRESOLVED_LINK: ["关联未解析", "unresolved link", "关联指向的记录不在这批记录中", "a link points to a record that is not in this set"],
  };
  const auditFlag = (f, long = false) => AUDIT_FLAG[f] ? T(...AUDIT_FLAG[f].slice(long ? 2 : 0, long ? 4 : 2)) : f;
  const stageLabel = s => { const x = STAGES.find(y => y[0] === s); return x ? T(x[1], x[2]) : s; };
  // Nodes in columns, edges drawn between them from the laid-out boxes (redrawn on resize); hovering a node
  // dims everything not linked to it. cols: [{title, nodes: [{id, html, cls}]}]; edges: [{s, o, color, key, cls}].
  function linkedColumns(host, cols, edges, { onNode = null, legend = "", minWidth = 980 } = {}) {
    host.innerHTML = `<div class="wf-scroll"><div class="wf" style="min-width:${minWidth}px"><svg class="wf-edges" aria-hidden="true"></svg><div class="wf-cols">${cols.map(c => `<div class="wf-col">
      <div class="wf-col-h">${c.title}</div>${c.nodes.map(n => `<button type="button" class="wf-node ${n.cls || ""}" data-id="${esc(n.id)}">${n.html}</button>`).join("")}</div>`).join("")}</div></div></div>${legend}`;
    const root = $(".wf", host), svg = $(".wf-edges", host);
    const colors = [...new Set(edges.map(e => e.color))];
    const draw = () => {
      const box = root.getBoundingClientRect();
      svg.setAttribute("width", root.scrollWidth); svg.setAttribute("height", root.scrollHeight);
      const pos = id => { const el = $(`.wf-node[data-id="${CSS.escape(id)}"]`, root); if (!el) return null; const r = el.getBoundingClientRect(); return { l: r.left - box.left, r: r.right - box.left, cy: r.top - box.top + r.height / 2, cx: r.left - box.left + r.width / 2 }; };
      svg.innerHTML = `<defs>${colors.map((c, i) => `<marker id="lc-a${i}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="${c}"/></marker>`).join("")}</defs>` +
        edges.map(e => {
          const a = pos(e.s), b = pos(e.o); if (!a || !b) return "";
          let d;
          if (Math.abs(a.cx - b.cx) < 40) { const x = a.r + 4, bx = b.r + 4, off = 26 + Math.abs(a.cy - b.cy) * .12; d = `M${x} ${a.cy}C${x + off} ${a.cy} ${bx + off} ${b.cy} ${bx} ${b.cy}`; }
          else if (a.cx < b.cx) d = `M${a.r} ${a.cy}C${(a.r + b.l) / 2} ${a.cy} ${(a.r + b.l) / 2} ${b.cy} ${b.l - 2} ${b.cy}`;
          else d = `M${a.l} ${a.cy}C${(a.l + b.r) / 2} ${a.cy} ${(a.l + b.r) / 2} ${b.cy} ${b.r + 2} ${b.cy}`;
          return `<path d="${d}"${e.cls ? ` class="${esc(e.cls)}"` : ""} data-s="${esc(e.s)}" data-o="${esc(e.o)}" style="stroke:${e.color}" marker-end="url(#lc-a${colors.indexOf(e.color)})"><title>${esc(e.key || "")}</title></path>`;
        }).join("");
    };
    requestAnimationFrame(draw);
    if ("ResizeObserver" in window) new ResizeObserver(() => draw()).observe(root);
    root.addEventListener("pointerover", ev => {
      const b = ev.target.closest(".wf-node"); if (!b) return;
      const id = b.dataset.id, near = new Set([id]);
      $$("path", svg).forEach(p => { const on = p.dataset.s === id || p.dataset.o === id; p.classList.toggle("on", on); if (on) { near.add(p.dataset.s); near.add(p.dataset.o); } });
      root.classList.add("focus"); $$(".wf-node", root).forEach(n => n.classList.toggle("on", near.has(n.dataset.id)));
    });
    root.addEventListener("pointerleave", () => { root.classList.remove("focus"); $$("path", svg).forEach(p => p.classList.remove("on")); $$(".wf-node", root).forEach(n => n.classList.remove("on")); });
    root.addEventListener("click", ev => { const b = ev.target.closest(".wf-node"); if (b && onNode) onNode(b.dataset.id); });
  }
  function workflow(host, w, { onNode = null } = {}) {
    const order = new Map((w.step_order || []).map((id, i) => [id, i + 1]));
    const cols = COLUMNS.map(stages => ({ stages, nodes: stages.flatMap(s => w.nodes.filter(n => n.stage === s)) })).filter(c => c.nodes.length).map(c => ({
      title: [...new Set(c.nodes.map(n => n.stage))].map(stageLabel).join(" · "),
      nodes: c.nodes.map(n => ({ id: n.id, cls: `wf-${n.stage}${(n.flags || []).length ? " flagged" : ""}`, html:
        `<span class="wf-stage">${esc(stageLabel(n.stage))}${order.has(n.id) ? ` <span class="mono">#${order.get(n.id)}</span>` : ""}${n.source_part && n.source_part !== "main_text" ? ` <span class="wf-part">${T("补充材料", "supplement")}</span>` : ""}</span>
        <span class="wf-label">${esc(clip(n.label || n.id, 120))}</span>
        ${(n.flags || []).map(f => `<span class="tag amber">${icon("alert")}${esc(FLAG_LABEL[f] ? T(...FLAG_LABEL[f]) : f)}</span>`).join("")}` })),
    }));
    const edges = w.edges.map(e => ({ s: e.s, o: e.o, color: (EDGE_TYPES[e.type] || [, , "var(--ink-3)"])[2], key: e.field }));
    const legend = `<div class="legend" style="margin-top:12px">${Object.entries(EDGE_TYPES).filter(([k]) => (w.edges_by_type || {})[k]).map(([k, [zh, en, c]]) => `<span><i class="swatch" style="background:${c};height:3px;width:16px;vertical-align:3px"></i>${esc(T(zh, en))} · ${w.edges_by_type[k]}</span>`).join("")}</div>`;
    linkedColumns(host, cols, edges, { onNode, legend });
  }

  return { DATA, SITE, T, esc, $, $$, fmt, count, short, clip, icon, LOGO, PAGES, pageOf, local, mount, hash, setHash, observe, reduced, toast, copy, download, term,
    openDialog, recordDrawer, FIELDS, fieldDef, fieldHref, fieldLink, av, json, annotate, KINDS, kindLabel, kindColor, kindTag, REVIEW, reviewTag, summary, forceGraph, workflow, linkedColumns,
    STAGES, stageLabel, EDGE_TYPES, FLAG_LABEL, AUDIT_FLAG, auditFlag, get lang() { return lang; } };
})();
