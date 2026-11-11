# The Structures category: designing data structures

Status: **built:** Building blocks (operation costs) and the first Cross-indexed technique (position map), in
`categories/structures/bricks/`; the rest is the plan. Same model and naming rule as `patterns-taxonomy.md`, applied to a different skill.

## 1. The skill

Given operations and how fast each must be, choose the state to keep so every operation is cheap and the code stays
simple. It is the step that decides most "design a data structure" interview problems, and most implementation rounds:
once the state is right, the code is usually easy.

The method taught throughout is the textbook one for *augmenting data structures* (CLRS, the chapter of that name):
choose an underlying structure, decide what extra information to keep, check that every operation keeps it up to date,
then build the new operations. In this category's words:

1. **Operations and targets.** List the operations and the cost each must have.
2. **The bottleneck.** In the obvious design, which operation is too slow?
3. **Combine, and name the invariant.** Add a structure that makes the slow operation fast, and write down the fact
   that ties the structures together (`pos[items[i]] == i` for every i).
4. **Keep it true.** Check that every operation preserves the invariant, then implement.

## 2. What makes it learnable

- **Costs are graded per operation.** A cost test builds the structure at two sizes, 10× apart, and times each
  operation. Correct code with the wrong structure fails, naming the slow operation and how its time grew
  (`remove(): ×9.6 for 10× the items, like O(n); target O(1)`). Timing separates "grows with n" from "doesn't"; it
  can't separate O(log n) from O(1), so targets are stated as one or the other only where it can tell.
- **One requirement changes at a time.** A twin keeps the requirements and changes the story; a variation adds one
  operation or tightens one cost; the cost tests show exactly when the old design stopped being enough.
- **Design before code.** Every problem has a design card (what you'll keep, the invariant, each operation's cost) to
  fill in first and compare with ours after. Opening ours before solving counts as revealing the solution.
- **Worked designs.** A technique's first problem walks the reasoning one question at a time (which operation is the
  bottleneck, what could fix it, what must stay true), then steps through the code with every field of the object
  shown as it changes, so you watch the structures stay in sync.

## 3. Model and roles

Category → **family** (a pattern, in Patterns' terms) → **technique** (a variant, a brick) → problem with a role:
worked design (example), completion, twin, variation, stretch, reviews, and drills ("which technique fits these
operations?" then "what in the requirements told you?"). Problems here are classes, tested by sequences of operations
(correctness, against the reference) and by cost tests.

## 4. Families, in the recommended order

1. **Building blocks** (built): the cost of Python's own structures.
2. **Cross-indexed structures** (one technique of three built): two structures joined by an index.
3. Augmented structures: one structure plus extra information kept up to date (a stack that knows its minimum).
4. Ordered structures: sorted lists with binary search, heaps with lazy deletion, two heaps.
5. Time and versions: sliding windows of events, snapshots, undo.

Family names are **ours**: no guide names these groupings. "Augmented" follows CLRS.

---

## Family 1: Building blocks

### 1.1 Operation costs

- **Key** `operation-costs` · **Name status** ours · **Aliases** time complexity of built-ins, big-O of Python
  operations
- **Source** the Python wiki's TimeComplexity page (https://wiki.python.org/moin/TimeComplexity), which lists the
  costs of list, deque, set and dict operations in CPython.
- **Idea** Every structure is fast at some operations and slow at others. A list is fast at its end and slow at its
  front; a deque is fast at both ends; a set or dict answers "is x here?" in O(1); a list answers it in O(n).
- **Invariant** (for a queue built on a deque) the deque holds the waiting items, oldest at the left.
- **Common mistakes** `list.pop(0)` or `list.insert(0, x)` for a queue (O(n): every other item shifts); `x in some_list`
  for membership (O(n): it scans).
- **Problems**

  | Role | Problem | What changes |
  | --- | --- | --- |
  | worked design | Ticket counter: join the line, serve the next person, count who's waiting | |
  | completion | Print queue (the deque calls are blank) | |
  | twin | Support tickets, first come first served | story only |
  | variation | Undo history: take the most recent instead of the oldest | which end you take from (a plain list is fine again) |
  | stretch | Recent visitors: keep the last k visits and answer "visited recently?" in O(1) | a second structure (a count per name) kept in sync |

---

## Family 2: Cross-indexed structures

Two structures, each fast at different operations, joined by an index so each can find things in the other. The
invariant is always "the two agree".

### 2.1 Position map with swap-remove

- **Key** `position-map` · **Name status** ours · **Aliases** swap-remove ("swap and pop"; Rust's `Vec::swap_remove`),
  indexed array, randomized set
- **Idea** A list gives O(1) random access but slow removal from the middle; a dict gives O(1) lookup but no random
  access. Keep both: the list of items, and a dict from each item to its position. To remove from the middle, swap the
  item with the last one, update the moved item's position, and pop the end.
- **Invariant** `pos[items[i]] == i` for every position i, and the dict holds exactly the items in the list.
- **Common mistakes** `list.remove(x)` (O(n)); `random.choice(list(a_set))` (O(n)); forgetting to update the moved
  item's position after the swap; removing the item that's already last (the swap is with itself: delete its entry
  last, or skip the swap).
- **Problems**

  | Role | Problem | What changes |
  | --- | --- | --- |
  | worked design | Raffle: add a ticket, remove a ticket, draw a random one, all O(1) | |
  | completion | The same raffle, `remove` with its swap and position update blank | |
  | twin | Online players: join, leave, pick a random opponent | story only |
  | variation | Bag of marbles: duplicates allowed (a color maps to a set of positions) | duplicates |
  | stretch | Shuffle bag: draw without repeats until a refill, everything O(1) | a second region in the list, with its own boundary |

### 2.2 Linked hash map (planned)

- **Name status** textbook: Java's `LinkedHashMap`, Python's `OrderedDict`. **Aliases** LRU cache structure, hash map
  plus doubly linked list. Problems: an LRU cache, then variations.

### 2.3 Frequency buckets (planned)

- **Name status** textbook: the O(1) LFU scheme (Shah, Mitra and Matani, "An O(1) algorithm for implementing the LFU
  cache eviction scheme", 2010). **Aliases** LFU cache structure. Problems: an LFU cache, then variations.
