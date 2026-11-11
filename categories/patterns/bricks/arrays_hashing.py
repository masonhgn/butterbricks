"""Pattern 1: Arrays & Hashing. Trade memory for time: remember what you've seen, so each question about it is one
O(1) lookup instead of a rescan. docs/patterns-taxonomy.md has the reasoning behind each name and sequence."""

import random

from framework.tests import CallTest as T

from framework.curriculum import Drill, Pattern, Problem, Variant


def _rng(seed):
    return random.Random(seed)


def _ints(seed, n, lo, hi):
    """n random ints in [lo, hi), the same every time for a given seed"""
    r = _rng(seed)
    return [r.randrange(lo, hi) for _ in range(n)]


def groups_any_order(value):
    """groups compare equal whatever order the groups, and the items in each, come in. Anything that isn't a list of
    groups (a dict, say) is left as something that can't match"""
    if isinstance(value, (list, tuple)) and all(isinstance(g, (list, tuple)) for g in value):
        return sorted(sorted(g) for g in value)
    return ("not a list of groups", type(value).__name__)


# ---------------------------------------------------------------------------------------------------------------------
# 1.1 Membership set

MS_ADD_FIRST = "adding to the set before checking it, so every item finds itself"
MS_LIST = "keeping a list instead of a set, so every check rescans everything (O(n²))"
MS_UNHASHABLE = "putting a list in a set: lists aren't hashable, so convert to a tuple first"


def _distinct_then(prefix, n, repeat):
    return [f"{prefix}{i}" for i in range(n)] + [repeat]


