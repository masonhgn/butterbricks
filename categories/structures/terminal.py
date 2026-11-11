#!/usr/bin/env python3
"""the Butterbricks Structures problems in the terminal. Run it as ./butterbricks.py structures

  ./butterbricks.py structures                          list the families, techniques and problems
  ./butterbricks.py structures raffle                   write categories/structures/solutions/<problem>.py from the
                                                      starter (first time), then run every test
  ./butterbricks.py structures <problem> my_file.py     use another file
  ./butterbricks.py structures --selftest               check every problem: references pass, traces build, and a
                                                      starter that does nothing fails
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))  # the shared framework package

from bricks import PATTERNS, get_problem  # noqa: E402
from framework.curriculum_tools import terminal  # noqa: E402

if __name__ == "__main__":
    terminal("butterbricks.py structures", __doc__, HERE, PATTERNS, get_problem)
