"""API Rate Limiter: sliding-window limits per client, several rules at once, weighted requests, idle-client eviction"""

import random

from framework import OpsTest, Part, Problem

INTRO = """
Your company runs a public API gateway. Every request carries a client id, and each client may only make so many
requests in a sliding time window. You're writing the component that answers one question per request:
**allow it or reject it?**

It sits on the hot path of every request, so each decision needs to be fast, and it sees hundreds of thousands of
clients, most of whom go quiet after a few calls, so memory can't grow forever.

Implement a class `RateLimiter`. Each part adds requirements to the same class, and tests for a part also re-run
every earlier part's tests.

Throughout: timestamps are integers (seconds), and they never decrease from one call to the next, across all clients
and all methods.
"""

PART1 = """
```python
class RateLimiter:
    def __init__(self, limit: int, window: int): ...
    def allow(self, client_id: str, timestamp: int) -> bool: ...
```

A request at time `t` is **allowed** if the client has had fewer than `limit` allowed requests in the window
`(t - window, t]`, that is, strictly after `t - window`, up to and including `t`. Allowed requests count against
the client's limit; **rejected requests don't count**. Clients are independent.

**Example**

```python
rl = RateLimiter(limit=2, window=10)
rl.allow("ana", 1)    # True
rl.allow("ana", 5)    # True
rl.allow("ana", 9)    # False: 1 and 5 are in (-1, 9]
rl.allow("bo", 9)     # True: bo has his own budget
rl.allow("ana", 11)   # True: the window is now (1, 11], so only 5 counts
rl.allow("ana", 12)   # False: 5 and 11
rl.allow("ana", 15)   # True: the window (5, 15] holds only 11
```

Hidden tests include a few very busy clients with large limits.
"""

PART2 = """
```python
    def add_rule(self, limit: int, window: int) -> None: ...
```

A gateway usually enforces more than one limit, like *10 per second and 500 per hour*. `add_rule` adds another
limit alongside the one from the constructor. A request is allowed only if **every** rule allows it, and an allowed
request counts against every rule. A rejected request counts against none.

All `add_rule` calls happen before the first `allow`.

**Example**

```python
rl = RateLimiter(limit=2, window=10)
rl.add_rule(limit=3, window=100)
rl.allow("ana", 0)    # True
rl.allow("ana", 1)    # True
rl.allow("ana", 2)    # False: 2 per 10s
rl.allow("ana", 20)   # True
rl.allow("ana", 40)   # False: 3 per 100s (0, 1, 20)
rl.allow("ana", 100)  # True: (0, 100] holds only 1 and 20
```
"""

PART3 = """
```python
    def allow(self, client_id: str, timestamp: int, cost: int = 1) -> bool: ...
```

Some endpoints are more expensive than others. A request now has a `cost` (a positive integer, default 1), and
limits are on total cost rather than on request count: a request is allowed if, for every rule, the cost of the
client's allowed requests in the window plus this request's cost is at most the rule's `limit`.

A request costing more than a rule's limit is always rejected.

**Example**

```python
rl = RateLimiter(limit=10, window=60)
rl.allow("ana", 0, cost=6)    # True
rl.allow("ana", 1, cost=5)    # False: 6 + 5 > 10
rl.allow("ana", 2, cost=4)    # True: 6 + 4 = 10
rl.allow("ana", 3)            # False: already at 10
rl.allow("ana", 60, cost=6)   # True: the window (0, 60] holds only the 4
```
"""

PART4 = """
```python
    def active_clients(self, timestamp: int) -> int: ...
```

Operations wants a live count of **active clients**: clients with at least one allowed request in
`(timestamp - W, timestamp]`, where `W` is the longest window of any rule.

The gateway sees a long tail of clients who make a few calls and leave. The hidden tests send several hundred
thousand clients through the limiter and ask for `active_clients` every 50 requests, so both
`active_clients` and the memory the limiter holds must not grow with the number of clients ever seen. Only recent
ones should count.

**Example**

```python
rl = RateLimiter(limit=5, window=10)
rl.allow("ana", 1)
rl.allow("bo", 4)
rl.active_clients(5)    # 2
rl.active_clients(11)   # 1: ana's request at 1 is outside (1, 11]
rl.active_clients(14)   # 0
```
"""

STARTER = '''class RateLimiter:
    def __init__(self, limit: int, window: int):
        pass

    def allow(self, client_id: str, timestamp: int) -> bool:
        pass
'''

