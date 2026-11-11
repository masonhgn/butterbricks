"use strict";

// shared by every Butterbricks page: helpers, localStorage and syncing it to your account, signing in, splitters,
// editor keys and confetti. Each track's app.js loads after this and uses these as globals; pages start with
// ready.then(init), so they read storage only after a signed-in browser has pulled the account's saves

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html !== undefined) e.innerHTML = html; return e; };

//storage: every key is butterbricks:<track>:<name>. A null value removes the key. In a browser that's signed in,
//every change to a synced key is also sent to the account (see accounts, below)

const PREFIX = "butterbricks:";
const SYNC_USER = "butterbricks:sync:user";        // the account this browser's saves belong to
const SYNC_PENDING = "butterbricks:sync:pending";  // keys changed here that the account doesn't have yet
// what stays in this browser: pane sizes, the timer's paused state, and the sync bookkeeping itself
const LOCAL_ONLY = /^butterbricks:(migrated$|sync:|sidebar:|home:|[a-z]+:(left-w|results-h|timer-paused)$)/;
const isSynced = (key) => key.startsWith(PREFIX) && !LOCAL_ONLY.test(key);

function raw(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(key);
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch (e) { return null; }
  return undefined;
}

// set while signing out, so nothing (like a page's save-on-leave handler) writes your work back after it's cleared
let storageFrozen = false;

function storage(key, value) {
  if (storageFrozen && value !== undefined) return undefined;
  const out = raw(key, value);
  if (value !== undefined && isSynced(key) && raw(SYNC_USER)) queueSync(key);
  return out;
}

function storedJson(key, fallback) {
  try { return JSON.parse(storage(key)) ?? fallback; } catch (e) { return fallback; }
}

function syncedKeys() {
  const keys = [];
  try { for (let i = 0; i < localStorage.length; i++) if (isSynced(localStorage.key(i))) keys.push(localStorage.key(i)); } catch (e) {}
  return keys;
}

// data saved by earlier versions of the site on the same address: SQLQuest (sqlquest:), ImplQuest (implquest:) and
// Butterbrick (butterbrick:), and this site's own butterbricks:impl: from before the category was renamed. Copy it over
// once; the old keys stay, in case anything goes wrong
(function migrateStorage() {
  try {
    if (localStorage.getItem("butterbricks:migrated") === "2") return;
    const moves = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      let to = null;
      if (k.startsWith("butterbricks:impl:")) to = `butterbricks:implementation:${k.slice(18)}`;
      else if (k.startsWith("butterbrick:impl:")) to = `butterbricks:implementation:${k.slice(17)}`;
      else if (k.startsWith("butterbrick:") && !/^butterbrick:(migrated|unlocked|last-track)$/.test(k)) to = `butterbricks:${k.slice(12)}`;
      else if (k.startsWith("sqlquest:") && !/^sqlquest:(unlocked|editor-h)$/.test(k)) to = `butterbricks:sql:${k.slice(9)}`;
      else if (k.startsWith("implquest:")) to = `butterbricks:implementation:${k.slice(10)}`;
      if (to && localStorage.getItem(to) === null) moves.push([to, localStorage.getItem(k)]);
    }
    for (const [k, v] of moves) if (localStorage.getItem(k) === null) localStorage.setItem(k, v);
    localStorage.setItem("butterbricks:migrated", "2");
  } catch (e) { /* storage blocked: nothing to carry over */ }
})();

// a button that asks for a second click instead of opening a confirm() dialog
function armed(button, prompt, action) {
  const label = button.textContent;
  let timer = null;
  button.addEventListener("click", () => {
    if (!timer) {
      button.textContent = prompt;
      button.classList.add("danger");
      timer = setTimeout(reset, 3000);
      return;
    }
    reset();
    action();
  });
  function reset() {
    clearTimeout(timer);
    timer = null;
    button.textContent = label;
    button.classList.remove("danger");
  }
}

// syntax-highlighted code outside the editor
function highlighted(src, mode) {
  const pre = el("pre");
  const code = el("code");
  CodeMirror.runMode(src, mode, code);
  pre.append(code);
  return pre;
}

