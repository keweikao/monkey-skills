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

import importlib
import sys
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent

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


# ==========================================================================
# The subtractions the filings do not state (plan Task E)
# ==========================================================================
#
# WHY THIS EXISTS AT ALL: a US filer's quarterly reporting does not hand you
# four discrete quarters. Q4 appears in NO filing -- there is no fourth-quarter
# 10-Q, only the 10-K -- and a 10-Q's cash-flow statement carries cumulative
# figures where its income statement carries a discrete column. So some
# quarters must be differenced out of the cumulative columns, and doing it here
# rather than accepting the dependency's own version is what keeps a period
# key's span describing the span of its value (see this module's docstring).
#
# THE THREE SUBTRACTIONS ARE NAMED, NOT GENERIC. Each one pairs two cumulative
# columns of the SAME fiscal year, identified by role:
#
#     Q2 = YTD6 - Q1        Q3 = YTD9 - YTD6        Q4 = FY - YTD9
#
# A generic "difference consecutive cumulative columns" rule would look
# equivalent and is not: with YTD6 absent it would emit YTD9 - Q1, a true
# subtraction spanning TWO quarters, honestly keyed and therefore invisible to
# a reader scanning for quarters. Requiring a role by name means a missing
# input suppresses exactly the quarters that needed it -- losing YTD6 costs Q2
# and Q3 and leaves Q4, whose own inputs are untouched.
#
# The dependency states these same three formulas in its own docstring for
# `_unaccumulate_cashflow_ytd` at `edgar/xbrl/stitching/core.py:716-718`
# (opened and read 2026-07-30, edgartools==5.42.0). Its NUMBERS were never in
# question -- only the keys it filed them under.

# Role → the span window that identifies it, READ from Task C's committed
# classifier through its public `span_windows()` accessor rather than restated
# here, so the two cannot drift and so a widening for a 52/53-week calendar
# (plan Task G) reaches this subtraction instead of needing a second edit.
#
# WHAT THAT PROPAGATION DOES AND DOES NOT BUY, stated precisely because an
# earlier version of this comment promised safety this module did not enforce.
# It removes the second EDIT; it does not remove the second REVIEW. The role
# resolution below is unambiguous only while the four windows stay DISJOINT and
# in role order, and a widening can break that. Both failure modes were
# measured on this fixture 2026-07-30, widening the nine-month window to
# `(260, 380)` so it also covers a 364-day fiscal year:
#
#   - windows overlap, both columns present -> the 273-day and 364-day columns
#     both match the nine-month role, so the role is refused as ambiguous and
#     NOTHING is derived for that year. Silent: no filer is entitled to a
#     derived quarter, so an empty answer looks like an ordinary one.
#   - windows overlap, the 273-day column absent -> the 364-day column is the
#     ONLY match for both the nine-month and the annual role, so the Q4
#     subtraction takes that one column as both minuend and subtrahend and
#     emits `duration_2025-07-01_2025-06-30` -- a period starting after it ends,
#     every value 0.
#
# `_reject_overlapping_role_windows` is what makes the first case loud, and
# `_reject_degenerate_pair` is what makes the second impossible. Task G carries
# both as findings.
#
# Task C's module is pure stdlib; the sibling import follows this skill's
# established lazy pattern (`kpi_8k_candidates.py:359`,
# `kpi_prose_candidates.py:745`) -- both of which, like this one, insert this
# script's own directory on `sys.path` first and then call a sibling's PUBLIC
# function. Round 1 read Task C's underscore-private constants instead, which
# those two precedents did not cover.
#
# Both precedents write a plain `import kpi_store` statement, which needs the
# module name as a literal. This module keeps the name in a constant -- the test
# fixture that patches Task C's accessor resolves the very module object this one
# imports through `sys.modules[_PERIODS_MODULE]` -- so the import goes through
# `importlib.import_module`, the idiomatic form for a name held in a variable.
# Not `__import__`, which is the low-level hook `import_module` is documented to
# be preferred over; for a non-dotted name the two return the same object.
_PERIODS_MODULE = "kpi_us_quarterly_periods"

# The four cumulative roles, in the order their windows must ascend.
_ROLES_IN_SPAN_ORDER = ("q1", "ytd6", "ytd9", "fy")


