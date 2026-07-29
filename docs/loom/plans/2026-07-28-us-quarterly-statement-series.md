# Plan: US quarterly three-statement series, 10+ years

**Source brief**: docs/loom/specs/2026-07-28-us-quarterly-statement-series.md
**Total tasks**: 9
**Critical-path depth**: 5 (A → D → E → F → H)
**Execution order**: parallel-where-possible
**Plan-document-reviewer verdict**: PASS (2026-07-29, round 5, 14/14). Round 3 also PASSed; that verdict was voided by the user's 2026-07-29 clarification that ten years is a FLOOR, not a target — a substantive scope change, re-reviewed.

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

- **Description**: Add a function that takes the accession list from Task A and
  returns the three statements via `XBRLS.from_filings(...)` with
  `discrete_quarters=True, include_quarterly=True` **and `max_periods` set from
  the size of the assembled list, never left at its default**. No derivation.
  `XBRLS.get_statement`'s signature defaults `max_periods=8`, so a 77-filing
  request left unset silently returns 8 periods with every test still green —
  that is the defect this wording exists to prevent.
- **Module**: investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_series.py
- **Files touched**: investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_series.py, investing-toolkit/tests/analysis/test_kpi_us_quarterly_series.py, investing-toolkit/tests/data/fixtures/us_quarterly_stitched_msft.json
- **Context paths**:
  - investing-toolkit/skills/analysis-kpi/scripts/kpi_us_statement_shape.py
  - investing-toolkit/skills/data-markets/scripts/sec_edgar_client.py
- **Acceptance**:
  - **RED**: `test_stitched_periods_are_discrete_and_not_truncated` — against the committed fixture **`investing-toolkit/tests/data/fixtures/us_quarterly_stitched_msft.json`**, captured ONCE for MSFT by this task and checked in, assert BOTH that the cash-flow duration periods are ~90-day (not ~180/270-day) AND that the returned period COUNT matches what the fixture's filing count implies — a count equal to the `max_periods` default of 8 fails the test.
  - **GREEN**: all three statement kinds return, the fixture is committed, and the cash-flow assertion passes offline. **This task owns that fixture — Task E's RED asserts against it.**
- **External surfaces**: `edgartools==5.42.0` `XBRLS.from_filings` / `get_statement`; pinned, no new dependency.
- **Reuse-adequacy**: reuses the dependency's stitching rather than this repo's `statements_for` — the two produce different shapes and this lane wants the multi-filing one; `statements_for` stays the single-filing path and is not called here.
- **Dependencies**: Task A completes first
- **Independent**: true
- **Brief item covered**: "Stitch them with edgartools' XBRLS.from_filings(), requesting discrete_quarters=True, include_quarterly=True."

## Task E — Derive the Q4 income column

- **Description**: Add the one subtraction the stitching path does not perform:
  Q4 income = FY − Q3-YTD, over periods the stitched result already returns
  (they share a start date). Mark the produced period as derived.
- **Module**: investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_series.py
- **Files touched**: investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_series.py, investing-toolkit/tests/analysis/test_kpi_us_quarterly_series.py
- **Context paths**:
  - investing-toolkit/skills/analysis-kpi/scripts/kpi_us_quarterly_series.py
  - investing-toolkit/tests/data/fixtures/us_quarterly_stitched_msft.json
- **Acceptance**:
  - **RED**: `test_derived_q4_revenue_matches_the_independent_implementation` — runs **OFFLINE against the committed fixture `us_quarterly_stitched_msft.json`** (captured by Task D; no network at test time). For MSFT FY2025, derived Q4 revenue equals **76,441,000,000** — the value `edgar/ttm/calculator.py`'s independent `FY − YTD_9M` path produces, recorded here so the two implementations are compared without a live call.
  - **GREEN**: the assertion passes offline, and a fiscal year whose Q3-YTD input is absent from the fixture produces NO derived period rather than a wrong one.
- **External surfaces**: none new; operates on Task D's returned structure.
- **Dependencies**: Task D completes first
- **Independent**: false
- **Brief item covered**: "Derive the Q4 income column the library does not emit: FY − Q3-YTD, over periods it already returns."

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
  returning Task F's projection.
- **Module**: investing-toolkit/skills/data-markets/scripts/pack_us.py
- **Files touched**: investing-toolkit/skills/data-markets/scripts/pack_us.py, investing-toolkit/skills/data-markets/scripts/pack.py, investing-toolkit/tests/data/test_data_markets_us.py
- **Context paths**:
  - investing-toolkit/skills/data-markets/scripts/pack_us.py
  - investing-toolkit/skills/data-markets/scripts/pack.py
- **Acceptance**:
  - **RED**: `test_quarterly_series_verb_is_registered_and_us_only` — the verb appears in the pack registry, rejects a non-US ticker, and returns the labelled projection for a stubbed series.
  - **GREEN**: the test passes, the verb is declared in the skill's CLI reference so it has a documented entry point, AND a ONE-OFF live run against a real filer returns a series whose discrete-quarter count and date span are both recorded in the task's close-out — the requirement is "all available history, ten years as the floor", and no fixture-based test can observe it.
- **External surfaces**: the pack CLI surface; the new verb must be added to `analysis-kpi/references/cli-reference.md` and verified to run.
- **Dependencies**: Task F completes first
- **Independent**: false
- **Brief item covered**: "A verb that, given a ticker, returns the three statements as a discrete-quarter series over **ALL available history**, where **every period states what it is**."
- **Note on the annual verb**: `pack_reconstruct` SURVIVES unchanged. The brief's What-Becomes-Obsolete asks this to be stated rather than left implicit: the two paths differ in shape (single-filing reconstruction vs multi-filing stitched series) and in dependency (`statements_for` vs `XBRLS`), so this task neither replaces nor deprecates it. Revisit only if the series verb proves able to answer every annual question.

## Task I — Verify the oldest available filings still parse

- **Description**: The span now reaches back to the start of XBRL mandate
  (~2009-2011), and only 2014+ has been verified. Capture the OLDEST available
  10-Q for one filer and assert the production parse path still yields three
  classified statement kinds with populated hierarchy — or fails loudly.
- **Module**: investing-toolkit/tests/data/test_us_oldest_filing_parse.py
- **Files touched**: investing-toolkit/tests/data/test_us_oldest_filing_parse.py, investing-toolkit/tests/data/fixtures/us_oldest_filing_rows.json
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