membership_set = Variant(
    key="membership-set",
    name="Membership set",
    status="ours",
    aliases=["seen set", "visited set", "hash set lookup"],
    sources=[],
    idea="Keep a set of everything you've seen so far, and ask the set before adding to it. Asking a set "
         "\"is x in you?\" takes the same time however big it gets, so one pass answers \"have I seen this before?\" "
         "for every item.",
    invariant="Before step i, `seen` holds exactly the items before index i.",
    template="seen = set()\nfor x in items:\n    if x in seen:\n        ...  # x appeared before\n    seen.add(x)",
    complexity="O(n) time, O(n) space",
    signals=["\"any duplicates?\"", "\"has this appeared before?\"", "\"the first repeated ...\"", "\"is every item unique?\""],
    near_misses=["Frequency counting: when you need how many times, not whether"],
    mistakes=[MS_ADD_FIRST, MS_LIST, MS_UNHASHABLE],
    prerequisites=[],
    problems=[
        Problem(
            key="badge-scanned-twice",
            role="example",
            title="Badge scanned twice",
            statement="Badges are scanned at a door, one after another. Return `True` if any badge was scanned more "
                      "than once, and `False` otherwise.",
            function="has_repeat",
            signature="def has_repeat(badges: list[str]) -> bool:",
            reference="def has_repeat(badges):\n"
                      "    seen = set()\n"
                      "    for badge in badges:\n"
                      "        if badge in seen:\n"
                      "            return True\n"
                      "        seen.add(badge)\n"
                      "    return False\n",
            tests=[
                T("a badge comes back", (["A1", "B2", "A1"],), True),
                T("all different", (["A1", "B2", "C3"],), False),
            ],
            trace_args=(["A1", "C3", "B7", "C3", "D4"],),
            notes={
                "seen = set()": "Nothing has been seen yet.",
                "for badge in badges": "Take the next badge.",
                "if badge in seen": "Ask the set first: has this badge come through already? One lookup, however many "
                                    "badges came before.",
                "return True": "It has: this badge is a repeat.",
                "seen.add(badge)": "Only now remember it, after asking. Adding first would make every badge find "
                                   "itself.",
            },
            predict={"if badge in seen": "badge in seen"},
            takeaway="Ask, then add. The set stands for \"everything before this one\", which is exactly what the "
                     "question needs.",
        ),
        Problem(
            key="order-number-reused",
            role="completion",
            title="Order number reused",
            statement="Order numbers should never repeat. Given them in the order they were issued, return `True` if "
                      "any number was issued twice.\n\nFill in the two blanks (`___`).",
            function="has_reused",
            signature="def has_reused(orders: list[int]) -> bool:",
            starter="def has_reused(orders: list[int]) -> bool:\n"
                    "    seen = set()\n"
                    "    for order in orders:\n"
                    "        if ___:  # has this number been issued before?\n"
                    "            return True\n"
                    "        ___  # remember it, so later orders can find it\n"
                    "    return False\n",
            reference="def has_reused(orders):\n"
                      "    seen = set()\n"
                      "    for order in orders:\n"
                      "        if order in seen:\n"
                      "            return True\n"
                      "        seen.add(order)\n"
                      "    return False\n",
            tests=[
                T("a number issued twice", ([1001, 1002, 1001],), True),
                T("all different", ([7, 8, 9],), False),
                T("one order is not a repeat", ([42],), False, hidden=True, catches=MS_ADD_FIRST),
                T("no orders", ([],), False, hidden=True),
                T("200,000 orders, the repeat at the very end", lambda: (list(range(200_000)) + [5],), True,
                  hidden=True, time_limit=1.0, catches=MS_LIST),
            ],
            hints=["The first blank is the question \"is it in the set?\"; the second adds it."],
            takeaway="Same shape as the badges: ask, then add.",
        ),
        Problem(
            key="username-signed-up-twice",
            role="twin",
            title="Username signed up twice",
            statement="Sign-ups arrive as a list of usernames. Return `True` if any username signed up more than once. "
                      "Usernames are compared exactly (`\"Ana\"` and `\"ana\"` are different).",
            function="duplicate_signup",
            signature="def duplicate_signup(usernames: list[str]) -> bool:",
            reference="def duplicate_signup(usernames):\n"
                      "    seen = set()\n"
                      "    for name in usernames:\n"
                      "        if name in seen:\n"
                      "            return True\n"
                      "        seen.add(name)\n"
                      "    return False\n",
            tests=[
                T("a name twice", (["ana", "bo", "ana"],), True),
                T("all different", (["ana", "Ana", "bo"],), False),
                T("a single sign-up", (["solo"],), False, hidden=True, catches=MS_ADD_FIRST),
                T("200,000 sign-ups, the repeat last", lambda: (_distinct_then("user", 200_000, "user7"),), True,
                  hidden=True, time_limit=1.0, catches=MS_LIST),
            ],
            changes="Only the story: usernames at sign-up instead of badges at a door.",
            takeaway="Nothing changed but the story. Recognizing \"same shape, different words\" is the skill.",
        ),
        Problem(
            key="first-repeated-username",
            role="variation",
            title="The first repeated username",
            statement="Return the first username that repeats: scanning the sign-ups in order, the first one that had "
                      "already appeared earlier. Return `None` if nothing repeats.",
            function="first_repeat",
            signature="def first_repeat(usernames: list[str]) -> str | None:",
            reference="def first_repeat(usernames):\n"
                      "    seen = set()\n"
                      "    for name in usernames:\n"
                      "        if name in seen:\n"
                      "            return name\n"
                      "        seen.add(name)\n"
                      "    return None\n",
            tests=[
                T("bo repeats before cy does", (["cy", "bo", "ana", "bo", "cy"],), "bo"),
                T("nothing repeats", (["ana", "bo"],), None),
                T("a single sign-up", (["solo"],), None, hidden=True, catches=MS_ADD_FIRST),
                T("the first repeat, not the most repeated", (["a", "b", "b", "a", "a", "a"],), "b", hidden=True),
                T("200,000 sign-ups, the repeat last", lambda: (_distinct_then("user", 200_000, "user9"),), "user9",
                  hidden=True, time_limit=1.0, catches=MS_LIST),
            ],
            changes="Return which username repeats first, instead of whether any does.",
            takeaway="The set and the loop are untouched. Only what you return when the check hits changed: the "
                     "element instead of True.",
        ),
        Problem(
            key="longest-run-of-tickets",
            role="stretch",
            title="Longest run of ticket numbers",
            statement="Given ticket numbers in any order (possibly with duplicates), return the length of the longest "
                      "run of consecutive numbers, like 4, 5, 6, 7. Aim for O(n): sorting works, but there's a way "
                      "without it.",
            function="longest_run",
            signature="def longest_run(numbers: list[int]) -> int:",
            reference="def longest_run(numbers):\n"
                      "    present = set(numbers)\n"
                      "    best = 0\n"
                      "    for n in present:\n"
                      "        if n - 1 not in present:  # only count from the start of a run\n"
                      "            length = 1\n"
                      "            while n + length in present:\n"
                      "                length += 1\n"
                      "            best = max(best, length)\n"
                      "    return best\n",
            tests=[
                T("the run 1, 2, 3, 4", ([100, 4, 200, 1, 3, 2],), 4),
                T("no tickets", ([],), 0),
                T("duplicates don't break a run", ([1, 2, 2, 3],), 3, hidden=True),
                T("two runs, the later one longer", ([10, 11, 1, 2, 3, 4, 12],), 4, hidden=True),
                T("200,000 numbers forming one run, shuffled",
                  lambda: (_rng(1).sample(range(200_000), 200_000),), 200_000, hidden=True, time_limit=2.0,
                  catches="counting up from every number instead of only where a run starts (O(n²) on one long run)"),
            ],
            hints=["Put every number in a set first.", "A number starts a run only if number − 1 isn't in the set. "
                   "Count up only from those."],
            takeaway="The set answered two questions here: \"is n + 1 present?\" to extend a run, and \"is n − 1 "
                     "present?\" to know where runs start. Starting only at run starts keeps it O(n).",
        ),
        Problem(
            key="meter-read-twice",
            role="review",
            title="Meter read twice",
            statement="A field worker logs meter IDs as they read them. Return `True` if any meter was read twice.",
            function="read_twice",
            signature="def read_twice(meters: list[int]) -> bool:",
            reference="def read_twice(meters):\n"
                      "    seen = set()\n"
                      "    for m in meters:\n"
                      "        if m in seen:\n"
                      "            return True\n"
                      "        seen.add(m)\n"
                      "    return False\n",
            tests=[
                T("meter 3 read twice", ([3, 9, 3],), True),
                T("all different", ([3, 9, 4],), False),
                T("a single reading", ([12],), False, hidden=True, catches=MS_ADD_FIRST),
                T("200,000 readings", lambda: (list(range(200_000)) + [17],), True, hidden=True, time_limit=1.0,
                  catches=MS_LIST),
            ],
        ),
        Problem(
            key="first-coupon-reused",
            role="review",
            title="First coupon used twice",
            statement="Return the first coupon code that's used a second time (in the order they were redeemed), or "
                      "`None` if every code is used once.",
            function="first_reused_coupon",
            signature="def first_reused_coupon(codes: list[str]) -> str | None:",
            reference="def first_reused_coupon(codes):\n"
                      "    seen = set()\n"
                      "    for code in codes:\n"
                      "        if code in seen:\n"
                      "            return code\n"
                      "        seen.add(code)\n"
                      "    return None\n",
            tests=[
                T("SAVE5 comes back first", (["SAVE5", "FALL", "SAVE5", "FALL"],), "SAVE5"),
                T("no repeats", (["A", "B"],), None),
                T("one code", (["A"],), None, hidden=True, catches=MS_ADD_FIRST),
            ],
        ),
        Problem(
            key="robot-revisits-a-cell",
            role="review",
            title="Robot revisits a cell",
            statement="A robot's path is a list of grid cells, each a `[row, col]` list. Return `True` if it visits "
                      "any cell twice.",
            function="revisits",
            signature="def revisits(path: list[list[int]]) -> bool:",
            reference="def revisits(path):\n"
                      "    seen = set()\n"
                      "    for cell in path:\n"
                      "        key = tuple(cell)\n"
                      "        if key in seen:\n"
                      "            return True\n"
                      "        seen.add(key)\n"
                      "    return False\n",
            tests=[
                T("back to the start", ([[0, 0], [0, 1], [1, 1], [0, 0]],), True),
                T("never the same cell", ([[0, 0], [0, 1], [1, 1]],), False, catches=MS_UNHASHABLE),
                T("a single cell", ([[2, 3]],), False, hidden=True, catches=MS_ADD_FIRST),
            ],
            hints=["A list can't go in a set. What can stand for [row, col] that can?"],
        ),
    ],
    drills=[
        Drill(
            key="ms-drill-tickets",
            statement="Ticket codes are presented at a gate one at a time. Raise an alarm as soon as any code is "
                      "presented a second time.",
            choices=["Frequency counting", "Complement lookup", "Grouping by key"],
            signal='"A second time": only whether a code was seen before matters',
            wrong_signals=['"Ticket codes": they\'re strings, so group them by a canonical key', '"One at a time": count how often each code appears', '"Presented": each code needs a matching partner code'],
            why="\"Seen before?\" is a yes/no question about the past: a membership set. Counting would work too, but "
                "it answers a question nobody asked.",
        ),
        Drill(
            key="ms-drill-unique",
            statement="Given a list of user IDs, return True if every ID is unique.",
            choices=["Frequency counting", "Grouping by key", "Converging pointers (Two Pointers)"],
            signal='"Every ID is unique": no ID may have been seen before',
            wrong_signals=['"A list of user IDs": tally how many times each ID appears, then check the totals', '"Return True": pair each ID with the ID that completes it', '"User IDs": group the IDs by a shared key'],
            why="Unique means \"never seen before\", checked for every item: ask the set, then add.",
        ),
        Drill(
            key="ms-drill-first-equal",
            statement="Sensor readings come in order. Find the first reading that equals some earlier reading.",
            choices=["Complement lookup", "Frequency counting", "Grouping by key"],
            signal='"Equals some earlier reading": a lookup among what came before',
            wrong_signals=['"Readings come in order": start at both ends and move inward', '"Some earlier reading": count every reading first, then pick', '"The first reading": group the readings by value'],
            why="Each reading asks whether it's among the earlier ones, so the earlier ones go in a set.",
        ),
    ],
)


