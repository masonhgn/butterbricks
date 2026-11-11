"""Fulfillment Center: orders, stock, and packing shipped orders onto as few trucks as possible"""

import math
import random

from framework import OpsTest, Part, Problem, ScenarioTest, Unordered
from framework.tests import fresh, same, show, show_call

INTRO = """
You're building the order system for a manufacturing company's fulfillment center. Customers place orders for
items (by SKU) to be delivered to a destination. The warehouse holds limited stock, and once a day the center
**dispatches**: it decides which pending orders can be filled and loads them onto trucks.

Trucks are the expensive part. Many orders go to the same places, so grouping them well matters, and the center
handles thousands of orders a day, so your code needs to stay fast as the numbers grow.

Implement a class `FulfillmentCenter`. The problem comes in parts: each one adds requirements to the same class,
so keep your design easy to extend. Tests for a part also re-run every earlier part's tests.
"""

PART1 = """
```python
class FulfillmentCenter:
    def __init__(self): ...
    def restock(self, sku: str, qty: int) -> int: ...
    def stock(self, sku: str) -> int: ...
    def place_order(self, order_id: str, destination: str, items: dict[str, int]) -> bool: ...
    def cancel_order(self, order_id: str) -> bool: ...
    def order_status(self, order_id: str) -> str | None: ...
    def pending_orders(self) -> list[str]: ...
```

- `restock(sku, qty)` adds `qty` units (always positive) and returns the new quantity on hand.
- `stock(sku)` is the quantity on hand, `0` for a SKU never seen.
- `place_order` records a new **pending** order and returns `True`. It returns `False` and records nothing if the
  `order_id` has been used before (by any order, in any state), if `items` is empty, or if any quantity is ≤ 0.
  Placing an order does **not** take stock: stock is only taken when an order ships (part 2).
- `cancel_order` cancels a pending order and returns `True`. It returns `False` for unknown orders and for orders
  that aren't pending.
- `order_status` is `"pending"`, `"cancelled"` or `"shipped"`, or `None` for an unknown id.
- `pending_orders()` lists pending order ids, oldest (first placed) first.

**Example**

```python
fc = FulfillmentCenter()
fc.restock("bolt", 50)                                   # 50
fc.place_order("o1", "Denver", {"bolt": 10, "nut": 4})   # True
fc.place_order("o1", "Austin", {"nut": 1})               # False: o1 is taken
fc.place_order("o2", "Austin", {})                       # False: no items
fc.place_order("o3", "Austin", {"bolt": 5})              # True
fc.cancel_order("o1")                                    # True
fc.order_status("o1")                                    # "cancelled"
fc.pending_orders()                                      # ["o3"]
fc.stock("bolt")                                         # 50
```

Hidden tests place and cancel tens of thousands of orders, calling `pending_orders()` along the way.
"""

PART2 = """
```python
    def dispatch(self, truck_capacity: int) -> list[dict]: ...
```

`dispatch` ships what it can and returns the trucks it loaded. It works in two steps.

**1. Decide which orders ship.** Go through pending orders oldest first. An order ships if the warehouse has enough
stock for **every** item in it **and** its total unit count (the sum of its quantities) is at most
`truck_capacity`. A shipping order takes its stock right away and becomes `"shipped"`. An order that can't ship is
skipped and stays pending (a later, smaller order may still ship). Orders are never split.

**2. Load the shipped orders onto trucks.** Each truck is a dict `{"stops": [destination], "orders": [order ids]}`:

- every shipped order is on exactly one truck,
- a truck's orders all go to the same destination, which is its only stop,
- the units on a truck add up to at most `truck_capacity`.

Order of trucks, and of orders within a truck, doesn't matter. Return `[]` if nothing ships.

**Use as few trucks as you can.** Tests compare your truck count with the reference solution's: you pass at or
below its count (big hidden tests allow 2% slack). This is the open-ended part: there's no fast way to always find
the minimum, so pick an approach you can justify.

**Example**

```python
fc = FulfillmentCenter()
fc.restock("bolt", 100)
for oid, n in [("a", 1), ("b", 3), ("c", 8), ("d", 9), ("e", 7)]:
    fc.place_order(oid, "Denver", {"bolt": n})
fc.place_order("f", "Austin", {"bolt": 90})
fc.dispatch(10)
# f doesn't fit on a truck and stays pending; the rest ship, 28 units to Denver.
# Loading them in arrival order takes 4 trucks; 3 is possible:
# [{"stops": ["Denver"], "orders": ["d", "a"]},
#  {"stops": ["Denver"], "orders": ["c"]},
#  {"stops": ["Denver"], "orders": ["e", "b"]}]
fc.stock("bolt")      # 72
```
"""

