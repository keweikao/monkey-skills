#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests==2.33.1", "edgartools==5.42.0"]
# ///
"""Regenerate `us_quarterly_stitched_msft.json` — the live capture that lets
plan Task D's stitching suite (and Task E's discrete-quarter derivation suite,
which reuses this SAME fixture) run OFFLINE
(docs/loom/plans/2026-07-28-us-quarterly-statement-series.md).

WHAT IT ANSWERS. Task D wraps two `edgartools` calls -- `XBRLS.from_filings`
and `XBRLS.get_statement` -- around Task A's filing list
(`sec_edgar_client.assemble_quarterly_filing_span`). This captures what the
DEPENDENCY itself returns for a real, generously-large `max_periods` (never
truncated), for all three statement kinds, so:

  * Task D's own test can build a duck-typed stand-in for `XBRLS` around this
    fixture whose `get_statement(statement_type, max_periods=...)` replicates
    the real library's documented truncation (`periods[:max_periods]`,
    `core.py:300`/`371`/`374`) -- so the test is sensitive to what `max_periods`
    OUR module actually derives and passes, not just to what this fixture
    contains.
  * Task E's derivation test can read MSFT FY2025's actual cumulative figures
    from the income and cash-flow `statement_data`, offline, and subtract them.
    For income, FY minus Q3-YTD reproduces the value this arc's brief already
    live-verified against a second, independent implementation
    (`edgar/ttm/calculator.py`): 76,441,000,000.

WHY `discrete_quarters=False` -- THE POINT OF THIS CAPTURE'S 2026-07-30
RE-RUN. Requested with `True`, the dependency computes discrete cash-flow
quarters correctly but files each one under the CUMULATIVE period key whose
end date it shares, so a key's span stops describing its value: a 364-day key
held one quarter, and an 89-day and a 273-day key held the same number. With
`False` the cash-flow statement comes back as filed -- every duration key's
value spans exactly what the key says -- and this arc does its own
subtraction in Task E instead. Measured on this filer immediately before the
re-capture, same 11 filings, both flags in one process:

    key (cash flow, NetCashProvidedByUsedInOperatingActivities)
                                     span   discrete_quarters=True    =False
    duration_2024-07-01_2024-09-30    91d          34.180B           34.180B
    duration_2024-07-01_2024-12-31   183d          22.291B           56.471B
    duration_2024-07-01_2025-03-31   273d          37.044B           93.515B
    duration_2024-07-01_2025-06-30   364d          42.647B          136.162B

Under `False` that column set is monotonic in span, as a cumulative series
must be; under `True` it is not (91d > 183d). The flag is gated to
`CashFlowStatement` inside the dependency, and that was CONFIRMED here rather
than assumed: in the same two-flag run the income statement's values were
byte-identical between flags, and all three kinds returned identical period
lists. See plan §RESOLVED FINDING 2026-07-30 for the decision this
implements.

FILER + SPAN -- MSFT, CIK 789019, `years=3`
(`assemble_quarterly_filing_span(789019, years=3)`). The exact filings are
recorded per-run in `_capture.filings` (accession, form, filing date) --
NOT restated here, because `years=3` is a window relative to the RUN DATE and
therefore this list is not stable across re-captures. It already moved once:
the 2026-07-29 capture got 12 filings, and this 2026-07-30 re-run got 11,
having rolled past a 10-K filed 2023-07-27. Any assertion pinning a literal
period count is pinning THIS run; when a re-capture changes the count, the
count is the thing to update, and `_capture.filings` is how you see what
moved. Chosen over the full uncapped history (~77 filings, 20-37 minutes per
the brief) because both this task's truncation assertion and Task E's FY2025
figures only need span through FY2025 (10-K filed 2025-07-30) plus its Q3-YTD
10-Q (filed 2025-04-30) -- both are inside this window with room either side.
The filing count is also comfortably over the library's `max_periods=8`
default, which is the exact defect this fixture exists to make visible
offline.

WHAT'S STORED, PER STATEMENT KIND (`income` / `balance_sheet` / `cash_flow`):
`get_statement`'s own `{"periods": [...], "statement_data": [...]}` shape,
UNTRIMMED for `income` (Task E needs the real revenue lines) and for
`cash_flow` (Task D's own duration-span assertion reads every period's key,
and a trimmed period list would defeat the point of proving no truncation
happened). `balance_sheet`'s `statement_data` IS trimmed -- see
`_trim_balance_sheet` -- because no task reads its line values, only that the
kind returns at all; its `periods` list is kept in full for the same
not-truncated check as the other two.

BALANCE-SHEET ROW ORDER IS NOT STABLE ACROSS CAPTURES. Two captures of the
same 11 filings, minutes apart, returned `balance_sheet.statement_data` rows
in DIFFERENT orders -- the same 40 concepts throughout (a permutation, no
row gained or lost), with sibling rows such as `AssetsCurrent` and
`OtherAssetsCurrent` swapping positions. NEITHER FLAG THIS SCRIPT PASSES CAN
CAUSE IT, and that is documented and measured rather than inferred.
`discrete_quarters` is gated to `CashFlowStatement` in its own docstring
("If True and statement_type is CashFlowStatement", edgartools 5.42.0
`edgar/xbrl/stitching/xbrls.py:165`) and in the code (`core.py:181`:
`if discrete_quarters and statement_type == 'CashFlowStatement'`), and what
it rewrites is DURATION periods -- of which this captured balance sheet has
ZERO: measured over the committed fixture's own `balance_sheet.periods`, all
11 are `instant_*`. `include_quarterly` states its own no-op outright --
"Has no effect for BalanceSheet" (`xbrls.py:171`; that sentence documents
`include_quarterly`, not `discrete_quarters`). What is left is run-to-run
instability in the dependency's ordering. `income` and
`cash_flow` row order did NOT move in the same comparison. Consequence for
anyone writing a test against this fixture: address balance-sheet rows by
CONCEPT, never by index, and do not read a re-capture's reordered
balance-sheet diff as a regression.

WHAT IS DELIBERATELY NOT CAPTURED: `max_periods` itself is NOT a stored
field -- it is call-site behavior of the dependency, not a property of the
filing, and freezing it here would invite exactly the "committed verdict
from a live function" hazard `capture_us_statement_reconstruction.py`
documents. What's captured is the FULL untruncated periods that exist for
this filer at this span, at a capture-time `max_periods` generous enough
that it did not truncate (asserted below, not assumed).

NETWORK. Hits `www.sec.gov` live through the repo's shared acquirer
`sec_edgar_client._acquire_raw_filing`, then `edgartools`' own
`XBRLS.from_filings` (which itself calls `XBRL.from_filing` per filing --
this is the ONE place in this arc that parses filing documents beyond the
raw acquisition boundary). NOT part of the offline suite -- this is not a
`test_*` module and pytest never collects it. Re-run by hand when the
captured shape is questioned:

    PYTHONDONTWRITEBYTECODE=1 uv run --quiet --with 'edgartools==5.42.0' \\
      --with requests==2.33.1 python \\
      investing-toolkit/tests/data/fixtures/capture_us_quarterly_stitched.py \\
      > investing-toolkit/tests/data/fixtures/us_quarterly_stitched_msft.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parents[4]
_DATA_MARKETS_SCRIPTS = _REPO_ROOT / "investing-toolkit" / "skills" / "data-markets" / "scripts"
sys.path.insert(0, str(_DATA_MARKETS_SCRIPTS))
import sec_edgar_client as sec  # noqa: E402

sec._QUIET = True

TICKER = "MSFT"
CIK = 789019
YEARS = 3

# Generous headroom for THIS capture-time call only -- not the production
# module's derivation (that lives in kpi_us_quarterly_series.py and is
# derived from the filing count, never a constant). This script's whole job
# is to prove what the FULL, untruncated period set looks like, so a large
# fixed number is correct here and would be wrong there.
_CAPTURE_MAX_PERIODS = 200

_STATEMENT_TYPES = {
    "income": "IncomeStatement",
    "balance_sheet": "BalanceSheet",
    "cash_flow": "CashFlowStatement",
}


def _trim_balance_sheet(statement_data: list[dict]) -> list[dict]:
    """Drop every line's `values`/`decimals` payload, keeping label/concept/
    level/is_abstract/is_total -- no task reads a balance-sheet VALUE from
    this fixture, only that the kind returns rows at all, and the full
    per-period value maps are the bulk of this statement's size."""
    trimmed = []
    for item in statement_data:
        copy = dict(item)
        copy["values"] = {}
        copy["decimals"] = {}
        copy["preferred_signs"] = {}
        trimmed.append(copy)
    return trimmed


