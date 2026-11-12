"""the shape of a brick-based category (Patterns, Structures): a Pattern (a family) holds Variants (techniques, the
"bricks"), and a Variant holds Problems, each with a role in the variant's sequence, and Drills.
docs/patterns-taxonomy.md and docs/structures-taxonomy.md explain every field and the naming rule behind every name.

A problem is a function to write (Patterns) or a class (Structures); class problems also list their operations with
target costs, and can carry a design card. A worked example is either a code trace (functions: trace_args; classes:
trace_script) or, for classes, a worked design: questions about the design, then the trace.

The checks here enforce the authoring checklist, so a variant that's missing a role, a common mistake without a test
that catches it, or a completion without blanks fails to load instead of shipping half-built."""

import re
from dataclasses import dataclass, field

from .tests import CallTest, CostTest, OpsTest, ScenarioTest

# the order a variant's problems are met in; review twins come back on a spaced schedule instead
SEQUENCE = ["example", "completion", "twin", "variation", "stretch"]
ROLES = SEQUENCE + ["review"]
ROLE_LABELS = {
    "example": "Worked example",
    "completion": "Fill in the blanks",
    "twin": "Twin",
    "variation": "Variation",
    "stretch": "Stretch",
    "review": "Review",
}
NAME_STATUS = {"consensus", "textbook", "ours"}
BLANK = "___"  # what a completion problem's starter leaves for the learner to fill in
TAG = re.compile(r"\s*# @([a-z][a-z0-9-]*)\s*$")  # a line's move tag, like  # @ask


def move_tags(code):
    """the move each line is tagged with: {line number: key}"""
    out = {}
    for i, line in enumerate(code.splitlines(), 1):
        m = TAG.search(line)
        if m:
            out[i] = m.group(1)
    return out


def strip_tags(code):
    return "\n".join(TAG.sub("", line) for line in code.split("\n"))


@dataclass
class Step:
    """one step of a worked design: some text, and optionally a question to think about, whose reasoning is shown when
    asked for (no options to pick from: you think it through, then compare)"""

    text: str  # markdown
    ask: str = ""
    why: str = ""  # the reasoning, revealed on request


@dataclass
class Move:
    """one named step of a pattern (a subgoal label). Code lines that do this step end with the tag `# @<key>`, and
    every place the code is shown tints those lines in the move's color, so the pattern stands out from the problem"""

    key: str
    label: str
    text: str


@dataclass
class Example:
    """a solved problem in a lesson: read-only, run to check it, and playable in the visualizer"""

    title: str
    statement: str
    function: str
    code: str  # move-tagged lines; problem-specific lines untagged
    cases: list  # (args tuple, expected) pairs the code must produce
    trace_args: tuple
    differs: str = ""  # how this one differs from the template
    classic: str = ""  # the well-known problem it matches
    notes: dict = field(default_factory=dict)  # code fragment -> what that line is doing
    viz: dict = field(default_factory=dict)  # hints for the visualizer (see web/visual.js)
    problem: str = ""  # the key of the brick problem this example is, if any


@dataclass
class Lesson:
    """a subpattern's Learn page: what it teaches, why the obvious code is slow, the steps, why it works, worked examples,
    Python idioms and mistakes with code. docs/patterns-taxonomy.md ("Lesson format") explains the layout"""

    goals: list
    problem: str  # the question it answers, in plain words (markdown)
    brute_force: str  # the obvious code; it runs, and agrees with examples[0]
    brute_cost: str
    moves: list
    holds: str  # what the table means at every step
    why: list  # [at the start, after each step, at the end]
    examples: list
    cost_why: str
    toolkit: list = field(default_factory=list)  # (label, code, note) triples
    mistake_code: dict = field(default_factory=dict)  # mistake -> (wrong code, right code)


@dataclass
class PlannedVariant:
    """a subpattern on the map that isn't built yet"""

    name: str
    question: str  # "You need to know…"
    keep: str
    line: str  # the tell-tale line of code
    status: str = "ours"
    aliases: list = field(default_factory=list)
    classic: str = ""