PART3 = """
Nearby destinations are now grouped into delivery routes, and one truck can serve several stops on the same route.

```python
    def set_route(self, route_id: str, stops: list[str]) -> None: ...
    def dispatch(self, truck_capacity: int, max_stops: int | None = None) -> list[dict]: ...
```

- `set_route` defines a route. Calling it again with the same `route_id` replaces that route's stops. A destination
  is on at most one route: listing it in a route removes it from any route it was on. A destination on no route is
  served on its own, as in part 2.
- A truck's orders must all go to destinations on **one** route (or all to the same unrouted destination). Its
  `"stops"` list holds each destination it delivers to, once.
- `max_stops`, when given, limits how many stops one truck may make. `None` means no limit.
- Routes only affect loading. Which orders ship is decided exactly as in part 2.

Truck counts are graded as in part 2, against the reference with 5% slack on big tests.

**Example**

```python
fc.set_route("west", ["Denver", "Boise", "Reno"])
# Orders: Denver 6 units, Boise 4, Reno 5, Reno 5, Austin 3; capacity 10
fc.dispatch(10)
# [{"stops": ["Denver", "Boise"], "orders": [...]},
#  {"stops": ["Reno"], "orders": [...]},
#  {"stops": ["Austin"], "orders": [...]}]
```
"""

PART4 = """
```python
    def place_order(self, order_id: str, destination: str, items: dict[str, int], express: bool = False) -> bool: ...
```

Some customers pay for express delivery. Change `dispatch` so that:

- **express orders get first claim on stock.** Step 1 now goes through pending express orders oldest first, then
  pending standard orders oldest first.
- **express and standard orders never share a truck** (express trucks leave as soon as they're loaded).

Everything else is unchanged. `pending_orders()` still lists every pending order by placement time, express or not.
"""

STARTER = '''class FulfillmentCenter:
    def __init__(self):
        pass

    def restock(self, sku: str, qty: int) -> int:
        pass

    def stock(self, sku: str) -> int:
        pass

    def place_order(self, order_id: str, destination: str, items: dict[str, int]) -> bool:
        pass

    def cancel_order(self, order_id: str) -> bool:
        pass

    def order_status(self, order_id: str) -> str | None:
        pass

    def pending_orders(self) -> list[str]:
        pass
'''

