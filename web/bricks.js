"use strict";

// the engine for brick-based categories (Patterns, Structures). Each page sets window.CATEGORY first (see
// patterns/index.html) and loads this. Three views, chosen by the URL: the wall (/<category>/), one problem
// (/<category>/#<problem>) and a recognition drill session (/<category>/#drill). docs/patterns-taxonomy.md and
// docs/structures-taxonomy.md describe the model: patterns (families) hold variants (techniques, the "bricks"),
// variants hold problems with a role each, and drills. Structures' problems add an operations table, a design card,
// and worked designs (questions before the code trace); they show wherever a problem has them.

const C = window.CATEGORY;

const S = {
  data: null,           // patterns.json
  index: new Map(),     // problem key -> { problem, variant, pattern }
  current: null,        // the open problem's key
  running: false,
  step: 0,              // the worked example's current step
  answered: new Set(),  // the example steps whose prediction has been answered
  drill: null,          // the drill session in progress
};

let cm, stepCm, py, errors;

//helpers

function md(text) {
  const box = el("div", "md", marked.parse(text.trim()));
  for (const code of box.querySelectorAll("pre code")) {
    const src = code.textContent;
    code.textContent = "";
    CodeMirror.runMode(src, "python", code);
  }
  return box;
}

const inline = (text) => marked.parseInline(text);

