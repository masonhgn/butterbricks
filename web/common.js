"use strict";

// shared by every Butterbrick page: helpers, localStorage, the password gate, splitters, editor keys and confetti.
// Each track's app.js loads after this and uses these as globals

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html !== undefined) e.innerHTML = html; return e; };

//storage: every key is butterbrick:<track>:<name>. A null value removes the key

function storage(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(key);
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch (e) { return null; }
}

function storedJson(key, fallback) {
  try { return JSON.parse(storage(key)) ?? fallback; } catch (e) { return fallback; }
}

// before the merge the two sites kept their data under sqlquest: and implquest:. Copy it over once, so code, notes and
// progress saved on the same address carry into Butterbrick. The old keys stay, in case anything goes wrong
(function migrateStorage() {
  try {
    if (localStorage.getItem("butterbrick:migrated")) return;
    const moves = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      let to = null;
      if (k === "sqlquest:unlocked") to = "butterbrick:unlocked";
      else if (k === "sqlquest:editor-h") to = null;  // the SQL editor's height, from a layout that no longer exists
      else if (k.startsWith("sqlquest:")) to = `butterbrick:sql:${k.slice(9)}`;
      else if (k.startsWith("implquest:")) to = `butterbrick:impl:${k.slice(10)}`;
      if (to && localStorage.getItem(to) === null) moves.push([to, localStorage.getItem(k)]);
    }
    for (const [k, v] of moves) localStorage.setItem(k, v);
    localStorage.setItem("butterbrick:migrated", "1");
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
  const leftKey = `butterbrick:${track}:left-w`, bottomKey = `butterbrick:${track}:results-h`;
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

function confetti(count) {
  const canvas = document.createElement("canvas");
  canvas.id = "confetti";
  document.body.appendChild(canvas);
  const dpr = window.devicePixelRatio || 1;
  canvas.width = innerWidth * dpr;
  canvas.height = innerHeight * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  const colors = ["#f6cd57", "#ffe9a3", "#eebc3f", "#1e7f45", "#7fd49a", "#e8573f", "#3b82f6"];
  // two bursts from the bottom corners, aimed up and inward
  const bits = Array.from({ length: count }, (_, i) => {
    const left = i % 2 === 0;
    const angle = (left ? -60 : -120) * Math.PI / 180 + (Math.random() - 0.5) * 0.9;
    const speed = 9 + Math.random() * 9;
    return {
      x: left ? 0 : innerWidth, y: innerHeight * 0.9,
      vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
      w: 6 + Math.random() * 6, h: 8 + Math.random() * 8,
      rot: Math.random() * Math.PI, vr: (Math.random() - 0.5) * 0.3,
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
      b.rot += b.vr;
      ctx.save();
      ctx.translate(b.x, b.y);
      ctx.rotate(b.rot);
      ctx.fillStyle = b.color;
      ctx.fillRect(-b.w / 2, -b.h / 2, b.w, b.h * Math.cos(b.rot * 2));
      ctx.restore();
    }
    if (t < 3000) requestAnimationFrame(frame);
    else canvas.remove();
  }
  requestAnimationFrame(frame);
}

//password gate. It only keeps casual visitors out: the site's files are public, so it is not real security

const PASSWORD_SHA256 = "03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4";
const UNLOCK_KEY = "butterbrick:unlocked";

async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function unlock() {
  if (storage(UNLOCK_KEY) === PASSWORD_SHA256) return Promise.resolve();
  const logo = document.querySelector('link[rel="icon"]')?.href || "";
  const gate = el("div", "gate", `<form class="gate-box">
    <div class="brand"><img class="logo" src="${esc(logo)}" alt=""> Butterbrick</div>
    <label for="gate-password">Password</label>
    <input type="password" id="gate-password" autocomplete="current-password" required>
    <div class="gate-error" hidden>Wrong password.</div>
    <button class="btn primary" type="submit">Enter</button>
  </form>`);
  document.body.append(gate);
  const input = gate.querySelector("input");
  input.focus();
  return new Promise((resolve) => {
    gate.querySelector("form").onsubmit = async (e) => {
      e.preventDefault();
      if (await sha256(input.value) === PASSWORD_SHA256) {
        storage(UNLOCK_KEY, PASSWORD_SHA256);
        gate.remove();
        resolve();
      } else {
        gate.querySelector(".gate-error").hidden = false;
        input.select();
      }
    };
  });
}
