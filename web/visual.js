"use strict";

// the step-through visualizer: plays a trace recorded by categories/framework/trace.py, drawing every variable as
// what it is (a list as cells with the loop's position under them, a set as a hash table with its buckets, a dict as
// a key → value table, an object as its fields) and showing what changed since the step before. Used by the worked
// example's stepper and by every worked example on a Learn page. makePlayer() is the entry point; it needs common.js
// (el, esc) and CodeMirror's runmode.

const MOVE_TAG = /[ \t]*# @([a-z][a-z0-9-]*)[ \t]*$/;

// code with its move tags taken off: [{ text, tag }]
function taggedLines(src) {
  return src.replace(/\n$/, "").split("\n").map((line) => {
    const m = line.match(MOVE_TAG);
    return { text: m ? line.slice(0, m.index) : line, tag: m ? m[1] : null };
  });
}

const stripTags = (src) => taggedLines(src).map((l) => l.text).join("\n");

// the color class for a move: its place in the lesson's list, so a move has the same color everywhere
function moveClass(tag, moves) {
  if (!tag) return "";
  if (tag === "slow") return "m-slow";
  const i = (moves || []).findIndex((m) => m.key === tag);
  return i < 0 ? "" : `m-${i + 1}`;
}

// code as lines, each tinted by its move, with the move's name on the first line of each tinted run
function annotatedCode(src, moves, { labels = true, numbers = false } = {}) {
  const box = el("div", "acode");
  const lines = [];
  let prev = null;
  taggedLines(src).forEach(({ text, tag }, i) => {
    const row = el("div", `aline ${moveClass(tag, moves)}`);
    row.dataset.line = i + 1;
    if (numbers) row.append(el("span", "lnum", String(i + 1)));
    const code = el("span", "atext");
    CodeMirror.runMode(text || " ", "python", code);
    row.append(code);
    if (labels && tag && tag !== prev) {
      const k = (moves || []).findIndex((m) => m.key === tag);
      if (k >= 0) row.append(el("span", "move-chip", `${k + 1} · ${esc(moves[k].label)}`));
      else if (tag === "slow") row.append(el("span", "move-chip", "the slow part"));
    }
    prev = tag;
    box.append(row);
    lines.push(row);
  });
  return { box, lines };
}

//values

const pyStr = (v) => `'${v.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}'`;
const sameSnap = (a, b) => JSON.stringify(a) === JSON.stringify(b);

// a snapshot as short inline text (html)
function snapHTML(s, quote = true) {
  switch (s.t) {
    case "str": return `<span class="s-str">${esc(quote ? pyStr(s.v) : s.v)}</span>`;
    case "int": case "float": return `<span class="s-num">${esc(s.v)}</span>`;
    case "bool": return `<span class="s-kw">${s.v ? "True" : "False"}</span>`;
    case "none": return `<span class="s-kw">None</span>`;
    case "list": case "deque": case "tuple": {
      const [o, c] = s.t === "tuple" ? ["(", s.items.length === 1 ? ",)" : ")"] : ["[", "]"];
      return `${s.t === "deque" ? "deque(" : ""}${o}${s.items.map((x) => snapHTML(x)).join(", ")}${s.more ? `, …+${s.more}` : ""}${c}${s.t === "deque" ? ")" : ""}`;
    }
    case "set": return s.items.length ? `{${s.items.map((x) => snapHTML(x)).join(", ")}}` : "set()";
    case "dict": return `{${s.entries.map(([k, v]) => `${snapHTML(k)}: ${snapHTML(v)}`).join(", ")}}`;
    case "obj": return `<span class="s-obj">${esc(s.cls)}</span>`;
    case "ref": return `<span class="s-obj">↺</span>`;
    default: return esc(s.v);
  }
}