REFERENCE = '''from collections import defaultdict
from dataclasses import dataclass


@dataclass
class Order:
    id: str
    destination: str
    items: dict
    units: int
    express: bool
    status: str = "pending"


class FulfillmentCenter:
    def __init__(self):
        self.stock_on_hand = defaultdict(int)
        self.orders = {}           # every order ever placed, by id
        self.pending = {}          # pending ids in placement order (dicts keep insertion order) -> None
        self.route_of = {}         # destination -> route id
        self.routes = {}           # route id -> set of destinations

    # part 1

    def restock(self, sku, qty):
        self.stock_on_hand[sku] += qty
        return self.stock_on_hand[sku]

    def stock(self, sku):
        return self.stock_on_hand.get(sku, 0)

    def place_order(self, order_id, destination, items, express=False):
        if order_id in self.orders or not items or any(q <= 0 for q in items.values()):
            return False
        self.orders[order_id] = Order(order_id, destination, dict(items), sum(items.values()), express)
        self.pending[order_id] = None
        return True

    def cancel_order(self, order_id):
        if order_id not in self.pending:
            return False
        del self.pending[order_id]
        self.orders[order_id].status = "cancelled"
        return True

    def order_status(self, order_id):
        order = self.orders.get(order_id)
        return order.status if order else None

    def pending_orders(self):
        return list(self.pending)

    # parts 2-4

    def set_route(self, route_id, stops):
        for dest in self.routes.pop(route_id, ()):
            del self.route_of[dest]
        self.routes[route_id] = set()
        for dest in stops:
            old = self.route_of.get(dest)
            if old is not None:
                self.routes[old].discard(dest)
            self.route_of[dest] = route_id
            self.routes[route_id].add(dest)

    def dispatch(self, truck_capacity, max_stops=None):
        shipped = []
        # express first, then standard; sorted() is stable so each group stays oldest first
        for oid in sorted(self.pending, key=lambda oid: not self.orders[oid].express):
            order = self.orders[oid]
            if order.units > truck_capacity:
                continue
            if any(self.stock_on_hand.get(sku, 0) < q for sku, q in order.items.items()):
                continue
            for sku, q in order.items.items():
                self.stock_on_hand[sku] -= q
            order.status = "shipped"
            del self.pending[oid]
            shipped.append(order)

        # orders that may share a truck: same route (or same unrouted destination), same speed
        groups = defaultdict(list)
        for order in shipped:
            route = self.route_of.get(order.destination)
            key = ("route", route) if route is not None else ("dest", order.destination)
            groups[key, order.express].append(order)

        trucks = []
        for group in groups.values():
            trucks += pack(group, truck_capacity, max_stops)
        return trucks


def pack(orders, capacity, max_stops):
    """first fit decreasing: biggest orders first, each onto the first truck it fits on"""
    loaded = []  # [room left, stops, order ids]
    for order in sorted(orders, key=lambda o: o.units, reverse=True):
        for truck in loaded:
            room, stops, _ = truck
            if room >= order.units and (order.destination in stops or max_stops is None or len(stops) < max_stops):
                break
        else:
            truck = [capacity, [], []]
            loaded.append(truck)
        truck[0] -= order.units
        if order.destination not in truck[1]:
            truck[1].append(order.destination)
        truck[2].append(order.id)
    return [{"stops": stops, "orders": ids} for _, stops, ids in loaded]
'''

WRITEUP = """
### How the reference works

**Data layout.** Every order lives in one dict keyed by id, so status lookups and duplicate checks are O(1). Pending
orders are kept in a second dict used as an *ordered set*: Python dicts keep insertion order, so iterating it gives
oldest first, and cancelling is an O(1) delete. A plain list makes `cancel_order` O(n) (`list.remove`, plus the
`in` check). That still passes the tests here, because both run at C speed, but it's quadratic overall and worth
naming.

**Allocation is separate from packing.** `dispatch` first decides *who ships* (a deterministic, greedy, oldest-first
pass), then decides *how to load* the shipped orders. Keeping them apart is what makes parts 3 and 4 small changes:
routes and express only change the grouping key and the iteration order.

**Packing is bin packing**, which is NP-hard, so the reference uses **first fit decreasing** (FFD) inside each group:
sort orders by size, biggest first, and put each one on the first truck with room, opening a new truck when none has
room. FFD never uses more than about 11/9 of the optimum, and on realistic data it's usually at or within one truck of
the lower bound `ceil(total units / capacity)`. Biggest first matters: small orders placed early fill gaps that the
big orders arriving later needed. Loading in arrival order (first fit) or only ever topping up the newest truck (next
fit) can be much worse.

With `max_stops`, FFD also requires that a truck either already stops at the order's destination or has a stop to
spare. This greedy rule is weaker: it can spread one destination's orders over many trucks. A good alternative is to
pack each destination on its own first, then merge the partially filled trucks within a route.

### Tradeoffs worth saying out loud

- **Greedy allocation vs maximising orders shipped.** Oldest first is fair and predictable, but a big early order
  can take stock that would have filled three later ones. Shipping the most orders is a knapsack-style problem.
  Fairness is the usual business answer; say why.
- **Cost.** FFD here is O(n · trucks) per group. With thousands of orders that's fine; with millions you'd want a
  balanced tree keyed by remaining room (best fit in O(log n)) or bucket by room, since capacities are small integers.
- **Exact vs heuristic.** Optimal packing (branch and bound, or an ILP solver) is fine for a few dozen orders per
  truck route and hopeless at scale. Use a heuristic with a known bound and measure it against the lower bound.
- **What's missing.** Real dispatch has weight and volume (two-dimensional bins), truck routing order, time windows,
  partial shipments and stock reservations at order time. Mention which you'd add next and how the separation of
  allocation and packing makes room for them.
"""

