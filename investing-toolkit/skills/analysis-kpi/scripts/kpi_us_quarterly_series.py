#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["edgartools==5.42.0"]
# ///
"""kpi_us_quarterly_series.py — stitch a filer's own ALREADY-ACQUIRED filing
list (Task A's `sec_edgar_client.assemble_quarterly_filing_span` produces the
accession list; acquiring each one is Task J's concern, see below) into the
three statements as `edgartools` own multi-filing stitcher returns them (plan
Task D, docs/loom/plans/2026-07-28-us-quarterly-statement-series.md).

PASS-THROUGH ONLY. This module derives nothing about the numbers -- every
subtraction that turns cumulative columns into discrete quarters lives in
plan Task E. This module's entire job is two library calls --
`XBRLS.from_filings` and `XBRLS.get_statement`, once per statement kind --
with one parameter derived rather than defaulted or guessed.

WHY `discrete_quarters=False` (plan §RESOLVED FINDING 2026-07-30). Asked
for `True`, the dependency computes discrete cash-flow quarters correctly
but files each one under the CUMULATIVE period key sharing its end date, so
a key's day span stops describing the span of its value -- a 364-day key
holding a single quarter, and an 89-day and a 273-day key holding one
number between them. Requesting `False` takes the cash-flow statement as
filed instead, which restores the invariant the rest of this arc reads the
keys under: A PERIOD KEY'S SPAN ALWAYS DESCRIBES ITS VALUE'S SPAN, in all
three statements. The subtraction is not lost, it MOVES -- to Task E, which
cross-checks its arithmetic against the dependency's own
`_unaccumulate_cashflow_ytd` (`edgar/xbrl/stitching/core.py:705`), whose
NUMBERS were never in question; only the keys it filed them under were.

The flag is gated to `CashFlowStatement` inside the dependency, so it is a
no-op for the income statement and balance sheet. That was measured on this
arc's own fixture filer rather than taken on trust: with both flag values
requested from one `XBRLS` instance over the same 11 filings, the income
statement's `statement_data` came back byte-identical, and all three kinds
returned identical period IDs. What `True` additionally changed was cash-flow
period LABELS -- it relabelled the 364-day column `'Q4 FY Jun 30, 2025'`,
creating six label collisions where a cumulative and a discrete column shared
one label; under `False` those collisions drop to zero. Labels are not read
here, but that count is the clearest single symptom of the defect.

THE HAZARD THIS MODULE EXISTS TO CLOSE: `XBRLS.get_statement`'s own
`max_periods` DEFAULTS TO 8. A ~77-filing request left at that default
silently returns 8 periods -- a truncated answer and a complete one have
the SAME shape, so every test still passes. `max_periods` is therefore
ALWAYS derived from `len(filings)` here, never left at the library
default and never a hand-picked constant -- the identical defect class
`sec_edgar_client.assemble_quarterly_filing_span` (signature
`(cik, years=None)` -- it has no `limit` of its own) documents in its own
docstring for the `limit` parameter it must supply to `list_filings`, which
is where `limit` is actually declared, and the same remedy: derive the bound
from the caller's own real data rather than guess a number that looks
sufficient today.

WHY `* 2`, STATED RATHER THAN GUESSED: `include_quarterly=True`'s own
docstring (`XBRLS.get_statement`) states each filing can contribute UP TO
TWO distinct stitched periods -- a 10-Q contributes both its 90-day
discrete-quarter column and its YTD column; a 10-K contributes both its
annual column and its embedded Q4 column. `_select_periods`
(`edgar/xbrl/stitching/core.py:300`/`371`/`374`) truncates the FULL
distinct-period list to `max_periods` with a plain slice, so
`len(filings) * 2` is a bound DERIVED from that stated two-columns-
per-filing ceiling -- not a comfortable margin picked by feel. It can only
ever be equal to or larger than the true distinct-period count (some
periods collapse across filings, e.g. a shared quarter-end reported by two
consecutive 10-Qs), never smaller -- the same "provably never truncates"
shape Task A's own `limit` derivation uses.

NOT CALLED HERE: `statements_for` (`kpi_us_statement_shape.py`) -- that is
the single-filing reconstruction path and produces a DIFFERENT shape (this
repo's own `Statements`/`Line` dataclasses); this module reuses the
dependency's own multi-filing stitcher instead, per the plan's Decision
Log and Reuse-adequacy note for Task D.

ACQUISITION IS NOT THIS MODULE'S JOB. This module takes an already-acquired
`filings` list -- it never calls `sec_edgar_client._acquire_raw_filing` and
never imports `sec_edgar_client` at all. The repo's recorded convention is
that `analysis-*` skills reach `data-markets` I/O by SUBPROCESS, never by
cross-skill import. THREE precedents cross it that way, each naming its
target script as a path constant and then shelling out to it:
`kpi_8k_candidates.py:53,124` (path constant, then `subprocess.run` ->
`exhibit_tables.py`), `kpi_prose_candidates.py:62,149` (likewise ->
`exhibit_prose.py`), and `analysis-comps/scripts/etf_aggregator.py`, which
has TWO call sites reaching TWO DIFFERENT data-markets scripts: `:68` is the
`pack.py` path constant and `:111` shells out to it, while `:69` is the
`yfinance_client.py` path constant and `:94` shells out to THAT. An earlier
version of this docstring credited both call sites to `pack.py`; the
precedent stands either way -- both callees are data-markets scripts -- but
the attribution was wrong. The one import exception,
`kpi_xbrl.py:1361`'s function-level `import sec_edgar_client`, reaches a
PURE-compute helper (`_dimension_quarterly_absence`, called at
`kpi_xbrl.py:1365`), never network I/O.

Acquiring each accession -- and deciding what a partially-failed
acquisition does -- therefore belongs to the CALLER, on the data-markets
side of that subprocess boundary; see plan Task J for the owning task. The
boundary is the durable fact here, and the reason is the paragraph above:
an `analysis-*` module that acquired its own filings would have to import
`data-markets`, which this repo does not do. Where the responsibility is
docketed is the plan Decision Log's business, not this module's, and is
deliberately not restated here.

THE D<->J SEAM IS NOT WITNESSED OFFLINE -- state this plainly rather than
let a reader assume otherwise. Nothing in this module's own suite proves
that the objects the acquire loop yields are accepted by this function
unmodified: that suite feeds duck-typed stand-ins, and no committed
raw-filing fixture exists anywhere in this arc to feed real ones. Per plan
Task J, Acceptance, that loop's test pins its output contract from its own
side only; per plan Task H, Acceptance, the end-to-end seam is exercised
solely by a ONE-OFF LIVE RUN. So the two halves are joined by a live run
and by these two docstrings agreeing -- not by any offline test.

`edgar` IS IMPORTED LOCALLY, inside `_build_xbrls` below, never at module
level -- mirroring `sec_edgar_client.py`'s own convention (verified
2026-07-30: all four of its `import edgar` sites are function-local, none at
module scope; cited by count rather than by line because that file is under
active edit in this arc). This repo's
default offline test command does not install edgartools, so a module-level
import would break test COLLECTION for every test in this file, not just
the ones exercising a live filing. `_build_xbrls` is the seam a test
monkeypatches to run this module's own logic (the `max_periods` derivation)
against a duck-typed stand-in, without installing the dependency.
"""
from __future__ import annotations