// every variable as { name, snap }, an object's fields as self.<field>
function flatten(snap, hide = []) {
  const out = [];
  for (const [name, s] of Object.entries(snap || {})) {
    if (hide.includes(name)) continue;
    if (s.t === "obj" && name === "self") {
      for (const [f, v] of Object.entries(s.fields)) if (!hide.includes(`self.${f}`)) out.push({ name: `self.${f}`, snap: v });
    } else out.push({ name, snap: s });
  }
  return out;
}

//drawing one step

function drawStage(stage, step, prev, viz = {}, mem = {}) {
  stage.innerHTML = "";
  const gen = String((+stage.dataset.gen || 0) + 1);
  stage.dataset.gen = gen;
  const cursors = step.cursors || [];
  const events = step.events || [];
  const hide = viz.hide || [];
  const entries = flatten(step.snap, hide);
  const before = new Map(flatten(prev?.snap, hide).map((e) => [e.name, e.snap]));
  const pointers = viz.pointers || {};
  const isArray = (e) => ["list", "tuple", "deque"].includes(e.snap.t) ||
    (e.snap.t === "str" && cursors.some((c) => c.array === e.name && c.index < e.snap.v.length + 1));
  const scalars = entries.filter((e) => !isArray(e) && !["set", "dict"].includes(e.snap.t));
  const arrays = entries.filter(isArray);
  const tables = entries.filter((e) => ["set", "dict"].includes(e.snap.t));

  if (!entries.length) {
    stage.append(el("div", "v-empty muted small", step.op ? "Nothing to show until the call starts." : "No variables yet."));
    return;
  }
  if (scalars.length) {
    const strip = el("div", "v-scalars");
    for (const e of scalars) {
      const old = before.get(e.name);
      const cls = old === undefined ? (prev ? "new" : "") : !sameSnap(old, e.snap) ? "changed" : "";
      strip.append(el("span", `v-scalar ${cls}`, `<span class="v-name">${esc(e.name)}</span> = ${snapHTML(e.snap)}`));
    }
    stage.append(strip);
  }
  const cellsByArray = new Map();
  if (arrays.length) {
    const col = el("div", "v-arrays");
    for (const e of arrays) col.append(drawArray(e, before.get(e.name), cursors, pointers[e.name] || [], step, cellsByArray));
    stage.append(col);
  }
  const rowsByDict = new Map();
  if (tables.length) {
    const row = el("div", "v-tables");
    for (const e of tables) {
      const lookup = events.find((ev) => ev.kind === "lookup" && ev.in === e.name);
      row.append(e.snap.t === "set" ? drawSet(e, before.get(e.name), lookup) : drawDict(e, before.get(e.name), lookup, rowsByDict));
    }
    stage.append(row);
  }
  flip(stage, cellsByArray, mem);
  const links = Object.entries(viz.indexes || {});
  if (links.length) requestAnimationFrame(() => { if (stage.dataset.gen === gen) drawLinks(stage, links, rowsByDict, cellsByArray, events); });
}

function drawArray(e, old, cursors, pointerNames, step, cellsByArray) {
  const s = e.snap;
  const items = s.t === "str" ? [...s.v].map((ch) => ({ t: "str", v: ch })) : s.items;
  const oldItems = !old ? null : old.t === "str" ? [...old.v].map((ch) => ({ t: "str", v: ch })) : old.items || [];
  const box = el("div", "v-box v-arraybox");
  box.append(el("div", "v-title", `${esc(e.name)}${s.t === "deque" ? ' <span class="muted">deque: front at the left</span>' : ""}`));
  const row = el("div", "v-array");
  const marks = {};
  for (const c of cursors.filter((c) => c.array === e.name)) (marks[c.index] ||= []).push(c.label);
  for (const name of pointerNames) {
    const v = step.snap?.[name];
    if (v && v.t === "int") (marks[v.v] ||= []).push(name);
  }
  const cells = [];
  items.forEach((x, i) => {
    const changed = oldItems && (i >= oldItems.length || !sameSnap(oldItems[i], x));
    const cell = el("div", `v-cell${changed ? " changed" : ""}${marks[i] ? " at" : ""}`);
    cell.append(el("div", "v-val", snapHTML(x, false)));
    cell.append(el("div", "v-idx", String(i)));
    if (marks[i]) cell.append(el("div", "v-mark", marks[i].map((m) => `▲ ${esc(m)}`).join("<br>")));
    cell.dataset.key = JSON.stringify(x);
    row.append(cell);
    cells.push(cell);
  });
  if (s.more) row.append(el("div", "v-cell more", `<div class="v-val">+${s.more}</div>`));
  if (!items.length) row.append(el("div", "v-cell empty", `<div class="v-val muted">empty</div>`));
  const end = Object.keys(marks).map(Number).filter((k) => k >= items.length);
  if (end.length) row.append(el("div", "v-cell end at", `<div class="v-val muted">end</div><div class="v-idx"></div><div class="v-mark">${end.flatMap((k) => marks[k]).map((m) => `▲ ${esc(m)}`).join("<br>")}</div>`));
  box.append(row);
  cellsByArray.set(e.name, cells);
  return box;
}