REFERENCE = '''from collections import OrderedDict, deque


class Window:
    """one client's allowed requests under one rule: (timestamp, cost) pairs inside the window, plus their total"""

    __slots__ = ("events", "total")

    def __init__(self):
        self.events = deque()
        self.total = 0

    def expire(self, cutoff):
        events = self.events
        while events and events[0][0] <= cutoff:
            self.total -= events.popleft()[1]


class RateLimiter:
    def __init__(self, limit, window):
        self.rules = [(limit, window)]
        self.longest = window
        self.clients = {}             # client id -> [Window per rule]
        self.last_seen = OrderedDict()  # client id -> time of its last allowed request, oldest first

    def add_rule(self, limit, window):
        self.rules.append((limit, window))
        self.longest = max(self.longest, window)

    def allow(self, client_id, timestamp, cost=1):
        self.evict(timestamp)
        windows = self.clients.get(client_id)
        if windows is None:
            windows = [Window() for _ in self.rules]
        for (limit, window), w in zip(self.rules, windows):
            w.expire(timestamp - window)
            if w.total + cost > limit:
                return False
        for w in windows:
            w.events.append((timestamp, cost))
            w.total += cost
        self.clients[client_id] = windows
        self.last_seen[client_id] = timestamp
        self.last_seen.move_to_end(client_id)
        return True

    def active_clients(self, timestamp):
        self.evict(timestamp)
        return len(self.last_seen)

    def evict(self, timestamp):
        """forget clients whose last allowed request is outside every window; their state would be empty anyway"""
        cutoff = timestamp - self.longest
        last_seen = self.last_seen
        while last_seen:
            client, t = next(iter(last_seen.items()))
            if t > cutoff:
                break
            last_seen.popitem(last=False)
            del self.clients[client]
'''

WRITEUP = """
### How the reference works

**One deque per client per rule.** Each deque holds the client's allowed requests that are still inside that rule's
window, as `(timestamp, cost)` pairs, plus a running total. Because timestamps never decrease, expired entries are
always at the left end, so expiring is `popleft` until the head is inside the window. Every entry is appended once
and popped once, so `allow` is **amortised O(rules)**, however busy the client is.

The common slow version keeps a list per client and rebuilds it every call
(`times = [t for t in times if t > now - window]`). That's O(limit) per call, which is what the busy-client hidden
tests catch with large limits.

**Check all rules, then commit.** A rejected request must not count anywhere, so `allow` checks every rule first and
only appends once all pass. Doing it in one loop (check rule 1, append, check rule 2, fail) leaves a phantom entry
in rule 1.

**Eviction with an ordered dict.** `last_seen` maps each client to its latest allowed timestamp, with the most
recently active client moved to the end. So the front of the dict is always the client who has been quiet the
longest, and eviction pops from the front while that client's last request is outside the longest window. Its
deques would be empty by then, so dropping them loses nothing. `active_clients` is then just `len(last_seen)`,
amortised O(1), and memory is bounded by the clients active in the last `W` seconds.

### Tradeoffs worth saying out loud

- **Sliding log (this) vs fixed window vs sliding counter vs token bucket.** A log is exact but stores up to `limit`
  entries per client per rule. A *fixed window* (one counter per client per `window`-aligned bucket) is O(1) memory
  but lets a client send 2× the limit across a bucket boundary. A *sliding window counter* weights the previous
  bucket's count by overlap: O(1) memory, approximately right. A *token bucket* refills continuously, allows
  controlled bursts, and is O(1). The exact semantics asked for here force a log; in production you'd usually take
  the approximation.
- **Many rules.** Storing a deque per rule duplicates entries. One deque sized to the longest window, with prefix
  sums of cost and a binary search per rule, stores each request once at O(log n) per rule per call.
- **Distributed gateways.** With many gateway servers, state lives in something shared (Redis with a sorted set per
  client, or `INCR` with a TTL for fixed windows). Then the questions are atomicity (check-and-add must be one
  operation, e.g. a Lua script), clock skew between servers, and what to do when the store is down (fail open or
  fail closed).
- **Timestamps that go backwards.** The tests promise they don't. If they could, you'd need a sorted structure per
  client instead of a deque, or you'd clamp to the latest time seen.
"""

DISCUSSION = [
    "What is the time complexity of allow, and what's the worst case for a single call?",
    "How much memory does your limiter use per client? Per rule? What would you trade to bound it further?",
    "Compare your approach with a fixed window counter and a token bucket. When is each one the right choice?",
    "If a request fails the second rule, how do you make sure it doesn't count against the first?",
    "How would you run this across 50 gateway servers that must share limits?",
    "What happens if timestamps can arrive slightly out of order (say, up to 2 seconds late)?",
]