@dataclass
class Design:
    """the reference design card: what to keep, what must stay true, and each operation's cost"""

    state: list  # one line per field, like "items: list of tickets, in no particular order"
    invariant: str
    costs: dict  # operation -> cost, like {"add": "O(1)"}
    checks: list = field(default_factory=list)  # the key points, as a checklist to compare your design with


@dataclass
class Problem:
    key: str  # unique across the whole category: it's the problem's URL and its saved-progress key
    role: str
    title: str
    statement: str  # markdown; the sample tests are shown under it as examples
    function: str  # the function or class the learner writes
    signature: str  # its first line, or for a class its skeleton's first line
    reference: str  # a full solution: the source of expected values and the code an example steps through
    tests: list
    starter: str = ""  # defaults to the signature and `pass`; a completion leaves BLANKs in the reference instead
    hints: list = field(default_factory=list)
    changes: str = ""  # a twin's or variation's one difference from the problem before it
    takeaway: str = ""  # shown once it's solved: what to notice
    kind: str = "function"  # function | class
    operations: list = field(default_factory=list)  # class problems: (signature, target cost) pairs
    design: Design = None  # class problems: the reference design card
    walkthrough: list = field(default_factory=list)  # a worked design's Steps, before its trace
    trace_args: tuple = None  # a function example's input, which the stepper walks through
    trace_init: tuple = ()  # a class example's constructor arguments
    trace_script: list = None  # a class example's operations, as (method, args) pairs, which the stepper walks through
    notes: dict = field(default_factory=dict)  # an example's code fragment -> what that line is doing
    viz: dict = field(default_factory=dict)  # hints for the visualizer (see web/visual.js)

    def __post_init__(self):
        if self.role not in ROLES:
            raise ValueError(f"{self.key}: unknown role {self.role!r}")
        if self.kind not in ("function", "class"):
            raise ValueError(f"{self.key}: kind must be function or class")
        if not self.starter:
            self.starter = f"{self.signature}\n    pass\n"
        names = [t.name for t in self.tests]
        if len(set(names)) != len(names):
            raise ValueError(f"{self.key}: duplicate test names")
        for t in self.tests:
            if isinstance(t, CallTest):
                t.function = self.function
            if isinstance(t, (OpsTest, CostTest, ScenarioTest)) and not t.cls:
                t.cls = self.function
        if self.role == "example":
            if self.kind == "function" and self.trace_args is None:
                raise ValueError(f"{self.key}: a worked example needs trace_args, the input its stepper walks through")
            if self.kind == "class" and self.trace_script is None:
                raise ValueError(f"{self.key}: a worked example needs trace_script, the operations its stepper walks through")
        if self.role == "completion" and BLANK not in self.starter:
            raise ValueError(f"{self.key}: a completion's starter must leave {BLANK} blanks to fill in")
        if self.role in ("twin", "variation") and not self.changes:
            raise ValueError(f"{self.key}: a {self.role} must say what changes")
        if self.role != "example" and not any(not t.hidden for t in self.tests):
            raise ValueError(f"{self.key}: needs at least one sample (visible) test")
        if self.kind == "class" and self.role != "example" and not self.operations:
            raise ValueError(f"{self.key}: a class problem lists its operations and their target costs")


@dataclass
class Drill:
    """a statement and two questions: which variant is this, and what in the statement told you"""

    key: str
    statement: str
    choices: list  # the wrong answers, ideally near-misses (the right one is added automatically)
    signal: str  # what in the statement gives it away
    wrong_signals: list
    why: str  # shown after answering
    question: str = ""  # defaults to the category's ("Which pattern is this?")
    answer: str = ""  # defaults to the variant's name


