"""Tests for analysis-kpi/scripts/kpi_us_quarterly_series.py — stitch a
filer's own ALREADY-ACQUIRED filing list into the three statements via
`edgartools`' own multi-filing stitcher (plan Task D), subtract the
discrete quarters the filings never state (plan Task E), and project the
result with every period labelled (plan Task F), all in
docs/loom/plans/2026-07-28-us-quarterly-statement-series.md.

THREE FUNCTIONS, ONE PIPELINE: stitch → derive → project. The third is the
answer a consumer reads, and its own section at the bottom of this file
states what it pins; the two below are its inputs.

TWO FUNCTIONS, TWO HALVES OF ONE PIPELINE. `stitch_quarterly_statements`
takes the cumulative columns as filed; `derive_discrete_quarters` differences
them. The second exists because a US filer's filings do not contain four
discrete quarters: Q4 appears in no filing at all (there is no Q4 10-Q, only
the 10-K), and a 10-Q's cash-flow statement may carry only cumulative
figures. See "WHAT TASK E'S TESTS PIN" below.

`stitch_quarterly_statements(filings)` is pass-through only (no
derivation): it takes an already-acquired filing list, builds
`XBRLS.from_filings(...)`, and calls `.get_statement(...)` once per
statement kind with `discrete_quarters=False, include_quarterly=True` and,
THE POINT OF THIS TASK, `max_periods` DERIVED from the filing count rather
than left at the library's own default of 8.

WHY `discrete_quarters=False` MATTERS TO THIS SUITE. Asked for `True`, the
dependency replaces each cumulative cash-flow period's value IN PLACE with
the discrete quarter ENDING on that period's end date (its own
`_unaccumulate_cashflow_ytd` docstring says so). The values are right, the
keys they land under are not -- a 273-day key ends up holding an 89-day
number. `False` takes the cash-flow statement as filed, restoring the
invariant this arc reads keys under: a period key's day span always
describes the span of its value. See plan §RESOLVED FINDING 2026-07-30.

ACQUISITION IS NOT UNDER TEST HERE, AND ITS SEAM IS NOT WITNESSED OFFLINE.
Turning accession rows into filing objects belongs to the caller on the
data-markets side of the subprocess boundary (plan Task J owns it); the
module under test never calls `sec_edgar_client._acquire_raw_filing` and
never imports it, because `analysis-*` reaches `data-markets` I/O by
subprocess, never by cross-skill import -- see the module's own docstring
for the precedents. Nothing in THIS file, and nothing in the acquire loop's
own suite, proves that the objects that loop yields are accepted by
`stitch_quarterly_statements` unmodified: this suite feeds duck-typed
stand-ins, and no committed raw-filing fixture exists in this arc to feed
real ones. Per plan Task H, Acceptance, that end-to-end seam is exercised
only by a ONE-OFF LIVE RUN. Stated here so no reader mistakes this suite's
green for coverage of it.

THIS SUITE RUNS OFFLINE against `tests/data/fixtures/
us_quarterly_stitched_msft.json` -- a live capture of MSFT's real,
UNTRUNCATED stitched statements (see the capture script
`tests/data/fixtures/capture_us_quarterly_stitched.py` for full provenance,
including why its filing count moves between captures). The test replaces
the module's own local-import seam (`_build_xbrls` -- `edgar` is not
installed under this repo's default offline test command, so it is never
imported at module scope) with a duck-typed `_FakeXBRLS` that replicates the
ONE behavior this task's correctness hinges on: `get_statement` slices its
full period list to `max_periods`. This makes the offline test genuinely
sensitive to what `max_periods` THE MODULE derives and passes -- leaving it
at the library's default of 8 truncates the fake's answer exactly as it
would truncate a live one, and the test catches it.

THE LITERAL NUMBERS BELOW ARE MEASURED, from the committed fixture, after
the 2026-07-30 re-capture -- never copied from prose. Where a `True`-mode
value is quoted for contrast it is recorded as a comment, not asserted; it
came from a one-off `discrete_quarters=True` capture over the same filings,
which is not committed because nothing should run against it.

WHAT TASK E'S TESTS PIN, and where each expected number comes from. The
invariant the whole arc rests on is that A PERIOD KEY'S SPAN ALWAYS
DESCRIBES THE SPAN OF ITS VALUE, so a derived quarter is only correct if
BOTH its number and its key are. Every Task E test therefore checks the
key as well as the figure, and one of them checks the key through the
committed span classifier (`kpi_us_quarterly_periods.period_kind`) — because
a derived Q4 mis-keyed onto either of its own inputs would classify as
`annual` or `ytd` and pass every value-only assertion in this file.

Three grades of oracle are used, and they are NOT interchangeable:

  1. CONFIRMED THREE WAYS, its independence RECORDED BUT NOT REPRODUCIBLE:
     derived FY2025 Q4 revenue `76,441,000,000`. The FIGURE is solid — the
     plan, this file's constant, and the fixture's own
     `281,724,000,000 − 205,283,000,000` all agree, and the third of those is
     re-read from the input by the test itself. Its INDEPENDENCE is a weaker
     claim than earlier drafts of this file made: it rests on a session-scoped
     probe of `edgar/ttm/calculator.py:665` (`_derive_q4_from_fy`) that the
     brief itself records as not re-derivable, and NO artifact in this repo
     shows the two implementations agreeing. So this file does not call it a
     verified-independent oracle (plan Task E, Acceptance, "Bound on the word
     independent"). Recorded, never called at test time.
  2. NOT INDEPENDENT, and this file must not pretend otherwise: the FY2025
     operating-cash-flow quarters `34,180 / 22,291 / 37,044 / 42,647`
     (x10^6). The dependency's own `_unaccumulate_cashflow_ytd` applies the
     SAME formula to the SAME stitched inputs, so agreeing with it is a
     differential test of implementation and cannot catch a wrong formula
     or a wrong period pairing. What redeems the pair is the third grade.
  3. READ BACK FROM THE INPUT: the filer's OWN filed discrete cash-flow
     columns. MSFT files three-month cash-flow columns for Q1-Q3, so
     deleting them from an in-test copy and re-deriving them reproduces
     numbers the filer stated independently of any subtraction. That is the
     assertion a wrong formula or a wrong pairing cannot survive, and it is
     the reason grade 2 alone was not left to carry the cash-flow lane.

Grade 3 also removes the "expected value written as a literal" trap: the
expectation is read out of the input the test itself mutated, so no constant
can satisfy it.

No `@req` tags: this dispatch carries no registered loom-spec REQ-ids (the
work is tracked by named plan Tasks D, E and F), so `@req` is omitted per the
implementer contract.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pytest
from conftest import SKILLS

SERIES_SCRIPT = SKILLS / "analysis-kpi" / "scripts" / "kpi_us_quarterly_series.py"
# Task C's committed span classifier, loaded so Task E's tests can check a
# DERIVED key through the same reader every downstream consumer uses.
PERIODS_SCRIPT = SKILLS / "analysis-kpi" / "scripts" / "kpi_us_quarterly_periods.py"
FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "data" / "fixtures" / "us_quarterly_stitched_msft.json"
)

_STATEMENT_TYPE_OF = {
    "IncomeStatement": "income",
    "BalanceSheet": "balance_sheet",
    "CashFlowStatement": "cash_flow",
}

# --- measured from the committed fixture (2026-07-30 re-capture) ----------

# MSFT FY2025 (fiscal year starting 2024-07-01). Under discrete_quarters=
# False these four cash-flow columns are CUMULATIVE, each spanning exactly
# what its key says. Under `True` the same four keys held
# 34,180 / 22,291 / 37,044 / 42,647 (x10^6) -- the four DISCRETE quarters,
# filed under cumulative keys. Those four sum to 136,162, this row's FY
# figure, which is what proves they were the discrete quarters rather than
# anything else; it is also why three of these four cells change value when
# the flag flips, making this the sharpest form of clause 1.
_CFO_CONCEPT = "us-gaap_NetCashProvidedByUsedInOperatingActivities"
_FY2025_CASHFLOW_CUMULATIVE = {
    "duration_2024-07-01_2024-09-30": 34_180_000_000,   # 91d  Q1 (= discrete)
    "duration_2024-07-01_2024-12-31": 56_471_000_000,   # 183d first half
    "duration_2024-07-01_2025-03-31": 93_515_000_000,   # 273d nine months
    "duration_2024-07-01_2025-06-30": 136_162_000_000,  # 364d fiscal year
}

# Clause 1's named pair: two cash-flow duration keys that share an END date
# (2025-03-31) and differ in span. SHARING THE END DATE IS THE LOAD-BEARING
# PART -- the dependency's in-place replacement writes the quarter ending at
# a key's end date into that key, so an end-date-sharing pair is exactly
# where the defect collides two spans onto one number. A pair merely drawn
# from the same fiscal year is not: of the 24 same-fiscal-year
# (quarter x cumulative) pairs on this line, only the 6 sharing an end date
# collide under `True`, so 18 of 24 such picks stay green on the defect.
_CUMULATIVE_273D = "duration_2024-07-01_2025-03-31"
_DISCRETE_89D = "duration_2025-01-01_2025-03-31"
_CASHFLOW_273D_VALUE = 93_515_000_000  # under `True` this key held 37,044,000,000
_CASHFLOW_89D_VALUE = 37_044_000_000   # unchanged by the flag -- already discrete

# Clause 2 (regression guard): the same two keys in the INCOME statement,
# which `include_quarterly=True` supplies honestly in both modes.
_INCOME_CONCEPT = "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"
_INCOME_273D_VALUE = 205_283_000_000
_INCOME_89D_VALUE = 70_066_000_000

# Clause 3 (regression guard): measured period counts. Each is far above the
# library's max_periods=8 default, which is the defect the derivation exists
# to prevent. These move when the fixture is re-captured -- `years=3` is a
# window relative to the capture's run date (capture script docstring); a
# mismatch here means re-capture drift, and the fixture's
# `_capture.filings` shows exactly which filings moved.
_EXPECTED_PERIOD_COUNTS = {"income": 17, "balance_sheet": 11, "cash_flow": 17}

_MAX_PERIODS_LIBRARY_DEFAULT = 8

# --- Task E: the periods the subtraction reads and the ones it writes -----
#
# MSFT's fiscal year starts July 1. The four CUMULATIVE columns of FY2025 are
# `_FY2025_CASHFLOW_CUMULATIVE` above; these are the two the Q4 subtraction
# consumes, and the key it must produce.
_FY2025_FY = "duration_2024-07-01_2025-06-30"          # 364d, FY
_FY2025_YTD9 = "duration_2024-07-01_2025-03-31"        # 273d, nine months
# 2025-04-01 is the day after YTD9 ends; 2025-06-30 is the day FY ends. This
# key is in NEITHER input -- reusing either input's key is the defect the
# whole arc exists to remove, so the key is asserted, not assumed.
_FY2025_DERIVED_Q4 = "duration_2025-04-01_2025-06-30"  # 90d, fiscal Q4

# The previous fiscal year, present in the same fixture with a complete
# cumulative set -- so "derives Q4" is pinned on TWO years, not one, and a
# hard-coded single answer cannot satisfy it.
_FY2024_DERIVED_Q4 = "duration_2024-04-01_2024-06-30"  # 90d, fiscal Q4

# The fiscal year the fixture DELIBERATELY leaves incomplete: it carries
# Q1 / YTD6 / YTD9 but NO FY column, because `years=3` is a window relative
# to the capture's run date and that year had not closed. It is the offline
# refusal case for Q4 (plan Task E, GREEN, as reworded 2026-07-30).
_OPEN_YEAR_START = "2025-07-01"
_OPEN_YEAR_YTD9 = "duration_2025-07-01_2026-03-31"     # 273d, its last column
# The key a Q4 for that year would have to carry. Nothing may emit it.
_OPEN_YEAR_WOULD_BE_Q4 = "duration_2026-04-01_2026-06-30"

# GRADE 1 ORACLE. The FIGURE is confirmed three ways; its INDEPENDENCE is
# recorded but not reproducible in this repo -- see the module docstring's
# grade 1 note. The name says `RECORDED`, not `INDEPENDENT`, so a reader
# reaching this constant first does not inherit the stronger claim.
_RECORDED_FY2025_Q4_REVENUE = 76_441_000_000

# GRADE 2 ORACLE (NOT independent -- same formula, same inputs as the
# dependency's `_unaccumulate_cashflow_ytd`). FY2025 operating cash flow, the
# four DISCRETE quarters. Q1-Q3 are filed by MSFT itself; only Q4 is derived.
_FY2025_CASHFLOW_DISCRETE = {
    "duration_2024-07-01_2024-09-30": 34_180_000_000,  # Q1: filed (= its own YTD)
    "duration_2024-10-01_2024-12-31": 22_291_000_000,  # Q2: filed by MSFT
    "duration_2025-01-01_2025-03-31": 37_044_000_000,  # Q3: filed by MSFT
    _FY2025_DERIVED_Q4: 42_647_000_000,                # Q4: DERIVED, in no filing
}

# The line whose subtraction is float-HOSTILE on this very fixture, so the
# `Decimal` requirement is pinned by real data rather than a constructed
# value: 13.64 - 9.99 is 3.6500000000000004 in binary float and exactly 3.65
# in decimal. Every other income line here is whole dollars, where float
# happens to be exact and would prove nothing.
_EPS_DILUTED_CONCEPT = "us-gaap_EarningsPerShareDiluted"
_EPS_DILUTED_FY2025_Q4 = Decimal("3.65")

# A line with no fractional cent anywhere, used where the point is the figure
# rather than its representation.
_CFO_FY2025_Q4 = 42_647_000_000


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _span_days(period_id: str) -> int:
    start_s, end_s = period_id[len("duration_"):].split("_")
    return (date.fromisoformat(end_s) - date.fromisoformat(start_s)).days


def _row_of(statement: dict, concept: str) -> dict:
    for row in statement["statement_data"]:
        if row.get("concept") == concept:
            return row
    raise AssertionError(f"concept {concept!r} absent from the statement")


def _values_of(statement: dict, concept: str) -> dict:
    return _row_of(statement, concept)["values"]


@pytest.fixture(scope="module")
def fixture_doc():
    return json.loads(FIXTURE_PATH.read_text())


# Sentinel distinguishing "the module passed this flag" from "the module
# omitted it and the library's own default applied". Both of the module's
# mandatory flags default to False in the REAL `XBRLS.get_statement`
# signature, so a fake mirroring that default cannot tell the two apart --
# dropping `discrete_quarters=False` from the call would leave an assertion
# on the recorded value green. The fake therefore diverges from the real
# default here DELIBERATELY, and only here.
_OMITTED = object()


class _FakeXBRLS:
    """Duck-typed stand-in for what `_build_xbrls` returns, closed over
    `statements` (`fixture_doc`'s real, untruncated capture). Replicates only
    the one documented behavior this task's correctness depends on:
    `get_statement` slices the full period list to `max_periods` -- so THIS
    test is sensitive to what max_periods the module under test derives, not
    merely to what the fixture contains.

    Also RECORDS every `get_statement` call's kwargs on `self.calls` -- the
    module's two mandatory flags are otherwise invisible to this fake: it
    used to accept and silently drop them, which let the module pass `False`
    for both and still pass every assertion. `self.calls` is what makes the
    flags themselves observable, and `_OMITTED` is what makes a MISSING flag
    distinguishable from one explicitly set to the library's default.
    """

    def __init__(self, statements: dict):
        self._statements = statements
        self.calls: list[dict] = []

    def get_statement(self, statement_type, max_periods=8, standard=True,
                      use_optimal_periods=True, include_dimensions=False,
                      discrete_quarters=_OMITTED, include_quarterly=_OMITTED):
        self.calls.append({
            "statement_type": statement_type,
            "max_periods": max_periods,
            "discrete_quarters": discrete_quarters,
            "include_quarterly": include_quarterly,
        })
        kind = _STATEMENT_TYPE_OF[statement_type]
        full = self._statements[kind]
        return {
            "periods": full["periods"][:max_periods],
            "statement_data": full["statement_data"],
        }


@pytest.fixture
def series(monkeypatch, fixture_doc):
    module = _load("kpi_us_quarterly_series_test", SERIES_SCRIPT)

    # Stub the module's OWN local-import seam (`_build_xbrls`) -- `edgar` is
    # not installed under this repo's default offline test command (see the
    # module's docstring), so the real `XBRLS.from_filings` can never run
    # here. `filings` is deliberately ignored by the fake's constructor --
    # this task is pass-through, so only its COUNT (already baked into
    # `max_periods` by the caller before `_build_xbrls` is invoked) matters.
    instances: list[_FakeXBRLS] = []

    def _build_xbrls_stub(filings):
        instance = _FakeXBRLS(fixture_doc["statements"])
        instances.append(instance)
        return instance

    monkeypatch.setattr(module, "_build_xbrls", _build_xbrls_stub)
    module._fake_xbrls_instances = instances
    return module


def _fake_filings(fixture_doc):
    """Duck-typed stand-in for an ALREADY-ACQUIRED filing list -- the
    module no longer acquires anything itself, so a bare sentinel per
    accession is sufficient; only the COUNT matters to the max_periods
    derivation under test."""
    return [object() for _ in fixture_doc["_capture"]["accessions"]]


# One concept that appears in EXACTLY ONE of the three fixture statements
# (re-verified against the 2026-07-30 re-captured fixture: each is present
# in its own kind's `statement_data` and absent from the other two). They
# are what makes a returned kind's IDENTITY observable -- see
# `test_each_kind_carries_that_statements_own_lines`.
_MARKER_CONCEPT_OF = {
    "income": _INCOME_CONCEPT,
    "balance_sheet": "us-gaap_CashAndCashEquivalentsAtCarryingValue",
    "cash_flow": "us-gaap_NetCashProvidedByUsedInOperatingActivitiesAbstract",
}


def test_each_kind_carries_that_statements_own_lines(series, fixture_doc):
    """`result["income"]` must hold the INCOME statement, not merely three
    statements under three keys.

    This closes a mutation that survived every other assertion in this file:
    swapping the `income` and `cash_flow` entries of the module's own
    `_STATEMENT_TYPE_OF` left the whole suite green. Nothing else here can
    see it -- the period-count assertion compares only COUNTS (both kinds
    have the same number of periods in the fixture) and the flag assertion
    inspects only the recorded kwargs.

    A per-kind marker concept is used rather than the call ORDER because the
    contract that matters is which statement each RETURNED KEY carries; the
    order the module happens to iterate its mapping in is not a contract.
    """
    result = series.stitch_quarterly_statements(_fake_filings(fixture_doc))

    for kind, marker in _MARKER_CONCEPT_OF.items():
        concepts = {row.get("concept") for row in result[kind]["statement_data"]}
        assert marker in concepts, (
            f"result[{kind!r}] does not carry the {kind} statement: its "
            f"marker concept {marker!r} is absent from statement_data -- "
            f"_STATEMENT_TYPE_OF maps {kind!r} to the wrong statement_type"
        )
        for other, other_marker in _MARKER_CONCEPT_OF.items():
            if other != kind:
                assert other_marker not in concepts, (
                    f"result[{kind!r}] carries {other}'s marker concept "
                    f"{other_marker!r} -- the kinds are crossed"
                )


def test_reports_the_filing_count_it_used(series, fixture_doc):
    """`n_filings_used` is part of the documented return contract and the
    only thing in the result that reports the derivation's INPUT -- a caller
    whose acquire loop hands over FEWER filings than the span listed (because
    an accession failed) needs it to tell a full span from a partially
    acquired one. Deleting the key broke no test before this one."""
    filings = _fake_filings(fixture_doc)
    result = series.stitch_quarterly_statements(filings)

    assert result["n_filings_used"] == len(filings) == fixture_doc["n_filings"]


def test_empty_filings_is_rejected_loudly(series):
    """An empty `filings` list must raise, not return an empty answer.

    This is the module's only guard, and it is load-bearing in a way its size
    hides: `max_periods` is derived as `len(filings) * 2`, so an empty list
    makes it 0, and `get_statement` then slices every period list to nothing.
    The result is a fully-shaped answer -- all three statement kinds present,
    each with an empty `periods` list -- that is INDISTINGUISHABLE IN SHAPE
    from a complete one. That is precisely the silent-truncation failure mode
    this module exists to prevent, arrived at from the other direction, so
    the guard fails loud instead.

    Added after a reviewer's mutation showed that disabling the guard left
    every other test in this file green.
    """
    with pytest.raises(ValueError):
        series.stitch_quarterly_statements([])


def test_stitched_periods_describe_their_own_spans_and_are_not_truncated(
    series, fixture_doc
):
    """Plan Task D's RED. Clause 1 is the RED proper; clauses 2 and 3 are
    regression guards that were already green on the pre-2026-07-30 fixture
    and cannot fail on the defect -- they are here so the behaviour
    `include_quarterly=True` and the `max_periods` derivation buy cannot
    silently stop working, not as evidence about direction 乙.
    """
    result = series.stitch_quarterly_statements(_fake_filings(fixture_doc))

    # --- CLAUSE 1 (THE RED): a cash-flow key's span describes its value ---
    #
    # 1a. The named end-date-sharing pair. Under discrete_quarters=True both
    # of these keys held 37,044,000,000 -- the dependency wrote the quarter
    # ENDING 2025-03-31 into the 273-day key as well as the 89-day one, so a
    # nine-month span and a one-quarter span reported one number between
    # them. Under `False` the 273-day key holds the true nine-month
    # cumulative and the two differ.
    cash_flow = _values_of(result["cash_flow"], _CFO_CONCEPT)
    assert _span_days(_CUMULATIVE_273D) == 273
    assert _span_days(_DISCRETE_89D) == 89
    assert cash_flow[_CUMULATIVE_273D] == _CASHFLOW_273D_VALUE, (
        f"the 273-day cash-flow key {_CUMULATIVE_273D} holds "
        f"{cash_flow[_CUMULATIVE_273D]:,.0f}, expected the true nine-month "
        f"cumulative {_CASHFLOW_273D_VALUE:,.0f}. Holding "
        f"{_CASHFLOW_89D_VALUE:,.0f} means the discrete quarter ending "
        "2025-03-31 was written into it -- i.e. discrete_quarters=True"
    )
    assert cash_flow[_DISCRETE_89D] == _CASHFLOW_89D_VALUE
    assert cash_flow[_CUMULATIVE_273D] != cash_flow[_DISCRETE_89D], (
        "a 273-day and an 89-day cash-flow key hold the same value, so at "
        "least one of them misdescribes its own span"
    )

    # 1b. The same claim over the WHOLE fiscal year rather than one pair:
    # FY2025's four cumulative cash-flow columns, each spanning what its key
    # says. Under `True` three of these four differ (they held the discrete
    # quarters 22,291 / 37,044 / 42,647 instead), so this is clause 1 in its
    # sharpest form.
    for period_id, expected in _FY2025_CASHFLOW_CUMULATIVE.items():
        assert cash_flow[period_id] == expected, (
            f"{period_id} ({_span_days(period_id)}d) holds "
            f"{cash_flow[period_id]:,.0f}, expected the cumulative "
            f"{expected:,.0f}"
        )
    # The cumulative chain's consecutive differences ARE the discrete
    # quarters, which is what makes this fixture usable by the derivation
    # task downstream; asserted here only as a self-consistency check on the
    # four values above.
    chain = list(_FY2025_CASHFLOW_CUMULATIVE.values())
    assert chain == sorted(chain), (
        "FY2025's cumulative cash-flow columns are not monotonic in span, so "
        "they cannot all be cumulative totals of the same fiscal year"
    )

    # 1c. Generalised by RULE across EVERY cash-flow line, not just the
    # operating one: no line may report the same NON-ZERO value under two
    # duration keys that share an end date but differ in span, because the
    # longer span strictly contains the shorter. Measured on the committed
    # fixture: 0 such lines at this end date. The `True`-mode capture of the
    # same filings had many; that count is MEASURED-not-repo (28, counted
    # against the deliberately uncommitted `True`-mode capture) and so is NOT
    # re-derivable by a later reader -- nothing here rests on the exact
    # figure, only on 0-versus-many. What IS re-derivable from the committed
    # fixture, and bounds it: 30 of this statement's 40 lines carry both of
    # these keys with a non-zero value under each, so 30 is the ceiling any
    # collision count at this end date can reach.
    #
    # Scoped to ONE end date deliberately. Sweeping every end date is NOT a
    # valid rule: measured, one line (`RepaymentsOfDebtMaturingInMoreThan
    # ThreeMonths`, end 2025-12-31) legitimately reports 3,000,000,000 for
    # both a 91-day and a 183-day key because the whole half-year's
    # repayment fell inside that one quarter. Zero values are skipped for
    # the same reason -- zero spans any period.
    collisions = []
    for row in result["cash_flow"]["statement_data"]:
        values = row.get("values") or {}
        if _CUMULATIVE_273D not in values or _DISCRETE_89D not in values:
            continue
        cumulative, discrete = values[_CUMULATIVE_273D], values[_DISCRETE_89D]
        if cumulative == discrete and cumulative != 0:
            collisions.append((row.get("concept"), cumulative))
    assert collisions == [], (
        f"{len(collisions)} cash-flow line(s) report the same non-zero value "
        f"for a 273-day and an 89-day period ending 2025-03-31, so one key "
        f"misdescribes its span: {collisions[:5]}"
    )

    # --- CLAUSE 2 (regression guard): income keeps BOTH column kinds ------
    # What `include_quarterly=True` buys. The income statement is unaffected
    # by `discrete_quarters` (the dependency gates it to CashFlowStatement),
    # so this was green on the defective fixture too -- it guards against
    # `include_quarterly` being dropped, nothing more.
    income_periods = {period_id for period_id, _label in result["income"]["periods"]}
    assert _DISCRETE_89D in income_periods, "income lost its discrete columns"
    assert _CUMULATIVE_273D in income_periods, "income lost its cumulative columns"
    income = _values_of(result["income"], _INCOME_CONCEPT)
    assert income[_DISCRETE_89D] == _INCOME_89D_VALUE
    assert income[_CUMULATIVE_273D] == _INCOME_273D_VALUE

    # --- CLAUSE 3 (regression guard): no truncation ------------------------
    # Also green on the defective fixture -- `discrete_quarters` changes
    # values and labels, never the period COUNT. This guards the max_periods
    # derivation: a count of 8 means the library default applied.
    for kind, expected_count in _EXPECTED_PERIOD_COUNTS.items():
        assert expected_count > _MAX_PERIODS_LIBRARY_DEFAULT, (
            f"the expected {kind} count ({expected_count}) must itself "
            "exceed 8, or it proves nothing about truncation"
        )
        got = len(result[kind]["periods"])
        assert got == expected_count, (
            f"{kind} returned {got} periods, expected {expected_count}. "
            f"{_MAX_PERIODS_LIBRARY_DEFAULT} means max_periods was left at "
            "the library default instead of being derived from the filing "
            "count; any other mismatch means fixture re-capture drift (see "
            "the fixture's _capture.filings)"
        )
        assert len(fixture_doc["statements"][kind]["periods"]) == expected_count, (
            f"the committed fixture's own {kind} period count no longer "
            f"matches this test's measured {expected_count} -- the fixture "
            "was re-captured; re-measure rather than loosening the assertion"
        )


def test_both_mandatory_flags_are_passed_explicitly(series, fixture_doc):
    """`discrete_quarters=False` and `include_quarterly=True` must reach
    every `get_statement` call.

    Split out of the clause test because neither of that test's assertions
    can see the flags: the fixture's values come back whatever the module
    passes, and the count check is driven by `max_periods` alone.

    `discrete_quarters` is asserted to be exactly `False` AND NOT MERELY
    ABSENT. The real signature already defaults it to `False`, so omitting
    the argument produces identical behaviour against edgartools 5.42.0 --
    which is why the fake defaults it to `_OMITTED` instead. The explicit
    pass is the contract: this arc chose `False` against a measurement, so an
    upstream change of that default must break this test rather than quietly
    change what the module means.
    """
    series.stitch_quarterly_statements(_fake_filings(fixture_doc))

    calls = series._fake_xbrls_instances[0].calls
    assert len(calls) == len(_STATEMENT_TYPE_OF), (
        f"expected one get_statement call per statement kind, got {len(calls)}"
    )
    for call in calls:
        assert call["discrete_quarters"] is False, (
            f"{call['statement_type']}: discrete_quarters must be passed "
            f"explicitly as False, got {call['discrete_quarters']!r} "
            "(_OMITTED means the module did not pass it at all)"
        )
        assert call["include_quarterly"] is True, (
            f"{call['statement_type']}: include_quarterly must be True, "
            f"got {call['include_quarterly']!r}"
        )


def test_max_periods_is_derived_from_the_filing_count_not_any_constant(
    series, fixture_doc
):
    """THE POINT OF THIS TASK, pinned from ABOVE -- against the value the
    module actually passes -- and not only from below.

    Every other assertion in this file sees `max_periods` solely through its
    CONSEQUENCE, the fake's `periods[:max_periods]` slice, and a slice is
    blind to any bound at or above the true period count. So the whole suite
    stayed green under three mutations a reviewer's harness ran: raising
    `_PERIODS_PER_FILING_CEILING` from 2 to 3; replacing the derivation with
    the hand-picked constant `200` that the module's own docstring
    explicitly forbids; and `11 * _PERIODS_PER_FILING_CEILING`, which drops
    the `len(filings)` dependence entirely yet still passes for THIS
    fixture's filing count.

    Two properties make this assertion able to fail, both taken from the
    same-branch proven pattern in `tests/data/test_us_quarterly_filing_list.
    py:172`, `test_uncapped_path_derives_limit_from_the_payloads_own_row_
    count`, whose docstring states the principle: a seed "bigger than any
    constant" cannot pin a derivation, because a bigger constant always
    beats it -- pin the DERIVATION instead.

      1. The expected value is READ BACK from the filing list actually
         passed, never written as a literal here, so it cannot drift from
         the fixture and no constant -- 8, 22, 200, 10_000 -- can satisfy it.
      2. The module is called TWICE, with DIFFERENT filing counts. With one
         count only, `11 * 2` and `len(filings) * 2` agree on every
         observation, and the third mutation survives.

    The `* 2` IS a literal here, deliberately not read from the module's own
    `_PERIODS_PER_FILING_CEILING` -- mirroring the module's constant would
    make the 2->3 mutation invisible again. 2 is the
    up-to-two-stitched-periods-per-filing ceiling that `include_quarterly`'s
    own docstring states (edgartools 5.42.0,
    `edgar/xbrl/stitching/xbrls.py:167-171`), which is the whole
    justification for the derivation; see the module docstring's "WHY * 2".
    """
    fixture_count = len(fixture_doc["_capture"]["accessions"])
    # A second count that DIFFERS from the fixture's own -- that difference
    # is the entire reason for the second call (see property 2 above).
    # Nothing else about the number matters: this module is pass-through and
    # the fake ignores the filings themselves, only their count reaches the
    # derivation.
    other_count = 3
    assert other_count != fixture_count, (
        "the second call's filing count must differ from the fixture's "
        f"({fixture_count}), or a constant equal to it stays invisible"
    )

    for n_filings in (fixture_count, other_count):
        filings = [object() for _ in range(n_filings)]
        series.stitch_quarterly_statements(filings)

        recorded = [
            call["max_periods"]
            for call in series._fake_xbrls_instances[-1].calls
        ]
        expected = [len(filings) * 2] * len(_STATEMENT_TYPE_OF)
        assert recorded == expected, (
            f"with {len(filings)} filings, get_statement must be called with "
            f"max_periods={len(filings) * 2} (the filing count times the "
            f"documented two-stitched-periods-per-filing ceiling) on all "
            f"{len(_STATEMENT_TYPE_OF)} statement kinds; got {recorded}. "
            f"A value of {_MAX_PERIODS_LIBRARY_DEFAULT} means the library "
            "default applied; any other value independent of the filing "
            "count means the derivation was replaced by a constant, which is "
            "the silent-truncation defect this module exists to prevent"
        )


# ==========================================================================
# Plan Task E — derive the discrete quarters the filings do not state
# ==========================================================================


@pytest.fixture(scope="module")
def period_kind():
    """Task C's COMMITTED span classifier — the reader every downstream
    consumer will use on a derived key. Loaded here rather than reimplemented
    so a test cannot agree with a derived key that the real classifier would
    label `annual`."""
    return _load("kpi_us_quarterly_periods_for_task_e", PERIODS_SCRIPT).period_kind


@pytest.fixture
def statements(fixture_doc):
    """A DEEP COPY of the captured statements, so a test may delete a period
    to construct a case the run-date-relative capture does not contain
    (plan Task E, GREEN: construct it in an in-test copy, never re-capture)."""
    return copy.deepcopy(fixture_doc["statements"])


def _derived_by_key(derived: dict, kind: str) -> dict:
    """`{period_key: entry}` for one statement kind, failing loudly on a
    duplicate key — two derived entries for one period would make every
    lookup below silently pick one of them."""
    entries = derived[kind]
    by_key = {entry["key"]: entry for entry in entries}
    assert len(by_key) == len(entries), (
        f"{kind}: two derived entries share a period key: "
        f"{[e['key'] for e in entries]}"
    )
    return by_key


def _figures(entry: dict) -> dict:
    """A derived entry's `values` re-keyed by CONCEPT alone.

    The module keys them by `(row_index, concept)`, because a concept does not
    identify a line — two rows can share one. Most tests here feed statements
    whose concepts are unique and are about something else entirely (a window
    bound, the sort order, `Decimal` exactness), so this lets them keep saying
    "this concept's figure" without also pinning a row index incidental to
    their subject.

    RAISES on a repeated concept rather than picking a winner. Picking one is
    precisely the defect
    `test_two_lines_sharing_a_concept_each_keep_their_own_derived_figure`
    pins, and a helper that quietly re-committed it here would hide a
    regression of that exact shape from every test that goes through it.
    """
    figures: dict = {}
    for (index, concept), value in entry["values"].items():
        assert concept not in figures, (
            f"concept {concept!r} appears on more than one line of this "
            f"statement (line {index} and another), so re-keying by concept "
            "alone would drop a figure — assert on the (row_index, concept) "
            "keys directly instead"
        )
        figures[concept] = value
    return figures


def _drop_period(statements: dict, kind: str, period_key: str) -> dict:
    """Remove one period column from an in-test copy — from the statement's
    own `periods` list AND from every line's `values`, which is how a capture
    that never had the column would look. Returns `{concept: value}` for the
    values removed, so a test can assert a re-derived figure against what was
    taken away rather than against a literal."""
    statement = statements[kind]
    before = len(statement["periods"])
    statement["periods"] = [
        entry for entry in statement["periods"] if entry[0] != period_key
    ]
    assert len(statement["periods"]) == before - 1, (
        f"{period_key} was not a period of the {kind} statement, so dropping "
        "it proves nothing -- the test's premise is wrong"
    )
    removed = {}
    for row in statement["statement_data"]:
        values = row.get("values") or {}
        if period_key in values:
            removed[row["concept"]] = values.pop(period_key)
    assert removed, f"no {kind} line carried a value for {period_key}"
    return removed


def _declared_precision(row: dict, period_key: str) -> Decimal:
    """The worth of the last digit the FILER VOUCHED FOR in `row` at
    `period_key`, read from XBRL's own `decimals` attribute as the capture
    carries it: `decimals: -6` says the figure is stated to the nearest
    million, so `10 ** 6` is what its last vouched digit is worth. Never a
    literal -- the number comes out of the row, per period key, so a re-capture
    that changes a filer's stated precision changes this with it.

    Returns `Decimal(0)` -- i.e. DEMAND AN EXACT MATCH -- when the row declares
    no usable precision for that key: the key is absent from `decimals`, or its
    value is not an integer (`None`, a stringified number, or XBRL's `INF`,
    which means "exact" and for which exact is the right answer anyway). An
    absent declaration is NOT licence for an unbounded tolerance, so the
    undeclared case is held to the STRICTEST standard rather than the loosest:
    it can make this test fail loudly, never pass quietly. `bool` is excluded
    explicitly because it is an `int` subclass in Python and `True` is not a
    precision.
    """
    declared = (row.get("decimals") or {}).get(period_key)
    if isinstance(declared, bool) or not isinstance(declared, int):
        return Decimal(0)
    return Decimal(10) ** -declared


def test_derived_q4_revenue_matches_the_recorded_cross_implementation_figure(
    series, fixture_doc, period_kind
):
    """Plan Task E's first RED. Its oracle, 76,441,000,000, is the closest this
    file has to an independent one -- and the claim is bounded, because an
    earlier draft of this docstring called it "genuinely INDEPENDENT" and that
    was more than the evidence supports (plan Task E, Acceptance, "Bound on the
    word independent").

    THE NAME NO LONGER SAYS `independent`, and the divergence from the plan is
    deliberate: plan Task E's RED names this
    `test_derived_q4_revenue_matches_the_independent_implementation`, while the
    same Acceptance clause states the figure's independence rests on a
    session-scoped probe that is not re-derivable. A test name is read as an
    assertion, so it may only claim what holds -- the figure is RECORDED from a
    second implementation, not shown to agree with one here. Reported back for
    the plan's RED to be amended to this name (round 3).

    What IS established: the figure agrees three ways -- the plan, this file's
    constant, and the fixture's own `281,724,000,000 - 205,283,000,000`, which
    part 1 below re-reads out of the input rather than trusting the constant.
    What is NOT: that a second implementation was ever seen to produce it. That
    rests on a session-scoped probe of `edgar/ttm/calculator.py:665`
    (`_derive_q4_from_fy`) which the brief itself records as not re-derivable,
    and no artifact in this repo shows the two agreeing. Recorded, not called.

    THE STRONGEST EXTERNAL SUPPORT IS FOR THE KEY RULE, NOT THE FIGURE, and it
    is reproducible. The dependency computes a derived quarter's start as the
    day after its subtrahend's period ends -- exactly this module's rule -- at
    four independent sites in `edgar/ttm/calculator.py` (edgartools==5.42.0,
    opened and read 2026-07-30): `:620` (`q2_start = q1.period_end +
    timedelta(days=1)`), `:655` (`q3_start = ytd6.period_end + ...`), `:703`
    (`q4_start = ytd9.period_end + ...`) and `:772`. That function also refuses
    on ambiguity rather than guessing -- `:756`, `if len(distinct) != 3:`, whose
    own comment reads "gaps, overlaps, stub periods ... skip rather than emit a
    wrong value" -- which is the same discipline as this module's two-candidate
    refusal, arrived at separately.

    Fed by the real `stitch_quarterly_statements` output rather than the
    fixture dict, so this also pins that the two functions COMPOSE -- the
    seam the projection task will call through.

    Three things are asserted, and the KEY is the one a value-only test
    would miss. A Q4 written back onto its own FY input's key would hold the
    right number under a 364-day key, which is precisely the defect
    direction 乙 was chosen to remove; the classifier assertion is what makes
    that mis-keying loud instead of silent, since the real classifier reads
    day spans and would answer `annual`.
    """
    stitched = series.stitch_quarterly_statements(_fake_filings(fixture_doc))
    derived = series.derive_discrete_quarters(stitched)

    income = _derived_by_key(derived, "income")
    assert _FY2025_DERIVED_Q4 in income, (
        f"no derived income period keyed {_FY2025_DERIVED_Q4}; got "
        f"{sorted(income)}"
    )
    entry = income[_FY2025_DERIVED_Q4]

    # 1. The figure, against the independent oracle -- AND against the same
    # subtraction read back out of the input, so neither a stale literal nor
    # a constant can satisfy this on its own.
    filed = _values_of(stitched["income"], _INCOME_CONCEPT)
    read_back = Decimal(str(filed[_FY2025_FY])) - Decimal(str(filed[_FY2025_YTD9]))
    assert read_back == _RECORDED_FY2025_Q4_REVENUE, (
        f"the fixture's own FY minus Q3-YTD is {read_back}, but the "
        f"independent implementation's recorded answer is "
        f"{_RECORDED_FY2025_Q4_REVENUE} -- the fixture moved; re-measure "
        "rather than loosening this"
    )
    assert _figures(entry)[_INCOME_CONCEPT] == _RECORDED_FY2025_Q4_REVENUE

    # 2. The key describes the value's span, and is NEITHER input's key.
    assert entry["key"] not in (_FY2025_FY, _FY2025_YTD9), (
        "the derived quarter reuses one of its own inputs' period keys, so a "
        "key's span no longer describes the span of its value"
    )
    assert (entry["start"], entry["end"]) == ("2025-04-01", "2025-06-30")
    assert _span_days(entry["key"]) == 90

    # 3. The committed classifier agrees it is a discrete quarter.
    assert period_kind(entry["key"]) == "discrete_quarter", (
        f"{entry['key']} classifies as {period_kind(entry['key'])!r}; a "
        "derived quarter that does not read as a discrete quarter is exactly "
        "the silent mis-keying this assertion exists to catch"
    )

    # The provenance of the subtraction, so a reader can re-check it.
    assert entry["minuend"] == _FY2025_FY
    assert entry["subtrahend"] == _FY2025_YTD9


def test_derived_cashflow_quarters_match_the_dependencys_own_arithmetic(
    series, fixture_doc, statements, period_kind
):
    """Plan Task E's second RED. Its named oracle is NOT independent -- the
    dependency's `_unaccumulate_cashflow_ytd` applies the same formula to the
    same inputs (module docstring, grade 2) -- so this test does not stop
    there. Part 3 re-derives columns MSFT itself filed, after deleting them,
    which is an oracle no wrong formula and no wrong period pairing survives.

    Part 3's re-derived figures are compared to the filer's DECLARED PRECISION
    rather than to the dollar, because a difference of two columns stated to the
    nearest million is itself only good to the nearest million or two. That
    bound is computed per line from the row's own XBRL `decimals`
    (`_declared_precision`), never a literal, and a line that declares NO
    precision is compared EXACTLY. Parts 1 and 2 remain exact.

    The dependency is NOT called here. Its figures are recorded constants.
    """
    derived = series.derive_discrete_quarters(fixture_doc["statements"])
    cash_flow = _derived_by_key(derived, "cash_flow")

    # --- PART 1: the one quarter no filing contains ------------------------
    # Q4 exists in no filing at all (there is no Q4 10-Q), so it is the only
    # FY2025 cash-flow quarter this derivation has to supply.
    assert _FY2025_DERIVED_Q4 in cash_flow, (
        f"no derived cash-flow period keyed {_FY2025_DERIVED_Q4}; got "
        f"{sorted(cash_flow)}"
    )
    q4 = cash_flow[_FY2025_DERIVED_Q4]
    assert _figures(q4)[_CFO_CONCEPT] == _CFO_FY2025_Q4
    assert period_kind(q4["key"]) == "discrete_quarter"

    # --- PART 2: all four discrete quarters, and their sum -----------------
    # Three are filed by MSFT, the fourth is derived. Their sum must be the
    # fixture's OWN fiscal-year figure -- read back, not written in -- which
    # is what proves the four are a partition of the year rather than four
    # numbers that individually look plausible.
    filed = _values_of(fixture_doc["statements"]["cash_flow"], _CFO_CONCEPT)
    quarters = {}
    for key, expected in _FY2025_CASHFLOW_DISCRETE.items():
        value = (
            _figures(cash_flow[key])[_CFO_CONCEPT]
            if key in cash_flow
            else Decimal(str(filed[key]))
        )
        assert value == expected, (
            f"FY2025 operating cash flow at {key} is {value}, expected "
            f"{expected}"
        )
        quarters[key] = value
    assert sum(quarters.values()) == Decimal(str(filed[_FY2025_FY])), (
        f"the four discrete quarters sum to {sum(quarters.values())}, but the "
        f"fiscal year they partition is {filed[_FY2025_FY]} -- so they are "
        "not the four quarters of that year"
    )

    # --- PART 3: re-derive what the filer stated, after deleting it --------
    # MSFT files three-month cash-flow columns, so Q2 and Q3 are normally
    # taken as filed and never derived. Dropping them makes the Q2 = YTD6 - Q1
    # and Q3 = YTD9 - YTD6 subtractions fire, and the expected values are the
    # ones just removed -- the filer's own numbers, arrived at without any
    # subtraction. A wrong formula, or a pairing off by one period, cannot
    # reproduce them.
    #
    # THE COMPARISON IS TO THE FILER'S OWN DECLARED PRECISION, NOT TO THE
    # DOLLAR -- and the bound is READ FROM THE DATA, never written in. Every
    # cash-flow column in this capture carries `decimals: -6`, MSFT's own
    # statement that the figure is accurate to the nearest million and no
    # further. Two such columns differenced therefore cannot be expected to
    # land on a third such column exactly: each of the three carries up to half
    # a million of rounding, so a CORRECT subtraction can miss the filed
    # quarter by up to 1.5M. `_declared_precision` sums the whole last-digit
    # worth of the two INPUT columns -- 1M + 1M here -- which covers that 1.5M
    # without this test having to reason in halves. It is 2M only because the
    # filer said `-6`: a filer stating whole dollars collapses it to zero and
    # this comparison is exact again. Exactly 2 of the 32 Q3 lines actually need
    # it, each by exactly 1M (`IncreaseDecreaseInOtherCurrentAssets`,
    # `...OtherCurrentLiabilities`); the other 30, and all 32 of Q2's, still
    # match to the dollar. PARTS 1 AND 2 STAY EXACT -- Part 2 sums four columns
    # against a fifth the filer stated, where a rounding residue would be a
    # finding rather than expected noise.
    #
    # THIS IS NOT A LICENCE TO BE APPROXIMATELY RIGHT, and that was measured,
    # not assumed: four mutations of the module under test, each run on a
    # scratchpad copy against this comparison (2026-07-30).
    #   - Q3 re-paired as YTD9 - Q1 in `_SUBTRACTIONS`: the derived KEY moves to
    #     duration_2024-10-01_2025-03-31, so Q3 is never derived and the
    #     key-presence assertion above fires first.
    #   - the same mis-pairing applied to the VALUES ONLY, key left correct, so
    #     that only this comparison can catch it: 29 of 32 lines exceed
    #     tolerance, the smallest excess being 16M (8x the 2M bound) and the
    #     largest 24.108e9.
    #   - subtraction replaced by addition: 31 of 32 lines exceed tolerance in
    #     each quarter, smallest excess 66M (Q2) / 84M (Q3), largest 112.942e9.
    #   - derived key's start shifted one day: every derived key moves, so
    #     neither quarter is found at all.
    # The smallest over-tolerance deviation any of them produced was 16M, eight
    # times this bound; the largest, 112.942e9, was 56,471 times it.
    q2_key = "duration_2024-10-01_2024-12-31"
    q3_key = "duration_2025-01-01_2025-03-31"
    # The two cumulative columns each derivation must pair, named here rather
    # than taken from the derived entry's own `minuend`/`subtrahend`: a
    # tolerance computed from the thing under test is a tolerance the thing
    # under test can widen.
    q1_key = "duration_2024-07-01_2024-09-30"
    ytd6_key = "duration_2024-07-01_2024-12-31"
    ytd9_key = "duration_2024-07-01_2025-03-31"
    removed_q2 = _drop_period(statements, "cash_flow", q2_key)
    removed_q3 = _drop_period(statements, "cash_flow", q3_key)

    re_derived = _derived_by_key(series.derive_discrete_quarters(statements),
                                "cash_flow")
    cases = (
        (q2_key, removed_q2, ytd6_key, q1_key),
        (q3_key, removed_q3, ytd9_key, ytd6_key),
    )
    for key, removed, minuend_key, subtrahend_key in cases:
        assert key in re_derived, (
            f"{key} was deleted from the input and NOT re-derived; the "
            f"subtraction that produces it never fired. Got {sorted(re_derived)}"
        )
        assert period_kind(key) == "discrete_quarter"
        values = _figures(re_derived[key])
        mismatched = {}
        for concept, was_filed in removed.items():
            row = _row_of(statements["cash_flow"], concept)
            tolerance = (
                _declared_precision(row, minuend_key)
                + _declared_precision(row, subtrahend_key)
            )
            got = values.get(concept)
            if got is None or abs(got - Decimal(str(was_filed))) > tolerance:
                mismatched[concept] = (got, was_filed, tolerance)
        assert not mismatched, (
            f"{key}: {len(mismatched)} line(s) re-derived to something other "
            f"than the value MSFT itself filed for that quarter, by MORE than "
            f"the precision the filer declared for the two inputs "
            f"({minuend_key} minus {subtrahend_key}); each entry is "
            f"(re-derived, filed, tolerance): {list(mismatched.items())[:5]}"
        )


def test_a_year_missing_the_input_period_yields_no_derived_period(
    series, fixture_doc, statements
):
    """Plan Task E, GREEN: a fiscal year missing any input the subtraction
    needs produces NO derived period -- never a partial subtraction and never
    a fabricated figure.

    Two cases, and the second is the one that bites. Refusing when a year is
    absent entirely is easy; refusing when a year is PRESENT but its middle
    cumulative column is missing is where a consecutive-difference rule
    would happily emit a six-month remainder under a six-month key. That
    remainder would be arithmetically true and honestly keyed -- and still
    wrong, because nothing asked for it and a reader scanning for quarters
    would count it as one.
    """
    derived = series.derive_discrete_quarters(fixture_doc["statements"])

    # --- CASE 1: the fixture's own open year (no FY column captured) -------
    # Non-vacuous: the year IS in the fixture, with three of its four
    # cumulative columns, so nothing but the absent FY can be refusing Q4.
    for kind in ("income", "cash_flow"):
        period_ids = {entry[0] for entry in fixture_doc["statements"][kind]["periods"]}
        assert _OPEN_YEAR_YTD9 in period_ids, (
            f"the {kind} statement no longer carries {_OPEN_YEAR_YTD9}, so "
            "this test's premise about the open fiscal year is stale"
        )
        assert not any(
            pid.startswith(f"duration_{_OPEN_YEAR_START}_") and _span_days(pid) > 300
            for pid in period_ids
        ), (
            f"the {kind} statement now HAS an annual column for the fiscal "
            f"year starting {_OPEN_YEAR_START}; the fixture was re-captured "
            "and this refusal case no longer exists"
        )
        keys = set(_derived_by_key(derived, kind))
        assert _OPEN_YEAR_WOULD_BE_Q4 not in keys, (
            f"{kind}: a Q4 was derived for the fiscal year starting "
            f"{_OPEN_YEAR_START}, whose FY column is absent -- so it was "
            "computed from something other than FY minus nine months"
        )
        assert not any(key.startswith("duration_2026-04-01_") for key in keys), (
            f"{kind}: something was derived starting 2026-04-01, where that "
            f"year's only inputs end at {_OPEN_YEAR_YTD9}"
        )

    # --- CASE 2: a year present, with a MIDDLE cumulative column removed ---
    q2_key = "duration_2024-10-01_2024-12-31"
    q3_key = "duration_2025-01-01_2025-03-31"
    ytd6_key = "duration_2024-07-01_2024-12-31"
    _drop_period(statements, "cash_flow", q2_key)
    _drop_period(statements, "cash_flow", q3_key)
    _drop_period(statements, "cash_flow", ytd6_key)

    keys = set(_derived_by_key(series.derive_discrete_quarters(statements),
                               "cash_flow"))
    assert q2_key not in keys, (
        "Q2 was derived although its YTD6 input is gone -- the only inputs "
        "left for it are Q1 and YTD9"
    )
    assert q3_key not in keys, "Q3 was derived although its YTD6 input is gone"
    # The specific fabrication a naive consecutive-difference rule commits:
    # YTD9 - Q1 spans two quarters, so it is neither Q2 nor Q3.
    bridge = "duration_2024-10-01_2025-03-31"
    assert bridge not in keys, (
        f"{bridge} ({_span_days(bridge)}d) was emitted in place of the two "
        "quarters whose shared input is missing -- a true subtraction of the "
        "wrong pair, which a reader scanning for quarters would miscount"
    )
    # And the refusal is TARGETED, not a blanket give-up: Q4's own inputs
    # (FY and YTD9) are untouched, so Q4 must still be derived.
    assert _FY2025_DERIVED_Q4 in keys, (
        "dropping YTD6 also suppressed Q4, whose inputs are FY and YTD9 -- "
        "the refusal is too broad"
    )


def test_no_derived_period_ever_overwrites_a_column_the_filer_stated(
    series, fixture_doc
):
    """A derived figure is a subtraction; a filed figure is a primary source.
    This function fills the gaps the filings leave and never writes over a
    column the filer stated -- so a filed number can never be replaced by a
    computed one, which is the shape of the defect this arc removed from the
    cash-flow lane.

    Pinned as a rule over every kind, and then by the exact consequence for
    this filer: MSFT files three-month cash-flow columns for Q1-Q3, so the
    ONLY cash-flow quarters left to derive are the two Q4s. If a future
    change starts emitting Q2/Q3 alongside the filer's own, this fails.
    """
    stitched = series.stitch_quarterly_statements(_fake_filings(fixture_doc))
    derived = series.derive_discrete_quarters(stitched)

    for kind in ("income", "balance_sheet", "cash_flow"):
        filed_keys = {entry[0] for entry in stitched[kind]["periods"]}
        overlap = sorted(set(_derived_by_key(derived, kind)) & filed_keys)
        assert overlap == [], (
            f"{kind}: {len(overlap)} derived period(s) reuse a key the filer "
            f"already states: {overlap}"
        )

    assert sorted(_derived_by_key(derived, "cash_flow")) == [
        _FY2024_DERIVED_Q4, _FY2025_DERIVED_Q4,
    ]
    assert sorted(_derived_by_key(derived, "income")) == [
        _FY2024_DERIVED_Q4, _FY2025_DERIVED_Q4,
    ]


def test_every_derived_period_is_marked_derived_and_keyed_as_a_quarter(
    series, fixture_doc, period_kind
):
    """Plan Task E, GREEN: every derived period is marked derived, so a
    consumer can tell a subtraction from a filed figure.

    `derived` is a SEPARATE BOOLEAN, never a period-kind value (plan Decision
    Log, one-way door #1) -- a derived Q4 is both a discrete quarter AND
    derived, and collapsing the two axes would make "every discrete quarter
    regardless of provenance" unanswerable. Both halves are asserted here:
    the flag is exactly `True`, and the same period still classifies as
    `discrete_quarter` through Task C's untouched classifier.

    The balance sheet is included deliberately: it is instant-based, so it
    has no duration column to difference and must come back with nothing
    rather than with something invented.
    """
    derived = series.derive_discrete_quarters(fixture_doc["statements"])

    assert set(derived) == {"income", "balance_sheet", "cash_flow"}, (
        f"every statement kind must be answered, got {sorted(derived)}"
    )
    assert derived["balance_sheet"] == [], (
        "the balance sheet is instant-based -- it carries no duration column "
        f"to difference, so nothing may be derived for it: "
        f"{derived['balance_sheet']}"
    )

    total = 0
    for kind in ("income", "cash_flow"):
        for entry in derived[kind]:
            total += 1
            assert entry["derived"] is True, (
                f"{kind} {entry['key']}: derived is {entry['derived']!r}, "
                "must be exactly True -- a consumer cannot otherwise tell a "
                "subtraction from a figure the filer stated"
            )
            assert period_kind(entry["key"]) == "discrete_quarter", (
                f"{kind} {entry['key']} classifies as "
                f"{period_kind(entry['key'])!r}, not discrete_quarter"
            )
            assert entry["values"], (
                f"{kind} {entry['key']} carries no values -- an empty column "
                "is not a derivation"
            )
    assert total == 4, (
        f"expected 4 derived quarters (a Q4 for each of the fixture's two "
        f"complete fiscal years, in each of the two duration statements), "
        f"got {total}"
    )


def test_derived_values_are_exact_decimals_not_binary_floats(
    series, fixture_doc
):
    """Cross-period arithmetic on money goes through `Decimal`, never binary
    float (docs/loom/memory/construction-guaranteed-invariant-proves-nothing.md,
    whose closing section records this same class manufacturing a false
    restatement flag in this module family).

    The value here is float-hostile on the REAL fixture rather than
    constructed: MSFT's FY2025 diluted EPS is 13.64 and its nine-month figure
    is 9.99, and `13.64 - 9.99` in binary float is 3.6500000000000004. Every
    other income line on this fiscal year is whole dollars, where float is
    exact and a green assertion would prove nothing -- so this one line is
    the whole test.
    """
    derived = series.derive_discrete_quarters(fixture_doc["statements"])
    entry = _derived_by_key(derived, "income")[_FY2025_DERIVED_Q4]
    value = _figures(entry)[_EPS_DILUTED_CONCEPT]

    filed = _values_of(fixture_doc["statements"]["income"], _EPS_DILUTED_CONCEPT)
    float_answer = filed[_FY2025_FY] - filed[_FY2025_YTD9]
    assert repr(float_answer) != str(_EPS_DILUTED_FY2025_Q4), (
        "this fixture's diluted-EPS subtraction is no longer float-hostile "
        f"({float_answer!r}), so this test can no longer fail -- find a line "
        "that is, or the Decimal requirement is unpinned"
    )

    assert isinstance(value, Decimal), (
        f"derived values must be Decimal, got {type(value).__name__} -- "
        "binary float is what manufactured a false restatement in this "
        "module family"
    )
    assert value == _EPS_DILUTED_FY2025_Q4
    assert str(value) == "3.65", (
        f"the derived diluted-EPS quarter is {value}, not the exact 3.65; "
        f"{float_answer!r} means the subtraction ran in binary float"
    )


def test_a_line_missing_one_input_value_is_omitted_never_zeroed(
    series, statements
):
    """Plan Task E: never a partial subtraction, never a fabricated zero --
    at LINE granularity, not only at period granularity.

    A line present in one of the two input columns and absent from the other
    has no derivable quarter. Treating the absent side as zero would emit the
    whole cumulative figure as if it were one quarter, which is the largest
    single error this function could make and the hardest to notice, since
    the number is real and the key is honest.
    """
    row = next(
        r for r in statements["income"]["statement_data"]
        if r.get("concept") == _INCOME_CONCEPT
    )
    dropped = row["values"].pop(_FY2025_YTD9)
    assert dropped, "the premise is stale: this line had no nine-month value"

    values = _figures(_derived_by_key(
        series.derive_discrete_quarters(statements), "income"
    )[_FY2025_DERIVED_Q4])

    assert _INCOME_CONCEPT not in values, (
        f"{_INCOME_CONCEPT} was derived from one input alone: it holds "
        f"{values.get(_INCOME_CONCEPT)}, where the fiscal-year figure is "
        f"{row['values'][_FY2025_FY]} and the nine-month figure it must be "
        "reduced by is absent"
    )
    # Other lines on the same period are unaffected -- one missing cell must
    # not take the whole column down.
    assert _CFO_CONCEPT not in values  # income statement, different concept
    assert len(values) >= 10, (
        f"only {len(values)} income lines derived; one line's missing input "
        "suppressed the rest of the column"
    )


# ==========================================================================
# Plan Task E, round 2 — the machinery the round-1 tests did not reach
# ==========================================================================
#
# EVERY TEST IN THIS SECTION WAS WRITTEN AGAINST A MEASURED MUTATION, not
# against a reading of the code. Round 1 shipped 14 green tests over this
# function while five separate pieces of its machinery could be deleted or
# inverted without turning any of them red — including the two-candidate
# refusal, which carries the strongest safety claim in the module. Per
# docs/loom/memory/a-test-can-be-correct-and-still-unable-to-fail.md, a test
# written to close a known gap is only worth what its mutation run proves, so
# each test below names the mutation it kills and that mutation was run.
#
# The mutation runs are recorded in this branch's task report rather than
# inline, with one exception: where a test needs an input shape no capture
# contains, the reason is stated at the test.


@pytest.fixture
def periods_module(series):
    """The very `kpi_us_quarterly_periods` module object the series module
    imports at runtime — NOT the one this file's `period_kind` fixture loads.

    Task E reads Task C's day-span windows through `span_windows()` at call
    time, so patching an attribute on THIS object is what a real edit to Task C
    would do. The two module objects are deliberately distinct: a test that
    reorders Task C's windows must not also change what `period_kind` answers
    for the assertions in the same test.
    """
    series._role_windows()  # force the lazy sibling import
    return sys.modules[series._PERIODS_MODULE]


def _synthetic_statement(start, spans_by_role, values_by_concept):
    """A statement built from day SPANS rather than from captured dates, for
    the input shapes no real capture contains.

    Returns `(key_of, statement)`, where `key_of[role]` is the period key that
    role landed on — so a test never writes a `duration_...` literal it would
    have to recompute by hand when a window moves.

    CONSTRUCTED, and labelled as such wherever it is used: these are not
    filings. Two of the tests below need a column whose span sits EXACTLY on a
    window bound, and one needs a fiscal year with a column missing in a way
    this filer never exhibits; neither shape can be captured, and the module's
    behaviour at exactly those points is the whole question.
    """
    key_of = {
        role: (
            f"duration_{start.isoformat()}_"
            f"{(start + timedelta(days=span)).isoformat()}"
        )
        for role, span in spans_by_role.items()
    }
    statement = {
        "periods": [[key_of[role], role] for role in spans_by_role],
        "statement_data": [
            {
                "concept": concept,
                "values": {
                    key_of[role]: value for role, value in per_role.items()
                },
            }
            for concept, per_role in values_by_concept.items()
        ],
    }
    return key_of, statement


def _role_windows_from_task_c(periods_mod):
    """`{role: (low, high)}` built from Task C's PUBLIC accessor by this test
    file's own mapping, independently of the module under test.

    Deliberately not `series._role_windows()`: several tests below feed inputs
    positioned relative to these bounds, and taking the bounds from the code
    under test would let a mutant move both the input and the expectation
    together and stay green.
    """
    windows = periods_mod.span_windows()
    ytd6, ytd9 = sorted(windows["ytd"], key=lambda span: span[0])
    return {
        "q1": windows["discrete_quarter"][0],
        "ytd6": ytd6,
        "ytd9": ytd9,
        "fy": windows["annual"][0],
    }


def test_role_windows_are_read_through_task_cs_public_accessor(
    series, periods_module, monkeypatch
):
    """Task E must reach Task C's day-span windows through `span_windows()` —
    Task C's declared public surface — not through its underscore-private
    constants.

    Round 1 read `_DISCRETE_QUARTER_SPAN` / `_YTD_SPANS` / `_ANNUAL_SPAN`
    directly. The precedents cited for that (`kpi_8k_candidates.py:359`,
    `kpi_prose_candidates.py:745`) are real, and both call a sibling's PUBLIC
    function; neither is precedent for reading private state.

    Patching the ACCESSOR is what makes the difference observable: a module
    still reading the constants would ignore this patch entirely and report the
    real windows.
    """
    monkeypatch.setattr(
        periods_module,
        "span_windows",
        lambda: {
            "discrete_quarter": ((10, 20),),
            "ytd": ((30, 40), (50, 60)),
            "annual": ((70, 80),),
        },
    )

    assert series._role_windows() == {
        "q1": (10, 20), "ytd6": (30, 40), "ytd9": (50, 60), "fy": (70, 80),
    }, (
        "the role windows did not follow Task C's public accessor, so this "
        "module is still reading Task C's private constants"
    )


def test_reordering_task_cs_ytd_windows_cannot_swap_the_six_and_nine_month_roles(
    series, periods_module, fixture_doc, monkeypatch
):
    """KILLS: `sorted(windows["ytd"], key=...)` → `tuple(windows["ytd"])`.

    Which YTD window is the six-month column is decided by its own low bound,
    never by its position in Task C's tuple — so a reordering there (a
    plausible edit while widening for a 52/53-week calendar) cannot silently
    swap the two roles. With the sort removed and the tuple reversed, `ytd6`
    becomes the nine-month window and `Q3 = YTD9 - YTD6` subtracts a longer
    column from a shorter one.

    The whole derivation is compared, not just one figure, so the pin does not
    depend on which line happens to move.
    """
    expected = series.derive_discrete_quarters(fixture_doc["statements"])

    real = periods_module.span_windows()
    assert len(real["ytd"]) == 2, "the premise is stale: Task C no longer has two YTD windows"
    reordered = {**real, "ytd": tuple(reversed(real["ytd"]))}
    monkeypatch.setattr(periods_module, "span_windows", lambda: reordered)
    assert periods_module.span_windows()["ytd"] == tuple(reversed(real["ytd"])), (
        "the premise is broken: the reordered windows were not installed"
    )

    assert series.derive_discrete_quarters(fixture_doc["statements"]) == expected, (
        "reversing the order of Task C's two YTD windows changed the "
        "derivation, so which window is treated as the six-month column "
        "depends on tuple position rather than on the window itself"
    )


def test_a_third_year_to_date_window_is_refused_loudly(
    series, periods_module, monkeypatch
):
    """This module's three subtractions name exactly TWO year-to-date roles — a
    six-month and a nine-month cumulative column — so a third YTD window in
    Task C names no role here.

    That coupling is deliberate and is stated rather than removed: a third
    window is a question about which quarter it bounds, and answering it by
    quietly ignoring the extra window would drop a quarter with no signal. What
    round 1 had was the same coupling expressed as a bare two-name unpack,
    which raised `ValueError: too many values to unpack` — true, but it names
    neither the module, the constant, nor what to do about it. Plan Task G
    carries this as a finding precisely because it is scheduled to widen these
    windows.
    """
    monkeypatch.setattr(
        periods_module,
        "span_windows",
        lambda: {
            "discrete_quarter": ((80, 100),),
            "ytd": ((175, 190), (260, 285), (300, 320)),
            "annual": ((350, 380),),
        },
    )

    with pytest.raises(ValueError) as raised:
        series._role_windows()

    message = str(raised.value)
    assert "span_windows" in message, (
        f"the refusal does not name where the windows came from: {message}"
    )
    assert "3" in message, (
        f"the refusal does not say how many windows it found: {message}"
    )
    assert "two" in message.lower(), (
        f"the refusal does not say how many it needs: {message}"
    )


_TASK_G_WIDENING = ((175, 190), (260, 380))


def test_widening_a_window_until_it_overlaps_the_next_is_refused_loudly(
    series, periods_module, statements, monkeypatch
):
    """The role resolution is correct only while Task C's four windows stay
    DISJOINT, and this is that precondition checked rather than assumed.

    The widening used here is the one plan Task G's own GREEN authorises: Task G
    exists to make a 52/53-week filer's periods classify, and its GREEN says
    that if a row does not match, "widening them is part of this task". Setting
    the nine-month YTD window to (260, 380) so it also covers a 364-day fiscal
    year is exactly such a widening, and it makes that window overlap the annual
    one.

    MEASURED on this fixture 2026-07-30, which is why the refusal has to be
    loud rather than a skip. Both outcomes of the overlap are silent:

      - with both the 273-day and the 364-day column present, the nine-month
        role has two candidates, is refused as ambiguous, and NOTHING is
        derived for that fiscal year -- indistinguishable from a filer who
        simply had no derivable quarter;
      - with the 273-day column absent (the case constructed below), the
        364-day column is the only match for BOTH the nine-month and the
        annual role, and the Q4 subtraction differences that column from
        itself.

    A configuration that turns every Q4 into either silence or nonsense must
    stop the run it is introduced on.
    """
    widened = {**periods_module.span_windows(), "ytd": _TASK_G_WIDENING}
    monkeypatch.setattr(periods_module, "span_windows", lambda: widened)
    # The second, sharper case: no nine-month column, so one column is the only
    # candidate for two roles.
    _drop_period(statements, "cash_flow", _FY2025_YTD9)

    with pytest.raises(ValueError) as raised:
        series.derive_discrete_quarters(statements)

    message = str(raised.value)
    assert "ytd9" in message and "fy" in message, (
        f"the refusal does not name the two roles whose windows collide: {message}"
    )
    assert str(_TASK_G_WIDENING[1]) in message, (
        f"the refusal does not quote the widened window a reader has to fix: "
        f"{message}"
    )
    assert "disjoint" in message.lower(), (
        f"the refusal does not say what the windows must be: {message}"
    )


def test_a_role_pair_resolving_to_one_column_never_emits_a_backwards_period(
    series, monkeypatch
):
    """The emit-time backstop: a period may never be emitted whose start is
    after its end, nor one whose minuend and subtrahend are the same column.

    Reached here by patching `_role_windows` directly, because the disjointness
    check above is what stops these windows arriving through Task C -- and a
    guard that can only be shown to work by disabling another guard has to be
    exercised that way or it is an untested claim
    (docs/loom/memory/construction-guaranteed-invariant-proves-nothing.md: an
    invariant nothing can execute is a bookkeeping check, not protection).

    So this is a deliberate belt-and-braces: with disjoint windows the
    degenerate pair is unreachable, and the point of pinning it is that
    "unreachable" is a property of the CURRENT constants, which plan Task G is
    scheduled to change.
    """
    # ytd9 and fy resolve to the same 364-day column: overlapping windows, and
    # a fiscal year carrying no nine-month column to separate them.
    monkeypatch.setattr(
        series,
        "_role_windows",
        lambda: {"q1": (80, 100), "ytd6": (175, 190), "ytd9": (260, 380),
                 "fy": (350, 380)},
    )
    key_of, statement = _synthetic_statement(
        date(2024, 7, 1),
        {"q1": 91, "ytd6": 183, "fy": 364},  # CONSTRUCTED: no 273-day column
        {"us-gaap_Revenue": {"q1": 10, "ytd6": 30, "fy": 100}},
    )

    with pytest.raises(ValueError) as raised:
        series.derive_discrete_quarters({"income": statement})

    message = str(raised.value)
    assert key_of["fy"] in message, (
        f"the refusal does not name the column it was asked to difference from "
        f"itself: {message}"
    )
    assert "q4" in message.lower(), (
        f"the refusal does not name which quarter was being derived: {message}"
    )


def _derived_key(start, subtrahend_span: int, minuend_span: int) -> str:
    """The period key a subtraction of two spans from `start` must produce: the
    day after the subtrahend ends, through the day the minuend ends. Computed,
    never written as a literal, so these tests keep working when a window moves.
    """
    return (
        f"duration_{(start + timedelta(days=subtrahend_span + 1)).isoformat()}"
        f"_{(start + timedelta(days=minuend_span)).isoformat()}"
    )


def test_a_role_with_two_candidate_columns_derives_nothing_from_that_role(series):
    """KILLS: `len(candidates) == 1` → `len(candidates) >= 1` in
    `_roles_for_year`, i.e. "take the first candidate".

    This carries the strongest safety claim in the module -- picking one of two
    candidates makes the subtraction depend on WHICH, and the resulting figure is
    indistinguishable from a correct one -- and round 1 left it unpinned. The
    mutation survived 14 green tests because the committed fixture has no
    ambiguous role: every fiscal year in it has exactly one column per window,
    so `== 1` and `>= 1` cannot differ on it. Measured 2026-07-30: with the
    mutation applied and the fixture unchanged, the derivation is byte-identical.

    So the input is CONSTRUCTED -- two columns sharing a fiscal-year start whose
    spans both fall in the discrete-quarter window. That is not exotic: a
    restated or re-filed quarter, or one 91-day and one 85-day column from a
    transition year, produce exactly this.

    The refusal must also be TARGETED. Q1 is ambiguous, so Q2 (which needs it)
    is refused -- but Q3 and Q4, whose own inputs are unambiguous, must still be
    derived. A blanket give-up would pass a keys-absent assertion while being
    wrong in the other direction.
    """
    start = date(2020, 7, 1)
    key_of, statement = _synthetic_statement(
        start,
        # CONSTRUCTED: q1_short and q1_long BOTH land in the 80-100 window.
        {"q1_short": 85, "q1_long": 91, "ytd6": 183, "ytd9": 273, "fy": 364},
        {"us-gaap_Revenue": {
            "q1_short": 10, "q1_long": 10, "ytd6": 30, "ytd9": 60, "fy": 100,
        }},
    )

    derived = series.derive_discrete_quarters({"income": statement})
    by_key = _derived_by_key(derived, "income")

    q3_key = _derived_key(start, 183, 273)
    q4_key = _derived_key(start, 273, 364)
    assert sorted(by_key) == sorted([q3_key, q4_key]), (
        "with TWO columns matching the Q1 window, the Q1 role must be left "
        "unresolved and Q2 refused -- while Q3 and Q4, whose inputs are "
        f"unambiguous, are still derived. Got {sorted(by_key)}"
    )
    # The two that did derive are right, so the refusal above is not being
    # satisfied by a derivation that fails for some other reason.
    assert _figures(by_key[q3_key])["us-gaap_Revenue"] == 30
    assert _figures(by_key[q4_key])["us-gaap_Revenue"] == 40


def test_a_period_no_line_can_supply_is_not_emitted_as_an_empty_column(series):
    """KILLS: removing the `if not values: continue` guard.

    Both roles can resolve from the `periods` list while NO line carries both
    columns -- the roles are read from the period list, the values from the rows,
    and nothing makes the two agree. Emitting that as a derived period would
    announce a quarter that exists and happens to be blank, which is a different
    and worse claim than not deriving it.

    CONSTRUCTED, because the committed fixture has no such column: every period
    in it is carried by at least one line, which is why the mutation survived.
    Here Q2's inputs are both populated and Q2 must appear; Q3 and Q4 need the
    nine-month and annual columns, which are declared in `periods` and empty in
    every row.
    """
    start = date(2021, 7, 1)
    key_of, statement = _synthetic_statement(
        start,
        {"q1": 91, "ytd6": 183, "ytd9": 273, "fy": 364},
        # CONSTRUCTED: no line carries ytd9 or fy.
        {"us-gaap_Revenue": {"q1": 10, "ytd6": 30},
         "us-gaap_CostOfRevenue": {"q1": 4, "ytd6": 9}},
    )
    period_ids = {entry[0] for entry in statement["periods"]}
    assert {key_of["ytd9"], key_of["fy"]} <= period_ids, (
        "the premise is broken: the two empty columns must still be declared "
        "periods, or the roles never resolve and the guard is not reached"
    )

    by_key = _derived_by_key(series.derive_discrete_quarters({"income": statement}),
                            "income")

    assert sorted(by_key) == [_derived_key(start, 91, 183)], (
        "only Q2 has any line carrying both of its inputs; the periods whose "
        f"inputs no line supplies must not be emitted at all. Got {sorted(by_key)}"
    )
    assert _figures(by_key[_derived_key(start, 91, 183)]) == {
        "us-gaap_Revenue": Decimal(20), "us-gaap_CostOfRevenue": Decimal(5),
    }


@pytest.mark.parametrize("bound_name,bound_index", [("low", 0), ("high", 1)])
def test_a_column_exactly_on_a_role_windows_bound_resolves_that_role(
    series, periods_module, bound_name, bound_index
):
    """KILLS: `low <= span <= high` → `low < span < high` in `_roles_for_year`
    (either comparison).

    The windows are INCLUSIVE, and round 1 could not tell: the committed
    fixture's spans are 91 / 183 / 273 / 364, every one of them strictly inside
    its window, so both comparisons agree on all of them. Task C's own suite
    pins its eight bounds exhaustively, but this is a SECOND copy of the same
    comparison in a different module, and the two are not connected by anything
    executable.

    CONSTRUCTED by necessity: a column whose span is exactly a window bound is
    what the test needs, and the bounds are read from Task C's accessor so this
    stays exact after plan Task G widens them.
    """
    windows = _role_windows_from_task_c(periods_module)
    spans = {role: window[bound_index] for role, window in windows.items()}
    assert len(set(spans.values())) == 4, (
        f"the four role windows share a {bound_name} bound, so this test cannot "
        f"tell them apart: {spans}"
    )

    start = date(2019, 7, 1)
    _key_of, statement = _synthetic_statement(
        start, spans,
        {"us-gaap_Revenue": {"q1": 10, "ytd6": 30, "ytd9": 60, "fy": 100}},
    )

    by_key = _derived_by_key(series.derive_discrete_quarters({"income": statement}),
                            "income")
    expected = {
        _derived_key(start, spans["q1"], spans["ytd6"]): 20,
        _derived_key(start, spans["ytd6"], spans["ytd9"]): 30,
        _derived_key(start, spans["ytd9"], spans["fy"]): 40,
    }
    assert sorted(by_key) == sorted(expected), (
        f"with every column sitting exactly on its window's {bound_name} bound, "
        f"all three subtractions must still fire -- the windows are inclusive. "
        f"Got {sorted(by_key)}, expected {sorted(expected)}"
    )
    for key, value in expected.items():
        assert _figures(by_key[key])["us-gaap_Revenue"] == value


@pytest.mark.parametrize("reverse_input", [False, True])
def test_derived_periods_come_back_in_ascending_key_order(
    series, statements, reverse_input
):
    """KILLS: removing the final `sorted(derived, key=...)`.

    The contract is oldest key first, and it must hold whatever order the input
    period list arrives in -- so BOTH orders are run. This capture's own period
    list is NEWEST-first (`duration_2026-01-01_2026-03-31` is its first entry),
    which is what makes the sort load-bearing: the fiscal-year groups are walked
    in the order they appear, so without the sort the answer comes back
    newest-first, following the input.

    Getting this wrong is instructive and is recorded rather than quietly fixed:
    the first version of this test REVERSED the input, on the assumption the
    capture was oldest-first. That turned the input into ascending order, which
    is exactly the order that survives with no sort at all, and the mutation
    survived a green test. The parametrisation is the fix -- one of the two rows
    must always be the discriminating one, whichever way a future re-capture
    happens to order its periods.
    """
    if reverse_input:
        for kind in ("income", "cash_flow"):
            statements[kind]["periods"].reverse()

    derived = series.derive_discrete_quarters(statements)
    for kind in ("income", "cash_flow"):
        keys = [entry["key"] for entry in derived[kind]]
        assert len(keys) >= 2, (
            f"{kind}: {len(keys)} derived period(s) -- an order assertion over "
            "fewer than two proves nothing"
        )
        assert keys == sorted(keys), (
            f"{kind}: derived periods came back {keys}, which is not ascending "
            f"by key (input period list reversed: {reverse_input}); the output "
            "followed the input's order instead of the contract's"
        )


def _one_line_statement(bad_value):
    """A four-column fiscal year whose six-month cell holds `bad_value`."""
    return _synthetic_statement(
        date(2022, 7, 1),
        {"q1": 91, "ytd6": 183, "ytd9": 273, "fy": 364},
        {"us-gaap_Revenue": {"q1": 10, "ytd6": bad_value, "ytd9": 60, "fy": 100}},
    )


@pytest.mark.parametrize(
    "bad_value,description",
    [
        (None, "an explicit null"),
        ("1,234", "a thousands-separated string Decimal cannot parse"),
        ("n/a", "a not-applicable marker"),
        ("", "an empty string"),
        (float("nan"), "a NaN, which Decimal accepts SILENTLY as Decimal('NaN')"),
        (float("inf"), "an infinity"),
    ],
)
def test_a_cell_that_is_not_a_finite_number_fails_loudly(
    series, bad_value, description
):
    """A cell that is PRESENT and is not a finite number aborts the call, naming
    the line and the column.

    This is the one asymmetry with Task C's must-not-raise contract that this
    module keeps, so it is pinned rather than left as a docstring claim. An
    ABSENT cell is ordinary and has a correct answer -- no quarter for that line,
    pinned by `test_a_line_missing_one_input_value_is_omitted_never_zeroed`. A
    cell that is present and uninterpretable has no correct answer, and skipping
    it would drop a line from a column that otherwise looks complete.

    THE NaN ROW IS THE ONE THAT WAS NOT OBVIOUS, and it is why this is a
    finiteness check rather than a parse check. `Decimal(str(float("nan")))`
    succeeds and yields `Decimal("NaN")`, which then propagates through the
    subtraction into a derived value that compares unequal to everything
    including itself -- a corrupt figure in the output with nothing raised and
    nothing logged. Measured 2026-07-30.

    A stringified NUMBER is deliberately NOT here: `Decimal(str("30"))` parses to
    30, so a numeric string passes through harmlessly and is pinned as accepted
    by the test below rather than rejected here.

    CONSTRUCTED: all 794 values in the committed fixture are numeric and finite,
    so nothing captured exercises any of these rows.
    """
    _key_of, statement = _one_line_statement(bad_value)

    with pytest.raises(ValueError) as raised:
        series.derive_discrete_quarters({"income": statement})

    message = str(raised.value)
    assert "us-gaap_Revenue" in message, (
        f"{description}: the refusal does not name the line it choked on: {message}"
    )
    assert "duration_2022-07-01_2022-12-31" in message, (
        f"{description}: the refusal does not name the column: {message}"
    )


def test_a_numerically_valid_string_cell_is_accepted_not_refused(series):
    """The flip side of the refusal above, so that check cannot quietly widen
    into "reject anything that is not already a number".

    A stitched capture may carry a figure as a string; `Decimal("30")` is exactly
    30, so there is nothing to refuse and the subtraction is still exact. This is
    also what stops the finiteness check being written as an `isinstance` test on
    the raw cell, which would reject this.
    """
    _key_of, statement = _one_line_statement("30")

    by_key = _derived_by_key(series.derive_discrete_quarters({"income": statement}),
                            "income")
    assert _figures(by_key[_derived_key(date(2022, 7, 1), 91, 183)])[
        "us-gaap_Revenue"
    ] == Decimal(20)


@pytest.mark.parametrize(
    "period_key,description",
    [
        # Stopped by `_duration_bounds`' prefix guard and its part-count guard;
        # these three never reach a date parse at all.
        ("instant_2025-06-30", "an instant key, which has no span to difference"),
        ("duration_2024-07-01", "a duration key carrying only one date"),
        ("duration_2024-07-01_2025-06-30_restated", "a third underscore part"),
        # THE TWO DISCRIMINATING ROWS: well-formed shape, unparseable dates, so
        # these reach `date.fromisoformat` and are stopped by its `except`.
        ("duration_not-a-date_2025-06-30", "a start that is not a date at all"),
        ("duration_2024-07-01_2025-06-31", "a June 31st -- shaped right, no such day"),
    ],
)
def test_a_period_key_carrying_no_readable_span_is_skipped_never_refused(
    series, period_key, description
):
    """A period key this module cannot read as a day span is SKIPPED, and the
    rest of the statement still derives. This is the one place the module aligns
    with Task C's must-not-raise contract for a malformed period key rather than
    departing from it, and it was unpinned: making `_duration_bounds` re-raise
    instead of returning `None` left the whole suite green.

    The asymmetry with the finiteness table above is the point, not an
    inconsistency. A bad CELL is refused loudly because skipping it would drop a
    line from a column that otherwise looks complete -- the reader cannot see the
    hole. A bad KEY costs only the column it names: one filer's stray period among
    many, and every other column of that statement is still derivable. So the key
    is skipped and the cell is refused, and both halves are now pinned.

    Two of the five rows are the ones that can fail: `duration_not-a-date_...` and
    the June 31st reach `date.fromisoformat` inside `_duration_bounds`, so
    removing its `except ValueError` makes them raise out of the whole call. The
    first three are stopped by the prefix and part-count guards before any parse,
    and are here as a table of what "no readable span" covers -- they hold against
    a narrower mutation, not against this one.

    CONSTRUCTED: every period key in the committed capture is a well-formed
    `duration_` or `instant_` key, so nothing captured exercises rows 2-5. The bad
    key is added to the `periods` list, which is where `_duration_bounds` reads
    keys from (`_periods_by_year_and_span`); a stray cell under the same key in a
    row would be inert, since only a resolved minuend and subtrahend are ever read
    out of a row.
    """
    start = date(2023, 7, 1)
    _key_of, statement = _synthetic_statement(
        start,
        {"q1": 91, "ytd6": 183, "ytd9": 273, "fy": 364},
        {"us-gaap_Revenue": {"q1": 10, "ytd6": 30, "ytd9": 60, "fy": 100}},
    )
    statement["periods"].append([period_key, "unreadable"])

    # The helper's own documented answer, asserted directly: `None`, not a raise.
    assert series._duration_bounds(period_key) is None, (
        f"{description}: _duration_bounds must answer None for a key it cannot "
        "read as a day span"
    )

    by_key = _derived_by_key(series.derive_discrete_quarters({"income": statement}),
                            "income")
    expected = {
        _derived_key(start, 91, 183): 20,
        _derived_key(start, 183, 273): 30,
        _derived_key(start, 273, 364): 40,
    }
    assert sorted(by_key) == sorted(expected), (
        f"{description}: the unreadable period key {period_key!r} cost this "
        f"statement its derivable quarters. Got {sorted(by_key)}, expected "
        f"{sorted(expected)}"
    )
    for key, value in expected.items():
        assert _figures(by_key[key])["us-gaap_Revenue"] == value


def test_derivation_does_not_mutate_the_statements_it_is_given(series):
    """The stitched statements are the caller's, and in this suite they are a
    module-scoped fixture shared by every test above -- so a derivation that
    wrote its results back into the input would both corrupt the caller's
    data and make this file's test order load-bearing.

    Writing derived quarters back over the columns they came from is also,
    exactly, the upstream defect this arc replaced (plan §RESOLVED FINDING):
    the dependency's own unaccumulation is correct arithmetic filed IN PLACE.

    THE INPUT IS READ FRESH FROM THE FIXTURE FILE, and that is the whole
    difference between this test working and this test being decorative. An
    earlier version took `before = copy.deepcopy(fixture_doc["statements"])`,
    and `fixture_doc` is MODULE-SCOPED: SEVEN tests above have already called
    `derive_discrete_quarters` over that same dict's rows (counted 2026-07-30 --
    five hand it in directly, two reach the same rows through
    `stitch_quarterly_statements`, whose fake returns `statement_data` BY
    REFERENCE), so an in-place write-back would already be present in anything
    copied from it. The baseline would contain the defect and the comparison
    would hold. MEASURED 2026-07-30 on a
    copy of this file carrying the old baseline: a mutant writing each derived
    value back into its own input row under the derived key passed the WHOLE FILE
    (37 passed) and failed only when this test was selected alone (1 failed, 36
    deselected) -- i.e. the assertion's outcome depended on execution order,
    which is precisely the hazard the paragraph above names. With the baseline
    below, the same mutant fails the whole-file run, and it is the only test in
    the file that fails.

    The function-scoped `statements` fixture is NOT the fix either, for the same
    reason: it deep-copies `fixture_doc`, so it inherits any pollution and an
    idempotent write-back stays invisible through it. Only an input the module
    has provably never seen makes the baseline trustworthy.
    """
    pristine = json.loads(FIXTURE_PATH.read_text())["statements"]
    before = copy.deepcopy(pristine)
    series.derive_discrete_quarters(pristine)
    assert pristine == before, (
        "derive_discrete_quarters mutated the statements it was handed"
    )


# ==========================================================================
# Plan Task F — project the series with explicit period labels
# ==========================================================================
#
# WHAT THIS SECTION IS FOR. The two functions above answer "what did the
# filer state" and "what must be differenced out"; neither produces an
# ANSWER a consumer can read. `project_quarterly_series` is the series' own
# output shape, and the one thing it must never do is hand back a period
# whose meaning has to be inferred from its day span -- which is what the
# whole arc exists to remove (brief, Smallest End State step 5).
#
# THE PROJECTION IS ITS OWN SHAPE, NOT AN EXTENSION OF `derive-as-filed`
# (user decision, brief Open Question 1). `derive-as-filed` lives in
# `kpi_spine_view.py` with its own suite (`tests/analysis/
# test_kpi_spine_view.py`) and neither file is touched by this task. NOTHING
# HERE ASSERTS THAT IT IS UNCHANGED, deliberately: a test in this file over
# a module this file does not import could not fail if that module changed,
# and a test that cannot fail is the defect class this branch has shipped
# seven times (plan Task F, Acceptance, "RED clause corrected 2026-07-30";
# docs/loom/memory/a-test-can-be-correct-and-still-unable-to-fail.md).
#
# THE LITERAL COUNTS BELOW ARE MEASURED from the committed fixture through
# the two committed functions, on 2026-07-31 -- never copied from prose.

# 17 filed income periods + the 2 derived Q4s; 17 + 2 for cash flow; the
# balance sheet's 11 instants + nothing (it carries no duration column to
# difference). Each duration total is asserted to EXCEED its filed count
# below, so a projection that dropped the derived quarters cannot satisfy it.
_PROJECTED_PERIOD_COUNTS = {"income": 19, "balance_sheet": 11, "cash_flow": 19}

# The same 41 periods bucketed by what Task C's classifier calls them. This
# is the breakdown a consumer filters on, so it is pinned rather than only
# the totals: a projection that emitted the derived Q4s under the wrong kind
# would keep every total above intact.
_PROJECTED_KIND_COUNTS = {
    "income": {"discrete_quarter": 11, "ytd": 6, "annual": 2},
    "balance_sheet": {"instant": 11},
    "cash_flow": {"discrete_quarter": 11, "ytd": 6, "annual": 2},
}

# The two Task E quarters, per statement kind. The balance sheet's empty
# list is an assertion, not a placeholder -- an instant-based statement that
# started reporting derived periods would be inventing them.
_DERIVED_KEYS_BY_KIND = {
    "income": [_FY2024_DERIVED_Q4, _FY2025_DERIVED_Q4],
    "balance_sheet": [],
    "cash_flow": [_FY2024_DERIVED_Q4, _FY2025_DERIVED_Q4],
}

_STATEMENT_KINDS = ("income", "balance_sheet", "cash_flow")


def _projection_of(series, fixture_doc, ticker: str = "MSFT") -> dict:
    """The projection of the real stitched capture, through the real
    `stitch_quarterly_statements` -- so these tests pin that the three
    functions COMPOSE, which is the seam plan Task H calls through."""
    stitched = series.stitch_quarterly_statements(_fake_filings(fixture_doc))
    return series.project_quarterly_series(stitched, ticker)


def _periods_of(projection: dict, kind: str) -> list[dict]:
    return projection["statements"][kind]["periods"]


def test_every_projected_period_declares_its_kind(
    series, fixture_doc, period_kind
):
    """Plan Task F's RED. Every emitted period says WHAT IT IS -- a kind from
    Task C's classifier and a `derived` boolean -- so no consumer has to infer
    a period's meaning from its day span. The brief states the gap under
    CURRENT STATE EVIDENCE, not under Smallest End State, and the sentence is
    quoted here verbatim (corrected round 2 -- it was attributed to "Smallest
    End State step 5", which is a different sentence, and the quote had been
    lightly reworded inside its own quote marks):
    "**there is no period type field anywhere in the row schema**, which is
    why step 5 above is a requirement and not a nicety"
    (docs/loom/specs/2026-07-28-us-quarterly-statement-series.md:90-92, opened
    2026-07-31). Step 5 is the requirement the sentence points AT
    (`:62-63`, "Label every period explicitly").

    `kind` is checked against the COMMITTED classifier this file loads
    separately, not against a literal table: a projection that bucketed spans
    its own way would agree with a table written from the same misreading.

    THAT CHECK BINDS THE FILED BRANCH ONLY, on this fixture. Both derived Q4s
    here classify as `discrete_quarter` anyway, so nothing in this test can
    tell a classifier read from a hardcoded kind on the DERIVED branch;
    `test_a_derived_periods_kind_also_comes_from_the_classifier` below is what
    pins that, on a constructed input whose derived quarter classifies
    `unknown`.

    THE COUNTS ARE THE LOAD-BEARING PART, and they are why this test is a RED
    rather than a vacuous universal. Every per-period assertion here is
    satisfied vacuously by a projection that DROPS periods -- emitting only
    the filed ones, or only the ones it found easy, leaves "every period
    declares its kind" true and the answer wrong. So the total per statement
    kind, the breakdown by kind, and the exact set of derived keys are all
    pinned, and the duration totals are asserted to exceed their own filed
    counts so a filed-only projection fails on the number rather than on a
    lucky key.

    `derived` is a SEPARATE BOOLEAN, never a sixth kind value (plan Decision
    Log, one-way door #1): the two Q4s are asserted to be BOTH
    `derived is True` AND `kind == "discrete_quarter"`, which is unaskable if
    the two axes are ever collapsed.
    """
    projection = _projection_of(series, fixture_doc)
    stitched = series.stitch_quarterly_statements(_fake_filings(fixture_doc))

    for kind in _STATEMENT_KINDS:
        periods = _periods_of(projection, kind)
        filed_keys = {entry[0] for entry in stitched[kind]["periods"]}

        # --- every period declares both axes ---------------------------
        for entry in periods:
            assert entry["kind"] == period_kind(entry["key"]), (
                f"{kind} {entry['key']}: projected kind {entry['kind']!r} "
                f"disagrees with the committed classifier's "
                f"{period_kind(entry['key'])!r}"
            )
            assert isinstance(entry["derived"], bool), (
                f"{kind} {entry['key']}: derived is {entry['derived']!r}, "
                "which is not a boolean -- a consumer cannot tell a "
                "subtraction from a figure the filer stated"
            )

        # --- the counts, which no dropped period can survive ------------
        expected_total = _PROJECTED_PERIOD_COUNTS[kind]
        assert len(periods) == expected_total, (
            f"{kind} projected {len(periods)} periods, expected "
            f"{expected_total} ({len(filed_keys)} filed + "
            f"{len(_DERIVED_KEYS_BY_KIND[kind])} derived)"
        )
        assert len(periods) == len(filed_keys) + len(_DERIVED_KEYS_BY_KIND[kind]), (
            f"{kind}: the projected total no longer reconciles with the "
            "stitched input plus this task's derived quarters"
        )
        assert Counter(entry["kind"] for entry in periods) == (
            _PROJECTED_KIND_COUNTS[kind]
        ), (
            f"{kind} kind breakdown is "
            f"{dict(Counter(entry['kind'] for entry in periods))}, expected "
            f"{_PROJECTED_KIND_COUNTS[kind]}"
        )

        # --- exactly the Task E quarters are marked derived -------------
        derived_keys = sorted(e["key"] for e in periods if e["derived"])
        assert derived_keys == _DERIVED_KEYS_BY_KIND[kind], (
            f"{kind}: the periods marked derived are {derived_keys}, "
            f"expected {_DERIVED_KEYS_BY_KIND[kind]}"
        )
        for entry in periods:
            if entry["derived"]:
                assert entry["kind"] == "discrete_quarter", (
                    f"{kind} {entry['key']} is derived but classifies as "
                    f"{entry['kind']!r} -- a derived Q4 is both a discrete "
                    "quarter AND derived, on two separate axes"
                )
                assert entry["key"] not in filed_keys, (
                    f"{kind} {entry['key']} is marked derived but the filer "
                    "states that column"
                )
            else:
                assert entry["key"] in filed_keys, (
                    f"{kind} {entry['key']} is marked filed but appears in "
                    "neither the stitched statement's own periods"
                )

    # The two duration statements' totals must exceed their filed counts, or
    # the count assertions above would be green on a filed-only projection.
    for kind in ("income", "cash_flow"):
        filed = len(stitched[kind]["periods"])
        assert _PROJECTED_PERIOD_COUNTS[kind] > filed, (
            f"the expected {kind} total ({_PROJECTED_PERIOD_COUNTS[kind]}) "
            f"does not exceed its {filed} filed periods, so it proves "
            "nothing about the derived quarters being carried"
        )

    # The balance sheet's instants: all of them, and nothing derived.
    balance = _periods_of(projection, "balance_sheet")
    assert {entry["kind"] for entry in balance} == {"instant"}
    assert [entry for entry in balance if entry["derived"]] == [], (
        "the balance sheet is instant-based -- it carries no duration column "
        "to difference, so nothing in it may be marked derived"
    )


def test_a_derived_periods_kind_also_comes_from_the_classifier(
    series, periods_module, period_kind
):
    """A DERIVED period's `kind` is READ from Task C's classifier, exactly as a
    filed one's is -- never assumed from the fact that a subtraction produced
    it.

    ADDED ROUND 2 ON A QUALITY REVIEW'S MEASUREMENT. The test above pins this
    for filed periods only: on the committed fixture both derived Q4s classify
    as `discrete_quarter` anyway, so replacing `period_kind(derived["key"])`
    with the literal `"discrete_quarter"` survives that test and every other one
    in this file.

    THE INPUT IS LEGAL, NOT CONTRIVED, which is what makes this a killer rather
    than a mutation-score exercise. Both spans sit INSIDE Task C's own published
    windows -- a 100-day Q1 is the top of the `discrete_quarter` window and a
    175-day six-month column is the bottom of the first `ytd` window, both taken
    from `span_windows()` here rather than written as literals. A filer whose
    quarters run long is the whole shape. Their difference is 74 days, which
    falls in NO window, and Task C answers `unknown` by design rather than
    bucketing it (plan Decision Log, one-way door #1: an out-of-window span must
    be VISIBLE). A hardcoded `discrete_quarter` calls it a quarter.

    `"unknown"` IS ASSERTED AS A LITERAL DELIBERATELY, beside the classifier
    comparison. It is not the expectation -- the classifier is -- it is the
    guard that this constructed input still exercises the divergence. Plan Task
    G is scheduled to widen these windows for a 52/53-week calendar; if a
    widening ever swallows the 74-day gap, this line fails and says to re-pick
    the two spans rather than leaving the test quietly toothless.
    """
    windows = _role_windows_from_task_c(periods_module)
    q1_span, ytd6_span = windows["q1"][1], windows["ytd6"][0]

    _key_of, statement = _synthetic_statement(
        date(2024, 1, 1),
        {"q1": q1_span, "ytd6": ytd6_span},
        {"Revenue": {"q1": Decimal(30), "ytd6": Decimal(70)}},
    )
    projection = series.project_quarterly_series({"income": statement}, "MSFT")

    derived = [
        entry for entry in _periods_of(projection, "income") if entry["derived"]
    ]
    assert len(derived) == 1, (
        f"a {q1_span}-day Q1 and a {ytd6_span}-day six-month column should "
        f"yield exactly one derived quarter, got {derived}"
    )
    entry = derived[0]

    span = (
        date.fromisoformat(entry["end"]) - date.fromisoformat(entry["start"])
    ).days
    assert period_kind(entry["key"]) == "unknown", (
        f"the derived period {entry['key']} spans {span} days, which Task C "
        f"now classifies as {period_kind(entry['key'])!r} rather than "
        "'unknown' -- the windows moved, so this test no longer distinguishes "
        "a classifier read from a hardcoded kind; pick two spans whose "
        "difference again falls outside every window"
    )
    assert entry["kind"] == period_kind(entry["key"]), (
        f"the derived period {entry['key']} projects kind {entry['kind']!r} "
        f"while the committed classifier answers "
        f"{period_kind(entry['key'])!r} -- a derived period's kind is read, "
        "not assumed from its provenance"
    )


def test_every_periods_start_and_end_reconstruct_its_own_key(
    series, fixture_doc
):
    """`start` and `end` bound EXACTLY what the key says, so the arc's one
    invariant -- a period key's span always describes the span of its value --
    is readable without re-parsing a composite string.

    Pinned by RECONSTRUCTING the key from the two dates rather than by
    comparing them to literals: a swapped pair, an off-by-one quarter start,
    or a derived period carrying its own FY input's dates all fail, and no
    single hard-coded expectation can satisfy 41 periods at once.

    An INSTANT is a point in time, so it comes back with `start == end ==`
    its own date rather than with a null half-interval. A consumer computing
    `end - start` then gets 0 days, which is what an instant's span IS; a
    `None` would make every consumer branch on the kind before it could read
    a date at all.
    """
    projection = _projection_of(series, fixture_doc)

    seen_duration = seen_instant = 0
    for kind in _STATEMENT_KINDS:
        for entry in _periods_of(projection, kind):
            key, start, end = entry["key"], entry["start"], entry["end"]
            if key.startswith("instant_"):
                seen_instant += 1
                assert start == end == key[len("instant_"):], (
                    f"{kind} {key}: an instant projects to "
                    f"({start!r}, {end!r}), expected its own date on both "
                    "sides -- an instant spans no days"
                )
                continue
            seen_duration += 1
            assert key == f"duration_{start}_{end}", (
                f"{kind} {key} projects to start {start!r} and end {end!r}, "
                "which do not reconstruct the key -- the dates and the key "
                "disagree about what period this is"
            )
            assert start < end, (
                f"{kind} {key}: start {start!r} is not before end {end!r}"
            )

    # 19 income + 19 cash-flow duration periods and the balance sheet's 11
    # instants -- the same three totals `_PROJECTED_PERIOD_COUNTS` pins, split
    # by which branch of this test they exercise, so neither branch can go
    # unrun without failing here.
    assert (seen_duration, seen_instant) == (38, 11), (
        f"expected 38 duration and 11 instant periods across the three "
        f"statements, saw {seen_duration} and {seen_instant} -- both branches "
        "of this test must actually run"
    )

    # The derived Q4 is the sharpest case: its dates are in NEITHER of its
    # two inputs, so a projection that copied an input's dates fails here.
    for kind in ("income", "cash_flow"):
        q4 = next(
            entry for entry in _periods_of(projection, kind)
            if entry["key"] == _FY2025_DERIVED_Q4
        )
        assert (q4["start"], q4["end"]) == ("2025-04-01", "2025-06-30"), (
            f"{kind} derived Q4 spans {q4['start']}..{q4['end']}; its FY "
            "input starts 2024-07-01 and its nine-month input ends "
            "2025-03-31, so either would be a copied date rather than the "
            "quarter's own"
        )


def test_the_envelope_key_sets_are_exact_at_every_level(series, fixture_doc):
    """Plan Decision Log, ONE-WAY DOOR #2 — the projection reuses the
    existing pack envelope (`pack` / `ticker` / `fetched_at` / `_status` /
    `n_filings_used`) with `statements.<kind>.{lines, periods}`, each period
    carrying exactly `{key, kind, derived, start, end}`.

    ASSERTED AS EXACT KEY SETS, not as "contains". A one-way door is the one
    contract a later change must not widen quietly: existing consumers and
    tooling already read this envelope, and an extra field added here is a
    field they will start depending on before anyone decides it should exist.
    A missing one fails the same assertion, so the door holds in both
    directions.

    THE NAME WAS `test_the_envelope_is_the_one_the_user_ratified` UNTIL ROUND
    2, and the rename is the point of this paragraph rather than housekeeping.
    Written that way, this test asserted a SIX-key envelope while the user had
    ratified five — so the one guard against a quiet widening was itself
    ratifying the widening it existed to catch, under a name claiming an
    approval that did not exist. The user has since ratified `n_filings_used`
    (plan Decision Log, one-way door #2, widened 2026-07-31), so the assertion
    is now correct; the name still had to go, because a name that says WHO
    APPROVED cannot be checked by running it, while a name that says WHAT IS
    CHECKED can. The same instinct is already on record one screen up
    (`test_derived_q4_revenue_matches_the_recorded_cross_implementation_
    figure` declined the plan's own name for claiming more than the evidence
    supports) — applied there and not here, in the same file, by the same
    author.

    NO `label` ON A PERIOD, deliberately, and this is the one omission worth
    stating. The stitched result carries the filer's own period labels and
    they are exactly what this arc learned not to read: `discrete_quarters=
    True` produced SIX label collisions on this filer, where a cumulative and
    a discrete column shared one label. That six is MEASURED-not-repo —
    counted against the deliberately uncommitted `True`-mode capture (module
    docstring), so a later reader cannot re-derive it from anything in this
    repo; nothing here rests on the exact figure, only on many-versus-zero.
    `kind` is the machine-readable answer that replaces the labels, and adding
    the label back beside it would re-offer the collision as if it were data.

    `n_filings_used` rides through from the stitched input because it is the
    only thing in the answer that reports its own INPUT -- a caller whose
    acquire loop lost an accession needs it to tell a full span from a
    partial one, and this projection is the last layer that can carry it. It
    is ABSENT rather than fabricated when the input does not carry it (the
    doctrine `kpi_spine_view.derive_spine_as_filed` states for its own
    optional markers): a zero would claim a run that used no filings.
    """
    projection = _projection_of(series, fixture_doc, "MSFT")

    assert set(projection) == {
        "pack", "ticker", "fetched_at", "_status", "n_filings_used",
        "statements",
    }, f"the envelope's top-level keys are {sorted(projection)}"
    assert projection["pack"] == "quarterly-series"
    assert projection["ticker"] == "MSFT"
    assert projection["_status"] == "ok"
    assert projection["n_filings_used"] == fixture_doc["n_filings"] == 11

    stamped = datetime.fromisoformat(projection["fetched_at"])
    assert stamped.tzinfo is not None, (
        f"fetched_at {projection['fetched_at']!r} carries no timezone, so it "
        "cannot be compared against any other run's"
    )
    assert stamped.utcoffset() == timedelta(0), (
        f"fetched_at {projection['fetched_at']!r} is not UTC; every other "
        "pack in this repo stamps UTC"
    )

    assert set(projection["statements"]) == set(_STATEMENT_KINDS)
    for kind in _STATEMENT_KINDS:
        assert set(projection["statements"][kind]) == {"lines", "periods"}, (
            f"{kind} projects "
            f"{sorted(projection['statements'][kind])}, expected exactly "
            "lines and periods"
        )
        for entry in _periods_of(projection, kind):
            assert set(entry) == {"key", "kind", "derived", "start", "end"}, (
                f"{kind} {entry.get('key')!r} projects the fields "
                f"{sorted(entry)}, which is not the ratified period shape"
            )

    # A stitched result with no filing count reported: the key is left out,
    # never zero-filled.
    bare = series.project_quarterly_series(fixture_doc["statements"], "MSFT")
    assert "n_filings_used" not in bare, (
        "an input that never reported a filing count came back claiming "
        f"{bare.get('n_filings_used')!r} filings"
    )


def test_each_line_carries_the_derived_cells_beside_the_filed_ones(
    series, fixture_doc
):
    """A period the projection ANNOUNCES must be a period a reader can read a
    figure from. The period axis says a derived Q4 exists; the lines are
    where its numbers live, and a projection that listed the period and
    dropped its cells would be an answer shaped like a series with a hole in
    it.

    Three things are pinned, and the third is the one a values-only test
    would miss:

      1. Every stitched line survives, in order and with its filed cells
         untouched -- this is a projection of the filer's statement, not a
         rewrite of it.
      2. Every derived figure Task E produced appears under the derived
         period's own key, on the line that produced it.
      3. The COUNT of lines carrying each derived key equals the number of
         figures Task E produced for it. A cell invented for a line that
         carried only one of the two inputs is exactly the fabricated zero
         Task E refuses to emit, and it would satisfy assertion 2.

    VALUES STAY `Decimal`, as they arrive from the subtraction. Projecting
    them to text or to float belongs at the CLI boundary, which is where
    `kpi_spine_view` puts the same projection for the same reason
    (`_project_money_to_text`: `float()` re-routes exact money through the
    binary representation this module family bans, and a `default=str` dump
    would stringify a float just as happily). Plan Task H owns that boundary;
    this function must not pre-empt it, because a consumer in-process wants
    the exact number.
    """
    stitched = series.stitch_quarterly_statements(_fake_filings(fixture_doc))
    derived = series.derive_discrete_quarters(stitched)
    projection = series.project_quarterly_series(stitched, "MSFT")

    for kind in _STATEMENT_KINDS:
        lines = projection["statements"][kind]["lines"]
        rows = stitched[kind]["statement_data"]

        # 1. every filed line and cell, in order and unchanged
        assert [line.get("concept") for line in lines] == [
            row.get("concept") for row in rows
        ], f"{kind}: the projected lines are not the statement's own lines"
        for line, row in zip(lines, rows):
            for filed_key, filed_value in (row.get("values") or {}).items():
                assert line["values"][filed_key] == filed_value, (
                    f"{kind} {line.get('concept')}: the filed cell at "
                    f"{filed_key} came back {line['values'][filed_key]!r}, "
                    f"not the filer's own {filed_value!r}"
                )

        for entry in derived[kind]:
            # 2. every derived figure, on its own line, still exact.
            #
            # ADDRESSED BY THE INDEX THE SUBTRACTION ITSELF RECORDED, never by
            # a line lookup built here. An earlier version of this oracle keyed
            # the lines `{line["concept"]: line}`, which re-derived a row
            # identity of its own -- last-wins, matching Task E's tie-break by
            # coincidence and never querying Task F's opposite one. It agreed
            # with whichever side it happened to match, so the two functions
            # could disagree with the whole suite green (measured: flipping
            # `_project_lines`' `setdefault` to plain assignment left 1526
            # passing). Assertion 1 above has already pinned that `lines` is
            # `statement_data` in order, which is what makes the index mean
            # the same row on both sides.
            for (index, concept), value in entry["values"].items():
                cell = lines[index]["values"][entry["key"]]
                assert cell == value and isinstance(cell, Decimal), (
                    f"{kind} line {index} ({concept}) at {entry['key']}: "
                    f"projected {cell!r} ({type(cell).__name__}), expected the "
                    f"exact Decimal {value!r} the subtraction produced"
                )
            # 3. and NOT ONE CELL MORE
            carrying = [
                line.get("concept") for line in lines
                if entry["key"] in line["values"]
            ]
            assert len(carrying) == len(entry["values"]), (
                f"{kind} {entry['key']}: {len(carrying)} lines carry this "
                f"derived period but the subtraction produced only "
                f"{len(entry['values'])} figures -- the surplus cells were "
                "invented for lines that carried only one input"
            )

    # The measured shape, so a silent collapse of either axis is visible:
    # 19 income lines, 40 in each of the other two, and 15 / 32 derived
    # figures per Q4.
    assert [
        len(projection["statements"][kind]["lines"]) for kind in _STATEMENT_KINDS
    ] == [19, 40, 40]
    assert [len(entry["values"]) for entry in derived["income"]] == [15, 15]
    assert [len(entry["values"]) for entry in derived["cash_flow"]] == [32, 32]


def test_two_lines_sharing_a_concept_each_keep_their_own_derived_figure(series):
    """KILLS the divergence between the two functions that identify a line:
    Task E's `_difference_rows` kept the LAST row under a concept, Task F's
    `_project_lines` placed onto the FIRST. Neither is wrong on its own; the
    two disagreeing is what put one line's figure onto another line.

    MEASURED on this exact input before the fix (2026-08-07, the module run
    directly): the subtraction answered `{'us-gaap_Revenues': Decimal('1500')}`
    -- one figure where two lines earn one -- and the projection put that 1500
    on segment A, whose own quarter is 150, while segment B came back with no
    derived cell at all. The figure was real and the period key was honest, so
    nothing in the output marked it: this arc's own failure shape, at cell
    granularity.

    CONSTRUCTED, because no committed fixture can reach it -- 0 repeated
    concepts across all 99 rows of the MSFT capture, which is exactly why every
    existing test agreed with whichever tie-break it happened to match. Two
    lines under one concept is ordinary XBRL all the same: a segment breakdown,
    or a restated line filed beside the line it restates.

    The two lines are given figures that cannot be confused for each other
    (150 vs 1500) and that are not each other's multiple by any span, so a
    swap, a collapse, and a zero-fill each produce a visibly different answer.
    """
    start = date(2020, 7, 1)
    shared = "us-gaap_Revenues"
    key_of, statement = _synthetic_statement(
        start, {"q1": 91, "ytd6": 183},
        {shared: {"q1": 100, "ytd6": 250}},
    )
    statement["statement_data"][0]["label"] = "segment A"
    # CONSTRUCTED: a SECOND line under the SAME concept, carrying both input
    # columns itself, so it earns a derived quarter of its own.
    statement["statement_data"].append({
        "concept": shared,
        "label": "segment B",
        "values": {key_of["q1"]: 1000, key_of["ytd6"]: 2500},
    })

    q2_key = _derived_key(start, 91, 183)
    entry, = _derived_by_key(
        series.derive_discrete_quarters({"income": statement}), "income"
    ).values()
    assert sorted(entry["values"].values()) == [Decimal(150), Decimal(1500)], (
        "the subtraction produced "
        f"{sorted(entry['values'].values())} for two lines that each carry "
        "both input columns -- one figure per LINE is owed, and a concept-keyed "
        f"answer can only hold one of them. Entry values: {entry['values']!r}"
    )

    lines = series.project_quarterly_series(
        {"income": statement}, "TEST"
    )["statements"]["income"]["lines"]
    assert [line["values"].get(q2_key) for line in lines] == [
        Decimal(150), Decimal(1500)
    ], (
        "each line's derived Q2 must be the subtraction of ITS OWN two cells "
        "-- 250-100 for segment A, 2500-1000 for segment B. Got "
        f"{[line['values'].get(q2_key) for line in lines]} for lines "
        f"{[line.get('label') for line in lines]}"
    )


@pytest.mark.parametrize(
    "mutate,description",
    [
        (lambda rows: list(reversed(rows)), "the same lines, re-ordered"),
        (lambda rows: rows[:1], "a statement with the line index cut off it"),
    ],
)
def test_entries_paired_with_another_statement_are_refused_not_mis_filed(
    series, mutate, description
):
    """KILLS: dropping either arm of `_row_the_subtraction_read`, i.e.
    `return rows[index]` on its own.

    Addressing a line by POSITION is exact and it is BLIND. Inside
    `project_quarterly_series` the two lists are one list, so the index always
    names the right row -- but `derive_discrete_quarters` is PUBLIC, its
    entries outlive the call, and nothing in their shape says which statement
    they were derived from. Pair them with a re-ordered or shortened one and a
    positional write puts a real figure onto a line that did not produce it:
    the exact defect this addressing was adopted to remove, re-entering
    through the door the fix opened.

    So the refusal is what makes positional addressing safe to hand out, and
    it is asserted on BOTH arms, because they fail differently: a re-ordered
    statement is in range and holds the wrong line (silent without the concept
    check), a shortened one is out of range.

    CONSTRUCTED and reached through the private projection, which is the only
    seam where the mismatch is expressible -- the public entry point derives
    its own entries and can never present one.
    """
    start = date(2020, 7, 1)
    _key_of, statement = _synthetic_statement(
        start, {"q1": 91, "ytd6": 183},
        {"us-gaap_Revenue": {"q1": 10, "ytd6": 30},
         "us-gaap_CostOfRevenue": {"q1": 4, "ytd6": 9}},
    )
    entries = series.derive_discrete_quarters({"income": statement})["income"]
    assert entries, "the premise is broken: nothing was derived to mis-file"

    other = dict(statement, statement_data=mutate(statement["statement_data"]))
    with pytest.raises(ValueError) as excinfo:
        series._project_lines(other, entries)

    message = str(excinfo.value)
    assert _derived_key(start, 91, 183) in message, (
        f"the refusal does not name the derived period whose figure was about "
        f"to be mis-filed ({description}): {message}"
    )


def _statements_with(fixture_doc, *kinds: str) -> dict:
    """The captured statements with only `kinds` populated; the rest present
    but EMPTY -- the shape a stitched result takes when the stitcher returned
    a statement kind with no periods at all."""
    statements = copy.deepcopy(fixture_doc["statements"])
    for kind in _STATEMENT_KINDS:
        if kind not in kinds:
            statements[kind] = {"periods": [], "statement_data": []}
    return statements


@pytest.mark.parametrize(
    "populated,expected",
    [
        (("income", "balance_sheet", "cash_flow"), "ok"),
        (("income", "cash_flow"), "partial"),
        (("balance_sheet",), "partial"),
        ((), "failed"),
    ],
)
def test_status_reports_which_statements_actually_came_back(
    series, fixture_doc, populated, expected
):
    """`_status` is the envelope's own verdict on itself, and it exists
    because an EMPTY statement projects to exactly the same shape as a full
    one: three kinds, each with `lines` and `periods`, all well-formed. That
    is the silent-truncation failure this module family already guards
    against from the other direction (`stitch_quarterly_statements` refuses an
    empty filing list rather than returning a fully-shaped nothing).

    Three values, matching what the pack envelope already means elsewhere in
    this repo (`pack_us.py` builds `ok` / `partial` / `failed` from its own
    per-item counts): every kind answered, some did, none did.

    ALL FOUR ROWS ARE ASSERTED, including `failed`, because a status that
    only ever reads `ok` in the tests is a field nobody has checked can say
    anything else.
    """
    projection = series.project_quarterly_series(
        _statements_with(fixture_doc, *populated), "MSFT"
    )

    assert projection["_status"] == expected, (
        f"with {list(populated) or 'no'} statement(s) populated the "
        f"projection reports {projection['_status']!r}, expected {expected!r}"
    )
    # Whatever the status, the SHAPE is unchanged -- which is precisely why
    # the status has to carry the news.
    assert set(projection["statements"]) == set(_STATEMENT_KINDS)
    for kind in _STATEMENT_KINDS:
        assert set(projection["statements"][kind]) == {"lines", "periods"}


def test_status_counts_periods_not_lines(series, fixture_doc):
    """`_status` reads the PERIOD axis. A statement kind that came back with
    rows but with no period to read them under has answered NOTHING.

    ADDED ROUND 2 ON A QUALITY REVIEW'S MEASUREMENT. The parametrized test
    above cannot see which field is counted: its `_statements_with` helper
    empties `periods` and `statement_data` together, so a `_status` that
    counted `lines` instead agrees with it on all four rows. The shape that
    separates them is rows-without-periods, which no captured statement has --
    hence constructed here, from the real capture's own rows so the lines are
    genuinely non-empty.

    WITH ALL THREE KINDS IN THAT SHAPE the two readings give OPPOSITE verdicts:
    every kind has lines, so a lines-counting status reports `ok` -- a payload
    announcing a complete answer whose every period axis is empty. The correct
    answer is `failed`. This is the same silent-truncation family the envelope's
    `_status` exists for: a full answer and an empty one are the same shape, and
    a status field that reads the wrong axis makes it worse than none, because
    it says so out loud.
    """
    statements = {
        kind: {
            "periods": [],
            "statement_data": copy.deepcopy(
                fixture_doc["statements"][kind]["statement_data"]
            ),
        }
        for kind in _STATEMENT_KINDS
    }

    projection = series.project_quarterly_series(statements, "MSFT")

    for kind in _STATEMENT_KINDS:
        view = projection["statements"][kind]
        assert view["lines"], (
            f"{kind} projected no lines, so this input no longer distinguishes "
            "a period count from a line count"
        )
        assert view["periods"] == [], (
            f"{kind} projected {len(view['periods'])} periods from a statement "
            "that carries none"
        )
    assert projection["_status"] == "failed", (
        "three statements carrying rows but not one readable period report "
        f"{projection['_status']!r} -- a status counting lines rather than "
        "periods calls that a complete answer"
    )


def test_projection_does_not_mutate_the_statements_it_is_given(series):
    """The stitched statements are the caller's. A projection that wrote its
    derived cells into the input rows would be the arc's own defect one layer
    up -- a derivation filed in place, over the columns it read.

    THE BASELINE IS READ FRESH FROM THE FIXTURE FILE, for the reason
    docs/loom/memory/a-no-mutation-test-cannot-baseline-off-shared-fixture-state.md
    records: `fixture_doc` is MODULE-SCOPED and every projection test above
    has already run over its rows -- and this suite's `_FakeXBRLS` hands
    those rows back BY REFERENCE, so a projection that aliased them would
    have written its cells into that shared dict before this test could
    snapshot it. A `copy.deepcopy(fixture_doc[...])` baseline inherits the
    same pollution. Only an input the module has provably never seen is a
    trustworthy baseline.

    MEASURED, not argued: with the projection sharing the caller's row dicts
    rather than copying them, this test fails and names the derived Q4 key it
    wrote into the input's own `values`.
    """
    pristine = json.loads(FIXTURE_PATH.read_text())["statements"]
    before = copy.deepcopy(pristine)

    projection = series.project_quarterly_series(pristine, "MSFT")

    assert pristine == before, (
        "project_quarterly_series mutated the statements it was handed"
    )
    # And the answer is not a VIEW onto them either: editing what came back
    # must not reach the input.
    projection["statements"]["income"]["lines"][0]["values"]["probe"] = 1
    assert pristine == before, (
        "editing the projection reached back into the caller's statements, "
        "so the two share row objects"
    )


@pytest.mark.parametrize("reverse_input", [False, True])
def test_periods_come_back_newest_first_with_each_derived_quarter_in_place(
    series, fixture_doc, reverse_input
):
    """Periods are ordered END DESCENDING, then SHORTEST SPAN FIRST -- one
    rule for filed and derived alike, so a derived quarter sits with the
    periods it belongs among rather than in an appendix at the end.

    THE RULE IS NOT INVENTED HERE: it is what the stitcher itself returns.
    Measured on the committed capture, sorting the filed periods this way
    reproduces their stitched order EXACTLY, in all three statements -- so
    the projection re-orders nothing a reader had already learned to expect,
    and part 1 below asserts that against the untouched input rather than
    against a literal ordering.

    Where the derived Q4 lands is the consequence that matters: it ends on
    the same day as its own FY column and spans 90 days rather than 364, so
    it comes immediately BEFORE it -- next to the quarters it is comparable
    with. Appending derived periods after the filed ones would leave every
    other assertion in this file green.

    Run over the stitched input BOTH WAYS. A projection that merely preserved
    input order would pass the forward case and fail reversed; the ordering
    has to be the projection's own answer, not an inherited one.
    """
    stitched = series.stitch_quarterly_statements(_fake_filings(fixture_doc))
    if reverse_input:
        for kind in _STATEMENT_KINDS:
            stitched[kind]["periods"] = list(reversed(stitched[kind]["periods"]))
    projection = series.project_quarterly_series(stitched, "MSFT")

    for kind in _STATEMENT_KINDS:
        keys = [entry["key"] for entry in _periods_of(projection, kind)]
        ends = [entry["end"] for entry in _periods_of(projection, kind)]
        spans = [
            (date.fromisoformat(entry["end"]) - date.fromisoformat(entry["start"])).days
            for entry in _periods_of(projection, kind)
        ]
        ordering = list(zip([-date.fromisoformat(e).toordinal() for e in ends], spans))
        assert ordering == sorted(ordering), (
            f"{kind}: the projected periods are not newest-end-first, "
            f"shortest-span-first: {keys}"
        )

        # 1. For the FILED periods alone, that ordering IS the stitcher's own.
        filed_projected = [
            entry["key"] for entry in _periods_of(projection, kind)
            if not entry["derived"]
        ]
        stitched_order = [
            entry[0] for entry in fixture_doc["statements"][kind]["periods"]
        ]
        assert filed_projected == stitched_order, (
            f"{kind}: the filed periods came back in a different order than "
            f"the stitcher returned them.\n  got: {filed_projected}\n  "
            f"stitched: {stitched_order}"
        )

    # 2. Each derived Q4 immediately precedes the FY column it was
    # subtracted out of -- same end date, one quarter instead of a year.
    for kind in ("income", "cash_flow"):
        keys = [entry["key"] for entry in _periods_of(projection, kind)]
        assert keys.index(_FY2025_DERIVED_Q4) + 1 == keys.index(_FY2025_FY), (
            f"{kind}: the derived Q4 {_FY2025_DERIVED_Q4} is at position "
            f"{keys.index(_FY2025_DERIVED_Q4)} and its own FY column at "
            f"{keys.index(_FY2025_FY)}; they end on the same day, so the "
            "quarter belongs immediately before the year"
        )


def test_a_period_key_with_no_readable_dates_still_projects_and_sorts_last(
    series
):
    """A period key this module cannot read as dates is still PROJECTED --
    with `kind: "unknown"` and no dates -- and sorts to the end.

    Skipping it would be the worse answer: the column exists in the filer's
    statement and its cells are in the lines, so dropping it from the period
    axis would leave figures no period accounts for. Task C already answers
    `unknown` rather than bucketing such a key, and this is the same posture
    one layer up -- VISIBLE, never rounded to a neighbour and never silently
    gone.

    It sorts LAST because there is nothing to sort it by: an ordering rule
    reading dates it does not have would have to invent them.

    CONSTRUCTED: every period key in the committed capture is well-formed, so
    nothing captured exercises this at all.
    """
    start = date(2023, 7, 1)
    key_of, statement = _synthetic_statement(
        start,
        {"q1": 91, "ytd6": 183, "ytd9": 273, "fy": 364},
        {"us-gaap_Revenue": {"q1": 10, "ytd6": 30, "ytd9": 60, "fy": 100}},
    )
    statement["periods"].append(["duration_2024-07-01_2025-06-31", "no such day"])

    projection = series.project_quarterly_series({"income": statement}, "MSFT")
    entries = _periods_of(projection, "income")

    unreadable = entries[-1]
    assert unreadable["key"] == "duration_2024-07-01_2025-06-31", (
        f"the unreadable key did not sort last: "
        f"{[entry['key'] for entry in entries]}"
    )
    assert (unreadable["kind"], unreadable["start"], unreadable["end"]) == (
        "unknown", None, None,
    ), f"the unreadable key projected as {unreadable}"
    # And it cost the statement nothing else: the four filed columns and the
    # three derivable quarters are all still there.
    assert len(entries) == len(key_of) + 3 + 1


def test_the_ticker_is_normalised_and_a_missing_one_is_refused(
    series, fixture_doc
):
    """The envelope's `ticker` is the projection's only statement of WHOSE
    numbers these are, so it is normalised on the way in and refused when it
    is not there.

    NORMALISED to upper case, because every other pack in this repo stamps it
    that way (`pack_us.py`'s own envelope does `ticker.upper()`), and a
    consumer keying two runs of the same filer by this field would otherwise
    hold `msft` and `MSFT` as two companies.

    REFUSED when blank -- loudly, not by emitting an empty string. This is
    the same asymmetry `stitch_quarterly_statements` already draws for an
    empty filing list: a fully-shaped payload attributed to nobody is
    indistinguishable from a real one, and the whole point of this envelope
    is that a reader can tell what they are looking at. Whitespace counts as
    blank; a ticker of spaces is not a filer.
    """
    projection = series.project_quarterly_series(fixture_doc["statements"], "msft")
    assert projection["ticker"] == "MSFT", (
        f"a lower-case ticker projected as {projection['ticker']!r}, so two "
        "runs of one filer would key as two companies"
    )

    for blank in ("", "   "):
        with pytest.raises(ValueError):
            series.project_quarterly_series(fixture_doc["statements"], blank)