def gen(seed, *, n, clients, rules, max_cost=1, hot=0.0, gap=3, active_every=0, churn=False):
    """a request log: (method, args) steps with non-decreasing timestamps"""
    def build():
        r = random.Random(seed)
        steps = [("add_rule", rule) for rule in rules[1:]]
        t = 0
        hot_ids = [f"hot{i}" for i in range(3)]
        fresh = 0
        for i in range(n):
            t += r.randint(0, gap)
            if hot and r.random() < hot:
                cid = r.choice(hot_ids)
            elif churn:
                fresh += r.random() < 0.6
                cid = f"c{max(0, fresh - r.randint(0, 20))}"
            else:
                cid = f"c{r.randint(0, clients - 1)}"
            if max_cost > 1:
                steps.append(("allow", (cid, t, r.randint(1, max_cost))))
            else:
                steps.append(("allow", (cid, t)))
            if active_every and i % active_every == 0:
                steps.append(("active_clients", (t,)))
        return steps
    return build


PART1_TESTS = [
    OpsTest("example from the statement", [
        ("allow", ("ana", 1), True),
        ("allow", ("ana", 5), True),
        ("allow", ("ana", 9), False),
        ("allow", ("bo", 9), True),
        ("allow", ("ana", 11), True),
        ("allow", ("ana", 12), False),
        ("allow", ("ana", 15), True),
    ], cls="RateLimiter", args=(2, 10)),
    OpsTest("window edges", [
        ("allow", ("x", 0), True),
        ("allow", ("x", 0), True),
        ("allow", ("x", 0), True),
        ("allow", ("x", 4), False),
        ("allow", ("x", 5), True),
        ("allow", ("x", 5), True),
        ("allow", ("x", 5), True),
        ("allow", ("x", 9), False),
        ("allow", ("x", 10), True),
    ], cls="RateLimiter", args=(3, 5), description="a request exactly `window` seconds old no longer counts"),
    OpsTest("rejections don't count", [
        ("allow", ("x", 0), True),
        ("allow", ("x", 1), False),
        ("allow", ("x", 2), False),
        ("allow", ("x", 3), False),
        ("allow", ("x", 4), True),
        ("allow", ("x", 7), False),
        ("allow", ("x", 8), True),
    ], cls="RateLimiter", args=(1, 4)),
    OpsTest("limit of one, window of one", [
        ("allow", ("x", 0), True), ("allow", ("x", 0), False), ("allow", ("x", 1), True), ("allow", ("y", 1), True),
        ("allow", ("x", 1), False), ("allow", ("x", 2), True),
    ], cls="RateLimiter", args=(1, 1), hidden=True),
    OpsTest("big gaps", [
        ("allow", ("x", 0), True), ("allow", ("x", 1), True), ("allow", ("x", 1_000_000), True),
        ("allow", ("x", 1_000_001), True), ("allow", ("x", 1_000_002), False),
    ], cls="RateLimiter", args=(2, 100), hidden=True),
    OpsTest("100 clients", gen(101, n=3_000, clients=100, rules=[(5, 30)]), cls="RateLimiter", args=(5, 30), hidden=True),
    OpsTest("busy clients, big limit (150,000 calls)", gen(102, n=150_000, clients=1, rules=[(5_000, 20_000)], hot=1.0, gap=1),
            cls="RateLimiter", args=(5_000, 20_000), hidden=True, time_limit=2.0,
            description="three clients hammering one limiter with a limit of 5,000"),
]

R2 = [(3, 10), (10, 100), (40, 1_000)]
R2_BIG = [(300, 1_000), (1_000, 5_000), (3_000, 20_000)]
PART2_TESTS = [
    OpsTest("example from the statement", [
        ("add_rule", (3, 100), None),
        ("allow", ("ana", 0), True),
        ("allow", ("ana", 1), True),
        ("allow", ("ana", 2), False),
        ("allow", ("ana", 20), True),
        ("allow", ("ana", 40), False),
        ("allow", ("ana", 100), True),
    ], cls="RateLimiter", args=(2, 10)),
    OpsTest("failing one rule doesn't count against the other", [
        ("add_rule", (2, 3), None),
        ("allow", ("x", 0), True),
        ("allow", ("x", 1), True),
        ("allow", ("x", 2), False),
        ("allow", ("x", 3), True),
        ("allow", ("x", 4), True),
        ("allow", ("x", 5), False),
        ("allow", ("x", 6), False),
        ("allow", ("x", 50), True),
    ], cls="RateLimiter", args=(4, 50),
        description="at time 2 rule 2 rejects; if rule 1 had counted it, time 4 would be rejected too"),
    OpsTest("three rules", gen(201, n=4_000, clients=20, rules=R2), cls="RateLimiter", args=R2[0], hidden=True),
    OpsTest("three rules, busy (100,000 calls)", gen(202, n=100_000, clients=50, rules=R2_BIG, hot=0.8, gap=1),
            cls="RateLimiter", args=R2_BIG[0], hidden=True, time_limit=2.0, description="large limits, a few hot clients"),
]

