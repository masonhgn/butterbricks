"""test cases. Each one runs against the user's loaded solution module and either returns or raises Fail.

Two kinds cover most implementation problems:
- OpsTest: build an object, call methods in order, compare each return value. Steps that leave out the expected
  value get it from the reference solution, so large generated tests need no hand-written answers.
- ScenarioTest: a function that drives the solution however it likes and checks properties of the result. This is
  for open-ended parts with many right answers (any valid packing, any order), and for scored targets via ctx.metric.
"""

import linecache
import re
import reprlib

REFERENCE = object()  # expected value placeholder: ask the reference solution


class _Any:
    def __repr__(self):
        return "ANY"


ANY = _Any()  # expected value placeholder: call it but don't check the result


class Unordered:
    """expected value for a list whose order doesn't matter"""

    def __init__(self, items):
        self.items = list(items)

    def matches(self, got):
        if not isinstance(got, (list, tuple, set, frozenset)):
            return False
        try:
            return sorted(map(repr, got)) == sorted(map(repr, self.items))
        except TypeError:
            return False

    def __repr__(self):
        return f"{self.items!r} (any order)"


class Fail(Exception):
    """a failed check, with extra lines of detail for the results panel"""

    def __init__(self, message, details=(), where=None):
        super().__init__(message)
        self.message = message
        self.details = list(details)
        self.where = where  # optional {"line", "frames"} pointing into the user's code, like runner.error_where


def shadowed_method(module, obj, name):
    """a Fail for an instance attribute that hides a method of the same name (self.stock = {} next to def stock),
    which otherwise surfaces as a bare "'dict' object is not callable" raised from test code, not the user's"""
    value = getattr(obj, name)
    kind = type(value).__name__
    assign = re.compile(rf"\bself\.{re.escape(name)}\s*(?::[^=]*)?=(?!=)")
    lines = linecache.getlines(getattr(module, "__file__", "") or "")
    lineno = next((i for i, line in enumerate(lines, 1) if assign.search(line)), None)
    if callable(getattr(type(obj), name, None)):
        message = f"self.{name} is a {kind}, which hides your {name}() method"
        details = [f"Your class has a method {name}(), but self.{name} = ... stores a {kind} on the object under the same",
                   f"name, and the object's own attribute wins. So obj.{name}(...) finds the {kind} and tries to call it.",
                   f"Rename the attribute, for example to self._{name}, or give it a more specific name."]
    else:
        message = f"self.{name} is a {kind}, but the tests call {name}() as a method"
        details = [f"The tests call obj.{name}(...), and your class has no {name}() method, only the attribute self.{name}.",
                   f"Add the method, and rename the attribute (for example to self._{name}) so it doesn't hide it."]
    if lineno:
        details[:0] = [f"  line {lineno}:  {lines[lineno - 1].strip()}", ""]
    return Fail(message,
                details, {"line": lineno, "frames": []} if lineno else None)


_short = reprlib.Repr()
_short.maxstring = 60
_short.maxother = 60
_short.maxlist = _short.maxtuple = _short.maxset = _short.maxdict = 8
_short.maxlevel = 3


def show(value):
    """a repr that stays readable for big values"""
    return _short.repr(value)


def show_call(method, args, kwargs=None):
    parts = [show(a) for a in args] + [f"{k}={show(v)}" for k, v in (kwargs or {}).items()]
    return f"{method}({', '.join(parts)})"


def fresh(v):
    """a deep copy of plain data (much faster than copy.deepcopy, which matters inside timed tests)"""
    if isinstance(v, dict):
        return {k: fresh(x) for k, x in v.items()}
    if isinstance(v, list):
        return [fresh(x) for x in v]
    if isinstance(v, tuple):
        return tuple(fresh(x) for x in v)
    if isinstance(v, set):
        return set(v)
    return v


def same(got, want):
    if want is ANY:
        return True
    if isinstance(want, Unordered):
        return want.matches(got)
    return _norm(got) == _norm(want)


