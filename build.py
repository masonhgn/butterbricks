#!/usr/bin/env python3
"""builds everything the static site in web/ needs: each track's data (sql/build_web.py, impl/build_web.py), then
web/tracks.json, the counts the home page shows progress against"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")
TRACKS = ["sql", "impl"]


def main():
    for track in TRACKS:
        # each script runs from its own directory so its imports (challenges, problems) resolve as they always have
        subprocess.run([sys.executable, os.path.join(HERE, track, "build_web.py")], check=True)
    with open(os.path.join(WEB, "sql", "data.json")) as f:
        sql = json.load(f)
    with open(os.path.join(WEB, "impl", "problems.json")) as f:
        impl = json.load(f)
    tracks = {
        "sql": {"challenges": len(sql["challenges"]), "levels": len(sql["levels"])},
        "impl": {"problems": len(impl["problems"]), "parts": sum(len(p["parts"]) for p in impl["problems"])},
    }
    with open(os.path.join(WEB, "tracks.json"), "w") as f:
        json.dump(tracks, f)
    print("wrote web/tracks.json")


if __name__ == "__main__":
    main()
