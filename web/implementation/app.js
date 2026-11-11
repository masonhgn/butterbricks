"use strict";

const S = {
  files: [], problems: [],
  problem: null,       // the open problem's manifest
  part: 1,             // the part runs and submits target
  running: false,
  timer: { paused: false, last: Date.now() },
};

let cm;

//helpers (the shared ones are in ../common.js)

function md(text) {
  const box = el("div", "", marked.parse(text.trim()));
  for (const code of box.querySelectorAll("pre code")) {
    const src = code.textContent;
    code.textContent = "";
    CodeMirror.runMode(src, "python", code);
  }
  return box;
}

//python runs in a web worker (worker.js); a test that runs far past its limit is stopped by killing the worker

let worker, workerReady, nextCall = 0;
const pending = new Map();

function startWorker() {
  worker = new Worker("worker.js?v=bb-1");
  worker.onmessage = ({ data }) => {
    const p = pending.get(data.id);
    if (!p) return;
    pending.delete(data.id);
    clearTimeout(p.timer);
    if (data.error !== undefined) p.reject(new Error(data.error));
    else p.resolve(data.value);
  };
  worker.onerror = (e) => pyStatus("error", "Python failed to load");
  pyStatus("busy", "Loading Python…");
  workerReady = call("init", { files: S.files }).then((version) => {
    pyStatus("ready", `Python ${version} ready`);
  }, (e) => {
    pyStatus("error", "Python failed to load");
    throw e;
  });
}

function call(op, args, timeout) {
  return new Promise((resolve, reject) => {
    const id = nextCall++;
    const p = { resolve, reject };
    if (timeout) p.timer = setTimeout(() => {
      pending.delete(id);
      worker.terminate();
      for (const q of pending.values()) { clearTimeout(q.timer); q.reject(new Error("Python was restarted")); }
      pending.clear();
      startWorker();
      const err = new Error("killed");
      err.killed = true;
      reject(err);
    }, timeout);
    pending.set(id, p);
    worker.postMessage({ id, op, args });
  });
}

async function python(op, args, timeout) {
  await workerReady;
  return call(op, args, timeout);
}

function pyStatus(kind, text) {
  const s = $("py-status");
  s.className = `py-status ${kind}`;
  s.textContent = text;
}

//progress: which parts of which problems are solved, plus code, notes and timers per problem, all in localStorage

const PROGRESS_KEY = "butterbricks:implementation:progress";

function progress() {
  return storedJson(PROGRESS_KEY, { solved: {}, current: null });
}

function saveProgress(p) {
  storage(PROGRESS_KEY, JSON.stringify(p));
}

function solvedParts(key) {
  return new Set(progress().solved[key] || []);
}

function unlockedThrough(problem) {
  const solved = solvedParts(problem.key);
  let n = 1;
  while (n < problem.parts.length && solved.has(n)) n++;
  return n;
}

function markSolved(key, part) {
  const p = progress();
  const parts = new Set(p.solved[key] || []);
  const first = !parts.has(part);
  parts.add(part);
  p.solved[key] = [...parts].sort((a, b) => a - b);
  saveProgress(p);
  return first;
}

const codeKey = (k) => `butterbricks:implementation:code:${k}`;
const notesKey = (k) => `butterbricks:implementation:notes:${k}`;
const timeKey = (k) => `butterbricks:implementation:time:${k}`;
const partKey = (k) => `butterbricks:implementation:part:${k}`;
const revealKey = (k) => `butterbricks:implementation:revealed:${k}`;
const scratchKey = (k) => `butterbricks:implementation:scratch:${k}`;

//sidebar

function renderSidebar() {
  showProblemList("implementation", S.problem?.key, openProblem);
  const total = S.problems.reduce((n, p) => n + p.parts.length, 0);
  const done = S.problems.reduce((n, p) => n + solvedParts(p.key).size, 0);
  $("progress-text").textContent = `${done} / ${total} Implementation parts`;
  $("progress-fill").style.width = `${(100 * done) / total}%`;
}

