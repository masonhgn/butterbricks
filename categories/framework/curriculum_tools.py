"""what every brick-based category (Patterns, Structures) does the same way: build its page's data, check its content,
run its problems in the terminal, and answer the browser's worker. Each category's build_web.py, terminal.py and
browser.py are thin wrappers that pass in their own content package (`bricks`)."""

import json
import os
import shutil
import sys

from . import runner
from .curriculum import BLANK, ROLE_LABELS, PlannedVariant, check_category, strip_tags
from .tests import REFERENCE, fresh, show, show_call
from .trace import build_trace, trace_function


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
        out["walkthrough"] = [{"text": s.text, "ask": s.ask, "why": s.why}
                              for s in problem.walkthrough]
    if problem.viz:
        out["viz"] = problem.viz
    if problem.role == "example":
        out["trace"] = build_trace(problem)
        out["notes"] = problem.notes
    return out


def _example_manifest(ex):
    return {
        "title": ex.title, "statement": ex.statement, "function": ex.function, "code": ex.code,
        "cases": [[show_call(ex.function, args), show(expected)] for args, expected in ex.cases],
        "differs": ex.differs, "classic": ex.classic, "notes": ex.notes, "viz": ex.viz, "problem": ex.problem,
        "args": ", ".join(repr(a) for a in ex.trace_args),
        "trace": trace_function(ex.code, ex.function, ex.trace_args, ex.notes, key=ex.title),
    }


def _lesson_manifest(L):
    return {
        "goals": L.goals, "problem": L.problem, "bruteForce": L.brute_force, "bruteCost": L.brute_cost,
        "moves": [{"key": m.key, "label": m.label, "text": m.text} for m in L.moves],
        "holds": L.holds, "why": L.why, "costWhy": L.cost_why,
        "examples": [_example_manifest(ex) for ex in L.examples],
        "toolkit": [list(t) for t in L.toolkit],
        "mistakeCode": {m: list(pair) for m, pair in L.mistake_code.items()},
    }


def _planned_manifest(item):
    if isinstance(item, str):
        return {"name": item}
    return {"name": item.name, "question": item.question, "keep": item.keep, "line": item.line,
            "status": item.status, "aliases": item.aliases, "classic": item.classic}


def _variant_manifest(v):
    return {
        "key": v.key, "name": v.name, "status": v.status, "aliases": v.aliases, "sources": v.sources,
        "idea": v.idea, "invariant": v.invariant, "template": v.template, "complexity": v.complexity,
        "signals": v.signals, "mistakes": v.mistakes, "prerequisites": v.prerequisites,
        "referenceTable": [list(r) for r in v.reference_table],
        "lesson": _lesson_manifest(v.lesson) if v.lesson else None,
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
                      "sources": p.sources, "planned": [_planned_manifest(x) for x in p.planned],
                      "overview": p.overview, "map": [list(r) for r in p.map_rows],
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


def _normalized(code):
    lines = [l.split("#")[0].rstrip() for l in strip_tags(code).splitlines()]
    return "\n".join(l for l in lines if l.strip())


def check_lesson(v):
    """a lesson's code all runs and says what it claims: every example gives its cases, the brute force agrees with the
    first example, every trace builds, and no example is a practice problem's answer in disguise"""
    L = v.lesson
    out = []
    answers = {_normalized(p.reference): p.key for p in v.problems if p.role != "example"}
    for ex in L.examples:
        try:
            module = runner.load_source(ex.code, name="lesson_example", filename="lesson.py")
            fn = getattr(module, ex.function)
            for args, expected in ex.cases:
                got = fn(*fresh(tuple(args)))
                if got != expected:
                    out.append(f"{ex.title}: {show_call(ex.function, args)} gives {show(got)}, not {show(expected)}")
            trace = trace_function(ex.code, ex.function, ex.trace_args, ex.notes, key=ex.title)
            json.dumps(trace)
            if len(trace["steps"]) > 80:
                out.append(f"{ex.title}: the trace has {len(trace['steps'])} steps; keep it under 80 to follow")
        except runner.LoadError as e:
            out.append(f"{ex.title}: {e.message}")
        except Exception as e:  # noqa: BLE001
            out.append(f"{ex.title}: {type(e).__name__}: {e}")
        if _normalized(ex.code) in answers:
            out.append(f"{ex.title}: it's the answer to {answers[_normalized(ex.code)]}")
    first = L.examples[0]
    try:
        brute = getattr(runner.load_source(L.brute_force, name="brute", filename="brute.py"), first.function)
        for args, expected in first.cases:
            if brute(*fresh(tuple(args))) != expected:
                out.append(f"the brute force disagrees with {first.title} on {show_call(first.function, args)}")
    except Exception as e:  # noqa: BLE001
        out.append(f"the brute force: {getattr(e, 'message', e)}")
    return out


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
            if v.lesson:
                problems_here = check_lesson(v)
                mark = _paint("✓", "32") if not problems_here else _paint("✗", "31")
                print(f"  {mark} {v.name} · {'Lesson':<18} {len(v.lesson.examples)} examples  {'; '.join(problems_here)}")
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

    def trace(source, function, args, notes):
        """trace an example on input typed on the page (a Python argument list, like `[1, 2], 3`)"""
        import ast
        try:
            parsed = ast.literal_eval(f"({args},)") if args.strip() else ()
        except Exception as e:  # noqa: BLE001
            return json.dumps({"error": f"Couldn't read that input: {type(e).__name__}. Write Python values separated by commas, like [1, 2], 3"})
        try:
            return json.dumps(trace_function(source, function, parsed, json.loads(notes), custom=True))
        except runner.LoadError as e:
            return json.dumps({"error": e.message})
        except Exception as e:  # noqa: BLE001
            return json.dumps({"error": f"{type(e).__name__}: {e}"})

    return prepare, run_one, scratch, trace
