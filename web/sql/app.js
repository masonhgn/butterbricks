"use strict";

// the SQL category's page. Helpers, storage, accounts, the problem list and the editor setup are shared, in ../common.js

const S = {
  levels: [], challenges: [], schema: {}, progress: null,
  index: 0, attempts: 0, hintsShown: 0,
  solution: null,      // {index} once the reference answer for that challenge is revealed
  tableCache: {},      // pristine table data, name -> grid
  modified: {},        // tables as they looked after the last run, name -> grid
  result: null, expected: null, after: null,
  extraTables: [],     // tables opened with the + button
  active: null,        // active sheet tab id
  sort: {},            // sheet tab id -> {col, dir}
  view: null,          // rows currently drawn in the grid, after filter and sort
  sel: null,           // selected cell {r, c}
};

let cm;

const letters = (i) => { let s = ""; i += 1; while (i) { s = String.fromCharCode(65 + ((i - 1) % 26)) + s; i = Math.floor((i - 1) / 26); } return s; };
const current = () => S.challenges[S.index];

//engine: sql runs in a web worker (engine.js) so a runaway query can be stopped by killing it

const QUERY_TIMEOUT = 5000;
let worker, workerReady, nextCall = 0;
const pending = new Map();

function startWorker() {
  worker = new Worker("engine.js?v=bb-1");
  worker.onmessage = ({ data }) => {
    const p = pending.get(data.id);
    if (!p) return;
    pending.delete(data.id);
    clearTimeout(p.timer);
    if (data.error !== undefined) p.reject(new Error(data.error));
    else p.resolve(data.value);
  };
  workerReady = call("init", { dbUrl: "store.db", challenges: S.challenges });
}

function call(op, args, timeout) {
  return new Promise((resolve, reject) => {
    const id = nextCall++;
    const p = { resolve, reject };
    if (timeout) p.timer = setTimeout(() => {
      pending.delete(id);
      worker.terminate();
      for (const q of pending.values()) { clearTimeout(q.timer); q.reject(new Error("the engine was restarted")); }
      pending.clear();
      startWorker();
      reject(new Error(`query took longer than ${QUERY_TIMEOUT / 1000}s and was stopped`));
    }, timeout);
    pending.set(id, p);
    worker.postMessage({ id, op, args });
  });
}

async function engine(op, args, timeout) {
  await workerReady;
  return call(op, args, timeout);
}

//progress lives in this browser's localStorage, in the same format as the terminal version's progress.json

const PROGRESS_KEY = "butterbricks:sql:progress";
const draftKey = (key) => `butterbricks:sql:draft:${key}`;

function loadProgress() {
  const data = storedJson(PROGRESS_KEY, {});
  const keys = new Set(S.challenges.map((c) => c.key));
  const solved = new Set((data.solved || []).filter((k) => keys.has(k)));
  let index = Math.min(firstUnsolved(solved), S.challenges.length - 1);
  const i = S.challenges.findIndex((c) => c.key === data.current);
  if (i >= 0) index = i;
  return { solved, index };
}

function saveProgress(solved, index) {
  storage(PROGRESS_KEY, JSON.stringify({ solved: [...solved].sort(), current: S.challenges[index].key }, null, 2));
  return progressJson(solved, index);
}

function firstUnsolved(solved) {
  const i = S.challenges.findIndex((c) => !solved.has(c.key));
  return i < 0 ? S.challenges.length : i;
}

function progressJson(solved, index) {
  return { solved: [...solved].sort(), current: index, first_unsolved: firstUnsolved(solved) };
}

async function runChallenge(index, sql) {
  const out = await engine("run", { index, sql }, QUERY_TIMEOUT).catch((e) => ({
    result: null, after: null, changes: 0, modified: {}, status: "error", message: e.message,
    tip: "Usually a JOIN without an ON clause, which pairs every row with every other row.",
  }));
  // signed out, a query still runs so you can explore the data, but checking it is a submission: that needs an account
  if (account.online && !account.user && out.status !== "error") return { ...out, status: "unchecked" };
  if (out.status !== "correct") return out;
  const ch = S.challenges[index];
  const { solved } = loadProgress();
  const firstTime = !solved.has(ch.key);
  solved.add(ch.key);
  const levelDone = S.challenges.every((c) => c.level !== ch.level || solved.has(c.key));
  return {
    ...out,
    solution: ch.solution,
    level_complete: firstTime && levelDone,
    first_time: firstTime,
    all_complete: solved.size === S.challenges.length,
    progress: saveProgress(solved, index),
  };
}

