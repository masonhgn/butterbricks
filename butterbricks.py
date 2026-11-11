#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["rich>=13", "prompt_toolkit>=3"]
# ///
"""Butterbricks in the terminal.

  ./butterbricks.py                                          list the categories
  ./butterbricks.py sql                                      the SQL challenges, one after another (--rebuild remakes the database)
  ./butterbricks.py implementation                           list the Implementation problems
  ./butterbricks.py implementation fulfillment               write categories/implementation/solutions/fulfillment.py from the
                                                             starter (first time) and run part 1's sample tests
  ./butterbricks.py implementation fulfillment --part 2 --submit    every test for parts 1-2, hidden ones included
  ./butterbricks.py selftest                                 every category's reference solutions pass their own checks

It runs through uv (https://docs.astral.sh/uv/), which installs the SQL terminal's two UI libraries on first run.
Each category's terminal lives in categories/<category>/terminal.py and runs as its own process."""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CATEGORIES = {
    "sql": "78 SQL challenges in 10 levels, against a real SQLite database",
    "implementation": "multi-part problems: build a small system in Python against a test suite",
}


def run(category, args):
    script = os.path.join(HERE, "categories", category, "terminal.py")
    return subprocess.run([sys.executable, script, *args]).returncode


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        for key, about in CATEGORIES.items():
            print(f"  {key:<16} {about}")
        return 0
    command, rest = argv[0], argv[1:]
    if command == "selftest":
        failed = [c for c in CATEGORIES if run(c, ["--selftest"]) != 0]
        print(f"\nselftest: {'all categories pass' if not failed else 'failing: ' + ', '.join(failed)}")
        return 1 if failed else 0
    if command not in CATEGORIES:
        print(f"no category {command!r}; the categories are {', '.join(CATEGORIES)}", file=sys.stderr)
        return 2
    return run(command, rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
