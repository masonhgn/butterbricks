"""builds the traces the visualizer plays (web/visual.js): runs code under a line tracer and records, for every line
about to run, the line number, each variable's value as structured data (so a set can be drawn as a hash table and a
list as cells), where each loop is in the sequence it walks, and any lookup the line is about to do. What the page
shows is what Python actually did.

A function trace runs `function(*args)`. A class trace builds `cls(*init)`, then runs each (method, args) of a
script; each call starts with an "op" step naming it, and the object is shown as `self` throughout, so you watch
every structure inside it change. Notes are attached by matching code fragments to lines.

Snapshots (the "snap" of a step) are JSON values:
  {"t": "int"|"float"|"str"|"bool"|"none", "v": ...}
  {"t": "list"|"tuple"|"deque", "items": [...], "more": n}
  {"t": "set", "items": [...], "buckets": [...], "more": n}   buckets: each item's slot in a toy 8-slot hash table
  {"t": "dict", "cls": "Counter"|..., "entries": [[k, v], ...], "more": n}
  {"t": "obj", "cls": "Raffle", "id": 1, "fields": {...}}
  {"t": "ref", "id": 1}                                        an object already drawn in this step
  {"t": "repr", "v": "..."}                                    anything else"""

import ast
import collections
import sys

from . import runner
from .tests import fresh, show_call

MAX_STEPS = 140  # an authored trace longer than this is a sign its input is too big to follow
MAX_STEPS_CUSTOM = 300  # a trace of input typed on the page stops here
MAX_ITEMS = 40
MAX_DEPTH = 4
BUCKETS = 8
FILENAME = "example.py"


def line_of(source, fragment):
    for i, line in enumerate(source.splitlines(), 1):
        if fragment in line:
            return i
    raise ValueError(f"no line contains {fragment!r}")


#snapshots

def toy_hash(value):
    """a small, stable stand-in for hash(): Python's own string hashes change from run to run, and a drawing whose
    buckets moved every time you reloaded would teach the wrong thing"""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        h = 0
        for ch in value:
            h = (h * 31 + ord(ch)) % 1_000_003
        return h
    if isinstance(value, (tuple, frozenset)):
        h = 7
        for x in (value if isinstance(value, tuple) else sorted(value, key=repr)):
            h = (h * 131 + toy_hash(x)) % 1_000_003
        return h
    if isinstance(value, float):
        return int(value * 1000)
    return len(repr(value))


def bucket(value):
    return ((toy_hash(value) * 2654435761) % 2 ** 32 >> 16) % BUCKETS  # mixed, so similar keys spread out


class Snapshotter:
    """turns values into snapshots; objects keep the same id across a whole trace, so the page can follow them"""

    def __init__(self):
        self.ids = {}

    def __call__(self, value, depth=0, drawn=None):
        drawn = set() if drawn is None else drawn
        if value is None:
            return {"t": "none", "v": None}
        if isinstance(value, bool):
            return {"t": "bool", "v": value}
        if isinstance(value, int):
            return {"t": "int", "v": value} if abs(value) < 2 ** 53 else {"t": "repr", "v": runner.safe_repr(value)}
        if isinstance(value, float):
            return {"t": "float", "v": value}
        if isinstance(value, str):
            return {"t": "str", "v": value if len(value) <= 200 else value[:200] + "…"}
        if depth >= MAX_DEPTH:
            return {"t": "repr", "v": runner.safe_repr(value)}
        sub = lambda x: self(x, depth + 1, drawn)  # noqa: E731
        if isinstance(value, (list, tuple, collections.deque)):
            t = "list" if isinstance(value, list) else "tuple" if isinstance(value, tuple) else "deque"
            items = list(value)
            out = {"t": t, "items": [sub(x) for x in items[:MAX_ITEMS]]}
            if len(items) > MAX_ITEMS:
                out["more"] = len(items) - MAX_ITEMS
            return out
        if isinstance(value, (set, frozenset)):
            items = sorted(value, key=lambda x: (bucket(x), repr(x)))
            out = {"t": "set", "items": [sub(x) for x in items[:MAX_ITEMS]],
                   "buckets": [bucket(x) for x in items[:MAX_ITEMS]]}
            if isinstance(value, frozenset):
                out["cls"] = "frozenset"
            if len(items) > MAX_ITEMS:
                out["more"] = len(items) - MAX_ITEMS
            return out
        if isinstance(value, dict):
            entries = list(value.items())
            out = {"t": "dict", "entries": [[sub(k), sub(v)] for k, v in entries[:MAX_ITEMS]]}
            if type(value) is not dict:
                out["cls"] = type(value).__name__
            if len(entries) > MAX_ITEMS:
                out["more"] = len(entries) - MAX_ITEMS
            return out
        attrs = getattr(value, "__dict__", None)
        if isinstance(attrs, dict) and not isinstance(value, type) and not callable(value):
            n = self.ids.setdefault(id(value), len(self.ids) + 1)
            if n in drawn:
                return {"t": "ref", "id": n}
            drawn.add(n)
            return {"t": "obj", "cls": type(value).__name__, "id": n,
                    "fields": {k: sub(v) for k, v in list(attrs.items())[:MAX_ITEMS]}}
        return {"t": "repr", "v": runner.safe_repr(value)}


