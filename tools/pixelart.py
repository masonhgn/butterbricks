#!/usr/bin/env python3
"""draws the site's pixel art: web/logo.svg (three sticks of butter, stacked) and the tiling textures, which it
prints as CSS custom properties to paste into web/common.css.

Everything is drawn pixel by pixel on a small grid, then written as one <rect> per run of same-colored pixels with
shape-rendering="crispEdges", so it stays sharp at any size."""

import os
import random
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "..", "web")


def to_svg(grid, title=None):
    h, w = len(grid), len(grid[0])
    rects = []
    for y, row in enumerate(grid):
        x = 0
        while x < w:
            c = row[x]
            if c is None:
                x += 1
                continue
            run = 1
            while x + run < w and row[x + run] == c:
                run += 1
            rects.append(f'<rect x="{x}" y="{y}" width="{run}" height="1" fill="{c}"/>')
            x += run
    t = f"<title>{title}</title>" if title else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w * 4}" height="{h * 4}" '
            f'shape-rendering="crispEdges">{t}{"".join(rects)}</svg>')


#the logo: three sticks of butter, each a long box seen from the front, a little above and to the right

OUTLINE = "#7a4e12"
TOP = "#fff2b0"       # the face on top, catching the light
FRONT = "#fbd55a"     # the long side facing you
FRONT_HI = "#ffe58a"  # its top edge
END = "#e8ad2e"       # the end on the right, in shade
TICK = "#d29a24"      # the tablespoon marks printed along a stick
SHINE = "#ffffff"


def stick(grid, x0, y0, length, height, depth, ticks=True, shine=False):
    """paints one stick: its front face's top-left corner is (x0, y0); the top and end faces recede up and right by
    depth pixels. Then a 1px outline around the whole stick, so a stick in front reads cleanly over one behind"""
    cells = {}
    for y in range(y0, y0 + height):
        for x in range(x0, x0 + length):
            cells[(x, y)] = FRONT_HI if y == y0 else FRONT
    for k in range(1, depth + 1):
        for x in range(x0 + k, x0 + length + k):
            cells[(x, y0 - k)] = TOP
        for y in range(y0 - k + 1, y0 + height - k + 1):
            cells[(x0 + length - 1 + k, y)] = END
    if ticks:
        for x in range(x0 + 4, x0 + length - 3, 4):
            for y in (y0 + 1, y0 + 2):
                cells[(x, y)] = TICK
    if shine:
        for x in range(x0 + 4, x0 + 11):
            cells[(x + 1, y0 - depth + 1)] = SHINE
    # the outline is the stick's own border, so the joins between faces stay inside it
    border = {p for p in cells if any((p[0] + dx, p[1] + dy) not in cells for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
    for (x, y), c in cells.items():
        grid[y][x] = OUTLINE if (x, y) in border else c


def logo():
    w, h = 40, 34
    grid = [[None] * w for _ in range(h)]
    # bottom to top, each resting on the one below and a little off, like a stack someone set down by hand
    stick(grid, 1, 25, 27, 8, 6)
    stick(grid, 6, 17, 27, 8, 6)
    stick(grid, 3, 9, 27, 8, 6, shine=True)
    return grid


#textures: drawn at 32px or so and shown at 2x, so their pixels match the 2px pixels of the text

def parchment(rng, w=32, h=32):
    base, flecks = "#fffaee", ["#f6ead0", "#fbf2dc", "#f3e4c2"]
    grid = [[base] * w for _ in range(h)]
    for _ in range(14):
        x, y = rng.randrange(w), rng.randrange(h)
        grid[y][x] = rng.choice(flecks)
    return grid


def planks(rng, colors, w=128, h=16):
    """two planks per tile, each 8 rows: a highlight row, wood with grain streaks, a seam"""
    hi, wood, grain, seam = colors
    grid = []
    for plank in range(h // 8):
        rows = [[hi] * w] + [[wood] * w for _ in range(6)] + [[seam] * w]
        for _ in range(12):
            r = rng.randrange(1, 7)
            x, n = rng.randrange(w), rng.randrange(3, 10)
            for i in range(n):
                rows[r][(x + i) % w] = grain
        grid += rows
    return grid


def css_url(grid):
    return 'url("data:image/svg+xml,' + urllib.parse.quote(to_svg(grid)) + '")'


def main():
    with open(os.path.join(WEB, "logo.svg"), "w") as f:
        f.write(to_svg(logo(), "Butterbricks") + "\n")
    rng = random.Random(7)
    print("  --tex-parchment:", css_url(parchment(rng)) + ";")
    print("  --tex-cream:", css_url(planks(rng, ("#fffaf0", "#fdf2d6", "#f8e7bd", "#ecd7a2"))) + ";")


if __name__ == "__main__":
    main()