# ---------------------------------------------------------------------------------------------------------------------
# 1.2 Frequency counting

FC_KEYERROR = "reading count[x] before x was ever counted (KeyError): use count.get(x, 0)"
FC_SET_ONLY = "comparing which letters appear, not how many of each (\"aab\" vs \"abb\")"
FC_RECOUNT = "calling .count() inside the loop, which rescans everything each time (O(n²))"


def _shuffled(seed, text):
    letters = list(text)
    _rng(seed).shuffle(letters)
    return "".join(letters)


def _random_letters(seed, n):
    r = _rng(seed)
    return "".join(r.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(n))


frequency_counting = Variant(
    key="frequency-counting",
    name="Frequency counting",
    status="ours",
    aliases=["frequency map", "counter", "histogram", "tally"],
    sources=[],
    idea="Map each value to how many times it has appeared. One pass builds the tally; after that, \"how many x?\" "
         "is a single lookup. Two tallies that are equal describe the same items, in any order.",
    invariant="`count[x]` is how many times x occurs in the part processed so far.",
    template="count = {}\nfor x in items:\n    count[x] = count.get(x, 0) + 1",
    complexity="O(n) time, O(k) space for k distinct values",
    signals=["\"how many times\"", "\"most common\"", "\"the same letters\"", "\"a rearrangement of\"", "\"majority\""],
    near_misses=["Membership set: when only whether matters", "Sorting: also works, but O(n log n) where counting is O(n)"],
    mistakes=[FC_KEYERROR, FC_SET_ONLY, FC_RECOUNT],
    prerequisites=["membership-set"],
    problems=[
        Problem(
            key="rearranged-words",
            role="example",
            title="Rearranged words",
            statement="Return `True` if word `b` is a rearrangement of word `a`: the same letters, each used the same "
                      "number of times.",
            function="same_letters",
            signature="def same_letters(a: str, b: str) -> bool:",
            reference="def same_letters(a, b):\n"
                      "    if len(a) != len(b):\n"
                      "        return False\n"
                      "    count = {}\n"
                      "    for ch in a:\n"
                      "        count[ch] = count.get(ch, 0) + 1\n"
                      "    for ch in b:\n"
                      "        count[ch] = count.get(ch, 0) - 1\n"
                      "        if count[ch] < 0:\n"
                      "            return False\n"
                      "    return True\n",
            tests=[
                T("listen and silent", ("listen", "silent"), True),
                T("rat and car", ("rat", "car"), False),
            ],
            trace_args=("tab", "bat"),
            notes={
                "if len(a) != len(b)": "Different lengths can't be rearrangements: a quick exit.",
                "count = {}": "An empty tally.",
                "count[ch] = count.get(ch, 0) + 1": "Count one more of this letter. get(ch, 0) treats a letter never "
                                                    "seen as 0.",
                "count[ch] = count.get(ch, 0) - 1": "Use up one of this letter for b.",
                "if count[ch] < 0": "Has b used more of this letter than a has?",
                "return True": "Same length, and b never ran out of a letter: every count ended at 0.",
            },
            predict={"if count[ch] < 0": "count[ch] < 0"},
            takeaway="Count up for one side, down for the other. Equal lengths plus never going below zero means every "
                     "count came back to exactly 0.",
        ),
        Problem(
            key="note-from-a-magazine",
            role="completion",
            title="A note from a magazine",
            statement="Can `note` be built from letters cut out of `magazine`, using each letter in the magazine at "
                      "most once? Fill in the two blanks.",
            function="can_build",
            signature="def can_build(note: str, magazine: str) -> bool:",
            starter="def can_build(note: str, magazine: str) -> bool:\n"
                    "    count = {}\n"
                    "    for ch in magazine:\n"
                    "        count[ch] = count.get(ch, 0) + 1\n"
                    "    for ch in note:\n"
                    "        ___  # use up one of this letter\n"
                    "        if ___:  # did the note need more of it than the magazine had?\n"
                    "            return False\n"
                    "    return True\n",
            reference="def can_build(note, magazine):\n"
                      "    count = {}\n"
                      "    for ch in magazine:\n"
                      "        count[ch] = count.get(ch, 0) + 1\n"
                      "    for ch in note:\n"
                      "        count[ch] = count.get(ch, 0) - 1\n"
                      "        if count[ch] < 0:\n"
                      "            return False\n"
                      "    return True\n",
            tests=[
                T("two a's from aab", ("aa", "aab"), True),
                T("two a's, only one in the magazine", ("aa", "ab"), False),
                T("a letter the magazine doesn't have", ("z", "abc"), False, hidden=True, catches=FC_KEYERROR),
                T("letters present, but not enough of one", ("aab", "abb"), False, hidden=True, catches=FC_SET_ONLY),
                T("an empty note", ("", "xyz"), True, hidden=True),
                T("a 200,000-letter note", lambda: (_random_letters(2, 100_000), _random_letters(2, 100_000) * 2), True,
                  hidden=True, time_limit=1.0, catches=FC_RECOUNT),
            ],
            hints=["Using up a letter is the same line as counting one, with − instead of +.",
                   "A letter the magazine never had has no entry yet: get(ch, 0)."],
            takeaway="The example's two loops, with the magazine on the counting side and the note on the spending side.",
        ),
        Problem(
            key="letter-tiles",
            role="twin",
            title="Letter tiles",
            statement="You have letter tiles (a list of single letters). Return `True` if they can spell `word`, using "
                      "each tile at most once.",
            function="can_spell",
            signature="def can_spell(tiles: list[str], word: str) -> bool:",
            reference="def can_spell(tiles, word):\n"
                      "    count = {}\n"
                      "    for t in tiles:\n"
                      "        count[t] = count.get(t, 0) + 1\n"
                      "    for ch in word:\n"
                      "        count[ch] = count.get(ch, 0) - 1\n"
                      "        if count[ch] < 0:\n"
                      "            return False\n"
                      "    return True\n",
            tests=[
                T("enough tiles", (["c", "a", "t", "s"], "cat"), True),
                T("one o, word needs two", (["b", "o", "k"], "book"), False),
                T("a letter with no tile", (["a", "b"], "ax"), False, hidden=True, catches=FC_KEYERROR),
                T("right letters, wrong amounts", (["a", "b", "b"], "aab"), False, hidden=True, catches=FC_SET_ONLY),
                T("100,000 tiles", lambda: (list(_random_letters(3, 100_000)), _random_letters(3, 50_000)), True,
                  hidden=True, time_limit=1.0, catches=FC_RECOUNT),
            ],
            changes="Only the story: tiles in a list instead of a magazine's text.",
            takeaway="Tiles or magazine letters: a supply, a demand, and one tally between them.",
        ),
        Problem(
            key="first-letter-used-once",
            role="variation",
            title="First letter used once",
            statement="Return the index of the first character in `text` that appears exactly once in the whole text, "
                      "or `-1` if every character repeats.",
            function="first_unique",
            signature="def first_unique(text: str) -> int:",
            reference="def first_unique(text):\n"
                      "    count = {}\n"
                      "    for ch in text:\n"
                      "        count[ch] = count.get(ch, 0) + 1\n"
                      "    for i, ch in enumerate(text):\n"
                      "        if count[ch] == 1:\n"
                      "            return i\n"
                      "    return -1\n",
            tests=[
                T("u is the first unique", ("butterbrick",), 1),
                T("everything repeats", ("aabb",), -1),
                T("a single character", ("z",), 0, hidden=True),
                T("unique only at the end", ("aabbc",), 4, hidden=True),
                T("100,000 characters", lambda: (_random_letters(4, 100_000) + "#",), 100_000, hidden=True,
                  time_limit=1.0, catches=FC_RECOUNT),
            ],
            changes="Ask one tally a question (\"which appears exactly once?\") instead of comparing two tallies.",
            takeaway="Two passes: one to build the tally, one to ask it about each position in order. The tally is "
                     "built the same way; only the question changed.",
        ),
        Problem(
            key="top-tags",
            role="stretch",
            title="Top tags",
            statement="Return the `k` most frequent tags, most frequent first. Ties go to the tag that appeared first "
                      "in the list. Try grouping tags by their count (one bucket per count) instead of sorting all of "
                      "them.",
            function="top_tags",
            signature="def top_tags(tags: list[str], k: int) -> list[str]:",
            reference="def top_tags(tags, k):\n"
                      "    count = {}\n"
                      "    for t in tags:\n"
                      "        count[t] = count.get(t, 0) + 1\n"
                      "    buckets = [[] for _ in range(len(tags) + 1)]\n"
                      "    for t, c in count.items():  # a dict keeps first-appearance order\n"
                      "        buckets[c].append(t)\n"
                      "    out = []\n"
                      "    for c in range(len(tags), 0, -1):\n"
                      "        for t in buckets[c]:\n"
                      "            if len(out) == k:\n"
                      "                return out\n"
                      "            out.append(t)\n"
                      "    return out\n",
            tests=[
                T("the two most common", (["sql", "py", "sql", "go", "py", "sql"], 2), ["sql", "py"]),
                T("a tie goes to the earlier tag", (["b", "a", "a", "b", "c"], 2), ["b", "a"]),
                T("k larger than the number of tags", (["x"], 3), ["x"], hidden=True),
                T("100,000 tags", lambda: ([f"t{n}" for n in _ints(5, 100_000, 0, 500)], 10),
                  hidden=True, time_limit=1.5, catches=FC_RECOUNT),
            ],
            hints=["Count first. Then buckets[c] can hold every tag seen exactly c times.",
                   "Walk the buckets from the highest count down, until you have k tags."],
            takeaway="A tally, then bucketing by count: values become indexes. That's \"bucket sort by frequency\", "
                     "O(n) where sorting by count would be O(n log n).",
        ),
        Problem(
            key="license-plate-rearranged",
            role="review",
            title="Rearranged license plate",
            statement="A witness remembers the characters of a license plate but not their order. Return `True` if "
                      "plate `b` uses exactly the characters of `a`, each the same number of times.",
            function="is_rearrangement",
            signature="def is_rearrangement(a: str, b: str) -> bool:",
            reference="def is_rearrangement(a, b):\n"
                      "    if len(a) != len(b):\n"
                      "        return False\n"
                      "    count = {}\n"
                      "    for ch in a:\n"
                      "        count[ch] = count.get(ch, 0) + 1\n"
                      "    for ch in b:\n"
                      "        count[ch] = count.get(ch, 0) - 1\n"
                      "        if count[ch] < 0:\n"
                      "            return False\n"
                      "    return True\n",
            tests=[
                T("same characters", ("7KX2", "X27K"), True),
                T("one character off", ("7KX2", "7KX3"), False),
                T("right characters, wrong amounts", ("AAB", "ABB"), False, hidden=True, catches=FC_SET_ONLY),
            ],
        ),
        Problem(
            key="enough-ingredients",
            role="review",
            title="Enough ingredients",
            statement="A recipe is a list of ingredient names, one entry per unit needed. The pantry is a list too. "
                      "Return `True` if the pantry has enough of everything.",
            function="enough",
            signature="def enough(recipe: list[str], pantry: list[str]) -> bool:",
            reference="def enough(recipe, pantry):\n"
                      "    count = {}\n"
                      "    for item in pantry:\n"
                      "        count[item] = count.get(item, 0) + 1\n"
                      "    for item in recipe:\n"
                      "        count[item] = count.get(item, 0) - 1\n"
                      "        if count[item] < 0:\n"
                      "            return False\n"
                      "    return True\n",
            tests=[
                T("plenty", (["egg", "egg", "flour"], ["egg", "flour", "egg", "milk"]), True),
                T("one egg short", (["egg", "egg"], ["egg"]), False),
                T("an ingredient the pantry never had", (["saffron"], ["salt"]), False, hidden=True,
                  catches=FC_KEYERROR),
            ],
        ),
        Problem(
            key="first-word-said-once",
            role="review",
            title="First word said once",
            statement="Return the first word in `words` that appears exactly once, or `None` if every word repeats.",
            function="first_once",
            signature="def first_once(words: list[str]) -> str | None:",
            reference="def first_once(words):\n"
                      "    count = {}\n"
                      "    for w in words:\n"
                      "        count[w] = count.get(w, 0) + 1\n"
                      "    for w in words:\n"
                      "        if count[w] == 1:\n"
                      "            return w\n"
                      "    return None\n",
            tests=[
                T("um repeats, so", (["um", "so", "um", "like"],), "so"),
                T("everything repeats", (["a", "a"],), None),
                T("100,000 words", lambda: ([f"w{i % 1000}" for i in range(100_000)] + ["rare"],), "rare",
                  hidden=True, time_limit=1.0, catches=FC_RECOUNT),
            ],
        ),
    ],
    drills=[
        Drill(
            key="fc-drill-manifests",
            statement="Two shipping manifests list item codes. Do they contain the same items, the same number of "
                      "times each, in any order?",
            choices=["Membership set", "Grouping by key", "Complement lookup"],
            signal='"The same number of times each": how many, not just whether',
            wrong_signals=['"Contain the same items": a set of each list is enough', '"In any order": group the items by a sorted key', '"Two manifests": look up each item\'s partner in the other list'],
            why="Equal multisets are equal tallies. A set would miss \"aab\" vs \"abb\".",
        ),
        Drill(
            key="fc-drill-common-word",
            statement="Find the most common word in a product review.",
            choices=["Membership set", "Grouping by key", "Converging pointers (Two Pointers)"],
            signal='"Most common": a count per word, then the largest',
            wrong_signals=['"A word": the answer is one item, so remember which words were seen', '"In a review": group the words by their first letter', '"Find the word": look up the word each word pairs with'],
            why="\"Most common\" asks for a count per value, then the largest.",
        ),
        Drill(
            key="fc-drill-majority",
            statement="An election has ballots for candidates. Did any candidate get more than half the votes?",
            choices=["Membership set", "Complement lookup", "Grouping by key"],
            signal='"More than half the votes": a count per candidate, against a threshold',
            wrong_signals=['"Did any candidate": a yes/no question about whether one was seen', '"Ballots": group the ballots by candidate and keep the lists', '"Half": pair each ballot with an opposing one'],
            why="A tally per candidate, then check whether any count passes n / 2. (There's also a cleverer O(1)-space "
                "method, Boyer–Moore voting, for later.)",
        ),
    ],
)