function shuffled(items) {
  const a = [...items];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

//progress. One synced key holds it all:
//  solved:   problem -> { t, assisted }   (assisted: its solution was revealed before it was solved)
//  revealed: problem -> t
//  laid:     variant -> t                 (a brick is laid when its variation or stretch is solved unassisted)
//  reviews:  variant -> { stage, due }    (due is a time, or null once every review is done)
//  drills:   drill -> { ok, t }

const PROGRESS_KEY = `butterbricks:${C.key}:progress`;
const codeKey = (k) => `butterbricks:${C.key}:code:${k}`;
const designKey = (k) => `butterbricks:${C.key}:design:${k}`;  // your design card for a problem
const INTRO_KEY = `butterbricks:${C.key}:intro-closed`;  // this browser only
const DAY = 24 * 60 * 60 * 1000;
const REVIEW_DAYS = [1, 3, 7, 21];
const LAYS_BRICK = ["variation", "stretch"];

function progress() {
  const p = storedJson(PROGRESS_KEY, {});
  for (const k of ["solved", "revealed", "laid", "reviews", "drills"]) p[k] ||= {};
  return p;
}

function saveProgress(p) { storage(PROGRESS_KEY, JSON.stringify(p)); }

// records a solve; returns what it changed: { first, laid, reviewed }
function markSolved(key) {
  const { problem, variant } = S.index.get(key);
  const p = progress();
  const now = Date.now();
  const out = { first: !p.solved[key], laid: false, reviewed: false };
  if (out.first) p.solved[key] = { t: now, assisted: !!p.revealed[key] };
  if (LAYS_BRICK.includes(problem.role) && !p.revealed[key] && !p.laid[variant.key]) {
    p.laid[variant.key] = now;
    p.reviews[variant.key] = { stage: 0, due: now + REVIEW_DAYS[0] * DAY };
    out.laid = true;
  }
  if (problem.role === "review" && p.reviews[variant.key]?.due && p.reviews[variant.key].due <= now) {
    const stage = p.reviews[variant.key].stage + 1;
    p.reviews[variant.key] = { stage, due: stage < REVIEW_DAYS.length ? now + REVIEW_DAYS[stage] * DAY : null };
    out.reviewed = true;
  }
  saveProgress(p);
  return out;
}

function variantState(variant, p = progress()) {
  const seq = variant.problems.filter((x) => x.role !== "review");
  const solved = seq.filter((x) => p.solved[x.key]).length;
  const review = p.reviews[variant.key];
  return {
    solved, total: seq.length,
    laid: !!p.laid[variant.key],
    due: !!(review && review.due && review.due <= Date.now()),
    nextDue: review?.due || null,
    started: solved > 0 || variant.problems.some((x) => storage(codeKey(x.key))),
  };
}

// where to go next in a variant: its first unsolved problem in sequence, or its review if one is due
function nextProblem(variant, p = progress()) {
  const st = variantState(variant, p);
  if (st.due) return reviewProblem(variant, p);
  return variant.problems.find((x) => x.role !== "review" && !p.solved[x.key]) || variant.problems[0];
}

function reviewProblem(variant, p = progress()) {
  const reviews = variant.problems.filter((x) => x.role === "review");
  const stage = p.reviews[variant.key]?.stage || 0;
  return reviews[stage % reviews.length];
}

function allVariants() {
  return S.data.patterns.flatMap((pattern) => pattern.variants.map((variant) => ({ pattern, variant })));
}

// the recommended next brick: the first one not laid whose prerequisites are laid (or, failing that, not laid at all)
function recommended(p = progress()) {
  const open = allVariants().filter(({ variant }) => !p.laid[variant.key]);
  return open.find(({ variant }) => variant.prerequisites.every((k) => p.laid[k])) || open[0] || null;
}

function renderProgressBar() {
  const p = progress();
  const all = allVariants();
  const laid = all.filter(({ variant }) => p.laid[variant.key]).length;
  $("progress-fill").style.width = `${(100 * laid) / all.length}%`;
  $("progress-text").textContent = `${laid} / ${all.length} bricks laid`;
}

//views

function showView(name) {
  $("wall-view").hidden = name !== "wall";
  $("drill-view").hidden = name !== "drill";
  $("problem-view").hidden = name !== "problem";
  document.body.classList.toggle("scroll-page", name !== "problem");
}

function route() {
  const h = problemHash();
  if (h === "drill") return startDrill();
  if (S.index.has(h)) return openProblem(h);
  showWall();
}

//the wall

function brickButton(pattern, variant, p) {
  const st = variantState(variant, p);
  const cls = st.laid ? (st.due ? "laid due" : "laid") : st.started ? "started" : "new";
  const b = el("a", `brick ${cls}`,
    `<span class="brick-name">${esc(variant.name)}</span>` +
    `<span class="brick-sub">${st.laid ? (st.due ? "review due" : "laid") : `${st.solved}/${st.total}`}</span>`);
  b.href = `#${encodeURIComponent(nextProblem(variant, p).key)}`;
  b.title = `${pattern.name} · ${variant.name}${st.laid ? " (laid)" : ""}\n${variant.idea}`;
  return b;
}

function showWall() {
  showView("wall");
  if (location.hash) history.replaceState(null, "", location.pathname);
  const p = progress();
  const box = $("wall-view");
  box.innerHTML = "";
  const page = el("div", "wall-page");

  const intro = el("section", "panel wall-intro");
  intro.innerHTML = `<h1>${esc(C.title)}</h1><p>${C.summary}</p>`;
  if (C.howItWorks) intro.append(howItWorks());
  const actions = el("div", "wall-actions");
  const rec = recommended(p);
  if (rec) {
    const next = nextProblem(rec.variant, p);
    const a = el("a", "btn primary", `Continue: ${esc(rec.variant.name)} · ${esc(next.roleLabel)} ›`);
    a.href = `#${encodeURIComponent(next.key)}`;
    actions.append(a);
  }
  const drill = el("a", "btn", "Recognition drill ›");
  drill.href = "#drill";
  drill.title = `${C.drillQuestion} Then: what gave it away?`;
  actions.append(drill);
  intro.append(actions);
  page.append(intro);

  // the review queue
  const queue = el("section", "panel review-queue", "<h2>Review queue</h2>");
  const due = allVariants().filter(({ variant }) => variantState(variant, p).due);
  if (due.length) {
    for (const { pattern, variant } of due) {
      const row = el("div", "queue-row", `<span><b>${esc(variant.name)}</b> <span class="muted">${esc(pattern.name)}</span></span>`);
      const go = el("a", "btn small primary", "Review ›");
      go.href = `#${encodeURIComponent(reviewProblem(variant, p).key)}`;
      row.append(go);
      queue.append(row);
    }
  } else {
    const upcoming = allVariants().map(({ variant }) => ({ variant, at: p.reviews[variant.key]?.due })).filter((x) => x.at).sort((a, b) => a.at - b.at)[0];
    queue.append(el("p", "muted", upcoming
      ? `Nothing due. Next: ${esc(upcoming.variant.name)}, ${new Date(upcoming.at).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}.`
      : "Nothing due. Bricks come back here 1, 3, 7 and 21 days after you lay them, each time as a new problem in disguise."));
  }
  page.append(queue);

  // the wall itself, built from the bottom up: the first pattern is the foundation
  const wall = el("section", "wall");
  wall.append(el("h2", "wall-title", "The wall"));
  const rows = [];
  S.data.patterns.forEach((pattern) => {
    const row = el("div", "wall-row");
    row.append(el("div", "row-label", esc(pattern.name)));
    const bricks = el("div", "bricks");
    for (const v of pattern.variants) bricks.append(brickButton(pattern, v, p));
    for (const name of pattern.planned || []) bricks.append(el("span", "brick ghost planned-brick", `<span class="brick-name">${esc(name)}</span><span class="brick-sub">planned</span>`));
    row.append(bricks);
    rows.push(row);
  });
  for (const name of S.data.planned.slice(0, 4)) {
    const row = el("div", "wall-row planned");
    row.append(el("div", "row-label", esc(name)), el("div", "bricks", `<span class="brick ghost">planned</span>`));
    rows.push(row);
  }
  const more = S.data.planned.length - 4;
  if (more > 0) rows.push(el("div", "wall-row planned more", `<div class="row-label"></div><div class="bricks muted small">and ${more} more: ${esc(S.data.planned.slice(4).join(", "))}</div>`));
  rows.reverse().forEach((r, i) => { r.classList.toggle("offset", i % 2 === 1); wall.append(r); });
  wall.append(el("div", "wall-ground"));
  page.append(wall);

  box.append(page);
  renderProgressBar();
}

// the category's "how it works" panel: open on a first visit, folded after that
function howItWorks() {
  const box = el("details", "how-it-works");
  box.open = raw(INTRO_KEY) !== "1";
  box.append(el("summary", "", `How ${esc(C.title)} works`));
  box.append(el("div", "how-body", C.howItWorks));
  box.addEventListener("toggle", () => raw(INTRO_KEY, box.open ? null : "1"));
  return box;
}

//one problem

function renderSidebar() {
  const bar = $("sidebar");
  const p = progress();
  const { variant: here } = S.index.get(S.current);
  bar.innerHTML = "";
  const head = el("div", "cat-head", `<a class="back-link" href="/">‹ All problems</a>` +
    `<span class="cat-line"><span class="cat-title"><a href="#" class="wall-link">${esc(C.title)}</a></span><span class="cat-count">${$("progress-text").textContent}</span></span>`);
  head.querySelector(".wall-link").onclick = (e) => { e.preventDefault(); history.pushState(null, "", location.pathname); showWall(); };
  bar.append(head);
  for (const pattern of S.data.patterns) {
    bar.append(el("h3", "group-head", `<span>${esc(pattern.name)}</span>`));
    for (const v of pattern.variants) {
      const st = variantState(v, p);
      const item = el("a", `variant-link${v.key === here.key ? " current" : ""}${st.laid ? " laid" : ""}`,
        `<span class="mini-brick ${st.laid ? "laid" : st.started ? "started" : ""}"></span><span class="vname">${esc(v.name)}</span>` +
        `<span class="vcount">${st.due ? "review" : `${st.solved}/${st.total}`}</span>`);
      item.href = `#${encodeURIComponent(nextProblem(v, p).key)}`;
      bar.append(item);
      if (v.key !== here.key) continue;
      for (const x of v.problems) {
        if (x.role === "review" && x.key !== S.current) continue;
        const done = !!p.solved[x.key];
        const link = el("a", `problem-step${x.key === S.current ? " current" : ""}${done ? " solved" : ""}`,
          `<span class="mark">${done ? "✓" : "○"}</span><span class="role">${esc(x.roleLabel)}</span><span class="ptitle">${esc(x.title)}</span>`);
        link.href = `#${encodeURIComponent(x.key)}`;
        bar.append(link);
      }
    }
  }
  const drill = el("a", "drill-link", "Recognition drill ›");
  drill.href = "#drill";
  bar.append(drill);
  bar.querySelector(".problem-step.current")?.scrollIntoView({ block: "nearest" });
}

function showTab(name) {
  for (const t of $("left-tabs").querySelectorAll(".tab")) {
    t.classList.toggle("on", t.dataset.tab === name);
    $(`tab-${t.dataset.tab}`).hidden = t.dataset.tab !== name;
  }
}

function openProblem(key) {
  if (S.running) return;
  if (S.current && S.current !== key && S.index.get(S.current).problem.role !== "example") saveCode();
  S.current = key;
  showView("problem");
  setProblemHash(key);
  const p = progress();
  p.current = key;
  saveProgress(p);
  const { problem } = S.index.get(key);
  renderProgressBar();
  renderSidebar();
  renderStatement();
  renderLearn();
  renderSolution();
  showTab("problem");
  const example = problem.role === "example";
  $("solve-pane").hidden = example;
  $("step-pane").hidden = !example;
  if (example) {
    startStepper(problem);
  } else {
    errors.clear();
    cm.setValue(storage(codeKey(key)) ?? problem.starter);
    cm.clearHistory();
    markBlanks();
    clearResults();
    const samples = problem.tests.filter((t) => !t.hidden).length;
    $("run-target").textContent = `${plural(samples, "sample")} · Submit runs all ${problem.tests.length} tests`;
    setTimeout(() => cm.refresh(), 0);
  }
}

function sequenceDots(variant, problem, p) {
  const seq = variant.problems.filter((x) => x.role !== "review");
  return `<span class="seq">${seq.map((x) => `<span class="dot${p.solved[x.key] ? " done" : ""}${x.key === problem.key ? " here" : ""}" title="${esc(x.roleLabel)}"></span>`).join("")}</span>`;
}

const ROLE_HELP = C.roleHelp || {
  example: "Step through the solution on the right. At some steps you'll predict what happens before it's shown.",
  completion: "The code on the right is nearly done: fill in the blanks marked ___.",
  twin: "The same structure as before, in a different story. Write it from scratch.",
  variation: "One thing changes from the problem before. Solving this without revealing the solution lays the brick.",
  stretch: "A bigger twist, or this idea combined with another. Solving it without the solution also lays the brick.",
  review: "A review: the same idea in a new disguise, to keep it from fading.",
};

function renderStatement() {
  const { problem, variant, pattern } = S.index.get(S.current);
  const p = progress();
  const box = $("tab-problem");
  box.innerHTML = "";
  box.append(el("div", "crumbs", `${esc(pattern.name)} › <a href="#" data-learn>${esc(variant.name)}</a>`));
  box.querySelector("[data-learn]").onclick = (e) => { e.preventDefault(); showTab("learn"); };
  box.append(el("h1", "", esc(problem.title)));
  const meta = el("div", "meta", `<span class="chip role-chip role-${problem.role}">${esc(problem.roleLabel)}</span>` +
    (problem.role !== "review" ? sequenceDots(variant, problem, p) : "") +
    (p.solved[problem.key] ? `<span class="chip easy">✓ ${problem.role === "example" ? "studied" : "solved"}${p.solved[problem.key].assisted ? " (assisted)" : ""}</span>` : ""));
  box.append(meta);
  box.append(el("p", "role-help muted", esc(ROLE_HELP[problem.role])));
  if (problem.changes) box.append(el("div", "changes", `<b>What changes:</b> ${inline(problem.changes)}`));
  box.append(md(problem.statement));
  if (problem.operations.length) {
    box.append(operationsTable(problem));
  } else {
    const sig = el("div", "signature");
    sig.append(highlighted(problem.signature, "python"));
    box.append(sig);
  }
  if (problem.walkthrough) box.append(walkthrough(problem));
  const samples = problem.tests.filter((t) => !t.hidden && t.preview.length);
  if (samples.length && problem.role !== "example") {
    box.append(el("h3", "", "Examples"));
    box.append(highlighted(samples.flatMap((t) => t.preview).join("\n"), "python"));
  }
  if (problem.design && problem.role !== "example") box.append(designCard(problem));
  if (problem.hints.length) box.append(hintBox(problem.hints));
  if (p.solved[problem.key] && problem.takeaway) box.append(el("div", "takeaway", `<b>Takeaway.</b> ${inline(problem.takeaway)}`));
}

// the operations a class problem asks for, each with the cost it must have
function operationsTable(problem) {
  const box = el("div", "ops");
  box.append(el("h3", "", "Operations"));
  const table = el("table", "ops-table");
  table.append(el("tr", "", "<th>operation</th><th>must cost</th>"));
  for (const [sig, cost] of problem.operations) {
    table.append(el("tr", "", `<td><code>${esc(sig)}</code></td><td>${cost ? `<b>${esc(cost)}</b>` : `<span class="muted">(constructor)</span>`}</td>`));
  }
  box.append(table);
  return box;
}

//the design card: what you'll keep, what must stay true, and each operation's cost, written before coding. Ours is
//shown after you solve it; opening it earlier counts as revealing the solution

function designCard(problem) {
  const mine = storedJson(designKey(problem.key), {});
  const box = el("section", "design-card");
  box.append(el("h3", "", "Your design"));
  box.append(el("p", "muted small", "Before you code, write the plan you'd say out loud in an interview. It's saved as you type, and you can compare it with ours once you've solved the problem."));
  const field = (label, name, placeholder) => {
    const l = el("label", "", `<span>${label}</span>`);
    const t = el("textarea");
    t.rows = 2;
    t.placeholder = placeholder;
    t.value = mine[name] || "";
    t.oninput = () => { const d = storedJson(designKey(problem.key), {}); d[name] = t.value; storage(designKey(problem.key), JSON.stringify(d)); };
    l.append(t);
    box.append(l);
  };
  field("What will you keep?", "state", "Each field and what it holds, like: items: list of tickets");
  field("What must always be true? (the invariant)", "invariant", "The fact that ties your fields together");
  const costs = el("div", "cost-inputs", "<span>What will each operation cost?</span>");
  for (const op of Object.keys(problem.design.costs)) {
    const row = el("label", "cost-row", `<code>${esc(op)}</code>`);
    const input = el("input");
    input.placeholder = "O(?)";
    input.value = mine.costs?.[op] || "";
    input.oninput = () => { const d = storedJson(designKey(problem.key), {}); d.costs ||= {}; d.costs[op] = input.value; storage(designKey(problem.key), JSON.stringify(d)); };
    row.append(input);
    costs.append(row);
  }
  box.append(costs);
  const p = progress();
  const compare = el("div", "design-compare");
  const showOurs = () => {
    const d = problem.design;
    compare.innerHTML = `<h4>Our design</h4><p><b>Keep:</b></p><ul>${d.state.map((x) => `<li>${inline(x)}</li>`).join("")}</ul>
      <p><b>Invariant:</b> ${inline(d.invariant)}</p>
      <p><b>Costs:</b> ${Object.entries(d.costs).map(([op, c]) => `<code>${esc(op)}</code> ${esc(c)}`).join(", ")}</p>
      <p><b>Did yours have…</b></p>`;
    const checks = el("div", "checks");
    for (const c of d.checks) checks.append(el("label", "", `<input type="checkbox"> ${inline(c)}`));
    compare.append(checks);
  };
  if (p.solved[problem.key] || p.revealed[problem.key]) {
    showOurs();
  } else {
    const b = el("button", "btn small", "Compare with our design");
    armed(b, "Before solving, this counts as revealing the solution. Click again", () => {
      const q = progress();
      q.revealed[problem.key] = Date.now();
      saveProgress(q);
      renderSolution();
      showOurs();
    });
    compare.append(b);
  }
  box.append(compare);
  return box;
}

//a worked design: the design built up one question at a time; the code stepper unlocks once every question is answered

function walkthrough(problem) {
  S.walk ||= {};
  const answers = (S.walk[problem.key] ||= []);
  const box = el("section", "walkthrough");
  box.append(el("h3", "", "Worked design"));
  box.append(el("p", "muted small", "Answer each question to see the next step. Then step through the code on the right."));
  for (let i = 0; i < problem.walkthrough.length; i++) {
    const step = problem.walkthrough[i];
    const card = el("div", "walk-step");
    card.append(el("div", "walk-num", `${i + 1}`));
    const body = el("div", "walk-body");
    body.append(md(step.text));
    if (step.ask) {
      body.append(el("p", "walk-ask", `<b>${inline(step.ask)}</b>`));
      const opts = el("div", "choices compact");
      for (const opt of step.options) {
        const b = el("button", "choice", inline(opt));
        if (answers[i] !== undefined) {
          b.disabled = true;
          if (opt === step.answer) b.classList.add("right");
          else if (opt === answers[i]) b.classList.add("wrong");
        }
        b.onclick = () => { answers[i] = opt; renderStatement(); if (walkDone(problem)) renderStep(); };
        opts.append(b);
      }
      body.append(opts);
      if (answers[i] !== undefined) body.append(el("div", `walk-why ${answers[i] === step.answer ? "right" : "wrong"}`, `${answers[i] === step.answer ? "Right." : "Not quite."} ${inline(step.why)}`));
    }
    card.append(body);
    box.append(card);
    if (step.ask && answers[i] === undefined) break;  // the next step shows once this one is answered
  }
  return box;
}

function walkDone(problem) {
  if (!problem.walkthrough) return true;
  const answers = S.walk?.[problem.key] || [];
  return problem.walkthrough.every((step, i) => !step.ask || answers[i] !== undefined) || !!progress().solved[problem.key];
}

function hintBox(hints) {
  const box = el("div", "hint-box");
  let shown = 0;
  const btn = el("button", "btn small", `Show a hint (${hints.length} available)`);
  btn.onclick = () => {
    box.insertBefore(el("div", "hint", `<b>Hint ${shown + 1}.</b> ${inline(hints[shown])}`), btn);
    shown++;
    if (shown === hints.length) btn.remove();
    else btn.textContent = `Another hint (${hints.length - shown} left)`;
  };
  box.append(btn);
  return box;
}

const STATUS_TEXT = {
  consensus: "Consensus name: the major interview guides agree on it.",
  textbook: "Textbook name: the guides disagree, so this is the textbook's.",
  ours: "Our name: no established name exists, so this one says what it does.",
};

function renderLearn() {
  const { variant, pattern } = S.index.get(S.current);
  const box = $("tab-learn");
  box.innerHTML = "";
  box.append(el("div", "crumbs", esc(pattern.name)));
  box.append(el("h1", "", esc(variant.name)));
  box.append(el("div", "meta", `<span class="chip status-${variant.status}" title="${esc(STATUS_TEXT[variant.status])}">${esc(variant.status)} name</span>` +
    (variant.aliases.length ? `<span>also called ${variant.aliases.map((a) => `<i>${esc(a)}</i>`).join(", ")}</span>` : "")));
  box.append(el("p", "idea", inline(variant.idea)));
  box.append(el("div", "invariant", `<b>Invariant.</b> ${inline(variant.invariant)}`));
  box.append(el("h3", "", "Template"));
  box.append(highlighted(variant.template, "python"));
  box.append(el("p", "", `<b>Cost.</b> ${esc(variant.complexity)}`));
  const list = (title, items) => {
    if (!items.length) return;
    box.append(el("h3", "", esc(title)));
    const ul = el("ul");
    for (const it of items) ul.append(el("li", "", inline(it)));
    box.append(ul);
  };
  if (variant.referenceTable.length) {
    box.append(el("h3", "", "What each operation costs"));
    const t = el("table", "ops-table cost-sheet");
    t.append(el("tr", "", "<th>operation</th><th>cost</th><th></th>"));
    for (const [op, cost, note] of variant.referenceTable) t.append(el("tr", "", `<td><code>${esc(op)}</code></td><td><b>${esc(cost)}</b></td><td class="muted">${esc(note)}</td>`));
    box.append(t);
  }
  list("Signals: when a problem says…", variant.signals);
  list("Easily confused with", variant.nearMisses);
  list("Common mistakes (each one has a test that catches it)", variant.mistakes);
  box.append(el("h3", "", "About the name"));
  box.append(el("p", "muted small", esc(STATUS_TEXT[variant.status]) + (variant.sources.length
    ? ` Sources: ${variant.sources.map(([label, url]) => `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(label)}</a>`).join(", ")}.`
    : "")));
}