function exportProgress() {
  const { solved, index } = loadProgress();
  const text = JSON.stringify({ solved: [...solved].sort(), current: S.challenges[index].key }, null, 2);
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text + "\n"], { type: "application/json" }));
  a.download = "progress.json";
  a.click();
  URL.revokeObjectURL(a.href);
}

async function importProgress(file) {
  let data;
  try { data = JSON.parse(await file.text()); } catch (e) { data = null; }
  if (!data || !Array.isArray(data.solved)) {
    setStatus("error", "✗ Import", "That file isn't a SQL progress.json.");
    return;
  }
  storage(PROGRESS_KEY, JSON.stringify(data));
  const { solved, index } = loadProgress();
  S.progress = progressJson(solved, index);
  renderProgress();
  enter(index);
  setStatus("info", "Imported", `${plural(solved.size, "challenge")} marked solved.`);
}

// S.draftFor is the challenge whose draft is in the editor, so switching never writes one challenge's text into another's slot
function saveDraft() { if (cm && S.draftFor) storage(draftKey(S.draftFor), cm.getValue()); }

//sidebar and progress

function renderProgress() {
  const done = S.progress.solved.length, total = S.challenges.length;
  $("progress-fill").style.width = `${(100 * done) / total}%`;
  $("progress-text").textContent = `${done} / ${total} SQL challenges`;
}

function renderSidebar() {
  showProblemList("sql", current().key, (key) => enter(S.challenges.findIndex((c) => c.key === key)));
}

//the left pane: challenge, lesson, schema, solution

function showTab(name) {
  for (const t of $("left-tabs").querySelectorAll(".tab")) {
    t.classList.toggle("on", t.dataset.tab === name);
    $(`tab-${t.dataset.tab}`).hidden = t.dataset.tab !== name;
  }
}

function currentTab() {
  return $("left-tabs").querySelector(".tab.on").dataset.tab;
}

function emphasize(text, ch) {
  const words = new Set(ch.tables);
  for (const t of ch.tables) for (const col of S.schema[t] || []) words.add(col.name);
  // a quoted string must not touch letters on either side, so apostrophes like order's aren't mistaken for one
  return esc(text).replace(/(?<![A-Za-z])'[^']*'(?![A-Za-z])|\b[A-Za-z_][A-Za-z0-9_]*\b/g, (m) =>
    m.startsWith("'") || words.has(m) ? `<code>${m}</code>` : m);
}

// lessons are plain text: lines indented two spaces are sql examples, everything else is prose
function renderLesson(text, into) {
  let code = [], prose = [];
  const flushCode = () => {
    while (code.length && !code[code.length - 1].trim()) code.pop();
    if (code.length) into.append(highlighted(code.join("\n"), "text/x-sqlite"));
    code = [];
  };
  const flushProse = () => { if (prose.length) into.append(el("p", "", esc(prose.join(" ")))); prose = []; };
  for (const line of text.split("\n")) {
    if (line.startsWith("  ")) { flushProse(); code.push(line.slice(2)); }
    else if (!line.trim()) { if (code.length) code.push(""); else flushProse(); }
    else { flushCode(); prose.push(line); }
  }
  flushCode(); flushProse();
}

function renderTask() {
  const ch = current();
  $("level-chip").textContent = `Level ${ch.level + 1} · ${S.levels[ch.level].title}`;
  $("challenge-count").textContent = `challenge ${S.index + 1} of ${S.challenges.length}`;
  $("task-title").textContent = ch.title;
  const tags = $("task-tags");
  tags.innerHTML = "";
  if (S.progress.solved.includes(ch.key)) tags.append(el("span", "chip easy", "✓ solved"));
  if (ch.ordered) tags.append(el("span", "chip", "row order matters"));
  if (ch.modifies) tags.append(el("span", "chip", "changes data · checked by the table state afterwards"));
  $("task-prompt").innerHTML = emphasize(ch.prompt, ch);
  renderHints();
  $("btn-prev").disabled = S.index === 0;
  $("btn-next").disabled = S.index + 1 >= S.challenges.length;
  $("run-target").textContent = `Level ${ch.level + 1} · challenge ${S.index + 1}`;

  const lesson = $("tab-lesson");
  lesson.innerHTML = `<h2>Lesson ${ch.level + 1} · ${esc(S.levels[ch.level].title)}</h2>`;
  renderLesson(S.levels[ch.level].lesson, lesson);
  renderSolution();
}