#what each line is about to do, worked out from its code

def _target_name(node):
    """`seen` or `self.pos`, as a variable name the snapshot uses"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
        return f"self.{node.attr}"
    return None


def _lookups(source):
    """line -> the lookups that line does: `key in name`, `name.get(key…)`, `name[key]` (reading), as
    (name, key expression) pairs"""
    found = {}
    for node in ast.walk(ast.parse(source)):
        hit = None
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], (ast.In, ast.NotIn)):
            hit = (_target_name(node.comparators[0]), node.left)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get" and node.args:
            hit = (_target_name(node.func.value), node.args[0])
        elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load) and not isinstance(node.slice, ast.Slice):
            hit = (_target_name(node.value), node.slice)
        if hit and hit[0]:
            found.setdefault(node.lineno, []).append((hit[0], ast.unparse(hit[1])))
    return found


def _loops(source):
    """each `for` loop over a plain sequence: its line, the sequence's name, and the loop variable to label it with"""
    loops = {}
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.For):
            continue
        it, label = node.iter, ast.unparse(node.target)
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == "enumerate" and it.args:
            it = it.args[0]
            if isinstance(node.target, ast.Tuple) and node.target.elts:
                label = ast.unparse(node.target.elts[0])
        name = _target_name(it)
        if name:
            loops[node.lineno] = (name, label)
    return loops


def _resolve(name, frame):
    if name.startswith("self."):
        obj = frame.f_locals.get("self")
        return getattr(obj, name[5:], None) if obj is not None else None
    return frame.f_locals.get(name, frame.f_globals.get(name))