function renderSolution() {
  const { problem } = S.index.get(S.current);
  const box = $("tab-solution");
  box.innerHTML = "<h2>Reference solution</h2>";
  const p = progress();
  if (problem.role === "example") {
    box.append(el("p", "muted", "A worked example's solution is the code you're stepping through."));
    return;
  }
  if (p.revealed[problem.key] || p.solved[problem.key]) {
    box.append(highlighted(problem.reference, "python"));
    if (problem.takeaway) box.append(el("div", "takeaway", `<b>Takeaway.</b> ${inline(problem.takeaway)}`));
    return;
  }
  const lays = LAYS_BRICK.includes(problem.role);
  box.append(el("p", "muted", `Revealing marks this problem as assisted${lays ? ": solving it afterwards won't lay the brick" : ""}. Try the hints first.`));
  const b = el("button", "btn", "Reveal the solution");
  b.onclick = () => {
    const q = progress();
    q.revealed[problem.key] = Date.now();
    saveProgress(q);
    renderSolution();
  };
  box.append(b);
}

//the editor

function saveCode() {
  if (S.current && S.index.get(S.current).problem.role !== "example") storage(codeKey(S.current), cm.getValue());
}

// the ___ blanks in a completion problem, highlighted
const blankOverlay = {
  token(stream) {
    if (stream.match("___")) return "blank";
    while (stream.next() != null && !stream.match("___", false)) { /* skip */ }
    return null;
  },
};