def main() -> None:
    filing_rows = sec.assemble_quarterly_filing_span(CIK, years=YEARS)
    accessions = [row["accessionNumber"] for row in filing_rows]
    # Per-filing provenance. `years=3` is relative to the RUN DATE, so the
    # span this script returns moves over time (see the module docstring); this
    # is what makes a changed period count diagnosable instead of mysterious.
    filings_provenance = [
        {
            "accession": row["accessionNumber"],
            "form": row.get("form"),
            "filing_date": row.get("filingDate"),
        }
        for row in filing_rows
    ]

    filings = []
    for accession in accessions:
        filing = sec._acquire_raw_filing(accession)
        if isinstance(filing, dict):
            raise RuntimeError(f"capture: accession {accession!r} failed: {filing}")
        filings.append(filing)

    from edgar.xbrl.stitching.xbrls import XBRLS

    xbrls = XBRLS.from_filings(filings)

    statements = {}
    for kind, statement_type in _STATEMENT_TYPES.items():
        result = xbrls.get_statement(
            statement_type,
            max_periods=_CAPTURE_MAX_PERIODS,
            # `False`, so a period key's span describes its value in every
            # statement -- see the module docstring's "WHY discrete_quarters=
            # False" for the measurement, and keep this in step with the
            # production module's own call.
            discrete_quarters=False,
            include_quarterly=True,
        )
        n_periods = len(result["periods"])
        if n_periods >= _CAPTURE_MAX_PERIODS:
            # The capture-time headroom did not prove itself generous enough
            # -- fail loud rather than silently ship a fixture that is ITSELF
            # truncated, the exact defect this arc exists to prevent.
            raise RuntimeError(
                f"capture: {kind} returned {n_periods} periods at "
                f"max_periods={_CAPTURE_MAX_PERIODS} -- headroom insufficient, "
                "raise _CAPTURE_MAX_PERIODS and re-run"
            )
        statement_data = result["statement_data"]
        if kind == "balance_sheet":
            statement_data = _trim_balance_sheet(statement_data)
        statements[kind] = {
            "periods": result["periods"],
            "statement_data": statement_data,
        }

    doc = {
        "_capture": {
            "what": (
                "Live capture of XBRLS.from_filings(...).get_statement(...) "
                "for MSFT's three statements, discrete_quarters=False, "
                "include_quarterly=True, grounding plan Task D "
                "(docs/loom/plans/2026-07-28-us-quarterly-statement-series.md) "
                "and reused by Task E."
            ),
            "captured_at": "2026-07-30",
            "sdk": "edgartools==5.42.0",
            "ticker": TICKER,
            "cik": CIK,
            "years_span": YEARS,
            "n_filings": len(filings),
            "accessions": accessions,
            "filings": filings_provenance,
            "span_is_run_date_relative": (
                "years=3 resolves against the run date, so this filing set "
                "moves over time -- the 2026-07-29 capture had 12 filings, "
                "this one has 11 (rolled past a 10-K filed 2023-07-27). A "
                "changed period count in the offline suite means re-capture "
                "drift, not a code regression; diff `filings` to see it."
            ),
            "discrete_quarters": (
                "False. True computes discrete cash-flow quarters but files "
                "them under cumulative period keys, so a key's span stops "
                "describing its value; the subtraction is done in Task E "
                "instead. Measurement in the capture script's docstring."
            ),
            "capture_max_periods": _CAPTURE_MAX_PERIODS,
            "regenerate": (
                "investing-toolkit/tests/data/fixtures/"
                "capture_us_quarterly_stitched.py"
            ),
            "balance_sheet_trimmed": (
                "statement_data values/decimals/preferred_signs are emptied "
                "-- no task reads a balance-sheet line VALUE from this "
                "fixture, only that the kind returns rows. periods is kept "
                "in full, same not-truncated proof as the other two kinds."
            ),
        },
        "n_filings": len(filings),
        "statements": statements,
    }
    print(json.dumps(doc, indent=1, default=str))


if __name__ == "__main__":
    main()
