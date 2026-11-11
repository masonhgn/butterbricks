"""Family 2: Cross-indexed structures. Two structures, each fast at different operations, joined by an index so each
can find things in the other; the invariant is always "the two agree". docs/structures-taxonomy.md has the reasoning."""

from framework.curriculum import Design, Drill, Family, Problem, Step, Technique
from framework.tests import ANY, CostTest, OpsTest, ScenarioTest

PM_LIST_REMOVE = "removing with list.remove(x), which scans and shifts (O(n))"
PM_SCAN = "checking `x in` the list for duplicates, which scans every item (O(n))"
PM_SET_CHOICE = "drawing with random.choice(list(a_set)), which copies every item each time (O(n))"
PM_STALE = "not updating the moved item's position after the swap"
PM_LAST = "removing the item that's already last: deleting its entry before the swap puts it back"
PM_ONE_INDEX = "keeping one position per value when values repeat, so duplicates overwrite each other"


#tests every "add, remove, pick at random" structure shares, given its method names

def _set_steps(add, remove, pick):
    return [(add, ("a",), True), (add, ("b",), True), (add, ("a",), False), (remove, ("a",), True),
            (remove, ("a",), False), (pick, (), "b"), (remove, ("b",), True), (pick, (), None)]


def _moved_item(add, remove, pick):
    """remove from the middle, then remove the item that was moved into the gap"""
    return [(add, ("a",), True), (add, ("b",), True), (add, ("c",), True), (remove, ("a",), True),
            (remove, ("c",), True), (remove, ("b",), True), (pick, (), None), (add, ("c",), True), (pick, (), "c")]


def _last_item(add, remove, pick):
    """remove whatever is last, then add it back"""
    return [(add, ("a",), True), (add, ("b",), True), (remove, ("b",), True), (add, ("b",), True),
            (remove, ("a",), True), (pick, (), "b"), (remove, ("b",), True), (add, ("b",), True), (pick, (), "b")]


def _fair_picks(add, remove, pick, label="picks only current items, each about equally often"):
    def check(ctx):
        obj = ctx.new(ctx.cls)
        for x in "abcdef":
            getattr(obj, add)(x)
        getattr(obj, remove)("a")
        getattr(obj, remove)("d")
        counts = {}
        for _ in range(4_000):
            x = getattr(obj, pick)()
            ctx.check(x in "bcef", f"{pick}() returned {x!r}, which isn't in the structure",
                      ["After adding a to f and removing a and d, only b, c, e and f are left."])
            counts[x] = counts.get(x, 0) + 1
        ctx.check(all(600 <= counts.get(x, 0) <= 1400 for x in "bcef"),
                  f"{pick}() isn't uniform: out of 4,000 picks, {counts}",
                  ["Each of the 4 items should come up about 1,000 times."])
    return ScenarioTest(label, check, hidden=True)


def _set_costs(add, remove, pick):
    """one cost test per operation, so each names the mistake that makes that operation slow"""
    def build(o, n):
        for i in range(n):
            getattr(o, add)(f"x{i}")
    return [
        CostTest(f"{add} stays fast as it grows", build, {add: lambda o, n, i: getattr(o, add)(f"new{i}")},
                 hidden=True, catches=PM_SCAN),
        CostTest(f"{remove} stays fast as it grows", build,
                 {remove: lambda o, n, i: getattr(o, remove)(f"x{n - 1 - i}")}, hidden=True, catches=PM_LIST_REMOVE),
        CostTest(f"{pick} stays fast as it grows", build, {pick: lambda o, n, i: getattr(o, pick)()},
                 hidden=True, catches=PM_SET_CHOICE),
    ]


def _skeleton(cls, add, remove, pick, item="item"):
    return (f"import random\n\n\nclass {cls}:\n    def __init__(self):\n        pass\n\n"
            f"    def {add}(self, {item}: str) -> bool:\n        pass\n\n"
            f"    def {remove}(self, {item}: str) -> bool:\n        pass\n\n"
            f"    def {pick}(self) -> str | None:\n        pass\n")


