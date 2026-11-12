"use strict";

// the engine for brick-based categories (Patterns, Structures). Each page sets window.CATEGORY first (see
// patterns/index.html) and loads this, after visual.js. Three views, chosen by the URL: the wall (/<category>/), a
// pattern's overview and map (/<category>/#pattern/<key>) and one problem (/<category>/#<problem>).
// docs/patterns-taxonomy.md and docs/structures-taxonomy.md describe the model: patterns (families) hold variants
// (techniques, the "bricks"), variants hold problems with a role each and, in Patterns, a lesson for the Learn tab.
// Structures' problems add an operations table, a design card, and worked designs (reasoning before the code trace);
// they show wherever a problem has them. Worked examples play in the visualizer (visual.js).

const C = window.CATEGORY;

const S = {
  data: null,           // patterns.json
  index: new Map(),     // problem key -> { problem, variant, pattern }
  current: null,        // the open problem's key
  running: false,
  player: null,         // the worked example's visualizer, in the right-hand pane
};

let cm, py, errors;

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
//  drills:   drill -> { ok, t }            (from the retired recognition drills)
//  learned:  variant -> t                 (its Learn page was opened, so its example opens on Problem from now on)

const PROGRESS_KEY = `butterbricks:${C.key}:progress`;
const codeKey = (k) => `butterbricks:${C.key}:code:${k}`;
const designKey = (k) => `butterbricks:${C.key}:design:${k}`;  // your design card for a problem
const INTRO_KEY = `butterbricks:${C.key}:intro-closed`;  // this browser only
const DAY = 24 * 60 * 60 * 1000;
const REVIEW_DAYS = [1, 3, 7, 21];
const LAYS_BRICK = ["variation", "stretch"];

function progress() {
  const p = storedJson(PROGRESS_KEY, {});
  for (const k of ["solved", "revealed", "laid", "reviews", "drills", "learned"]) p[k] ||= {};
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
  $("overview-view").hidden = name !== "overview";
  $("problem-view").hidden = name !== "problem";
  document.body.classList.toggle("scroll-page", name !== "problem");
}

function route() {
  const h = problemHash();
  if (h.startsWith("pattern/") && S.data.patterns.some((p) => p.key === h.slice(8) && p.overview)) return showOverview(h.slice(8));
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
    row.append(el("div", "row-label", pattern.overview
      ? `<a href="#pattern/${encodeURIComponent(pattern.key)}" title="the map of ${esc(pattern.name)}: what each brick is for">${esc(pattern.name)} <span class="small">map ›</span></a>`
      : esc(pattern.name)));
    const bricks = el("div", "bricks");
    for (const v of pattern.variants) bricks.append(brickButton(pattern, v, p));
    for (const x of pattern.planned || []) bricks.append(el("span", "brick ghost planned-brick", `<span class="brick-name">${esc(x.name)}</span><span class="brick-sub">planned</span>`));
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
    bar.append(el("h3", "group-head", pattern.overview ? `<a href="#pattern/${encodeURIComponent(pattern.key)}">${esc(pattern.name)}</a>` : `<span>${esc(pattern.name)}</span>`));
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
  bar.querySelector(".problem-step.current")?.scrollIntoView({ block: "nearest" });
}

function showTab(name) {
  if (name !== "learn" && !$("tab-learn").hidden) markLearned();
  for (const t of $("left-tabs").querySelectorAll(".tab")) {
    t.classList.toggle("on", t.dataset.tab === name);
    $(`tab-${t.dataset.tab}`).hidden = t.dataset.tab !== name;
  }
  $(`tab-${name}`).scrollTop = 0;
}

// a lesson counts as read once you leave it, so its example opens on Problem from then on
function markLearned() {
  if (!S.current) return;
  const { variant } = S.index.get(S.current);
  const p = progress();
  if (variant.lesson && !p.learned[variant.key]) { p.learned[variant.key] = Date.now(); saveProgress(p); }
}

