#!/usr/bin/env python3
"""builds what the Patterns category of the site needs: web/patterns/patterns.json (every pattern, variant, problem,
drill and worked-example trace) and web/patterns/py/ (see framework/curriculum_tools.py)"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))  # the shared framework package

from bricks import PATTERNS, PLANNED  # noqa: E402
from framework.curriculum_tools import build  # noqa: E402

if __name__ == "__main__":
    build(HERE, os.path.join(HERE, "..", "..", "web", "patterns"), PATTERNS, PLANNED, "patterns")