const BUCKETS = 8;

function drawSet(e, old, lookup) {
  const s = e.snap;
  const box = el("div", "v-box v-setbox");
  box.append(el("div", "v-title", `${esc(e.name)} <span class="muted">${s.cls || "set"}: ${s.items.length + (s.more || 0)} item${s.items.length === 1 ? "" : "s"}</span>`));
  const oldKeys = new Set((old?.items || []).map((x) => JSON.stringify(x)));
  const table = el("div", "v-buckets");
  for (let b = 0; b < BUCKETS; b++) {
    const probe = lookup && lookup.bucket === b;
    const row = el("div", `v-bucket${probe ? ` probe ${lookup.found ? "found" : "miss"}` : ""}`);
    row.append(el("span", "v-bnum", String(b)));
    const chips = el("span", "v-chips");
    s.items.forEach((x, i) => {
      if (s.buckets[i] !== b) return;
      const hit = probe && lookup.found && sameSnap(x, lookup.key);
      chips.append(el("span", `v-chip${old && !oldKeys.has(JSON.stringify(x)) ? " new" : ""}${hit ? " hit" : ""}`, snapHTML(x, false)));
    });
    row.append(chips);
    if (probe) row.append(el("span", "v-probe", `${snapHTML(lookup.key, false)} ${lookup.found ? "is here ✓" : "isn't here"}`));
    table.append(row);
  }
  box.append(table);
  if (lookup) box.append(el("div", "v-caption", `<code>${esc(lookup.expr)}</code> hashes to bucket ${lookup.bucket}: only that bucket is checked, so the lookup takes the same time however many items there are.`));
  return box;
}

function drawDict(e, old, lookup, rowsByDict) {
  const s = e.snap;
  const box = el("div", "v-box v-dictbox");
  const n = s.entries.length + (s.more || 0);
  box.append(el("div", "v-title", `${esc(e.name)} <span class="muted">${s.cls || "dict"}: ${n} key${n === 1 ? "" : "s"}</span>`));
  const oldMap = new Map((old?.entries || []).map(([k, v]) => [JSON.stringify(k), v]));
  const table = el("table", "v-dict");
  const rows = new Map();
  for (const [k, v] of s.entries) {
    const key = JSON.stringify(k);
    const isNew = old && !oldMap.has(key);
    const changed = old && !isNew && !sameSnap(oldMap.get(key), v);
    const hit = lookup && lookup.found && sameSnap(k, lookup.key);
    const tr = el("tr", `${isNew ? "new" : changed ? "changed" : ""}${hit ? " hit" : ""}`);
    tr.append(el("td", "v-key", snapHTML(k, false)));
    const val = el("td", "v-dval");
    val.innerHTML = ["list", "tuple"].includes(v.t) ? `<span class="v-mini">${v.items.map((x) => `<span>${snapHTML(x, false)}</span>`).join("") || '<span class="muted">empty</span>'}</span>` : snapHTML(v);
    tr.append(val);
    table.append(tr);
    rows.set(key, { tr, val, v });
  }
  if (!s.entries.length) table.append(el("tr", "", `<td class="muted" colspan="2">empty</td>`));
  if (lookup && !lookup.found) table.append(el("tr", "ghost", `<td class="v-key">${snapHTML(lookup.key, false)}</td><td class="muted">not in ${esc(e.name)}</td>`));
  box.append(table);
  if (lookup) box.append(el("div", "v-caption", `<code>${esc(lookup.expr)}</code>: ${lookup.found ? "found" : "not there"}, in one lookup.`));
  rowsByDict.set(e.name, rows);
  return box;
}

