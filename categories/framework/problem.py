"""the shape of a problem: a scenario split into parts that build on each other, each with its own tests"""

from dataclasses import dataclass, field

from .tests import TestCase


@dataclass
class Part:
    """one stage of a problem. Later parts extend the same code, so their runs include every earlier part's tests"""

    title: str
    statement: str  # markdown
    tests: list[TestCase]
    hints: list[str] = field(default_factory=list)


@dataclass
class Problem:
    key: str
    title: str
    difficulty: str  # easy | medium | hard
    summary: str  # one line for the problem list
    intro: str  # markdown: the scenario, shown above part 1
    parts: list[Part]
    starter: str  # code the editor starts with
    reference: str  # a full solution, the source of expected values for tests that don't spell them out
    discussion: list[str] = field(default_factory=list)  # tradeoff questions an interviewer would ask
    writeup: str = ""  # markdown: how the reference works and why, revealed on request
    tags: list[str] = field(default_factory=list)
    minutes: int = 60  # rough interview time budget

    def __post_init__(self):
        for i, p in enumerate(self.parts, 1):
            names = [t.name for t in p.tests]
            dupes = {n for n in names if names.count(n) > 1}
            if dupes:
                raise ValueError(f"{self.key} part {i}: duplicate test names {sorted(dupes)}")

    def tests_through(self, part, include_hidden=True):
        """tests for parts 1..part (1-based), earliest first"""
        return [(i + 1, t) for i, p in enumerate(self.parts[:part]) for t in p.tests if include_hidden or not t.hidden]

    def manifest(self):
        """everything the web page shows about this problem, without running any tests"""
        return {
            "key": self.key,
            "title": self.title,
            "difficulty": self.difficulty,
            "summary": self.summary,
            "intro": self.intro,
            "tags": self.tags,
            "minutes": self.minutes,
            "starter": self.starter,
            "reference": self.reference,
            "discussion": self.discussion,
            "writeup": self.writeup,
            "parts": [{
                "title": p.title,
                "statement": p.statement,
                "hints": p.hints,
                "tests": [t.summary() for t in p.tests],
            } for p in self.parts],
        }