function openProblem(key) {
  if (S.running) return;
  if (S.current && S.current !== key && S.index.get(S.current).problem.role !== "example") saveCode();
  if (S.current && S.current !== key && !$("tab-learn").hidden) markLearned();
  const reopened = S.current === key && !$("problem-view").hidden;  // opened again (a sync, say): keep the tab you're on
  const onTab = [...$("left-tabs").querySelectorAll(".tab")].find((t) => t.classList.contains("on"))?.dataset.tab;
  S.current = key;
  showView("problem");
  setProblemHash(key);
  const p = progress();
  p.current = key;
  saveProgress(p);
  const { problem, variant } = S.index.get(key);
  renderProgressBar();
  renderSidebar();
  renderStatement();
  renderLearn();
  renderSolution();
  // a subpattern starts with its lesson: the first time its worked example opens, it opens on Learn
  const firstVisit = problem.role === "example" && variant.lesson && !p.learned[variant.key];
  showTab(reopened ? onTab : firstVisit ? "learn" : "problem");
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
  example: "Step through the solution on the right and watch every variable and structure change as it runs. Change the input to watch it run on yours.",
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

//a worked design: the design built up one step at a time. Each question is for thinking through; its reasoning shows
//when you ask for it, and the next step after that. The code stepper unlocks once every step is shown

function walkthrough(problem) {
  S.walk ||= {};
  const shown = (S.walk[problem.key] ||= []);
  const box = el("section", "walkthrough");
  box.append(el("h3", "", "Worked design"));
  box.append(el("p", "muted small", "Think each question through before you show the reasoning. Then step through the code on the right."));
  for (let i = 0; i < problem.walkthrough.length; i++) {
    const step = problem.walkthrough[i];
    const card = el("div", "walk-step");
    card.append(el("div", "walk-num", `${i + 1}`));
    const body = el("div", "walk-body");
    body.append(md(step.text));
    if (step.ask) {
      body.append(el("p", "walk-ask", `<b>Think:</b> ${inline(step.ask)}`));
      if (shown[i]) body.append(el("div", "walk-why right", inline(step.why)));
      else {
        const b = el("button", "btn small", "Show the reasoning");
        b.onclick = () => { shown[i] = true; renderStatement(); if (walkDone(problem)) startStepper(problem); };
        body.append(b);
      }
    }
    card.append(body);
    box.append(card);
    if (step.ask && !shown[i]) break;  // the next step shows once this one's reasoning is shown
  }
  return box;
}

function walkDone(problem) {
  if (!problem.walkthrough) return true;
  const shown = S.walk?.[problem.key] || [];
  return problem.walkthrough.every((step, i) => !step.ask || shown[i]) || !!progress().solved[problem.key];
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

// a code block with each move's lines tinted
function tinted(src, moves, cls = "") {
  const { box } = annotatedCode(src, moves, { labels: true });
  if (cls) box.classList.add(cls);
  return box;
}

function nameNote(variant) {
  return el("p", "muted small", esc(STATUS_TEXT[variant.status]) + (variant.sources.length
    ? ` Sources: ${variant.sources.map(([label, url]) => `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(label)}</a>`).join(", ")}.`
    : ""));
}

// a worked example in a lesson: the problem, then the visualizer playing its code (tinted by move)
function lessonExample(ex, i, moves) {
  const card = el("section", "lesson-example");
  card.append(el("h3", "", `Example ${i + 1}: ${esc(ex.title)}`));
  if (ex.classic) card.append(el("div", "classic muted small", `Known as ${esc(ex.classic)}`));
  card.append(md(ex.statement));
  card.append(el("div", "cases", ex.cases.map(([call, out]) => `<code>${esc(call)}</code> → <code>${esc(out)}</code>`).join("<br>")));
  makePlayer(card, {
    trace: ex.trace, code: ex.code, moves, viz: ex.viz, compact: true,
    custom: { py, source: ex.code, function: ex.function, args: ex.args, notes: ex.notes },
  });
  if (ex.differs) card.append(el("div", "differs", `<b>What's different here.</b> ${inline(ex.differs)}`));
  if (ex.problem && ex.problem !== S.current) {
    const a = el("a", "btn small", "Open it as the worked example ›");
    a.href = `#${encodeURIComponent(ex.problem)}`;
    card.append(a);
  }
  return card;
}

function renderLearn() {
  const { variant, pattern } = S.index.get(S.current);
  const box = $("tab-learn");
  box.innerHTML = "";
  const crumb = pattern.overview ? `<a href="#pattern/${encodeURIComponent(pattern.key)}">${esc(pattern.name)}</a>` : esc(pattern.name);
  const L = variant.lesson;
  const n = pattern.variants.indexOf(variant) + 1;
  box.append(el("div", "crumbs", `${crumb} › ${esc(variant.name)}${L ? ` · subpattern ${n} of ${pattern.variants.length}` : ""}`));
  box.append(el("h1", "", esc(variant.name)));
  box.append(el("div", "meta", `<span class="chip status-${variant.status}" title="${esc(STATUS_TEXT[variant.status])}">${esc(variant.status)} name</span>` +
    (variant.aliases.length ? `<span>also called ${variant.aliases.map((a) => `<i>${esc(a)}</i>`).join(", ")}</span>` : "")));
  if (!L) return renderCard(box, variant);

  const section = (title, cls = "") => { const s = el("section", `lesson-part ${cls}`); s.append(el("h2", "", title)); box.append(s); return s; };
  const goals = el("div", "goals");
  goals.append(el("div", "goals-title", "What you'll learn"));
  const ul = el("ul");
  for (const g of L.goals) ul.append(el("li", "", inline(g)));
  goals.append(ul);
  box.append(goals);

  let s = section("The problem it solves");
  s.append(md(L.problem));
  s.append(el("div", "label-line", "The obvious way:"));
  s.append(tinted(L.bruteForce, L.moves, "brute"));
  s.append(el("p", "cost-line", `<b>Cost:</b> ${inline(L.bruteCost)}`));

  s = section("How it works");
  const steps = el("ol", "moves");
  L.moves.forEach((m, i) => {
    const li = el("li", `move m-${i + 1}`);
    li.append(el("span", `move-chip m-${i + 1}`, `${i + 1}`), el("div", "", `<b>${esc(m.label)}.</b> ${inline(m.text)}`));
    steps.append(li);
  });
  s.append(steps);
  s.append(el("div", "label-line", "The template, with each step's lines in its color:"));
  s.append(tinted(variant.template, L.moves));

  s = section("Why it works");
  s.append(el("div", "holds", `<b>What the table means:</b> ${inline(L.holds)}`));
  const why = el("ul", "why");
  for (const w of L.why) why.append(el("li", "", inline(w)));
  s.append(why);

  s = section("Worked examples");
  s.append(el("p", "muted small", "Each example is solved with the same steps, tinted the same colors. Press play, or step with ← →, and watch the structures change. Change the input and press Run to watch it run on yours."));
  L.examples.forEach((ex, i) => s.append(lessonExample(ex, i, L.moves)));

  if (L.toolkit.length) {
    s = section("Python toolkit");
    for (const [label, code, noteText] of L.toolkit) {
      const t = el("div", "tool");
      t.append(el("div", "tool-label", `<b>${esc(label)}</b>`));
      t.append(highlighted(code, "python"));
      if (noteText) t.append(el("p", "small", inline(noteText)));
      s.append(t);
    }
  }

  s = section("Cost");
  s.append(el("p", "", `<b>${esc(variant.complexity)}.</b> ${inline(L.costWhy)}`));

  s = section("Spot it");
  s.append(el("p", "", "Problems that need this usually say something like:"));
  const sig = el("ul", "signals");
  for (const x of variant.signals) sig.append(el("li", "", inline(x)));
  s.append(sig);

  s = section("Common mistakes");
  s.append(el("p", "muted small", "Each one has a hidden test built to catch it."));
  for (const m of variant.mistakes) {
    const card = el("div", "mistake");
    card.append(el("p", "", `<b>${inline(m.charAt(0).toUpperCase() + m.slice(1))}.</b>`));
    const pair = L.mistakeCode[m];
    if (pair) {
      const two = el("div", "wrong-right");
      const w = el("div", "wrong", '<div class="wr-label">✗ wrong</div>');
      w.append(highlighted(pair[0], "python"));
      const r = el("div", "right", '<div class="wr-label">✓ right</div>');
      r.append(highlighted(pair[1], "python"));
      two.append(w, r);
      card.append(two);
    }
    s.append(card);
  }

  s = section("About the name", "name-note");
  s.append(nameNote(variant));

  const p = progress();
  const ex = variant.problems.find((x) => x.role === "example");
  if (ex && !p.solved[ex.key]) {
    const go = el("button", "btn primary", "Now step through the worked example ›");
    go.onclick = () => { if (S.current !== ex.key) location.hash = encodeURIComponent(ex.key); showTab("problem"); };
    const end = el("div", "lesson-end");
    end.append(go);
    box.append(end);
  }
}

// a variant without a lesson (Structures): its reference card
function renderCard(box, variant) {
  box.append(el("p", "idea", inline(variant.idea)));
  box.append(el("div", "invariant", `<b>What stays true.</b> ${inline(variant.invariant)}`));
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
    for (const [op, cost, noteText] of variant.referenceTable) t.append(el("tr", "", `<td><code>${esc(op)}</code></td><td><b>${esc(cost)}</b></td><td class="muted">${esc(noteText)}</td>`));
    box.append(t);
  }
  list("Signals: when a problem says…", variant.signals);
  list("Common mistakes (each one has a test that catches it)", variant.mistakes);
  box.append(el("h3", "", "About the name"));
  box.append(nameNote(variant));
}