def _reference(cls, add, remove, pick, item="item"):
    return (f"import random\n\n\nclass {cls}:\n"
            f"    def __init__(self):\n        self.items = []\n        self.pos = {{}}\n\n"
            f"    def {add}(self, {item}):\n        if {item} in self.pos:\n            return False\n"
            f"        self.pos[{item}] = len(self.items)\n        self.items.append({item})\n        return True\n\n"
            f"    def {remove}(self, {item}):\n        if {item} not in self.pos:\n            return False\n"
            f"        i = self.pos[{item}]\n        last = self.items[-1]\n        self.items[i] = last\n"
            f"        self.pos[last] = i\n        self.items.pop()\n        del self.pos[{item}]\n        return True\n\n"
            f"    def {pick}(self):\n        return random.choice(self.items) if self.items else None\n")


def _set_problem(key, role, title, cls, add, remove, pick, statement, item="item", **kw):
    """a problem with the raffle's shape: add and remove return whether they changed anything, pick is random"""
    tests = [
        OpsTest("add, remove and pick", _set_steps(add, remove, pick)),
        OpsTest("removing an item, then the one moved into its place", _moved_item(add, remove, pick),
                hidden=True, catches=PM_STALE),
        OpsTest("removing the last item, then adding it back", _last_item(add, remove, pick),
                hidden=True, catches=PM_LAST),
        _fair_picks(add, remove, pick),
        *_set_costs(add, remove, pick),
    ]
    return Problem(
        key=key, role=role, title=title, kind="class", statement=statement, function=cls,
        signature=f"class {cls}:",
        operations=[(f"{add}({item}: str) -> bool", "O(1)"), (f"{remove}({item}: str) -> bool", "O(1)"),
                    (f"{pick}() -> str | None", "O(1)")],
        design=Design(
            state=[f"items: a list of every {item}, in no particular order",
                   f"pos: dict {item} → its index in items"],
            invariant=f"pos[items[i]] == i for every i, and pos holds exactly the {item}s in items",
            costs={add: "O(1)", remove: "O(1)", pick: "O(1)"},
            checks=[f"A list, so {pick} can choose a random index", f"A dict from {item} to index, so {remove} can "
                    "find it", f"{remove} fills the gap with the last {item} and updates that {item}'s position",
                    f"Removing the {item} that's already last still works"],
        ),
        starter=kw.pop("starter", _skeleton(cls, add, remove, pick, item)),
        reference=_reference(cls, add, remove, pick, item),
        tests=tests, **kw,
    )


