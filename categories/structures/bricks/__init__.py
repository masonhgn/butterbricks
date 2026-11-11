"""every family in the Structures category, in the recommended order (docs/structures-taxonomy.md section 4). Only the
families built so far are here; PLANNED lists the rest, for the wall"""

from framework.curriculum import check_category

from . import building_blocks, cross_indexed

PATTERNS = check_category([building_blocks.FAMILY, cross_indexed.FAMILY])

PLANNED = ["Augmented structures", "Ordered structures", "Time and versions"]


def all_problems():
    return [p for family in PATTERNS for v in family.variants for p in v.problems]


def get_problem(key):
    for p in all_problems():
        if p.key == key:
            return p
    raise KeyError(f"no problem named {key!r}")
