"""loads solution source as a module and runs test cases against it. Used by both the CLI and the browser (Pyodide)"""

import contextlib
import io
import linecache
import reprlib
import time
import traceback
import types

from .tests import Context, Fail

SOLUTION_FILE = "solution.py"
STDOUT_LIMIT = 4000
TIME_SCALE = 1.0  # multiplies every time limit; the browser raises it because Python in WebAssembly runs slower

MAX_FRAMES = 6
MAX_VARS = 30  # per frame

_references = {}

_repr = reprlib.Repr()
_repr.maxstring = _repr.maxother = 160
_repr.maxlist = _repr.maxtuple = _repr.maxset = _repr.maxfrozenset = _repr.maxdeque = 12
_repr.maxdict = 10
_repr.maxlevel = 3


class LoadError(Exception):
    def __init__(self, message, details, where=None):
        super().__init__(message)
        self.message = message
        self.details = details
        self.where = where


def load_source(source, name="solution", filename=SOLUTION_FILE):
    """exec source into a fresh module. Raises LoadError with a readable traceback if it doesn't import cleanly"""
    module = types.ModuleType(name)
    module.__file__ = filename
    # the source isn't on disk under this name, so register it for tracebacks to show each line's code
    linecache.cache[filename] = (len(source), None, source.splitlines(True), filename)
    try:
        code = compile(source, filename, "exec")
        with contextlib.redirect_stdout(io.StringIO()):
            exec(code, module.__dict__)
    except SyntaxError as e:
        lines = [f'  File "{filename}", line {e.lineno}']
        if e.text:
            lines += ["    " + e.text.rstrip("\n"), "    " + " " * max((e.offset or 1) - 1, 0) + "^"]
        where = {"line": e.lineno, "frames": []} if e.lineno else None
        raise LoadError(f"SyntaxError: {e.msg} (line {e.lineno})", lines, where) from None
    except Exception as e:
        raise LoadError(f"your code raised {type(e).__name__} while loading", user_traceback(e), error_where(e)) from None
    return module


def reference_module(problem):
    if problem.key not in _references:
        _references[problem.key] = load_source(problem.reference, name=f"{problem.key}_reference", filename="reference.py")
    return _references[problem.key]


def user_traceback(exc):
    """the traceback frames inside the user's file, plus the exception line"""
    frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == SOLUTION_FILE]
    lines = []
    for f in frames[-6:]:
        lines.append(f'  File "{f.filename}", line {f.lineno}, in {f.name}')
        if f.line:
            lines.append(f"    {f.line}")
    lines += traceback.format_exception_only(type(exc), exc)[-1:]
    return [l.rstrip("\n") for l in lines]


def safe_repr(value):
    try:
        return _repr.repr(value)
    except Exception as e:
        return f"<repr failed: {type(e).__name__}>"


def frame_vars(frame):
    """a frame's variables as (name, repr) pairs, with self's attributes listed as self.<name>, and how many were cut"""
    pairs = []
    for name, value in frame.f_locals.items():
        if name.startswith("__") and name.endswith("__"):
            continue
        attrs = getattr(value, "__dict__", None) if name == "self" else None
        if isinstance(attrs, dict):
            pairs += [(f"self.{k}", v) for k, v in attrs.items()]
        else:
            pairs.append((name, value))
    return [[k, safe_repr(v)] for k, v in pairs[:MAX_VARS]], max(len(pairs) - MAX_VARS, 0)


def error_where(exc):
    """where an exception left the user's code: the line to highlight (the innermost frame in the user's file) and
    each of the user's frames, outermost first, with its variables as they were when the error happened"""
    frames = []
    tb = exc.__traceback__
    while tb is not None:
        if tb.tb_frame.f_code.co_filename == SOLUTION_FILE:
            frames.append((tb.tb_frame, tb.tb_lineno))
        tb = tb.tb_next
    if not frames:
        return None
    out = []
    for frame, lineno in frames[-MAX_FRAMES:]:
        name = frame.f_code.co_name
        variables, more = frame_vars(frame) if name != "<module>" else ([], 0)
        out.append({"name": name, "line": lineno, "vars": variables, "more": more})
    return {"line": frames[-1][1], "frames": out}


def run_test(test, solution, reference, part=None):
    """run one test case; always returns a json-friendly dict"""
    ctx = Context(solution, reference)
    out = io.StringIO()
    result = {"name": test.name, "part": part, "hidden": test.hidden, "kind": test.kind,
              "description": test.description, "time_limit": test.time_limit * TIME_SCALE}
    elapsed = 0.0
    where = None
    try:
        test.prepare(ctx)
        with contextlib.redirect_stdout(out):
            start = time.perf_counter()
            try:
                test.execute(ctx)
            finally:
                elapsed = time.perf_counter() - start
        limit = test.time_limit * TIME_SCALE
        if elapsed > limit:
            status, message, details = "slow", f"took {elapsed:.2f}s, the limit is {limit:g}s", [
                "The answers may be right, but this input is sized so that the intended approach finishes well in time.",
                "Look for a loop that re-scans data you could have kept indexed.",
            ]
        else:
            status, message, details = "pass", "", []
    except Fail as e:
        status, message, details, where = "fail", e.message, e.details, e.where
    except RecursionError as e:
        status, message, details = "error", "RecursionError: maximum recursion depth exceeded", user_traceback(e)[:12]
        where = error_where(e)
    except Exception as e:
        status, message, details = "error", f"{type(e).__name__}: {e}", user_traceback(e)
        where = error_where(e)
    if status in ("fail", "error", "slow") and getattr(test, "catches", ""):
        details = list(details) + ["", f"This test is built to catch a common mistake: {test.catches}"]
    stdout = out.getvalue()
    if len(stdout) > STDOUT_LIMIT:
        stdout = stdout[:STDOUT_LIMIT] + f"\n… ({len(stdout) - STDOUT_LIMIT:,} more characters)"
    result.update(status=status, message=message, details=details, elapsed=round(elapsed, 4),
                  metrics=ctx.metrics, notes=ctx.notes, stdout=stdout, where=where)
    return result


def plan(problem, part, mode):
    """the (part, test) pairs a run executes. mode 'run' is the sample tests, 'submit' is everything"""
    return problem.tests_through(part, include_hidden=(mode == "submit"))


def scratch(source, snippet):
    """run a snippet with the user's code already loaded into its namespace; returns stdout or the error"""
    try:
        module = load_source(source)
    except LoadError as e:
        return {"ok": False, "output": "\n".join([e.message, *e.details]), "where": e.where}
    namespace = dict(module.__dict__)
    out = io.StringIO()
    try:
        code = compile(snippet, "scratch.py", "exec")
        with contextlib.redirect_stdout(out):
            exec(code, namespace)
        return {"ok": True, "output": out.getvalue()}
    except Exception as e:
        tb = [f for f in traceback.extract_tb(e.__traceback__) if f.filename in (SOLUTION_FILE, "scratch.py")]
        lines = [f'  File "{f.filename}", line {f.lineno}, in {f.name}\n    {f.line}' for f in tb[-6:]]
        lines += traceback.format_exception_only(type(e), e)
        return {"ok": False, "output": out.getvalue() + "Traceback (most recent call last):\n" + "\n".join(l.rstrip() for l in lines),
                "where": error_where(e)}