@dataclass
class Variant:
    key: str
    name: str
    status: str  # consensus | textbook | ours: how the name was chosen
    aliases: list
    sources: list  # (label, url) pairs
    idea: str
    invariant: str
    template: str
    complexity: str
    signals: list
    near_misses: list  # kept for the docs; not shown on the page
    mistakes: list  # each must be caught by at least one test's `catches`
    prerequisites: list  # variant keys
    problems: list
    drills: list
    reference_table: list = field(default_factory=list)  # optional (operation, cost, note) rows, for Learn
    lesson: Lesson = None  # the full Learn page; without one, Learn shows the reference card

    def __post_init__(self):
        if self.status not in NAME_STATUS:
            raise ValueError(f"{self.key}: name status must be one of {sorted(NAME_STATUS)}")
        roles = [p.role for p in self.problems]
        for role in SEQUENCE:
            if roles.count(role) != 1:
                raise ValueError(f"{self.key}: needs exactly one {role} problem, has {roles.count(role)}")
        if roles.count("review") < 3:
            raise ValueError(f"{self.key}: needs at least three review problems")
        if len(self.drills) < 3:
            raise ValueError(f"{self.key}: needs at least three drills")
        caught = {t.catches for p in self.problems for t in p.tests if getattr(t, "catches", "")}
        missing = [m for m in self.mistakes if m not in caught]
        if missing:
            raise ValueError(f"{self.key}: no test catches these common mistakes: {missing}")
        for d in self.drills:
            if not d.answer:
                d.answer = self.name
            if d.answer in d.choices:
                raise ValueError(f"{d.key}: the right answer is added automatically; don't list {d.answer!r}")
        # problems in the order they're met: the sequence, then the reviews
        self.problems.sort(key=lambda p: ROLES.index(p.role))
        if self.lesson:
            self._check_lesson()

    def _check_lesson(self):
        L = self.lesson
        moves = [m.key for m in L.moves]
        if len(set(moves)) != len(moves) or not 2 <= len(moves) <= 4:
            raise ValueError(f"{self.key}: a lesson has 2 to 4 moves with distinct keys")
        def tags_ok(code, where):
            unknown = set(move_tags(code).values()) - set(moves)
            if unknown:
                raise ValueError(f"{self.key}: {where} tags unknown moves {sorted(unknown)}")
            return set(move_tags(code).values())
        missing = set(moves) - tags_ok(self.template, "the template")
        if missing:
            raise ValueError(f"{self.key}: the template doesn't show the moves {sorted(missing)}")
        if len(L.examples) < 2:
            raise ValueError(f"{self.key}: a lesson needs at least two worked examples")
        for ex in L.examples:
            if len(tags_ok(ex.code, f"example {ex.title!r}")) < 2:
                raise ValueError(f"{self.key}: example {ex.title!r} should show at least two of the moves")
            if not ex.cases:
                raise ValueError(f"{self.key}: example {ex.title!r} needs cases to check it against")
        for p in self.problems:
            if p.role == "example":
                tags_ok(p.reference, f"problem {p.key}")
        if len(L.why) != 3:
            raise ValueError(f"{self.key}: why is [at the start, after each step, at the end]")
        unknown = [m for m in L.mistake_code if m not in self.mistakes]
        if unknown:
            raise ValueError(f"{self.key}: mistake_code for mistakes that aren't listed: {unknown}")

    def sequence(self):
        return [p for p in self.problems if p.role in SEQUENCE]

    def reviews(self):
        return [p for p in self.problems if p.role == "review"]


@dataclass
class Pattern:
    key: str
    name: str
    status: str
    aliases: list
    idea: str
    variants: list
    sources: list = field(default_factory=list)
    planned: list = field(default_factory=list)  # PlannedVariants (or names) still to come, shown as bricks not yet laid
    overview: str = ""  # markdown for the pattern's overview page, above its map
    map_rows: list = field(default_factory=list)  # (question, keep, variant key, tell-tale line) for built variants


def check_category(patterns):
    """what can only be checked across a whole category: unique problem keys, and prerequisites that exist"""
    variants = {v.key for p in patterns for v in p.variants}
    keys = [x.key for p in patterns for v in p.variants for x in v.problems]
    dupes = {k for k in keys if keys.count(k) > 1}
    if dupes:
        raise ValueError(f"problem keys used twice: {sorted(dupes)}")
    for p in patterns:
        for v in p.variants:
            unknown = [k for k in v.prerequisites if k not in variants]
            if unknown:
                raise ValueError(f"{v.key}: unknown prerequisites {unknown}")
    return patterns


# the names Structures uses for the same things
Family = Pattern
Technique = Variant
