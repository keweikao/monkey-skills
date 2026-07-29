#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests==2.33.1", "edgartools==5.42.0"]
# ///
"""Regenerate `us_oldest_filing_rows.json` -- the live capture that lets plan
Task I's oldest-filing suite run OFFLINE
(docs/loom/plans/2026-07-28-us-quarterly-statement-series.md, Task I).

WHAT IT ANSWERS. The quarterly series now reaches back to the start of the
XBRL mandate (~2009-2011); only 2014+ has ever been verified (brief "Current
State Evidence" -- KO's oldest 10-Q AT THE TIME, filed 2014, and a 2021
filing, both parsed 3/3 kinds). `assemble_quarterly_filing_span(CIK,
years=None)` (plan Task A, landed) returns KO's WHOLE 10-Q/10-K history --
127 filings, 97 of them 10-Qs, reaching back to 1994 -- so this capture asks
the question at the ACTUAL floor rather than the one assumed from the earlier
probe.

TWO DATA POINTS, BOTH LIVE, BOTH NEEDED -- the genuinely oldest 10-Q the span
yields is pre-XBRL and cannot be parsed at all, so a single "capture the
oldest, parse it" script would only ever exercise the failure branch. This
script therefore captures:

  1. THE GENUINELY OLDEST 10-Q (`0000021344-94-000012`, filed 1994-05-06,
     period 1994-03-31) -- `sec_edgar_client._acquire_raw_filing` on this
     accession returns a `{"error": ..., "error_class": "resolution"}` slot,
     never a silent None: EDGAR's own full-text/accession index does not
     resolve it via edgartools 5.42.0. This is the "fails loudly" branch the
     plan's acceptance names, captured as it actually happens rather than
     synthesised.

  2. THE EARLIEST 10-Q THAT ACTUALLY PARSES. Found by sampling forward from
     1994 rather than an exhaustive scan of all 97 filings -- a handful of
     fetches was enough once a filing with XBRL and one without straddled the
     known mandate date, so scanning the remaining quarters would only
     re-confirm what the boundary pair already pins (no rate-limit guard or
     fetch budget is imposed by the task; this is a sampling-efficiency
     choice on its own merits): 1998, 2000 and 2008 10-Qs all resolve but
     carry no XBRL (`filing.xbrl()` is `None`) -- every one of them predates
     the mandate date below. The 2009-04-30 filing (period 2009-03-31) also
     carries no XBRL. The 2009-07-30 filing (period 2009-07-03) is the first to carry
     XBRL AND parse to all three statement kinds -- which lines up with the
     SEC's own phased mandate: Phase 1 was large accelerated filers using US
     GAAP with worldwide public float over $5 billion (~500 companies),
     effective for periods ending on or after 2009-06-15 (17 CFR 232.405,
     Release 33-9002); the second year covered "All other domestic and
     foreign large accelerated filers using U.S. GAAP" (2010-06-15) and the
     third "All remaining filers using U.S. GAAP, including smaller
     reporting companies" plus all foreign private issuers preparing their
     financial statements in accordance with IFRS as issued by the IASB
     (2011-06-15). THOSE TWO QUOTED STRINGS ARE VERBATIM from 74 FR 6776,
     string-matched on 2026-07-30 against govinfo's FR-2009-02-10 text (one
     hit each, including the sentence-initial capital); the IFRS clause
     paraphrases the remainder of the same sentence, and the "Phase 1/2/3"
     shorthand here is this docstring's, not the source's -- 74 FR 6776
     never uses it. The US-GAAP qualifier is load-bearing: a large
     accelerated filer reporting under IFRS sat in the third year, not the
     second. KO clears the $5B float threshold and reports under US GAAP, so
     Phase 1's date is the one that applies to it.
     This is not a coincidence this script had to search hard for; it is
     Phase 1's own effective date. Earlier quarters are not sampled further
     once the accepted-vs-rejected pair straddles that date -- and a
     voluntary XBRL filing program predates the mandate, so a filer COULD in
     principle carry XBRL earlier than its own phase date. Rather than
     speculate about that, this script records an INDEX SCAN, exhaustive
     rather than sampled (step 3 below, `_scan_isxbrl_index`): across EVERY
     row of KO's submissions index -- all 3,287 rows at the capture date,
     every form, not just 10-Qs -- no row filed before 2009-07-30 carries
     `isXBRL=1` (900 such rows, 46 of them 10-Qs), and exactly one row filed
     ON that date does. That is the flag REPORTED AS THE INDEX CARRIES IT,
     not a reading of what it means: it is demonstrably not a plain "this
     filing has XBRL" bit, since a later ORIGINAL 10-Q (filed 2009-10-29)
     carries `isXBRL=0` while the 10-Q/A filed that same day carries
     `isXBRL=1` -- that pair is pinned in
     `FLAG_SEMANTICS_COUNTEREXAMPLE_ACCESSIONS` and written to the fixture, so
     the point is checkable there. The `filing.xbrl()` results remain what
     they are -- a
     five-filing sample, pinned by accession in
     `SAMPLED_PRE_MANDATE_ACCESSIONS` and probed live so the fixture records
     each one's flag and outcome instead of four bare years in a sentence.

KO, CIK 21344 -- same filer as this arc's other fixtures
(`ko_fy2017_income_statement_as_filed.json`,
`us_statement_reconstruction_2026-07-26.json`), chosen for continuity.

NETWORK. Everything goes through the repo's shared boundaries: one
`fetch_submissions` (via `assemble_quarterly_filing_span`, then re-read warm
from the same cache for the index scan), plus
`sec_edgar_client._acquire_raw_filing` + `Filing.xbrl()` (the same boundary
`capture_us_statement_reconstruction.py` uses) for SIX accessions -- the
oldest 10-Q, the earliest-parsing one, and the four resolvable pre-mandate
samples. The oldest one is acquired once and its result reused by the sample
step rather than re-requested. The index scan and the same-day counterexample
pair are read off the already-fetched submissions payload and cost no request.
NOT part of the offline suite -- this is not a `test_*` module and pytest
never collects it.

Re-run by hand when the captured shape is questioned:

    PYTHONDONTWRITEBYTECODE=1 uv run --quiet --with 'edgartools==5.42.0' \\
      --with requests==2.33.1 python \\
      investing-toolkit/tests/data/fixtures/capture_us_oldest_filing.py \\
      > investing-toolkit/tests/data/fixtures/us_oldest_filing_rows.json
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parents[4]
_DATA_MARKETS_SCRIPTS = _REPO_ROOT / "investing-toolkit" / "skills" / "data-markets" / "scripts"
_ANALYSIS_KPI_SCRIPTS = _REPO_ROOT / "investing-toolkit" / "skills" / "analysis-kpi" / "scripts"
sys.path.insert(0, str(_DATA_MARKETS_SCRIPTS))
sys.path.insert(0, str(_ANALYSIS_KPI_SCRIPTS))
import sec_edgar_client as sec  # noqa: E402
from kpi_us_statement_shape import statement_kind, statements_for  # noqa: E402

sec._QUIET = True

CIK = 21344  # The Coca-Cola Company (KO)
TICKER = "KO"

# Provenance the fixture carries so a reader can judge its age, same two
# fields and same formats as the sibling captures
# (`us_quarterly_stitched_msft.json`, `us_statement_reconstruction_*.json`):
# the date this script was last actually RUN against the live SEC, and the
# pinned SDK from the PEP 723 header above that produced those rows. Bump
# CAPTURED_AT when you re-run.
CAPTURED_AT = "2026-07-30"
SDK = "edgartools==5.42.0"

# Found by the forward sample described in the module docstring.
EARLIEST_PARSING_ACCESSION = "0001047469-09-007013"  # filed 2009-07-30, period 2009-07-03

# The forward sample the module docstring describes, PINNED to accessions so
# the fixture records exactly which filings were probed rather than four bare
# years. Oldest first; the first entry is the genuinely oldest 10-Q, which
# fails acquisition, so it never reaches `filing.xbrl()`. Filing dates are NOT
# hardcoded here -- they are read back from the submissions index alongside
# each accession's `isXBRL` flag, so both come from the source.
SAMPLED_PRE_MANDATE_ACCESSIONS = (
    "0000021344-94-000012",  # 1994 -- the oldest 10-Q in the span
    "0000021344-98-000007",  # 1998
    "0000021344-00-000014",  # 2000
    "0001047469-08-005195",  # 2008
    "0001047469-09-004778",  # 2009, the quarter BEFORE the earliest parsing one
)

# Why the scan below reports `isXBRL` without interpreting it: these two rows
# share a filing date, yet the ORIGINAL 10-Q carries `isXBRL=0` and the
# amendment carries `isXBRL=1` -- so the flag is not a plain "this filing has
# XBRL" bit. Recorded from the index (no request of its own) so the claim is
# checkable in the fixture instead of asserted from memory.
FLAG_SEMANTICS_COUNTEREXAMPLE_ACCESSIONS = (
    "0001047469-09-009286",  # 10-Q  filed 2009-10-29
    "0001047469-09-009321",  # 10-Q/A filed 2009-10-29
)


def _capture_roles_and_rows(xbrl) -> list[dict]:
    captured = []
    for role in (str(r) for r in xbrl.presentation_roles):
        if statement_kind(role) is None:
            continue
        captured.append({"role": role, "rows": list(xbrl.get_statement(role))})
    return captured


def _index_rows(recent: dict) -> list[dict]:
    """Flatten the submissions index's parallel arrays into one row per filing,
    carrying the `isXBRL` flag EDGAR already ships with every row."""
    n = len(recent.get("form", []))
    flags = recent.get("isXBRL", [])
    assert len(flags) == n, (
        f"submissions index has {n} rows but {len(flags)} isXBRL flags -- a "
        "per-row flag cannot be read off a ragged column, so the exhaustive "
        "scan below would be unsound"
    )
    return [
        {
            "accession": recent["accessionNumber"][i],
            "form": recent["form"][i],
            "filing_date": recent["filingDate"][i],
            "report_date": recent["reportDate"][i],
            "isXBRL": flags[i],
        }
        for i in range(n)
    ]


def _scan_isxbrl_index(rows: list[dict]) -> dict:
    """Scan EVERY row of the index -- every form, not just 10-Qs -- for the
    `isXBRL` flag, and count how many rows filed before the earliest-parsing
    filing's own date carry it.

    The floor date comes from `EARLIEST_PARSING_ACCESSION`'s own index row, NOT
    from the minimum flagged row, so `rows_filed_before_that_date_with_isxbrl_1`
    is a real measurement rather than a tautology: a flagged 1997 row would
    show up in it. `earliest_isxbrl_1` is then derived independently, and the
    offline suite cross-checks that the two agree.

    Nothing here interprets what the flag MEANS -- it is reported as the index
    carries it.
    """
    by_accession = {row["accession"]: row for row in rows}
    floor_row = by_accession.get(EARLIEST_PARSING_ACCESSION)
    assert floor_row is not None, (
        f"{EARLIEST_PARSING_ACCESSION} is not in the submissions index at all"
    )
    floor_date = floor_row["filing_date"]

    flagged = sorted(
        (row for row in rows if row["isXBRL"] == 1),
        key=lambda row: (row["filing_date"] or "", row["accession"] or ""),
    )
    assert flagged, "no row in the submissions index carries isXBRL=1"

    before = [row for row in rows if (row["filing_date"] or "") < floor_date]
    tenq_before = [row for row in before if row["form"] == "10-Q"]
    return {
        "what": (
            "Exhaustive scan of every row in KO's EDGAR submissions index for "
            "the isXBRL flag the index already ships per row. Reported as "
            "carried; this scan does not interpret what the flag means."
        ),
        "floor_date": floor_date,
        "index_rows_scanned_all_forms": len(rows),
        "rows_with_isxbrl_1": len(flagged),
        "earliest_isxbrl_1": flagged[0],
        "isxbrl_1_rows_on_that_date": sum(
            1 for row in flagged if row["filing_date"] == floor_date
        ),
        "rows_filed_before_that_date": len(before),
        "rows_filed_before_that_date_with_isxbrl_1": sum(
            1 for row in before if row["isXBRL"] == 1
        ),
        "tenq_filed_before_that_date": len(tenq_before),
        "tenq_filed_before_that_date_with_isxbrl_1": sum(
            1 for row in tenq_before if row["isXBRL"] == 1
        ),
    }


def _probe_sample(row: dict, already_acquired=None) -> dict:
    """Record one sampled filing's index flag AND what `filing.xbrl()` returned
    for it, so the docstring's five-filing sample cites fixture rows instead of
    a claim only a live re-run could check.

    `already_acquired` reuses the acquisition step 1 has already performed for
    the oldest filing rather than spending a second request on it.
    """
    filing = (
        already_acquired
        if already_acquired is not None
        else sec._acquire_raw_filing(row["accession"])
    )
    probed = {
        "accession": row["accession"],
        "form": row["form"],
        "filing_date": row["filing_date"],
        "report_date": row["report_date"],
        "isXBRL": row["isXBRL"],
    }
    if isinstance(filing, dict):  # the loud, named acquisition-error slot
        probed["outcome"] = "acquisition_failed"
        probed["xbrl_is_none"] = None  # never reached `filing.xbrl()`
    else:
        probed["outcome"] = "resolved"
        probed["xbrl_is_none"] = filing.xbrl() is None
    return probed


def _build_doc() -> dict:
    span = sec.assemble_quarterly_filing_span(CIK, years=None)
    tenqs = [row for row in span if row.get("form") == "10-Q"]
    assert tenqs, f"no 10-Q filings found for CIK {CIK} in the assembled span"
    oldest = tenqs[0]  # assemble_quarterly_filing_span is oldest-first
    oldest_accession = oldest["accessionNumber"]

    # --- 1. the genuinely oldest 10-Q: expected to fail loudly -------------
    oldest_filing = sec._acquire_raw_filing(oldest_accession)
    if isinstance(oldest_filing, dict):  # the loud, named acquisition-error slot
        oldest_result = {
            "accession": oldest_accession,
            "filing_date": oldest.get("filingDate"),
            "report_date": oldest.get("reportDate"),
            "outcome": "acquisition_failed",
            "error": oldest_filing,
        }
    else:
        oldest_xbrl = oldest_filing.xbrl()
        if oldest_xbrl is None:
            oldest_result = {
                "accession": oldest_accession,
                "filing_date": str(oldest_filing.filing_date),
                "report_date": oldest.get("reportDate"),
                "outcome": "no_xbrl",
            }
        else:
            oldest_result = {
                "accession": oldest_accession,
                "filing_date": str(oldest_filing.filing_date),
                "report_date": oldest.get("reportDate"),
                "outcome": "parsed",
                "presentation_roles": [str(r) for r in oldest_xbrl.presentation_roles],
                "roles_captured": _capture_roles_and_rows(oldest_xbrl),
            }

    # --- 2. the earliest 10-Q that actually parses --------------------------
    parsing_filing = sec._acquire_raw_filing(EARLIEST_PARSING_ACCESSION)
    assert not isinstance(parsing_filing, dict), (
        f"expected {EARLIEST_PARSING_ACCESSION} to acquire cleanly: {parsing_filing}"
    )
    parsing_xbrl = parsing_filing.xbrl()
    assert parsing_xbrl is not None, f"expected {EARLIEST_PARSING_ACCESSION} to carry XBRL"
    roles = [str(r) for r in parsing_xbrl.presentation_roles]
    roles_captured = _capture_roles_and_rows(parsing_xbrl)

    # Run the REAL production path once, live, so the capture records what it
    # actually found -- informational only. The offline test recomputes its
    # own verdict via `statements_for` against the captured rows, never by
    # trusting this number.
    live = statements_for(parsing_filing)
    all_lines = [line for lines in live.by_kind.values() for line in lines]
    n_with_parent = sum(1 for line in all_lines if line.calculation_parent is not None)

    # --- 3. the isXBRL index scan and the sample, as fixture evidence -------
    # `fetch_submissions` is already warm from step 1's span assembly, so this
    # costs no extra request.
    submissions = sec.fetch_submissions(CIK)
    assert "error" not in submissions, f"submissions fetch failed: {submissions}"
    rows = _index_rows(submissions["data"]["filings"]["recent"])
    isxbrl_scan = _scan_isxbrl_index(rows)

    by_accession = {row["accession"]: row for row in rows}
    counterexample = []
    for accession in FLAG_SEMANTICS_COUNTEREXAMPLE_ACCESSIONS:
        row = by_accession.get(accession)
        assert row is not None, f"counterexample accession {accession} is not in the index"
        counterexample.append(row)
    isxbrl_scan["flag_semantics_counterexample"] = counterexample

    sampled = []
    for accession in SAMPLED_PRE_MANDATE_ACCESSIONS:
        row = by_accession.get(accession)
        assert row is not None, f"sampled accession {accession} is not in the index"
        sampled.append(
            _probe_sample(
                row,
                already_acquired=oldest_filing if accession == oldest_accession else None,
            )
        )
    isxbrl_scan["sampled"] = sampled

    return {
        "_capture": {
            "what": (
                "Live capture pinning plan Task I's oldest-filing measurement: "
                "the genuinely oldest 10-Q assemble_quarterly_filing_span yields "
                "for KO (CIK 21344), plus the earliest 10-Q that actually parses. "
                "docs/loom/plans/2026-07-28-us-quarterly-statement-series.md."
            ),
            "captured_at": CAPTURED_AT,
            "sdk": SDK,
            "ticker": TICKER,
            "cik": CIK,
            "span_size": len(span),
            "tenq_count": len(tenqs),
            "regenerate": (
                "investing-toolkit/tests/data/fixtures/"
                "capture_us_oldest_filing.py"
            ),
            "live_verdict_informational_only": {
                "kinds": sorted(live.by_kind.keys()),
                "n_lines_total": len(all_lines),
                "n_lines_with_calculation_parent": n_with_parent,
            },
            "isxbrl_index_scan": isxbrl_scan,
        },
        "ticker": TICKER,
        "cik": CIK,
        "oldest_available": oldest_result,
        "earliest_parsing": {
            "accession": EARLIEST_PARSING_ACCESSION,
            "filing_date": str(parsing_filing.filing_date),
            "period_of_report": str(parsing_filing.period_of_report),
            "form": parsing_filing.form,
            "presentation_roles": roles,
            "roles_captured": roles_captured,
        },
    }


def main() -> None:
    # edgartools prints library-internal warnings straight to stdout (not
    # stderr, not `logging`) when an old accession's period index is missing
    # -- observed on the 1994 accession below. Redirected here so ONLY the
    # JSON document reaches stdout; nothing about the captured DATA is
    # suppressed -- a non-empty buffer is relocated to stderr, not discarded,
    # so a FUTURE stray diagnostic stays visible instead of vanishing.
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        doc = _build_doc()
    captured = buffer.getvalue()
    if captured:
        print(captured, file=sys.stderr, end="")
    print(json.dumps(doc, indent=1, default=str))


if __name__ == "__main__":
    main()
