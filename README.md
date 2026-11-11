# implquest

Practice for the "small implementation" interview round (the Palantir style): you get a realistic scenario and build
a small system that has to pass an extensive test suite, then defend your design. The problems aren't algorithm
puzzles. They come in **parts** that extend the same code, the way an interviewer adds requirements once the first
version works, and some parts are open-ended (any valid answer passes, as long as it's good enough).

## Problems

| key | problem | parts |
| --- | --- | --- |
| `fulfillment` | **Fulfillment Center**: orders and stock, then load shipped orders onto as few trucks as possible (bin packing), with delivery routes and express orders | 4 |
| `rate-limiter` | **API Rate Limiter**: sliding-window limits per client, several rules at once, weighted requests, evicting idle clients | 4 |
| `kv-store` | **Transactional Key-Value Store**: value counts, nested transactions with rollback, ordered range scans | 3 |

Each problem also has discussion questions (the tradeoffs an interviewer would push on), hints, and a reference
solution with a writeup of its tradeoffs.

## Web version (the main way to use it)

A HackerRank-style page: the problem statement on the left, an editor on the right, test results underneath.
Python runs in your browser through [Pyodide](https://pyodide.org), so it's a static site with no server-side code.

```
./serve.py          # or: ./serve.py 8001 for another port
```

Then open http://localhost:8000. `serve.py` runs `build_web.py` and serves `web/` with browser caching turned off
(a plain `python3 -m http.server 8000 -d web` works too, after `python3 build_web.py`, but the browser may keep stale
files around).

- **Run samples** (Ctrl+Enter) runs the visible tests for the current part and every earlier part. **Submit**
  (Ctrl+Shift+Enter) adds the hidden tests. Passing a submit completes the part and unlocks the next one. Later
  parts stay hidden until you reach them, as in the interview.
- Failed tests show the step that went wrong, what was expected, the calls just before it, and anything you
  printed. Open-ended tests also show scores, such as your truck count next to the reference's count and the lower
  bound.
- **Console** runs any snippet with your classes in scope, for experimenting.
- **Notes** is for writing down your design and its tradeoffs; **Discussion** lists the questions to answer.
  **Solution** shows the reference and writeup once you choose to look.
- A timer per problem tracks how long you've spent. Code, notes, progress and timers are saved in your browser.

Time limits in the browser are 2.5× the terminal ones, because Python in WebAssembly runs slower. A test that runs
far past its limit is stopped by restarting Python.

## Terminal version

```
./implquest.py                                  # list problems
./implquest.py fulfillment                      # writes solutions/fulfillment.py from the starter, runs part 1's samples
./implquest.py fulfillment --part 2 --submit    # every test for parts 1-2, hidden ones included
./implquest.py fulfillment path/to/file.py      # use another file
./implquest.py --selftest                       # every reference solution passes its own tests
```

It needs only the standard library. `solutions/` is gitignored.

## How problems are built

`framework/` holds the structure, and `problems/` has one file per problem.

- **`Problem`** has the scenario intro, its `Part`s, the starter code, a reference solution (as source), discussion
  questions and the writeup. **`Part`** has a markdown statement, hints and test cases. Running part *n* runs the
  tests of parts 1..*n*.
- **`OpsTest`** constructs a class and calls methods in order, comparing each return value. Steps written as
  `(method, args, expected)` are checked against `expected`. Steps written as `(method, args)` get their expected
  value from the reference solution, so a big randomly generated test needs no hand-written answers: pass a function
  that builds the steps.
- **`ScenarioTest`** wraps a function `fn(ctx)` for checks that aren't "equal to X": validate that any packing is
  legal, compare against the reference's score with `ctx.metric(name, value, target=...)`, and so on. `ctx.new(cls)`
  and `ctx.new_reference(cls)` build the user's and the reference's objects. Use `ctx.check`/`ctx.fail` to report
  problems.
- Every test has a `time_limit` (seconds) and can be `hidden`. Scale tests are sized so that the intended approach
  finishes well inside the limit and the naive approach (rescanning, copying, re-sorting) doesn't.
- `framework/runner.py` loads solution source as a module and runs tests, returning plain dicts. The CLI and the
  browser (through `framework/web.py`) both use it.

To add a problem, write `problems/<name>.py` defining `PROBLEM = Problem(...)`, add it to `problems/__init__.py`,
then run `./implquest.py --selftest` and `python3 build_web.py`.
