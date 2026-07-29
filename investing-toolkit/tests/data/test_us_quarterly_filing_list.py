"""test_us_quarterly_filing_list.py -- `assemble_quarterly_filing_span` must
return a filer's ENTIRE 10-Q/10-K history, oldest first, uncapped by default.

Plan Task A (docs/loom/plans/2026-07-28-us-quarterly-statement-series.md):
ten years is a FLOOR, not a target -- the default span is ALL available
history (~77 filings for a filer with full XBRL history), with an OPTIONAL
`years` cap for a quick look. `list_filings`'s own `limit` parameter
truncates by row count when no `min_filing_date` is given, so an uncapped
caller that passes a constant `limit` (e.g. a "generous" 200) silently
truncates once a filer's real history exceeds it -- the same shape of defect
`narrative_filings_window_days`'s docstring already documents for a sibling
parameter (`narrative_filings_window_days`, sec_edgar_client.py:896-933).

Offline: `requests` is injected as a `sys.modules` stub BEFORE importing
sec_edgar_client (its module-level `import requests` runs at import time);
every test stubs `_sec_get` -- no network. Same stubbing pattern as
test_sec_submissions_pagination.py.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
MARKETS_SCRIPTS = ROOT / "skills" / "data-markets" / "scripts"

if "requests" not in sys.modules:  # module-level `import requests` runs on import
    sys.modules["requests"] = mock.MagicMock(name="requests")
if str(MARKETS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(MARKETS_SCRIPTS))

import sec_edgar_client as sec  # noqa: E402

CIK = 1326801

ARRAY_KEYS = (
    "form",
    "filingDate",
    "accessionNumber",
    "primaryDocument",
    "primaryDocDescription",
    "items",
    "reportDate",
)

# Each subsequent filing is 400 days older than the last -- comfortably more
# than one calendar year apart (366-day leap-safe year), so no single
# filing's classification into "within N years" vs "outside N years" can flip
# on leap-year arithmetic or an off-by-one boundary.
_STEP_DAYS = 400
_N_FILINGS = 15  # spans ~15 * 400 / 365 ~= 16.4 years of history


def _dated(i: int) -> str:
    return (date.today() - timedelta(days=i * _STEP_DAYS)).isoformat()


def _rows(specs):
    """Build a `recent`-shaped parallel-array dict from (form, date) pairs."""
    block = {k: [] for k in ARRAY_KEYS}
    for form, filing_date in specs:
        block["form"].append(form)
        block["filingDate"].append(filing_date)
        block["accessionNumber"].append(f"acc-{form}-{filing_date}")
        block["primaryDocument"].append(f"{form}-{filing_date}.htm")
        block["primaryDocDescription"].append(form)
        block["items"].append("")
        block["reportDate"].append(filing_date)
    return block


def _main_doc(recent):
    return {
        "cik": CIK,
        "name": "Example Corp",
        "filings": {"recent": recent, "files": []},
    }


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("INVESTING_TOOLKIT_CACHE", str(tmp_path / "cache"))
    yield


@pytest.fixture
def responder(monkeypatch):
    """Stub `_sec_get` with a URL -> payload map that records every call."""
    calls: list[str] = []
    routes: dict[str, object] = {}

    def _get(url, *, as_json=True):
        calls.append(url)
        if url not in routes:
            return {"error": f"unrouted test URL: {url}"}
        payload = routes[url]
        return payload() if callable(payload) else payload

    monkeypatch.setattr(sec, "_sec_get", _get)
    return type("Responder", (), {"calls": calls, "routes": routes})()


def _url_main(cik=CIK):
    return sec.SEC_SUBMISSIONS_URL.format(cik=cik)


def _seed_filer(responder):
    """15 10-Q/10-K filings spread ~16 years, oldest at index 14, newest at 0
    -- plus a batch of interleaved 8-Ks the assembly must exclude, so the
    derived `limit` (built from the TOTAL row count across all forms) is
    exercised against a history where matching rows are a strict subset of
    the total.
    """
    quarterly_specs = [
        ("10-K" if i % 3 == 0 else "10-Q", _dated(i)) for i in range(_N_FILINGS)
    ]
    # Interleaved noise: unrelated forms the assembly must not return, dated
    # inside the same span so they inflate the total row count.
    noise_specs = [("8-K", _dated(i) if i < _N_FILINGS else _dated(0)) for i in range(20)]
    recent = _rows(quarterly_specs + noise_specs)
    responder.routes[_url_main()] = _main_doc(recent)
    return quarterly_specs


def test_uncapped_request_returns_every_available_filing(responder):
    quarterly_specs = _seed_filer(responder)

    rows = sec.assemble_quarterly_filing_span(CIK)

    assert len(rows) == _N_FILINGS, (
        f"uncapped call must return every 10-Q/10-K, got {len(rows)}: {rows}"
    )
    forms_returned = {r["form"] for r in rows}
    assert forms_returned == {"10-Q", "10-K"}, (
        f"expected both forms present, got {forms_returned}"
    )
    dates_returned = [r["filingDate"] for r in rows]
    assert dates_returned == sorted(dates_returned), (
        f"rows must be ordered oldest-first: {dates_returned}"
    )
    # Oldest (i=14) must be first, newest (i=0) must be last.
    expected_oldest, expected_newest = quarterly_specs[14][1], quarterly_specs[0][1]
    assert dates_returned[0] == expected_oldest
    assert dates_returned[-1] == expected_newest


def test_years_cap_returns_only_the_most_recent_window(responder):
    _seed_filer(responder)

    rows = sec.assemble_quarterly_filing_span(CIK, years=5)

    # Filings at i=0..4 (ages 0,400,800,1200,1600 days) fall within 5*366
    # days (1830); i=5 (age 2000 days) falls outside it.
    assert len(rows) == 5, (
        f"years=5 must return only the most recent 5 years' worth, got "
        f"{len(rows)}: {[r['filingDate'] for r in rows]}"
    )
    dates_returned = [r["filingDate"] for r in rows]
    assert dates_returned == sorted(dates_returned), (
        f"capped rows must also be ordered oldest-first: {dates_returned}"
    )
    cutoff = (date.today() - timedelta(days=5 * 366)).isoformat()
    assert all(d >= cutoff for d in dates_returned), (
        f"a row older than the 5-year cutoff leaked through: {dates_returned}"
    )


def test_uncapped_path_derives_limit_from_the_payloads_own_row_count(
    responder, monkeypatch
):
    """The defect this task exists to prevent: a caller passing a constant
    `limit` (however generous) to `list_filings` truncates once history
    exceeds it. Seeding "more rows than any constant" cannot pin this --
    any fixed number chosen for the seed can always be beaten by a bigger
    constant in the implementation, so that shape of test is structurally
    unable to fail on the regression it names.

    Pin the DERIVATION instead: monkeypatch `list_filings` to record the
    `limit` it is actually called with, then assert that value equals the
    `_seed_filer` payload's own total row count (15 quarterly + 20 noise =
    35, read back from the seeded payload rather than hardcoded here so
    the assertion cannot drift from the fixture). A constant of 8, 90, 200,
    or 10_000 all fail this assertion; only a value derived from the
    payload's own row count passes.
    """
    _seed_filer(responder)
    recent = responder.routes[_url_main()]["filings"]["recent"]
    total_rows = len(recent["form"])

    recorded_limits: list[int] = []
    real_list_filings = sec.list_filings

    def _recording_list_filings(cik, forms, limit, min_filing_date=None):
        recorded_limits.append(limit)
        return real_list_filings(cik, forms, limit, min_filing_date=min_filing_date)

    monkeypatch.setattr(sec, "list_filings", _recording_list_filings)

    sec.assemble_quarterly_filing_span(CIK)

    assert recorded_limits == [total_rows], (
        f"uncapped call must derive `limit` from the payload's own total row "
        f"count ({total_rows}), got {recorded_limits}"
    )


def test_uncapped_request_handles_a_history_larger_than_common_constants(responder):
    """End-to-end companion to the derivation test above: seeds a filer
    history (90 filings) larger than several constants a careless
    implementation might reach for, and asserts none are dropped. This is
    a real-world-shaped smoke test, not proof against every constant --
    that proof is the derivation test above, which no fixed seed size can
    provide."""
    many = 90  # larger than the ~77-filing real-world ceiling cited in the brief
    specs = [("10-Q" if i % 4 else "10-K", _dated(i)) for i in range(many)]
    responder.routes[_url_main()] = _main_doc(_rows(specs))

    rows = sec.assemble_quarterly_filing_span(CIK)

    assert len(rows) == many, (
        f"uncapped assembly dropped filings: expected {many}, got {len(rows)}"
    )


def test_undated_filing_sorts_last_not_first(responder):
    """`_append_submission_block` deliberately pads short columns with
    `None` (sec_edgar_client.py:452) and `list_filings` keeps such rows
    rather than dropping them. Sorting with a bare
    `r.get("filingDate") or ""` key would put a `None`-dated row FIRST
    (an empty string sorts before any real date string) -- i.e. it would
    claim the OLDEST slot in an oldest-first contract for a row that has
    no date at all. Assert it sorts LAST instead."""
    dated_specs = [("10-Q", _dated(i)) for i in range(3)]
    recent = _rows(dated_specs)
    # Simulate a short/padded column: one more 10-Q row with no filingDate.
    recent["form"].append("10-Q")
    recent["filingDate"].append(None)
    recent["accessionNumber"].append("acc-undated")
    recent["primaryDocument"].append("undated.htm")
    recent["primaryDocDescription"].append("10-Q")
    recent["items"].append("")
    recent["reportDate"].append(None)
    responder.routes[_url_main()] = _main_doc(recent)

    rows = sec.assemble_quarterly_filing_span(CIK)

    assert len(rows) == 4
    assert rows[-1]["filingDate"] is None, (
        f"an undated filing must sort LAST, not claim the oldest slot: "
        f"{[r['filingDate'] for r in rows]}"
    )