function markBlanks() {
  cm.removeOverlay(blankOverlay);
  if (S.index.get(S.current).problem.role === "completion") cm.addOverlay(blankOverlay);
}

function clearResults() {
  $("results").innerHTML = "";
  $("results-summary").hidden = true;
  $("results-empty").hidden = false;
}

function setBusy(busy) {
  S.running = busy;
  $("btn-run").disabled = busy;
  $("btn-submit").disabled = busy;
}

async function runTests(mode) {
  if (S.running || !S.current) return;
  const { problem } = S.index.get(S.current);
  if (problem.role === "example") return;
  if (mode === "submit" && !(await requireSignIn("Sign in to submit. Your progress is saved to your account."))) return;
  saveCode();
  setBusy(true);
  errors.clear();
  const summary = $("results-summary");
  const list = $("results");
  $("results-empty").hidden = true;
  list.innerHTML = "";
  summary.hidden = false;
  summary.className = "results-summary running";
  summary.textContent = py.readyDone ? "Loading your code…" : "Waiting for Python to load…";
  const key = S.current;
  try {
    const run = await runTestPlan({
      py, args: { key, mode, source: cm.getValue() }, list, summary, errors,
      info: (r) => problem.tests.find((t) => t.name === r.name) || {},
    });
    if (run.loadError) return;
    const all = summarizeRun(summary, run.results, mode);
    if (!all || mode !== "submit") {
      if (all) {
        const go = el("button", "btn small primary", "Submit");
        go.onclick = () => runTests("submit");
        summary.append(el("span", "small", "Samples pass. Submit to run every test."), go);
      }
      return;
    }
    solved(key);
  } catch (e) {
    summary.className = "results-summary fail";
    summary.textContent = `Something went wrong running the tests: ${e.message}`;
  } finally {
    setBusy(false);
  }
}

