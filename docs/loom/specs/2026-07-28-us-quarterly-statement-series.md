# US quarterly three-statement series, 10+ years — brief

- **Date**: 2026-07-28
- **Stage**: brainstorming output. Feeds `writing-plans`.
- **Branch**: `feat-us-quarterly-statement-series` (renamed from
  `feat-as-filed-hierarchy-selection` once the hierarchy-selection work that
  named it was withdrawn on measurement — see §What Becomes Obsolete).
- **Evidence**: `docs/loom/audits/2026-07-28-revenue-chain-and-hierarchy-audit.md`
  §4, §5, §8, plus the live probes recorded in §Current State Evidence below.

## Problem

**The job**: look at one US-listed company's income statement, balance sheet and
cash-flow statement, quarter by quarter, over at least ten years — and be able to
trust each number enough to reason about a trend.

Stated by the user, twice, narrowing each time: first "quarterly three statements
plus operational KPIs", then "quarterly as the minimum unit, at least 10 years of
history, local accumulation is nice-to-have not required". The accumulation
clause matters: the job is **analysis on demand**, not maintaining a warehouse.
What must not happen is a number that looks like a quarter and is actually a
nine-month cumulative — a wrong trend reads as a real one.

## Users

The repo's owner, doing single-stock fundamental analysis, on a laptop, working
from this toolkit's CLI. No team, no scheduled pipeline, no SLA. Fetching is
allowed to be slow the first time; it is not allowed to be slow every time (see
the caching decision below — this is the one place the user overrode a "defer
it" recommendation).

Job story: *when I am forming a view on a company, I want its three statements at
quarterly granularity for a decade, so I can see whether a trend is real or an
artefact of one good year.*

## Smallest End State

A verb that, given a ticker, returns the three statements as a discrete-quarter
series over **ALL available history**, where **every period states what it is**.

**Clarified by the user 2026-07-29: ten years is a FLOOR, not a target — "as much
as is available".** So the span parameter inverts from the earlier draft: the
default is everything, and `--years N` becomes an optional UPPER bound for a
quick look. This changes three things — the filing count (~77, not ~40), the cold
cost (20-37 min, not 11-19), and the parse-depth risk, which now reaches back to
the start of XBRL mandate (~2009-2011) where only 2014+ has been verified.

1. Assemble the filing list — every 10-Q and 10-K available, oldest first
   (~77 filings for a filer with full XBRL history), optionally capped.
2. **Cache the raw filings on disk.** They are immutable, so the cache needs no
   invalidation policy beyond existence.
3. Stitch them with `edgartools`' `XBRLS.from_filings()`, requesting
   **`discrete_quarters=False, include_quarterly=True`**. **Amended 2026-07-30**:
   this step said `discrete_quarters=True` until measurement showed that setting
   makes the cash-flow statement file discrete quarters under CUMULATIVE period
   keys — a 364-day key holding one quarter, and two keys holding the same
   quarter's value. The dependency's arithmetic is right; its output keys
   misdescribe it. Full measurement and the user's direction decision are recorded
   in the plan's §RESOLVED FINDING 2026-07-30.
4. Derive the Q4 income column the library does not emit: `FY − Q3-YTD`, over
   periods it already returns.
5. **Label every period explicitly** — discrete quarter / year-to-date / annual /
   derived — rather than leaving it to be inferred from a day-span.
6. Project into this toolkit's output shape.

## Current State Evidence

**Forward** — `pack_reconstruct` (`pack_us.py:1456`) resolves a CIK
(`sec_edgar_client.resolve_cik`), calls `list_filings(cik, ["10-K"], 8)` with the
form list as an **inline literal** (`pack_us.py:1539-1541`) and
`RECONSTRUCT_ANNUAL_FILINGS = 8` (`:1218`), then per accession
`_acquire_raw_filing` → `kpi_us_statement_shape.statements_for` → projection by
`_reconstruction_payload` (`:1287-1295`). The verb takes **no form parameter**.

**Reverse** — the pack is consumed by the CLI facade (`pack.py:116`, dispatch at
`pack_us.py:1846`) and by `kpi_spine_view derive-as-filed`
(`kpi_spine_view.py:1244-1287`), which projects 14 canonical fields × periods.
Nothing persists: `pack_us.py:1465-1472` states the reconstruction is recomputed
per run and declares no `source_kind`, deliberately.

**Error** — a per-accession failure returns an error dict that becomes a
`failed_items` entry (`pack_us.py:1553-1555`); the verification layer is
contained so a refusal degrades the run rather than aborting it (`:1581-1601`).
Note the known defect that `requested == 0` reports `ok` (BACKLOG entry, fix
shape already decided).

**Data** — `Line` (`kpi_us_statement_shape.py:319-326`) carries `label`,
`concept`, `level`, `weight`, `calculation_parent`, `balance`, `values`,
`decimals`. Periods exist only as composite key strings
(`duration_2024-07-01_2025-06-30`, `instant_2025-06-30`) — **there is no period
type field anywhere in the row schema**, which is why step 5 above is a
requirement and not a nicety.

**Boundary** — `_acquire_raw_filing` (`sec_edgar_client.py:1200`; was `:1121`
when this brief was written — Task A's `assemble_quarterly_filing_span` landed
above it and shifted it ~79 lines, verified 2026-07-30) has **no cache
wrapper**; measured cold cost 15.9-29.1 s per filing, and a fresh process
re-pays it in full (~16.2 s). The per-filing figure is the durable measurement;
the total follows the span. At the ~40 filings of the original ten-year framing
that was 11-19 minutes; at the ~77 of the clarified all-available-history
requirement it is **20-37 minutes every run**. `cache_util`'s TTLs (`cache_util.py:66-92`) cover only the
submissions/facts layer. edgartools' own disk cache holds SEC quarterly index
files, not filing documents.

**Evidence paths**: probes and captures for this brief were session-scoped;
their measured conclusions are recorded in
`docs/loom/audits/2026-07-28-revenue-chain-and-hierarchy-audit.md` §8 and in the
findings quoted throughout this brief. The 10-Q feasibility probe, the
12-year-depth probe and the two edgartools capability probes are NOT re-derivable
from the repo.

## Decision

Adopt `edgartools`' stitching rather than building the series machinery, and
build only the things it does not do: the filing-list assembly, a cache, and
**four subtractions across two statements** — one for the income statement's Q4,
three for the cash-flow statement's Q2/Q3/Q4.

**Amended 2026-07-30**: this said "one subtraction" on the belief that the
dependency's cash-flow unaccumulation was usable as shipped. Its arithmetic is
correct and its output keys are not — it writes discrete quarters into the
cumulative period keys they were derived from, so a full-fiscal-year key holds one
quarter. We therefore ask it for the cumulative columns as filed and do the
subtraction ourselves, which keeps one invariant true everywhere: **a period key's
span always describes the span of its value.** Measurement, the two rejected
alternatives, and the user's decision are in the plan's §RESOLVED FINDING
2026-07-30.

The pivotal measurements:

- **10-Q works today.** Five filers, zero exceptions, three statement kinds each,
  `calculation_parent` rates matching or exceeding their own 10-Ks, and **zero
  spine-field regressions** versus the same filer's 10-K.
- **Depth holds.** KO's oldest 10-Q (filed 2014) and a 2021 one both parse
  cleanly — 3/3 kinds, 76-97% `calculation_parent`. The taxonomy-drift risk did
  not materialise. Raw material exists: 35-36 10-Qs + 12 10-Ks per filer over
  12 years, no anomalous gaps.
- **The hard arithmetic already ships, twice.** `_unaccumulate_cashflow_ytd`
  (`edgar/xbrl/stitching/core.py:705`) does `Q2 = YTD6 − Q1`,
  `Q3 = YTD9 − YTD6`, `Q4 = FY − YTD9`; live-verified on MSFT (FY2025 operating
  cash flow 136,162 − 93,515 = 42,647, matching the library exactly). A second,
  independent implementation (`edgar/ttm/calculator.py:665`) derives Q4 from a
  different data source and produced the **same** FY2025 Q4 revenue, 76,441 —
  which is also what `FY − Q3-YTD` gives by hand on the stitched output. Two
  implementations, two sources, one number.
- **What it does not do**: the discrete-quarter derivation is gated to cash flow
  (`core.py:181`, `if discrete_quarters and statement_type == 'CashFlowStatement'`),
  so the stitched income statement has no Q4 column. The inputs are present — FY
  and Q3-YTD share a start date — so this is one subtraction, not a subsystem.
- **Balance sheet needs nothing**: instant-based, and the stitched span returned
  every quarter-end with no gaps.

**Caching is now load-bearing, not merely convenient.** At ~77 filings and
20-37 minutes cold, a run without cache is unusable for iterative analysis. It
was already in v1 by user decision; the span clarification removes the option of
deferring it.

**Caching is in v1 by explicit user decision**, overriding a recommendation to
defer it. The measured cost is per run, not one-off, because nothing caches
filing documents — 20-37 minutes at the clarified span. Filings are immutable, so
this is the cheapest safe cache in the system.

## Alternatives Considered

| Option | Why not |
|---|---|
| **Build the series machinery ourselves** (the original plan) | Rejected on evidence. The two derivations we scoped as the core risk — YTD→discrete and Q4 — already ship in a pinned dependency, live-verified. Building them would duplicate working code and re-introduce the risk it already handles (its incomplete-set fallback declines to subtract rather than fabricating). |
| **`sec-api-python`** ([source](https://github.com/janlukasschroeder/sec-api-python)) | Commercial API, requires a paid key. Conflicts with this toolkit's key-free posture. |
| **Arelle** (raised by JA sources) | A reference XBRL processor — lower level than what is needed. We are not short of parsing capability; `edgartools` already sits on top of this layer. |
| **`edgar_analytics`** ([source](https://github.com/zoharbabin/edgar_analytics)) | Built on edgartools, computes ratios. A consumer, not a solution to period semantics. |
| **Feed the store instead (the old rung B)** | Deferred, not rejected. The user's goal does not require accumulation, and the store path carries an unresolved trust-vocabulary decision plus a layering inversion (audit §5). Revisit only if on-demand proves insufficient. |

Sources: [XBRL US DQC_0213](https://xbrl.us/data-rule/dqc_0213/) and
[DQC_0099](https://xbrl.us/data-rule/dqc_0099pr/) (EN) establish that filers
routinely omit calculation children, which is why a structure-only rule is
unsafe; [シラベルノート](https://srbrnote.work/archives/2143) (JA) states the
same practical conclusion from the other side — assembling clean time series is
the hard part, not fetching.

## What Becomes Obsolete

- ~~**The planned YTD-differencing and Q4-derivation work** — superseded by the
  dependency. Remove from planning; do not build.~~ **REVERSED 2026-07-30. BUILD
  IT.** This directive rested on the dependency producing usable discrete
  quarters. It produces correct NUMBERS under keys that misdescribe them (see
  §Smallest End State step 3 and the plan's §RESOLVED FINDING), so the work is
  back in scope: four subtractions across two statements, owned by plan Task E.
  Anyone reading this bullet as still operative would delete Task E's cash-flow
  work as scope creep — which is why it is reversed here rather than only in the
  plan.
- **Rung A (convert 13 spine fields to structure-driven selection)** — already
  withdrawn on measurement (audit §8); this brief does not revive it.
- **`RECONSTRUCT_ANNUAL_FILINGS = 8` as a fixed constant** and the inline
  `["10-K"]` — both become parameters of the new verb. If the annual-only verb
  survives alongside it, say why in the plan rather than leaving two paths.

## Open Questions

1. ~~**Output shape.** Does the series render through the existing
   `derive-as-filed` view (14 canonical fields × periods), or does a
   quarterly series want its own projection?~~ **RESOLVED 2026-07-28 by the
   user: its own projection.** The existing view has no period-type concept,
   which step 5 requires; and the quarterly period semantics (discrete / YTD /
   derived) do not exist in an annual view, so folding them in would show
   annual readers markings that mean nothing to them. `derive-as-filed` is left
   byte-unchanged.
2. **Span parameterisation.** Years back, or explicit start/end? A span in years
   is simpler; explicit dates compose better with a later store lane.
3. **Cache granularity.** Cache the raw filing document, or the parsed XBRL
   object? The document is unambiguously immutable; the parsed object is faster
   to reuse but is invalidated by our own parser changing — the same argument
   `pack_us.py:1465-1472` makes against persisting reconstructions.
4. **Fiscal-year-end handling.** MSFT (June) and WMT (January) were probed and
   worked, but no filer with a 52/53-week calendar was tested in this arc.

## Next arc — operational KPIs (user-confirmed 2026-07-29)

Operational / management KPIs remain a stated goal; the user deferred them to the
arc AFTER this one rather than dropping them. Recorded here so the deferral is a
decision, not an omission.

**The seam to know about before that arc starts.** The existing operational-KPI
machinery (`kpi_prose_candidates`, `kpi_8k_candidates`) writes into `kpi_store`;
this arc's quarterly series deliberately does NOT touch the store. So combining
the two for analysis has no single place to read from, and that join is unbuilt.
No design work for it belongs in THIS arc — that would be paying for a speculative
requirement — but the next arc should start from the knowledge that the seam
exists rather than discovering it.

That arc also remains blocked on its own prerequisite (the surface-version marker
and the anchor gate on the commit path), which is unchanged by this work. When the
backlog branch carrying the ratified order is resolved, this note belongs there as
a proper entry.