//problem pane

function openProblem(key) {
  if (S.running) return;
  if (S.problem) saveCode();
  const problem = S.problems.find((p) => p.key === key) || S.problems[0];
  S.problem = problem;
  setProblemHash(problem.key);
  const p = progress();
  p.current = problem.key;
  saveProgress(p);

  const unlocked = unlockedThrough(problem);
  const stored = parseInt(storage(partKey(problem.key)), 10);
  S.part = stored >= 1 && stored <= unlocked ? stored : unlocked;

  $("problem-title").textContent = problem.title;
  const meta = $("problem-meta");
  meta.innerHTML = "";
  meta.append(el("span", `chip ${problem.difficulty}`, esc(problem.difficulty)));
  meta.append(el("span", "chip", `~${problem.minutes} min`));
  for (const t of problem.tags) meta.append(el("span", "chip", esc(t)));

  clearErrorLine();
  cm.setValue(storage(codeKey(problem.key)) ?? problem.starter);
  cm.clearHistory();
  $("notes").value = storage(notesKey(problem.key)) || "";
  $("scratch").value = storage(scratchKey(problem.key)) ?? defaultScratch(problem);
  $("scratch-output").textContent = "";

  const disc = $("discussion");
  disc.innerHTML = "";
  for (const q of problem.discussion) disc.append(el("li", "", esc(q)));

  renderSolution();
  renderStatement();
  clearResults();
  renderSidebar();
  renderTimer();
  showTab("left", "problem");
}

function setPart(n) {
  if (S.running) return;
  S.part = n;
  storage(partKey(S.problem.key), String(n));
  renderStatement();
  clearResults();
}

function renderStatement() {
  const problem = S.problem;
  const solved = solvedParts(problem.key);
  const unlocked = unlockedThrough(problem);

  const chips = $("part-chips");
  chips.innerHTML = "";
  problem.parts.forEach((part, i) => {
    const n = i + 1;
    const b = el("button", "part-chip", `${solved.has(n) ? "✓ " : n > unlocked ? "🔒 " : ""}Part ${n} · ${esc(part.title)}`);
    if (n === S.part) b.classList.add("on");
    if (solved.has(n)) b.classList.add("done");
    b.disabled = n > unlocked;
    b.title = n > unlocked ? "solve the previous part to unlock this one" : "";
    b.onclick = () => setPart(n);
    chips.append(b);
  });

  const body = $("statement");
  body.innerHTML = "";
  body.append(md(problem.intro));
  problem.parts.slice(0, unlocked).forEach((part, i) => {
    const n = i + 1;
    const sec = el("details", "part-section");
    sec.open = n === S.part;
    if (n === S.part) sec.classList.add("current");
    sec.append(el("summary", "", `Part ${n}: ${esc(part.title)} ${solved.has(n) ? '<span class="muted">✓ solved</span>' : ""}`));
    sec.append(md(part.statement));
    if (n === S.part && part.hints.length) sec.append(hintBox(part.hints));
    body.append(sec);
  });
  if (unlocked < problem.parts.length) {
    body.append(el("p", "muted", `${plural(problem.parts.length - unlocked, "more part")} unlock${problem.parts.length - unlocked === 1 ? "s" : ""} as you go. As in the interview, you don't see them until you get there.`));
  }
  const target = S.part > 1 ? `Runs tests for parts 1–${S.part}` : "Runs tests for part 1";
  $("run-target").textContent = target;
}

function hintBox(hints) {
  const box = el("div", "hint-box");
  let shown = 0;
  const btn = el("button", "btn small", `Show a hint (${hints.length} available)`);
  btn.onclick = () => {
    box.insertBefore(el("div", "hint", `<b>Hint ${shown + 1}.</b> ${esc(hints[shown])}`), btn);
    shown++;
    if (shown === hints.length) btn.remove();
    else btn.textContent = `Another hint (${hints.length - shown} left)`;
  };
  box.append(btn);
  return box;
}

