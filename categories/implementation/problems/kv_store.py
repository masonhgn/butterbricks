"""Transactional Key-Value Store: get/set with value counts, nested transactions, and ordered range scans"""

import random

from framework import OpsTest, Part, Problem

INTRO = """
A deployment platform keeps its configuration (service settings, feature flags, routing rules) in a small in-memory
key-value store. Operators make changes in batches that must apply all at once or not at all, and tools on top of the
store need to answer questions like "how many services are set to `canary`?" and "list every key under `svc/payments/`".

Implement a class `Database`. Keys and values are strings. Each part adds requirements to the same class, and tests
for a part also re-run every earlier part's tests.
"""

PART1 = """
```python
class Database:
    def __init__(self): ...
    def set(self, key: str, value: str) -> None: ...
    def get(self, key: str) -> str | None: ...
    def delete(self, key: str) -> bool: ...
    def count(self, value: str) -> int: ...
```

- `set` creates or overwrites a key.
- `get` returns the value, or `None` if the key isn't set.
- `delete` removes a key and returns `True`, or returns `False` if it wasn't set.
- `count(value)` is how many keys currently hold exactly `value`.

**Example**

```python
db = Database()
db.set("svc/api/mode", "canary")
db.set("svc/web/mode", "canary")
db.count("canary")             # 2
db.set("svc/web/mode", "stable")
db.count("canary")             # 1
db.get("svc/web/mode")         # "stable"
db.delete("svc/api/mode")      # True
db.delete("svc/api/mode")      # False
db.count("canary")             # 0
```

Hidden tests make 100,000+ calls with `count` mixed in throughout.
"""

PART2 = """
```python
    def begin(self) -> None: ...
    def rollback(self) -> bool: ...
    def commit(self) -> bool: ...
```

- `begin` opens a transaction. Transactions **nest**: calling `begin` inside one opens an inner one.
- Every read (`get`, `count`, and later `scan`) sees all changes made so far, including uncommitted ones.
- `rollback` undoes every change made since the innermost open transaction began, and closes it. It returns
  `False` (and does nothing) if no transaction is open.
- `commit` makes the changes of **all** open transactions permanent and closes them all. It returns `False` if no
  transaction is open.

**Example**

```python
db = Database()
db.set("a", "10")
db.begin()
db.set("a", "20")
db.begin()
db.delete("a")
db.get("a")          # None
db.rollback()        # True: undoes the delete
db.get("a")          # "20"
db.rollback()        # True: undoes set a=20
db.get("a")          # "10"
db.rollback()        # False: nothing open
db.begin()
db.set("b", "1")
db.begin()
db.set("c", "1")
db.commit()          # True: both levels
db.rollback()        # False
db.count("1")        # 2
```

The store holds tens of thousands of keys while operators open and roll back small transactions all day.
`begin` and `rollback` must not cost time proportional to the size of the store.
"""

PART3 = """
```python
    def scan(self, start: str, end: str) -> list[tuple[str, str]]: ...
```

`scan` returns `(key, value)` pairs for every key with `start <= key < end` (plain string comparison), sorted by key.
It sees uncommitted changes like every other read, and rolled-back changes must disappear from it.

A prefix query is a range: every key starting with `svc/payments/` is `scan("svc/payments/", "svc/payments0")`,
since `0` is the character right after `/`.

**Example**

```python
db.set("svc/web/mode", "stable")
db.set("svc/api/mode", "canary")
db.set("svc/api/replicas", "3")
db.set("svc/b", "x")
db.scan("svc/api/", "svc/api0")
# [("svc/api/mode", "canary"), ("svc/api/replicas", "3")]
db.scan("svc/a", "svc/c")
# [("svc/api/mode", "canary"), ("svc/api/replicas", "3"), ("svc/b", "x")]
```

Hidden tests run thousands of scans over a store of 50,000 keys that keeps changing.
"""

STARTER = '''class Database:
    def __init__(self):
        pass

    def set(self, key: str, value: str) -> None:
        pass

    def get(self, key: str) -> str | None:
        pass

    def delete(self, key: str) -> bool:
        pass

    def count(self, value: str) -> int:
        pass
'''