//the pixel look for the big wordmark on the home page: render it normally, then resample it onto a 2px grid with hard
//edges. The blocks are built from offset copies of one sample per cell, so they're 2 CSS px at any screen density

(function pixelFilter() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("width", "0");
  svg.setAttribute("height", "0");
  svg.setAttribute("aria-hidden", "true");
  svg.style.position = "absolute";
  svg.innerHTML = `
    <filter id="px-crisp" x="0" y="0" width="1" height="1" color-interpolation-filters="sRGB">
      <feGaussianBlur in="SourceGraphic" stdDeviation="0.55" result="soft"/>
      <feFlood x="0" y="0" width="1" height="1" flood-color="#000" result="dot"/>
      <feComposite in="dot" in2="dot" operator="over" width="2" height="2" result="cell"/>
      <feTile in="cell" result="grid"/>
      <feComposite in="soft" in2="grid" operator="in" result="s"/>
      <feOffset in="s" dx="1" result="s1"/><feOffset in="s" dy="1" result="s2"/><feOffset in="s" dx="1" dy="1" result="s3"/>
      <feMerge result="blocks"><feMergeNode in="s"/><feMergeNode in="s1"/><feMergeNode in="s2"/><feMergeNode in="s3"/></feMerge>
      <feComponentTransfer in="blocks"><feFuncA type="discrete" tableValues="0 0 1 1"/></feComponentTransfer>
    </filter>`;
  document.body.prepend(svg);
})();

//editor

// backspace in a line's leading spaces deletes back to the previous indent stop, like LeetCode's editor
function backspaceIndent(c) {
  const ranges = c.listSelections();
  if (ranges.some((r) => !r.empty())) return CodeMirror.Pass;
  const unit = c.getOption("indentUnit");
  const cuts = [];
  for (const { head } of ranges) {
    if (head.ch === 0 || !/^ +$/.test(c.getLine(head.line).slice(0, head.ch))) return CodeMirror.Pass;
    cuts.push({ line: head.line, from: (Math.ceil(head.ch / unit) - 1) * unit, to: head.ch });
  }
  c.operation(() => {
    for (const { line, from, to } of cuts.reverse()) c.replaceRange("", { line, ch: from }, { line, ch: to }, "+delete");
  });
}

// editor options both tracks share; each adds its mode and keys
const EDITOR_DEFAULTS = {
  lineNumbers: true,
  lineWrapping: true,
  indentUnit: 4,
  tabSize: 4,
  matchBrackets: true,
  styleActiveLine: true,
};

function editorKeys(extra) {
  return {
    Tab: (c) => (c.somethingSelected() ? c.indentSelection("add") : c.replaceSelection("    ")),
    "Shift-Tab": (c) => c.indentSelection("subtract"),
    Backspace: backspaceIndent,
    ...extra,
  };
}

//splitters: drag to resize the statement pane and the results pane; sizes are remembered per track

function splitter(handle, onMove, onDone) {
  handle.addEventListener("mousedown", (e) => {
    e.preventDefault();
    handle.classList.add("dragging");
    const move = (ev) => onMove(ev);
    const up = () => {
      handle.classList.remove("dragging");
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
      onDone();
    };
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
  });
}

function setupSplitters(track, onResize) {
  const root = document.documentElement.style;
  const leftKey = `${PREFIX}${track}:left-w`, bottomKey = `${PREFIX}${track}:results-h`;
  if (storage(leftKey)) root.setProperty("--left-w", storage(leftKey));
  if (storage(bottomKey)) root.setProperty("--results-h", storage(bottomKey));
  splitter($("vsplit"), (e) => {
    const start = $("sidebar").getBoundingClientRect().right;
    const w = Math.max(280, Math.min(e.clientX - start, window.innerWidth - start - 360));
    root.setProperty("--left-w", `${w}px`);
  }, () => { storage(leftKey, root.getPropertyValue("--left-w")); onResize(); });
  splitter($("hsplit"), (e) => {
    const h = Math.max(90, Math.min(window.innerHeight - e.clientY, window.innerHeight - 220));
    root.setProperty("--results-h", `${h}px`);
  }, () => { storage(bottomKey, root.getPropertyValue("--results-h")); onResize(); });
}