function renderHints() {
  const ch = current(), box = $("hints");
  box.innerHTML = "";
  ch.hints.slice(0, S.hintsShown).forEach((h, i) => box.append(el("div", "hint", `<b>Hint ${i + 1}.</b> ${emphasize(h, ch)}`)));
  const left = ch.hints.length - S.hintsShown;
  if (left) {
    const btn = el("button", "btn small", S.hintsShown ? `Another hint (${left} left)` : `Show a hint (${plural(left, "hint")} available)`);
    btn.onclick = () => { S.hintsShown += 1; renderHints(); };
    box.append(btn);
  } else if (ch.hints.length) {
    box.append(el("p", "muted small", "No more hints. Try Expected output, or the Solution tab."));
  }
}

function renderSolution() {
  const box = $("tab-solution"), ch = current();
  box.innerHTML = "<h2>Reference solution</h2>";
  if (S.solution && S.solution.index === S.index) {
    box.append(highlighted(ch.solution, "text/x-sqlite"));
    box.append(el("p", "muted small", "Type it in yourself to solve the challenge; any query with the same result passes."));
  } else {
    box.append(el("p", "muted", "One way to write this challenge's query. It's more useful after you've tried, and checked the Expected output."));
    const reveal = el("button", "btn", "Reveal the solution");
    reveal.onclick = () => { S.solution = { index: S.index }; renderSolution(); };
    box.append(reveal);
  }
}

function renderSchema() {
  const box = $("tab-schema");
  box.innerHTML = `<h2>Schema</h2><p class="muted small">Every table in the database. Click a table's name to open it as a sheet.</p>`;
  const grid = el("div", "schema-grid");
  for (const [t, cols] of Object.entries(S.schema)) {
    const table = el("table", "", `<caption><button data-open="${esc(t)}">${esc(t)}</button></caption>` +
      cols.map((c) => `<tr><td>${esc(c.name)}</td><td>${esc(c.type)}</td><td>${esc(c.notes)}</td></tr>`).join(""));
    grid.append(table);
  }
  grid.onclick = (e) => { const b = e.target.closest("[data-open]"); if (b) openTable(b.dataset.open); };
  box.append(grid);
}

//the verdict line at the top of the results pane

function setStatus(kind, verdict, html) {
  const node = $("status");
  if (!kind) { node.hidden = true; return; }
  node.hidden = false;
  node.className = `status ${kind}`;
  node.innerHTML = `<span class="verdict">${esc(verdict)}</span><div class="body">${html}</div>`;
}

//sheet tabs

function tabList() {
  const tabs = [{ id: "result", label: "Result", special: true }];
  if (S.after) tabs.push({ id: "after", label: "Checked state", special: true });
  if (S.expected) tabs.push({ id: "expected", label: "Expected", special: true });
  const seen = new Set();
  for (const t of current().tables) { seen.add(t); tabs.push({ id: `t:${t}`, label: t, table: t }); }
  for (const t of S.extraTables) if (!seen.has(t)) tabs.push({ id: `t:${t}`, label: t, table: t, closable: true });
  return tabs;
}

function renderTabs() {
  const tabs = tabList();
  if (!tabs.some((t) => t.id === S.active)) S.active = tabs[0].id;
  $("sheet-tab-list").innerHTML = tabs.map((t) => {
    const dot = t.table && S.modified[t.table] ? `<span class="dot" title="changed by your last run">•</span>` : "";
    const close = t.closable ? `<span class="close" data-close="${esc(t.table)}" title="close">×</span>` : "";
    return `<button class="sheet-tab ${t.special ? "special" : ""} ${t.id === S.active ? "active" : ""}" data-tab="${esc(t.id)}">${esc(t.label)}${dot}${close}</button>`;
  }).join("");
  const open = new Set(tabs.filter((t) => t.table).map((t) => t.table));
  $("add-menu").innerHTML = Object.keys(S.schema).map((t) =>
    `<button data-open="${esc(t)}">${open.has(t) ? "✓ " : ""}${esc(t)}</button>`).join("");
}

