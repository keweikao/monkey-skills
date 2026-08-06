# Plan: US quarterly three-statement series, 10+ years

**Source brief**: docs/loom/specs/2026-07-28-us-quarterly-statement-series.md
**Total tasks**: 10 (Task J added 2026-07-29 by plan review — see its header note)
**Critical-path depth**: 5 (A → D → E → F → H). Task J's chain A → B → J → H is depth 4, so the ceiling is unmoved.
**Execution order**: parallel-where-possible
**Plan-document-reviewer verdict**: PENDING — **amendment series** round A4.

**NOT BLOCKED.** The cash-flow finding that blocked Tasks E/F/G was resolved by
user decision on 2026-07-30 — see §RESOLVED FINDING. Any sentence below telling
you the plan is blocked on a user decision is stale; this line wins.

Two separate review series exist; do not conflate their round numbers.
- **Original series** (2026-07-28/29): PASS at round 5, 14/14. Its round 3 also
  PASSed, and that verdict was voided by the user's 2026-07-29 clarification that
  ten years is a FLOOR, not a target — a substantive scope change, re-reviewed.
- **Amendment series** (2026-07-29/30, the acquisition boundary): A1 (13/14) split
  the acquire loop out of Task H into Task J; A2 (13/14) found Task J's seam clause
  unexecutable from its own position and three citations in Task D's Description
  wrong — both applied 2026-07-30; A3 (13/14) found Task D's RED asserts something
  its own fixture refutes — **resolved**, see §RESOLVED FINDING; A4 (12/14) found
  Task D's restated RED could go green on first run and that the brief itself must
  be amended, both applied 2026-07-30.

## Notes

- **No loom-spec change-folder bound.** Two non-archived change-folders exist
  (`docs/loom/2026-07-12-us-sec-primary-source-layer`,
  `docs/loom/2026-07-19-8k-prose-kpi-intake`); neither matches this branch and
  neither is this arc's work. Input is the brainstorming brief. Stated rather
  than silently skipped.
- **The two derivations this plan does NOT build** are in the pinned dependency
  and were live-verified: `_unaccumulate_cashflow_ytd`
  (`edgar/xbrl/stitching/core.py:705`) and `_derive_q4_from_fy`
  (`edgar/ttm/calculator.py:665`). Tasks E and G verify our use of them against
  real numbers; no task reimplements them.
- **Task B's ordering is deliberate but not load-bearing.** Nothing depends on B
  for CORRECTNESS — Tasks D/E/F all run against committed fixtures — so B carries
  no dependency edge to them. Its benefit (a ~77-filing build costing seconds
  instead of 20-37 minutes) reaches the live path used by Task H and by real use;
  land B before any live multi-filing run, not because a test requires it.
- **Task C is deliberately pure** (string → classification, no network, no
  edgartools import) so the 52/53-week boundary risk in Task G can be tested
  exhaustively without fetching anything.

---

## RESOLVED FINDING 2026-07-30 — a period key did NOT describe its own value in the cash-flow statement

**Status: RESOLVED by user decision 2026-07-30 — direction 乙. See §Resolution at
the end of this section for what changes. Kept in full because the measurement is
the reason for the change and must not be re-discovered.**

Measured directly from this branch's own fixture
(`us_quarterly_stitched_msft.json` as it stood on 2026-07-29 — a **12-filing**
`discrete_quarters=True` capture, untracked at the time of measurement), not
inferred. The re-capture that direction 乙 requires holds **11** filings, because
`years=3` resolves against the run date and the window rolled past a 10-K; the
values below are the record of the DEFECT, not of the shipped fixture:

| period key | span | income statement | cash-flow statement |
|---|---|---|---|
| `duration_2024-07-01_2025-06-30` | 364d | `281,724,000,000` — the true fiscal year | `42,647,000,000` — **Q4 alone** |
| `duration_2024-07-01_2025-03-31` | 273d | `205,283,000,000` — the true nine-month cumulative | `37,044,000,000` — **Q3 alone** |
| `duration_2025-01-01_2025-03-31` | 89d | `70,066,000,000` — Q3 | `37,044,000,000` — **identical to the 273d column** |

The income statement's keys mean what they say. **The cash-flow statement's do
not**: requesting `discrete_quarters=True` replaced the values with discrete
quarters while leaving the original cumulative period keys in place. So a key
spanning a full fiscal year holds one quarter, and two different keys hold the
same quarter's value.

`42,647,000,000` is exactly the Q4 figure the brief cites as live-verified
(`136,162 − 93,515 = 42,647`, brief §Decision). The dependency's arithmetic is
right; it files the answer under a key that misdescribes it.

**The dependency itself knows.** It labels that 364-day cash-flow column
`'Q4 FY Jun 30, 2025'` — the label carries the truth, the key does not. But labels
are not a usable fallback either: the cash-flow statement has **six** label
collisions, one per quarter, where a discrete column and a cumulative column share
a label (e.g. `'Q3 Mar 31, 2026'` names both an 89-day and a 273-day key).

**Also measured**: no fiscal-Q4 period exists anywhere in the capture — no key
starts `2025-04-01`, which for a June-30 fiscal year is where Q4 begins. The
discrete Q4 is present only as the mislabelled FY-keyed column above.