function renderSolution() {
  const revealed = storage(revealKey(S.problem.key)) === "1";
  $("solution-locked").hidden = revealed;
  const body = $("solution-body");
  body.hidden = !revealed;
  body.innerHTML = "";
  if (!revealed) return;
  body.append(md(S.problem.writeup));
  body.append(el("h3", "", "Reference code"));
  body.append(highlighted(S.problem.reference, "python"));
  const hide = el("button", "btn small", "Hide again");
  hide.onclick = () => { storage(revealKey(S.problem.key), null); renderSolution(); };
  body.append(hide);
}

function defaultScratch(problem) {
  const test = problem.parts[0].tests.find((t) => t.preview.length);
  if (!test) return "# your solution is loaded here; try it out\n";
  const lines = test.preview.map((line, i) => {
    if (i === 0) return line;
    const [call, want] = line.split("  →  ");
    return want === undefined ? `print(${call})` : `print(${call})  # expect ${want}`;
  });
  return `# your solution's classes are in scope; experiment freely\n${lines.join("\n")}\n`;
}

//tabs and layout

function showTab(side, name) {
  const tabs = side === "left" ? $("left-tabs") : $("bottom-tabs");
  for (const t of tabs.querySelectorAll(".tab")) {
    t.classList.toggle("on", t.dataset.tab === name);
    $(`tab-${t.dataset.tab}`).hidden = t.dataset.tab !== name;
  }
  if (side === "left" && name === "notes") $("notes").focus();
}

//timer: time spent per problem, counted while the tab is visible and not paused

function renderTimer() {
  const secs = Math.floor(parseFloat(storage(timeKey(S.problem.key)) || "0"));
  const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60), s = secs % 60;
  const pad = (n) => String(n).padStart(2, "0");
  $("timer-text").textContent = h ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
  $("btn-timer").textContent = S.timer.paused ? "Resume" : "Pause";
  document.querySelector(".timer").classList.toggle("paused", S.timer.paused);
}

function tick() {
  const now = Date.now();
  const dt = (now - S.timer.last) / 1000;
  S.timer.last = now;
  if (!S.problem || S.timer.paused || document.visibilityState !== "visible" || dt > 5) return;
  const k = timeKey(S.problem.key);
  storage(k, String(parseFloat(storage(k) || "0") + dt));
  renderTimer();
}

//running tests

function saveCode() {
  storage(codeKey(S.problem.key), cm.getValue());
}

function clearResults() {
  $("results").innerHTML = "";
  $("results-summary").hidden = true;
  $("results-empty").hidden = false;
}

function testInfo(part, name) {
  return S.problem.parts[part - 1].tests.find((t) => t.name === name) || {};
}

function setBusy(busy) {
  S.running = busy;
  $("btn-run").disabled = busy;
  $("btn-submit").disabled = busy;
  $("btn-scratch").disabled = busy;
}