# ---------------------------------------------------------------------------------------------------------------------
# 1.3 Complement lookup

CL_STORE_FIRST = "storing x before looking for its partner, so x can pair with itself"
CL_VALUES = "returning the two values when their positions were asked for"
CL_NESTED = "trying every pair with a nested loop (O(n²))"


def _big_pair(n):
    """distinct weights where only the last two sum to the limit, so a nested loop has to try almost every pair.
    The others are multiples of 3, and the limit leaves a remainder of 2, so no two of them (and neither of them with
    the first of the last two) can reach it"""
    values = [i * 3 for i in range(1, n - 1)]
    return values + [10**9 - 1, 2], 10**9 + 1


def _big_apart(n):
    """readings 4 apart, then the only pair that's 1 apart at the very end"""
    return [i * 4 for i in range(n)] + [10**9 + 2, 10**9 + 3], 1


complement_lookup = Variant(
    key="complement-lookup",
    name="Complement lookup",
    status="ours",
    aliases=["two-sum hash map", "target minus x", "index map"],
    sources=[],
    idea="For each x, the partner it needs is fixed: target − x. So instead of trying every pair, look the partner up "
         "among the items before x, then store x for the items after it.",
    invariant="Before step i, the map holds value → index for exactly the items before i.",
    template="index = {}\nfor i, x in enumerate(nums):\n    if target - x in index:\n        return index[target - x], i\n"
             "    index[x] = i",
    complexity="O(n) time, O(n) space",
    signals=["\"two items that add up to\"", "\"a pair with difference\"", "unsorted input", "the answer is positions"],
    near_misses=["Converging pointers (Two Pointers): when the input is sorted, or may be, and O(1) space matters",
                 "Prefix sums with a hash map (later): the same idea over running sums"],
    mistakes=[CL_STORE_FIRST, CL_VALUES, CL_NESTED],
    prerequisites=["membership-set", "frequency-counting"],
    problems=[
        Problem(
            key="two-gift-cards",
            role="example",
            title="Two gift cards",
            statement="Exactly two of your gift cards add up to the price. Return their positions, earlier one first.",
            function="gift_cards",
            signature="def gift_cards(balances: list[int], price: int) -> tuple[int, int]:",
            reference="def gift_cards(balances, price):\n"
                      "    index = {}\n"
                      "    for i, balance in enumerate(balances):\n"
                      "        partner = price - balance\n"
                      "        if partner in index:\n"
                      "            return index[partner], i\n"
                      "        index[balance] = i\n",
            tests=[
                T("10 and 40", ([25, 10, 40, 15], 50), (1, 2)),
                T("two equal cards", ([20, 20], 40), (0, 1)),
            ],
            trace_args=([25, 10, 40, 15], 50),
            notes={
                "index = {}": "Balances seen so far, and where each was.",
                "partner = price - balance": "The one balance that would complete this card.",
                "if partner in index": "Has that partner already gone by? One lookup instead of checking every pair.",
                "return index[partner], i": "Found it: the partner's position, then this card's.",
                "index[balance] = i": "Remember this card for the cards after it. Storing after the check means a card "
                                      "can't pair with itself.",
            },
            predict={"if partner in index": "partner in index"},
            takeaway="Each item knows exactly what partner it needs, so the question becomes a lookup. Check first, "
                     "store after.",
        ),
        Problem(
            key="readings-apart",
            role="completion",
            title="Readings exactly d apart",
            statement="Exactly one pair of readings differs by `d` (and `d > 0`). Return their positions, earlier one "
                      "first. Fill in the two partners each reading could have.",
            function="pair_apart",
            signature="def pair_apart(readings: list[int], d: int) -> tuple[int, int]:",
            starter="def pair_apart(readings: list[int], d: int) -> tuple[int, int]:\n"
                    "    index = {}\n"
                    "    for j, x in enumerate(readings):\n"
                    "        for partner in (___, ___):  # the two values x could pair with\n"
                    "            if partner in index:\n"
                    "                return index[partner], j\n"
                    "        index[x] = j\n",
            reference="def pair_apart(readings, d):\n"
                      "    index = {}\n"
                      "    for j, x in enumerate(readings):\n"
                      "        for partner in (x - d, x + d):\n"
                      "            if partner in index:\n"
                      "                return index[partner], j\n"
                      "        index[x] = j\n",
            tests=[
                T("4 and 12 are 8 apart", ([10, 4, 12, 30], 8), (1, 2)),
                T("a pair at the start", ([1, 6], 5), (0, 1)),
                T("the partner is larger", ([9, 2, 30], 7), (0, 1), hidden=True),
                T("100,000 readings, the pair at the end", lambda: _big_apart(100_000),
                  hidden=True, time_limit=1.0, catches=CL_NESTED),
            ],
            hints=["A reading x pairs with something d below it or d above it."],
            takeaway="With a difference, there are two possible partners instead of one, and each is still one lookup.",
        ),
        Problem(
            key="fill-the-truck",
            role="twin",
            title="Fill the truck exactly",
            statement="Exactly two shipments together weigh exactly the truck's `limit`. Return their positions, "
                      "earlier one first.",
            function="fill_truck",
            signature="def fill_truck(weights: list[int], limit: int) -> tuple[int, int]:",
            reference="def fill_truck(weights, limit):\n"
                      "    index = {}\n"
                      "    for i, w in enumerate(weights):\n"
                      "        if limit - w in index:\n"
                      "            return index[limit - w], i\n"
                      "        index[w] = i\n",
            tests=[
                T("700 and 300", ([200, 700, 450, 300], 1000), (1, 3)),
                T("the first two", ([5, 5, 9], 10), (0, 1)),
                T("a shipment can't pair with itself", ([5, 7, 3], 10), (1, 2), hidden=True, catches=CL_STORE_FIRST),
                T("positions, not weights", ([60, 15, 5], 20), (1, 2), hidden=True, catches=CL_VALUES),
                T("100,000 shipments", lambda: _big_pair(100_000), hidden=True, time_limit=1.0, catches=CL_NESTED),
            ],
            changes="Only the story: shipments and a weight limit instead of gift cards and a price.",
            takeaway="Gift cards or shipments: \"which two make the target?\" is one lookup per item.",
        ),
        Problem(
            key="count-the-pairs",
            role="variation",
            title="How many pairs",
            statement="Return how many pairs of positions `i < j` have `nums[i] + nums[j] == target`. Values can "
                      "repeat.",
            function="count_pairs",
            signature="def count_pairs(nums: list[int], target: int) -> int:",
            reference="def count_pairs(nums, target):\n"
                      "    seen = {}\n"
                      "    pairs = 0\n"
                      "    for x in nums:\n"
                      "        pairs += seen.get(target - x, 0)\n"
                      "        seen[x] = seen.get(x, 0) + 1\n"
                      "    return pairs\n",
            tests=[
                T("1 + 5 once, 3 + 3 three ways", ([1, 5, 3, 3, 3], 6), 4),
                T("four 2s make six pairs", ([2, 2, 2, 2], 4), 6),
                T("one 3 can't pair with itself", ([3], 6), 0, hidden=True, catches=CL_STORE_FIRST),
                T("no pairs", ([1, 2, 3], 100), 0, hidden=True),
                T("100,000 numbers", lambda: (_ints(6, 100_000, 0, 1000), 1000),
                  hidden=True, time_limit=1.0, catches=CL_NESTED),
            ],
            changes="Count every pair instead of finding one: the map stores how many times each value has appeared, "
                    "not where.",
            takeaway="Same lookup of target − x. Because you need every pair, the map now holds counts (frequency "
                     "counting) instead of positions.",
        ),
        Problem(
            key="songs-in-whole-minutes",
            role="stretch",
            title="Songs that fill whole minutes",
            statement="Song lengths are in seconds. Return how many pairs of songs have a total length that's a "
                      "multiple of 60.",
            function="whole_minute_pairs",
            signature="def whole_minute_pairs(lengths: list[int]) -> int:",
            reference="def whole_minute_pairs(lengths):\n"
                      "    seen = {}\n"
                      "    pairs = 0\n"
                      "    for t in lengths:\n"
                      "        need = (60 - t % 60) % 60\n"
                      "        pairs += seen.get(need, 0)\n"
                      "        seen[t % 60] = seen.get(t % 60, 0) + 1\n"
                      "    return pairs\n",
            tests=[
                T("three pairs", ([30, 20, 150, 100, 40],), 3),
                T("three whole minutes, three pairs", ([60, 60, 60],), 3),
                T("one song can't pair with itself", ([30],), 0, hidden=True, catches=CL_STORE_FIRST),
                T("100,000 songs", lambda: (_ints(7, 100_000, 1, 600),),
                  hidden=True, time_limit=1.0, catches=CL_NESTED),
            ],
            hints=["Only a song's remainder (length % 60) matters.", "A remainder r needs a partner with remainder "
                   "(60 − r) % 60. Why the extra % 60?"],
            takeaway="The complement doesn't have to be target − x: it's whatever x needs. Here, the remainder that "
                     "rounds x up to a whole minute.",
        ),
        Problem(
            key="two-prices",
            role="review",
            title="Two prices for the budget",
            statement="Exactly two items cost `budget` together. Return their positions, earlier one first.",
            function="two_prices",
            signature="def two_prices(prices: list[int], budget: int) -> tuple[int, int]:",
            reference="def two_prices(prices, budget):\n"
                      "    index = {}\n"
                      "    for i, p in enumerate(prices):\n"
                      "        if budget - p in index:\n"
                      "            return index[budget - p], i\n"
                      "        index[p] = i\n",
            tests=[
                T("8 and 12", ([3, 8, 30, 12], 20), (1, 3)),
                T("can't buy one item twice", ([5, 7, 3], 10), (1, 2), hidden=True, catches=CL_STORE_FIRST),
            ],
        ),
        Problem(
            key="score-pairs",
            role="review",
            title="Pairs of scores",
            statement="Return how many pairs of positions `i < j` have `scores[i] + scores[j] == target`.",
            function="score_pairs",
            signature="def score_pairs(scores: list[int], target: int) -> int:",
            reference="def score_pairs(scores, target):\n"
                      "    seen = {}\n"
                      "    pairs = 0\n"
                      "    for s in scores:\n"
                      "        pairs += seen.get(target - s, 0)\n"
                      "        seen[s] = seen.get(s, 0) + 1\n"
                      "    return pairs\n",
            tests=[
                T("two pairs", ([4, 6, 6, 1], 10), 2),
                T("a 5 alone", ([5], 10), 0, hidden=True, catches=CL_STORE_FIRST),
            ],
        ),
        Problem(
            key="changes-that-cancel",
            role="review",
            title="Changes that cancel out",
            statement="Exactly one pair of balance changes cancels out (adds to 0). Return their positions, earlier "
                      "one first.",
            function="cancel_pair",
            signature="def cancel_pair(changes: list[int]) -> tuple[int, int]:",
            reference="def cancel_pair(changes):\n"
                      "    index = {}\n"
                      "    for i, c in enumerate(changes):\n"
                      "        if -c in index:\n"
                      "            return index[-c], i\n"
                      "        index[c] = i\n",
            tests=[
                T("+40 and -40", ([15, 40, -7, -40],), (1, 3)),
                T("100,000 changes", lambda: ([i for i in range(1, 100_000)] + [-99_999],), (99_998, 99_999),
                  hidden=True, time_limit=1.0, catches=CL_NESTED),
            ],
        ),
    ],
    drills=[
        Drill(
            key="cl-drill-two-amounts",
            statement="Given unsorted transaction amounts and a target, return the positions of two transactions that "
                      "add up to the target.",
            choices=["Converging pointers (Two Pointers)", "Membership set", "Frequency counting"],
            signal='"Two that add up to the target", unsorted, positions wanted: each partner is fixed',
            wrong_signals=['"Transaction amounts": sort them and walk two pointers inward', '"Return the positions": remember which amounts have been seen, nothing more', '"A target": count how often each amount appears'],
            why="Each amount needs exactly target − amount. Unsorted input and positions in the answer rule out "
                "sorting and converging.",
        ),
        Drill(
            key="cl-drill-differ-by-k",
            statement="How many pairs of numbers in a list differ by exactly k?",
            choices=["Frequency counting", "Grouping by key", "Converging pointers (Two Pointers)"],
            signal='"Differ by exactly k": each number\'s partner is x − k or x + k',
            wrong_signals=['"How many pairs": count each number\'s occurrences and add them up', '"A list": sort it and keep two pointers at the ends', '"Numbers": group the numbers that share a key'],
            why="Every number knows the two values it could pair with, so each is a lookup. The map holds counts "
                "because you need every pair.",
        ),
        Drill(
            key="cl-drill-cancel",
            statement="In a list of temperature changes, is there a pair that cancels out exactly?",
            choices=["Frequency counting", "Grouping by key", "Converging pointers (Two Pointers)"],
            signal='"Cancels out exactly": each change\'s partner is its negative',
            wrong_signals=['"Temperature changes": tally how often each change occurs', '"Is there a pair": a yes/no about whether one value was seen twice', '"A pair": group the changes by sign'],
            why="The complement of c is −c: look it up among the earlier changes.",
        ),
    ],
)