def _role_windows() -> dict[str, tuple[int, int]]:
    """`{role: (low, high)}` for the four cumulative roles, taken from Task C's
    public `span_windows()`.

    The two year-to-date windows are ordered by their own low bound rather than
    by position in Task C's tuple, so a reordering there cannot silently swap
    which one this module treats as the six-month column.

    Raises `ValueError` when Task C reports anything other than exactly two
    year-to-date windows, or windows that are not disjoint and in role order --
    see `_reject_overlapping_role_windows` for why that is a refusal rather than
    a best effort.
    """
    if str(_SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPT_DIR))
    periods = importlib.import_module(_PERIODS_MODULE)
    windows = periods.span_windows()

    ytd = sorted(windows["ytd"], key=lambda span: span[0])
    if len(ytd) != 2:
        raise ValueError(
            f"{_PERIODS_MODULE}.span_windows() reports {len(ytd)} year-to-date "
            f"window(s), {ytd}, but this module's three subtractions name "
            "exactly two of them -- a six-month and a nine-month cumulative "
            "column. Widening the existing two windows is safe; adding or "
            "removing one is a question about which quarter the new window "
            "bounds, and it is refused here rather than answered by ignoring "
            "the extra window and silently dropping a quarter."
        )

    roles = {
        "q1": windows["discrete_quarter"][0],
        "ytd6": ytd[0],
        "ytd9": ytd[1],
        "fy": windows["annual"][0],
    }
    _reject_overlapping_role_windows(roles)
    return roles


def _reject_overlapping_role_windows(roles: dict[str, tuple[int, int]]) -> None:
    """Refuse role windows that are not DISJOINT and ascending in role order.

    This is the precondition the whole role resolution rests on, checked rather
    than assumed. Each role is resolved by finding the columns whose day span
    falls inside its window, so two overlapping windows let ONE column match two
    roles -- after which the subtraction either refuses that fiscal year as
    ambiguous (deriving nothing, silently) or, when the overlapping window's
    other column is absent, differences that column from itself.

    It refuses LOUDLY, which is a deliberate asymmetry with Task C's own
    contract that a malformed period key must never raise. A malformed key is
    one filer's bad data among many and skipping it costs only that key. Windows
    that overlap are THIS REPO'S OWN CONSTANTS being wrong: not per-filer, not
    recoverable by skipping anything, and identical for every caller and every
    year. A change that turns every derived quarter into either silence or
    nonsense must stop the run it is introduced on.
    """
    ordered = [(role, roles[role]) for role in _ROLES_IN_SPAN_ORDER]
    for (lower_role, lower), (upper_role, upper) in zip(ordered, ordered[1:]):
        if lower[1] >= upper[0]:
            raise ValueError(
                f"{_PERIODS_MODULE}.span_windows() gives the {lower_role} role "
                f"the day-span window {lower} and the {upper_role} role "
                f"{upper}: {lower_role} does not end before {upper_role} "
                "begins. The four role windows must be DISJOINT and ascending "
                "in role order, because a column whose span matches two roles "
                "makes this subtraction either refuse a whole fiscal year or "
                "difference one column from itself. Widen the windows so they "
                "stay separated, or decide explicitly which role a shared span "
                "belongs to."
            )


# (target quarter, minuend role, subtrahend role). The derived quarter starts
# the day after the subtrahend ends and ends when the minuend ends.
_SUBTRACTIONS = (
    ("q2", "ytd6", "q1"),
    ("q3", "ytd9", "ytd6"),
    ("q4", "fy", "ytd9"),
)

_DURATION_PREFIX = "duration_"


def _duration_bounds(period_key: str) -> tuple[date, date] | None:
    """`(start, end)` for a `duration_<start>_<end>` key, else `None` -- which
    covers an instant key and a malformed one alike, because neither carries a
    span this module can difference."""
    if not period_key.startswith(_DURATION_PREFIX):
        return None
    parts = period_key[len(_DURATION_PREFIX):].split("_")
    if len(parts) != 2:
        return None
    try:
        return date.fromisoformat(parts[0]), date.fromisoformat(parts[1])
    except ValueError:
        return None


def _roles_for_year(
    keys_by_span: dict[int, list[str]], windows: dict[str, tuple[int, int]]
) -> dict[str, str]:
    """`{role: period_key}` for one fiscal-year start group.

    A role with TWO candidate columns is left UNRESOLVED rather than resolved
    arbitrarily: picking one would make the subtraction depend on which, and
    the resulting figure would be indistinguishable from a correct one.
    """
    resolved: dict[str, str] = {}
    for role, (low, high) in windows.items():
        candidates = [
            key
            for span, keys in keys_by_span.items()
            if low <= span <= high
            for key in keys
        ]
        if len(candidates) == 1:
            resolved[role] = candidates[0]
    return resolved