DISCUSSION = [
    "Why did you pick that data structure for pending orders? What are cancel_order and pending_orders' complexities?",
    "Packing trucks optimally is NP-hard. Which heuristic did you pick, how far from optimal can it get, and how would you know in production?",
    "Oldest-first allocation can ship fewer orders than the maximum possible. When would you change that policy, and to what?",
    "Should stock be reserved when an order is placed instead of when it ships? What breaks either way?",
    "How did part 3 (routes) or part 4 (express) change your code? What in your part 2 design made that easy or hard?",
    "If dispatch had to handle 10 million orders, what would you change first?",
]


# test helpers


def order_units(items):
    return sum(items.values())


class Tracker:
    """replays a script independently of both solutions, to know each order's destination, size and route"""

    def __init__(self):
        self.orders = {}  # id -> (destination, units, express), for orders the reference accepted
        self.route_of = {}
        self.routes = {}

    def apply(self, method, args, kwargs, ok):
        if method == "place_order" and ok:
            oid, dest, items = args[:3]
            express = kwargs.get("express", args[3] if len(args) > 3 else False)
            self.orders[oid] = (dest, order_units(items), express)
        elif method == "set_route":
            rid, stops = args
            for d in self.routes.pop(rid, ()):
                self.route_of.pop(d, None)
            self.routes[rid] = set()
            for d in stops:
                if d in self.route_of:
                    self.routes[self.route_of[d]].discard(d)
                self.route_of[d] = rid
                self.routes[rid].add(d)

    def group(self, oid):
        dest, _, express = self.orders[oid]
        route = self.route_of.get(dest)
        return (("route", route) if route is not None else ("dest", dest)), express


def check_trucks(ctx, label, trucks, want, tracker, capacity, max_stops, slack):
    ctx.check(isinstance(trucks, list), f"{label} returned {show(trucks)}, expected a list of trucks")
    seen = set()
    for n, t in enumerate(trucks, 1):
        where = f"{label}, truck {n} of {len(trucks)}"
        ctx.check(isinstance(t, dict) and isinstance(t.get("stops"), (list, tuple)) and isinstance(t.get("orders"), (list, tuple)),
                  f'{where} is {show(t)}, expected {{"stops": [...], "orders": [...]}}')
        ctx.check(len(t["orders"]) > 0, f"{where} is empty")
        for oid in t["orders"]:
            ctx.check(oid in tracker.orders, f"{where} carries {oid!r}, which is not an order")
            ctx.check(oid not in seen, f"{where} carries {oid!r}, which is already on another truck")
            seen.add(oid)
        units = sum(tracker.orders[oid][1] for oid in t["orders"])
        ctx.check(units <= capacity, f"{where} holds {units} units, the capacity is {capacity}", [f"orders: {show(t['orders'])}"])
        dests = {tracker.orders[oid][0] for oid in t["orders"]}
        ctx.check(len(set(t["stops"])) == len(t["stops"]) and set(t["stops"]) == dests,
                  f'{where} lists stops {show(t["stops"])} but its orders go to {show(sorted(dests))}')
        groups = {tracker.group(oid) for oid in t["orders"]}
        if len({g[0] for g in groups}) > 1:
            ctx.fail(f"{where} mixes destinations that aren't on one route: {show(sorted(dests))}")
        if len(groups) > 1:
            ctx.fail(f"{where} mixes express and standard orders")
        if max_stops is not None:
            ctx.check(len(dests) <= max_stops, f"{where} makes {len(dests)} stops, max_stops is {max_stops}")

    want_ids = {oid for t in want for oid in t["orders"]}
    missing, extra = sorted(want_ids - seen), sorted(seen - want_ids)
    if missing or extra:
        details = []
        if missing:
            details.append(f"should have shipped but didn't: {show(missing)}")
        if extra:
            details.append(f"shipped but shouldn't have: {show(extra)}")
        details.append("orders ship oldest first (express first, from part 4) if every item is in stock and the order fits on a truck")
        ctx.fail(f"{label} shipped the wrong set of orders", details)

    per_group = {}
    for oid in want_ids:
        g = tracker.group(oid)
        per_group[g] = per_group.get(g, 0) + tracker.orders[oid][1]
    lower = sum(math.ceil(u / capacity) for u in per_group.values())
    target = len(want) + math.floor(slack * len(want))
    ctx.metric(f"trucks ({label})", len(trucks), target=target,
               context=f"reference {len(want)}, lower bound {lower}" + (f", {slack:.0%} slack" if slack else ""))