R3 = [(20, 60), (100, 600)]
PART3_TESTS = [
    OpsTest("example from the statement", [
        ("allow", ("ana", 0, 6), True),
        ("allow", ("ana", 1, 5), False),
        ("allow", ("ana", 2, 4), True),
        ("allow", ("ana", 3), False),
        ("allow", ("ana", 60, 6), True),
    ], cls="RateLimiter", args=(10, 60)),
    OpsTest("too expensive ever", [
        ("allow", ("x", 0, 11), False),
        ("allow", ("x", 0, 10), True),
        ("allow", ("x", 100, 11), False),
    ], cls="RateLimiter", args=(10, 50)),
    OpsTest("cost with two rules", [
        ("add_rule", (15, 100), None),
        ("allow", ("x", 0, 8), True),
        ("allow", ("x", 10, 8), False),
        ("allow", ("x", 10, 7), True),
        ("allow", ("x", 20, 1), False),
        ("allow", ("x", 101, 8), True),
    ], cls="RateLimiter", args=(10, 10), hidden=True),
    OpsTest("weighted traffic", gen(301, n=4_000, clients=30, rules=R3, max_cost=8), cls="RateLimiter", args=R3[0],
            hidden=True),
    OpsTest("weighted, busy (100,000 calls)", gen(302, n=100_000, clients=200, rules=R3, max_cost=8, hot=0.3, gap=1),
            cls="RateLimiter", args=R3[0], hidden=True, time_limit=2.0),
]

R4 = [(10, 30), (50, 300)]
PART4_TESTS = [
    OpsTest("example from the statement", [
        ("allow", ("ana", 1), True),
        ("allow", ("bo", 4), True),
        ("active_clients", (5,), 2),
        ("active_clients", (11,), 1),
        ("active_clients", (14,), 0),
    ], cls="RateLimiter", args=(5, 10)),
    OpsTest("longest window decides", [
        ("add_rule", (100, 50), None),
        ("allow", ("a", 0), True),
        ("allow", ("b", 30), True),
        ("active_clients", (40,), 2),
        ("active_clients", (50,), 1),
        ("allow", ("a", 60), True),
        ("active_clients", (79,), 2),
        ("active_clients", (80,), 1),
    ], cls="RateLimiter", args=(1, 5)),
    OpsTest("rejected requests don't make a client active", [
        ("allow", ("a", 0), True),
        ("allow", ("a", 5), False),
        ("active_clients", (10,), 0),
        ("allow", ("a", 10), True),
        ("active_clients", (10,), 1),
    ], cls="RateLimiter", args=(1, 10), hidden=True),
    OpsTest("a coming and going crowd", gen(401, n=5_000, clients=0, rules=R4, churn=True, active_every=50),
            cls="RateLimiter", args=R4[0], hidden=True),
    OpsTest("the long tail (200,000 calls)", gen(402, n=200_000, clients=0, rules=R4, churn=True, active_every=50, gap=1),
            cls="RateLimiter", args=R4[0], hidden=True, time_limit=3.0,
            description="~120,000 distinct clients, active_clients every 50 requests"),
]

PROBLEM = Problem(
    key="rate-limiter",
    title="API Rate Limiter",
    difficulty="medium",
    summary="Allow or reject each request under sliding-window limits, fast and with bounded memory.",
    tags=["design", "sliding window", "queues"],
    minutes=60,
    intro=INTRO,
    parts=[
        Part("Sliding window", PART1, PART1_TESTS, hints=[
            "Timestamps never decrease, so a client's old requests always leave from the front. Which structure removes from the front in O(1)?",
            "Only append a request once you've decided to allow it.",
        ]),
        Part("Several rules", PART2, PART2_TESTS, hints=[
            "Check every rule first; only if all pass, record the request under each of them.",
        ]),
        Part("Weighted requests", PART3, PART3_TESTS, hints=[
            "Keep a running total of cost for each window instead of counting entries.",
        ]),
        Part("Active clients", PART4, PART4_TESTS, hints=[
            "If you track each client's last allowed time in order of last activity, the clients to forget are always at the front.",
            "collections.OrderedDict has move_to_end and popitem(last=False).",
        ]),
    ],
    starter=STARTER,
    reference=REFERENCE,
    discussion=DISCUSSION,
    writeup=WRITEUP,
)
