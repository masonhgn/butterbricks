# Butterbrick

Interview practice, laid one brick at a time. Two tracks share one site:

- **SQL**: 78 challenges in 10 levels, from `SELECT *` to window functions, data changes and multi-step boss
  problems, against a real SQLite database of a small online store (customers, orders, products, employees).
- **Implementation**: the "small implementation" interview round (the Palantir style). You get a realistic scenario,
  build a small system that has to pass an extensive test suite, then defend your design. Problems come in parts that
  extend the same code, the way an interviewer adds requirements once the first version works.

Everything runs in the browser (SQLite through [sql.js](https://sql.js.org), Python through
[Pyodide](https://pyodide.org)), so the site is static and deploys to GitHub Pages. Each track also has a terminal
version.

## Running it

```
./serve.py          # or: ./serve.py 8001 for another port
```

Then open http://localhost:8000. `serve.py` runs `build.py`, which exports each track's data into `web/`, and
serves `web/` with browser caching turned off. Python changes (problems, challenges, the test framework) need a
rebuild: restart `serve.py` or run `./build.py`.

The site asks for a password first. It only keeps casual visitors out: the files are public, so it isn't real
security. The password's SHA-256 is in `web/common.js`.

## The site

Both tracks use the same layout: the list on the left, the statement in the middle, the editor on the right with
results underneath. Drag the dividers to resize them. Progress, code and drafts are saved in your browser.

### SQL

- The **Challenge** tab has the prompt and hints, **Lesson** the current level's lesson (a new level opens on it),
  **Schema** every table's columns, and **Solution** a reference answer once you choose to look.
- **Run** (Ctrl+Enter) checks your query by comparing its result to the reference solution's, so any correct query
  passes. Column names and aliases aren't checked; column order is, and so is row order when the challenge asks for
  sorting. Ctrl+Space autocompletes table and column names.
- Every run uses a fresh in-memory copy of the data, so `DELETE FROM customers;` can't break anything. Queries that
  take longer than 5 seconds are stopped.
- Results show in a spreadsheet-style grid with sheet tabs: `Result`, `Expected` (from **Expected output**), the
  tables the challenge uses, and `+` to open any other table. Click a column header to sort, click a cell to see its
  full value in the formula bar, double-click a cell to paste its value into the editor, and use "Filter rows…" to
  search. For challenges that change data, the tables your statements touched show their changed state (marked •,
  changed rows highlighted).
- **Export** and **Import** move progress between browsers as a `progress.json` in the same format the terminal
  version uses.

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
  went wrong, what was expected, the calls just before it, and anything you printed. Open-ended tests show scores,
  such as your truck count next to the reference's count and the lower bound.
- **Console** runs any snippet with your classes in scope. **Notes** is for your design and its tradeoffs;
  **Discussion** lists the questions an interviewer would push on; **Solution** shows the reference and its writeup.
- A timer per problem tracks how long you've spent. Time limits are 2.5× the terminal ones, because Python in
  WebAssembly runs slower, and a test that runs far past its limit is stopped by restarting Python.

## Terminal versions

```
sql/sqlquest.py                                      # the SQL track as a terminal app
sql/sqlquest.py --selftest                           # every reference solution passes the checker
sql/sqlquest.py --rebuild                            # regenerate the database

impl/implquest.py                                    # list the implementation problems
impl/implquest.py fulfillment                        # writes impl/solutions/fulfillment.py from the starter, runs part 1's samples
impl/implquest.py fulfillment --part 2 --submit      # every test for parts 1-2, hidden ones included
impl/implquest.py --selftest                         # every reference solution passes its own tests
```

`sqlquest.py` runs through [uv](https://docs.astral.sh/uv/), which installs its two UI libraries (rich and
prompt_toolkit) on first run; without uv, `pip install rich prompt_toolkit`. It highlights SQL as you type, Tab
completes names, and Enter runs once the query ends with `;`. Its commands are `.hint` `.expected` `.solution`
`.lesson` `.prompt` `.tables` `.schema [table]` `.list` `.goto N` `.clear` `.reset` `.help` `.quit`, and progress is saved in
`sql/progress.json`. `sqlite3 sql/sqlquest.db` opens the same data in any SQLite tool. `implquest.py` needs only
the standard library.

## Layout

```
build.py, serve.py     build the site's data; build and serve it locally
web/                   the static site: index.html (home), common.css/common.js (shared), logo.svg
web/sql/               the SQL track's page; engine.js checks answers with sql.js in a web worker
web/impl/              the implementation track's page; worker.js runs the tests in Pyodide
sql/                   challenges.py (lessons and challenges), dataset.py (the data), engine.py (the checker)
impl/framework/        Problem/Part, OpsTest/ScenarioTest, the runner shared by the terminal and the browser
impl/problems/         one file per problem
```

**Adding a SQL challenge**: append a dict with a prompt and a solution to `sql/challenges.py`, then run
`sql/sqlquest.py --selftest`. The browser's checker in `web/sql/engine.js` is a port of `sql/engine.py`.

**Adding an implementation problem**: write `impl/problems/<name>.py` defining `PROBLEM = Problem(...)`, add it to
`impl/problems/__init__.py`, then run `impl/implquest.py --selftest`.

- A **`Problem`** has the scenario intro, its `Part`s, the starter code, a reference solution (as source), discussion
  questions and the writeup. A **`Part`** has a markdown statement, hints and test cases. Running part *n* runs the
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

## Deploying

Pushing to `main` deploys `web/` to GitHub Pages through `.github/workflows/pages.yml`, which runs `build.py` first.
In the repository's settings, Pages has to be set to deploy from GitHub Actions.