def _reject_degenerate_pair(
    target: str, minuend: str, subtrahend: str, start: date, end: date
) -> None:
    """Refuse a subtraction whose two columns cannot bound a quarter between
    them: the same column on both sides, or a period starting after it ends.

    Both are arithmetically impossible for real inputs while the role windows
    are disjoint and ascending -- with the same fiscal-year start date, a role
    from a higher window always ends later than one from a lower window. So this
    is a BACKSTOP for the precondition `_reject_overlapping_role_windows`
    enforces, kept because "unreachable" is a property of the current constants
    and plan Task G is scheduled to change them. It was measured reachable the
    moment those windows overlap: the Q4 subtraction emitted
    `duration_2025-07-01_2025-06-30`, every value 0, minuend equal to
    subtrahend.

    It does NOT catch a subtraction that pairs the wrong two REAL columns -- one
    that produces a 180-day "quarter" from FY minus the six-month column is
    arithmetically fine and this guard passes it. That case is the two-candidate
    refusal's job in `_roles_for_year`, and the two are tested separately.
    """
    if minuend == subtrahend:
        raise ValueError(
            f"deriving {target} would difference the column {minuend!r} from "
            "itself, which can only mean two roles resolved to one column. "
            "Every value would be 0 and the period key would start after it "
            f"ends ({start.isoformat()} to {end.isoformat()})."
        )
    if start > end:
        raise ValueError(
            f"deriving {target} from {minuend!r} minus {subtrahend!r} gives the "
            f"period {start.isoformat()} to {end.isoformat()}, which starts "
            "after it ends -- the subtrahend does not end before the minuend, so "
            "these two columns cannot bound a quarter between them."
        )


def _difference_rows(
    rows: list[Any], minuend: str, subtrahend: str
) -> dict[str, Any]:
    """`{concept: minuend_value - subtrahend_value}` over every row that carries
    BOTH columns, as `Decimal`.

    A row missing either side is omitted, never zero-filled: treating the absent
    side as zero would emit the whole cumulative figure as if it were one
    quarter -- the largest error this module could make and the hardest to see,
    since the number is real and the key is honest.

    A cell that is present but is not a FINITE number raises out of the whole
    call rather than being skipped -- see `_cell_decimal`.
    """
    values: dict[str, Any] = {}
    for row in rows:
        concept = row.get("concept")
        if not concept:
            continue
        row_values = row.get("values") or {}
        if minuend not in row_values or subtrahend not in row_values:
            continue
        values[concept] = (
            _cell_decimal(concept, minuend, row_values[minuend])
            - _cell_decimal(concept, subtrahend, row_values[subtrahend])
        )
    return values


def _cell_decimal(concept: str, period_key: str, raw: Any) -> Decimal:
    """One statement cell as an exact `Decimal`, or `ValueError` naming the line
    and the column.

    Refusing is the deliberate asymmetry with Task C's contract that a malformed
    period KEY must never raise. An ABSENT cell is ordinary -- filers leave a
    line out of a column all the time -- and `_difference_rows` answers it by
    deriving no quarter for that line. A cell that is PRESENT and uninterpretable
    has no such answer: skipping it would drop a line from a column that
    otherwise looks complete, with nothing to tell a reader the line went
    missing.

    NON-FINITE IS CHECKED, NOT JUST UNPARSEABLE, and that is the case worth
    knowing about: `Decimal(str(float("nan")))` SUCCEEDS and yields
    `Decimal("NaN")`, which propagates through the subtraction into an output
    figure that compares unequal to everything including itself. A parse-only
    check would let it through silently -- the same shape as the binary-float
    defect this module family already shipped once
    (docs/loom/memory/construction-guaranteed-invariant-proves-nothing.md).

    A cell holding a numeric STRING is accepted: `Decimal("30")` is exactly 30,
    so there is nothing to refuse.
    """
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        raise ValueError(
            f"{concept} holds {raw!r} at period {period_key}, which is not a "
            "number this subtraction can read. A cell that is absent is skipped "
            "for that line; a cell that is present and uninterpretable is "
            "refused, because skipping it would drop the line from a column that "
            "otherwise looks complete."
        ) from None
    if not value.is_finite():
        raise ValueError(
            f"{concept} holds {raw!r} at period {period_key}, which reads as "
            f"{value} -- not a finite figure. Decimal accepts NaN and infinity "
            "without complaint, and either one would propagate through the "
            "subtraction into a derived value that is silently meaningless."
        )
    return value


def _periods_by_year_and_span(periods: list[Any]) -> dict[date, dict[int, list[str]]]:
    """`{fiscal_year_start: {day_span: [period_key, ...]}}` over the duration
    keys only -- instant keys and malformed ones carry no span to difference."""
    by_year: dict[date, dict[int, list[str]]] = {}
    for entry in periods:
        bounds = _duration_bounds(entry[0])
        if bounds is None:
            continue
        start, end = bounds
        by_year.setdefault(start, {}).setdefault((end - start).days, []).append(entry[0])
    return by_year


