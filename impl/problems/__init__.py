"""every problem, in the order the problem list shows them"""

from . import fulfillment, kv_store, rate_limiter

PROBLEMS = [fulfillment.PROBLEM, rate_limiter.PROBLEM, kv_store.PROBLEM]


def get(key):
    for p in PROBLEMS:
        if p.key == key:
            return p
    raise KeyError(f"no problem named {key!r}; there are: {', '.join(p.key for p in PROBLEMS)}")
