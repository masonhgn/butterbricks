"""the shape of the Patterns category: a Pattern holds Variants (the "bricks"), and a Variant holds Problems, each
with a role in the variant's sequence, and Drills. docs/patterns-taxonomy.md explains every field and the naming rule
behind every name.

The checks here enforce the authoring checklist, so a variant that's missing a role, a common mistake without a test
that catches it, or a completion without blanks fails to load instead of shipping half-built."""

from dataclasses import dataclass, field

from framework.tests import CallTest

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


@dataclass
class Problem:
    key: str  # unique across the whole category: it's the problem's URL and its saved-progress key
    role: str
    title: str
    statement: str  # markdown; the sample tests are shown under it as examples
    function: str  # the function the learner writes
    signature: str  # its first line, like "def has_repeat(badges: list[str]) -> bool:"
    reference: str  # a full solution: the source of expected values and the code an example steps through
    tests: list
    starter: str = ""  # defaults to the signature and `pass`; a completion leaves BLANKs in the reference instead
    hints: list = field(default_factory=list)
    changes: str = ""  # a twin's or variation's one difference from the problem before it
    takeaway: str = ""  # shown once it's solved: what to notice
    trace_args: tuple = None  # an example's input, which the stepper walks through
    notes: dict = field(default_factory=dict)  # an example's code fragment -> what that line is doing
    predict: dict = field(default_factory=dict)  # an example's code fragment -> a yes/no expression to predict there

    def __post_init__(self):
        if self.role not in ROLES:
            raise ValueError(f"{self.key}: unknown role {self.role!r}")
        if not self.starter:
            self.starter = f"{self.signature}\n    pass\n"
        names = [t.name for t in self.tests]
        if len(set(names)) != len(names):
            raise ValueError(f"{self.key}: duplicate test names")
        for t in self.tests:
            if isinstance(t, CallTest):
                t.function = self.function
        if self.role == "example" and self.trace_args is None:
            raise ValueError(f"{self.key}: a worked example needs trace_args, the input its stepper walks through")
        if self.role == "completion" and BLANK not in self.starter:
            raise ValueError(f"{self.key}: a completion's starter must leave {BLANK} blanks to fill in")
        if self.role in ("twin", "variation") and not self.changes:
            raise ValueError(f"{self.key}: a {self.role} must say what changes")
        if self.role != "example" and not any(not t.hidden for t in self.tests):
            raise ValueError(f"{self.key}: needs at least one sample (visible) test")


@dataclass
class Drill:
    """a statement and two questions: which variant is this, and what in the statement told you"""

    key: str
    statement: str
    choices: list  # wrong variant names, ideally the variant's near-misses (the right one is added automatically)
    signal: str  # what in the statement gives it away
    wrong_signals: list
    why: str  # shown after answering


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
    near_misses: list
    mistakes: list  # each must be caught by at least one test's `catches`
    prerequisites: list  # variant keys
    problems: list
    drills: list

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
        # problems in the order they're met: the sequence, then the reviews
        self.problems.sort(key=lambda p: ROLES.index(p.role))

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

    def __post_init__(self):
        keys = {v.key for v in self.variants}
        for v in self.variants:
            for d in v.drills:
                if v.name in d.choices:
                    raise ValueError(f"{d.key}: the right answer is added automatically; don't list {v.name!r}")
            unknown = [k for k in v.prerequisites if k not in keys and "." not in k]
            if unknown:
                raise ValueError(f"{v.key}: unknown prerequisites {unknown}")
