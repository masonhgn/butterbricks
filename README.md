# Butterbricks

Interview practice, laid one brick at a time: [butterbricks.org](https://butterbricks.org).

One list of problems, sorted into categories:

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

## The site

The sidebar lists every problem by category; each category's page fits its kind of problem, and a link like
`/sql/#distinct_categories` or `/implementation/#kv-store` opens one directly. Drag the dividers to resize the panes.

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
web/                       the site: index.html (home), common.css/common.js (shared: problem list, accounts, sync,
                           editor, the pixel look), logo.svg
tools/pixelart.py          draws the logo and the textures (prints the textures as CSS to paste into common.css)
web/<category>/            each category's page
categories/sql/            challenges.py (lessons and challenges), dataset.py (the data), engine.py (the checker)
categories/implementation/ framework/ (Problem, Part, OpsTest, ScenarioTest, the runner) and problems/ (one file each)
```

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
