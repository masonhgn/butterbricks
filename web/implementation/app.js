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

//python runs in a worker (../pyrun.js); errors marks the line an error came from

let py, errors;

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

  errors.clear();
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
  errors.clear();
  showTab("bottom", "results");
  const problem = S.problem, part = S.part;
  const args = { key: problem.key, part, mode, source: cm.getValue() };
  const summary = $("results-summary");
  const list = $("results");
  $("results-empty").hidden = true;
  list.innerHTML = "";
  summary.hidden = false;
  summary.className = "results-summary running";
  summary.textContent = py.readyDone ? "Loading your code…" : "Waiting for Python to load…";

  try {
    const run = await runTestPlan({ py, args, list, summary, errors, info: (r) => testInfo(r.part, r.name) });
    if (run.loadError) return;
    const results = run.results;
    finish(problem, part, mode, results);
  } catch (e) {
    summary.className = "results-summary fail";
    summary.textContent = `Something went wrong running the tests: ${e.message}`;
  } finally {
    setBusy(false);
  }
}

function finish(problem, part, mode, results) {
  const summary = $("results-summary");
  const all = summarizeRun(summary, results, mode);
  if (!all || mode !== "submit") {
    if (all) {
      const go = el("button", "btn small primary", "Submit");
      go.onclick = () => runTests("submit");
      summary.append(el("span", "small", "Samples pass. Submit to run the hidden tests."), go);
    }
    return;
  }
  const first = markSolved(problem.key, part);
  if (first) logSolve("implementation", `${problem.key}#${part}`, `${problem.title} · part ${part}`);
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

async function runScratch() {
  if (S.running) return;
  saveCode();
  storage(scratchKey(S.problem.key), $("scratch").value);
  setBusy(true);
  errors.clear();
  const out = $("scratch-output");
  out.className = "console-output muted";
  out.textContent = "Running…";
  try {
    const r = await py.call("scratch", { source: cm.getValue(), snippet: $("scratch").value }, 20000);
    out.className = `console-output${r.ok ? "" : " err"}`;
    out.textContent = r.output || (r.ok ? "(no output; use print)" : "");
    if (r.where) errors.show(r.where, r.output.trim().split("\n").pop());
  } catch (e) {
    out.className = "console-output err";
    out.textContent = e.killed ? "Stopped after 20s. Python was restarted." : e.message;
  } finally {
    setBusy(false);
  }
}

//startup

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
  errors = errorLine(cm);
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
  py = startPython({ base: "/implementation/", files: S.files, onStatus: pyStatus });

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
    errors.clear();
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
