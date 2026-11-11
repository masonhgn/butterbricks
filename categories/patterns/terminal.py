#!/usr/bin/env python3
"""the Butterbricks Patterns problems in the terminal. Run it as ./butterbricks.py patterns

  ./butterbricks.py patterns                          list the patterns, variants and problems
  ./butterbricks.py patterns badge-scanned-twice      write categories/patterns/solutions/<problem>.py from the
                                                      starter (first time), then run every test
  ./butterbricks.py patterns <problem> my_file.py     use another file
  ./butterbricks.py patterns --selftest               check every problem: references pass, traces build, and a
                                                      starter that does nothing fails
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))  # the shared framework package

from bricks import PATTERNS, get_problem  # noqa: E402
from bricks.model import BLANK, ROLE_LABELS  # noqa: E402
from framework import runner  # noqa: E402
from trace import build_trace  # noqa: E402


def paint(text, color):
    return f"\033[{color}m{text}\033[0m" if sys.stdout.isatty() else text


def run(problem, source, quiet=False):
    """run every test; returns (passed, total)"""
    try:
        solution = runner.load_source(source)
    except runner.LoadError as e:
        if not quiet:
            print(paint(e.message, "31"))
            print("\n".join(e.details))
        return 0, len(problem.tests)
    reference = runner.reference_module(problem)
    passed = 0
    for t in problem.tests:
        r = runner.run_test(t, solution, reference)
        passed += r["status"] == "pass"
        if not quiet:
            mark = paint("✓", "32") if r["status"] == "pass" else paint("✗", "31")
            print(f"  {mark} {t.name}{paint(' (hidden)', '2') if t.hidden else ''}  {paint(format(r['elapsed'], '.2f') + 's', '2')}")
            if r["status"] != "pass":
                print(f"      {r['message']}")
                for line in r["details"]:
                    print(f"      {line}")
    return passed, len(problem.tests)


def selftest():
    failures = []
    for pattern in PATTERNS:
        print(paint(pattern.name, "1"))
        for v in pattern.variants:
            for p in v.problems:
                problems_here = []
                passed, total = run(p, p.reference, quiet=True)
                if passed != total:
                    problems_here.append(f"the reference passes {passed}/{total}")
                if p.role == "example":
                    try:
                        build_trace(p)
                    except Exception as e:  # noqa: BLE001
                        problems_here.append(f"trace: {e}")
                else:
                    # a solution that does nothing must fail, or the tests don't test anything
                    if run(p, f"{p.signature}\n    pass\n", quiet=True)[0] == len(p.tests):
                        problems_here.append("a do-nothing solution passes every test")
                    if p.role == "completion" and BLANK in p.starter and run(p, p.starter, quiet=True)[0] == len(p.tests):
                        problems_here.append("the unfilled starter passes every test")
                mark = paint("✓", "32") if not problems_here else paint("✗", "31")
                print(f"  {mark} {v.name} · {ROLE_LABELS[p.role]:<18} {p.key}  {'; '.join(problems_here)}")
                failures += problems_here
    print(paint("all good", "32") if not failures else paint(f"{len(failures)} problem(s)", "31"))
    return not failures


def main():
    ap = argparse.ArgumentParser(prog="butterbricks.py patterns", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("problem", nargs="?")
    ap.add_argument("file", nargs="?", help="solution file (default solutions/<problem>.py)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(0 if selftest() else 1)
    if not args.problem:
        for pattern in PATTERNS:
            print(paint(pattern.name, "1"))
            for v in pattern.variants:
                print(f"  {v.name}")
                for p in v.problems:
                    print(f"    {ROLE_LABELS[p.role]:<18} {p.key:<28} {p.title}")
        print("\nrun ./butterbricks.py patterns <problem> to start one")
        return
    problem = get_problem(args.problem)
    path = args.file or os.path.join(HERE, "solutions", f"{problem.key}.py")
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(problem.starter if problem.role != "example" else problem.reference)
        print(f"wrote the starter to {os.path.relpath(path)}")
    with open(path) as f:
        source = f.read()
    print(f"{problem.title} ({ROLE_LABELS[problem.role]})")
    passed, total = run(problem, source)
    print(paint(f"\n{passed}/{total} passed", "32" if passed == total else "31"))
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
