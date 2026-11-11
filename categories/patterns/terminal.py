#!/usr/bin/env python3
"""the Butterbricks Patterns problems in the terminal. Run it as ./butterbricks.py patterns

  ./butterbricks.py patterns                          list the patterns, variants and problems
  ./butterbricks.py patterns badge-scanned-twice      write categories/patterns/solutions/<problem>.py from the
                                                      starter (first time), then run every test
  ./butterbricks.py patterns <problem> my_file.py     use another file
  ./butterbricks.py patterns --selftest               check every problem: references pass, traces build, and a
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
    terminal("butterbricks.py patterns", __doc__, HERE, PATTERNS, get_problem)