//celebrating a correct answer

function flash(node) {
  if (!node) return;
  node.classList.remove("flash");
  void node.offsetWidth;  // restart the animation if it is already applied
  node.classList.add("flash");
  node.addEventListener("animationend", () => node.classList.remove("flash"), { once: true });
}

function celebrate(big, ...nodes) {
  for (const n of nodes) flash(n);
  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) confetti(big ? 260 : 120);
}

// square, unrotated bits on the same 2px grid as the rest of the site
function confetti(count) {
  const canvas = document.createElement("canvas");
  canvas.id = "confetti";
  document.body.appendChild(canvas);
  const dpr = window.devicePixelRatio || 1;
  canvas.width = innerWidth * dpr;
  canvas.height = innerHeight * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  const colors = ["#f6cd57", "#ffe9a3", "#e3ad32", "#a8741a", "#6abf69", "#e8573f", "#5b9bd5"];
  // two bursts from the bottom corners, aimed up and inward
  const bits = Array.from({ length: count }, (_, i) => {
    const left = i % 2 === 0;
    const angle = (left ? -60 : -120) * Math.PI / 180 + (Math.random() - 0.5) * 0.9;
    const speed = 9 + Math.random() * 9;
    return {
      x: left ? 0 : innerWidth, y: innerHeight * 0.9,
      vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
      size: 2 * (2 + Math.floor(Math.random() * 4)), blink: Math.random() * 10,
      color: colors[Math.floor(Math.random() * colors.length)],
    };
  });
  const start = performance.now();
  function frame(now) {
    const t = now - start;
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    ctx.globalAlpha = Math.max(0, Math.min(1, (3000 - t) / 800));
    for (const b of bits) {
      b.vy += 0.25;
      b.vx *= 0.99;
      b.x += b.vx;
      b.y += b.vy;
      // snap to a 2px grid; every so often a bit "flips" to its thin side, like a sprite turning
      const thin = Math.floor((t / 90 + b.blink) % 4) === 0;
      ctx.fillStyle = b.color;
      ctx.fillRect(Math.round(b.x / 2) * 2, Math.round(b.y / 2) * 2, thin ? 2 : b.size, b.size);
    }
    if (t < 3000) requestAnimationFrame(frame);
    else canvas.remove();
  }
  requestAnimationFrame(frame);
}

//the problem list, from catalog.json (built by build.py). The home page lists every problem; a category's page calls
//showProblemList, which lists that category's problems in the sidebar, with a link back to the home page

let catalog = null, catalogLoading = null;

async function loadCatalog() {
  catalogLoading ||= fetch("/catalog.json").then((r) => r.json()).then((c) => (catalog = c));
  return catalogLoading;
}

// how much of each problem is done: 1 or 0 for a SQL challenge, the number of solved parts for an implementation one
const DONE = {
  sql: () => { const solved = new Set(storedJson("butterbricks:sql:progress", {}).solved || []); return (key) => (solved.has(key) ? 1 : 0); },
  implementation: () => { const solved = storedJson("butterbricks:implementation:progress", {}).solved || {}; return (key) => (solved[key] || []).length; },
};

function categoryDone(cat) {
  const done = DONE[cat.key]();
  return cat.groups.reduce((n, g) => n + g.problems.reduce((m, p) => m + done(p.key), 0), 0);
}

const problemHash = () => decodeURIComponent(location.hash.slice(1));

function setProblemHash(key) {
  if (problemHash() !== key) history.replaceState(null, "", `#${encodeURIComponent(key)}`);
  storage("butterbricks:last", `${location.pathname.split("/")[1]}/#${encodeURIComponent(key)}`);
}