# ---------------------------------------------------------------------------------------------------------------------
# 1.4 Grouping by key

GK_UNHASHABLE = "using a list as the key: lists aren't hashable, so use a tuple or a string"
GK_NOT_CANONICAL = "a key that isn't the same for equivalent items, like a set of letters (\"aab\" and \"abb\" collide)"
GK_DICT = "returning the dictionary itself when a list of groups was asked for"

grouping_by_key = Variant(
    key="grouping-by-key",
    name="Grouping by key",
    status="ours",
    aliases=["canonical key", "bucketing", "group by signature"],
    sources=[],
    idea="Compute a key for each item that's the same for every item you consider equivalent, and different "
         "otherwise. Then collect items by key: everything that shares a key is one group.",
    invariant="`groups[key(x)]` holds every processed item with that key.",
    template="groups = {}\nfor x in items:\n    groups.setdefault(key(x), []).append(x)\nreturn list(groups.values())",
    complexity="O(n × the cost of one key)",
    signals=["\"group\"", "\"which ones are equivalent\"", "\"classify\"", "\"the same up to order / shift / case\""],
    near_misses=["Frequency counting: counting per key instead of collecting"],
    mistakes=[GK_UNHASHABLE, GK_NOT_CANONICAL, GK_DICT],
    prerequisites=["frequency-counting"],
    problems=[
        Problem(
            key="group-rearranged-words",
            role="example",
            title="Group rearranged words",
            statement="Group words that are rearrangements of each other. Return a list of groups; the order of the "
                      "groups, and of words within a group, doesn't matter.",
            function="group_words",
            signature="def group_words(words: list[str]) -> list[list[str]]:",
            reference="def group_words(words):\n"
                      "    groups = {}\n"
                      "    for word in words:\n"
                      "        key = \"\".join(sorted(word))\n"
                      "        groups.setdefault(key, []).append(word)\n"
                      "    return list(groups.values())\n",
            tests=[
                T("two groups and a single", (["tea", "ate", "tan", "eat", "nat", "bat"],),
                  [["tea", "ate", "eat"], ["tan", "nat"], ["bat"]], normalize=groups_any_order),
            ],
            trace_args=(["tea", "ate", "tan", "eat"],),
            notes={
                "groups = {}": "Key → the words that share it.",
                "key = \"\".join(sorted(word))": "Sorting the letters gives every rearrangement the same key: tea, "
                                                 "ate and eat all become \"aet\".",
                "groups.setdefault(key, []).append(word)": "Start a group the first time a key appears, then add the "
                                                           "word to it.",
                "return list(groups.values())": "The groups themselves, not the dictionary.",
            },
            predict={"groups.setdefault(key, []).append(word)": "key in groups"},
            takeaway="Choosing the key is the whole problem: equivalent items must get the same key, and different "
                     "items different keys.",
        ),
        Problem(
            key="group-by-letter-counts",
            role="completion",
            title="Group by letter counts",
            statement="The same grouping, with a different key: the count of each letter a to z. Words use lowercase "
                      "letters only. Fill in the key.",
            function="group_by_counts",
            signature="def group_by_counts(words: list[str]) -> list[list[str]]:",
            starter="def group_by_counts(words: list[str]) -> list[list[str]]:\n"
                    "    groups = {}\n"
                    "    for word in words:\n"
                    "        counts = [0] * 26\n"
                    "        for ch in word:\n"
                    "            counts[ord(ch) - ord(\"a\")] += 1\n"
                    "        key = ___  # counts as a key (a list can't be one)\n"
                    "        groups.setdefault(key, []).append(word)\n"
                    "    return list(groups.values())\n",
            reference="def group_by_counts(words):\n"
                      "    groups = {}\n"
                      "    for word in words:\n"
                      "        counts = [0] * 26\n"
                      "        for ch in word:\n"
                      "            counts[ord(ch) - ord(\"a\")] += 1\n"
                      "        key = tuple(counts)\n"
                      "        groups.setdefault(key, []).append(word)\n"
                      "    return list(groups.values())\n",
            tests=[
                T("rearrangements together", (["tea", "eat", "tan"],), [["tea", "eat"], ["tan"]],
                  normalize=groups_any_order),
                T("a list key won't hash", (["ab", "ba"],), [["ab", "ba"]], normalize=groups_any_order,
                  catches=GK_UNHASHABLE),
                T("same letters, different counts", (["aab", "abb", "aba"],), [["aab", "aba"], ["abb"]],
                  normalize=groups_any_order, hidden=True, catches=GK_NOT_CANONICAL),
                T("no words", ([],), [], normalize=groups_any_order, hidden=True),
            ],
            hints=["What's a list's hashable twin?"],
            takeaway="Sorting the letters and counting them are two keys for the same equivalence. Counting avoids the "
                     "sort, at the price of a 26-slot key.",
        ),
        Problem(
            key="group-product-codes",
            role="twin",
            title="Group product codes",
            statement="Codes that use the same characters (in any order) refer to the same product. Group them. The "
                      "order of groups, and within groups, doesn't matter.",
            function="group_codes",
            signature="def group_codes(codes: list[str]) -> list[list[str]]:",
            reference="def group_codes(codes):\n"
                      "    groups = {}\n"
                      "    for code in codes:\n"
                      "        groups.setdefault(\"\".join(sorted(code)), []).append(code)\n"
                      "    return list(groups.values())\n",
            tests=[
                T("two products", (["A1B", "B1A", "C2D", "1AB"],), [["A1B", "B1A", "1AB"], ["C2D"]],
                  normalize=groups_any_order),
                T("a list of groups, not a dict", (["X"],), [["X"]], normalize=groups_any_order, catches=GK_DICT),
                T("same characters, different amounts", (["AAB", "ABB"],), [["AAB"], ["ABB"]],
                  normalize=groups_any_order, hidden=True, catches=GK_NOT_CANONICAL),
            ],
            changes="Only the story: product codes instead of words.",
            takeaway="Same key, new story.",
        ),
        Problem(
            key="group-shifted-words",
            role="variation",
            title="Group shifted words",
            statement="Shifting a word moves every letter forward by the same amount, wrapping z around to a (\"abc\" "
                      "→ \"bcd\", \"az\" → \"ba\"). Group words that are shifts of each other. Lowercase letters "
                      "only; order doesn't matter.",
            function="group_shifts",
            signature="def group_shifts(words: list[str]) -> list[list[str]]:",
            reference="def group_shifts(words):\n"
                      "    groups = {}\n"
                      "    for w in words:\n"
                      "        key = tuple((ord(b) - ord(a)) % 26 for a, b in zip(w, w[1:]))\n"
                      "        groups.setdefault(key, []).append(w)\n"
                      "    return list(groups.values())\n",
            tests=[
                T("four groups", (["abc", "bcd", "acd", "dfg", "az", "ba", "a", "z"],),
                  [["abc", "bcd"], ["acd", "dfg"], ["az", "ba"], ["a", "z"]], normalize=groups_any_order),
                T("a key that wraps", (["za", "ab"],), [["za", "ab"]], normalize=groups_any_order),
                T("shifts, not rearrangements", (["abc", "cba"],), [["abc"], ["cba"]], normalize=groups_any_order,
                  hidden=True, catches=GK_NOT_CANONICAL),
                T("list keys don't hash", (["ab", "bc"],), [["ab", "bc"]], normalize=groups_any_order, hidden=True,
                  catches=GK_UNHASHABLE),
            ],
            changes="Which key: the gaps between consecutive letters, instead of the sorted letters.",
            takeaway="The loop is identical; only the key changed. Ask what stays the same when you shift a word: the "
                     "gaps between its letters.",
        ),
        Problem(
            key="duplicate-files",
            role="stretch",
            title="Duplicate files",
            statement="Files are `(path, content)` pairs. Return groups of paths whose files have identical content, "
                      "keeping only groups with two or more paths. Order doesn't matter.",
            function="duplicate_files",
            signature="def duplicate_files(files: list[tuple[str, str]]) -> list[list[str]]:",
            reference="def duplicate_files(files):\n"
                      "    groups = {}\n"
                      "    for path, content in files:\n"
                      "        groups.setdefault(content, []).append(path)\n"
                      "    return [paths for paths in groups.values() if len(paths) > 1]\n",
            tests=[
                T("two copies of one file", ([("a.txt", "hi"), ("b.txt", "yo"), ("c.txt", "hi")],),
                  [["a.txt", "c.txt"]], normalize=groups_any_order),
                T("nothing duplicated", ([("a", "1"), ("b", "2")],), [], normalize=groups_any_order),
                T("groups as a list", ([("x", "same"), ("y", "same")],), [["x", "y"]], normalize=groups_any_order,
                  hidden=True, catches=GK_DICT),
            ],
            takeaway="Group, then filter the groups: the key is the content itself.",
        ),
        Problem(
            key="group-scrambled-names",
            role="review",
            title="Group scrambled names",
            statement="Group names that are rearrangements of each other (case matters). Order doesn't matter.",
            function="group_names",
            signature="def group_names(names: list[str]) -> list[list[str]]:",
            reference="def group_names(names):\n"
                      "    groups = {}\n"
                      "    for n in names:\n"
                      "        groups.setdefault(\"\".join(sorted(n)), []).append(n)\n"
                      "    return list(groups.values())\n",
            tests=[
                T("two groups", (["mary", "army", "yram", "tom"],), [["mary", "army", "yram"], ["tom"]],
                  normalize=groups_any_order),
                T("letter counts matter", (["aab", "abb"],), [["aab"], ["abb"]], normalize=groups_any_order,
                  hidden=True, catches=GK_NOT_CANONICAL),
            ],
        ),
        Problem(
            key="same-inbox",
            role="review",
            title="Same inbox",
            statement="Two email addresses reach the same inbox if they match after: lowercasing everything, removing "
                      "dots from the part before `@`, and dropping anything from a `+` up to the `@`. Group addresses "
                      "by inbox. Order doesn't matter.",
            function="group_inboxes",
            signature="def group_inboxes(emails: list[str]) -> list[list[str]]:",
            reference="def group_inboxes(emails):\n"
                      "    groups = {}\n"
                      "    for e in emails:\n"
                      "        name, domain = e.lower().split(\"@\")\n"
                      "        name = name.split(\"+\")[0].replace(\".\", \"\")\n"
                      "        groups.setdefault(name + \"@\" + domain, []).append(e)\n"
                      "    return list(groups.values())\n",
            tests=[
                T("three spellings of one inbox", (["Ana.Lee@x.com", "analee+news@x.com", "ANALEE@X.COM", "bo@x.com"],),
                  [["Ana.Lee@x.com", "analee+news@x.com", "ANALEE@X.COM"], ["bo@x.com"]], normalize=groups_any_order),
                T("groups, not a dict", (["a@b.c"],), [["a@b.c"]], normalize=groups_any_order, hidden=True,
                  catches=GK_DICT),
            ],
        ),
        Problem(
            key="same-tune",
            role="review",
            title="The same tune",
            statement="A tune is a list of notes, numbers 0 to 11. Playing it in another key adds the same amount to "
                      "every note, wrapping 11 around to 0. Group tunes that are the same tune in different keys. "
                      "Return groups of positions in the input; order doesn't matter.",
            function="group_tunes",
            signature="def group_tunes(tunes: list[list[int]]) -> list[list[int]]:",
            reference="def group_tunes(tunes):\n"
                      "    groups = {}\n"
                      "    for i, t in enumerate(tunes):\n"
                      "        key = tuple((b - a) % 12 for a, b in zip(t, t[1:]))\n"
                      "        groups.setdefault(key, []).append(i)\n"
                      "    return list(groups.values())\n",
            tests=[
                T("two transpositions of one tune", ([[0, 4, 7], [2, 6, 9], [0, 3, 7]],), [[0, 1], [2]],
                  normalize=groups_any_order),
                T("a list key won't hash", ([[1, 2], [5, 6]],), [[0, 1]], normalize=groups_any_order, hidden=True,
                  catches=GK_UNHASHABLE),
            ],
        ),
    ],
    drills=[
        Drill(
            key="gk-drill-anagram-groups",
            statement="Given a list of words, return them in groups where every word in a group uses exactly the same "
                      "letters.",
            choices=["Frequency counting", "Membership set", "Complement lookup"],
            signal='"In groups" of words with the same letters: a canonical key per word',
            wrong_signals=['"Exactly the same letters": compare the letter counts of every pair of words', '"A list of words": remember which words have been seen', '"Every word in a group": count the words per letter'],
            why="Equivalent items share a canonical key (sorted letters, or letter counts); collect by key.",
        ),
        Drill(
            key="gk-drill-log-lines",
            statement="Cluster log lines that are identical once their timestamps are removed.",
            choices=["Membership set", "Frequency counting", "Complement lookup"],
            signal='"Identical once timestamps are removed": the normalized line is the key',
            wrong_signals=['"Identical": a set tells you which lines repeat', '"Cluster": count how many times each line appears', '"Log lines": pair each line with the one just before it'],
            why="Stripping the timestamp is the key function; lines with the same key form a cluster.",
        ),
        Drill(
            key="gk-drill-customer-orders",
            statement="Given a list of orders, each with a customer ID, list each customer's orders together.",
            choices=["Frequency counting", "Complement lookup", "Membership set"],
            signal='"Each customer\'s orders together": collect items under a shared key',
            wrong_signals=['"Each customer": count the orders per customer', '"A customer ID": check whether each ID has been seen before', '"Together": pair each order with a matching order'],
            why="Collect, don't count: groups keyed by customer. (A total per customer would be counting, a near "
                "relative.)",
        ),
    ],
)


PATTERN = Pattern(
    key="arrays-hashing",
    name="Arrays & Hashing",
    status="consensus",
    aliases=["hashing", "hash map patterns", "hash set patterns"],
    idea="Trade memory for time: remember what you have seen, so each question about it is one O(1) lookup instead "
         "of a rescan.",
    sources=[("NeetCode roadmap", "https://github.com/aridepai17/NEETCODE-ROADMAP")],
    variants=[membership_set, frequency_counting, complement_lookup, grouping_by_key],
)
