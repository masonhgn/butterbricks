"use strict";

// runs Python (Pyodide) off the main thread, so a solution stuck in a loop can be stopped by killing this worker

importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js");

const ROOT = "/home/pyodide/implquest";
let web;

async function init({ files }) {
  const py = await loadPyodide();
  for (const file of files) {
    const text = await (await fetch(`py/${file}`)).text();
    const dir = `${ROOT}/${file.split("/").slice(0, -1).join("/")}`;
    py.FS.mkdirTree(dir);
    py.FS.writeFile(`${ROOT}/${file}`, text);
  }
  py.runPython(`import sys; sys.path.insert(0, "${ROOT}")`);
  web = py.pyimport("framework.web");
  return py.runPython("import sys; sys.version.split()[0]");
}

const ops = {
  init,
  prepare: ({ key, part, mode, source }) => JSON.parse(web.prepare(key, part, mode, source)),
  run: ({ i }) => JSON.parse(web.run_one(i)),
  scratch: ({ source, snippet }) => JSON.parse(web.scratch(source, snippet)),
};

onmessage = async ({ data: { id, op, args } }) => {
  try {
    postMessage({ id, value: await ops[op](args) });
  } catch (e) {
    postMessage({ id, error: String(e && e.message || e) });
  }
};
