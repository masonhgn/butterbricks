#!/usr/bin/env python3
"""builds what the Patterns category of the site needs: web/patterns/patterns.json (every pattern, variant, problem,
drill and worked-example trace) and web/patterns/py/ (the shared framework, the bricks package and browser.py, which
the browser loads into Pyodide to run tests)"""

import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CATEGORIES = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, CATEGORIES)  # the shared framework package

from bricks import PATTERNS, PLANNED  # noqa: E402
from bricks.model import ROLE_LABELS  # noqa: E402
from framework import runner  # noqa: E402
from framework.tests import REFERENCE, fresh, show  # noqa: E402
from trace import build_trace  # noqa: E402

WEB = os.path.join(CATEGORIES, "..", "web", "patterns")
PACKAGES = [(CATEGORIES, "framework"), (HERE, "bricks")]
MODULES = [(HERE, "browser.py")]


def problem_manifest(problem):
    reference = runner.reference_module(problem)
    for t in problem.tests:  # show a sample's expected value, even when the test takes it from the reference
        if not t.hidden and getattr(t, "expect", None) is REFERENCE and not callable(t._args):
            t.shown_expect = show(getattr(reference, problem.function)(*fresh(t.args())))
    out = {
        "key": problem.key, "role": problem.role, "roleLabel": ROLE_LABELS[problem.role], "title": problem.title,
        "statement": problem.statement, "function": problem.function, "signature": problem.signature,
        "starter": problem.starter, "reference": problem.reference, "hints": problem.hints,
        "changes": problem.changes, "takeaway": problem.takeaway, "tests": [t.summary() for t in problem.tests],
    }
    if problem.role == "example":
        out["trace"] = build_trace(problem)
    return out


def variant_manifest(v):
    return {
        "key": v.key, "name": v.name, "status": v.status, "aliases": v.aliases, "sources": v.sources,
        "idea": v.idea, "invariant": v.invariant, "template": v.template, "complexity": v.complexity,
        "signals": v.signals, "nearMisses": v.near_misses, "mistakes": v.mistakes, "prerequisites": v.prerequisites,
        "problems": [problem_manifest(p) for p in v.problems],
        "drills": [{"key": d.key, "statement": d.statement, "answer": v.name, "choices": d.choices,
                    "signal": d.signal, "wrongSignals": d.wrong_signals, "why": d.why} for d in v.drills],
    }


def main():
    out = os.path.join(WEB, "py")
    shutil.rmtree(out, ignore_errors=True)
    files = []
    for root, pkg in PACKAGES:
        os.makedirs(os.path.join(out, pkg))
        for name in sorted(os.listdir(os.path.join(root, pkg))):
            if name.endswith(".py"):
                shutil.copyfile(os.path.join(root, pkg, name), os.path.join(out, pkg, name))
                files.append(f"{pkg}/{name}")
    for root, name in MODULES:
        shutil.copyfile(os.path.join(root, name), os.path.join(out, name))
        files.append(name)
    data = {
        "files": files,
        "planned": PLANNED,
        "patterns": [{"key": p.key, "name": p.name, "status": p.status, "aliases": p.aliases, "idea": p.idea,
                      "sources": p.sources, "variants": [variant_manifest(v) for v in p.variants]} for p in PATTERNS],
    }
    with open(os.path.join(WEB, "patterns.json"), "w") as f:
        json.dump(data, f)
    n = sum(len(v.problems) for p in PATTERNS for v in p.variants)
    print(f"wrote web/patterns/patterns.json ({len(PATTERNS)} pattern, {n} problems) and web/patterns/py/ ({len(files)} files)")


if __name__ == "__main__":
    main()