function activate(id) {
  S.active = id;
  S.sel = null;
  renderTabs();
  renderSheet();
}

function openTable(name) {
  if (!current().tables.includes(name) && !S.extraTables.includes(name)) S.extraTables.push(name);
  activate(`t:${name}`);
}

function closeTable(name) {
  S.extraTables = S.extraTables.filter((t) => t !== name);
  if (S.active === `t:${name}`) S.active = null;
  renderTabs();
  renderSheet();
}

//the grid

function gridFor(id) {
  if (id === "result") return S.result;
  if (id === "after") return S.after;
  if (id === "expected") return S.expected;
  const name = id.slice(2);
  return S.modified[name] || S.tableCache[name];
}

function compareValues(a, b) {
  if (a === b) return 0;
  if (a === null) return -1;
  if (b === null) return 1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  if (typeof a === "number") return -1;
  if (typeof b === "number") return 1;
  return String(a).localeCompare(String(b));
}

function renderSheet() {
  const id = S.active;
  const sheet = $("sheet");
  if (id.startsWith("t:") && !gridFor(id)) {
    const name = id.slice(2);
    sheet.innerHTML = `<div class="empty">Loading ${esc(name)}…</div>`;
    engine("table", { name }).then((g) => { S.tableCache[name] = g; if (S.active === id) renderSheet(); });
    return;
  }
  const g = gridFor(id);
  if (!g) {
    const msg = id === "result" ? (S.lastRunChanged ? "Your statements didn't return rows. Check the table tabs (• marks changed ones) or Checked state." : "Run a query to see its result here.") : "Nothing here yet.";
    sheet.innerHTML = `<div class="empty">${esc(msg)}</div>`;
    S.view = null;
    $("row-count").textContent = "";
    updateFormula();
    return;
  }

  const filter = $("filter").value.trim().toLowerCase();
  let rows = g.rows;
  if (filter) rows = rows.filter((r) => r.some((v) => v !== null && String(v).toLowerCase().includes(filter)));
  const sort = S.sort[id];
  if (sort) {
    rows = rows.map((r, i) => [r, i]).sort((a, b) => compareValues(a[0][sort.col], b[0][sort.col]) * sort.dir || a[1] - b[1]).map((x) => x[0]);
  }
  S.view = rows;

  // rows that aren't in the pristine table were inserted or updated by the last run
  let pristine = null;
  if (id.startsWith("t:") && S.modified[id.slice(2)] && S.tableCache[id.slice(2)]) {
    pristine = new Set(S.tableCache[id.slice(2)].rows.map((r) => JSON.stringify(r)));
  } else if (id.startsWith("t:") && S.modified[id.slice(2)]) {
    engine("table", { name: id.slice(2) }).then((t) => { S.tableCache[id.slice(2)] = t; if (S.active === id) renderSheet(); });
  }

  const types = {};
  if (id.startsWith("t:")) for (const c of S.schema[id.slice(2)] || []) types[c.name] = c;

  const parts = ['<table class="grid"><thead><tr class="letters"><th class="corner"></th>'];
  g.columns.forEach((_, c) => parts.push(`<th data-col="${c}">${letters(c)}</th>`));
  parts.push('</tr><tr class="names"><th class="corner"></th>');
  g.columns.forEach((name, c) => {
    const arrow = sort && sort.col === c ? `<span class="arrow">${sort.dir > 0 ? "▲" : "▼"}</span>` : "";
    const t = types[name];
    const title = t ? `${t.type}${t.notes ? " · " + t.notes : ""} — click to sort` : "click to sort";
    parts.push(`<th data-sort="${c}" title="${esc(title)}">${esc(name)}${arrow}</th>`);
  });
  parts.push("</tr></thead><tbody>");
  rows.forEach((r, ri) => {
    const changed = pristine && !pristine.has(JSON.stringify(r)) ? ' class="changed"' : "";
    parts.push(`<tr${changed}><th>${ri + 1}</th>`);
    r.forEach((v, ci) => {
      if (v === null) parts.push(`<td class="null" data-r="${ri}" data-c="${ci}">NULL</td>`);
      else parts.push(`<td${typeof v === "number" ? ' class="num"' : ""} data-r="${ri}" data-c="${ci}">${esc(v)}</td>`);
    });
    parts.push("</tr>");
  });
  parts.push("</tbody></table>");
  sheet.innerHTML = parts.join("");

  const total = g.total ?? g.rows.length;
  let count = filter ? `${rows.length} of ${g.rows.length} rows` : plural(g.rows.length, "row");
  if (total > g.rows.length) count += ` (first ${g.rows.length} of ${total})`;
  $("row-count").textContent = `${count} · ${plural(g.columns.length, "column")}`;
  if (S.sel && (S.sel.r >= rows.length || S.sel.c >= g.columns.length)) S.sel = null;
  drawSelection();
}

