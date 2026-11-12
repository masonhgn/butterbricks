"""Family 1: Building blocks. Every structure is fast at some operations and slow at others; this family is the
cheat sheet everything else builds on. docs/structures-taxonomy.md has the reasoning behind names and sequences."""

from framework.curriculum import Design, Drill, Family, Problem, Step, Technique
from framework.tests import CostTest, OpsTest

OC_POP_FRONT = "using list.pop(0) or list.insert(0, x) for a queue: every other item shifts (O(n))"
OC_SCAN = "checking `x in` a list or deque, which scans every item (O(n))"
OC_STALE = "leaving a name whose count reached 0 in the dict, so `name in counts` still says yes"


def _queue_costs(cls_join, cls_take, cls_size, catches):
    """the cost test every queue problem shares: join and take stay O(1) as the line grows"""
    return CostTest(
        "every operation stays fast as the line grows",
        build=lambda o, n: [getattr(o, cls_join)(f"p{i}") for i in range(n)],
        ops={
            cls_join: lambda o, n, i: getattr(o, cls_join)(f"new{i}"),
            cls_take: lambda o, n, i: getattr(o, cls_take)(),
            cls_size: lambda o, n, i: getattr(o, cls_size)(),
        },
        # list.pop(0) shifts with one fast memory copy, so it only shows as slow at larger sizes
        sizes=(10_000, 100_000), calls=2_000, hidden=True, catches=catches,
    )


def _line_steps(join, take, size):
    return [(join, ("ana",)), (join, ("bo",)), (take, (), "ana"), (size, (), 1), (join, ("cy",)),
            (take, (), "bo"), (take, (), "cy"), (take, (), None), (size, (), 0)]