async function runTests(mode) {
  if (S.running || !S.problem) return;
  if (mode === "submit" && !(await requireSignIn("Sign in to submit. Your progress is saved to your account."))) return;
  saveCode();
  setBusy(true);
  clearErrorLine();
  showTab("bottom", "results");
  const problem = S.problem, part = S.part;
  const args = { key: problem.key, part, mode, source: cm.getValue() };
  const summary = $("results-summary");
  const list = $("results");
  $("results-empty").hidden = true;
  list.innerHTML = "";
  summary.hidden = false;
  summary.className = "results-summary running";
  summary.textContent = workerReadyDone ? "Loading your code…" : "Waiting for Python to load…";

  try {
    let plan = await python("prepare", args, 60000);
    if (plan.error) {
      summary.className = "results-summary fail";
      summary.textContent = "Your code didn't load";
      const box = el("div", "load-error");
      box.append(el("div", "msg", esc(plan.error)));
      if (plan.details.length) box.append(el("pre", "", esc(plan.details.join("\n"))));
      if (plan.where?.frames.length) box.append(variablesPanel(plan.where));
      list.append(box);
      showErrorLine(plan.where, plan.error);
      return;
    }
    const rows = plan.tests.map((t) => {
      const row = resultRow({ ...t, status: "pending" });
      list.append(row);
      return row;
    });
    summary.textContent = `Running ${plural(plan.tests.length, "test")}…`;

    const results = [];
    let firstFailShown = false;
    for (let i = 0; i < plan.tests.length; i++) {
      const t = plan.tests[i];
      rows[i].replaceWith(rows[i] = resultRow({ ...t, status: "running" }));
      let r;
      const hard = Math.round(t.time_limit * 3 + 8);
      try {
        r = await python("run", { i }, hard * 1000);
      } catch (e) {
        if (!e.killed) throw e;
        r = { ...t, status: "killed", message: `stopped after ${hard}s; the limit is ${t.time_limit}s`,
              details: ["Probably an infinite loop, or an approach that's far too slow for this input size."],
              elapsed: hard, metrics: [], notes: [], stdout: "" };
        summary.textContent = "Restarting Python after a stuck test…";
        if (i + 1 < plan.tests.length) await python("prepare", args, 60000);
      }
      results.push(r);
      const open = r.status !== "pass" && !firstFailShown;
      firstFailShown ||= open;
      if (r.where && !errorMark) showErrorLine(r.where, r.message);
      rows[i].replaceWith(rows[i] = resultRow(r, open));
      summary.textContent = `Running… ${results.length} / ${plan.tests.length}`;
    }
    finish(problem, part, mode, results);
  } catch (e) {
    summary.className = "results-summary fail";
    summary.textContent = `Something went wrong running the tests: ${e.message}`;
  } finally {
    setBusy(false);
  }
}

function finish(problem, part, mode, results) {
  const passed = results.filter((r) => r.status === "pass").length;
  const total = results.length;
  const secs = results.reduce((s, r) => s + (r.elapsed || 0), 0);
  const summary = $("results-summary");
  const all = passed === total;
  summary.className = `results-summary ${all ? "pass" : "fail"}`;
  const kind = mode === "submit" ? "tests" : "sample tests";
  summary.innerHTML = `${all ? "✓" : "✗"} ${passed} / ${total} ${kind} passed <span class="muted small">${secs.toFixed(2)}s</span>`;
  if (!all || mode !== "submit") {
    if (all) {
      const go = el("button", "btn small primary", "Submit");
      go.onclick = () => runTests("submit");
      summary.append(el("span", "small", "Samples pass. Submit to run the hidden tests."), go);
    }
    return;
  }
  const first = markSolved(problem.key, part);
  celebrate(part === problem.parts.length, summary, document.querySelector(".editor"));
  renderSidebar();
  renderStatement();
  const banner = el("div", "unlock");
  if (part < problem.parts.length) {
    banner.innerHTML = `<span><b>Part ${part} complete.</b> ${first ? `Part ${part + 1} is unlocked.` : ""}</span>`;
    const go = el("button", "btn primary", `Go to part ${part + 1} ›`);
    go.onclick = () => { setPart(part + 1); $("statement").querySelector(".part-section.current")?.scrollIntoView({ behavior: "smooth" }); };
    banner.append(go);
  } else {
    banner.innerHTML = `<span><b>${esc(problem.title)} complete.</b> Now go through the Discussion questions, then compare with the reference in Solution.</span>`;
    const go = el("button", "btn", "Discussion ›");
    go.onclick = () => showTab("left", "discussion");
    banner.append(go);
  }
  $("results").prepend(banner);
}

const ICONS = { pass: "✓", fail: "✗", error: "!", slow: "⏱", killed: "⏱", pending: "·", running: "◌", skipped: "–" };

