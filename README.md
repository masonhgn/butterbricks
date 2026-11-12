# Butterbricks

Interview practice, laid one brick at a time: [butterbricks.org](https://butterbricks.org).

One list of problems, sorted into categories:

- **Patterns**: algorithm patterns, laid one brick at a time. Each brick (a *variant*, like "membership set") is one
  small idea: its Learn page teaches it with solved examples you can play step by step in a visualizer, then you step
  through a worked example, fill in its key lines, and solve a twin (same structure, new story), a variation (one
  change) and a stretch. Laid bricks come back for review after 1, 3, 7 and 21 days.
  `docs/patterns-taxonomy.md` has the model, the naming rule and the plan; Arrays & Hashing is built.
- **Structures**: designing data structures. Given what a class must do and how fast, choose what to store so every
  operation is cheap. Tests check answers and, separately, how each operation's time grows with the size of the
  structure, so correct code with the wrong structure fails, naming the slow operation. Each problem has a design card
  (what you'll keep, the invariant, each operation's cost) to fill in before coding. `docs/structures-taxonomy.md` has
  the model and plan; Building blocks and the first cross-indexed technique are built.
- **SQL**: 78 challenges in 10 levels, from `SELECT *` to window functions, data changes and multi-step boss
  problems, against a real SQLite database of a small online store (customers, orders, products, employees).
- **Implementation**: the "small implementation" interview round. You get a realistic scenario, build a small system
  in Python that has to pass an extensive test suite, then defend your design. Problems come in parts that extend the
  same code, the way an interviewer adds requirements once the first version works.

Answers are checked in the browser (SQLite through [sql.js](https://sql.js.org), Python through
[Pyodide](https://pyodide.org)). The server, a small Flask app, serves the site and keeps accounts and saved
progress.

## Running it locally

```
./serve.py          # or: ./serve.py 8001 for another port
```

Then open http://localhost:8000. `serve.py` (run through [uv](https://docs.astral.sh/uv/), which installs Flask)
runs `build.py`, which exports each category's data into `web/` and writes `web/catalog.json`, then starts `app.py`.
The local database is `instance/butterbricks.db` and the invite code is `dev`. Python changes (problems, challenges,
the test framework) need a rebuild: restart `serve.py` or run `./build.py`.

## Accounts

Anyone can practice without an account: code, drafts and notes are saved in the browser. **Submitting needs an
account**: Submit on an implementation problem, and checking a SQL answer (signed out, a query still runs so you can
explore the data). Signing up takes an invite code, set as the `INVITE_CODE` secret.

A signed-in browser sends every change to the account a couple of seconds after it happens, and pulls the account's
saves when a page loads, so progress follows you between browsers. The first time you sign in on a browser, what you
saved there joins the account (solved problems are combined; for code, the account's copy wins). Signing out clears
the browser's copy.

The server never runs your code; it stores the site's `butterbricks:*` localStorage keys per user (`app.py`).
Passwords are hashed with scrypt, sessions are signed HttpOnly cookies, sign-in is throttled, and state-changing
requests must be same-origin JSON.

## Profiles and XP

Every solve earns XP: a SQL challenge is worth 10 XP times its level (Level 1 is 10, Level 10 is 100), an
implementation part 100 XP, plus 150 for finishing a whole problem. Each level takes 100 XP more than the last (level
2 at 100, 3 at 300, 4 at 600, ...), with titles from Fresh Cream to Butter Legend. The header shows your level, and
leveling up announces itself.

`/profile/` shows your level and XP, problems solved, SQL progress by level, your implementation problems, your day
streak, time spent, and recent solves. Solves are logged with their dates from the moment profiles existed; XP is
computed from your saved progress, so older solves count too. It's all derived from the synced saves
(`butterbricks:activity` holds the solve log), so there's nothing extra on the server.

## The site

The home page lists every problem, tagged by category, with a search box (`/` focuses it; it searches titles,
levels, summaries and tags) and a filter per category. Opening a problem shows its category's page, whose sidebar lists
that category's problems; a link like `/sql/#distinct_categories` or `/implementation/#kv-store` opens one directly.
Drag the dividers to resize the panes.

### Patterns

- `/patterns/` is the wall: one row of bricks per pattern (foundation at the bottom) and the review queue.
  `/patterns/#pattern/<key>` is a pattern's overview and map of its subpatterns; `/patterns/#<problem>` opens a problem.
- **Learn** is the subpattern's lesson: what you'll learn, the brute force and why it's slow, the steps ("moves") of
  the pattern in color, why it works, three worked examples tinted by move and playable in the visualizer, Python
  idioms, cost, signals, and each common mistake as wrong and right code. `docs/patterns-taxonomy.md` section 5 has
  the format. A subpattern's worked example opens on Learn the first time.
- The **visualizer** (`web/visual.js`) plays a trace recorded by running the code (`categories/framework/trace.py`),
  so it shows exactly what Python did: lists as cells with the loop's position, sets as hash-table buckets with each
  lookup, dicts as tables, objects as their fields, with changes highlighted. Edit the input and press Run to trace
  your own (it runs in the page's Python).
- **Fill in the blanks** problems leave `___` in the key lines. Every common mistake has a test built to catch it,
  and a failing one says which mistake it caught.
- A brick is **laid** when its variation or stretch is solved without revealing that problem's solution.

### Structures

The same wall, bricks, reviews and visualizer as Patterns, on the same engine (`web/bricks.js`), plus:

- An **operations table** on every problem: each method and the cost it must have.
- A **design card**: what you'll keep, the invariant, each operation's cost. It's saved as you type; ours shows once
  you've solved the problem (opening it earlier counts as revealing the solution).
- **Worked designs**: a brick's first problem builds the design one question at a time (which operation is the
  bottleneck, what fixes it, what must stay true), then unblurs the code to step through, with every field of the
  object shown as it changes.
- **Cost tests** (`CostTest` in `categories/framework/tests.py`): each operation is timed at two sizes 10× apart; time
  per call that grows with the size fails, with the numbers. Timing can't tell O(log n) from O(1), so targets only say
  which operations must not grow.

### SQL

- The **Challenge** tab has the prompt and hints, **Lesson** the level's lesson (a new level opens on it), **Schema**
  every table's columns, and **Solution** a reference answer once you choose to look.
- **Run** (Ctrl+Enter) checks your query by comparing its result to the reference solution's, so any correct query
  passes. Column names and aliases aren't checked; column order is, and so is row order when the challenge asks for
  sorting. Ctrl+Space autocompletes table and column names.
- Every run uses a fresh in-memory copy of the data, so `DELETE FROM customers;` can't break anything. Queries that
  take longer than 5 seconds are stopped.
- Results show in a spreadsheet-style grid with sheet tabs: `Result`, `Expected` (from **Expected output**), the
  tables the challenge uses, and `+` to open any other table. Click a column header to sort, click a cell to see its
  full value, double-click one to paste it into the editor, and use "Filter rows…" to search. For challenges that
  change data, the tables your statements touched show their changed state (marked •, changed rows highlighted).
- **Export** and **Import** move SQL progress as a `progress.json`, the format the terminal version uses.

### Implementation

| key | problem | parts |
| --- | --- | --- |
| `fulfillment` | **Fulfillment Center**: orders and stock, then load shipped orders onto as few trucks as possible (bin packing), with delivery routes and express orders | 4 |
| `rate-limiter` | **API Rate Limiter**: sliding-window limits per client, several rules at once, weighted requests, evicting idle clients | 4 |
| `kv-store` | **Transactional Key-Value Store**: value counts, nested transactions with rollback, ordered range scans | 3 |

- **Run samples** (Ctrl+Enter) runs the visible tests for the current part and every earlier part. **Submit**
  (Ctrl+Shift+Enter) adds the hidden tests. Passing a submit completes the part and unlocks the next one. Later
  parts stay hidden until you reach them, as in the interview.
- When a test raises, the line it came from is marked in red in the editor, and the result lists every variable in
  each of your functions the error passed through, `self`'s fields included. Failed tests also show the step that
  went wrong, what was expected, and the calls just before it. Open-ended tests show scores, such as your truck count
  next to the reference's and the lower bound.
- **Console** runs any snippet with your classes in scope. **Notes** is for your design and its tradeoffs;
  **Discussion** lists the questions an interviewer would push on; **Solution** shows the reference and its writeup.
- A timer per problem tracks how long you've spent. Time limits are 2.5× the terminal ones, because Python in
  WebAssembly runs slower, and a test that runs far past its limit is stopped by restarting Python.

## In the terminal

```
./butterbricks.py                                              # the categories
./butterbricks.py patterns                                     # the pattern problems
./butterbricks.py patterns badge-scanned-twice                 # writes categories/patterns/solutions/<problem>.py, runs every test
./butterbricks.py structures raffle                            # the same, for a Structures problem
./butterbricks.py sql                                          # the SQL challenges, one after another
./butterbricks.py implementation                               # the implementation problems
./butterbricks.py implementation fulfillment                   # writes categories/implementation/solutions/fulfillment.py, runs part 1's samples
./butterbricks.py implementation fulfillment --part 2 --submit # every test for parts 1-2, hidden ones included
./butterbricks.py selftest                                     # every category's reference solutions pass
```

The SQL terminal highlights SQL as you type, Tab completes names, and Enter runs once the query ends with `;`. Its
commands are `.hint` `.expected` `.solution` `.lesson` `.prompt` `.tables` `.schema [table]` `.list` `.goto N`
`.clear` `.reset` `.help` `.quit`; progress is saved in `categories/sql/progress.json`, and
`sqlite3 categories/sql/store.db` opens the same data in any SQLite tool.

## Layout

```
app.py                     the server: the site, accounts and saves
build.py, serve.py         build the site's data; build and run it locally
butterbricks.py            the terminal version
web/                       the site: index.html (home: every problem), common.css/common.js (shared: the sidebar, accounts, sync,
                           editor, the pixel look), logo.svg
tools/pixelart.py          draws the logo
web/<category>/            each category's page; bricks.js/bricks.css are the engine for Patterns and Structures, and
                           pyworker.js/pyrun.js run Python for them and for Implementation
categories/framework/      the test framework shared by Patterns and Implementation: CallTest, OpsTest,
                           ScenarioTest, and the runner (in the terminal and, through Pyodide, the browser)
categories/framework/      also: curriculum.py (the brick model), trace.py (worked-example traces) and
                           curriculum_tools.py (build, self-test and terminal for brick-based categories)
categories/patterns/       bricks/ (one file per pattern)
categories/structures/     bricks/ (one file per family)
categories/sql/            challenges.py (lessons and challenges), dataset.py (the data), engine.py (the checker)
categories/implementation/ problems/ (one file each)
```

**Adding a pattern**: follow `docs/patterns-taxonomy.md`: write `categories/patterns/bricks/<pattern>.py` with a
`Pattern` of `Variant`s, each with a `Lesson`, one example, completion, twin, variation and stretch, three or more
reviews and three or more drills; add it to `bricks/__init__.py`; run `./butterbricks.py selftest`. The model refuses a variant that's
missing a role or has a common mistake no test catches; the self-test checks that every reference passes, every trace
builds, a do-nothing solution fails, and every lesson example runs and gives its cases.

**Adding a SQL challenge**: append a dict with a prompt and a solution to `categories/sql/challenges.py`, then run
`./butterbricks.py selftest`. The browser's checker, `web/sql/engine.js`, is a port of `categories/sql/engine.py`.

**Adding an implementation problem**: write `categories/implementation/problems/<name>.py` defining
`PROBLEM = Problem(...)`, add it to `problems/__init__.py`, then run `./butterbricks.py selftest`.

- A **`Problem`** has the scenario intro, its `Part`s, the starter code, a reference solution (as source), discussion
  questions and the writeup. A **`Part`** has a markdown statement, hints and test cases. Running part *n* runs the
  tests of parts 1..*n*.
- **`OpsTest`** constructs a class and calls methods in order, comparing each return value. Steps written as
  `(method, args, expected)` are checked against `expected`; steps written as `(method, args)` get their expected
  value from the reference solution, so a big randomly generated test needs no hand-written answers.
- **`ScenarioTest`** wraps a function `fn(ctx)` for checks that aren't "equal to X": validate that any packing is
  legal, compare against the reference's score with `ctx.metric(name, value, target=...)`, and so on.
- Every test has a `time_limit` (seconds) and can be `hidden`. Scale tests are sized so that the intended approach
  finishes well inside the limit and the naive approach doesn't.

**Adding a category**: a `categories/<name>/build_web.py` that writes its data into `web/<name>/`, a page in
`web/<name>/`, an entry in `build.py` (for the catalog), in `DONE` in `web/common.js` (how much of a problem is
done) and in `butterbricks.py`.

## Deploying

The site runs on [Fly.io](https://fly.io) as the app `butterbricks` (`fly.toml`, `Dockerfile`): one machine that
stops when idle, with the SQLite database on a 1 GB volume at `/data` (Fly snapshots volumes daily). Secrets:
`SECRET_KEY` (signs sessions) and `INVITE_CODE`.

```
fly deploy
fly secrets set INVITE_CODE=...      # change the invite code
```