// moved cells slide from where they were: a swap-remove shows the last item travelling into the gap
function flip(stage, cellsByArray, mem) {
  const before = mem.rects || new Map();
  const after = new Map();
  requestAnimationFrame(() => {
    const base = stage.getBoundingClientRect();
    for (const [name, cells] of cellsByArray) {
      const seen = new Map();
      for (const cell of cells) {
        const n = seen.get(cell.dataset.key) || 0;
        seen.set(cell.dataset.key, n + 1);
        const id = `${name}|${cell.dataset.key}|${n}`;
        const r = cell.getBoundingClientRect();
        const pos = { x: r.left - base.left, y: r.top - base.top };
        after.set(id, pos);
        const was = before.get(id);
        if (mem.animate && was && (Math.abs(was.x - pos.x) > 2 || Math.abs(was.y - pos.y) > 2) && cell.animate) {
          cell.animate([{ transform: `translate(${was.x - pos.x}px, ${was.y - pos.y}px)` }, { transform: "none" }],
            { duration: 420, easing: "cubic-bezier(.2,.7,.2,1)" });
        }
      }
    }
    mem.rects = after;
  });
}

// arrows from a dict's values to the list positions they hold (an index map pointing back into its list)
function drawLinks(stage, links, rowsByDict, cellsByArray, events) {
  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.classList.add("v-links");
  const base = stage.getBoundingClientRect();
  svg.setAttribute("width", stage.scrollWidth);
  svg.setAttribute("height", stage.scrollHeight);
  svg.innerHTML = `<defs><marker id="v-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" class="v-arrowhead"/></marker></defs>`;
  for (const [dictName, arrayName] of links) {
    const rows = rowsByDict.get(dictName);
    const cells = cellsByArray.get(arrayName);
    if (!rows || !cells) continue;
    const lookup = (events || []).find((ev) => ev.kind === "lookup" && ev.in === dictName && ev.found);
    for (const [key, { val, v }] of rows) {
      if (v.t !== "int" || !cells[v.v]) continue;
      const a = val.getBoundingClientRect();
      const b = cells[v.v].getBoundingClientRect();
      const x1 = a.left - base.left + 4, y1 = a.top - base.top + a.height / 2;
      const x2 = b.left - base.left + b.width / 2, y2 = b.bottom - base.top - 2;
      const path = document.createElementNS(svgNS, "path");
      const midY = Math.max(y1, y2) + 24;
      path.setAttribute("d", `M${x1},${y1} C${x1 - 40},${y1} ${x2},${midY} ${x2},${y2}`);
      path.setAttribute("class", `v-link${lookup && JSON.stringify(lookup.key) === key ? " hot" : ""}`);
      path.setAttribute("marker-end", "url(#v-arrow)");
      svg.append(path);
    }
  }
  stage.append(svg);
}

//the player: the drawing, the code with the current line, the note, and the controls

