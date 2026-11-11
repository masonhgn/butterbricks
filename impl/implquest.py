#!/usr/bin/env python3
"""implquest: interview-style implementation problems with test suites, run from the terminal

  ./implquest.py                                  list the problems
  ./implquest.py fulfillment                      copy the starter to solutions/fulfillment.py (first time) and run part 1's sample tests
  ./implquest.py fulfillment --part 2 --submit    run every test for parts 1 and 2
  ./implquest.py fulfillment my_file.py           use another file
  ./implquest.py --selftest                       check every reference solution passes its own tests
"""

import argparse
import os
import signal
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from framework import runner  # noqa: E402
from problems import PROBLEMS, get  # noqa: E402

COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
MARK = {"pass": ("✓", "32"), "fail": ("✗", "31"), "error": ("!", "31"), "slow": ("⏱", "33"), "killed": ("⏱", "31")}


def paint(text, code):
    return f"\033[{code}m{text}\033[0m" if COLOR else text


class Killed(BaseException):
    """raised by the alarm when a test runs far past its limit (a BaseException so the runner doesn't catch it)"""


def on_alarm(signum, frame):
    raise Killed()


def run(problem, source, part, mode, quiet=False):
    """run tests, print a line each, return (passed, total)"""
    try:
        solution = runner.load_source(source)
    except runner.LoadError as e:
        print(paint(e.message, "31"))
        print("\n".join(e.details))
        return 0, len(runner.plan(problem, part, mode))
    reference = runner.reference_module(problem)
    passed = 0
    tests = runner.plan(problem, part, mode)
    for p, test in tests:
        hard = test.time_limit * 5 + 3
        signal.signal(signal.SIGALRM, on_alarm)
        signal.setitimer(signal.ITIMER_REAL, hard)
        try:
            r = runner.run_test(test, solution, reference, p)
        except Killed:
            r = {"status": "killed", "message": f"stopped after {hard:g}s (limit {test.time_limit:g}s)", "details": [],
                 "elapsed": hard, "metrics": [], "notes": [], "stdout": ""}
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        passed += r["status"] == "pass"
        if quiet and r["status"] == "pass":
            continue
        mark, color = MARK[r["status"]]
        tag = " (hidden)" if test.hidden else ""
        took = f"{r['elapsed']:.2f}s"
        print(f"  {paint(mark, color)} part {p} · {test.name}{paint(tag, '2')}  {paint(took, '2')}")
        for m in r["metrics"]:
            print(paint(f"      {m['name']}: {m['value']}" + (f"  ({m['context']})" if m["context"] else ""), "2"))
        if r["status"] != "pass":
            print(f"      {r['message']}")
            for line in r["details"]:
                print(f"      {line}")
            if r.get("where") and r["where"]["frames"] and r["where"]["frames"][-1]["vars"]:
                frame = r["where"]["frames"][-1]
                print(paint(f"      variables in {frame['name']} (line {frame['line']}):", "2"))
                for name, value in frame["vars"]:
                    print(paint(f"        {name} = {value}", "2"))
        if r["stdout"] and not quiet:
            print(paint("      stdout:", "2"))
            for line in r["stdout"].rstrip("\n").split("\n")[:20]:
                print(paint(f"        {line}", "2"))
    return passed, len(tests)


def selftest():
    ok = True
    for problem in PROBLEMS:
        passed, total = run(problem, problem.reference, len(problem.parts), "submit", quiet=True)
        good = passed == total
        ok &= good
        print(f"{paint('✓' if good else '✗', '32' if good else '31')} {problem.key}: {passed}/{total} tests pass with the reference")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("problem", nargs="?")
    ap.add_argument("file", nargs="?", help="solution file (default solutions/<problem>.py)")
    ap.add_argument("--part", type=int, default=1)
    ap.add_argument("--submit", action="store_true", help="run hidden tests too")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(0 if selftest() else 1)
    if not args.problem:
        for p in PROBLEMS:
            print(f"{p.key:<14} {p.difficulty:<7} {len(p.parts)} parts  {p.title}: {p.summary}")
        print("\nrun ./implquest.py <problem> to start one")
        return

    problem = get(args.problem)
    part = max(1, min(args.part, len(problem.parts)))
    path = args.file or os.path.join(HERE, "solutions", f"{problem.key}.py")
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(problem.starter)
        print(f"wrote the starter code to {os.path.relpath(path)}")
    with open(path) as f:
        source = f.read()

    mode = "submit" if args.submit else "run"
    print(f"{problem.title}, part {part}: {problem.parts[part - 1].title} ({'all tests' if args.submit else 'sample tests'})")
    passed, total = run(problem, source, part, mode)
    done = passed == total
    print(paint(f"\n{passed}/{total} passed", "32" if done else "31"))
    if done and not args.submit:
        print("samples pass; add --submit to run the hidden tests")
    elif done and part < len(problem.parts):
        print(f"part {part} done; next: --part {part + 1}")
    sys.exit(0 if done else 1)


if __name__ == "__main__":
    main()
