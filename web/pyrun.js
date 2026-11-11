"use strict";

// shared by the categories that run Python in the browser (Implementation, Patterns): the client for the Pyodide
// worker (/pyworker.js), running a test plan with a live row per test, the red error line in the editor, and the
// gdb-style variables panel. Loads after common.js

//the worker. A call that runs far past its limit is stopped by killing the worker and starting a fresh one

function startPython({ base, files, onStatus }) {
  const py = { ready: null, readyDone: false };
  let worker, nextCall = 0;
  const waiting = new Map();

  function start() {
    worker = new Worker("/pyworker.js?v=bbs-6");
    worker.onmessage = ({ data }) => {
      const p = waiting.get(data.id);
      if (!p) return;
      waiting.delete(data.id);
      clearTimeout(p.timer);
      if (data.error !== undefined) p.reject(new Error(data.error));
      else p.resolve(data.value);
    };
    worker.onerror = () => onStatus("error", "Python failed to load");
    onStatus("busy", "Loading Python…");
    py.readyDone = false;
    py.ready = send("init", { base, files }).then((version) => {
      py.readyDone = true;
      onStatus("ready", `Python ${version} ready`);
    }, (e) => {
      onStatus("error", "Python failed to load");
      throw e;
    });
  }

  function send(op, args, timeout) {
    return new Promise((resolve, reject) => {
      const id = nextCall++;
      const p = { resolve, reject };
      if (timeout) p.timer = setTimeout(() => {
        waiting.delete(id);
        worker.terminate();
        for (const q of waiting.values()) { clearTimeout(q.timer); q.reject(new Error("Python was restarted")); }
        waiting.clear();
        start();
        const err = new Error("killed");
        err.killed = true;
        reject(err);
      }, timeout);
      waiting.set(id, p);
      worker.postMessage({ id, op, args });
    });
  }

  py.call = async (op, args, timeout) => {
    await py.ready;
    return send(op, args, timeout);
  };
  start();
  return py;
}

//the line an error came from, marked in red in the editor with the error message under it

function errorLine(cm) {
  let mark = null;
  return {
    get shown() { return mark !== null; },
    clear() {
      if (!mark) return;
      cm.removeLineClass(mark.handle, "background", "cm-error-line");
      cm.removeLineClass(mark.handle, "gutter", "cm-error-gutter");
      mark.widget.clear();
      mark = null;
    },
    show(where, message) {
      this.clear();
      const n = (where?.line ?? 0) - 1;
      if (n < 0 || n >= cm.lineCount()) return;
      const handle = cm.addLineClass(n, "background", "cm-error-line");
      cm.addLineClass(handle, "gutter", "cm-error-gutter");
      const widget = cm.addLineWidget(handle, el("div", "cm-error-widget", esc(message || "error")));
      mark = { handle, widget };
      cm.scrollIntoView({ line: n, ch: 0 }, 80);
    },
  };
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

//one row per test

const TEST_ICONS = { pass: "✓", fail: "✗", error: "!", slow: "⏱", killed: "⏱", pending: "·", running: "◌", skipped: "–" };

// info is the test's manifest entry (description, preview); errors is the editor's errorLine
function testResultRow(r, { open = false, info = {}, errors = null } = {}) {
  const row = el("div", `test-row st-${r.status}`);
  const head = el("button", "test-head");
  const time = r.elapsed !== undefined ? `${r.elapsed.toFixed(3)}s` : "";
  head.innerHTML = `<span class="icon">${TEST_ICONS[r.status]}</span>` +
    `<span class="tname">${esc(r.name)}${r.hidden ? '<span class="badge">hidden</span>' : ""}</span>` +
    (r.part ? `<span class="tpart">part ${r.part}</span>` : "") + `<span class="time">${time}</span>`;
  row.append(head);
  if (r.status === "pending" || r.status === "running") return row;

  const body = el("div", "test-body");
  body.hidden = !open;
  head.onclick = () => {
    body.hidden = !body.hidden;
    if (!body.hidden && r.where && errors) errors.show(r.where, r.message);
  };
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

//running a plan: the worker loads the code and lists the tests, then they run one at a time, each drawn as it ends.
//Returns { loadError } when the code doesn't load, else { results }

async function runTestPlan({ py, args, list, summary, errors, info }) {
  const plan = await py.call("prepare", args, 60000);
  if (plan.error) {
    summary.className = "results-summary fail";
    summary.textContent = "Your code didn't load";
    const box = el("div", "load-error");
    box.append(el("div", "msg", esc(plan.error)));
    if (plan.details.length) box.append(el("pre", "", esc(plan.details.join("\n"))));
    if (plan.where?.frames.length) box.append(variablesPanel(plan.where));
    list.append(box);
    errors.show(plan.where, plan.error);
    return { loadError: plan };
  }
  const rows = plan.tests.map((t) => {
    const row = testResultRow({ ...t, status: "pending" });
    list.append(row);
    return row;
  });
  summary.textContent = `Running ${plural(plan.tests.length, "test")}…`;

  const results = [];
  let firstFailShown = false;
  for (let i = 0; i < plan.tests.length; i++) {
    const t = plan.tests[i];
    rows[i].replaceWith(rows[i] = testResultRow({ ...t, status: "running" }));
    let r;
    const hard = Math.round(t.time_limit * 3 + 8);
    try {
      r = await py.call("run", { i }, hard * 1000);
    } catch (e) {
      if (!e.killed) throw e;
      r = { ...t, status: "killed", message: `stopped after ${hard}s; the limit is ${t.time_limit}s`,
            details: ["Probably an infinite loop, or an approach that's far too slow for this input size."],
            elapsed: hard, metrics: [], notes: [], stdout: "" };
      summary.textContent = "Restarting Python after a stuck test…";
      if (i + 1 < plan.tests.length) await py.call("prepare", args, 60000);
    }
    results.push(r);
    const open = r.status !== "pass" && !firstFailShown;
    firstFailShown ||= open;
    if (r.where && !errors.shown) errors.show(r.where, r.message);
    rows[i].replaceWith(rows[i] = testResultRow(r, { open, info: info(r), errors }));
    summary.textContent = `Running… ${results.length} / ${plan.tests.length}`;
  }
  return { results };
}

// the summary line once a run ends: "✓ 5 / 5 tests passed 0.12s"
function summarizeRun(summary, results, mode) {
  const passed = results.filter((r) => r.status === "pass").length;
  const total = results.length;
  const secs = results.reduce((s, r) => s + (r.elapsed || 0), 0);
  const all = passed === total;
  summary.className = `results-summary ${all ? "pass" : "fail"}`;
  const kind = mode === "submit" ? "tests" : "sample tests";
  summary.innerHTML = `${all ? "✓" : "✗"} ${passed} / ${total} ${kind} passed <span class="muted small">${secs.toFixed(2)}s</span>`;
  return all;
}