position_map = Technique(
    key="position-map",
    name="Position map with swap-remove",
    status="ours",
    aliases=["swap-remove", "swap and pop", "indexed array", "randomized set"],
    sources=[("Rust's Vec::swap_remove", "https://doc.rust-lang.org/std/vec/struct.Vec.html#method.swap_remove")],
    idea="A list can pick a random index in O(1) but can't remove from the middle quickly; a dict finds things in "
         "O(1) but can't pick at random. Keep both: the list of items, and a dict from each item to its position. To "
         "remove from the middle, move the last item into the gap, update its position, and pop the end.",
    invariant="`pos[items[i]] == i` for every position i, and `pos` holds exactly the items in `items`.",
    template="i = pos[x]\nlast = items[-1]\nitems[i] = last      # fill the gap with the last item\n"
             "pos[last] = i        # ...and record where it went\nitems.pop()\ndel pos[x]",
    complexity="O(1) for add, remove and random pick",
    signals=["\"random\" together with \"remove\"", "\"insert, delete and get random in O(1)\"",
             "order doesn't matter, but random access does"],
    near_misses=["Operation costs: a set alone (no random pick) or a list alone (slow removal)",
                 "Linked hash map: when the order of items matters (oldest first), not random picks"],
    mistakes=[PM_LIST_REMOVE, PM_SCAN, PM_SET_CHOICE, PM_STALE, PM_LAST, PM_ONE_INDEX],
    prerequisites=["operation-costs"],
    problems=[
        Problem(
            key="raffle",
            role="example",
            title="Raffle",
            kind="class",
            statement="Tickets go into a raffle and can be withdrawn. `add(ticket)` puts a ticket in (returning "
                      "`False` if it's already there), `remove(ticket)` takes it out (returning `False` if it wasn't "
                      "there), and `draw()` returns a uniformly random ticket (or `None` if there are none). All three "
                      "must be O(1).",
            function="Raffle",
            signature="class Raffle:",
            operations=[("add(ticket: str) -> bool", "O(1)"), ("remove(ticket: str) -> bool", "O(1)"),
                        ("draw() -> str | None", "O(1)")],
            walkthrough=[
                Step("**First idea: a set.** `add`, `remove` and \"is it there?\" are all O(1) on a set.",
                     ask="With only a set, which operation can't be O(1)?",
                     options=["add", "remove", "draw"],
                     answer="draw",
                     why="random.choice needs a sequence it can index into, and a set has no positions. Converting the "
                         "set to a list for every draw copies every ticket: O(n)."),
                Step("**Second idea: a list.** `random.choice(items)` picks a random index in O(1).",
                     ask="With only a list, which operations are now too slow?",
                     options=["only draw", "only remove", "add and remove", "none of them"],
                     answer="add and remove",
                     why="add has to check the ticket isn't already there (`ticket in items` scans), and remove has to "
                         "find the ticket (another scan) and close the gap (every later ticket shifts). Both O(n)."),
                Step("**Keep both: a list for drawing, and a dict for finding.** The list holds every ticket; the "
                     "dict maps each ticket to its index in the list. Finding is now O(1). Removing still leaves a gap "
                     "in the middle of the list.",
                     ask="How can you remove a ticket from the middle of the list in O(1)?",
                     options=["Swap it with the last ticket, then pop the end", "Set its slot to None",
                              "Call items.remove(ticket)", "Build a new list without it"],
                     answer="Swap it with the last ticket, then pop the end",
                     why="Popping the end is O(1), and a raffle doesn't care about order, so the last ticket can fill "
                         "the gap. A None would leave holes that draw() could land on."),
                Step("**The swap moves a ticket, so the dict must follow it.**",
                     ask="Right after the last ticket moves into the gap at index i, what must change in the dict?",
                     options=["Nothing: the dict only matters for the removed ticket",
                              "The moved ticket's entry becomes i", "Every entry after i goes down by one"],
                     answer="The moved ticket's entry becomes i",
                     why="Only one ticket moved, and only its recorded position is now wrong. Nothing else shifted, "
                         "which is the whole point of the swap."),
                Step("**The invariant:** `pos[items[i]] == i` for every i, and the dict holds exactly the tickets in "
                     "the list. Every operation must keep it true. **Now step through the code** on the right: watch "
                     "`self.items` and `self.pos` change together, especially during `remove('A')`."),
            ],
            design=Design(
                state=["items: a list of every ticket, in no particular order",
                       "pos: dict ticket → its index in items"],
                invariant="pos[items[i]] == i for every i, and pos holds exactly the tickets in items",
                costs={"add": "O(1)", "remove": "O(1)", "draw": "O(1)"},
                checks=["A list, so draw can choose a random index", "A dict from ticket to index, so remove can find it",
                        "remove fills the gap with the last ticket and updates that ticket's position",
                        "Removing the ticket that's already last still works"],
            ),
            reference="import random\n"
                      "\n"
                      "\n"
                      "class Raffle:\n"
                      "    def __init__(self):\n"
                      "        self.items = []  # every ticket, in no particular order\n"
                      "        self.pos = {}    # ticket -> its index in items\n"
                      "\n"
                      "    def add(self, ticket):\n"
                      "        if ticket in self.pos:\n"
                      "            return False\n"
                      "        self.pos[ticket] = len(self.items)\n"
                      "        self.items.append(ticket)\n"
                      "        return True\n"
                      "\n"
                      "    def remove(self, ticket):\n"
                      "        if ticket not in self.pos:\n"
                      "            return False\n"
                      "        i = self.pos[ticket]\n"
                      "        last = self.items[-1]\n"
                      "        self.items[i] = last  # move the last ticket into the gap\n"
                      "        self.pos[last] = i    # and record where it went\n"
                      "        self.items.pop()\n"
                      "        del self.pos[ticket]\n"
                      "        return True\n"
                      "\n"
                      "    def draw(self):\n"
                      "        if not self.items:\n"
                      "            return None\n"
                      "        return random.choice(self.items)\n",
            tests=[OpsTest("add, remove, draw", [("add", ("A",), True), ("add", ("A",), False), ("remove", ("A",), True),
                                                ("draw", (), None)])],
            trace_script=[("add", ("A",)), ("add", ("B",)), ("add", ("C",)), ("remove", ("A",))],
            notes={
                "self.items = []": "The list: every ticket, in no particular order.",
                "self.pos = {}": "The dict: where each ticket sits in the list.",
                "if ticket in self.pos": "Already in? One dict lookup, not a scan of the list.",
                "self.pos[ticket] = len(self.items)": "The new ticket will sit at the end: record that index first.",
                "self.items.append(ticket)": "Then put it there. The invariant holds again.",
                "i = self.pos[ticket]": "Find the ticket's index in O(1).",
                "last = self.items[-1]": "The ticket that will fill the gap.",
                "self.items[i] = last": "Move the last ticket into the gap.",
                "self.pos[last] = i": "The moved ticket now sits at i: update its entry. Skip this and the dict lies.",
                "self.items.pop()": "Drop the end, where the moved ticket used to be: O(1).",
                "del self.pos[ticket]": "Forget the removed ticket. Doing this last is what makes removing the last "
                                        "ticket safe.",
            },
            predict={"self.pos[last] = i": "self.pos[last] == i"},
            takeaway="Neither structure could do all three operations; together, joined by the position map, they "
                     "can. The price is the invariant: every operation that moves an item must update its position.",
        ),
        _set_problem(
            "raffle-remove", "completion", "Raffle: the remove", "Raffle", "add", "remove", "draw",
            "The raffle again, with `remove` left to finish. Fill in the two blanks: move the last ticket into the "
            "gap, and record where it went.",
            item="ticket",
            starter="import random\n"
                    "\n"
                    "\n"
                    "class Raffle:\n"
                    "    def __init__(self):\n"
                    "        self.items = []  # every ticket, in no particular order\n"
                    "        self.pos = {}    # ticket -> its index in items\n"
                    "\n"
                    "    def add(self, ticket: str) -> bool:\n"
                    "        if ticket in self.pos:\n"
                    "            return False\n"
                    "        self.pos[ticket] = len(self.items)\n"
                    "        self.items.append(ticket)\n"
                    "        return True\n"
                    "\n"
                    "    def remove(self, ticket: str) -> bool:\n"
                    "        if ticket not in self.pos:\n"
                    "            return False\n"
                    "        i = self.pos[ticket]\n"
                    "        last = self.items[-1]\n"
                    "        ___  # move the last ticket into the gap\n"
                    "        ___  # record where the moved ticket now is\n"
                    "        self.items.pop()\n"
                    "        del self.pos[ticket]\n"
                    "        return True\n"
                    "\n"
                    "    def draw(self) -> str | None:\n"
                    "        if not self.items:\n"
                    "            return None\n"
                    "        return random.choice(self.items)\n",
            hints=["The first blank writes into the list at index i; the second writes into the dict for `last`."],
            takeaway="Two lines, one per structure. The invariant is kept by updating both every time something moves.",
        ),
        _set_problem(
            "online-players", "twin", "Online players", "Lobby", "join", "leave", "random_opponent",
            "A game lobby tracks who's online. `join(player)` and `leave(player)` return whether anything changed, "
            "and `random_opponent()` returns a uniformly random online player (or `None`). All O(1).",
            item="player",
            changes="Only the story: players in a lobby instead of tickets in a raffle.",
            takeaway="Same requirements, same design: a list for random picks, a position map for O(1) removal.",
        ),
        Problem(
            key="marble-bag",
            role="variation",
            title="Bag of marbles",
            kind="class",
            statement="A bag holds marbles, and colors can repeat. `add(color)` puts one marble in, `remove(color)` "
                      "takes out one marble of that color (returning `False` if there's none), and `draw()` returns "
                      "the color of a uniformly random **marble** (so a color with three marbles comes up three times "
                      "as often as a color with one), or `None` if the bag is empty. All O(1).",
            function="MarbleBag",
            signature="class MarbleBag:",
            operations=[("add(color: str) -> None", "O(1)"), ("remove(color: str) -> bool", "O(1)"),
                        ("draw() -> str | None", "O(1)")],
            design=Design(
                state=["items: a list with one entry per marble (its color)",
                       "pos: dict color → the set of indices in items holding that color"],
                invariant="i is in pos[c] exactly when items[i] == c, and colors with no marbles aren't in pos",
                costs={"add": "O(1)", "remove": "O(1)", "draw": "O(1)"},
                checks=["One list entry per marble, so draw is uniform over marbles",
                        "A set of positions per color, since a color can sit in many places",
                        "remove takes any position of the color, swaps the last marble in, and updates the moved "
                        "marble's set (remove the old index, add the new one)",
                        "The case where the removed marble is already last"],
            ),
            starter="import random\n\n\nclass MarbleBag:\n    def __init__(self):\n        pass\n\n"
                    "    def add(self, color: str) -> None:\n        pass\n\n"
                    "    def remove(self, color: str) -> bool:\n        pass\n\n"
                    "    def draw(self) -> str | None:\n        pass\n",
            reference="import random\n"
                      "\n"
                      "\n"
                      "class MarbleBag:\n"
                      "    def __init__(self):\n"
                      "        self.items = []  # one entry per marble: its color\n"
                      "        self.pos = {}    # color -> set of indices in items\n"
                      "\n"
                      "    def add(self, color):\n"
                      "        self.pos.setdefault(color, set()).add(len(self.items))\n"
                      "        self.items.append(color)\n"
                      "\n"
                      "    def remove(self, color):\n"
                      "        if color not in self.pos:\n"
                      "            return False\n"
                      "        i = self.pos[color].pop()\n"
                      "        last_i = len(self.items) - 1\n"
                      "        last = self.items[last_i]\n"
                      "        self.items[i] = last\n"
                      "        self.pos[last].add(i)\n"
                      "        self.pos[last].discard(last_i)\n"
                      "        self.items.pop()\n"
                      "        if not self.pos[color]:\n"
                      "            del self.pos[color]\n"
                      "        return True\n"
                      "\n"
                      "    def draw(self):\n"
                      "        return random.choice(self.items) if self.items else None\n",
            tests=[
                OpsTest("two reds and a blue", [("add", ("red",)), ("add", ("red",)), ("add", ("blue",)),
                                                ("remove", ("red",), True), ("remove", ("blue",), True),
                                                ("draw", (), "red"), ("remove", ("red",), True), ("remove", ("red",), False),
                                                ("draw", (), None)]),
                OpsTest("duplicates don't overwrite each other", [
                    ("add", ("red",)), ("add", ("blue",)), ("add", ("red",)), ("remove", ("red",), True),
                    ("remove", ("red",), True), ("remove", ("red",), False), ("draw", (), "blue")],
                    hidden=True, catches=PM_ONE_INDEX),
                OpsTest("removing the last marble's color", [
                    ("add", ("a",)), ("add", ("b",)), ("remove", ("b",), True), ("add", ("b",)), ("remove", ("a",), True),
                    ("draw", (), "b"), ("remove", ("b",), True), ("draw", (), None)], hidden=True, catches=PM_LAST),
                OpsTest("the moved marble stays findable", [
                    ("add", ("a",)), ("add", ("b",)), ("add", ("c",)), ("add", ("c",)), ("remove", ("a",), True),
                    ("remove", ("c",), True), ("remove", ("c",), True), ("remove", ("b",), True), ("draw", (), None)],
                    hidden=True, catches=PM_STALE),
                ScenarioTest("draws are uniform over marbles, not colors", lambda ctx: _weighted(ctx), hidden=True),
                CostTest("add, remove and draw stay fast as the bag fills",
                         build=lambda o, n: [o.add(f"c{i % 50}") for i in range(n)],
                         ops={"add": lambda o, n, i: o.add(f"c{i % 50}"),
                              "remove": lambda o, n, i: o.remove(f"c{i % 50}"),
                              "draw": lambda o, n, i: o.draw()},
                         hidden=True, catches=PM_LIST_REMOVE),
            ],
            changes="Colors can **repeat**, and draws are uniform over marbles: one position per value isn't enough "
                    "any more.",
            hints=["A color can sit at many indices. What should pos map a color to?",
                   "When the last marble moves into the gap, its color's set loses the old index and gains the new one."],
            takeaway="Same list, same swap-remove. Only the index changed: with duplicates, each value maps to a set "
                     "of positions instead of one.",
        ),
        Problem(
            key="shuffle-bag",
            role="stretch",
            title="Shuffle bag",
            kind="class",
            statement="A shuffle bag draws every item once before repeating any. `add(item)` and `remove(item)` "
                      "return whether anything changed (a newly added item hasn't been drawn yet). `draw()` returns a "
                      "uniformly random item **not drawn since the last refill**, or `None` once all have been drawn. "
                      "`refill()` makes every item drawable again. All four O(1), including `refill`.",
            function="ShuffleBag",
            signature="class ShuffleBag:",
            operations=[("add(item: str) -> bool", "O(1)"), ("remove(item: str) -> bool", "O(1)"),
                        ("draw() -> str | None", "O(1)"), ("refill() -> None", "O(1)")],
            design=Design(
                state=["items: one list, split in two: items[:live] not yet drawn, items[live:] drawn",
                       "pos: dict item → its index in items", "live: how many items haven't been drawn"],
                invariant="pos[items[i]] == i for every i; items[:live] are exactly the items not yet drawn",
                costs={"add": "O(1)", "remove": "O(1)", "draw": "O(1)", "refill": "O(1)"},
                checks=["One list with a boundary, instead of two lists", "draw swaps the drawn item to the boundary "
                        "and moves the boundary", "refill just moves the boundary to the end",
                        "A swap helper that updates pos for both items keeps every operation honest"],
            ),
            starter="import random\n\n\nclass ShuffleBag:\n    def __init__(self):\n        pass\n\n"
                    "    def add(self, item: str) -> bool:\n        pass\n\n"
                    "    def remove(self, item: str) -> bool:\n        pass\n\n"
                    "    def draw(self) -> str | None:\n        pass\n\n"
                    "    def refill(self) -> None:\n        pass\n",
            reference="import random\n"
                      "\n"
                      "\n"
                      "class ShuffleBag:\n"
                      "    def __init__(self):\n"
                      "        self.items = []  # items[:live] not drawn yet, items[live:] drawn\n"
                      "        self.pos = {}    # item -> its index in items\n"
                      "        self.live = 0\n"
                      "\n"
                      "    def _swap(self, i, j):\n"
                      "        a, b = self.items[i], self.items[j]\n"
                      "        self.items[i], self.items[j] = b, a\n"
                      "        self.pos[a], self.pos[b] = j, i\n"
                      "\n"
                      "    def add(self, item):\n"
                      "        if item in self.pos:\n"
                      "            return False\n"
                      "        self.pos[item] = len(self.items)\n"
                      "        self.items.append(item)\n"
                      "        self._swap(self.pos[item], self.live)  # into the not-drawn part\n"
                      "        self.live += 1\n"
                      "        return True\n"
                      "\n"
                      "    def remove(self, item):\n"
                      "        if item not in self.pos:\n"
                      "            return False\n"
                      "        i = self.pos[item]\n"
                      "        if i < self.live:  # not drawn yet: first move it to the boundary\n"
                      "            self.live -= 1\n"
                      "            self._swap(i, self.live)\n"
                      "            i = self.live\n"
                      "        self._swap(i, len(self.items) - 1)  # then to the very end\n"
                      "        self.items.pop()\n"
                      "        del self.pos[item]\n"
                      "        return True\n"
                      "\n"
                      "    def draw(self):\n"
                      "        if self.live == 0:\n"
                      "            return None\n"
                      "        i = random.randrange(self.live)\n"
                      "        item = self.items[i]\n"
                      "        self.live -= 1\n"
                      "        self._swap(i, self.live)  # into the drawn part\n"
                      "        return item\n"
                      "\n"
                      "    def refill(self):\n"
                      "        self.live = len(self.items)\n",
            tests=[
                OpsTest("add, draw until empty, refill", [
                    ("add", ("a",), True), ("add", ("a",), False), ("draw", (), "a"), ("draw", (), None),
                    ("refill", ()), ("draw", (), "a"), ("remove", ("a",), True), ("refill", ()), ("draw", (), None)]),
                ScenarioTest("every item once per round, then None", lambda ctx: _rounds(ctx), hidden=True),
                ScenarioTest("removing drawn and undrawn items mid-round", lambda ctx: _mid_round(ctx), hidden=True,
                             catches=PM_STALE),
                CostTest("add, remove, draw and refill stay fast",
                         build=lambda o, n: [o.add(f"x{i}") for i in range(n)],
                         ops={"add": lambda o, n, i: o.add(f"new{i}"),
                              "remove": lambda o, n, i: o.remove(f"x{n - 1 - i}"),
                              "draw": lambda o, n, i: o.draw(),
                              "refill": lambda o, n, i: o.refill()},
                         hidden=True, catches="refill rebuilding or reshuffling the list, which is O(n)"),
            ],
            hints=["Keep one list and a boundary index: everything before it is still drawable.",
                   "A helper that swaps two positions and fixes both entries in pos makes every method short.",
                   "refill doesn't have to move anything."],
            takeaway="The position map made a second trick possible: a boundary inside the list. Moving items across "
                     "the boundary is a swap, and refill is one assignment.",
        ),
        _set_problem(
            "server-pool", "review", "Server pool", "ServerPool", "add_server", "remove_server", "pick",
            "Requests go to a uniformly random healthy server. `add_server(name)` and `remove_server(name)` return "
            "whether anything changed; `pick()` returns a random server or `None`. All O(1).", item="name"),
        _set_problem(
            "featured-products", "review", "Featured products", "Featured", "feature", "unfeature", "spotlight",
            "The homepage spotlights a random featured product. `feature(product)` and `unfeature(product)` return "
            "whether anything changed; `spotlight()` returns a random featured product or `None`. All O(1).",
            item="product"),
        Problem(
            key="units-in-stock",
            role="review",
            title="Units in stock",
            kind="class",
            statement="A warehouse picks a random **unit** to audit. `receive(product)` adds one unit, `ship(product)` "
                      "removes one unit (`False` if there are none), and `audit()` returns the product of a uniformly "
                      "random unit, or `None`. All O(1).",
            function="Stock",
            signature="class Stock:",
            operations=[("receive(product: str) -> None", "O(1)"), ("ship(product: str) -> bool", "O(1)"),
                        ("audit() -> str | None", "O(1)")],
            starter="import random\n\n\nclass Stock:\n    def __init__(self):\n        pass\n\n"
                    "    def receive(self, product: str) -> None:\n        pass\n\n"
                    "    def ship(self, product: str) -> bool:\n        pass\n\n"
                    "    def audit(self) -> str | None:\n        pass\n",
            reference="import random\n\n\nclass Stock:\n    def __init__(self):\n        self.items = []\n"
                      "        self.pos = {}\n\n    def receive(self, product):\n"
                      "        self.pos.setdefault(product, set()).add(len(self.items))\n        self.items.append(product)\n\n"
                      "    def ship(self, product):\n        if product not in self.pos:\n            return False\n"
                      "        i = self.pos[product].pop()\n        last_i = len(self.items) - 1\n"
                      "        last = self.items[last_i]\n        self.items[i] = last\n        self.pos[last].add(i)\n"
                      "        self.pos[last].discard(last_i)\n        self.items.pop()\n"
                      "        if not self.pos[product]:\n            del self.pos[product]\n        return True\n\n"
                      "    def audit(self):\n        return random.choice(self.items) if self.items else None\n",
            tests=[OpsTest("units come and go", [("receive", ("bolt",)), ("receive", ("bolt",)), ("receive", ("nut",)),
                                                 ("ship", ("bolt",), True), ("ship", ("nut",), True),
                                                 ("audit", (), "bolt"), ("ship", ("bolt",), True),
                                                 ("ship", ("bolt",), False), ("audit", (), None)]),
                   OpsTest("duplicates don't overwrite", [("receive", ("a",)), ("receive", ("b",)), ("receive", ("a",)),
                                                          ("ship", ("a",), True), ("ship", ("a",), True),
                                                          ("ship", ("a",), False), ("audit", (), "b")],
                           hidden=True, catches=PM_ONE_INDEX)],
        ),
    ],
    drills=[
        Drill(
            key="pm-drill-matchmaking",
            statement="A game server keeps a pool of available players. Players join and leave constantly, and "
                      "matchmaking picks a uniformly random available player. Everything must be O(1).",
            question="Which technique fits these operations?",
            choices=["Operation costs: a deque, fast at both ends", "Operation costs: a set alone",
                     "Linked hash map (coming later)"],
            signal="\"Random\" together with \"leave\": random access and removal by value, both O(1)",
            wrong_signals=["\"Join and leave constantly\": add and take at both ends",
                           "\"Available players\": membership is the only question",
                           "\"Matchmaking\": players are picked oldest first"],
            why="A set can't pick at random and a list can't remove by value quickly; a list plus a position map, with "
                "swap-remove, does both.",
        ),
        Drill(
            key="pm-drill-classic",
            statement="Support insert(x), remove(x) and get_random() on a collection of distinct values, each in O(1) "
                      "average time.",
            question="Which technique fits these operations?",
            choices=["Operation costs: a set alone", "Operation costs: a list alone", "Linked hash map (coming later)"],
            signal="get_random() together with remove(x): a list to index into, and positions to remove by",
            wrong_signals=["\"Distinct values\": a set handles every operation",
                           "insert(x): values go in at the end of a list, so a list is enough",
                           "\"Average time\": hashing alone gives O(1) for all three"],
            why="This is the classic statement of the technique: the list gives get_random, the position map makes "
                "remove O(1).",
        ),
        Drill(
            key="pm-drill-coupons",
            statement="A promotion hands out coupon codes: each request gives away a random still-active code and "
                      "deactivates it, and new codes are added throughout the day.",
            question="Which technique fits these operations?",
            choices=["Operation costs: a deque, oldest code first", "Operation costs: a set alone",
                     "Linked hash map (coming later)"],
            signal="\"A random still-active code\" that then leaves: random pick plus removal",
            wrong_signals=["\"Throughout the day\": codes are given out in the order they were added",
                           "\"Still-active\": membership is all that matters",
                           "\"Each request\": the most recent code goes first"],
            why="Pick at random, then remove what was picked: a list for the pick, swap-remove with a position map "
                "for the removal.",
        ),
    ],
)