def script_test(name, script, *, slack=0.0, **kw):
    """a ScenarioTest that runs a script of calls on both solutions. Plain calls must return what the reference returns;
    dispatch calls are validated instead, since many truck loadings are right"""

    def fn(ctx):
        steps = script() if callable(script) else script
        user, ref = ctx.new("FulfillmentCenter"), ctx.new_reference("FulfillmentCenter")
        tracker = Tracker()
        skus = set()
        dispatches = 0
        for i, (method, args, *rest) in enumerate(steps):
            kwargs = rest[0] if rest else {}
            call = show_call(method, args, kwargs)
            args, ref_args = fresh(args), args
            ctx.check(hasattr(user, method), f"FulfillmentCenter has no method {method}")
            if method == "dispatch":
                dispatches += 1
                capacity = args[0]
                max_stops = kwargs.get("max_stops", args[1] if len(args) > 1 else None)
                want = ref.dispatch(*ref_args, **kwargs)
                got = getattr(user, method)(*args, **kwargs)
                label = f"dispatch #{dispatches} (step {i + 1})" if dispatches > 1 or i + 1 < len(steps) else "dispatch"
                check_trucks(ctx, label, got, want, tracker, capacity, max_stops, slack)
                for sku in sorted(skus):
                    g, w = user.stock(sku), ref.stock(sku)
                    ctx.check(g == w, f"after {label}, stock({sku!r}) is {g}, expected {w}")
                ctx.check(same(user.pending_orders(), ref.pending_orders()), f"after {label}, pending_orders() is wrong",
                          [f"expected  {show(ref.pending_orders())}", f"got       {show(user.pending_orders())}"])
                continue
            want = getattr(ref, method)(*ref_args, **kwargs)
            got = getattr(user, method)(*args, **kwargs)
            ctx.check(same(got, want), f"wrong result at step {i + 1:,}",
                      [f"step {i + 1:,}: {call}", f"  expected  {show(want)}", f"  got       {show(got)}"])
            tracker.apply(method, ref_args, kwargs, want)
            if method == "restock":
                skus.add(args[0])
            if method == "place_order":
                skus.update(args[2])
        ctx.note(f"{len(steps):,} calls, {dispatches} dispatch{'es' if dispatches != 1 else ''}")

    sample = [] if callable(script) else ["fc = FulfillmentCenter()"] + [
        f"fc.{show_call(m, a, r[0] if r else {})}" for m, a, *r in script]
    return ScenarioTest(name, fn, sample=sample, **kw)


DESTS = ["Denver", "Austin", "Boise", "Reno", "Tulsa", "Omaha", "Fresno", "Tucson", "Mesa", "Wichita", "Toledo",
         "Laredo", "Durham", "Irvine", "Madison", "Spokane", "Tacoma", "Fargo", "Billings", "Provo"]


