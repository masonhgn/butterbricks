"""every pattern in the Patterns category, in the recommended order (docs/patterns-taxonomy.md section 3). Only the
patterns built so far are here; PLANNED lists the rest, for the wall"""

from . import arrays_hashing

PATTERNS = [arrays_hashing.PATTERN]

PLANNED = ["Two Pointers", "Sliding Window", "Prefix Sums", "Stack", "Binary Search", "Linked Lists",
           "Fast & Slow Pointers", "Trees", "Tries", "Heaps", "Intervals", "Graphs", "Backtracking",
           "Dynamic Programming", "Greedy", "Bit Manipulation"]


def all_problems():
    return [p for pattern in PATTERNS for v in pattern.variants for p in v.problems]


def get_problem(key):
    for p in all_problems():
        if p.key == key:
            return p
    raise KeyError(f"no problem named {key!r}")


def variant_of(key):
    for pattern in PATTERNS:
        for v in pattern.variants:
            if any(p.key == key for p in v.problems):
                return pattern, v
    raise KeyError(f"no problem named {key!r}")