// after a problem is solved (submitted, or an example studied): record it, celebrate, and point to what's next
function solved(key) {
  const { problem, variant } = S.index.get(key);
  const result = markSolved(key);
  if (result.first || result.reviewed) logSolve(C.key, key, `${variant.name} · ${problem.title}`);
  const p = progress();
  const banner = el("div", "unlock");
  let text = `<b>${problem.role === "example" ? "Studied." : "Solved."}</b>`;
  if (result.laid) text = `<b>Brick laid: ${esc(variant.name)}.</b> It comes back for review in a day.`;
  else if (result.reviewed) {
    const r = p.reviews[variant.key];
    text = `<b>Review done.</b> ${r.due ? `Next review in ${REVIEW_DAYS[r.stage]} days.` : "That was the last review: this brick is solid."}`;
  } else if (p.solved[key]?.assisted) text += " Assisted, since you revealed the solution first.";
  if (problem.takeaway) text += ` ${inline(problem.takeaway)}`;
  banner.innerHTML = `<span>${text}</span>`;
  const next = after(key);
  if (next) {
    const go = el("a", "btn primary", `Next: ${esc(next.title)} ›`);
    go.href = `#${encodeURIComponent(next.key)}`;
    banner.append(go);
  }
  const target = problem.role === "example" ? $("step-panel") : $("results");
  target.prepend(banner);
  celebrate(result.laid, problem.role === "example" ? banner : $("results-summary"), problem.role === "example" ? null : document.querySelector("#solve-pane .editor"));
  if (result.laid) toast(`Brick laid: ${variant.name}`);
  renderProgressBar();
  renderSidebar();
  renderStatement();
  renderSolution();
}