def _norm(v):
    """tuples and lists compare equal, recursively, so a solution may return either"""
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    if isinstance(v, dict):
        return {k: _norm(x) for k, x in v.items()}
    return v


class Context:
    """what a test sees: the user's module, the reference module, and a place to record metrics"""

    def __init__(self, solution, reference):
        self.solution = solution
        self.reference = reference
        self.metrics = []
        self.notes = []

    def new(self, cls, *args, **kwargs):
        """instantiate one of the user's classes"""
        return construct(self.solution, cls, args, kwargs)

    def new_reference(self, cls, *args, **kwargs):
        return construct(self.reference, cls, args, kwargs, where="the reference solution")

    def fail(self, message, details=()):
        raise Fail(message, details)

    def check(self, condition, message, details=()):
        if not condition:
            raise Fail(message, details)

    def note(self, line):
        """an informational line shown with the result, pass or fail"""
        self.notes.append(line)

    def metric(self, name, value, target=None, better="lower", context=""):
        """record a number. With a target, being worse than it fails the test"""
        ok = True
        if target is not None:
            ok = value <= target if better == "lower" else value >= target
        self.metrics.append({"name": name, "value": value, "target": target, "better": better, "ok": ok, "context": context})
        if not ok:
            sign = "≤" if better == "lower" else "≥"
            raise Fail(f"{name} is {value}, the target is {sign} {target}" + (f" ({context})" if context else ""))


def construct(module, cls, args, kwargs, where="your solution"):
    if not hasattr(module, cls):
        raise Fail(f"{where} has no class named {cls}")
    obj = getattr(module, cls)(*args, **kwargs)
    for name, value in getattr(obj, "__dict__", {}).items():
        if not name.startswith("_") and callable(getattr(type(obj), name, None)) and not callable(value):
            raise shadowed_method(module, obj, name)
    return obj


class TestCase:
    kind = "scenario"

    def __init__(self, name, *, description="", hidden=False, time_limit=2.0):
        self.name = name
        self.description = description
        self.hidden = hidden
        self.time_limit = time_limit  # seconds; going over fails the test

    def prepare(self, ctx):
        """untimed setup, such as asking the reference for expected values"""

    def execute(self, ctx):
        raise NotImplementedError

    def preview(self):
        """lines describing the test's input, shown for sample tests"""
        return []

    def summary(self):
        return {
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
            "hidden": self.hidden,
            "time_limit": self.time_limit,
            "preview": [] if self.hidden else self.preview(),
        }


class Step:
    """one method call in an OpsTest"""

    def __init__(self, method, args=(), expect=REFERENCE, kwargs=None):
        self.method = method
        self.args = tuple(args)
        self.kwargs = kwargs or {}
        self.expect = expect

    @classmethod
    def of(cls, item):
        """steps can be written as (method, args) or (method, args, expected) tuples"""
        if isinstance(item, Step):
            return item
        method, args, *rest = item
        if not isinstance(args, (list, tuple)):
            args = (args,)
        return cls(method, args, rest[0] if rest else REFERENCE)

    def label(self):
        return show_call(self.method, self.args, self.kwargs)

    def call(self, obj):
        """call on obj with fresh copies of any mutable arguments, so neither side can change the other's inputs"""
        args, kwargs = self.args, self.kwargs
        if any(isinstance(a, (list, dict, set)) for a in (*args, *kwargs.values())):
            args, kwargs = fresh(args), fresh(kwargs)
        return getattr(obj, self.method)(*args, **kwargs)


