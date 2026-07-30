"""Tests for analysis-kpi/scripts/kpi_us_quarterly_series.py — stitch a
filer's own ALREADY-ACQUIRED filing list into the three statements via
`edgartools`' own multi-filing stitcher (plan Task D,
docs/loom/plans/2026-07-28-us-quarterly-statement-series.md).

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

No `@req` tags: this dispatch carries no registered loom-spec REQ-ids (the
work is tracked by named plan Task D), so `@req` is omitted per the
implementer contract.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import pytest
from conftest import SKILLS

SERIES_SCRIPT = SKILLS / "analysis-kpi" / "scripts" / "kpi_us_quarterly_series.py"
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


def _values_of(statement: dict, concept: str) -> dict:
    for row in statement["statement_data"]:
        if row.get("concept") == concept:
            return row["values"]
    raise AssertionError(f"concept {concept!r} absent from the statement")


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