//a pattern's overview: how its structure works, and the map of its subpatterns

function showOverview(key) {
  showView("overview");
  const pattern = S.data.patterns.find((p) => p.key === key);
  const p = progress();
  const box = $("overview-view");
  box.innerHTML = "";
  const page = el("div", "overview-page");
  const head = el("section", "panel");
  head.append(el("div", "crumbs", `<a href="#" class="wall-link">${esc(C.title)}</a> › ${esc(pattern.name)}`));
  head.querySelector(".wall-link").onclick = (e) => { e.preventDefault(); history.pushState(null, "", location.pathname); showWall(); };
  head.append(el("h1", "", esc(pattern.name)));
  head.append(el("p", "idea", inline(pattern.idea)));
  head.append(md(pattern.overview));
  page.append(head);

  const first = pattern.variants[0]?.lesson?.examples[0];
  if (first) {
    const demo = el("section", "panel");
    demo.append(el("h2", "", "Watch a hash table answer"));
    demo.append(el("p", "muted small", "The set is drawn as its 8 buckets. On each lookup, watch only one bucket get checked, never the whole set. Change the input and press Run to try your own."));
    makePlayer(demo, { trace: first.trace, code: first.code, moves: pattern.variants[0].lesson.moves, viz: first.viz, compact: true,
      custom: { py, source: first.code, function: first.function, args: first.args, notes: first.notes } });
    page.append(demo);
  }

  const map = el("section", "panel");
  map.append(el("h2", "", "The map"));
  map.append(el("p", "", "Pick the subpattern by what you need to know about the items you've already passed:"));
  const table = el("table", "map-table");
  table.append(el("tr", "", "<th>You need to know…</th><th>Keep</th><th>Subpattern</th><th>The line that gives it away</th><th></th>"));
  for (const [question, keep, vkey, line] of pattern.map) {
    const v = pattern.variants.find((x) => x.key === vkey);
    const st = variantState(v, p);
    const tr = el("tr");
    tr.append(el("td", "", esc(question)), el("td", "", esc(keep)));
    tr.append(el("td", "", `<b>${esc(v.name)}</b> <span class="chip ${st.laid ? "easy" : ""}">${st.laid ? "laid" : st.started ? `${st.solved}/${st.total}` : "new"}</span>`));
    tr.append(el("td", "map-line"));
    tr.lastChild.append(highlighted(line, "python"));
    const go = el("a", "btn small", st.laid ? "Review ›" : st.started ? "Continue ›" : "Start ›");
    go.href = `#${encodeURIComponent(nextProblem(v, p).key)}`;
    const td = el("td");
    td.append(go);
    tr.append(td);
    table.append(tr);
  }
  for (const x of pattern.planned) {
    if (!x.question) continue;
    const tr = el("tr", "planned-row");
    tr.append(el("td", "", esc(x.question)), el("td", "", esc(x.keep)));
    tr.append(el("td", "", `<b>${esc(x.name)}</b> <span class="chip">planned</span>${x.classic ? `<div class="muted small">${esc(x.classic)}</div>` : ""}`));
    tr.append(el("td", "map-line"));
    tr.lastChild.append(highlighted(x.line, "python"));
    tr.append(el("td"));
    table.append(tr);
  }
  const wrap = el("div", "table-scroll");
  wrap.append(table);
  map.append(wrap);
  map.append(el("p", "muted small", "Learn them in this order: each one adds one thing to the one before. A set answers whether; a dict of counts answers how many; a dict of positions answers where a partner was; a dict of lists answers which ones go together."));
  page.append(map);
  box.append(page);
  renderProgressBar();
  window.scrollTo(0, 0);
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
  if (problem.role === "example") {
    $("step-pane").prepend(banner);
    S.player?.refresh();
  } else $("results").prepend(banner);
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

//the worked-example stepper: the visualizer, playing the trace built from the reference solution
//(categories/framework/trace.py), in the right-hand pane

function startStepper(problem) {
  const pane = $("step-pane");
  S.player?.stop();
  pane.innerHTML = "";
  const { variant } = S.index.get(problem.key);
  const locked = () => !walkDone(problem);
  pane.classList.toggle("locked", locked());
  if (locked()) pane.append(el("div", "vp-lock", "<b>First, the design.</b> Think through the steps on the left and show their reasoning; then step through the code here and watch it run."));
  S.player = makePlayer(pane, {
    trace: problem.trace, code: problem.reference, moves: variant.lesson?.moves || [], viz: problem.viz || {},
    kind: problem.kind, locked,
    custom: problem.kind === "function" ? { py, source: problem.reference, function: problem.function, args: problem.trace.call.slice(problem.function.length + 1, -1), notes: problem.notes } : null,
    onStep: (i, n, footer) => {
      if (i !== n - 1) return;
      const p = progress();
      if (p.solved[problem.key]) {
        const next = after(problem.key);
        if (next) {
          const go = el("a", "btn primary", `Next: ${esc(next.title)} ›`);
          go.href = `#${encodeURIComponent(next.key)}`;
          footer.append(go);
        }
      } else {
        const done = el("button", "btn primary", "Mark as studied ✓");
        done.onclick = async () => {
          if (!(await requireSignIn("Sign in to save your progress."))) return;
          solved(problem.key);
        };
        footer.append(done);
      }
    },
  });
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
    if (!$("step-pane").hidden && S.player && !e.target.closest(".vplayer") && (e.key === "ArrowRight" || e.key === "ArrowLeft")) {
      e.preventDefault();
      if (e.key === "ArrowRight") S.player.next(); else S.player.back();
    }
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); runTests(e.shiftKey ? "submit" : "run"); }
  });
  window.addEventListener("beforeunload", saveCode);
  window.addEventListener("hashchange", route);
  window.addEventListener("popstate", route);
  setupSplitters(C.key, () => { cm.refresh(); S.player?.refresh(); });
  await loadCatalog();
  route();
}

ready.then(main);
