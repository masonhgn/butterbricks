#!/usr/bin/env python3
"""builds everything the site in web/ needs: each category's data (categories/<category>/build_web.py), then
web/catalog.json, the list of every problem by category that the sidebar and the home page show"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")
CATEGORIES = ["sql", "implementation", "patterns"]


def sql_catalog():
    with open(os.path.join(WEB, "sql", "data.json")) as f:
        data = json.load(f)
    groups = []
    for li, level in enumerate(data["levels"]):
        groups.append({
            "title": level["title"],
            "problems": [{"key": c["key"], "title": c["title"], "num": i + 1}
                         for i, c in enumerate(data["challenges"]) if c["level"] == li],
        })
    return {"key": "sql", "title": "SQL", "unit": "challenge", "total": len(data["challenges"]),
            "blurb": "Queries against a real SQLite database of a small online store, checked by their result.",
            "groups": groups}


def implementation_catalog():
    with open(os.path.join(WEB, "implementation", "problems.json")) as f:
        data = json.load(f)
    problems = [{"key": p["key"], "title": p["title"], "parts": len(p["parts"]), "difficulty": p["difficulty"],
                 "minutes": p["minutes"], "summary": p["summary"], "tags": p.get("tags", [])} for p in data["problems"]]
    return {"key": "implementation", "title": "Implementation", "unit": "part", "total": sum(p["parts"] for p in problems),
            "blurb": "Build a small system in Python against an extensive test suite, one part at a time.",
            "groups": [{"title": None, "problems": problems}]}


def patterns_catalog():
    """one group per variant; review twins aren't listed (they come back through the review queue)"""
    with open(os.path.join(WEB, "patterns", "patterns.json")) as f:
        data = json.load(f)
    groups = []
    for pattern in data["patterns"]:
        for v in pattern["variants"]:
            groups.append({
                "title": f"{pattern['name']} · {v['name']}", "pattern": pattern["name"], "variant": v["key"],
                "problems": [{"key": p["key"], "title": p["title"], "role": p["role"], "roleLabel": p["roleLabel"]}
                             for p in v["problems"] if p["role"] != "review"],
            })
    return {"key": "patterns", "title": "Patterns", "unit": "problem",
            "total": sum(len(g["problems"]) for g in groups),
            "blurb": "Algorithm patterns, one small idea at a time: learn it, watch it work, then solve problems that "
                     "change one thing at a time.",
            "groups": groups}


def main():
    for category in CATEGORIES:
        # each script runs from its own directory, so its imports (challenges, problems) resolve as they always have
        subprocess.run([sys.executable, os.path.join(HERE, "categories", category, "build_web.py")], check=True)
    with open(os.path.join(WEB, "catalog.json"), "w") as f:
        json.dump({"categories": [patterns_catalog(), sql_catalog(), implementation_catalog()]}, f)
    print("wrote web/catalog.json")


if __name__ == "__main__":
    main()