// the problem after this one: the rest of this variant's sequence, then the recommended next brick
function after(key) {
  const { problem, variant } = S.index.get(key);
  const p = progress();
  if (problem.role !== "review") {
    const seq = variant.problems.filter((x) => x.role !== "review");
    const rest = seq.slice(seq.findIndex((x) => x.key === key) + 1);
    const next = rest.find((x) => !p.solved[x.key]) || rest[0];
    if (next) return next;
  }
  const rec = recommended(p);
  return rec ? nextProblem(rec.variant, p) : null;
}

//the worked-example stepper: walks the trace built at build time from the reference solution (categories/framework/trace.py)

let stepMark = null;

function startStepper(problem) {
  S.step = 0;
  S.answered = new Set();
  stepCm.setValue(problem.reference.replace(/\n$/, ""));
  $("step-call").textContent = problem.kind === "class" ? `${problem.function}: ${plural(problem.trace.script.length - 1, "operation")}` : problem.trace.call;
  setTimeout(() => { stepCm.refresh(); renderStep(); }, 0);
}

function renderStep() {
  const { problem } = S.index.get(S.current);
  const steps = problem.trace.steps;
  const i = S.step;
  const step = steps[i];
  const last = i === steps.length - 1;
  if (stepMark !== null) stepCm.removeLineClass(stepMark, "background", "cm-step-line");
  stepMark = step.line ? step.line - 1 : null;
  if (stepMark !== null) {
    stepCm.addLineClass(stepMark, "background", "cm-step-line");
    stepCm.scrollIntoView({ line: stepMark, ch: 0 }, 60);
  }
  $("step-count").textContent = `step ${i + 1} of ${steps.length}`;

  const panel = $("step-panel");
  panel.innerHTML = "";
  $("step-pane").classList.toggle("locked", !walkDone(problem));  // the code would give the design away
  if (!walkDone(problem)) {
    panel.append(el("div", "step-note", "<b>First, the design.</b> Answer the questions on the left; then step through the code here and watch it run."));
    return;
  }
  const waiting = step.predict && !S.answered.has(i);
  if (step.op) {
    panel.append(el("div", "step-note op-note", `<b>Calling</b> <code>${esc(step.op)}</code>`));
  } else if (step.returns !== undefined) {
    panel.append(el("div", "step-note", `<b>Line ${step.line} returns</b> <code>${esc(step.returns)}</code>.`));
  } else {
    panel.append(el("div", "step-note", `<b>About to run line ${step.line}${step.in && step.in !== problem.function && problem.kind === "class" ? ` in ${esc(step.in)}()` : ""}.</b> ${step.note ? esc(step.note) : ""}`));
  }
  if (step.predict) {
    const box = el("div", "predict");
    box.append(el("div", "", `<b>Predict:</b> will <code>${esc(step.predict.ask)}</code> be True or False?`));
    const buttons = el("div", "predict-buttons");
    for (const v of [true, false]) {
      const b = el("button", "btn", v ? "True" : "False");
      b.disabled = !waiting;
      b.onclick = () => {
        S.answered.add(i);
        S.lastGuess = { i, right: v === step.predict.answer };
        renderStep();
      };
      buttons.append(b);
    }
    box.append(buttons);
    if (!waiting) {
      const right = S.lastGuess?.i === i ? S.lastGuess.right : null;
      box.append(el("div", `verdict-line ${right === false ? "wrong" : "right"}`,
        `${right === false ? "Not quite: it's" : right === true ? "Right: it's" : "It's"} <b>${step.predict.answer ? "True" : "False"}</b>.`));
    }
    panel.append(box);
  }
  const table = el("table", "vars-table state");
  const prevStep = steps.slice(0, i).reverse().find((x) => x.vars.length);
  const prev = prevStep ? Object.fromEntries(prevStep.vars) : {};
  for (const [name, value] of step.vars) {
    const tr = el("tr", prev[name] !== undefined && prev[name] !== value ? "changed" : "");
    tr.append(el("td", "vname", esc(name)), el("td", "vval", esc(value)));
    table.append(tr);
  }
  if (step.vars.length) {
    panel.append(el("div", "label", "Variables"));
    panel.append(table);
  }
  const controls = el("div", "step-controls");
  const back = el("button", "btn", "◀ Back");
  back.disabled = i === 0;
  back.onclick = () => { S.step--; renderStep(); };
  const fwd = el("button", "btn primary", "Next ▶");
  fwd.disabled = last || waiting;
  fwd.onclick = () => { S.step++; renderStep(); };
  controls.append(back, fwd);
  if (last) {
    const p = progress();
    if (p.solved[problem.key]) {
      const next = after(problem.key);
      if (next) {
        const go = el("a", "btn primary", `Next: ${esc(next.title)} ›`);
        go.href = `#${encodeURIComponent(next.key)}`;
        controls.append(go);
      }
    } else {
      const done = el("button", "btn primary", "Mark as studied ✓");
      done.onclick = async () => {
        if (!(await requireSignIn("Sign in to save your progress."))) return;
        renderStep();  // first, so the banner solved() adds isn't wiped by the redraw
        solved(problem.key);
      };
      controls.append(done);
    }
  }
  panel.append(controls);
  if (waiting) panel.append(el("div", "muted small", "Answer the prediction to continue."));
}