function drawSelection() {
  const sheet = $("sheet");
  sheet.querySelectorAll(".sel, .hl").forEach((node) => node.classList.remove("sel", "hl"));
  if (S.sel) {
    const td = sheet.querySelector(`td[data-r="${S.sel.r}"][data-c="${S.sel.c}"]`);
    if (td) {
      td.classList.add("sel");
      td.parentElement.firstElementChild.classList.add("hl");
      const letter = sheet.querySelector(`tr.letters th[data-col="${S.sel.c}"]`);
      if (letter) letter.classList.add("hl");
      td.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
  }
  updateFormula();
}

function updateFormula() {
  const g = gridFor(S.active);
  if (!S.sel || !g || !S.view) { $("name-box").textContent = ""; $("formula-value").textContent = ""; return; }
  const v = S.view[S.sel.r][S.sel.c];
  $("name-box").textContent = `${letters(S.sel.c)}${S.sel.r + 1} · ${g.columns[S.sel.c]}`;
  $("name-box").title = $("name-box").textContent;
  $("formula-value").textContent = v === null ? "NULL" : String(v);
  $("formula-value").title = $("formula-value").textContent;
}

function sqlLiteral(v) {
  if (v === null) return "NULL";
  if (typeof v === "number") return String(v);
  return `'${String(v).replace(/'/g, "''")}'`;
}

function insertIntoEditor(text) {
  cm.replaceSelection(text);
  cm.focus();
}

//challenges

function enter(index, { lesson } = {}) {
  saveDraft();
  const prevLevel = S.challenges.length && S.index !== index ? current().level : null;
  S.index = index;
  S.attempts = 0;
  S.hintsShown = 0;
  S.result = S.after = S.expected = null;
  S.modified = {};
  S.lastRunChanged = false;
  S.sel = null;
  S.sort = {};
  const ch = current();
  const showLesson = lesson ?? (prevLevel !== null && prevLevel !== ch.level);
  S.active = ch.tables.length ? `t:${ch.tables[0]}` : "result";
  cm.setValue(storage(draftKey(ch.key)) || "");
  S.draftFor = ch.key;
  cm.clearHistory();
  setStatus(null);
  S.progress = saveProgress(loadProgress().solved, index);
  setProblemHash(ch.key);
  renderTask();
  renderSidebar();
  renderTabs();
  renderSheet();
  // a new level opens on its lesson; otherwise stay on the schema if that's open, or go back to the challenge
  showTab(showLesson ? "lesson" : currentTab() === "schema" ? "schema" : "challenge");
  cm.focus();
}

async function run() {
  const sql = cm.getValue();
  if (!sql.trim()) { setStatus("info", "Empty", "Type a query first."); return; }
  saveDraft();
  S.attempts += 1;
  $("btn-run").disabled = true;
  let d;
  try {
    d = await runChallenge(S.index, sql);
  } catch (e) {
    setStatus("error", "✗ Error", esc(e.message));
    return;
  } finally {
    $("btn-run").disabled = false;
  }
  const ch = current();
  S.result = d.result;
  S.after = d.after;
  S.modified = d.modified || {};
  S.lastRunChanged = d.changes > 0;
  S.sort.result = undefined;
  S.sort.after = undefined;
  for (const t of Object.keys(S.modified)) S.sort[`t:${t}`] = undefined;
  for (const t of Object.keys(S.modified)) if (!ch.tables.includes(t) && !S.extraTables.includes(t)) S.extraTables.push(t);

  const changedNote = d.changes ? `<div class="tip">${plural(d.changes, "row")} changed on a throwaway copy · tabs marked • show the changed tables</div>` : "";
  if (d.status === "error") {
    setStatus("error", "✗ Error", `${esc(d.message)}${d.tip ? `<div class="tip">${esc(d.tip)}</div>` : ""}`);
  } else if (d.status === "unchecked") {
    setStatus("info", "Ran", `Your query ran; its result is below. <button class="btn primary small" id="sign-in-to-check">Sign in</button> to submit it and save your progress.${changedNote}`);
    $("sign-in-to-check").onclick = () => requireSignIn("Sign in to submit answers. Your progress is saved to your account.");
  } else if (d.status === "wrong") {
    const left = ch.hints.length - S.hintsShown;
    const tip = left ? `${plural(left, "hint")} left in the Challenge tab, or compare with Expected output` : "Expected output shows the target, the Solution tab reveals an answer";
    setStatus("wrong", "✗ Not quite", `${esc(d.message)}<div class="tip">${tip}</div>${changedNote}`);
  } else {
    S.progress = d.progress;
    if (d.first_time) logSolve("sql", ch.key, ch.title);
    const tries = S.attempts === 1 ? "first try!" : `${S.attempts} attempts`;
    let html = `Correct, ${tries}`;
    if (d.all_complete && d.level_complete) html += `<div class="celebrate">All ${S.challenges.length} challenges cleared. You are officially dangerous with SQL.</div>`;
    else if (d.level_complete) html += `<div class="celebrate">Level ${ch.level + 1} complete! Up next: ${esc(S.levels[ch.level + 1].title)}</div>`;
    html += `<div class="tip">One way to write it:</div><pre></pre>`;
    if (S.index + 1 < S.challenges.length) html += `<div class="next"><button class="btn primary small" id="go-next">Next challenge ›</button></div>`;
    setStatus("correct", "✓ Correct", html);
    $("status").querySelector("pre").replaceWith(highlighted(d.solution, "text/x-sqlite"));
    celebrate(d.level_complete, $("status"), document.querySelector(".editor"));
    const goNext = $("go-next");
    if (goNext) goNext.onclick = () => enter(S.index + 1);
    renderSidebar();
    renderProgress();
    renderTask();
  }

  if (d.status !== "error") {
    if (d.result) S.active = "result";
    else if (Object.keys(S.modified).length) S.active = `t:${Object.keys(S.modified)[0]}`;
    else if (d.after) S.active = "after";
    else S.active = "result";
  }
  S.sel = null;
  renderTabs();
  renderSheet();
}

async function showExpected() {
  try {
    S.expected = await engine("expected", { index: S.index });
  } catch (e) {
    setStatus("error", "✗ Error", esc(e.message));
    return;
  }
  activate("expected");
}

//wiring

function bind() {
  $("btn-run").onclick = run;
  $("btn-prev").onclick = () => S.index > 0 && enter(S.index - 1);
  $("btn-next").onclick = () => enter(S.index + 1);
  $("btn-expected").onclick = showExpected;
  for (const t of $("left-tabs").querySelectorAll(".tab")) t.onclick = () => showTab(t.dataset.tab);

  armed($("btn-reset"), "Click again to erase", () => {
    S.progress = saveProgress(new Set(), 0);
    renderProgress();
    enter(0, { lesson: true });
  });

  $("btn-export").onclick = exportProgress;
  $("btn-import").onclick = () => $("import-file").click();
  $("import-file").onchange = (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (file) importProgress(file);
  };

  $("sheet-tab-list").onclick = (e) => {
    const close = e.target.closest("[data-close]");
    if (close) { e.stopPropagation(); closeTable(close.dataset.close); return; }
    const tab = e.target.closest("[data-tab]");
    if (tab) activate(tab.dataset.tab);
  };

  $("btn-add-tab").onclick = (e) => { e.stopPropagation(); $("add-menu").hidden = !$("add-menu").hidden; };
  $("add-menu").onclick = (e) => {
    const b = e.target.closest("[data-open]");
    if (b) { openTable(b.dataset.open); $("add-menu").hidden = true; }
  };
  document.addEventListener("click", (e) => { if (!e.target.closest(".add-tab")) $("add-menu").hidden = true; });

  $("filter").oninput = () => { S.sel = null; renderSheet(); };

  const sheet = $("sheet");
  sheet.tabIndex = 0;
  sheet.onclick = (e) => {
    const sortTh = e.target.closest("[data-sort]");
    if (sortTh) {
      const col = Number(sortTh.dataset.sort), s = S.sort[S.active];
      S.sort[S.active] = !s || s.col !== col ? { col, dir: 1 } : s.dir === 1 ? { col, dir: -1 } : undefined;
      renderSheet();
      return;
    }
    const td = e.target.closest("td[data-r]");
    if (td) { S.sel = { r: Number(td.dataset.r), c: Number(td.dataset.c) }; drawSelection(); }
  };
  sheet.ondblclick = (e) => {
    const td = e.target.closest("td[data-r]");
    if (td && S.view) insertIntoEditor(sqlLiteral(S.view[Number(td.dataset.r)][Number(td.dataset.c)]));
    const letter = e.target.closest("[data-col]");
    if (letter) insertIntoEditor(gridFor(S.active).columns[Number(letter.dataset.col)]);
  };
  sheet.onkeydown = (e) => {
    if (!S.sel || !S.view) return;
    const g = gridFor(S.active);
    const moves = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1], Enter: [1, 0], Tab: [0, e.shiftKey ? -1 : 1] };
    const m = moves[e.key];
    if (!m) return;
    e.preventDefault();
    S.sel = {
      r: Math.max(0, Math.min(S.view.length - 1, S.sel.r + m[0])),
      c: Math.max(0, Math.min(g.columns.length - 1, S.sel.c + m[1])),
    };
    drawSelection();
  };

  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && !e.target.closest("textarea, .CodeMirror")) { e.preventDefault(); run(); }
  });
  window.addEventListener("beforeunload", saveDraft);
}