def _weighted(ctx):
    bag = ctx.new(ctx.cls)
    for color in ["red", "red", "red", "blue"]:
        bag.add(color)
    reds = sum(bag.draw() == "red" for _ in range(4_000))
    ctx.check(2_700 <= reds <= 3_300, f"red came up {reds:,} times in 4,000 draws; about 3,000 was expected",
              ["Three of the four marbles are red, so red should come up about 3 times in 4."])


def _rounds(ctx):
    bag = ctx.new(ctx.cls)
    items = [f"s{i}" for i in range(20)]
    for x in items:
        bag.add(x)
    for round_ in range(3):
        got = [bag.draw() for _ in range(20)]
        ctx.check(sorted(got) == sorted(items), f"round {round_ + 1} didn't draw every item exactly once",
                  [f"drew: {got}"])
        ctx.check(bag.draw() is None, f"after drawing all 20, draw() should return None (round {round_ + 1})")
        bag.refill()


def _mid_round(ctx):
    bag = ctx.new(ctx.cls)
    for x in "abcdefgh":
        bag.add(x)
    first = [bag.draw() for _ in range(3)]
    undrawn = [x for x in "abcdefgh" if x not in first]
    ctx.check(bag.remove(first[0]), "removing a drawn item should return True")
    ctx.check(bag.remove(undrawn[0]), "removing an undrawn item should return True")
    ctx.check(bag.add("z"), "adding a new item should return True")
    rest = [bag.draw() for _ in range(len(undrawn))]
    ctx.check(sorted(rest) == sorted(undrawn[1:] + ["z"]), "the rest of the round drew the wrong items",
              [f"expected (any order): {sorted(undrawn[1:] + ['z'])}", f"drew: {rest}"])
    ctx.check(bag.draw() is None, "once the round is done, draw() should return None")
    bag.refill()
    again = sorted(bag.draw() for _ in range(7))
    expected = sorted([x for x in "abcdefgh" if x not in (first[0], undrawn[0])] + ["z"])
    ctx.check(again == expected, "after refill, every remaining item should be drawable once",
              [f"expected {expected}", f"drew {again}"])


FAMILY = Family(
    key="cross-indexed",
    name="Cross-indexed structures",
    status="ours",
    aliases=["composite structures", "two structures joined by an index"],
    idea="Two structures, each fast at different operations, joined by an index so each can find things in the "
         "other. The invariant is always: the two agree.",
    variants=[position_map],
    planned=["Linked hash map", "Frequency buckets"],
)