def random_script(seed, *, orders, dests, skus, capacity, rounds=1, cancel=0.05, routes=0, max_stops=None,
                  express=0.0, max_qty=6, lines=3, stock_ratio=0.8):
    """a day of activity: restocks, orders, cancellations, route changes and dispatches"""
    r = random.Random(seed)
    places = (DESTS + [f"Depot-{i}" for i in range(dests)])[:dests]
    sku_names = [f"sku-{i:03}" for i in range(skus)]
    steps, placed = [], []
    per_round = orders // rounds
    for rnd in range(rounds):
        demand = per_round * lines * (max_qty + 1) / 2 / skus
        for sku in sku_names:
            steps.append(("restock", (sku, max(1, int(demand * stock_ratio * r.uniform(0.5, 1.5))))))
        if routes:
            shuffled = places[:]
            r.shuffle(shuffled)
            for k in range(routes):
                steps.append(("set_route", (f"route-{k}", shuffled[k::routes + 1])))
        for _ in range(per_round):
            oid = f"o{len(placed) + 1}"
            items = {r.choice(sku_names): r.randint(1, max_qty) for _ in range(r.randint(1, lines))}
            if r.random() < 0.01:
                items = {r.choice(sku_names): capacity + 1}  # too big for any truck
            dest = r.choice(places[: max(1, len(places) * 2 // 3)] if r.random() < 0.7 else places)
            args = (oid, dest, items)
            if express and r.random() < express:
                steps.append(("place_order", args, {"express": True}))
            else:
                steps.append(("place_order", args))
            placed.append(oid)
            if r.random() < 0.01:
                steps.append(("place_order", (r.choice(placed), dest, items)))  # duplicate id
            if r.random() < cancel:
                steps.append(("cancel_order", (r.choice(placed),)))
        steps.append(("dispatch", (capacity,), {} if max_stops is None else {"max_stops": max_stops}))
    return steps


def ops_part1(seed, n):
    """big part 1 run: lots of places and cancels, checking pending_orders now and then"""
    def build():
        r = random.Random(seed)
        steps, ids = [], []
        for i in range(n):
            x = r.random()
            if x < 0.55 or not ids:
                oid = f"o{i}"
                ids.append(oid)
                steps.append(("place_order", (oid, r.choice(DESTS), {f"sku-{r.randint(0, 99)}": r.randint(1, 5)})))
            elif x < 0.85:
                steps.append(("cancel_order", (r.choice(ids),)))
            elif x < 0.95:
                steps.append(("order_status", (r.choice(ids),)))
            elif x < 0.995:
                steps.append(("restock", (f"sku-{r.randint(0, 99)}", r.randint(1, 50))))
            else:
                steps.append(("pending_orders", ()))
        steps.append(("pending_orders", ()))
        return steps
    return build


PART1_TESTS = [
    OpsTest("example from the statement", [
        ("restock", ("bolt", 50), 50),
        ("place_order", ("o1", "Denver", {"bolt": 10, "nut": 4}), True),
        ("place_order", ("o1", "Austin", {"nut": 1}), False),
        ("place_order", ("o2", "Austin", {}), False),
        ("place_order", ("o3", "Austin", {"bolt": 5}), True),
        ("cancel_order", ("o1",), True),
        ("order_status", ("o1",), "cancelled"),
        ("pending_orders", (), ["o3"]),
        ("stock", ("bolt",), 50),
    ], cls="FulfillmentCenter"),
    OpsTest("stock and unknown SKUs", [
        ("stock", ("gear",), 0),
        ("restock", ("gear", 3), 3),
        ("restock", ("gear", 4), 7),
        ("restock", ("cog", 1), 1),
        ("stock", ("gear",), 7),
        ("stock", ("cog",), 1),
    ], cls="FulfillmentCenter"),
    OpsTest("cancelling", [
        ("place_order", ("a", "Reno", {"x": 1}), True),
        ("place_order", ("b", "Reno", {"x": 2}), True),
        ("place_order", ("c", "Reno", {"x": 3}), True),
        ("cancel_order", ("b",), True),
        ("cancel_order", ("b",), False),
        ("cancel_order", ("zzz",), False),
        ("order_status", ("b",), "cancelled"),
        ("order_status", ("zzz",), None),
        ("pending_orders", (), ["a", "c"]),
        ("place_order", ("b", "Reno", {"x": 2}), False),
        ("place_order", ("d", "Reno", {"x": 2}), True),
        ("pending_orders", (), ["a", "c", "d"]),
    ], cls="FulfillmentCenter"),
    OpsTest("rejected orders", [
        ("place_order", ("a", "Reno", {"x": 0}), False),
        ("place_order", ("b", "Reno", {"x": 2, "y": -1}), False),
        ("order_status", ("a",), None),
        ("place_order", ("a", "Reno", {"x": 1}), True),
        ("pending_orders", (), ["a"]),
    ], cls="FulfillmentCenter", hidden=True, description="zero and negative quantities; a rejected id can be used later"),
    OpsTest("placing doesn't take stock", [
        ("restock", ("x", 5), 5),
        ("place_order", ("a", "Reno", {"x": 5}), True),
        ("place_order", ("b", "Reno", {"x": 5}), True),
        ("stock", ("x",), 5),
        ("order_status", ("a",), "pending"),
    ], cls="FulfillmentCenter", hidden=True),
    OpsTest("busy day (5,000 calls)", ops_part1(11, 5_000), cls="FulfillmentCenter", hidden=True),
    OpsTest("huge day (60,000 calls)", ops_part1(12, 60_000), cls="FulfillmentCenter", hidden=True, time_limit=3.0,
            description="mostly placing and cancelling"),
]

PART2_TESTS = [
    script_test("example from the statement", [
        ("restock", ("bolt", 100)),
        ("place_order", ("a", "Denver", {"bolt": 1})),
        ("place_order", ("b", "Denver", {"bolt": 3})),
        ("place_order", ("c", "Denver", {"bolt": 8})),
        ("place_order", ("d", "Denver", {"bolt": 9})),
        ("place_order", ("e", "Denver", {"bolt": 7})),
        ("place_order", ("f", "Austin", {"bolt": 90})),
        ("dispatch", (10,)),
        ("order_status", ("f",)),
        ("stock", ("bolt",)),
    ]),
    script_test("not enough stock", [
        ("restock", ("gear", 10)),
        ("restock", ("cog", 3)),
        ("place_order", ("a", "Reno", {"gear": 6, "cog": 1})),
        ("place_order", ("b", "Reno", {"gear": 6})),
        ("place_order", ("c", "Boise", {"gear": 4, "cog": 2})),
        ("place_order", ("d", "Boise", {"cog": 1})),
        ("dispatch", (20,)),
        ("pending_orders", ()),
        ("restock", ("gear", 2)),
        ("dispatch", (20,)),
        ("order_status", ("b",)),
        ("cancel_order", ("b",)),
    ], description="an order that can't be filled is skipped; later ones still ship; a second dispatch picks it up"),
    script_test("two destinations", [
        ("restock", ("x", 100)),
        *[("place_order", (f"o{i}", "Tulsa" if i % 2 else "Omaha", {"x": q})) for i, q in enumerate([5, 5, 4, 4, 3, 3, 3, 3])],
        ("dispatch", (10,)),
    ]),
    script_test("nothing to ship", [
        ("place_order", ("a", "Reno", {"x": 1})),
        ("dispatch", (10,)),
        ("cancel_order", ("a",)),
        ("dispatch", (10,)),
    ], hidden=True),
    script_test("exact fits", [
        ("restock", ("x", 1000)),
        *[("place_order", (f"o{i}", "Mesa", {"x": q})) for i, q in enumerate([7, 3, 6, 4, 5, 5, 2, 8, 9, 1])],
        ("dispatch", (10,)),
    ], hidden=True, description="50 units that pair up into 5 full trucks"),
    script_test("big orders first", [
        ("restock", ("x", 1000)),
        *[("place_order", (f"o{i}", "Fargo", {"x": q})) for i, q in enumerate([2, 2, 2, 2, 2, 2, 5, 5, 6, 6, 7, 7])],
        ("dispatch", (12,)),
    ], hidden=True),
    script_test("multi-SKU orders", random_script(21, orders=60, dests=4, skus=5, capacity=25, max_qty=8, lines=2),
                hidden=True, slack=0.1),
    script_test("a busy day", lambda: random_script(22, orders=2_000, dests=15, skus=40, capacity=40, max_qty=24, lines=2), hidden=True,
                slack=0.02, time_limit=2.0),
    script_test("a week of dispatches", lambda: random_script(23, orders=6_000, dests=20, skus=60, capacity=60, rounds=7, max_qty=30, lines=2),
                hidden=True, slack=0.02, time_limit=3.0),
]

PART3_TESTS = [
    script_test("example from the statement", [
        ("restock", ("x", 100)),
        ("set_route", ("west", ["Denver", "Boise", "Reno"])),
        ("place_order", ("a", "Denver", {"x": 6})),
        ("place_order", ("b", "Boise", {"x": 4})),
        ("place_order", ("c", "Reno", {"x": 5})),
        ("place_order", ("d", "Reno", {"x": 5})),
        ("place_order", ("e", "Austin", {"x": 3})),
        ("dispatch", (10,)),
    ]),
    script_test("moving stops between routes", [
        ("restock", ("x", 100)),
        ("set_route", ("r1", ["A", "B"])),
        ("set_route", ("r2", ["C", "B"])),
        ("place_order", ("a", "A", {"x": 5})),
        ("place_order", ("b", "B", {"x": 5})),
        ("place_order", ("c", "C", {"x": 5})),
        ("dispatch", (10,)),
        ("set_route", ("r2", ["D"])),
        ("place_order", ("d", "B", {"x": 5})),
        ("place_order", ("e", "C", {"x": 5})),
        ("dispatch", (10,)),
    ], description="B moves from r1 to r2; then r2 is redefined without B or C, so they're on no route"),
    script_test("stop limit", [
        ("restock", ("x", 100)),
        ("set_route", ("loop", ["A", "B", "C", "D"])),
        *[("place_order", (f"o{d}", d, {"x": 2})) for d in "ABCD"],
        ("dispatch", (20,), {"max_stops": 2}),
    ]),
    script_test("routes and limits mixed", random_script(31, orders=80, dests=10, skus=6, capacity=30, routes=3, max_stops=3, max_qty=8,
                                                              lines=2), hidden=True, slack=0.1),
    script_test("unlimited stops", lambda: random_script(32, orders=1_500, dests=20, skus=30, capacity=50, routes=4, max_qty=16, lines=2),
                hidden=True, slack=0.05, time_limit=2.0),
    script_test("regional week", lambda: random_script(33, orders=5_000, dests=20, skus=50, capacity=60, rounds=5, routes=5,
                                                       max_stops=3, max_qty=20, lines=2), hidden=True, slack=0.05, time_limit=3.0),
]

PART4_TESTS = [
    script_test("express gets stock first", [
        ("restock", ("x", 10)),
        ("place_order", ("std", "Reno", {"x": 8})),
        ("place_order", ("exp", "Reno", {"x": 5}), {"express": True}),
        ("dispatch", (20,)),
        ("order_status", ("std",)),
        ("pending_orders", ()),
    ]),
    script_test("separate trucks", [
        ("restock", ("x", 100)),
        ("place_order", ("a", "Reno", {"x": 3})),
        ("place_order", ("b", "Reno", {"x": 3}), {"express": True}),
        ("place_order", ("c", "Reno", {"x": 3})),
        ("dispatch", (10,)),
    ], description="three small orders that would fit on one truck, but b is express"),
    script_test("express everywhere", lambda: random_script(41, orders=3_000, dests=20, skus=40, capacity=50, rounds=3,
                                                            routes=4, max_stops=4, express=0.2, max_qty=16, lines=2), hidden=True, slack=0.05,
                time_limit=3.0),
    script_test("express, small", random_script(42, orders=50, dests=5, skus=4, capacity=20, routes=1, express=0.4, max_qty=6,
                                                     lines=2), hidden=True, slack=0.1),
]

PROBLEM = Problem(
    key="fulfillment",
    title="Fulfillment Center",
    difficulty="medium",
    summary="Track orders and stock, then load shipped orders onto as few trucks as you can.",
    tags=["design", "bin packing", "greedy"],
    minutes=75,
    intro=INTRO,
    parts=[
        Part("Orders and stock", PART1, PART1_TESTS, hints=[
            "You need both fast lookup by id and oldest-first iteration over pending orders. One structure can do both in Python.",
            "Keep cancelled and shipped orders around: their ids can never be reused.",
        ]),
        Part("Dispatch", PART2, PART2_TESTS, hints=[
            "Split dispatch into two functions: choose the orders that ship, then load them onto trucks.",
            "Group shipped orders by destination; each group is loaded independently.",
            "Loading in arrival order wastes space. Try sorting each group by size, biggest first, before placing orders.",
        ]),
        Part("Routes", PART3, PART3_TESTS, hints=[
            "If part 2 grouped by destination, the change is the grouping key: group by route instead.",
            "With a stop limit, an order can go on a truck if it has room and either already stops there or has a stop to spare.",
        ]),
        Part("Express orders", PART4, PART4_TESTS, hints=[
            "Allocation order: a stable sort on 'not express' keeps each group oldest first.",
            "Add express to the grouping key.",
        ]),
    ],
    starter=STARTER,
    reference=REFERENCE,
    discussion=DISCUSSION,
    writeup=WRITEUP,
)