REFERENCE = '''from bisect import bisect_left, insort
from collections import Counter

MISSING = object()


class Database:
    def __init__(self):
        self.data = {}
        self.counts = Counter()   # value -> number of keys holding it
        self.keys = []            # every key, sorted, for scans
        self.undo = []            # one list per open transaction of (key, previous value or MISSING)

    def write(self, key, value):
        """the single place data changes, so counts, the sorted index and the undo log can't drift apart"""
        old = self.data.get(key, MISSING)
        if old is value or old == value:
            return
        if self.undo:
            self.undo[-1].append((key, old))
        if old is MISSING:
            insort(self.keys, key)
        else:
            self.counts[old] -= 1
        if value is MISSING:
            del self.data[key]
            del self.keys[bisect_left(self.keys, key)]
        else:
            self.data[key] = value
            self.counts[value] += 1

    def set(self, key, value):
        self.write(key, value)

    def get(self, key):
        return self.data.get(key)

    def delete(self, key):
        if key not in self.data:
            return False
        self.write(key, MISSING)
        return True

    def count(self, value):
        return self.counts[value]

    def begin(self):
        self.undo.append([])

    def rollback(self):
        if not self.undo:
            return False
        changes = self.undo.pop()
        undo, self.undo = self.undo, []  # don't log the undo itself
        for key, old in reversed(changes):
            self.write(key, old)
        self.undo = undo
        return True

    def commit(self):
        if not self.undo:
            return False
        self.undo = []
        return True

    def scan(self, start, end):
        i, j = bisect_left(self.keys, start), bisect_left(self.keys, end)
        return [(k, self.data[k]) for k in self.keys[i:j]]
'''

WRITEUP = """
### How the reference works

**One write path.** Every change goes through `write(key, value)`, which updates the dict, the per-value counter,
the sorted key index, and the undo log together. `set`, `delete` and even `rollback` call it. With four structures
that must agree, having exactly one function that touches them is the main thing keeping the code correct as parts
are added.

**Counts are maintained, not computed.** A `Counter` from value to number of keys makes `count` O(1). Scanning the
dict per call is O(n), which the 100,000-call hidden test catches.

**Transactions are an undo log.** `begin` pushes an empty list. Each write inside a transaction records
`(key, previous value)`, with a sentinel for "didn't exist". `rollback` pops the innermost list and replays it
backwards (with logging switched off, so the undo isn't itself logged). `commit` drops every list: the changes are
already applied. `begin` and `commit` are O(1), and `rollback` is O(changes being undone).

The alternative, copying the whole store on `begin`, makes `begin` O(n), which the big part 2 test catches. A third
design, *layered overlays*, gives each transaction its own dict of changes and resolves reads through the stack. It
makes `begin`/`rollback` O(1), but reads cost O(depth), `count` gets complicated, and `commit` must merge every layer
down.

**Scans use a sorted list of keys.** `bisect` finds the range in O(log n). Inserting a new key with `insort` is
O(n) because of the list shift, but that's a fast `memmove` in C and fine for tens of thousands of keys. Sorting all
keys on every scan is O(n log n) per scan, which the part 3 hidden tests catch.

### Tradeoffs worth saying out loud

- **Undo log vs copy-on-begin vs overlays**: say which operation each one makes cheap. Undo logs suit short
  transactions that usually commit. Overlays suit long-lived read-heavy snapshots.
- **Sorted list vs balanced tree vs skip list for the index.** A sorted list is simplest and fast in Python up to
  roughly a million keys. A B-tree or skip list gives O(log n) inserts and is what real stores use (LevelDB/RocksDB
  memtables are skip lists). `sortedcontainers.SortedList` is the practical Python answer.
- **Memory.** The undo log stores the previous value once per change, so a transaction that rewrites the same key
  10,000 times logs 10,000 entries. Logging only the first change per key per transaction fixes that at the cost of
  a set per transaction.
- **What a real store adds**: durability (write-ahead log), isolation between concurrent transactions (locks or
  MVCC), and snapshots for scans that run while writes continue.
"""

DISCUSSION = [
    "Walk through what rollback does in your design. What does each of begin, commit and rollback cost?",
    "How do you keep count() correct across overwrites, deletes and rollbacks?",
    "Why might copying the store on begin() be acceptable in some systems? Where does it break down?",
    "What structure did you use for scan, and what does each operation cost with it?",
    "How would you add a second, concurrent client that shouldn't see the first client's uncommitted changes?",
    "What would you change so the store survives a process restart?",
]