function makePlayer(host, opts) {
  const P = { i: 0, trace: opts.trace, timer: null, mem: {}, original: opts.trace };
  const moves = opts.moves || [];
  const box = el("div", `vplayer${opts.compact ? " compact" : ""}`);
  box.tabIndex = 0;
  const bar = el("div", "vp-bar");
  const stage = el("div", "vp-stage");
  const note = el("div", "vp-note");
  const code = annotatedCode(opts.code, moves, { labels: true, numbers: true });
  const codeBox = el("div", "vp-code");
  codeBox.append(code.box);
  const controls = el("div", "vp-controls");
  const footer = el("div", "vp-footer");
  box.append(bar, stage, note, codeBox, controls, footer);
  host.append(box);

  // the call, editable when Python is available on the page
  const callText = el("span", "vp-call");
  const count = el("span", "vp-count muted small");
  bar.append(callText);
  let input = null;
  if (opts.custom) {
    callText.innerHTML = `<code>${esc(opts.custom.function)}(</code>`;
    input = el("input", "vp-input");
    input.value = opts.custom.args;
    input.spellcheck = false;
    input.title = "Change the input and press Enter to watch it run on yours";
    const close = el("code", "", ")");
    const run = el("button", "btn small", "Run it");
    const reset = el("button", "btn ghost small", "↺");
    reset.title = "back to the original input";
    run.onclick = () => retrace();
    reset.onclick = () => { input.value = opts.custom.args; load(P.original); };
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); retrace(); } e.stopPropagation(); });
    bar.append(input, close, run, reset);
  } else {
    callText.innerHTML = `<code>${esc(opts.trace.script?.length > 1 ? `${opts.trace.script.length - 1} operations on ${opts.trace.call}` : opts.trace.call)}</code>`;
  }
  bar.append(el("span", "spacer"), count);

  const btn = (label, title, fn) => { const b = el("button", "btn small", label); b.title = title; b.onclick = fn; controls.append(b); return b; };
  const first = btn("⏮", "first step", () => go(0));
  const back = btn("◀", "back a step (←)", () => go(P.i - 1));
  const play = btn("▶ Play", "play (space)", () => toggle());
  const fwd = btn("▶", "next step (→)", () => go(P.i + 1));
  const key = btn("Next key moment ⤳", "jump to the next step where the pattern does something", () => {
    const k = keySteps().find((j) => j > P.i);
    go(k ?? P.trace.steps.length - 1);
  });
  if (!moves.length) key.hidden = true;
  const speed = el("select", "vp-speed");
  for (const [v, l] of [[1400, "slow"], [800, "normal"], [400, "fast"]]) speed.append(new Option(l, v));
  speed.value = "800";
  speed.title = "playback speed";
  controls.append(speed);
  const scrubWrap = el("div", "vp-scrub");
  const scrub = el("input");
  scrub.type = "range";
  scrub.min = 0;
  scrub.oninput = () => go(+scrub.value, true);
  const ticks = el("div", "vp-ticks");
  scrubWrap.append(ticks, scrub);
  controls.append(scrubWrap);

  function tagOf(step) { return step.line ? taggedLines(opts.code)[step.line - 1]?.tag : null; }
  function keySteps() { return P.trace.steps.map((s, j) => (tagOf(s) || s.events ? j : -1)).filter((j) => j >= 0); }

  function load(trace) {
    stop();
    P.trace = trace;
    P.mem = {};
    scrub.max = trace.steps.length - 1;
    ticks.innerHTML = "";
    const n = Math.max(trace.steps.length - 1, 1);
    for (const j of keySteps()) {
      const t = el("span", `vp-tick ${moveClass(tagOf(trace.steps[j]), moves)}`);
      t.style.left = `${(100 * j) / n}%`;
      ticks.append(t);
    }
    go(0, true);
  }

  async function retrace() {
    if (!opts.custom.py) return;
    note.innerHTML = `<span class="muted">${opts.custom.py.readyDone ? "Running…" : "Waiting for Python to load…"}</span>`;
    try {
      const t = await opts.custom.py.call("trace", { source: opts.custom.source, function: opts.custom.function, args: input.value, notes: opts.custom.notes || {} }, 10000);
      if (t.error) { note.innerHTML = `<span class="v-error">${esc(t.error)}</span>`; return; }
      if (!t.steps.length) { note.innerHTML = `<span class="v-error">Nothing ran.</span>`; return; }
      load(t);
    } catch (e) {
      note.innerHTML = `<span class="v-error">${e.killed ? "That ran too long and was stopped." : esc(e.message)}</span>`;
    }
  }

  function go(i, jump = false) {
    if (opts.locked?.()) return;
    const steps = P.trace.steps;
    i = Math.max(0, Math.min(steps.length - 1, i));
    P.mem.animate = !jump && i === P.i + 1;
    P.i = i;
    render();
  }

  function render() {
    const steps = P.trace.steps;
    const i = P.i;
    const step = steps[i];
    const last = i === steps.length - 1;
    const prev = i > 0 ? steps.slice(0, i).reverse().find((s) => s.snap && Object.keys(s.snap).length) : null;
    drawStage(stage, step, prev, opts.viz || {}, P.mem);
    for (const l of code.lines) l.classList.remove("cur");
    const line = step.line ? code.lines[step.line - 1] : null;
    if (line) {
      line.classList.add("cur");
      const top = line.offsetTop - codeBox.offsetTop;
      if (top < codeBox.scrollTop || top > codeBox.scrollTop + codeBox.clientHeight - line.offsetHeight) codeBox.scrollTop = top - codeBox.clientHeight / 3;
    }
    const tag = tagOf(step);
    const mi = moves.findIndex((m) => m.key === tag);
    let text;
    if (step.op) text = `<b>Calling</b> <code>${esc(step.op)}</code>`;
    else if (step.returns !== undefined) text = `<b>Returns</b> <code>${esc(step.returns)}</code>${last && P.trace.truncated ? "" : ""}`;
    else text = `${mi >= 0 ? `<span class="move-chip ${moveClass(tag, moves)}">${mi + 1} · ${esc(moves[mi].label)}</span> ` : ""}${step.note ? esc(step.note) : `<span class="muted">Line ${step.line}${step.in && opts.kind === "class" ? ` in ${esc(step.in)}()` : ""}.</span>`}`;
    for (const ev of step.events || []) {
      if (ev.kind === "lookup") text += ` <span class="v-ev ${ev.found ? "found" : "miss"}"><code>${esc(ev.expr)}</code> is ${ev.found ? "there" : "not there"}</span>`;
    }
    if (last && P.trace.truncated) text += ` <span class="v-error">Stopped after ${steps.length} steps.</span>`;
    note.innerHTML = text;
    count.textContent = `step ${i + 1} of ${steps.length}`;
    scrub.value = i;
    first.disabled = back.disabled = i === 0;
    fwd.disabled = last;
    if (last) stop();
    footer.innerHTML = "";
    opts.onStep?.(i, steps.length, footer);
  }

  function toggle() { P.timer ? stop() : start(); }
  function start() {
    if (P.i >= P.trace.steps.length - 1) go(0, true);
    play.textContent = "❚❚ Pause";
    const tick = () => {
      if (P.i >= P.trace.steps.length - 1) return stop();
      go(P.i + 1);
      P.timer = setTimeout(tick, +speed.value);
    };
    P.timer = setTimeout(tick, +speed.value / 2);
  }
  function stop() {
    clearTimeout(P.timer);
    P.timer = null;
    play.textContent = "▶ Play";
  }

  box.addEventListener("keydown", (e) => {
    if (e.target.closest("input, select")) return;
    if (e.key === "ArrowRight") { e.preventDefault(); go(P.i + 1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); go(P.i - 1); }
    else if (e.key === " ") { e.preventDefault(); toggle(); }
  });

  load(opts.trace);
  return {
    el: box,
    next: () => go(P.i + 1),
    back: () => go(P.i - 1),
    toggle,
    stop,
    refresh: () => render(),
    get step() { return P.i; },
    get last() { return P.i === P.trace.steps.length - 1; },
  };
}
