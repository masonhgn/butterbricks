"""the functions the browser's web worker calls through Pyodide. Arguments and return values are json strings"""

import json

from problems import get

from . import runner

runner.TIME_SCALE = 2.5

_run = {}  # the run being executed: the loaded solution and the tests to go through


def prepare(key, part, mode, source):
    """load the user's code and list the tests a run will execute. Call run_one(i) for each afterwards"""
    problem = get(key)
    tests = runner.plan(problem, part, mode)
    _run.clear()
    try:
        solution = runner.load_source(source)
    except runner.LoadError as e:
        return json.dumps({"error": e.message, "details": e.details, "where": e.where})
    _run.update(problem=problem, solution=solution, reference=runner.reference_module(problem), tests=tests)
    return json.dumps({"tests": [{"name": t.name, "part": p, "hidden": t.hidden, "time_limit": t.time_limit * runner.TIME_SCALE} for p, t in tests]})


def run_one(i):
    part, test = _run["tests"][i]
    return json.dumps(runner.run_test(test, _run["solution"], _run["reference"], part))


def scratch(source, snippet):
    return json.dumps(runner.scratch(source, snippet))