def _derive_one_quarter(
    target: str,
    minuend: str,
    subtrahend: str,
    rows: list[Any],
    filed_keys: set[str],
) -> dict[str, Any] | None:
    """One derived quarter from one already-resolved pair of columns, or `None`
    when there is nothing to emit.

    `None` covers the two cases that are not errors: the filer already states a
    column for this period, or no line carries both input columns. Both mean
    "emit nothing", which is different from the degenerate pairs
    `_reject_degenerate_pair` raises on.
    """
    quarter_start = _duration_bounds(subtrahend)[1] + timedelta(days=1)
    quarter_end = _duration_bounds(minuend)[1]
    _reject_degenerate_pair(target, minuend, subtrahend, quarter_start, quarter_end)

    key = f"{_DURATION_PREFIX}{quarter_start.isoformat()}_{quarter_end.isoformat()}"
    # A filed column is a primary source; a derived one is a subtraction. Never
    # write over what the filer stated.
    if key in filed_keys:
        return None

    values = _difference_rows(rows, minuend, subtrahend)
    if not values:
        # Both roles resolved but no LINE carries both columns, so there is
        # nothing to report. An entry with no values is not a derivation -- it
        # would read as a quarter that exists and happens to be blank.
        return None

    return {
        "key": key,
        "start": quarter_start.isoformat(),
        "end": quarter_end.isoformat(),
        "derived": True,
        "minuend": minuend,
        "subtrahend": subtrahend,
        "values": values,
    }


def _derive_one_statement(
    statement: Any, windows: dict[str, tuple[int, int]]
) -> list[dict[str, Any]]:
    """Every derivable discrete quarter for one statement, oldest key first.

    The returned order is fixed by the single sort at the end. An earlier
    version also sorted the fiscal-year groups on the way in; that was a second
    mechanism for one contract, and since derived keys are unique per statement
    the final sort fully determines the order on its own.
    """
    periods = (statement or {}).get("periods") or []
    rows = (statement or {}).get("statement_data") or []
    filed_keys = {entry[0] for entry in periods}

    derived: list[dict[str, Any]] = []
    for keys_by_span in _periods_by_year_and_span(periods).values():
        roles = _roles_for_year(keys_by_span, windows)
        for target, minuend_role, subtrahend_role in _SUBTRACTIONS:
            minuend = roles.get(minuend_role)
            subtrahend = roles.get(subtrahend_role)
            if minuend is None or subtrahend is None:
                continue
            entry = _derive_one_quarter(
                target, minuend, subtrahend, rows, filed_keys
            )
            if entry is not None:
                derived.append(entry)
    return sorted(derived, key=lambda entry: entry["key"])


def derive_discrete_quarters(statements: Any) -> dict[str, list[dict[str, Any]]]:
    """The discrete quarters the filings do not state, per statement kind.

    Takes either `stitch_quarterly_statements`' return value or a bare
    `{kind: statement}` mapping -- only the three statement kinds are read, so
    the envelope's own `n_filings_used` is ignored rather than tripping over.

    Returns `{kind: [entry, ...]}` for ALL THREE kinds, each list oldest key
    first. The balance sheet always comes back EMPTY: it is instant-based, so
    it carries no duration column to difference, and answering it with `[]`
    says that rather than leaving the caller to wonder.

    Each entry is `{key, start, end, derived, minuend, subtrahend, values}`.
    `derived` is a SEPARATE BOOLEAN, never a period-kind value -- a derived Q4
    is both a discrete quarter AND derived, and collapsing those two axes would
    make "every discrete quarter regardless of provenance" unanswerable.
    `minuend` and `subtrahend` name the two input period keys, so a reader can
    re-check any figure without re-deriving the pairing.

    Values are `Decimal`, never binary float: this arithmetic subtracts money
    across periods, and float has already manufactured a false restatement flag
    in this module family (`docs/loom/memory/`
    `construction-guaranteed-invariant-proves-nothing.md`). A real case from
    this arc's own fixture -- diluted EPS `13.64 - 9.99` -- is `3.65` exactly in
    `Decimal` and `3.6500000000000004` in float.

    Does not mutate `statements`; every returned structure is freshly built.

    RAISES `ValueError` in three cases, all of which mean "this cannot be
    answered", never "this filer had no derivable quarter":

      - Task C's day-span windows are not a usable set -- not exactly two
        year-to-date windows, or windows that are not disjoint and ascending
        (`_role_windows`, `_reject_overlapping_role_windows`);
      - a subtraction resolved to one column on both sides, or to a period
        starting after it ends (`_reject_degenerate_pair`);
      - a statement cell is present but is not a finite number
        (`_cell_decimal`).

    An ordinary "nothing to derive" is an EMPTY LIST, not an exception: a
    missing input period, a period the filer already states, and a line that
    carries only one of the two columns all produce no entry and no error.
    """
    windows = _role_windows()
    return {
        kind: _derive_one_statement((statements or {}).get(kind), windows)
        for kind in _STATEMENT_TYPE_OF
    }