function showProblemList(category, currentKey, onPick) {
  const bar = $("sidebar");
  if (!catalog || !bar) return;
  const cat = catalog.categories.find((c) => c.key === category);
  if (!cat) return;
  const done = DONE[cat.key]();
  bar.innerHTML = "";
  const head = el("div", "cat-head", `<a class="back-link" href="/">‹ All problems</a>` +
    `<span class="cat-line"><span class="cat-title">${esc(cat.title)}</span><span class="cat-count">${categoryDone(cat)}/${cat.total}</span></span>`);
  head.title = cat.blurb;
  bar.append(head);
  for (const group of cat.groups) {
    if (group.title) {
      const n = group.problems.filter((p) => done(p.key)).length;
      bar.append(el("h3", "group-head", `<span>${esc(group.title)}</span><span>${n}/${group.problems.length}</span>`));
    }
    for (const p of group.problems) {
      const here = p.key === currentKey;
      let item;
      if (p.parts) {
        item = el("button", `problem-link${here ? " current" : ""}${done(p.key) === p.parts ? " complete" : ""}`,
          `<span class="name">${esc(p.title)}</span><span class="sub">${esc(p.difficulty)} · ${plural(p.parts, "part")} · ~${p.minutes} min</span>`);
        const pips = el("span", "pips");
        for (let i = 0; i < p.parts; i++) pips.append(el("span", `pip${i < done(p.key) ? " done" : ""}`));
        item.append(pips);
        item.title = p.summary;
      } else {
        const solved = done(p.key) > 0;
        item = el("button", `challenge-link${solved ? " solved" : ""}${here ? " current" : ""}`,
          `<span class="mark">${solved ? "✓" : "○"}</span><span class="num">${p.num}</span><span>${esc(p.title)}</span>`);
      }
      item.onclick = () => onPick(p.key);
      bar.append(item);
    }
  }
  bar.querySelector(".current")?.scrollIntoView({ block: "nearest" });
}

//progression: XP for every solve, levels with butter titles, and a log of solves with dates (for the streak and the
//profile's recent activity). Everything is computed from the synced saves, so it follows the account

const ACTIVITY_KEY = "butterbricks:activity";
const XP_RULES = {
  sqlPerLevel: 10,      // a SQL challenge is worth 10 XP times its level: Level 1 is 10, Level 10 is 100
  implPart: 100,        // each implementation part
  implProblemBonus: 150 // on top, for finishing every part of a problem
};
const TITLES = ["Fresh Cream", "Churner", "Butter Pat", "Half Stick", "Full Stick", "Butter Block", "Bricklayer",
  "Butter Mason", "Golden Wall", "Butter Tower", "Butter Castle", "Butter Legend"];

// the XP needed to reach a level: 0, 100, 300, 600, 1000, ... (each level asks 100 more than the last)
const levelFloor = (level) => 50 * level * (level - 1);

function levelFor(xp) {
  let level = 1;
  while (levelFloor(level + 1) <= xp) level++;
  const floor = levelFloor(level), next = levelFloor(level + 1);
  return { level, title: TITLES[Math.min(level, TITLES.length) - 1], xp, floor, next, into: xp - floor, span: next - floor };
}

function activityLog() { return storedJson(ACTIVITY_KEY, []); }

// everything the profile shows, from the catalog and this browser's (synced) saves
function progressStats() {
  const stats = { xp: 0, sql: { solved: 0, total: 0, levels: [] }, impl: { parts: 0, totalParts: 0, done: 0, problems: [] } };
  if (!catalog) return { ...stats, ...levelFor(0) };
  for (const cat of catalog.categories) {
    const done = DONE[cat.key]();
    if (cat.key === "sql") {
      cat.groups.forEach((g, gi) => {
        const solved = g.problems.filter((p) => done(p.key)).length;
        stats.sql.levels.push({ title: g.title, solved, total: g.problems.length });
        stats.sql.solved += solved;
        stats.sql.total += g.problems.length;
        stats.xp += solved * XP_RULES.sqlPerLevel * (gi + 1);
      });
    } else if (cat.key === "implementation") {
      for (const p of cat.groups.flatMap((g) => g.problems)) {
        const parts = Math.min(done(p.key), p.parts);
        stats.impl.problems.push({ ...p, solvedParts: parts });
        stats.impl.parts += parts;
        stats.impl.totalParts += p.parts;
        stats.xp += parts * XP_RULES.implPart;
        if (parts === p.parts) { stats.impl.done++; stats.xp += XP_RULES.implProblemBonus; }
      }
    }
  }
  const log = activityLog();
  const days = new Set(log.map((a) => new Date(a.t).toDateString()));
  let streak = 0;
  for (const d = new Date(); ; d.setDate(d.getDate() - 1)) {
    if (days.has(d.toDateString())) streak++;
    else if (!(streak === 0 && d.toDateString() === new Date().toDateString())) break;  // today can still be pending
  }
  let seconds = 0;
  for (const k of syncedKeys()) if (/:time:/.test(k)) seconds += parseFloat(raw(k)) || 0;
  return { ...stats, ...levelFor(stats.xp), streak, activeDays: days.size, seconds, log,
    problemsSolved: stats.sql.solved + stats.impl.done };
}