def gen(seed, *, n, keys, values, tx=0.0, scans=0.0, prefill=0, deep=False):
    """random traffic over `keys` keys and `values` distinct values"""
    def build():
        r = random.Random(seed)
        names = [f"svc/{r.choice('abcdefghij')}{i:05}/{r.choice(['mode', 'replicas', 'zone'])}" for i in range(keys)]
        vals = [f"v{i}" for i in range(values)]
        steps = [("set", (k, r.choice(vals))) for k in r.sample(names, prefill)]
        depth = 0
        for _ in range(n):
            x = r.random()
            if x < tx:
                y = r.random()
                if y < (0.5 if deep else 0.4) or depth == 0:
                    steps.append(("begin", ()))
                    depth += 1
                elif y < 0.85:
                    steps.append(("rollback", ()))
                    depth = max(0, depth - 1)
                else:
                    steps.append(("commit", ()))
                    depth = 0
            elif x < tx + scans:
                name = r.choice(names)
                start = name[: r.randint(8, len(name) - 1)]  # "svc/a000" or longer: a narrow range around a real key
                steps.append(("scan", (start, start + "~")))
            else:
                y = r.random()
                key = r.choice(names)
                if y < 0.5:
                    steps.append(("set", (key, r.choice(vals))))
                elif y < 0.65:
                    steps.append(("delete", (key,)))
                elif y < 0.85:
                    steps.append(("get", (key,)))
                else:
                    steps.append(("count", (r.choice(vals),)))
        return steps
    return build


PART1_TESTS = [
    OpsTest("example from the statement", [
        ("set", ("svc/api/mode", "canary"), None),
        ("set", ("svc/web/mode", "canary"), None),
        ("count", ("canary",), 2),
        ("set", ("svc/web/mode", "stable"), None),
        ("count", ("canary",), 1),
        ("get", ("svc/web/mode",), "stable"),
        ("delete", ("svc/api/mode",), True),
        ("delete", ("svc/api/mode",), False),
        ("count", ("canary",), 0),
    ], cls="Database"),
    OpsTest("missing keys and values", [
        ("get", ("nope",), None),
        ("count", ("nothing",), 0),
        ("delete", ("nope",), False),
        ("set", ("k", ""), None),
        ("get", ("k",), ""),
        ("count", ("",), 1),
    ], cls="Database", description="the empty string is a real value"),
    OpsTest("overwriting with the same value", [
        ("set", ("a", "x"), None),
        ("set", ("a", "x"), None),
        ("count", ("x",), 1),
        ("set", ("b", "x"), None),
        ("delete", ("a",), True),
        ("count", ("x",), 1),
    ], cls="Database", hidden=True),
    OpsTest("random traffic", gen(1, n=2_000, keys=200, values=10), cls="Database", hidden=True),
    OpsTest("busy store (120,000 calls)", gen(2, n=120_000, keys=40_000, values=50, prefill=20_000), cls="Database",
            hidden=True, time_limit=2.0),
]

