"use strict";

// runs Python (Pyodide) off the main thread, so a solution stuck in a loop can be stopped by killing this worker.
// Shared by every category that runs Python: each page starts its own worker and passes `base`, the folder its
// py/ files live in (like "/implementation/"). Those files always include browser.py, the module these ops call:
// prepare(key, part, mode, source), run_one(i) and scratch(source, snippet), each taking and returning json

importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js");

const ROOT = "/home/pyodide/butterbricks";
let browser;

async function init({ base, files }) {
  const py = await loadPyodide();
  for (const file of files) {
    const text = await (await fetch(`${base}py/${file}`)).text();
    const dir = `${ROOT}/${file.split("/").slice(0, -1).join("/")}`;
    py.FS.mkdirTree(dir);
    py.FS.writeFile(`${ROOT}/${file}`, text);
  }
  py.runPython(`import sys; sys.path.insert(0, "${ROOT}")`);
  browser = py.pyimport("browser");
  return py.runPython("import sys; sys.version.split()[0]");
}

const ops = {
  init,
  prepare: ({ key, part, mode, source }) => JSON.parse(browser.prepare(key, part ?? null, mode, source)),
  run: ({ i }) => JSON.parse(browser.run_one(i)),
  scratch: ({ source, snippet }) => JSON.parse(browser.scratch(source, snippet)),
};

onmessage = async ({ data: { id, op, args } }) => {
  try {
    postMessage({ id, value: await ops[op](args) });
  } catch (e) {
    postMessage({ id, error: String(e && e.message || e) });
  }
};