// the XP one solve was worth, given the stats with it counted: a SQL challenge by its level, an implementation part
// ("<problem>#<part>") plus the bonus if it finished the problem
function solveXp(category, key, stats) {
  if (category === "sql") {
    const gi = catalog.categories.find((c) => c.key === "sql").groups.findIndex((g) => g.problems.some((p) => p.key === key));
    return gi < 0 ? 0 : XP_RULES.sqlPerLevel * (gi + 1);
  }
  const p = stats.impl.problems.find((x) => x.key === key.split("#")[0]);
  return XP_RULES.implPart + (p && p.solvedParts === p.parts ? XP_RULES.implProblemBonus : 0);
}

// called by a category page right after it saves a first-time solve: logs it, and celebrates a new level
function logSolve(category, key, label) {
  const log = activityLog();
  log.unshift({ t: Date.now(), c: category, k: key, label });
  storage(ACTIVITY_KEY, JSON.stringify(log.slice(0, 300)));
  if (!catalog) return;
  const now = progressStats();
  const before = levelFor(now.xp - solveXp(category, key, now)).level;
  renderLevelBadge(now);
  if (now.level > before) toast(`Level up! You're a ${now.title} now (level ${now.level}).`);
}

function renderLevelBadge(stats = progressStats()) {
  const badge = $("level-badge");
  if (!badge) return;
  badge.textContent = `Lv ${stats.level}`;
  badge.title = `${stats.title} · ${stats.xp.toLocaleString()} XP`;
}

function toast(text) {
  const t = el("div", "toast", esc(text));
  document.body.append(t);
  setTimeout(() => t.classList.add("leaving"), 4200);
  setTimeout(() => t.remove(), 4800);
}

//accounts. Signing in is optional for practicing and required for submitting. A signed-in browser pulls the account's
//saves when a page loads and sends its own changes a moment after they happen; keys it couldn't send yet wait in
//SYNC_PENDING (in localStorage, so a closed tab doesn't lose them) and go first next time

const account = { online: false, user: null, signup: false };
let syncPending = new Set();
let flushTimer = null;

