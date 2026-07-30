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
- **Task C needs no change and becomes correct for all three statements.** It is
  committed (`88255590`); its span-bucketing was only ever wrong because the
  cash-flow keys lied. Do not edit it.
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
  validity. Cache the raw document, not the parsed object.
- **Module**: investing-toolkit/skills/data-markets/scripts/sec_edgar_client.py
- **Files touched**: investing-toolkit/skills/data-markets/scripts/sec_edgar_client.py, investing-toolkit/tests/data/test_raw_filing_cache.py
- **Context paths**:
  - investing-toolkit/skills/data-markets/scripts/sec_edgar_client.py
  - investing-toolkit/skills/data-markets/scripts/cache_util.py
- **Acceptance**:
  - **RED**: `test_second_acquire_of_same_accession_does_not_refetch` — a spy on the fetch path records exactly one call across two `_acquire_raw_filing` invocations for one accession.
  - **GREEN**: the spy records one fetch; a third invocation in a fresh process also records zero fetches (disk hit).
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
  **Income**: Q4 = FY − Q3-YTD. **Cash flow**: Q2 = YTD6 − Q1,
  Q3 = YTD9 − YTD6, Q4 = FY − YTD9. Mark every produced period as derived.
  When an input period is missing, produce NO derived period — never a partial
  subtraction, and never a fabricated zero.
- **Module**: investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_series.py
- **Files touched**: investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_series.py, investing-toolkit/tests/analysis/test_kpi_us_quarterly_series.py
- **Context paths**:
  - investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_series.py
  - investing-toolkit/tests/data/fixtures/us_quarterly_stitched_msft.json
- **Acceptance**:
  - **RED**: `test_derived_q4_revenue_matches_the_independent_implementation` — runs **OFFLINE against the re-captured fixture `us_quarterly_stitched_msft.json`** (owned by Task D; no network at test time). For MSFT FY2025, derived Q4 revenue equals **76,441,000,000** — the value `edgar/ttm/calculator.py`'s independent `FY − YTD_9M` path produces, recorded here so the two implementations are compared without a live call. This number is unaffected by direction 乙: it was recomputed from the fixture's income statement (281,724,000,000 − 205,283,000,000) and `discrete_quarters` never applied to the income statement.
  - **RED (cash flow, added 2026-07-30)**: `test_derived_cashflow_quarters_match_the_dependencys_own_arithmetic` — the derived cash-flow quarters equal what the dependency's `_unaccumulate_cashflow_ytd` (`core.py:705`) produces for the same filer and periods. Direction 乙 rejected that function's OUTPUT KEYS, not its arithmetic, so its numbers stay usable as an oracle. **It is NOT an independent one, and the plan must not claim it is** (A4): it applies the same formula to the same stitched inputs (`core.py:713-717`), so it is a differential test of *implementation* and cannot catch a wrong formula or a wrong period pairing if we make the same choice. The genuinely independent check is this task's other RED, whose `76,441,000,000` comes from `calculator.py:665` deriving Q4 from a different data source. Pin these measured FY2025 operating-cash-flow oracle values: **Q1 34,180 / Q2 22,291 / Q3 37,044 / Q4 42,647** (×10⁶), which sum to the brief's own FY figure 136,162. Record them from a one-off run; do not call the dependency at test time. **Reading a `True`-mode capture as an oracle requires the attribution rule in §RESOLVED FINDING** — the value at `duration_X_Y` is the discrete quarter ending at `Y` — because that capture's own keys are the ones direction 乙 rejected and its labels collide six ways.
  - **GREEN**: both assertions pass offline; **a fiscal year missing any input period the subtraction needs produces NO derived period rather than a wrong one**; and every derived period is marked derived so a consumer can tell a subtraction from a filed figure.
    **Reworded 2026-07-30 — the previous wording was unsatisfiable.** It said "a fiscal year whose Q3-YTD input is absent", and Task D's 11-filing re-capture removed the only year of that shape. Measured from the shipped fixture: the years starting `2023-07-01` and `2024-07-01` each carry the full Q1 / YTD6 / YTD9 / FY set, and the year starting `2025-07-01` carries Q1 / YTD6 / YTD9 but **no FY column**. So the offline refusal case available is the INVERSE of the one originally named — a year that cannot yield Q4 because its FY column is missing, not its Q3-YTD. Use that year. If a test also wants the absent-Q3-YTD case, construct it by deleting that period from an in-test copy of the fixture; do not re-capture to chase it, because the span is run-date-relative.
- **External surfaces**: none new; operates on Task D's returned structure. The `_unaccumulate_cashflow_ytd` comparison values are captured once, not called live.
- **Dependencies**: Task D completes first
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
  - **RED**: `test_every_projected_period_declares_its_kind` — no projected period lacks a kind, and the Q4 period from Task E is marked derived.
  - **GREEN**: the projection round-trips a fixture with every period labelled, and the existing `derive-as-filed` output is byte-unchanged.
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
3. **Cache on-disk format**: a thin envelope `{accession, fetched_at, sec_url,
   document}`, not the bare document. A few extra bytes buy provenance; adding it
   later would invalidate every cached filing on every user's machine, at 20-37
   minutes per filer to rebuild.

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