class OpsTest(TestCase):
    """construct `cls(*args)`, then run the steps in order and compare every return value"""

    kind = "ops"

    def __init__(self, name, steps, *, cls, args=(), **kw):
        super().__init__(name, **kw)
        self.cls = cls
        self.args = tuple(args)
        self._steps = steps  # a list, or a function returning one (for big generated tests)
        self._built = None

    def steps(self):
        if self._built is None:
            raw = self._steps() if callable(self._steps) else self._steps
            self._built = [Step.of(s) for s in raw]
        return self._built

    def preview(self):
        if callable(self._steps):
            return []
        lines = [f"obj = {show_call(self.cls, self.args)}"]
        for s in self.steps():
            want = "" if s.expect is REFERENCE else f"  →  {s.expect!r}"
            lines.append(f"obj.{s.label()}{want}")
        return lines

    def prepare(self, ctx):
        steps = self.steps()
        if all(s.expect is not REFERENCE for s in steps):
            self._want = [s.expect for s in steps]
            return
        obj = ctx.new_reference(self.cls, *self.args)
        self._want = [s.call(obj) if s.expect is REFERENCE else s.expect for s in steps]

    def execute(self, ctx):
        steps = self.steps()
        want = self._want
        obj = ctx.new(self.cls, *self.args)
        history = []
        for i, (s, w) in enumerate(zip(steps, want)):
            if not hasattr(obj, s.method):
                raise Fail(f"{self.cls} has no method {s.method}")
            if not callable(getattr(obj, s.method)):
                raise shadowed_method(ctx.solution, obj, s.method)
            got = s.call(obj)
            if not same(got, w):
                details = [f"step {i + 1:,} of {len(steps):,}: obj.{s.label()}", f"  expected  {show(w)}", f"  got       {show(got)}"]
                if history:
                    details += ["", "the steps just before it:"] + history[-4:]
                raise Fail(f"wrong result at step {i + 1:,}", details)
            history.append(f"  {i + 1:>6,}  obj.{s.label()}  →  {show(got)}")
        ctx.note(f"{len(steps):,} calls checked")


class ScenarioTest(TestCase):
    """runs fn(ctx), which drives the solution and raises Fail (via ctx.check / ctx.fail / ctx.metric) on a problem"""

    def __init__(self, name, fn, *, sample=(), **kw):
        super().__init__(name, **kw)
        self.fn = fn
        self.sample = list(sample)  # optional lines showing the input, for sample tests

    def preview(self):
        return self.sample

    def execute(self, ctx):
        self.fn(ctx)


class CallTest(TestCase):
    """call one function of the user's code with some arguments and compare the result: the shape of most pattern
    problems. `args` is a tuple, or a function returning one (for big generated inputs). Leave `expect` out to take it
    from the reference solution. `normalize`, if given, is applied to both sides before comparing (to sort groups whose
    order doesn't matter, say). `catches` names the common mistake the test is built to catch; a failure says so"""

    kind = "call"

    def __init__(self, name, args, expect=REFERENCE, *, function=None, normalize=None, catches="", **kw):
        super().__init__(name, **kw)
        self._args = args
        self._built = None
        self.expect = expect
        self.function = function  # the problem fills this in
        self.normalize = normalize
        self.catches = catches
        self.shown_expect = None  # the expected value as shown in a sample's preview, filled in at build time

    def args(self):
        if self._built is None:
            built = self._args() if callable(self._args) else self._args
            self._built = tuple(built) if isinstance(built, (list, tuple)) else (built,)
        return self._built

    def label(self):
        return show_call(self.function, self.args())

    def preview(self):
        if callable(self._args):
            return []
        want = self.shown_expect if self.expect is REFERENCE else show(self.expect)
        return [self.label() + (f"  →  {want}" if want is not None else "")]

    def summary(self):
        return {**super().summary(), "catches": self.catches}

    def prepare(self, ctx):
        if self.expect is REFERENCE:
            self._want = getattr(ctx.reference, self.function)(*fresh(self.args()))
        else:
            self._want = self.expect

    def execute(self, ctx):
        fn = getattr(ctx.solution, self.function, None)
        if not callable(fn):
            raise Fail(f"your code has no function named {self.function}",
                       [f"The tests call {self.function}(...). Check the name and that it's defined at the top level."])
        got = fn(*fresh(self.args()))
        want = self._want
        g, w = (self.normalize(got), self.normalize(want)) if self.normalize else (got, want)
        if not same(g, w):
            details = [self.label(), f"  expected  {show(want)}", f"  got       {show(got)}"]
            if self.catches:
                details += ["", f"This test is built to catch a common mistake: {self.catches}"]
            raise Fail("wrong answer", details)