//recognition drills

function startDrill() {
  showView("drill");
  const p = progress();
  const touched = allVariants().filter(({ variant }) => variant.problems.some((x) => p.solved[x.key]));
  const pool = (touched.length >= 2 ? touched : allVariants()).flatMap(({ variant }) => variant.drills);
  S.drill = { items: shuffled(pool).slice(0, 8), i: 0, named: 0, signals: 0, phase: "name" };
  renderDrill();
}

function renderDrill() {
  const box = $("drill-view");
  box.innerHTML = "";
  const page = el("div", "drill-page");
  const d = S.drill;
  const card = el("section", "panel drill-card");
  if (d.i >= d.items.length) {
    card.innerHTML = `<h1>Drill done</h1><p>You got <b>${d.named} of ${d.items.length}</b> answers right, and spotted <b>${d.signals} of ${d.items.length}</b> signals.</p>`;
    const again = el("button", "btn primary", "Another round");
    again.onclick = startDrill;
    const wall = el("a", "btn", "Back to the wall");
    wall.href = "#";
    wall.onclick = (e) => { e.preventDefault(); history.pushState(null, "", location.pathname); showWall(); };
    const row = el("div", "wall-actions");
    row.append(again, wall);
    card.append(row);
    page.append(card);
    box.append(page);
    return;
  }
  const item = d.items[d.i];
  card.append(el("div", "meta", `<span class="chip">Recognition drill</span><span>${d.i + 1} of ${d.items.length}</span>`));
  card.append(el("p", "drill-statement", esc(item.statement)));

  card.append(el("h3", "", esc(item.question || C.drillQuestion)));
  item.nameOptions ||= shuffled([item.answer, ...item.choices]);
  const names = el("div", "choices");
  for (const opt of item.nameOptions) {
    const b = el("button", "choice", esc(opt));
    if (item.picked) {
      b.disabled = true;
      if (opt === item.answer) b.classList.add("right");
      else if (opt === item.picked) b.classList.add("wrong");
    }
    b.onclick = () => {
      item.picked = opt;
      if (opt === item.answer) d.named++;
      renderDrill();
    };
    names.append(b);
  }
  card.append(names);

  if (item.picked) {
    card.append(el("h3", "", "What gave it away?"));
    item.signalOptions ||= shuffled([item.signal, ...item.wrongSignals]);
    const sigs = el("div", "choices");
    for (const opt of item.signalOptions) {
      const b = el("button", "choice", esc(opt));
      if (item.pickedSignal) {
        b.disabled = true;
        if (opt === item.signal) b.classList.add("right");
        else if (opt === item.pickedSignal) b.classList.add("wrong");
      }
      b.onclick = () => {
        item.pickedSignal = opt;
        const ok = item.picked === item.answer && opt === item.signal;
        if (opt === item.signal) d.signals++;
        const p = progress();
        const first = !p.drills[item.key]?.ok && ok;
        p.drills[item.key] = { ok: ok || !!p.drills[item.key]?.ok, t: Date.now() };
        saveProgress(p);
        if (first) logSolve(`${C.key}-drill`, item.key, `Drill: ${item.answer}`);
        renderDrill();
      };
      sigs.append(b);
    }
    card.append(sigs);
  }
  if (item.pickedSignal) {
    card.append(el("div", "takeaway", `<b>${esc(item.answer)}.</b> ${esc(item.why)}`));
    const next = el("button", "btn primary", d.i + 1 < d.items.length ? "Next drill ›" : "Finish");
    next.onclick = () => { d.i++; renderDrill(); };
    const row = el("div", "wall-actions");
    row.append(next);
    card.append(row);
  }
  page.append(card);
  box.append(page);
}

