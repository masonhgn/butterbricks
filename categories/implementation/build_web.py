#!/usr/bin/env python3
"""builds what the Implementation category of the site needs: web/implementation/problems.json (every problem's
text and test list) and web/implementation/py/ (the framework and problems packages, which the browser loads into
Pyodide to run tests)"""

import json
import os
import shutil

from problems import PROBLEMS

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "..", "..", "web", "implementation")
PACKAGES = ["framework", "problems"]


def main():
    out = os.path.join(WEB, "py")
    shutil.rmtree(out, ignore_errors=True)
    files = []
    for pkg in PACKAGES:
        os.makedirs(os.path.join(out, pkg))
        for name in sorted(os.listdir(os.path.join(HERE, pkg))):
            if name.endswith(".py"):
                shutil.copyfile(os.path.join(HERE, pkg, name), os.path.join(out, pkg, name))
                files.append(f"{pkg}/{name}")
    with open(os.path.join(WEB, "problems.json"), "w") as f:
        json.dump({"files": files, "problems": [p.manifest() for p in PROBLEMS]}, f)
    print(f"wrote web/implementation/problems.json ({len(PROBLEMS)} problems) and web/implementation/py/ ({len(files)} files)")


if __name__ == "__main__":
    main()
