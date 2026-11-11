"""the functions the browser's web worker (web/pyworker.js) calls through Pyodide for the Patterns category.
Arguments and return values are json strings. `part` is unused: pattern problems are single functions"""

import json

from bricks import get_problem
from framework import runner

runner.TIME_SCALE = 2.5

_run = {}  # the run being executed: the loaded solution and the tests to go through


def prepare(key, part, mode, source):
    """load the user's code and list the tests a run will execute: the samples for "run", every test for "submit"""
    problem = get_problem(key)
    tests = [t for t in problem.tests if mode == "submit" or not t.hidden]
    _run.clear()
    try:
        solution = runner.load_source(source)
    except runner.LoadError as e:
        return json.dumps({"error": e.message, "details": e.details, "where": e.where})
    _run.update(problem=problem, solution=solution, reference=runner.reference_module(problem), tests=tests)
    return json.dumps({"tests": [{"name": t.name, "part": None, "hidden": t.hidden,
                                  "time_limit": t.time_limit * runner.TIME_SCALE} for t in tests]})


def run_one(i):
    return json.dumps(runner.run_test(_run["tests"][i], _run["solution"], _run["reference"], None))


def scratch(source, snippet):
    return json.dumps(runner.scratch(source, snippet))