//startup

async function main() {
  try {
    S.data = await (await fetch(C.data)).json();
  } catch (e) {
    $("wall-view").hidden = false;
    $("wall-view").innerHTML = `<p class="panel">Couldn't load <code>${esc(C.data)}</code>. Run <code>./serve.py</code> from the repo root, which builds it first.</p>`;
    return;
  }
  for (const pattern of S.data.patterns) {
    for (const variant of pattern.variants) {
      for (const problem of variant.problems) S.index.set(problem.key, { problem, variant, pattern });
    }
  }

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
  stepCm = CodeMirror($("step-code"), { mode: "python", lineNumbers: true, readOnly: "nocursor", lineWrapping: true });
  errors = errorLine(cm);
  let saveTimer;
  cm.on("change", () => { clearTimeout(saveTimer); saveTimer = setTimeout(saveCode, 400); });
  py = startPython({ base: `/${C.key}/`, files: S.data.files, onStatus: (kind, text) => {
    const s = $("py-status");
    s.className = `py-status ${kind}`;
    s.textContent = text;
  } });

  for (const t of $("left-tabs").querySelectorAll(".tab")) t.onclick = () => showTab(t.dataset.tab);
  $("btn-run").onclick = () => runTests("run");
  $("btn-submit").onclick = () => runTests("submit");
  armed($("btn-reset-code"), "Click again to replace your code", () => {
    const { problem } = S.index.get(S.current);
    errors.clear();
    cm.setValue(problem.starter);
    saveCode();
  });
  armed($("btn-reset-progress"), "Click again to erase everything", () => {
    try {
      for (const k of Object.keys(localStorage)) if (k.startsWith(`butterbricks:${C.key}:`)) storage(k, null);
    } catch (e) {}
    route();
  });
  document.addEventListener("keydown", (e) => {
    if ($("problem-view").hidden || e.target.closest("textarea, input, .CodeMirror")) return;
    if (!$("step-pane").hidden && (e.key === "ArrowRight" || e.key === "ArrowLeft")) {
      const btn = [...$("step-panel").querySelectorAll(".step-controls .btn")].find((b) => b.textContent.includes(e.key === "ArrowRight" ? "Next ▶" : "Back"));
      if (btn && !btn.disabled) { e.preventDefault(); btn.click(); }
    }
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); runTests(e.shiftKey ? "submit" : "run"); }
  });
  window.addEventListener("beforeunload", saveCode);
  window.addEventListener("hashchange", route);
  window.addEventListener("popstate", route);
  setupSplitters(C.key, () => { cm.refresh(); stepCm.refresh(); });
  await loadCatalog();
  route();
}

ready.then(main);
