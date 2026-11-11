"""builds a worked example's trace: runs its reference solution under a line tracer and records, for every line about
to run, the line number and the variables. The stepper on the page walks this trace, so what it shows is what Python
actually did. Notes and predictions are attached by matching code fragments to lines.

A function example runs `function(*trace_args)`. A class example builds `cls(*trace_init)`, then runs each
(method, args) of `trace_script`; each call starts with an "op" step naming it, and variables show the object's own
fields as self.<name>, so you watch every structure inside it change."""

import sys

from . import runner
from .tests import fresh, show_call

MAX_STEPS = 140
FILENAME = "example.py"


def line_of(source, fragment):
    for i, line in enumerate(source.splitlines(), 1):
        if fragment in line:
            return i
    raise ValueError(f"no line contains {fragment!r}")


def build_trace(problem):
    source = problem.reference
    notes = {line_of(source, frag): text for frag, text in problem.notes.items()}
    predicts = {line_of(source, frag): expr for frag, expr in problem.predict.items()}
    module = runner.load_source(source, name="example", filename=FILENAME)
    steps = []

    def record(step):
        steps.append(step)
        if len(steps) > MAX_STEPS:
            raise ValueError(f"{problem.key}: the trace is longer than {MAX_STEPS} steps; use a smaller input")

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != FILENAME:
            return None
        if event in ("line", "return"):
            line = frame.f_lineno
            pairs, _ = runner.frame_vars(frame)
            step = {"line": line, "vars": pairs, "in": frame.f_code.co_name}
            if event == "return":
                if frame.f_code.co_name == "__init__":
                    return tracer  # constructing returns None; not worth a step
                step["returns"] = runner.safe_repr(arg)
                step["note"] = f"Returns {runner.safe_repr(arg)}."
            else:
                if line in notes:
                    step["note"] = notes[line]
                if line in predicts:
                    value = eval(predicts[line], frame.f_globals, dict(frame.f_locals))
                    if not isinstance(value, bool):
                        raise ValueError(f"{problem.key}: prediction {predicts[line]!r} must be True or False")
                    step["predict"] = {"ask": predicts[line], "answer": value}
            record(step)
        return tracer

    if problem.kind == "class":
        cls = getattr(module, problem.function)
        call = f"{problem.function}({', '.join(repr(a) for a in problem.trace_init)})"
        sys.settrace(tracer)
        try:
            record({"op": f"obj = {call}", "line": None, "vars": []})
            obj = cls(*fresh(tuple(problem.trace_init)))
            results = []
            for method, args in problem.trace_script:
                record({"op": f"obj.{show_call(method, args)}", "line": None, "vars": []})
                results.append(getattr(obj, method)(*fresh(tuple(args))))
        finally:
            sys.settrace(None)
        script = [call] + [f"obj.{show_call(m, a)}" for m, a in problem.trace_script]
        result = runner.safe_repr(results[-1]) if results else ""
    else:
        fn = getattr(module, problem.function)
        sys.settrace(tracer)
        try:
            out = fn(*fresh(tuple(problem.trace_args)))
        finally:
            sys.settrace(None)
        call = f"{problem.function}({', '.join(repr(a) for a in problem.trace_args)})"
        script = [call]
        result = runner.safe_repr(out)
    unused = (set(notes) | set(predicts)) - {s["line"] for s in steps}
    if unused:
        raise ValueError(f"{problem.key}: the trace never reaches lines {sorted(unused)}, which have notes")
    return {"call": call, "script": script, "result": result, "steps": steps}
