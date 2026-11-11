# Exercise ideas

Ideas for new kinds of exercises, kept here so they aren't lost. Each says what it trains, how it would be graded, and
what it would reuse. Status: ideas, not plans, unless marked otherwise.

## Context: what interviews are moving toward

Jane Street, "Our software engineering interviews are changing (a little)", Nov 2, 2026
(https://blog.janestreet.com/software-engineering-interviews-are-changing-a-little/):

- Most rounds stay traditional coding interviews, without LLM assistance: programming through a problem with an
  interviewer and talking as you go. Patterns and Implementation cover these.
- Since summer 2026 they've trialed extra onsite rounds for campus candidates: more high-level, less code-writing,
  focused on software design, on verifying the quality, structure and intent of code, and on using LLMs to produce code.
- The reasoning: code is now cheap to generate, so taste about what to build, abstractions that last, and making sure
  what got built is correct matter more.
- On tools: no elaborate agent workflow is expected; what matters is thinking clearly about what a tool is good at,
  where it falls short, and when to reach for something else.

## Ideas

### 1. Find the counterexample

A spec and a short, plausible solution: the kind a model writes, clean and confident, passing the obvious examples,
subtly wrong. The learner writes **the input that breaks it**.

- Trains: adversarial reading, verifying code you didn't write.
- Graded: exactly. The input counts if the buggy code and the reference disagree on it (and the input is valid for the
  spec, checked by a validator per problem).
- Reuses: CallTest, reference solutions, the stepper (to watch the bug happen once it's found).

### 2. Bug patterns as bricks

Bugs come in recognizable classes, like algorithms do: off-by-one at a boundary, mutating a collection while iterating
it, a shared mutable default, wrong behavior on empty or None, a hidden ordering assumption, a sort key that compares
the wrong thing, an early return that skips work. Each class gets the Patterns sequence: a worked example tracing the
bug happening, find the counterexample, write the minimal fix, variations, and "which bug class is this?" drills.

- Trains: a vocabulary of failure modes, and the reflex to check for them.
- Graded: counterexamples exactly; fixes by tests.
- Reuses: the whole Patterns model (category, pattern, variant, problem with a role) and the naming rule.

### 3. Review against the intent

A spec, code, and a change description. Name what's wrong (it doesn't do what was asked; it misses a requirement; it's
correct but needlessly complex; it's structured to break on the next change), then fix the most important issue.

- Trains: reviewing for quality, structure and intent: the closest match to the new rounds.
- Graded: the diagnosis by multiple choice, the fix by tests.

### 4. Change requests

A small working codebase, then a new requirement. Variants: two v1 designs, predict which absorbs v2 cleanly, then
implement it; or implement v2 and be graded on how much existing code you had to touch as well as on the tests.

- Trains: abstractions that last.
- Graded: tests, plus the size of the diff.

### 5. Read before you run

Unfamiliar code; predict its behavior: outputs, final state, which branch runs.

- Trains: reading speed and accuracy, which matter more when most code you meet isn't yours.
- Graded: exactly, from a trace.
- Reuses: the trace builder (categories/patterns/trace.py) almost unchanged.

### 6. Working with a model directly

A live LLM in the app: decide when to use it versus write a brute-force oracle or a property test, specify a task well
enough, catch the model's mistake before it ships.

- Trains: the "think clearly about your tools" skill, directly.
- Cost: API calls per use, and key management. Ideas 1 to 3 can simulate it with pre-written "model output" first.

### 7. Designing data structures (chosen direction, under discussion)

Isolate the skill of choosing the state and the structures that make every operation fast and the code simple. See the
discussion that follows this document's creation; once agreed, it gets its own taxonomy document like
`patterns-taxonomy.md`.
