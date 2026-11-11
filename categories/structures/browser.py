"""the functions the browser's web worker (web/pyworker.js) calls for the Structures category"""

from bricks import get_problem
from framework.curriculum_tools import browser_functions

prepare, run_one, scratch = browser_functions(get_problem)