**Why this is blocking rather than a Task-C bug**: it invalidates the one-way-door
decision the user approved on 2026-07-29 (period kind derived from the key's day
span — Decision Log, one-way door #1). Task C implements that decision faithfully;
the decision itself does not survive contact with the cash-flow statement. Any fix
inside Task C would be guessing at a direction the user has not chosen.

### Resolution — direction 乙, chosen by the user 2026-07-30

**Stop asking the dependency for discrete cash-flow quarters. Take the cumulative
columns as filed, and do the subtraction ourselves.**

The invariant this buys, which the rest of the arc depends on: **a period key's
span always describes the span of its value, in every statement.** The two
alternatives both failed that. Reading labels instead (direction 甲) fails because
the cash-flow statement has six label collisions and because it makes the
classifier statement-dependent — an exception every downstream consumer must
remember forever. Marking the quarterly cash-flow columns untrustworthy
(direction 丙) fails because quarterly cash flow is a third of what "three
statements" means.

**What this costs, stated plainly**: we now build the YTD-differencing the brief
scoped OUT on the grounds that it already ships in the dependency
(`_unaccumulate_cashflow_ytd`, `core.py:705`). That reasoning was correct and
incomplete — the shipped version computes the right numbers and files them under
keys that misdescribe them. The arithmetic is the same shape as Task E's existing
income-statement subtraction, so this widens Task E rather than adding a task.

**Task-by-task consequences:**

- **Task D** passes `discrete_quarters=False`. Note this parameter is gated to
  CashFlowStatement inside the dependency (brief §Decision cites
  `core.py:181`), so the change is a no-op for the income statement and balance
  sheet. `include_quarterly=True` is unchanged and is what supplies the income
  statement's honest discrete columns.
- **Task D's fixture must be RE-CAPTURED.** `us_quarterly_stitched_msft.json` was
  captured with `discrete_quarters=True` and therefore contains the defect above.
  Every number downstream of it moves. This is not optional and it is not a
  refactor.
- **Task E widens** from "derive the Q4 income column" to "derive the discrete
  quarters the filings do not state": Q4 income = FY − Q3-YTD (unchanged), plus
  cash-flow Q2 = YTD6 − Q1, Q3 = YTD9 − YTD6, Q4 = FY − YTD9. Its GREEN must
  cross-check at least one derived cash-flow figure against the dependency's own
  `_unaccumulate_cashflow_ytd` output, so the subtraction is verified against
  something other than itself.
- **Task C's SPAN BUCKETING needs no change and becomes correct for all three
  statements.** It is committed (`88255590`); it was only ever wrong because the
  cash-flow keys lied. **Do not re-bucket its windows to work around the
  cash-flow defect** — that is what this bullet forbids, and it still holds.
  **Narrowed 2026-07-30**: this said flatly "Do not edit it", which contradicted
  Task E's amended `Files touched` and the behaviour-preserving `span_windows()`
  accessor that shipped. A purely additive change that leaves `period_kind` and
  the windows untouched is allowed; changing what the classifier ANSWERS is not.
- **Tasks F and G** are unblocked once D's fixture is re-captured.

**One assumption round 4 must verify BEFORE writing any test** — nobody has run
`discrete_quarters=False`. But it is verified against a **pre-declared** expected
answer, not measure-then-assert, because the arithmetic already on record settles
what the answer must be.

The four `True`-mode discrete operating-cash-flow values for MSFT FY2025, measured
from the existing capture: **Q1 34,180 / Q2 22,291 / Q3 37,044 / Q4 42,647** (×10⁶).
They sum to **136,162**, which is the brief's own FY2025 operating-cash-flow figure
(§Decision) — so the sum independently confirms both that these are the four
discrete quarters and the attribution rule below.

Therefore `False` mode must yield, for the same filer and year:
**Q1 34,180 / YTD6 56,471 / YTD9 93,515 / FY 136,162** (×10⁶); the brief states
YTD9 = 93,515 and FY = 136,162 directly. Declare those four before running, then
check. If the capture disagrees with any of them, STOP and report — do not adjust
the expectation to match what came back, and do not amend this plan yourself.

**The attribution rule, needed to read a `True`-mode capture as an oracle at all**:
`core.py:720` states the YTD periods are replaced **in-place**, so in a
`True`-mode capture the value stored at `duration_X_Y` is the discrete quarter
ENDING at `Y`. (Cited as `:719-720` in an earlier draft; `:719` is blank —
corrected 2026-07-30 after opening the file.) Without this rule the only way to map a `True`-mode value to a
quarter is via the keys direction 乙 rejects, or via labels that collide six ways.

---

## Task A — Assemble the filing list for a span

- **Description**: Add a function that, given a CIK, returns the ordered
  accession list of EVERY available 10-Q and 10-K, oldest first, with an OPTIONAL
  years cap. Default is all available history — ten years is the user's floor,
  not the target. Uses the existing `list_filings`; does not fetch documents.
- **Module**: investing-toolkit/skills/data-markets/scripts/sec_edgar_client.py
- **Files touched**: investing-toolkit/skills/data-markets/scripts/sec_edgar_client.py, investing-toolkit/tests/data/test_us_quarterly_filing_list.py
- **Context paths**:
  - investing-toolkit/skills/data-markets/scripts/sec_edgar_client.py
  - investing-toolkit/tests/data/test_sec_submissions_pagination.py
- **Acceptance**:
  - **RED**: `test_uncapped_request_returns_every_available_filing` — for a stubbed submissions payload holding filings across 15 years, the uncapped call returns ALL of them (both forms, ordered oldest-first), and a `years=5` call returns only the most recent 5 years' worth.
  - **GREEN**: both assertions pass offline; the uncapped path applies no implicit limit of its own.
- **External surfaces**: SEC submissions JSON, already wrapped by `list_filings`; no new endpoint.
- **Dependencies**: none
- **Independent**: false
- **Brief item covered**: "Assemble the filing list — every 10-Q and 10-K available, oldest first (~77 filings for a filer with full XBRL history), optionally capped."

## Task B — Cache raw filing documents on disk

- **Description**: Wrap `_acquire_raw_filing` with a disk cache keyed by
  accession. Filings are immutable, so the cache has no TTL — existence is
  validity. ~~Cache the raw document, not the parsed object.~~ **Struck
  2026-07-31** — there is no document at this seam; see the RESOLVED note below and
  Decision Log #3. Cache the five values that rebuild the object.
  **RESOLVED 2026-07-31.** A pre-dispatch note here claimed the cache had to sit on
  "the DOCUMENT the object is built from" and that a `Filing` is not serialisable.
  An implementer measured both to be false and returned `NEEDS_CONTEXT` before
  writing any code; the user re-decided the on-disk format (Decision Log #3, which
  now carries the full finding). **`_acquire_raw_filing`'s return shape does NOT
  change** — a cache hit reconstructs an `edgar.Filing` from the five stored fields,
  so `fetch_narrative_sections` and `acquire_filing` are untouched, and
  `get_by_accession_number` is simply never called on a hit.
- **Module**: investing-toolkit/skills/data-markets/scripts/sec_edgar_client.py
- **Files touched**: investing-toolkit/skills/data-markets/scripts/sec_edgar_client.py, investing-toolkit/tests/data/test_raw_filing_cache.py, investing-toolkit/tests/data/test_sec_narrative.py, investing-toolkit/tests/test_exhibit_fetch.py (**last two added 2026-07-31** — `company` is one of the five values `edgar.Filing.__init__` requires, so the cache payload reads it; three pre-existing doubles omitted it and raise on a missing attribute by their own `fixtures-mirror-producer-shape` doctrine. Three added lines, no behaviour changed. **Third instance of this on this branch** — Task D's list gained its capture script, Task I's gained its own "exactly as Task D's was", and now this; the pattern is that a task's real file set is only knowable once the code exists.)
- **Context paths**:
  - investing-toolkit/skills/data-markets/scripts/sec_edgar_client.py
  - investing-toolkit/skills/data-markets/scripts/cache_util.py
- **Acceptance**:
  - **RED**: `test_second_acquire_of_same_accession_does_not_refetch` — a spy on the network path records exactly ONE call across two `_acquire_raw_filing` invocations for the same accession, and the second call returns something satisfying the same `.obj()` / `.form` / `.cik` / `.filing_date` surface as the first. **Both halves are required**: a cache that returns a hit of the wrong shape would satisfy the call count alone, and this arc's recurring defect is exactly a wrong answer with the right shape.
  - **GREEN (restated 2026-07-31 — the original said "a third invocation in a fresh process also records zero fetches", which no test in a pytest process can execute; an implementer would have had to either fake it or silently drop it)**: three things, all offline. (1) The spy records one network call for two invocations. (2) **Cross-process persistence is proven by writing the cache in one place and reading it in a test that re-imports the client fresh, with the network path made to RAISE** (**reworded 2026-07-31**: this said "writing in one test and reading in another", and the artifact writes from a module-scoped fixture instead. A spec review judged the letter wrong and the artifact right — a fixture is the stronger form, and it is what this repo's own `a-no-mutation-test-cannot-baseline-off-shared-fixture-state.md` prescribes. The clause's real requirement is that the reader shares nothing in memory with the writer.) The reader must also assert the returned value is NOT an error dict — otherwise `_acquire_raw_filing`'s own `except Exception` swallows the raise into an error slot and the test passes on a cache that refetched every time. — a fetch attempt then fails loudly instead of passing quietly, which is the executable form of "a fresh process gets a disk hit". (3) A DIFFERENT accession still fetches, so the cache is keyed rather than blanket-hit; without this, a wrapper that returns the first filing for every accession passes clauses 1 and 2. (4) **`.filing_date` on a cache hit is a `datetime.date`, not a `str`** — assert the TYPE, not just the value. `Filing.from_dict` coerces it to `str`, so this is a real divergence a live acquisition would not have, and no count-based or value-based assertion sees it (`str(date) == "2025-04-30"` compares equal to the string).
- **External surfaces**: local filesystem under `cache_util.resolve_cache_dir()`; no new network surface.
- **Dependencies**: Task A completes first
- **Independent**: false
- **Brief item covered**: "Cache the raw filings on disk. They are immutable, so the cache needs no invalidation policy beyond existence."

## Task C — Classify a period key into an explicit kind

- **Description**: Add a pure function mapping a period key
  (`duration_<start>_<end>` / `instant_<date>`) to one of
  `discrete_quarter | ytd | annual | instant`, by day-span bucketing. No
  network, no edgartools import.
- **Module**: investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_periods.py
- **Files touched**: investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_periods.py, investing-toolkit/tests/analysis/test_kpi_us_quarterly_periods.py
- **Context paths**:
  - investing-toolkit/skills/analysis-kpi/scripts/kpi_us_statement_shape.py
- **Acceptance**:
  - **RED**: `test_period_key_classifies_by_span` — a table of real period keys captured from filings maps to the expected kind, including a 273-day Q3-YTD and an 89-day quarter.
  - **GREEN**: every row of the table classifies correctly and an out-of-range span returns an explicit unknown rather than a guess.
- **Dependencies**: none
- **Independent**: true
- **Brief item covered**: "Label every period explicitly — discrete quarter / year-to-date / annual / derived — rather than leaving it to be inferred from a day-span."

## Task D — Stitch a filing list into three statements

- **Description**: Add a function that takes **already-acquired filing objects
  — NOT the accession rows Task A returns** — and returns the three statements
  via `XBRLS.from_filings(...)` with **`discrete_quarters=False`** (changed
  2026-07-30 by direction 乙 — see §RESOLVED FINDING; `True` made the cash-flow
  statement file discrete quarters under cumulative period keys) and
  `include_quarterly=True` **and `max_periods` set from the size of the passed
  list, never left at its default**. No derivation, and no acquisition:
  turning accession rows into filing objects would make an `analysis-*` module
  import `data-markets` directly, and this repo crosses that boundary by
  subprocess. Three precedents, with what sits at each line — **verified by
  opening them 2026-07-30, after two earlier citation attempts here were both
  wrong**: `kpi_8k_candidates.py:18-22` (the convention stated in prose, naming
  `etf_aggregator.py` as its own precedent), `:45` (`import subprocess`), `:53`
  (the `exhibit_tables.py` path constant), `:124` (`proc = subprocess.run(`);
  `kpi_prose_candidates.py:44` (`import subprocess`), `:51` (the convention in a
  comment), `:62` (the `exhibit_prose.py` path constant), `:149`
  (`proc = subprocess.run(`); `etf_aggregator.py:28` (`import subprocess`),
  `:68` (the `pack.py` path constant), `:94` and `:111` (two
  `proc = subprocess.run(` call sites). Five further modules state it as a prohibition
  in their own docstrings (`kpi_tw.py:7-8`, `kpi_us_statements.py:10,249-250`,
  `kpi_tw_ingest.py:28-30`, `kpi_us_statements_ingest.py:28-30`,
  `kpi_spine_view.py:19`). **Task J owns the acquire loop.** **Amended
  2026-07-29** after Task D's round-1 review found the original wording
  unsatisfiable — a module cannot both take accession rows and honour the
  boundary. `XBRLS.get_statement`'s signature defaults `max_periods=8`
  (`edgar/xbrl/stitching/xbrls.py:149-155`), so a 77-filing request left unset
  silently returns 8 periods with every test still green — that is the defect
  this wording exists to prevent.
- **Why the Task A edge survives the amendment**: D's function no longer
  consumes A's output shape, so the edge would read as vestigial. It is not —
  D owns capturing `us_quarterly_stitched_msft.json`, and the capture script
  calls A's function directly — `capture_us_quarterly_stitched.py` calls
  `sec.assemble_quarterly_filing_span(CIK, years=YEARS)`, defined at
  `sec_edgar_client.py:699`. Stated so an implementer does not "clean up" a live
  dependency. **Cited by SYMBOL, not line number, deliberately**: a line citation
  here was false within hours because the capture script is under active edit by
  the very task this plan is describing (it said `:118`, which is `YEARS = 3`; the
  call is at `:150` today and will move again). Cite a file another agent is
  editing by the symbol it defines or calls, never by position.
- **Module**: investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_series.py
- **Files touched**: investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_series.py, investing-toolkit/tests/analysis/test_kpi_us_quarterly_series.py, investing-toolkit/tests/data/fixtures/us_quarterly_stitched_msft.json, investing-toolkit/tests/data/fixtures/capture_us_quarterly_stitched.py (**added 2026-07-29** — the capture script that regenerates the fixture; it was produced by this task and cited by its test, but omitted from this list in the original plan)
- **Context paths**:
  - investing-toolkit/skills/analysis-kpi/scripts/kpi_us_statement_shape.py
  - investing-toolkit/skills/data-markets/scripts/sec_edgar_client.py
- **Acceptance**:
  - **RED (restated 2026-07-30**, twice: plan review A3 found both original clauses indeterminate against the fixture — clause 1 false under a universal reading and tautological under a charitable one, clause 2 naming no oracle — and direction 乙 then changed what the fixture contains): `test_stitched_periods_describe_their_own_spans_and_are_not_truncated` — against the RE-CAPTURED fixture `investing-toolkit/tests/data/fixtures/us_quarterly_stitched_msft.json`, assert three things, each with the measured number written in after re-capture, not before:
    1. **THIS IS THE RED. Clauses 2 and 3 are regression guards that were already green on the defective fixture — do not mistake them for it.** Assert against the two cash-flow duration keys that share an **END date** and differ in span: `duration_2024-07-01_2025-03-31` (273d) and `duration_2025-01-01_2025-03-31` (89d). Under `discrete_quarters=True` both hold `37,044,000,000` — measured. Under `False` the 273d key must hold the true nine-month cumulative `93,515,000,000` (brief §Decision) and the 89d key the discrete Q3. **Same END date is the load-bearing part of this clause**: A4 measured that only 6 of the 24 same-fiscal-year (quarter × cumulative) pairs collide, and they are exactly the 6 sharing an end date — so "pick any quarter and cumulative column of the same fiscal year", which this clause said before 2026-07-30, is green on the defective fixture 18 times out of 24 and is therefore not a RED at all.
    2. **The income statement carries both discrete and cumulative columns**, naming one key of each with its measured day count — this is what `include_quarterly=True` buys and it must not silently stop working.
    3. **The period COUNT per statement kind equals the re-captured measured value**, written in literally. A count of 8 (the `max_periods` default) must fail. Do not phrase this as "what the filing count implies" — the plan derives no such rule, which is exactly why A3 called the original indeterminate.
  - **GREEN**: all three statement kinds return, the re-captured fixture is committed, and all three assertions pass offline. **This task owns that fixture — Task E's RED asserts against it, so the re-capture must land before Task E is dispatched.**
- **External surfaces**: `edgartools==5.42.0` `XBRLS.from_filings` / `get_statement`; pinned, no new dependency.
- **Reuse-adequacy**: reuses the dependency's stitching rather than this repo's `statements_for` — the two produce different shapes and this lane wants the multi-filing one; `statements_for` stays the single-filing path and is not called here.
- **Dependencies**: Task A completes first
- **Independent**: true
- **Brief item covered**: "Stitch them with `edgartools`' `XBRLS.from_filings()`, requesting `discrete_quarters=False, include_quarterly=True`." — quoted from the brief's Smallest End State step 3 **as amended 2026-07-30**. History, so the change is traceable rather than silent: the brief originally asked for `discrete_quarters=True`, on the belief that it produced discrete quarters usably; measurement showed it produces them under keys that misdescribe them, and the brief itself was amended (not merely overridden here). The brief item's intent — a discrete-quarter series — is met by Task E's subtraction. **This citation was itself false for a few hours on 2026-07-30**, quoting the pre-amendment text after the brief had already changed; fourth instance on this branch of the orchestrator citing a document it was concurrently editing.

## Task E — Derive the discrete quarters the filings do not state

**Widened 2026-07-30 by direction 乙** (§RESOLVED FINDING). Was "Derive the Q4
income column"; now also covers the cash-flow statement, because Task D stopped
asking the dependency for discrete cash-flow quarters.

- **Description**: Add the subtractions the stitching path no longer performs, over
  periods the stitched result already returns (each pair shares a start date).
  **All three subtractions apply to EVERY duration statement**, income and cash
  flow alike: Q2 = YTD6 − Q1, Q3 = YTD9 − YTD6, Q4 = FY − YTD9. Mark every
  produced period as derived. When an input period is missing, produce NO derived
  period — never a partial subtraction, and never a fabricated zero. **Never
  overwrite a period the filer stated**, which is what makes the uniform rule
  safe: this filer files discrete income columns, so only its Q4s are actually
  derived, while a filer that files none would get all three.
  **Amended 2026-07-30.** This said "**Income**: Q4 = FY − Q3-YTD. **Cash flow**:
  Q2/Q3/Q4", assigning Q2 and Q3 to the cash-flow statement alone. The
  implementation applied all three uniformly, and a reviewer measured the
  divergence by deleting the filer's discrete income columns and watching income
  Q2 and Q3 appear. The uniform rule is the better design — this task's own
  ONE-task rationale below turns on income Q4 and cash-flow Q4 being literally the
  same formula — so the Description was corrected rather than the code narrowed.
  A filer without discrete income columns needs those quarters derived too.
- **Module**: investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_series.py
- **Files touched**: investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_series.py, investing-toolkit/tests/analysis/test_kpi_us_quarterly_series.py, investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_periods.py and investing-toolkit/tests/analysis/test_kpi_us_quarterly_periods.py (**both added 2026-07-30** — Task C's module gains a PUBLIC accessor for its day-span windows plus a docstring line recording who reads them, so Task E stops reaching into underscore-private state and the Task G implementer can see the dependency; Task C's committed behaviour is unchanged)
- **Context paths**:
  - investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_series.py
  - investing-toolkit/tests/data/fixtures/us_quarterly_stitched_msft.json
  - investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_periods.py (**added 2026-07-30** — Task C's committed classifier, read at runtime for its day-span windows)
- **Acceptance**:
  - **RED**: `test_derived_q4_revenue_matches_the_recorded_cross_implementation_figure` (**renamed 2026-07-30** from `..._matches_the_independent_implementation` — the old name asserted the very independence this clause records as unreproducible, and a name is the last place a bound like that holds) — runs **OFFLINE against the re-captured fixture `us_quarterly_stitched_msft.json`** (owned by Task D; no network at test time). For MSFT FY2025, derived Q4 revenue equals **76,441,000,000** — the value `edgar/ttm/calculator.py`'s independent `FY − YTD_9M` path produces, recorded here so the two implementations are compared without a live call. **Bound on the word "independent" (2026-07-30)**: the FIGURE is confirmed three ways — the plan, the test constant, and the fixture's own `281,724,000,000 − 205,283,000,000` all agree. Its INDEPENDENCE rests on a session-scoped probe of `calculator.py:665` that the brief itself records as not re-derivable, so no artifact in this repo demonstrates the two implementations agreeing. Do not describe it as verified-independent in code comments; describe the figure as confirmed and its independence as recorded-but-unreproducible. This number is unaffected by direction 乙: it was recomputed from the fixture's income statement (281,724,000,000 − 205,283,000,000) and `discrete_quarters` never applied to the income statement.
  - **RED (cash flow, added 2026-07-30)**: `test_derived_cashflow_quarters_match_the_dependencys_own_arithmetic` — the derived cash-flow quarters equal what the dependency's `_unaccumulate_cashflow_ytd` (`core.py:705`) produces for the same filer and periods. Direction 乙 rejected that function's OUTPUT KEYS, not its arithmetic, so its numbers stay usable as an oracle. **It is NOT an independent one, and the plan must not claim it is** (A4): it applies the same formula to the same stitched inputs (`core.py:716-718` — `:713` is blank; corrected 2026-07-30 after a reviewer found this pointer still stale here even though the same correction had already been applied 200 lines below), so it is a differential test of *implementation* and cannot catch a wrong formula or a wrong period pairing if we make the same choice. The genuinely independent check is this task's other RED, whose `76,441,000,000` comes from `calculator.py:665` deriving Q4 from a different data source. Pin these measured FY2025 operating-cash-flow oracle values: **Q1 34,180 / Q2 22,291 / Q3 37,044 / Q4 42,647** (×10⁶), which sum to the brief's own FY figure 136,162. Record them from a one-off run; do not call the dependency at test time. **Reading a `True`-mode capture as an oracle requires the attribution rule in §RESOLVED FINDING** — the value at `duration_X_Y` is the discrete quarter ending at `Y` — because that capture's own keys are the ones direction 乙 rejected and its labels collide six ways.
  - **GREEN**: both assertions pass offline; **a fiscal year missing any input period the subtraction needs produces NO derived period rather than a wrong one**; and every derived period is marked derived so a consumer can tell a subtraction from a filed figure.
  - **GREEN — the three refusals that RAISE rather than return nothing (ratified 2026-07-30; this clause exists because a reviewer found the artifact declaring refusals the plan had not enumerated).** A *missing* input period is a skip, per the clause above — no derived period, no error. These three are different and stop the run:
    1. **Task C's four day-span windows are not disjoint and ascending.** Repo-wide, not per-filer: it means this repo's own constants are unusable, identical for every caller and every year, and not fixable by skipping. Before this guard existed, a non-disjoint widening **silently deleted every derived quarter for every filer** — see §Task G's carried findings.
    2. **Task C reports a number of year-to-date windows other than two.** Widening the existing two is safe; adding a third names no third role, so it is a breaking change that must be seen.
    3. **A statement cell is present but not a finite number.** *Blast radius, stated as the reviewer asked: one non-finite cell in one line of one statement stops the whole call, taking all three statements and every fiscal year for that filer.* Ratified anyway, because a missing value and a corrupt value are different things — the former is ordinary and already handled per-line, while `Decimal(str(float('nan')))` yields `Decimal('NaN')` that propagates into a figure unequal to itself, with nothing raised. All 794 values in the committed fixture are finite, so the cost today is zero and the signal on the day it fires is immediate. Reversible in the cheap direction: narrowing to a per-line skip later is small, whereas discovering months of silently dropped lines is not.
    **Reworded 2026-07-30 — the previous wording was unsatisfiable.** It said "a fiscal year whose Q3-YTD input is absent", and Task D's 11-filing re-capture removed the only year of that shape. Measured from the shipped fixture: the years starting `2023-07-01` and `2024-07-01` each carry the full Q1 / YTD6 / YTD9 / FY set, and the year starting `2025-07-01` carries Q1 / YTD6 / YTD9 but **no FY column**. So the offline refusal case available is the INVERSE of the one originally named — a year that cannot yield Q4 because its FY column is missing, not its Q3-YTD. Use that year. If a test also wants the absent-Q3-YTD case, construct it by deleting that period from an in-test copy of the fixture; do not re-capture to chase it, because the span is run-date-relative.
- **External surfaces**: none new; operates on Task D's returned structure. The `_unaccumulate_cashflow_ytd` comparison values are captured once, not called live. **Amended 2026-07-30**: the implementation acquired a RUNTIME dependency on Task C's module — it reads Task C's day-span windows rather than restating them, so a widening for a 52/53-week calendar propagates instead of needing a second edit. That is an internal-module dependency, not an external surface, but it was undeclared and a reviewer was right to call the original wording contradicted by the artifact.
- **Dependencies**: Tasks C, D complete first (**amended 2026-07-30** — the `Task C` edge was added when the implementation began reading Task C's windows at runtime; nothing was broken because Task C is committed at `88255590`, but the plan no longer described the artifact. Note the plan had scheduled Task C's classifier to meet the series at Task F, not here.)
- **Independent**: false
- **Note on the Task D edge**: the edge covers Task D's fixture RE-CAPTURE, not just its code, because both of this task's REDs assert against that fixture. Nothing extra needs declaring — Task D's own GREEN names "the re-captured fixture is committed" as part of its done-condition, so `Task D completes first` already carries it. Written as a sibling bullet rather than inside `Dependencies`, which is a closed enumeration SDD parses.
- **Note on why this is ONE task despite two named REDs** (ruled by plan review A4, recorded so round 5 does not re-litigate it): a split is triggered by a **distinct mechanism or a distinct dependency set**, never by test count. Task H was split because it had both — CLI verb registration versus an acquisition loop with its own error contract, on two different dependency sets. Task E's two REDs pin ONE mechanism: difference two cumulative columns sharing a start date, emit the remainder, mark it derived, refuse on a missing input. Income Q4 is literally the same formula as cash-flow Q4, and the dependency implements all four in one function for that reason — its own docstring states the three cash-flow subtractions at `core.py:716-718` (opened and read 2026-07-30; an earlier draft here said `:713-717`, where `:713` is blank). Same Module, same Files touched, same Dependencies, same fixture.
- **Brief item covered**: "Derive the Q4 income column the library does not emit: FY − Q3-YTD, over periods it already returns." — widened to the cash-flow statement by direction 乙; the brief's own §Decision already names the three cash-flow subtractions (`Q2 = YTD6 − Q1`, `Q3 = YTD9 − YTD6`, `Q4 = FY − YTD9`) while attributing them to the dependency, so the arithmetic is the brief's, only its owner changed.

## Task F — Project the series with explicit period labels

- **Description**: Add the quarterly series' own projection — its own shape, NOT
  an extension of `derive-as-filed` (user decision). Every emitted period carries
  its kind from Task C, and a derived period is marked as such.
- **Module**: investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_series.py
- **Files touched**: investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_series.py, investing-toolkit/tests/analysis/test_kpi_us_quarterly_series.py
- **Context paths**:
  - investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_periods.py
  - investing-toolkit/skills/analysis-kpi/scripts/kpi_spine_view.py
- **Acceptance**:
  - **RED**: `test_every_projected_period_declares_its_kind` — over the committed fixture, EVERY period of every statement kind carries a `kind` from Task C's classifier and a `derived` boolean; the two Task E Q4s (`duration_2025-04-01_2025-06-30` and its FY2024 sibling) are `derived: true` and `kind: "discrete_quarter"`; every filed period is `derived: false`; and the balance sheet's instants come back `kind: "instant"`. **Assert the COUNT of projected periods per kind too** — a projection that silently dropped the derived quarters would otherwise satisfy every per-period assertion above.
  - **GREEN**: the projection round-trips the committed fixture with every period labelled; the envelope matches Decision Log one-way door #2 (`pack`/`ticker`/`fetched_at`/`_status`, `statements.<kind>.{lines, periods}`, each period `{key, kind, derived, start, end}`); and `derive-as-filed` is untouched.
  - **GREEN — the one refusal that RAISES (ratified 2026-07-31; this clause exists because the artifact declared a refusal this task's Acceptance did not enumerate — the same class Task E's GREEN already ratified once).** `project_quarterly_series` raises `ValueError` on a ticker that is empty or whitespace-only, before any derivation. A blank ticker is not a missing optional field: the envelope's `ticker` is the only statement of WHOSE numbers the payload holds, and a payload attributed to nobody is shaped exactly like a real one — this arc's recurring defect, and the same reason `stitch_quarterly_statements` refuses an empty filing list rather than answering with a well-formed nothing. It is a WHOLE-CALL refusal because there is nothing to attribute the result to; contrast Task E's per-line skip for a missing cell, which is ordinary. `ticker.upper()` normalisation is not a refusal and is unchanged (six precedents in `pack_us.py`).
    **GREEN clause corrected 2026-07-31** (mislabelled "RED clause corrected 2026-07-30" when first written — a spec review caught both the wrong clause name and the wrong date; a future reader would have hunted for a RED change that never happened): the GREEN said "the existing `derive-as-filed` output is byte-unchanged", which **no test in this task could have failed** — `derive-as-filed` lives in `kpi_spine_view.py` with its own suite (`tests/analysis/test_kpi_spine_view.py`), and neither file is in this task's `Files touched`. Structurally unable to fail is the defect class this branch has now shipped seven times; the honest form of that clause is that this task does not touch it, which its `Files touched` already states and its sibling suite already guards.
- **Dependencies**: Tasks C, E complete first
- **Independent**: false
- **Brief item covered**: "Project into this toolkit's output shape" + the user's option-乙 decision that the quarterly series gets its own projection.

## Task G — Verify the 52/53-week fiscal calendar boundary

- **Description**: Capture one 52/53-week filer's quarters and assert Task C's
  classifier handles them — their quarters vary in length year to year and can
  fall outside a naive 80-100 day window. If they do fall outside, the classifier
  must say so explicitly rather than mis-bucket.
- **Module**: investing-toolkit/tests/analysis/test_kpi_us_quarterly_periods.py
- **Files touched**: investing-toolkit/tests/analysis/test_kpi_us_quarterly_periods.py, investing-toolkit/tests/data/fixtures/us_52_53_week_periods.json, investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_periods.py
- **Context paths**:
  - investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_periods.py
  - docs/loom/references/xbrl-verification-universe.md
- **Acceptance**:
  - **RED**: `test_52_53_week_period_keys_classify_to_their_exact_kind` — a TABLE of real period keys captured from a 52/53-week filer, each asserted against its ONE expected kind (a 13-week quarter → `discrete_quarter`; a 14-week quarter in the 53-week year → `discrete_quarter`; the 371-day annual → `annual`; each YTD → `ytd`). Same table-driven shape as Task C's own RED. **Disjunctive acceptance is forbidden here** — "classifies OR returns unknown" would pass without any 52/53-week-specific work, since a 91-98 day span cannot land in the ~180/270-day bucket under any scheme that already passes Task C.
  - **GREEN**: every row matches its exact expected kind. If any row does not, Task C's windows are wrong for this calendar and widening them is part of this task, not a follow-up.
- **External surfaces**: SEC filings for the chosen 52/53-week filer, captured once into a fixture; the test itself runs offline.
- **CARRY THESE TWO FINDINGS (added 2026-07-30; CORRECTED 2026-07-30 — the first version of this bullet, written from a reviewer's compressed description, stated the mechanism wrongly and both reviewers re-measured it independently. Do not re-compress it.)** This task is scheduled to widen the very windows Task E reads at runtime, so a widening here lands on Task E's subtraction.

  **(1) Task E's role resolution is correct only while Task C's four windows stay DISJOINT and ASCENDING**, and there are two distinct failure modes, not one:

  - **What this task will actually hit.** Widen the nine-month window to `(260, 380)` — which this task's own GREEN authorises — and on a fiscal year carrying BOTH a ~273-day and a ~364-day column, both match, the nine-month role has two candidates, and Task E correctly refuses to guess. The consequence is that **Q3 and Q4 are both suppressed, silently, for every such year and every filer.** On the committed fixture that is every complete year, so the measured outcome of the widening alone is **zero derived periods in all three statements, with no error.** Overlap did not corrupt the arithmetic; it deleted it.
  - **The degenerate emission is a separate case with its own precondition**: a fiscal year that carries an annual column and **NO nine-month column**. Then the widened window has exactly one candidate, the two-candidate refusal correctly does not fire, and the annual column fills both roles — emitting `duration_2025-07-01_2025-06-30` (start after end), all values zero, minuend equal to subtrahend, plus a 180-day `duration_2025-01-01_2025-06-30` carrying real-looking non-zero values. **No year in the committed fixture has that shape**, which is why Task E's test has to construct it by deleting a column. Note the 180-day one classifies through Task C as `ytd`, not `discrete_quarter`, so a consumer filtering on discrete quarters drops it.
  - **As of Task E round 2, neither is reachable**: `_reject_overlapping_role_windows` raises at window-read time, before any derivation. So a non-disjoint widening now stops the run loudly instead of deleting quarters quietly. **Expect that ValueError if you widen into an adjacent window** — it is the guard working, not a bug.

  **(2) Task E requires EXACTLY TWO year-to-date windows.** It reads them through Task C's public `span_windows()` and raises a `ValueError` naming the module, the count found and the count needed. **Widening the existing two is safe; adding a third is a breaking change** — a third window names no third role, so there is nothing for Task E to pair it with.
- **Dependencies**: Task C completes first
- **Independent**: false
- **Brief item covered**: Open Question 4 — "no filer with a 52/53-week calendar was tested in this arc"; promoted to a blocking task because it hits the day-span bucketing mechanism directly.

## Task H — Expose the series as a verb

- **Description**: Wire the series into the pack CLI as a new verb taking a
  ticker and an OPTIONAL years cap (default: all available history, per Task A),
  returning Task F's projection. The acquire loop this task briefly owned is
  now **Task J** — plan review found that bundling it here gave Task H two
  unrelated failing tests, and sequenced the acquire loop behind `D → E → F`
  for no reason.
- **Module**: investing-toolkit/skills/data-markets/scripts/pack_us.py
- **Files touched**: investing-toolkit/skills/data-markets/scripts/pack_us.py, investing-toolkit/skills/data-markets/scripts/pack.py, investing-toolkit/tests/data/test_data_markets_us.py
- **Context paths**:
  - investing-toolkit/skills/data-markets/scripts/pack_us.py
  - investing-toolkit/skills/data-markets/scripts/pack.py
- **Acceptance**:
  - **RED**: `test_quarterly_series_verb_is_registered_and_us_only` — the verb appears in the pack registry, rejects a non-US ticker, and returns the labelled projection for a stubbed series.
  - **RED (partial and empty acquisition, added 2026-08-05 — the obligation Task J's return shape creates)**: `_acquire_filing_span` returns `(filings, failed_items)` and NO status — it defers the `{requested, succeeded, failed}` triple to this verb, so this verb must build it. Two clauses, both offline. (1) A span in which one accession fails to acquire returns `_status: "partial"`, the failed accession in `failed_items`, and `n_filings_used` equal to `len(filings)` — never `len(rows)`; a short answer must not be shaped like a complete one. (2) **An EMPTY span (`requested == 0`) must NOT report `ok`.** Do NOT copy `pack_reconstruct`'s status formula (`pack_us.py:1597-1601`): its `requested == 0 → ok` is the defect the brief records (§Error), and it is correct only for that verb's "nothing was asked for" case. Here a zero-filing span is a real answer to a real request — a foreign private issuer files 20-F, not 10-Q/10-K — and must surface as an explicit named failure, not as success over an empty series.
    **This is the THIRD unstated cross-task obligation on this branch**, and like the first two it was found by a reviewer rather than by the plan (Task F→H money serialisation; Task B→J cache stubbing; now Task J→H status). Three instances is a pattern, not a coincidence: a task that hands its caller a partial result must state, in the CALLER's entry, what the caller now owes — and the plan has never once caught this by itself.
  - **RED (money serialisation, added 2026-07-31 — this task's likeliest silent defect)**: Task F's projection returns line values as `Decimal`. **This verb must project them to exact text EXPLICITLY** — `pack_us._decimal_text` (`pack_us.py:1296-1312`) is the in-repo helper and its own docstring states why. It must NOT inherit the facade's fallback: `pack.py`'s `_emit` calls `json.dumps(obj, indent=2, default=str)` (**verified 2026-07-31 by opening it**), which serialises a `Decimal` **silently** — and would serialise a binary float just as happily, which is the whole point. Contrast `kpi_spine_view`, which dumps BARE (`json.dump(_project_money_to_text(view), ...)`), so a stray `Decimal` there really does raise. **Pin it with a bare `json.dumps` in the test, and make the stubbed series carry at least one `Decimal`** — otherwise this task's own RED goes green on a stub that has none, while the live run inherits the fallback. This entry exists because Task F's implementer described the behaviour as deliberate fail-loud; a spec reviewer opened the actual downstream path and found it silent.
  - **GREEN**: the test passes, the verb is declared in the skill's CLI reference so it has a documented entry point, AND a ONE-OFF live run against a real filer returns a series whose discrete-quarter count and date span are both recorded in the task's close-out — the requirement is "all available history, ten years as the floor", and no fixture-based test can observe it.
- **External surfaces**: the pack CLI surface; the new verb must be added to `analysis-kpi/references/cli-reference.md` and verified to run.
- **Dependencies**: Tasks F, J complete first
- **Independent**: false
- **Brief item covered**: "A verb that, given a ticker, returns the three statements as a discrete-quarter series over **ALL available history**, where **every period states what it is**."
- **Note on the annual verb**: `pack_reconstruct` SURVIVES unchanged. The brief's What-Becomes-Obsolete asks this to be stated rather than left implicit: the two paths differ in shape (single-filing reconstruction vs multi-filing stitched series) and in dependency (`statements_for` vs `XBRLS`), so this task neither replaces nor deprecates it. Revisit only if the series verb proves able to answer every annual question.

## Task I — Verify the oldest available filings still parse

- **Description**: The span now reaches back to the start of XBRL mandate
  (~2009-2011), and only 2014+ has been verified. Capture the OLDEST available
  10-Q for one filer and assert the production parse path still yields three
  classified statement kinds with populated hierarchy — or fails loudly.
- **Module**: investing-toolkit/tests/data/test_us_oldest_filing_parse.py
- **Files touched**: investing-toolkit/tests/data/test_us_oldest_filing_parse.py, investing-toolkit/tests/data/fixtures/us_oldest_filing_rows.json, investing-toolkit/tests/data/fixtures/capture_us_oldest_filing.py (**added 2026-07-30** — the capture script that regenerates the fixture; produced by this task and cited by its test, but omitted from this list in the original plan, exactly as Task D's was)
- **Context paths**:
  - investing-toolkit/skills/analysis-kpi/scripts/kpi_us_statement_shape.py
  - investing-toolkit/skills/data-markets/scripts/sec_edgar_client.py
- **Acceptance**:
  - **RED**: `test_oldest_available_filing_parses_or_fails_loudly` — against a committed fixture captured from the oldest 10-Q the filing list yields, `statements_for` returns three classified kinds and a non-zero `calculation_parent` rate; if it cannot, the test asserts an explicit, named failure rather than a silent empty result.
  - **GREEN**: the assertion passes, and the earliest year that parses is recorded in the test's docstring so the series' real floor is documented rather than assumed.
- **External surfaces**: SEC filings for the chosen filer, captured once into a fixture; the test runs offline.
- **Dependencies**: Task A completes first
- **Independent**: true
- **Brief item covered**: "the parse-depth risk, which now reaches back to the start of XBRL mandate (~2009-2011) where only 2014+ has been verified"

## Task J — Acquire a filing span, reporting partial failure

**Added 2026-07-29.** Split out of Task H by plan review: bundling the acquire
loop into the CLI-wiring task gave Task H two unrelated failing tests, and
sequenced the loop behind `D → E → F` although it has no relationship to the
projection.

- **Description**: Turn Task A's accession rows into the acquired filing objects
  Task D's function accepts, and decide what a partially-failed acquisition
  does. This is the responsibility Task D shed when its Description was amended
  to honour the `analysis-*` → `data-markets` subprocess boundary; without this
  task, no task in the plan covers accession rows → filing objects. An
  established in-repo pattern for this exact shape lives at
  `pack_us.py:1549-1563` — follow that shape rather than inventing a second one.
  **Both citations here were opened and read on 2026-07-30**, after an earlier
  draft of this task cited `:754-823,1476` on a review report's description
  without either author opening the lines. What is actually there:
  `:1549-1563` iterates accession rows, calls
  `sec_edgar_client._acquire_raw_filing(accession)`, appends
  `{"accession": accession, **filing}` to `failed_items` and `continue`s when the
  return is an error dict — i.e. exactly this task's loop, loud-skip included.
  `:1476` is prose in the surrounding docstring stating that an acquisition
  failure "is a LOUD skip recorded in `failed_items`, never a" silent one — the
  convention, not the loop.
- **Module**: investing-toolkit/skills/data-markets/scripts/pack_us.py
- **Files touched**: investing-toolkit/skills/data-markets/scripts/pack_us.py, investing-toolkit/tests/data/test_data_markets_us.py
- **Context paths**:
  - investing-toolkit/skills/data-markets/scripts/pack_us.py
  - investing-toolkit/skills/data-markets/scripts/sec_edgar_client.py
  - investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_series.py
- **Acceptance**:
  - **RED**: `test_partial_acquisition_failure_is_reported_not_silent` — when one accession in the span fails to acquire, the loop records that accession as a failed item AND still returns the filings acquired from the rest. A run that silently returns a shorter span, or that aborts the whole request, fails this test. **The same test also pins the loop's OUTPUT CONTRACT**: what it yields must be whatever `_acquire_raw_filing` returns, never an accession row or dict — that is the input contract Task D's Description fixes, and it is checkable from Task J's own position. **Narrowed 2026-07-30**: an earlier wording asked this test to prove the objects are accepted by Task D's function unmodified, which Task J cannot execute — it declares no dependency on Task D, and no committed raw-filing fixture exists in any task's `Files touched` to feed D's function offline. That end-to-end seam stays where it already lives, in Task H's one-off live run.
  - **GREEN**: the test passes offline, and a failed accession appears in the run's `failed_items` with its accession number, matching the existing per-accession failure shape at `pack_us.py:1553-1555`.
- **External surfaces**: none new — reuses `sec_edgar_client._acquire_raw_filing` through Task B's cache.
- **Note on Task B's cache (added 2026-07-31, from Task B's spec review — an obligation Task B created that this entry did not state)**: **stub at `sec_edgar_client._acquire_raw_filing`**, the boundary this file's own docstring already names (`test_data_markets_us.py:61-67`) — **not** at `edgar.get_by_accession_number`. Task B put a disk cache behind the latter, and `test_data_markets_us.py` pins no cache directory (**verified 2026-07-31: zero occurrences of `INVESTING_TOOLKIT_CACHE` in that file, and all six existing stub sites use the higher boundary**), so a lower stub would let the loop take a hit from the developer's real cache directory. On a second run the loop would take that disk hit instead of reaching the stub, and `test_partial_acquisition_failure_is_reported_not_silent` would **stop exercising the failure it exists to pin, without failing**. If a lower stub is ever needed, add an autouse `INVESTING_TOOLKIT_CACHE` fixture first — `test_sec_narrative.py:137-144` and `test_exhibit_fetch.py:88-93` are the pattern.
  **This is the second unstated cross-task obligation on this branch** — Task F created one for Task H (money serialisation) that also had to be written in after the fact. Both were found by a reviewer, neither by the plan. A task that changes a seam another task calls through should state what it now requires of that caller, in the caller's own entry, before the caller is dispatched.
- **Dependencies**: Tasks A, B complete first
- **Independent**: false
- **Brief item covered**: "Assemble the filing list — every 10-Q and 10-K available, oldest first (~77 filings for a filer with full XBRL history), optionally capped." — the acquisition half of that item; Task A covers the listing half.
- **Note on the Task B edge**: this edge is declared, not merely prose. Task H's GREEN mandates a live multi-filing run that the brief measures at 20-37 minutes uncached (brief §Boundary). An acquire loop built before the cache would make that run unusable, so the ordering is semantic, not stylistic.

---

## Decision Log

Added after the plan-document-reviewer PASS, per the kickoff-briefing protocol
(one-way doors brief to the user; two-way doors log here). The entries under the
two headings below were not a re-review trigger — they changed no task's
Description, Acceptance, Dependencies, or scope. The 2026-07-29 amendment
recorded in the third section DID change two Descriptions and one Acceptance,
and was re-reviewed; it is logged here rather than silently applied.

### One-way doors — briefed and approved by the user 2026-07-29

1. **Period-kind vocabulary**: `discrete_quarter | ytd | annual | instant | unknown`,
   with `derived: true|false` as a SEPARATE flag rather than a sixth kind. Rationale:
   a derived Q4 is both a discrete quarter AND derived — orthogonal axes, and
   collapsing them makes "every discrete quarter regardless of provenance"
   unaskable. `unknown` exists so an out-of-window span is VISIBLE rather than
   forced into the nearest bucket.
2. **Projection envelope**: reuse the existing pack envelope
   (`pack` / `ticker` / `fetched_at` / `_status`) with
   `statements.<kind>.{lines, periods}`, each period carrying
   `{key, kind, derived, start, end}`. No new top-level shape — existing consumers
   and tooling already read this envelope.
   **WIDENED 2026-07-31 by the user, on a spec review's escalation**: one more
   top-level key, **`n_filings_used`** — the SIXTH key of the returned dict, or the
   fifth envelope metadata field if you exclude the `statements` container, and this
   sentence says both because the count was miscounted twice on this branch — present
   only when the input reports one
   (absent rather than fabricated, following `kpi_spine_view`'s own optional-marker
   doctrine). It earns the widening because Task J's partial-acquisition failure is
   otherwise invisible downstream — a short answer and a complete one have the same
   shape, which is this arc's recurring defect. **How this came up matters more than
   the field**: Task F's implementer added it unasked, and the one test written to
   stop a quiet widening asserted the widened set under the name
   `test_the_envelope_is_the_one_the_user_ratified` — a guard that ratified what it
   existed to catch, under a name claiming an approval that did not yet exist. The
   approval now exists; the module docstring was corrected and the test renamed to
   `test_the_envelope_key_sets_are_exact_at_every_level` (round 2), so the name
   states what it checks rather than who approved it. **The durable rule that came
   out of it**: a name saying WHO APPROVED cannot be checked by running it; a name
   saying WHAT IS CHECKED can.
3. **Cache on-disk format**: ~~a thin envelope `{accession, fetched_at, sec_url,
   document}`, not the bare document.~~ **RE-DECIDED 2026-07-31 by the user, on an
   implementer's `NEEDS_CONTEXT`** — the original rested on a premise that
   measurement refuted, so it is superseded rather than amended. The provenance
   rationale is unchanged and still load-bearing: a few extra bytes buy provenance,
   and adding a field later would invalidate every cached filing on every user's
   machine, at 20-37 minutes per filer to rebuild.

   **The ratified format**:
   `{accession, fetched_at, sec_url, filing: {accession_number, cik, company, form, filing_date}}`

   **What was wrong with the original, measured rather than argued.** There is no
   document at this seam to cache. `_acquire_raw_filing` never fetches a filing
   document — it resolves an accession against SEC's quarterly INDEX files and
   builds a `Filing` from an index row. So `document` had no producer, and the
   envelope carried none of the five values needed to rebuild the object. The
   expensive thing is the index scan, and edgartools caches it with a process-local
   `@lru_cache(maxsize=8)`, which is exactly why the brief measured a fresh process
   re-paying in full. A disk cache is still the right fix; its payload was wrong.

   **A premise the user was given, now known false**: this plan and the dispatch
   both stated "a `Filing` is not serialisable". Measured: it pickles in a couple of
   hundred bytes — an implementer measured 216 and a reviewer re-measured 234 for the
   same filer, and the discrepancy is recorded rather than resolved because nothing
   rests on it — and the library ships `to_dict()` / `from_dict()`. Pickle is still NOT the format
   — a third-party object graph is a bad durable format and JSON via `cache_util` is
   this repo's convention — but the user re-decided knowing the premise was wrong.

   **Why the library's own `to_dict()` shape**: adopting the dependency's
   serialisation means a future edgartools field change surfaces as a mismatch
   rather than as our own silent drift.

   **`sec_url` stays, but must be the reconstructable archives URL** — built from
   `cik` + accession with `SEC_ARCHIVES_URL` and `_accession_nodash`, never
   `Filing.filing_url`. Measured: `filing_url` resolves the primary document over
   the wire (an implementer's probe died on `IdentityNotSetException`), so using it
   would add a network round-trip on every cache MISS — on the one seam whose
   purpose is removing network cost.

   **Do NOT use `Filing.from_dict` to read the cache back.** Its source coerces
   `filing_date=str(...)`, so a cache hit would carry `.filing_date` as `str` while
   a live acquisition carries `datetime.date`. Construct with `date.fromisoformat`
   instead. That divergence is invisible to a hit-count assertion, and it is exactly
   the RED's "a wrong answer with the right shape".

### Two-way doors — decided without escalation

- Classifier day-span windows align with the dependency's own boundaries
  (quarter 80-100, YTD 175-190 / 260-285, annual 350-380) rather than inventing
  new ones. Task G measures whether the 52/53-week calendar requires widening.
- Task A's function signature and internal data structures.
- MSFT as the stitched fixture subject — its derived Q4 figure is already
  cross-verified by two independent implementations in the dependency.
- Task I's oldest-filing subject follows from whatever Task A's list yields; not
  pinned in advance.

### Amendment 2026-07-29/30 — acquisition moves out of Task D, and lands in Task J

**Ownership moved twice.** Original Task D → (2026-07-29 amendment) Task H →
(2026-07-29 plan review) the new Task J. The task bodies are the current
contract; this section is the history of how they got there.

**What changed**: Task D's Description (takes already-acquired filing objects,
not accession rows); Task H's Description briefly took the acquire loop, then
shed it; **Task J** was created to own the loop, with its own RED covering
partial-acquisition failure, because bundling it into Task H gave Task H two
unrelated failing tests and sequenced the loop behind `D → E → F` for no reason.

**Why**: Task D as originally written was **unsatisfiable**. It asked an
`analysis-*` module to consume accession rows, which forces it to acquire
filings, which forces a direct import of `data-markets` — and this repo crosses
that boundary by subprocess, never by import. **The three precedents are cited
with per-line content in Task D's Description; do NOT re-copy line numbers from
here or from any review report without opening the files.** Both earlier attempts
to cite this convention were wrong, in two mutually inconsistent ways, and
neither author had opened a file — the implementer who did was the one who caught
it.

The implementer hit the boundary conflict mid-task and resolved it by changing
the signature; the round-2 spec review found that the change also orphaned a
responsibility, because after the move NO task in the plan covered accession rows
→ filing objects. Task J's RED closes that hole.

**Classification**: two-way door, no product consequence — an internal module
boundary with one caller. Logged rather than escalated. The plan edit itself was
re-reviewed because it touches Descriptions and Acceptance, which the amendment
rules do not exempt.

**Worth noting**: five rounds of plan review passed this plan 14/14 without
catching that one of its tasks contradicted a convention recorded in the repo's
own `CLAUDE.md`. It was found by writing the code and hitting the wall.