async function init() {
  const res = await fetch("data.json");
  if (!res.ok) throw new Error(`data.json (${res.status}). Run ./serve.py from the repo root, which builds it first`);
  Object.assign(S, await res.json());
  startWorker();
  const { solved, index } = loadProgress();
  S.progress = progressJson(solved, index);
  // a link like /sql/#distinct_categories opens that challenge
  const linked = S.challenges.findIndex((c) => c.key === problemHash());
  S.index = linked >= 0 ? linked : index;
  await loadCatalog();

  const hintTables = {};
  for (const [t, cols] of Object.entries(S.schema)) hintTables[t] = cols.map((c) => c.name);
  cm = CodeMirror($("editor"), {
    ...EDITOR_DEFAULTS,
    mode: "text/x-sqlite",
    smartIndent: true,
    extraKeys: editorKeys({
      "Ctrl-Enter": run,
      "Cmd-Enter": run,
      "Ctrl-Space": "autocomplete",
    }),
    hintOptions: { tables: hintTables, completeSingle: false },
  });
  let draftTimer;
  cm.on("change", () => { clearTimeout(draftTimer); draftTimer = setTimeout(saveDraft, 400); });
  cm.on("inputRead", (c, change) => { if (change.text[0] === ".") c.showHint(); });

  bind();
  setupSplitters("sql", () => cm.refresh());
  window.addEventListener("hashchange", () => {
    const i = S.challenges.findIndex((c) => c.key === problemHash());
    if (i >= 0 && i !== S.index) enter(i);
  });
  renderSchema();
  renderProgress();
  const first = S.challenges.findIndex((c) => c.level === current().level);
  enter(S.index, { lesson: first === S.index && !S.progress.solved.includes(current().key) });
}

ready
  .then(init)
  .catch((e) => setStatus("error", "✗ Error", `Couldn't load: ${esc(e.message)}`));