PART2_TESTS = [
    OpsTest("example from the statement", [
        ("set", ("a", "10"), None),
        ("begin", (), None),
        ("set", ("a", "20"), None),
        ("begin", (), None),
        ("delete", ("a",), True),
        ("get", ("a",), None),
        ("rollback", (), True),
        ("get", ("a",), "20"),
        ("rollback", (), True),
        ("get", ("a",), "10"),
        ("rollback", (), False),
        ("begin", (), None),
        ("set", ("b", "1"), None),
        ("begin", (), None),
        ("set", ("c", "1"), None),
        ("commit", (), True),
        ("rollback", (), False),
        ("count", ("1",), 2),
    ], cls="Database"),
    OpsTest("counts follow rollbacks", [
        ("set", ("a", "x"), None),
        ("set", ("b", "x"), None),
        ("begin", (), None),
        ("set", ("a", "y"), None),
        ("delete", ("b",), True),
        ("set", ("c", "x"), None),
        ("count", ("x",), 1),
        ("count", ("y",), 1),
        ("rollback", (), True),
        ("count", ("x",), 2),
        ("count", ("y",), 0),
        ("get", ("c",), None),
    ], cls="Database"),
    OpsTest("same key, many times", [
        ("begin", (), None),
        ("set", ("k", "1"), None),
        ("set", ("k", "2"), None),
        ("delete", ("k",), True),
        ("set", ("k", "3"), None),
        ("begin", (), None),
        ("set", ("k", "4"), None),
        ("rollback", (), True),
        ("get", ("k",), "3"),
        ("rollback", (), True),
        ("get", ("k",), None),
        ("count", ("3",), 0),
    ], cls="Database", hidden=True),
    OpsTest("commit with nothing open", [
        ("commit", (), False), ("begin", (), None), ("commit", (), True), ("commit", (), False), ("rollback", (), False),
    ], cls="Database", hidden=True),
    OpsTest("random transactions", gen(3, n=3_000, keys=100, values=5, tx=0.15), cls="Database", hidden=True),
    OpsTest("deep nesting", gen(4, n=5_000, keys=300, values=8, tx=0.3, deep=True), cls="Database", hidden=True),
    OpsTest("big store, small transactions (60,000 calls)", gen(5, n=60_000, keys=60_000, values=50, tx=0.3, prefill=50_000),
            cls="Database", hidden=True, time_limit=2.0,
            description="50,000 keys and ~18,000 transaction calls; begin and rollback can't copy the store"),
]

PART3_TESTS = [
    OpsTest("example from the statement", [
        ("set", ("svc/web/mode", "stable"), None),
        ("set", ("svc/api/mode", "canary"), None),
        ("set", ("svc/api/replicas", "3"), None),
        ("set", ("svc/b", "x"), None),
        ("scan", ("svc/api/", "svc/api0"), [("svc/api/mode", "canary"), ("svc/api/replicas", "3")]),
        ("scan", ("svc/a", "svc/c"), [("svc/api/mode", "canary"), ("svc/api/replicas", "3"), ("svc/b", "x")]),
    ], cls="Database"),
    OpsTest("scans and transactions", [
        ("set", ("b", "1"), None),
        ("begin", (), None),
        ("set", ("a", "2"), None),
        ("delete", ("b",), True),
        ("set", ("c", "3"), None),
        ("scan", ("a", "z"), [("a", "2"), ("c", "3")]),
        ("rollback", (), True),
        ("scan", ("a", "z"), [("b", "1")]),
    ], cls="Database"),
    OpsTest("edges", [
        ("set", ("a", "1"), None),
        ("set", ("b", "2"), None),
        ("scan", ("a", "b"), [("a", "1")]),
        ("scan", ("b", "a"), []),
        ("scan", ("", "~"), [("a", "1"), ("b", "2")]),
        ("scan", ("c", "d"), []),
    ], cls="Database", hidden=True, description="end is exclusive; an empty or backwards range"),
    OpsTest("random scans", gen(6, n=3_000, keys=300, values=6, tx=0.1, scans=0.2), cls="Database", hidden=True),
    OpsTest("big store, many scans (30,000 calls)", gen(7, n=30_000, keys=60_000, values=20, tx=0.05, scans=0.1,
                                                       prefill=50_000),
            cls="Database", hidden=True, time_limit=2.0, description="~3,000 scans over 50,000 changing keys"),
]

PROBLEM = Problem(
    key="kv-store",
    title="Transactional Key-Value Store",
    difficulty="medium",
    summary="A config store with value counts, nested transactions and ordered range scans.",
    tags=["design", "transactions", "indexing"],
    minutes=60,
    intro=INTRO,
    parts=[
        Part("Keys, values and counts", PART1, PART1_TESTS, hints=[
            "Keep a second dict from value to how many keys hold it, and update it on every change.",
        ]),
        Part("Transactions", PART2, PART2_TESTS, hints=[
            "Instead of saving the whole store at begin, save what each change overwrote.",
            "Route every change through one internal method, so the undo log and the counts can't be forgotten.",
        ]),
        Part("Range scans", PART3, PART3_TESTS, hints=[
            "Keep the keys in a sorted list next to the dict; the bisect module finds a range in O(log n).",
            "If rollback goes through the same write method, the sorted list stays right for free.",
        ]),
    ],
    starter=STARTER,
    reference=REFERENCE,
    discussion=DISCUSSION,
    writeup=WRITEUP,
)
