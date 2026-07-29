"""test_us_oldest_filing_parse.py -- plan Task I
(docs/loom/plans/2026-07-28-us-quarterly-statement-series.md): does the
production parse path (`kpi_us_statement_shape.statements_for`) still hold at
the TRUE floor of KO's available 10-Q history, not the 2014 floor the brief's
earlier probe assumed.

TWO MEASUREMENTS, BOTH LIVE, BOTH NEEDED -- captured once by
`fixtures/capture_us_oldest_filing.py` into the committed fixture
`fixtures/us_oldest_filing_rows.json`; this suite makes no network call.

  1. The GENUINELY oldest 10-Q `assemble_quarterly_filing_span` yields for KO
     (CIK 21344) is `0000021344-94-000012`, filed 1994-05-06 -- fifteen
     years before the 2009-07-30 floor recorded below, and it cannot be
     acquired at all: `sec_edgar_client._acquire_raw_filing` returns an
     explicit
     `{"error": ..., "error_class": "resolution"}` slot, never a silent None
     or an empty statement set. That IS the "fails loudly" branch the plan's
     acceptance names, so this test asserts the failure is explicit and named
     rather than trying to force a `statements_for` call the fixture never
     reached.

  2. THE EARLIEST 10-Q THAT ACTUALLY PARSES is `0001047469-09-007013`, filed
     2009-07-30, period 2009-07-03 (Q2 2009) -- earlier than the brief's
     assumed 2014 floor by five years. Filings sampled between 1994 and this
     one (1998, 2000, 2008, and 2009-04-30) all resolve but carry no XBRL at
     all (`filing.xbrl()` is `None`), consistent with the SEC's own phased
     mandate: Phase 1 was large accelerated filers using US GAAP with
     worldwide public float over $5 billion (~500 companies), effective for
     periods ending on or after 2009-06-15 (17 CFR 232.405, Release 33-9002);
     the second year covered "All other domestic and foreign large
     accelerated filers using U.S. GAAP" (2010-06-15) and the third "All
     remaining filers using U.S. GAAP, including smaller reporting
     companies" plus all foreign private issuers preparing their financial
     statements in accordance with IFRS as issued by the IASB (2011-06-15).
     THOSE TWO QUOTED STRINGS ARE VERBATIM from 74 FR 6776, string-matched
     on 2026-07-30 against govinfo's FR-2009-02-10 text (one hit each,
     including the sentence-initial capital); the IFRS clause paraphrases
     the remainder of the same sentence, and the "Phase 1/2/3" shorthand
     used below is this docstring's, not the source's -- 74 FR 6776 never
     uses it. KO clears the $5B float threshold and reports under US GAAP,
     so Phase 1's 2009-06-15 date is the
     one that applies to it -- 2009 Q2's period-end of 2009-07-03 is the
     first quarter-end after that date. This qualifier matters beyond KO: a
     filer without KO's float would have a later Phase 2/3 floor, not this
     2009 one, and the US-GAAP half of it is load-bearing too -- a large
     accelerated filer reporting under IFRS sat in Phase 3, not Phase 2.

     **THE EARLIEST YEAR THAT PARSES CLEANLY IS 2009 FOR KO** (Q2, 10-Q
     period 2009-07-03) -- the series' real floor for this filer, five years
     earlier than the 2014 floor the brief's original probe assumed and
     reaching the very first quarter to which the SEC's Phase 1 XBRL mandate
     applied. What is established is the mandated floor for a Phase 1 filer
     like KO. A voluntary XBRL filing program predates the mandate, so a
     filer COULD in principle carry XBRL earlier than its own phase date;
     rather than speculate about that, this suite reports an INDEX SCAN,
     exhaustive rather than sampled -- across EVERY row of KO's EDGAR
     submissions index (all 3,287 rows as of the 2026-07-30 capture, every
     form, not just 10-Qs), no row filed before 2009-07-30 carries
     `isXBRL=1` (900 such rows, 46 of them 10-Qs), and exactly one row filed
     ON that date does: this filing. That is the flag REPORTED AS THE INDEX
     CARRIES IT, not a reading of what it means -- it is demonstrably not a
     plain "this filing has XBRL" bit, since a later ORIGINAL 10-Q (filed
     2009-10-29) carries `isXBRL=0` while the 10-Q/A filed that same day
     carries `isXBRL=1`; that pair is recorded under
     `_capture.isxbrl_index_scan.flag_semantics_counterexample` rather than
     asserted from memory. The `filing.xbrl()` results above stay what they
     are: a five-filing sample, not a scan. Scan and sample are both
     recorded in the fixture under `_capture.isxbrl_index_scan` and asserted
     by `test_fixture_records_the_isxbrl_index_scan_the_docstring_cites`
     below, so each is checkable in-repo instead of only by a live re-run.

No `@req` tags: this dispatch carries no registered loom-spec REQ-ids (the
work is tracked by named plan Task I), so `@req` is omitted per the
implementer contract.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]  # investing-toolkit/
STATEMENT_SHAPE_SCRIPT = (
    ROOT / "skills" / "analysis-kpi" / "scripts" / "kpi_us_statement_shape.py"
)
FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "us_oldest_filing_rows.json"
)

EXPECTED_KINDS = frozenset({"income", "balance_sheet", "cash_flow"})


def _load_module(name: str, path: Path):
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def shape():
    return _load_module("kpi_us_statement_shape_oldest_test", STATEMENT_SHAPE_SCRIPT)


@pytest.fixture(scope="module")
def capture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class _CapturedXBRL:
    """The two-attribute slice of `edgar.xbrl.XBRL` that `statements_for`
    reads, built from the `earliest_parsing` block of the captured fixture --
    same shape as the double in
    `investing-toolkit/tests/analysis/test_kpi_us_statement_shape.py` (a
    SIBLING directory, not this one), duplicated here rather than imported
    so this module stays independently readable
    (repo convention: every statement-assembly test file owns its double)."""

    def __init__(self, entry: dict):
        self._rows_by_role = {
            item["role"]: item["rows"] for item in entry["roles_captured"]
        }
        self.presentation_roles = list(entry["presentation_roles"])

    def get_statement(self, role: str) -> list[dict]:
        return self._rows_by_role[role]


class _CapturedFiling:
    def __init__(self, entry: dict):
        self.accession_no = entry["accession"]
        self._xbrl = _CapturedXBRL(entry)

    def xbrl(self):
        return self._xbrl


def test_oldest_available_filing_parses_or_fails_loudly(shape, capture):
    """The earliest year that parses cleanly is 2009 -- see module docstring.

    Two assertions, one per captured data point:

      * the GENUINELY oldest 10-Q (1994, pre-XBRL) fails at acquisition with
        an EXPLICIT, NAMED error -- never a silent empty result. This is the
        "or fails loudly" branch: `statements_for` is never even reachable
        for this filing because it has no XBRL to acquire, and the fixture
        captures that failure as it actually happened rather than a stand-in.
      * the EARLIEST 10-Q that DOES carry XBRL (2009-07-30, period
        2009-07-03) still yields all three classified statement kinds AND the
        recorded `calculation_parent` count -- 93 lines total, 74 with a
        declared parent -- through the CURRENT production `statements_for`
        path. The rows are FROZEN in the fixture (the only variable is our
        own `statements_for`), so pinning the exact counts cannot break on
        dependency drift, and this is the module's existing convention
        (`kpi_us_statement_shape._is_rendered_line`'s own docstring pins
        "80 rows less 49 segment slices less 5 abstract rows" = 26).
        A regression collapsing 74 parents
        down to 1 would still pass a bare `> 0` check; asserting the
        recorded counts makes the assertion genuinely non-vacuous.
    """
    oldest = capture["oldest_available"]
    assert oldest["outcome"] == "acquisition_failed", (
        "the genuinely oldest 10-Q was expected to fail ACQUISITION (no XBRL "
        f"exists for it yet); got outcome={oldest['outcome']!r} instead -- if "
        "this now succeeds, re-run capture_us_oldest_filing.py, this fixture "
        "is stale, and the real floor may have moved earlier than 2009"
    )
    error = oldest["error"]
    assert error.get("error_class") == "resolution"
    assert oldest["accession"] in error.get("error", ""), (
        "the failure must NAME the accession it is about, not report a bare "
        "generic message"
    )

    parsing_entry = capture["earliest_parsing"]
    filing = _CapturedFiling(parsing_entry)
    statements = shape.statements_for(filing)

    assert set(statements.by_kind.keys()) == EXPECTED_KINDS, (
        f"expected all three statement kinds, got {sorted(statements.by_kind)}"
    )
    all_lines = [line for lines in statements.by_kind.values() for line in lines]
    assert all_lines, "assembly produced no lines at all"
    assert len(all_lines) == 93, (
        f"expected the recorded 93 total lines, got {len(all_lines)} -- if "
        "this changed, re-run capture_us_oldest_filing.py and confirm the "
        "shift is intentional before updating this pin"
    )
    n_with_parent = sum(1 for line in all_lines if line.calculation_parent is not None)
    assert n_with_parent == 74, (
        f"expected the recorded 74 lines with a declared calculation_parent, "
        f"got {n_with_parent} -- a collapse toward 0 or 1 is a degraded "
        "parse that a bare non-zero check would miss"
    )


def test_fixture_records_the_isxbrl_index_scan_the_docstring_cites(capture):
    """The module docstring's pre-2009 claim must be checkable IN THE REPO.

    The docstring states that no filing in KO's whole submissions index
    carries `isXBRL=1` before 2009-07-30. Without this test that sentence
    would cite nothing a reader can open: only a live re-run could refute
    it, and a later edit to the capture script could drop the evidence
    silently. So the scan's own counts are asserted here against the
    committed fixture.

    The two counts pinned exactly (`900` index rows, `46` of them 10-Qs)
    are counts of CLOSED history -- filings made before 2009-07-30 -- so
    they cannot drift as KO keeps filing. The index TOTAL is deliberately
    not pinned here for the opposite reason: it grows with every new filing,
    so the module docstring quotes it with a capture date instead. Pinning
    the closed-history counts follows this module's existing convention for
    the 93/74 line counts above.
    """
    scan = capture["_capture"]["isxbrl_index_scan"]
    earliest = scan["earliest_isxbrl_1"]

    assert earliest["accession"] == capture["earliest_parsing"]["accession"], (
        "the earliest index row flagged isXBRL=1 must be the same filing this "
        "suite parses; if these diverge the docstring's floor is wrong"
    )
    assert scan["rows_filed_before_that_date_with_isxbrl_1"] == 0, (
        "an index row before the floor carries isXBRL=1 -- the docstring's "
        "exhaustive claim is refuted; re-read the scan before editing it"
    )
    assert scan["isxbrl_1_rows_on_that_date"] == 1, (
        "more than one row on the floor date carries isXBRL=1, so 'the "
        "earliest' is ambiguous and the docstring must say which"
    )
    assert scan["rows_filed_before_that_date"] == 900, (
        f"expected the recorded 900 index rows filed before the floor, got "
        f"{scan['rows_filed_before_that_date']} -- this counts closed "
        "history and should not move; re-run capture_us_oldest_filing.py "
        "and confirm the shift is real before updating this pin"
    )
    assert scan["tenq_filed_before_that_date"] == 46, (
        f"expected the recorded 46 pre-floor 10-Q rows, got "
        f"{scan['tenq_filed_before_that_date']}"
    )
    assert scan["tenq_filed_before_that_date_with_isxbrl_1"] == 0

    # The five sampled filings the docstring names, each with the flag the
    # index actually carried for it -- so "the sample" is a list of
    # accessions in the repo, not four bare years in a sentence.
    sampled = scan["sampled"]
    assert [s["filing_date"] for s in sampled] == [
        "1994-05-06",
        "1998-05-12",
        "2000-05-11",
        "2008-04-25",
        "2009-04-30",
    ], f"the recorded sample is not the one the docstring names: {sampled}"
    assert all(s["isXBRL"] == 0 for s in sampled), (
        f"a sampled pre-mandate filing carries isXBRL=1: {sampled}"
    )
    assert [s["xbrl_is_none"] for s in sampled] == [None, True, True, True, True], (
        "the four resolvable samples must each have returned None from "
        f"`filing.xbrl()`, and the 1994 one must never have reached it: {sampled}"
    )

    # The docstring says the flag is NOT a plain "this filing has XBRL" bit,
    # and points at one same-day pair as its reason. That pair is evidence,
    # so it is checked here rather than believed.
    pair = scan["flag_semantics_counterexample"]
    assert {(row["form"], row["isXBRL"]) for row in pair} == {("10-Q", 0), ("10-Q/A", 1)}, (
        "the recorded pair no longer shows an original 10-Q flagged 0 beside "
        f"an amendment flagged 1, so the docstring's reason is gone: {pair}"
    )
    assert len({row["filing_date"] for row in pair}) == 1, (
        f"the pair must share ONE filing date for the point to hold: {pair}"
    )