class Tracer:
    def __init__(self, source, notes=None, max_steps=MAX_STEPS, truncate=False, key="example"):
        self.source = source
        self.lines = source.splitlines()
        self.notes = {line_of(source, frag): text for frag, text in (notes or {}).items()}
        self.loops = _loops(source)
        self.lookups = _lookups(source)
        self.snap = Snapshotter()
        self.steps = []
        self.max_steps = max_steps
        self.truncate = truncate
        self.truncated = False
        self.key = key
        self.counts = {}  # (frame id, loop line) -> how many times that loop has taken an item
        self.prev_line = {}  # frame id -> the last line it ran
        self.obj = None  # a class trace's object, shown as self on every step

    class Full(Exception):
        pass

    def record(self, step):
        if len(self.steps) >= self.max_steps:
            if self.truncate:
                self.truncated = True
                raise Tracer.Full()
            raise ValueError(f"{self.key}: the trace is longer than {self.max_steps} steps; use a smaller input")
        self.steps.append(step)

    def snapshot_frame(self, frame):
        out = {}
        for name, value in frame.f_locals.items():
            if name.startswith("__") and name.endswith("__"):
                continue
            out[name] = self.snap(value)
        if "self" not in out and self.obj is not None:
            out["self"] = self.snap(self.obj)
        return out

    def cursors(self, frame):
        fid = id(frame)
        out = []
        for line, (name, label) in self.loops.items():
            n = self.counts.get((fid, line))
            if n:
                out.append({"array": name, "index": n - 1, "label": label})
        return out

    def __call__(self, frame, event, arg):
        if frame.f_code.co_filename != FILENAME:
            return None
        fid = id(frame)
        if event == "call":  # a new frame can reuse a finished one's id
            self.prev_line.pop(fid, None)
            for k in [k for k in self.counts if k[0] == fid]:
                del self.counts[k]
            return self
        if event not in ("line", "return"):
            return self
        line = frame.f_lineno
        if event == "line" and line in self.loops:
            # arriving at a loop from above starts it over; arriving from its body means it takes the next item
            if self.prev_line.get(fid, 0) < line:
                self.counts[(fid, line)] = 0
        pairs, _ = runner.frame_vars(frame)
        step = {"line": line, "vars": pairs, "in": frame.f_code.co_name, "snap": self.snapshot_frame(frame),
                "cursors": self.cursors(frame)}
        if event == "return":
            if frame.f_code.co_name == "__init__":
                return self  # constructing returns None; not worth a step
            step["returns"] = runner.safe_repr(arg)
            step["note"] = f"Returns {runner.safe_repr(arg)}."
        else:
            if line in self.notes:
                step["note"] = self.notes[line]
            events = []
            for name, expr in self.lookups.get(line, []):
                table = _resolve(name, frame)
                if not isinstance(table, (set, frozenset, dict)):
                    continue
                try:
                    key = eval(expr, frame.f_globals, dict(frame.f_locals))  # our own example code, never the learner's
                    hash(key)
                except Exception:  # noqa: BLE001
                    continue
                events.append({"kind": "lookup", "in": name, "expr": expr, "key": self.snap(key),
                               "found": key in table, "bucket": bucket(key) if isinstance(table, (set, frozenset)) else None})
            if events:
                step["events"] = events
        self.record(step)
        if event == "line" and line in self.loops:
            self.counts[(fid, line)] = self.counts.get((fid, line), 0) + 1
        self.prev_line[fid] = line
        return self

    def finish(self):
        used = {s["line"] for s in self.steps}
        unused = set(self.notes) - used
        if unused and not self.truncated:
            raise ValueError(f"{self.key}: the trace never reaches lines {sorted(unused)}, which have notes")


def trace_function(source, function, args, notes=None, key="example", custom=False):
    """trace function(*args) from source; custom traces (input typed on the page) stop at MAX_STEPS_CUSTOM instead of
    failing"""
    t = Tracer(source, notes, MAX_STEPS_CUSTOM if custom else MAX_STEPS, truncate=custom, key=key)
    module = runner.load_source(source, name="example", filename=FILENAME)
    fn = getattr(module, function)
    call = f"{function}({', '.join(repr(a) for a in args)})"
    error = None
    out = None
    sys.settrace(t)
    try:
        out = fn(*fresh(tuple(args)))
    except Tracer.Full:
        pass
    except Exception as e:  # noqa: BLE001
        if not custom:
            raise
        error = f"{type(e).__name__}: {e}"
    finally:
        sys.settrace(None)
    t.finish()
    result = runner.safe_repr(out) if not (t.truncated or error) else ""
    return {"call": call, "script": [call], "result": result, "steps": t.steps,
            "truncated": t.truncated, "error": error}


def trace_class(source, cls_name, init, script, notes=None, key="example"):
    t = Tracer(source, notes, key=key)
    module = runner.load_source(source, name="example", filename=FILENAME)
    cls = getattr(module, cls_name)
    call = f"{cls_name}({', '.join(repr(a) for a in init)})"
    results = []
    sys.settrace(t)
    try:
        t.record({"op": f"obj = {call}", "line": None, "vars": [], "snap": {}, "cursors": []})
        t.obj = cls(*fresh(tuple(init)))
        for method, args in script:
            t.record({"op": f"obj.{show_call(method, args)}", "line": None, "vars": [],
                      "snap": {"self": t.snap(t.obj)}, "cursors": []})
            results.append(getattr(t.obj, method)(*fresh(tuple(args))))
    finally:
        sys.settrace(None)
    t.finish()
    return {"call": call, "script": [call] + [f"obj.{show_call(m, a)}" for m, a in script],
            "result": runner.safe_repr(results[-1]) if results else "", "steps": t.steps}


def build_trace(problem):
    """a brick's worked example, traced from its reference solution"""
    if problem.kind == "class":
        return trace_class(problem.reference, problem.function, problem.trace_init, problem.trace_script,
                           problem.notes, problem.key)
    return trace_function(problem.reference, problem.function, problem.trace_args, problem.notes, problem.key)