function resultRow(r, open = false) {
  const row = el("div", `test-row st-${r.status}`);
  const head = el("button", "test-head");
  const time = r.elapsed !== undefined ? `${r.elapsed.toFixed(3)}s` : "";
  head.innerHTML = `<span class="icon">${ICONS[r.status]}</span>` +
    `<span class="tname">${esc(r.name)}${r.hidden ? '<span class="badge">hidden</span>' : ""}</span>` +
    `<span class="tpart">part ${r.part}</span><span class="time">${time}</span>`;
  row.append(head);
  if (r.status === "pending" || r.status === "running") return row;

  const body = el("div", "test-body");
  body.hidden = !open;
  head.onclick = () => {
    body.hidden = !body.hidden;
    if (!body.hidden && r.where) showErrorLine(r.where, r.message);
  };
  const info = testInfo(r.part, r.name);
  if (r.message) body.append(el("div", "msg", esc(r.message)));
  if (r.details && r.details.length) body.append(el("pre", "", esc(r.details.join("\n"))));
  if (r.where?.frames.length) body.append(variablesPanel(r.where));
  if (r.metrics && r.metrics.length) {
    const m = el("div", "metrics");
    for (const x of r.metrics) {
      m.append(el("span", `metric ${x.target == null ? "" : x.ok ? "ok" : "bad"}`,
        `${esc(x.name)}: <b>${esc(x.value)}</b>${x.context ? ` <span class="ctx">(${esc(x.context)})</span>` : ""}`));
    }
    body.append(m);
  }
  if (r.notes && r.notes.length) body.append(el("div", "muted small", esc(r.notes.join(" · "))));
  if (info.description) body.append(el("div", "muted small", esc(info.description)));
  if (info.preview && info.preview.length) {
    body.append(el("div", "label", "Input"));
    body.append(highlighted(info.preview.join("\n"), "python"));
  } else if (r.hidden) {
    body.append(el("div", "muted small", "Hidden test: the input isn't shown."));
  }
  if (r.stdout) {
    body.append(el("div", "label", "Your output (print)"));
    body.append(el("pre", "", esc(r.stdout)));
  }
  if (!body.children.length) body.append(el("div", "muted small", "Passed."));
  row.append(body);
  return row;
}

//the line an error came from, marked in red in the editor with the error message under it

let errorMark = null;

function clearErrorLine() {
  if (!errorMark) return;
  cm.removeLineClass(errorMark.handle, "background", "cm-error-line");
  cm.removeLineClass(errorMark.handle, "gutter", "cm-error-gutter");
  errorMark.widget.clear();
  errorMark = null;
}

function showErrorLine(where, message) {
  clearErrorLine();
  const n = (where?.line ?? 0) - 1;
  if (n < 0 || n >= cm.lineCount()) return;
  const handle = cm.addLineClass(n, "background", "cm-error-line");
  cm.addLineClass(handle, "gutter", "cm-error-gutter");
  const widget = cm.addLineWidget(handle, el("div", "cm-error-widget", esc(message || "error")));
  errorMark = { handle, widget };
  cm.scrollIntoView({ line: n, ch: 0 }, 80);
}

// gdb-style: every frame of the user's code the error passed through, innermost first, with its variables
function variablesPanel(where) {
  const box = el("div", "vars");
  box.append(el("div", "label", "Variables when the error happened"));
  [...where.frames].reverse().forEach((f, i) => {
    const frame = el("details", "frame");
    frame.open = i === 0;
    frame.append(el("summary", "", `<code>${esc(f.name)}</code> <span class="muted small">line ${f.line}${i === 0 ? ", where it failed" : ", calling the frame above"}</span>`));
    if (f.vars.length) {
      const table = el("table", "vars-table");
      for (const [name, value] of f.vars) {
        const tr = el("tr");
        tr.append(el("td", "vname", esc(name)), el("td", "vval", esc(value)));
        table.append(tr);
      }
      frame.append(table);
    } else {
      frame.append(el("div", "muted small", f.name === "<module>" ? "module level (not listed)" : "no variables"));
    }
    if (f.more) frame.append(el("div", "muted small", `… and ${plural(f.more, "more variable")}`));
    box.append(frame);
  });
  return box;
}