async function api(method, url, body, { keepalive = false } = {}) {
  const res = await fetch(url, {
    method, keepalive, credentials: "same-origin",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = {};
  try { data = await res.json(); } catch (e) {}
  if (!res.ok) {
    const err = new Error(data.error || `The server answered ${res.status}.`);
    err.status = res.status;
    throw err;
  }
  return data;
}

function savePending() { raw(SYNC_PENDING, syncPending.size ? JSON.stringify([...syncPending]) : null); }

function queueSync(key) {
  syncPending.add(key);
  savePending();
  if (!flushTimer) flushTimer = setTimeout(flush, 2000);
}

async function flush({ keepalive = false } = {}) {
  clearTimeout(flushTimer);
  flushTimer = null;
  if (!syncPending.size || !account.user) return true;
  const keys = [...syncPending];
  const changes = {};
  for (const k of keys) changes[k] = raw(k);
  syncPending.clear();
  savePending();
  syncState("saving");
  try {
    await api("PUT", "/api/saves", { changes }, { keepalive });
    syncState(syncPending.size ? "saving" : "saved");
    return true;
  } catch (e) {
    for (const k of keys) syncPending.add(k);
    savePending();
    if (e.status === 401) { account.user = null; renderAccount(); return false; }
    syncState("offline");
    if (!keepalive) flushTimer = setTimeout(flush, 15000);
    return false;
  }
}

// two versions of the same key, from this browser and from the account: progress and the solve log are the union of
// both, timers keep the larger total, and anything else (code, notes, drafts) takes the account's copy
function combine(key, mine, theirs) {
  try {
    if (/:progress$/.test(key)) {
      const a = JSON.parse(mine), b = JSON.parse(theirs);
      if (Array.isArray(b.solved)) b.solved = [...new Set([...(b.solved || []), ...(a.solved || [])])].sort();
      else for (const [k, parts] of Object.entries(a.solved || {})) {
        b.solved[k] = [...new Set([...(b.solved[k] || []), ...parts])].sort((x, y) => x - y);
      }
      return JSON.stringify(b);
    }
    if (/:time:/.test(key)) return String(Math.max(parseFloat(mine) || 0, parseFloat(theirs) || 0));
    if (key === ACTIVITY_KEY) {
      const seen = new Set(), both = [];
      for (const a of [...JSON.parse(theirs), ...JSON.parse(mine)]) if (!seen.has(`${a.t}|${a.k}`)) { seen.add(`${a.t}|${a.k}`); both.push(a); }
      return JSON.stringify(both.sort((x, y) => y.t - x.t).slice(0, 300));
    }
  } catch (e) {}
  return theirs;
}

function wipeLocal() {
  for (const k of syncedKeys()) raw(k, null);
  syncPending.clear();
  raw(SYNC_PENDING, null);
  raw(SYNC_USER, null);
}

// the first time this browser syncs with an account: what's saved here goes up, combined with what the account has
async function adopt(user) {
  const owner = raw(SYNC_USER);
  if (owner && owner !== user.username) wipeLocal();  // another account's saves: they're on the server already
  const { saves } = await api("GET", "/api/saves");
  const changes = {};
  for (const k of syncedKeys()) {
    const mine = raw(k);
    if (!(k in saves)) { changes[k] = mine; continue; }
    const both = combine(k, mine, saves[k]);
    if (both !== saves[k]) changes[k] = both;
    saves[k] = both;
  }
  for (const [k, v] of Object.entries(saves)) raw(k, v);
  if (Object.keys(changes).length) await api("PUT", "/api/saves", { changes });
  raw(SYNC_USER, user.username);
  syncPending.clear();
  savePending();
}

// every later page load: send what's pending, then take the account's copy of everything else
async function pull() {
  await flush();
  const { saves } = await api("GET", "/api/saves");
  for (const k of syncedKeys()) if (!(k in saves) && !syncPending.has(k)) raw(k, null);
  for (const [k, v] of Object.entries(saves)) if (!syncPending.has(k)) raw(k, v);
}

async function startAccount() {
  syncPending = new Set(storedJson(SYNC_PENDING, []));
  try {
    const me = await api("GET", "/api/me");
    Object.assign(account, { online: true, user: me.user, signup: me.signup });
  } catch (e) {
    account.online = false;  // no server (a plain static copy of web/): everything stays in this browser
  }
  if (account.user) {
    try {
      if (raw(SYNC_USER) === account.user.username) await pull();
      else await adopt(account.user);
    } catch (e) { syncState("offline"); }
  }
  renderAccount();
  addEventListener("pagehide", () => flush({ keepalive: true }));
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") flush({ keepalive: true }); });
}

function syncState(state) {
  const node = $("sync-state");
  if (!node) return;
  node.textContent = { saving: "saving…", saved: "saved", offline: "not saved yet" }[state] || "";
  node.className = `sync-state ${state}`;
  node.title = state === "offline" ? "Couldn't reach the server. Your changes are kept here and sent when it's back." : "Saved to your account";
}

function renderAccount() {
  let box = $("account");
  if (!box) {
    box = el("div", "account");
    box.id = "account";
    document.querySelector(".titlebar")?.append(box);
  }
  box.innerHTML = "";
  if (!account.online) return;
  if (account.user) {
    const who = el("a", "who", `<span class="level-badge" id="level-badge">Lv ·</span> ${esc(account.user.username)}`);
    who.href = "/profile/";
    who.title = "Your profile";
    box.append(who, el("span", "sync-state", ""));
    box.lastChild.id = "sync-state";
    loadCatalog().then(() => renderLevelBadge(), () => {});
    const out = el("button", "btn ghost small", "Sign out");
    out.onclick = signOut;
    box.append(out);
    syncState(syncPending.size ? "saving" : "saved");
  } else {
    const inBtn = el("button", "btn primary small", "Sign in");
    inBtn.onclick = () => openAccountBox();
    box.append(inBtn);
  }
}

async function signOut() {
  await flush();
  try { await api("POST", "/api/logout", {}); } catch (e) {}
  storageFrozen = true;
  wipeLocal();  // so the next person on this browser doesn't see your work
  location.reload();
}

// resolves true if signed in (or there's no server to sign in to); otherwise opens the sign-in box and resolves false
async function requireSignIn(reason) {
  if (account.user || !account.online) return true;
  openAccountBox(reason);
  return false;
}

function openAccountBox(reason = "") {
  if ($("account-box")) return;
  let mode = "signin";
  const backdrop = el("div", "modal-backdrop");
  backdrop.id = "account-box";
  backdrop.innerHTML = `<form class="modal panel" novalidate>
    <div class="modal-head"><img class="logo" src="${esc(document.querySelector('link[rel="icon"]')?.href || "")}" alt=""><span class="wordmark">Butterbricks</span></div>
    <div class="modal-tabs">
      <button type="button" class="on" data-mode="signin">Sign in</button>
      <button type="button" data-mode="signup">Create account</button>
    </div>
    ${reason ? `<p class="modal-reason">${esc(reason)}</p>` : ""}
    <label>Username <input name="username" autocomplete="username" required></label>
    <label>Password <input name="password" type="password" autocomplete="current-password" required></label>
    <label class="invite" hidden>Invite code <input name="invite" autocomplete="off"></label>
    <div class="modal-error" hidden></div>
    <div class="modal-actions">
      <button type="button" class="btn ghost" data-close>Cancel</button>
      <button type="submit" class="btn primary">Sign in</button>
    </div>
    <p class="muted small modal-note">Progress you've saved in this browser joins your account when you sign in.</p>
  </form>`;
  document.body.append(backdrop);
  const form = backdrop.querySelector("form");
  const errorBox = form.querySelector(".modal-error");
  const close = () => backdrop.remove();
  const setMode = (m) => {
    mode = m;
    for (const b of form.querySelectorAll("[data-mode]")) b.classList.toggle("on", b.dataset.mode === m);
    form.querySelector(".invite").hidden = m !== "signup";
    form.password.autocomplete = m === "signup" ? "new-password" : "current-password";
    form.querySelector('[type="submit"]').textContent = m === "signup" ? "Create account" : "Sign in";
    errorBox.hidden = true;
  };
  for (const b of form.querySelectorAll("[data-mode]")) b.onclick = () => setMode(b.dataset.mode);
  if (!account.signup) form.querySelector('[data-mode="signup"]').hidden = true;
  form.querySelector("[data-close]").onclick = close;
  backdrop.addEventListener("mousedown", (e) => { if (e.target === backdrop) close(); });
  backdrop.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  form.onsubmit = async (e) => {
    e.preventDefault();
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    errorBox.hidden = true;
    try {
      const body = { username: form.username.value.trim(), password: form.password.value };
      if (mode === "signup") body.invite = form.invite.value.trim();
      const { user } = await api("POST", mode === "signup" ? "/api/signup" : "/api/login", body);
      account.user = user;
      await adopt(user);
      location.reload();
    } catch (err) {
      errorBox.textContent = err.message;
      errorBox.hidden = false;
      submit.disabled = false;
    }
  };
  form.username.focus();
}

const ready = startAccount();
