"""builds a worked example's trace: runs its reference solution on its trace_args under a line tracer and records,
for every line about to run, the line number and every local variable. The stepper on the page walks this trace, so
what it shows is what Python actually did. Notes and predictions are attached by matching code fragments to lines."""

import sys

from framework import runner
from framework.tests import fresh

MAX_STEPS = 80
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
    fn = getattr(module, problem.function)
    steps = []

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != FILENAME:
            return None
        if event in ("line", "return"):
            line = frame.f_lineno
            local = {k: v for k, v in frame.f_locals.items() if not k.startswith("__")}
            step = {"line": line, "vars": [[k, runner.safe_repr(v)] for k, v in local.items()]}
            if event == "return":
                step["returns"] = runner.safe_repr(arg)
                step["note"] = f"Returns {runner.safe_repr(arg)}."
            else:
                if line in notes:
                    step["note"] = notes[line]
                if line in predicts:
                    value = eval(predicts[line], frame.f_globals, dict(local))
                    if not isinstance(value, bool):
                        raise ValueError(f"{problem.key}: prediction {predicts[line]!r} must be True or False")
                    step["predict"] = {"ask": predicts[line], "answer": value}
            steps.append(step)
            if len(steps) > MAX_STEPS:
                raise ValueError(f"{problem.key}: the trace is longer than {MAX_STEPS} steps; use a smaller input")
        return tracer

    sys.settrace(tracer)
    try:
        result = fn(*fresh(tuple(problem.trace_args)))
    finally:
        sys.settrace(None)
    unused = (set(notes) | set(predicts)) - {s["line"] for s in steps}
    if unused:
        raise ValueError(f"{problem.key}: the trace never reaches lines {sorted(unused)}, which have notes")
    return {"call": f"{problem.function}({', '.join(repr(a) for a in problem.trace_args)})",
            "result": runner.safe_repr(result), "steps": steps}