async function runScratch() {
  if (S.running) return;
  saveCode();
  storage(scratchKey(S.problem.key), $("scratch").value);
  setBusy(true);
  clearErrorLine();
  const out = $("scratch-output");
  out.className = "console-output muted";
  out.textContent = "Running…";
  try {
    const r = await python("scratch", { source: cm.getValue(), snippet: $("scratch").value }, 20000);
    out.className = `console-output${r.ok ? "" : " err"}`;
    out.textContent = r.output || (r.ok ? "(no output; use print)" : "");
    if (r.where) showErrorLine(r.where, r.output.trim().split("\n").pop());
  } catch (e) {
    out.className = "console-output err";
    out.textContent = e.killed ? "Stopped after 20s. Python was restarted." : e.message;
  } finally {
    setBusy(false);
  }
}

//startup

let workerReadyDone = false;

async function main() {
  cm = CodeMirror($("editor"), {
    ...EDITOR_DEFAULTS,
    mode: "python",
    autoCloseBrackets: true,
    extraKeys: editorKeys({
      "Ctrl-Enter": () => runTests("run"),
      "Cmd-Enter": () => runTests("run"),
      "Shift-Ctrl-Enter": () => runTests("submit"),
      "Shift-Cmd-Enter": () => runTests("submit"),
      "Ctrl-/": "toggleComment",
      "Cmd-/": "toggleComment",
    }),
  });
  let saveTimer;
  cm.on("change", () => { clearTimeout(saveTimer); saveTimer = setTimeout(saveCode, 400); });

  let data;
  try {
    data = await (await fetch("problems.json")).json();
  } catch (e) {
    $("statement").innerHTML = "<p>Couldn't load <code>problems.json</code>. Run <code>./serve.py</code> from the repo root, which builds it first.</p>";
    pyStatus("error", "No problems.json");
    return;
  }
  S.files = data.files;
  S.problems = data.problems;
  startWorker();
  workerReady.then(() => { workerReadyDone = true; }, () => {});

  for (const t of document.querySelectorAll(".tab")) {
    t.onclick = () => showTab(t.closest("#left-tabs") ? "left" : "bottom", t.dataset.tab);
  }
  $("btn-run").onclick = () => runTests("run");
  $("btn-submit").onclick = () => runTests("submit");
  $("btn-scratch").onclick = runScratch;
  $("scratch").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); runScratch(); }
  });
  $("notes").addEventListener("input", () => storage(notesKey(S.problem.key), $("notes").value));
  $("btn-reveal").onclick = () => { storage(revealKey(S.problem.key), "1"); renderSolution(); };
  armed($("btn-reset-code"), "Click again to replace your code", () => {
    clearErrorLine();
    cm.setValue(S.problem.starter);
    saveCode();
  });
  armed($("btn-reset-progress"), "Click again to erase everything", () => {
    try {
      for (const k of Object.keys(localStorage)) if (k.startsWith("butterbricks:implementation:")) storage(k, null);
    } catch (e) {}
    openProblem(S.problems[0].key);
  });
  $("btn-timer").onclick = () => {
    S.timer.paused = !S.timer.paused;
    storage("butterbricks:implementation:timer-paused", S.timer.paused ? "1" : null);
    renderTimer();
  };
  armed($("btn-timer-reset"), "Reset timer?", () => { storage(timeKey(S.problem.key), "0"); renderTimer(); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && !e.target.closest("textarea, .CodeMirror")) {
      e.preventDefault();
      runTests(e.shiftKey ? "submit" : "run");
    }
  });
  window.addEventListener("beforeunload", () => S.problem && saveCode());

  S.timer.paused = storage("butterbricks:implementation:timer-paused") === "1";
  setInterval(tick, 1000);
  setupSplitters("implementation", () => cm.refresh());
  await loadCatalog();
  // a link like /implementation/#kv-store opens that problem
  openProblem(S.problems.some((p) => p.key === problemHash()) ? problemHash() : progress().current);
  window.addEventListener("hashchange", () => {
    if (S.problems.some((p) => p.key === problemHash()) && problemHash() !== S.problem?.key) openProblem(problemHash());
  });
}

ready.then(main);
