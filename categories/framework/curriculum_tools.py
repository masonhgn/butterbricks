"""what every brick-based category (Patterns, Structures) does the same way: build its page's data, check its content,
run its problems in the terminal, and answer the browser's worker. Each category's build_web.py, terminal.py and
browser.py are thin wrappers that pass in their own content package (`bricks`)."""

import json
import os
import shutil
import sys

from . import runner
from .curriculum import BLANK, ROLE_LABELS, check_category
from .tests import REFERENCE, fresh, show
from .trace import build_trace


#the page's data

def _problem_manifest(problem):
    reference = runner.reference_module(problem)
    for t in problem.tests:  # show a sample's expected value, even when the test takes it from the reference
        if not t.hidden and getattr(t, "expect", None) is REFERENCE and not callable(getattr(t, "_args", None)):
            t.shown_expect = show(getattr(reference, problem.function)(*fresh(t.args())))
    out = {
        "key": problem.key, "role": problem.role, "roleLabel": ROLE_LABELS[problem.role], "title": problem.title,
        "kind": problem.kind, "statement": problem.statement, "function": problem.function,
        "signature": problem.signature, "starter": problem.starter, "reference": problem.reference,
        "hints": problem.hints, "changes": problem.changes, "takeaway": problem.takeaway,
        "operations": [list(op) for op in problem.operations],
        "tests": [t.summary() for t in problem.tests],
    }
    if problem.design:
        d = problem.design
        out["design"] = {"state": d.state, "invariant": d.invariant, "costs": d.costs, "checks": d.checks}
    if problem.walkthrough:
        out["walkthrough"] = [{"text": s.text, "ask": s.ask, "options": s.options, "answer": s.answer, "why": s.why}
                              for s in problem.walkthrough]
    if problem.role == "example":
        out["trace"] = build_trace(problem)
    return out


def _variant_manifest(v):
    return {
        "key": v.key, "name": v.name, "status": v.status, "aliases": v.aliases, "sources": v.sources,
        "idea": v.idea, "invariant": v.invariant, "template": v.template, "complexity": v.complexity,
        "signals": v.signals, "nearMisses": v.near_misses, "mistakes": v.mistakes, "prerequisites": v.prerequisites,
        "referenceTable": [list(r) for r in v.reference_table],
        "problems": [_problem_manifest(p) for p in v.problems],
        "drills": [{"key": d.key, "statement": d.statement, "question": d.question, "answer": d.answer,
                    "choices": d.choices, "signal": d.signal, "wrongSignals": d.wrong_signals, "why": d.why}
                   for d in v.drills],
    }


def build(here, web, patterns, planned, label):
    """writes web/<category>/<label>.json and web/<category>/py/: the shared framework, the content package and
    browser.py, which the browser loads into Pyodide"""
    check_category(patterns)
    categories = os.path.dirname(here)
    out = os.path.join(web, "py")
    shutil.rmtree(out, ignore_errors=True)
    files = []
    for root, pkg in [(categories, "framework"), (here, "bricks")]:
        os.makedirs(os.path.join(out, pkg))
        for name in sorted(os.listdir(os.path.join(root, pkg))):
            if name.endswith(".py"):
                shutil.copyfile(os.path.join(root, pkg, name), os.path.join(out, pkg, name))
                files.append(f"{pkg}/{name}")
    shutil.copyfile(os.path.join(here, "browser.py"), os.path.join(out, "browser.py"))
    files.append("browser.py")
    data = {
        "files": files,
        "planned": planned,
        "patterns": [{"key": p.key, "name": p.name, "status": p.status, "aliases": p.aliases, "idea": p.idea,
                      "sources": p.sources, "planned": p.planned,
                      "variants": [_variant_manifest(v) for v in p.variants]} for p in patterns],
    }
    path = os.path.join(web, f"{label}.json")
    with open(path, "w") as f:
        json.dump(data, f)
    n = sum(len(v.problems) for p in patterns for v in p.variants)
    print(f"wrote {os.path.relpath(path, os.path.dirname(os.path.dirname(web)))} ({n} problems) and its py/ ({len(files)} files)")


#checks and the terminal

def _paint(text, color):
    return f"\033[{color}m{text}\033[0m" if sys.stdout.isatty() else text