from typing import Any

_STATEMENT_TYPE_OF = {
    "income": "IncomeStatement",
    "balance_sheet": "BalanceSheet",
    "cash_flow": "CashFlowStatement",
}

# See module docstring "WHY * 2" -- derived from `include_quarterly=True`'s
# documented up-to-two-periods-per-filing ceiling, not a guessed margin.
_PERIODS_PER_FILING_CEILING = 2


def _build_xbrls(filings: list[Any]):
    """`edgar.xbrl.stitching.xbrls.XBRLS.from_filings(filings)` -- the LOCAL
    import boundary a test monkeypatches (see module docstring for why the
    import lives here rather than at module scope)."""
    from edgar.xbrl.stitching.xbrls import XBRLS

    return XBRLS.from_filings(filings)


def stitch_quarterly_statements(filings: list[Any]) -> dict[str, Any]:
    """The three statements for `filings` -- an ALREADY-ACQUIRED, ordered
    (oldest first) list of `edgar.Filing` objects -- as `edgartools`' own
    multi-filing stitcher returns them: `discrete_quarters=False,
    include_quarterly=True` on every call, and `max_periods` DERIVED from
    `len(filings)`, never the library's default of 8 and never a
    hand-picked constant (see module docstring).

    `discrete_quarters=False` is passed EXPLICITLY even though it matches
    the library's current default, because it is a decision this arc made
    against a measurement, not an inherited default -- so a future upstream
    flip of that default cannot silently change what this module means. Its
    consequence: every cash-flow duration column comes back as filed, i.e.
    cumulative, and a period key's day span always describes the span of the
    value under it. Turning those cumulative columns into discrete quarters
    is the next task's subtraction, not this function's.

    Acquiring each accession is NOT this function's job -- see the module
    docstring's "ACQUISITION IS NOT THIS MODULE'S JOB" section; the caller
    acquires, and decides what to do about a partial acquisition, before
    calling this.

    Returns `{"income": {...}, "balance_sheet": {...}, "cash_flow": {...},
    "n_filings_used": N}`; each statement value is `get_statement`'s own
    `{"periods": [...], "statement_data": [...]}` shape, UNTOUCHED --
    pass-through only, no derivation (plan Task D).

    Raises `ValueError` on an empty `filings` list.
    """
    if not filings:
        raise ValueError("stitch_quarterly_statements: filings is empty")

    xbrls = _build_xbrls(filings)
    max_periods = len(filings) * _PERIODS_PER_FILING_CEILING

    result: dict[str, Any] = {"n_filings_used": len(filings)}
    for kind, statement_type in _STATEMENT_TYPE_OF.items():
        result[kind] = xbrls.get_statement(
            statement_type,
            max_periods=max_periods,
            # Passed explicitly although it matches the library's current
            # default -- see this function's docstring for why.
            discrete_quarters=False,
            include_quarterly=True,
        )
    return result