operation_costs = Technique(
    key="operation-costs",
    name="Operation costs",
    status="ours",
    aliases=["time complexity of built-ins", "big-O of Python operations"],
    sources=[("Python wiki: TimeComplexity", "https://wiki.python.org/moin/TimeComplexity")],
    idea="Every structure is fast at some operations and slow at others. A list is fast at its end and slow at its "
         "front; a deque is fast at both ends; a set or dict answers \"is x here?\" in O(1), where a list has to scan. "
         "Designing a structure starts with knowing these costs.",
    invariant="(for a queue on a deque) the deque holds the waiting items, oldest at the left.",
    template="from collections import deque\n\nline = deque()\nline.append(x)      # join at the back: O(1)\n"
             "first = line.popleft()  # serve the front: O(1)",
    complexity="O(1) per operation, with the right structure",
    signals=["\"in the order they arrived\" (a queue: both ends)", "\"the most recent\" (a stack: one end)",
             "\"is it already ...?\" (membership: a set or dict)"],
    near_misses=["A list with pop(0): correct, but O(n) per serve", "A set: fast membership, but no order"],
    mistakes=[OC_POP_FRONT, OC_SCAN, OC_STALE],
    prerequisites=[],
    reference_table=[
        ("list: append(x), pop(), lst[i], len(lst)", "O(1)", "the end, or a known position"),
        ("list: pop(0), insert(0, x)", "O(n)", "every other item shifts"),
        ("list: x in lst, lst.index(x), lst.remove(x)", "O(n)", "scans from the start"),
        ("deque: append, appendleft, pop, popleft", "O(1)", "fast at both ends"),
        ("deque: x in d, d[i] in the middle", "O(n)", "a deque doesn't fix scanning"),
        ("set: add, discard, x in s", "O(1) on average", "hashing; no order, no random pick"),
        ("dict: d[key], key in d, del d[key]", "O(1) on average", "hashing; keeps insertion order"),
        ("random.choice(seq)", "O(1)", "needs an indexable sequence; a set won't do"),
        ("sorted(lst), lst.sort()", "O(n log n)", ""),
        ("heapq.heappush, heapq.heappop", "O(log n)", "always the smallest first"),
    ],
    problems=[
        Problem(
            key="ticket-line",
            role="example",
            title="Ticket line",
            kind="class",
            statement="People line up for tickets. `join(name)` adds someone to the back, `serve()` removes and "
                      "returns whoever is at the front (or `None` if nobody's waiting), and `waiting()` says how "
                      "many are in line. Each must be O(1).",
            function="TicketLine",
            signature="class TicketLine:",
            operations=[("join(name: str) -> None", "O(1)"), ("serve() -> str | None", "O(1)"),
                        ("waiting() -> int", "O(1)")],
            walkthrough=[
                Step("**Start with the obvious design: a Python list.** `join` appends to the end, `serve` takes "
                     "from the front with `pop(0)`, and `waiting` is `len`.",
                     ask="Which operation is slow with a list?",
                     why="**serve, because of `pop(0)`.** Removing the first item shifts every other item one place left: O(n). Appending at the end "
                         "and asking the length are O(1)."),
                Step("**So we need a structure that's fast at both ends.** Python's `collections.deque` (a "
                     "double-ended queue) adds and removes at either end in O(1).",
                     ask="Which deque method takes from the front of the line?",
                     why="**`popleft()`.** `pop()` takes from the right, the back of the line. remove(name) searches by value: O(n)."),
                Step("**The invariant:** the deque holds exactly the people waiting, oldest at the left. `join` keeps "
                     "it true by adding on the right; `serve` by removing on the left. **Now step through the code** "
                     "on the right, and watch `self.line` change."),
            ],
            design=Design(
                state=["line: a deque of names, oldest at the left"],
                invariant="line holds exactly the people waiting, in the order they joined",
                costs={"join": "O(1)", "serve": "O(1)", "waiting": "O(1)"},
                checks=["A structure that's fast at the front, not just the end", "No pop(0) or insert(0, ...)"],
            ),
            reference="from collections import deque\n"
                      "\n"
                      "\n"
                      "class TicketLine:\n"
                      "    def __init__(self):\n"
                      "        self.line = deque()\n"
                      "\n"
                      "    def join(self, name):\n"
                      "        self.line.append(name)\n"
                      "\n"
                      "    def serve(self):\n"
                      "        if not self.line:\n"
                      "            return None\n"
                      "        return self.line.popleft()\n"
                      "\n"
                      "    def waiting(self):\n"
                      "        return len(self.line)\n",
            tests=[OpsTest("ana, then bo", _line_steps("join", "serve", "waiting"))],
            trace_script=[("join", ("ana",)), ("join", ("bo",)), ("join", ("cy",)), ("serve", ()), ("waiting", ())],
            notes={
                "self.line = deque()": "An empty line.",
                "self.line.append(name)": "Join at the back: O(1).",
                "if not self.line": "Is anyone waiting?",
                "return self.line.popleft()": "Serve the front: O(1), and nobody has to shift.",
                "return len(self.line)": "A deque knows its length: O(1).",
            },
            takeaway="Knowing which end of which structure is cheap is the whole design here. A list is fine at its "
                     "end; a queue needs a deque.",
        ),
        Problem(
            key="print-queue",
            role="completion",
            title="Print queue",
            kind="class",
            statement="Jobs print in the order they were submitted. Fill in the two blanks so every operation is O(1).",
            function="PrintQueue",
            signature="class PrintQueue:",
            operations=[("submit(job: str) -> None", "O(1)"), ("next_job() -> str | None", "O(1)"),
                        ("pending() -> int", "O(1)")],
            design=Design(
                state=["jobs: a deque of job names, oldest at the left"],
                invariant="jobs holds the jobs not yet printed, in the order they were submitted",
                costs={"submit": "O(1)", "next_job": "O(1)", "pending": "O(1)"},
                checks=["Submit adds on the right", "Next takes from the left with popleft"],
            ),
            starter="from collections import deque\n"
                    "\n"
                    "\n"
                    "class PrintQueue:\n"
                    "    def __init__(self):\n"
                    "        self.jobs = deque()\n"
                    "\n"
                    "    def submit(self, job: str) -> None:\n"
                    "        ___  # add the job at the back\n"
                    "\n"
                    "    def next_job(self) -> str | None:\n"
                    "        if not self.jobs:\n"
                    "            return None\n"
                    "        return ___  # take the job at the front, in O(1)\n"
                    "\n"
                    "    def pending(self) -> int:\n"
                    "        return len(self.jobs)\n",
            reference="from collections import deque\n"
                      "\n"
                      "\n"
                      "class PrintQueue:\n"
                      "    def __init__(self):\n"
                      "        self.jobs = deque()\n"
                      "\n"
                      "    def submit(self, job):\n"
                      "        self.jobs.append(job)\n"
                      "\n"
                      "    def next_job(self):\n"
                      "        if not self.jobs:\n"
                      "            return None\n"
                      "        return self.jobs.popleft()\n"
                      "\n"
                      "    def pending(self):\n"
                      "        return len(self.jobs)\n",
            tests=[
                OpsTest("first in, first out", _line_steps("submit", "next_job", "pending")),
                _queue_costs("submit", "next_job", "pending", OC_POP_FRONT),
            ],
            hints=["The deque methods mirror the example: one adds on the right, the other removes on the left."],
            takeaway="The same structure as the ticket line, with different names.",
        ),
        Problem(
            key="support-tickets",
            role="twin",
            title="Support tickets",
            kind="class",
            statement="Support tickets are handled first come, first served. `open(ticket)` files one, `take()` "
                      "returns the oldest unhandled ticket (or `None`), and `open_count()` says how many are waiting.",
            function="SupportTickets",
            signature="class SupportTickets:",
            operations=[("open(ticket: str) -> None", "O(1)"), ("take() -> str | None", "O(1)"),
                        ("open_count() -> int", "O(1)")],
            design=Design(
                state=["tickets: a deque, oldest at the left"],
                invariant="tickets holds the unhandled tickets, in the order they were filed",
                costs={"open": "O(1)", "take": "O(1)", "open_count": "O(1)"},
                checks=["A deque, not a list with pop(0)"],
            ),
            starter="class SupportTickets:\n"
                    "    def __init__(self):\n"
                    "        pass\n"
                    "\n"
                    "    def open(self, ticket: str) -> None:\n"
                    "        pass\n"
                    "\n"
                    "    def take(self) -> str | None:\n"
                    "        pass\n"
                    "\n"
                    "    def open_count(self) -> int:\n"
                    "        pass\n",
            reference="from collections import deque\n"
                      "\n"
                      "\n"
                      "class SupportTickets:\n"
                      "    def __init__(self):\n"
                      "        self.tickets = deque()\n"
                      "\n"
                      "    def open(self, ticket):\n"
                      "        self.tickets.append(ticket)\n"
                      "\n"
                      "    def take(self):\n"
                      "        return self.tickets.popleft() if self.tickets else None\n"
                      "\n"
                      "    def open_count(self):\n"
                      "        return len(self.tickets)\n",
            tests=[
                OpsTest("oldest first", _line_steps("open", "take", "open_count")),
                _queue_costs("open", "take", "open_count", OC_POP_FRONT),
            ],
            changes="Only the story: support tickets instead of print jobs.",
            takeaway="Same requirements, same structure: a queue is a deque.",
        ),
        Problem(
            key="undo-history",
            role="variation",
            title="Undo history",
            kind="class",
            statement="An editor records actions. `do(action)` records one, `undo()` removes and returns the **most "
                      "recent** action (or `None`), and `depth()` says how many can be undone.",
            function="UndoHistory",
            signature="class UndoHistory:",
            operations=[("do(action: str) -> None", "O(1)"), ("undo() -> str | None", "O(1)"),
                        ("depth() -> int", "O(1)")],
            design=Design(
                state=["actions: a list, most recent at the end"],
                invariant="actions holds what can be undone, oldest first",
                costs={"do": "O(1)", "undo": "O(1)", "depth": "O(1)"},
                checks=["Taking from the end you add to: a plain list's append and pop are O(1)",
                        "A deque works too, but isn't needed"],
            ),
            starter="class UndoHistory:\n"
                    "    def __init__(self):\n"
                    "        pass\n"
                    "\n"
                    "    def do(self, action: str) -> None:\n"
                    "        pass\n"
                    "\n"
                    "    def undo(self) -> str | None:\n"
                    "        pass\n"
                    "\n"
                    "    def depth(self) -> int:\n"
                    "        pass\n",
            reference="class UndoHistory:\n"
                      "    def __init__(self):\n"
                      "        self.actions = []\n"
                      "\n"
                      "    def do(self, action):\n"
                      "        self.actions.append(action)\n"
                      "\n"
                      "    def undo(self):\n"
                      "        return self.actions.pop() if self.actions else None\n"
                      "\n"
                      "    def depth(self):\n"
                      "        return len(self.actions)\n",
            tests=[
                OpsTest("most recent first", [("do", ("type",)), ("do", ("bold",)), ("undo", (), "bold"),
                                              ("depth", (), 1), ("do", ("paste",)), ("undo", (), "paste"),
                                              ("undo", (), "type"), ("undo", (), None), ("depth", (), 0)]),
                _queue_costs("do", "undo", "depth", OC_POP_FRONT),
            ],
            changes="Take the **most recent** item instead of the oldest: which end you take from changes which "
                    "structure is cheap.",
            takeaway="Taking from the end you add to is a stack, and a plain list's append and pop are O(1). Only "
                     "taking from the other end needed a deque.",
        ),
        Problem(
            key="recent-visitors",
            role="stretch",
            title="Recent visitors",
            kind="class",
            statement="A site remembers its last `k` visits. `visit(name)` records a visit (the oldest visit drops out "
                      "once there are more than `k`), and `visited_recently(name)` says whether `name` is among the "
                      "last `k` visits. Both O(1), however large `k` is.",
            function="RecentVisitors",
            signature="class RecentVisitors:",
            operations=[("RecentVisitors(k: int)", ""), ("visit(name: str) -> None", "O(1)"),
                        ("visited_recently(name: str) -> bool", "O(1)")],
            design=Design(
                state=["visits: a deque of the last k names, oldest at the left",
                       "counts: dict name → how many times it appears in visits"],
                invariant="counts[name] is the number of times name appears in visits, and names with 0 aren't in "
                          "counts",
                costs={"visit": "O(1)", "visited_recently": "O(1)"},
                checks=["The deque alone answers the question, but only by scanning",
                        "A count per name answers it in O(1)",
                        "When a visit drops out, its count goes down, and a 0 count is removed"],
            ),
            starter="class RecentVisitors:\n"
                    "    def __init__(self, k: int):\n"
                    "        pass\n"
                    "\n"
                    "    def visit(self, name: str) -> None:\n"
                    "        pass\n"
                    "\n"
                    "    def visited_recently(self, name: str) -> bool:\n"
                    "        pass\n",
            reference="from collections import deque\n"
                      "\n"
                      "\n"
                      "class RecentVisitors:\n"
                      "    def __init__(self, k):\n"
                      "        self.k = k\n"
                      "        self.visits = deque()\n"
                      "        self.counts = {}\n"
                      "\n"
                      "    def visit(self, name):\n"
                      "        self.visits.append(name)\n"
                      "        self.counts[name] = self.counts.get(name, 0) + 1\n"
                      "        if len(self.visits) > self.k:\n"
                      "            old = self.visits.popleft()\n"
                      "            self.counts[old] -= 1\n"
                      "            if self.counts[old] == 0:\n"
                      "                del self.counts[old]\n"
                      "\n"
                      "    def visited_recently(self, name):\n"
                      "        return name in self.counts\n",
            tests=[
                OpsTest("ana drops out after three newer visits", [
                    ("visit", ("ana",)), ("visit", ("bo",)), ("visited_recently", ("ana",), True),
                    ("visit", ("cy",)), ("visit", ("bo",)), ("visited_recently", ("ana",), False),
                    ("visited_recently", ("bo",), True)], args=(3,)),
                OpsTest("a name that left the window", [
                    ("visit", ("ana",)), ("visit", ("bo",)), ("visit", ("cy",)), ("visited_recently", ("ana",), False),
                    ("visited_recently", ("cy",), True)], args=(2,), hidden=True, catches=OC_STALE),
                OpsTest("visiting twice, then once dropping out", [
                    ("visit", ("ana",)), ("visit", ("ana",)), ("visit", ("bo",)), ("visited_recently", ("ana",), True),
                    ("visit", ("cy",)), ("visited_recently", ("ana",), False)], args=(2,), hidden=True),
                CostTest("visited_recently stays fast as the window grows",
                         build=lambda o, n: [o.visit(f"p{i}") for i in range(n)],
                         ops={"visit": lambda o, n, i: o.visit(f"new{i}"),
                              "visited_recently": lambda o, n, i: o.visited_recently("nobody")},
                         args=(10**9,), hidden=True, catches=OC_SCAN),
            ],
            hints=["The deque says who's in the window, but asking it \"is ana here?\" scans it.",
                   "Keep a count per name next to it, and keep the two in step whenever a visit enters or leaves."],
            takeaway="Two structures, each answering what it's fast at: the deque knows the order of visits, the dict "
                     "answers \"is this name here?\". Keeping them in step is the invariant. That's the idea the next "
                     "family is built on.",
        ),
        Problem(
            key="checkout-line",
            role="review",
            title="Checkout line",
            kind="class",
            statement="Shoppers queue at a checkout: `arrive(name)`, `next()` returns the next shopper or `None`, "
                      "`length()` is how many are waiting.",
            function="Checkout",
            signature="class Checkout:",
            operations=[("arrive(name: str) -> None", "O(1)"), ("next() -> str | None", "O(1)"),
                        ("length() -> int", "O(1)")],
            starter="class Checkout:\n    def __init__(self):\n        pass\n\n    def arrive(self, name: str) -> None:\n"
                    "        pass\n\n    def next(self) -> str | None:\n        pass\n\n    def length(self) -> int:\n"
                    "        pass\n",
            reference="from collections import deque\n\n\nclass Checkout:\n    def __init__(self):\n"
                      "        self.q = deque()\n\n    def arrive(self, name):\n        self.q.append(name)\n\n"
                      "    def next(self):\n        return self.q.popleft() if self.q else None\n\n"
                      "    def length(self):\n        return len(self.q)\n",
            tests=[OpsTest("in order", _line_steps("arrive", "next", "length")),
                   _queue_costs("arrive", "next", "length", OC_POP_FRONT)],
        ),
        Problem(
            key="browser-back",
            role="review",
            title="Browser back button",
            kind="class",
            statement="`visit(page)` opens a page, `back()` returns to the previous one by removing and returning the "
                      "current page (or `None` if there's no history), `history()` counts pages you can go back "
                      "through.",
            function="BackButton",
            signature="class BackButton:",
            operations=[("visit(page: str) -> None", "O(1)"), ("back() -> str | None", "O(1)"),
                        ("history() -> int", "O(1)")],
            starter="class BackButton:\n    def __init__(self):\n        pass\n\n    def visit(self, page: str) -> None:\n"
                    "        pass\n\n    def back(self) -> str | None:\n        pass\n\n    def history(self) -> int:\n"
                    "        pass\n",
            reference="class BackButton:\n    def __init__(self):\n        self.pages = []\n\n    def visit(self, page):\n"
                      "        self.pages.append(page)\n\n    def back(self):\n"
                      "        return self.pages.pop() if self.pages else None\n\n    def history(self):\n"
                      "        return len(self.pages)\n",
            tests=[OpsTest("most recent first", [("visit", ("a",)), ("visit", ("b",)), ("back", (), "b"),
                                                 ("history", (), 1), ("back", (), "a"), ("back", (), None)]),
                   _queue_costs("visit", "back", "history", OC_POP_FRONT)],
        ),
        Problem(
            key="elevator-requests",
            role="review",
            title="Elevator requests",
            kind="class",
            statement="Floor requests are handled in the order they were made: `request(floor)`, `next_floor()` "
                      "returns the oldest request or `None`, `queued()` counts them.",
            function="Elevator",
            signature="class Elevator:",
            operations=[("request(floor: int) -> None", "O(1)"), ("next_floor() -> int | None", "O(1)"),
                        ("queued() -> int", "O(1)")],
            starter="class Elevator:\n    def __init__(self):\n        pass\n\n    def request(self, floor: int) -> None:\n"
                    "        pass\n\n    def next_floor(self) -> int | None:\n        pass\n\n    def queued(self) -> int:\n"
                    "        pass\n",
            reference="from collections import deque\n\n\nclass Elevator:\n    def __init__(self):\n"
                      "        self.floors = deque()\n\n    def request(self, floor):\n        self.floors.append(floor)\n\n"
                      "    def next_floor(self):\n        return self.floors.popleft() if self.floors else None\n\n"
                      "    def queued(self):\n        return len(self.floors)\n",
            tests=[OpsTest("oldest request first", [("request", (5,)), ("request", (2,)), ("next_floor", (), 5),
                                                    ("queued", (), 1), ("next_floor", (), 2), ("next_floor", (), None)]),
                   _queue_costs("request", "next_floor", "queued", OC_POP_FRONT)],
        ),
    ],
    drills=[
        Drill(
            key="oc-drill-queue",
            statement="Customers are served in the order they arrive, and people join the line all day.",
            question="Which structure makes both operations O(1)?",
            answer="collections.deque: append, popleft",
            choices=["A list: append, pop(0)", "A list: append, pop()", "A set: add, pop"],
            signal="\"In the order they arrive\": add at one end, take from the other",
            wrong_signals=["\"All day\": many joins, so only the end of a list is touched",
                           "\"Customers\": each one is unique, so membership matters",
                           "\"Served\": take the most recent arrival first"],
            why="A queue takes from the front and adds at the back. A list's front is O(n) to remove from; a deque is "
                "O(1) at both ends. (pop() on a list would serve the newest customer: a stack, not a queue.)",
        ),
        Drill(
            key="oc-drill-undo",
            statement="An editor's undo always reverses the most recent change.",
            question="Which structure makes both operations O(1)?",
            answer="A list: append, pop()",
            choices=["collections.deque: append, popleft", "A list: insert(0, x), pop(0)", "A set: add, pop"],
            signal="\"The most recent change\": take from the end you added to",
            wrong_signals=["\"Always reverses\": changes must be taken from the front",
                           "\"An editor\": changes are looked up by name",
                           "\"Undo\": every change must be unique"],
            why="Last in, first out is a stack, and a list's end is O(1) for both append and pop.",
        ),
        Drill(
            key="oc-drill-taken",
            statement="Sign-up checks whether a username is already taken, among millions of users, thousands of "
                      "times a second.",
            question="Which structure answers this in O(1)?",
            answer="A set: name in taken",
            choices=["A list: name in users", "collections.deque: name in users", "A sorted list scanned from the start"],
            signal="\"Is it already taken?\": membership, asked constantly",
            wrong_signals=["\"Millions of users\": keep them in sign-up order",
                           "\"Thousands of times a second\": take from both ends",
                           "\"Sign-up\": the newest user is checked first"],
            why="`in` on a list or deque scans; on a set it's one hash lookup.",
        ),
    ],
)


FAMILY = Family(
    key="building-blocks",
    name="Building blocks",
    status="ours",
    aliases=["Python data structure costs"],
    idea="Every design starts from what Python's own structures are fast and slow at.",
    variants=[operation_costs],
)