def run_problem(problem, source, quiet=False):
    """run every test; returns (passed, total)"""
    try:
        solution = runner.load_source(source)
    except runner.LoadError as e:
        if not quiet:
            print(_paint(e.message, "31"))
            print("\n".join(e.details))
        return 0, len(problem.tests)
    reference = runner.reference_module(problem)
    passed = 0
    for t in problem.tests:
        r = runner.run_test(t, solution, reference)
        passed += r["status"] == "pass"
        if not quiet:
            mark = _paint("✓", "32") if r["status"] == "pass" else _paint("✗", "31")
            print(f"  {mark} {t.name}{_paint(' (hidden)', '2') if t.hidden else ''}  {_paint(format(r['elapsed'], '.2f') + 's', '2')}")
            for m in r["metrics"]:
                print(_paint(f"      {m['name']}: {m['value']}" + (f"  ({m['context']})" if m["context"] else ""), "2"))
            if r["status"] != "pass":
                print(f"      {r['message']}")
                for line in r["details"]:
                    print(f"      {line}")
    return passed, len(problem.tests)


def selftest(patterns):
    """every reference passes its tests, every trace builds, and a do-nothing or unfilled solution fails"""
    check_category(patterns)
    failures = []
    for pattern in patterns:
        print(_paint(pattern.name, "1"))
        for v in pattern.variants:
            for p in v.problems:
                problems_here = []
                passed, total = run_problem(p, p.reference, quiet=True)
                if passed != total:
                    problems_here.append(f"the reference passes {passed}/{total}")
                if p.role == "example":
                    try:
                        build_trace(p)
                    except Exception as e:  # noqa: BLE001
                        problems_here.append(f"trace: {e}")
                else:
                    empty = p.starter if p.kind == "class" and p.role != "completion" else f"{p.signature}\n    pass\n"
                    if run_problem(p, empty, quiet=True)[0] == len(p.tests):
                        problems_here.append("a do-nothing solution passes every test")
                    if p.role == "completion" and BLANK in p.starter and run_problem(p, p.starter, quiet=True)[0] == len(p.tests):
                        problems_here.append("the unfilled starter passes every test")
                mark = _paint("✓", "32") if not problems_here else _paint("✗", "31")
                print(f"  {mark} {v.name} · {ROLE_LABELS[p.role]:<18} {p.key}  {'; '.join(problems_here)}")
                failures += problems_here
    print(_paint("all good", "32") if not failures else _paint(f"{len(failures)} problem(s)", "31"))
    return not failures


def terminal(prog, doc, here, patterns, get_problem):
    import argparse
    ap = argparse.ArgumentParser(prog=prog, description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("problem", nargs="?")
    ap.add_argument("file", nargs="?", help="solution file (default solutions/<problem>.py)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(0 if selftest(patterns) else 1)
    if not args.problem:
        for pattern in patterns:
            print(_paint(pattern.name, "1"))
            for v in pattern.variants:
                print(f"  {v.name}")
                for p in v.problems:
                    print(f"    {ROLE_LABELS[p.role]:<18} {p.key:<28} {p.title}")
        print(f"\nrun ./butterbricks.py {prog.split()[-1]} <problem> to start one")
        return
    problem = get_problem(args.problem)
    path = args.file or os.path.join(here, "solutions", f"{problem.key}.py")
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(problem.starter if problem.role != "example" else problem.reference)
        print(f"wrote the starter to {os.path.relpath(path)}")
    with open(path) as f:
        source = f.read()
    print(f"{problem.title} ({ROLE_LABELS[problem.role]})")
    passed, total = run_problem(problem, source)
    print(_paint(f"\n{passed}/{total} passed", "32" if passed == total else "31"))
    sys.exit(0 if passed == total else 1)


#the browser's worker (web/pyworker.js) calls these through each category's browser.py; json in, json out

def browser_functions(get_problem):
    runner.TIME_SCALE = 2.5
    run = {}

    def prepare(key, part, mode, source):
        """load the user's code and list the tests a run will execute: the samples for "run", all for "submit\""""
        problem = get_problem(key)
        tests = [t for t in problem.tests if mode == "submit" or not t.hidden]
        run.clear()
        try:
            solution = runner.load_source(source)
        except runner.LoadError as e:
            return json.dumps({"error": e.message, "details": e.details, "where": e.where})
        run.update(problem=problem, solution=solution, reference=runner.reference_module(problem), tests=tests)
        return json.dumps({"tests": [{"name": t.name, "part": None, "hidden": t.hidden,
                                      "time_limit": t.time_limit * runner.TIME_SCALE} for t in tests]})

    def run_one(i):
        return json.dumps(runner.run_test(run["tests"][i], run["solution"], run["reference"], None))

    def scratch(source, snippet):
        return json.dumps(runner.scratch(source, snippet))

    return prepare, run_one, scratch
