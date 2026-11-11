#!/usr/bin/env python3
"""builds what the Implementation category of the site needs: web/implementation/problems.json (every problem's
text and test list) and web/implementation/py/ (the shared framework package, the problems package and browser.py,
which the browser loads into Pyodide to run tests)"""

import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CATEGORIES = os.path.dirname(HERE)
sys.path.insert(0, CATEGORIES)  # the shared framework package

from problems import PROBLEMS  # noqa: E402

WEB = os.path.join(HERE, "..", "..", "web", "implementation")
# what the browser loads: (source directory, package or file)
PACKAGES = [(CATEGORIES, "framework"), (HERE, "problems")]
MODULES = [(HERE, "browser.py")]


def main():
    out = os.path.join(WEB, "py")
    shutil.rmtree(out, ignore_errors=True)
    files = []
    for root, pkg in PACKAGES:
        os.makedirs(os.path.join(out, pkg))
        for name in sorted(os.listdir(os.path.join(root, pkg))):
            if name.endswith(".py"):
                shutil.copyfile(os.path.join(root, pkg, name), os.path.join(out, pkg, name))
                files.append(f"{pkg}/{name}")
    for root, name in MODULES:
        shutil.copyfile(os.path.join(root, name), os.path.join(out, name))
        files.append(name)
    with open(os.path.join(WEB, "problems.json"), "w") as f:
        json.dump({"files": files, "problems": [p.manifest() for p in PROBLEMS]}, f)
    print(f"wrote web/implementation/problems.json ({len(PROBLEMS)} problems) and web/implementation/py/ ({len(files)} files)")


if __name__ == "__main__":
    main()
