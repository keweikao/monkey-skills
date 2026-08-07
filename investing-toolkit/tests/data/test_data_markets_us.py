"""test_data_markets_us.py — Task 3a migration contract.

Verifies the US client + pack-builder migration into
skills/data-markets/scripts/:

  (a) migrated client files (yfinance_client.py, fred_client.py,
      sec_edgar_client.py) define no local cache-helper boilerplate
      (_CACHE_BASE / CACHE_DIR / CACHE_TTL_* constants,
      get_cache_path / load_cache / save_cache or underscore-variant
      defs) — source-scan check, no execution — and `import cache_util`.
  (b) pack_us.build_pack("snapshot", ["AAPL"]) produces a dict whose
      top-level section keys match the current data-us fixture sample
      (fixture-fed / mocked subprocess — offline, no network).
  (c) pack_us.SUPPORTED_PACKS matches data-us/scripts/pack.py's current
      --pack choices.

Offline: no network calls. The subprocess boundary (run_client) is
mocked in test (b).
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import sys
from decimal import Decimal
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
MARKETS_SCRIPTS = ROOT / "skills" / "data-markets" / "scripts"
FIXTURES = ROOT / "tests" / "data" / "fixtures"


@pytest.fixture(autouse=True)
def _stub_requests_for_sec_edgar_client(monkeypatch):
    """pack_us.pack_memo_fetch lazily imports
    sec_edgar_client.select_narrative_filings (a pure function) to decide
    which filings the narrative fetch covers. Offline CI installs
    pytest+pyyaml ONLY, so sec_edgar_client's top-level `import requests`
    would fail without a stub — breaking every test in this file that
    reaches pack_memo_fetch (mirrors test_sec_narrative.py's `sec_client`
    fixture; only `requests` is stubbed here, not `edgar`, because
    select_narrative_filings is a pure function that never reaches the
    edgartools boundary)."""
    if "requests" not in sys.modules:
        monkeypatch.setitem(sys.modules, "requests", mock.MagicMock(name="requests"))


@pytest.fixture(autouse=True)
def _stub_xval_producers_for_memo_fetch(monkeypatch):
    """Task 3: `pack_memo_fetch` now unconditionally calls
    `_fetch_xval_source_a` (which reaches edgartools' real `import edgar`,
    unlike the pure `select_narrative_filings` the fixture above already
    covers) and `build_companyfacts_pack` (a real SEC companyfacts fetch)
    for every memo-fetch. Tests in this file that exercise `pack_memo_fetch`
    but don't assert on xval (the pre-Task-3 narrative/DCF tests) must not
    crash on `ModuleNotFoundError: edgar` or attempt a real network call.

    Stubs at the PRODUCER'S OWN boundary (`sec_edgar_client._acquire_raw_filing`
    / `sec_edgar_client.build_companyfacts_pack`), not `pack_us._fetch_xval_source_a`
    itself -- Task 2's own direct-call tests
    (`test_fetch_xval_source_a_wraps_cells_envelope`,
    `test_fetch_xval_source_a_no_10k_is_wholesale_failure_not_crash`) exercise
    that real function's own logic and would break if this fixture shadowed
    it wholesale. Stubbing `_acquire_raw_filing` with a resolution-error slot
    lets `_fetch_xval_source_a`'s REAL implementation run unmodified, naturally
    producing its own already-tested wholesale-failure shape (harmless for
    tests that don't assert on it); `build_companyfacts_pack` has no direct
    unit test in THIS file (its own is in test_sec_xval.py), so stubbing it
    outright is safe. Tests that DO assert on xval
    (`test_pack_memo_fetch_emits_xval_packs_with_status`,
    `test_us_migration_memo_fetch_section_keys`) override this default with
    their own narrower `mock.patch.object` for the scope of their own `with`
    block."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import sec_edgar_client  # noqa: E402

    monkeypatch.setattr(
        sec_edgar_client, "_acquire_raw_filing",
        lambda accession: {
            "error": f"SEC EDGAR filing acquisition failed: accession {accession!r} did not resolve to a filing",
            "error_class": "resolution",
        },
    )
    monkeypatch.setattr(
        sec_edgar_client, "build_companyfacts_pack",
        lambda cik: {"cik": cik, "facts": {}},
    )

CLIENT_FILES = ["yfinance_client.py", "fred_client.py", "sec_edgar_client.py"]

# Local cache boilerplate being deleted per Task 3a — module-level
# constants and function definitions, matched at line start (so a mention
# inside a comment/docstring sentence doesn't false-positive, but an
# actual definition/assignment does).
_LOCAL_CACHE_HELPER_PATTERNS = [
    r"^_CACHE_BASE\s*=",
    r"^CACHE_DIR\s*=",
    r"^CACHE_TTL_\w*\s*=",
    r"^\s*def get_cache_path\(",
    r"^\s*def load_cache\(",
    r"^\s*def save_cache\(",
    r"^\s*def _load_cache\(",
    r"^\s*def _save_cache\(",
    r"^\s*def _cache_path\(",
]


def test_us_migration_contract():
    # --- (a) migrated clients: no local cache boilerplate, cache_util imported ---
    for fname in CLIENT_FILES:
        path = MARKETS_SCRIPTS / fname
        assert path.exists(), f"missing migrated client: {fname}"
        text = path.read_text()

        for pattern in _LOCAL_CACHE_HELPER_PATTERNS:
            assert not re.search(pattern, text, re.MULTILINE), (
                f"{fname} still defines local cache boilerplate matching {pattern!r}"
            )

        assert re.search(r"^import cache_util\s*$", text, re.MULTILINE), (
            f"{fname} does not `import cache_util`"
        )

    pack_us_path = MARKETS_SCRIPTS / "pack_us.py"
    assert pack_us_path.exists(), "missing pack_us.py"

    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402  (path-dependent import, must follow sys.path insert)

    # --- (c) SUPPORTED_PACKS matches data-us/scripts/pack.py's current --pack choices ---
    # Exact-equality, not a prefix check: the migration contract is that no
    # historical data-us pack was dropped, renamed, or reordered, AND that
    # any pack added after the consolidation (kpi-quarterly, 2026-07-18
    # memo-quarterly-kpi-wiring Task 1) is deliberately registered here in
    # its exact position. A future unregistered addition or reorder must
    # fail this assertion.
    assert pack_us.SUPPORTED_PACKS == (
        "snapshot", "memo-fetch", "comps-multiples", "screener-batch", "regime-pack",
        "kpi-quarterly", "kpi-topline-backfill", "statement-backfill", "reconstruct",
        "quarterly-series",
    ), f"SUPPORTED_PACKS diverges from data-us pack.py --pack choices: {pack_us.SUPPORTED_PACKS}"

    # --- (b) build_pack("snapshot", ...) section keys match fixture (fixture-fed, mocked subprocess) ---
    fixture = json.loads((FIXTURES / "data-us-snapshot-sample.json").read_text())
    expected_keys = set(fixture.keys())

    with mock.patch.object(pack_us, "run_client") as mock_run_client:
        mock_run_client.side_effect = [
            fixture["company_info"],
            fixture["price_history"],
        ]
        result = pack_us.build_pack("snapshot", ["AAPL"])

    assert mock_run_client.call_count == 2, (
        "pack_snapshot should shell out exactly twice (info, history) via run_client"
    )
    assert set(result.keys()) == expected_keys, (
        f"pack_us snapshot section keys diverge from data-us fixture: "
        f"missing={expected_keys - set(result.keys())} "
        f"extra={set(result.keys()) - expected_keys}"
    )
    assert result["ticker"] == "AAPL"
    assert result["company_info"] == fixture["company_info"]
    assert result["price_history"] == fixture["price_history"]


def _mock_run_client_for_memo_fetch(fixture: dict):
    """Route mocked run_client calls to fixture sections by script + args,
    so pack_memo_fetch's ~40 DCF-concept sub-calls (one per XBRL concept in
    DCF_CONCEPT_MAPPING) don't need individually-ordered side_effect entries.
    Concept-fetch calls return {} (no `observations`) — pack_us._fetch_dcf_concepts
    drops those, so income_statement/cash_flow/balance_sheet still assemble
    (as empty-series dicts) without asserting on their inner values here.
    """
    import pack_us  # noqa: E402  (module under test, already on sys.path)

    # accession -> producer-shaped narrative result, keyed from the fixture's
    # own sec_narrative.filings entries (each already carries "accession").
    narrative_by_accession = {
        entry["accession"]: entry
        for entry in fixture.get("sec_narrative", {}).get("filings", [])
        if "accession" in entry
    }

    def _side_effect(script, extra_args, timeout=pack_us.CLIENT_TIMEOUT_SECONDS):
        if script == pack_us.YF:
            if "info" in extra_args:
                return fixture["company_info"]
            return fixture["price_history"]
        if script == pack_us.SEC:
            if "filings" in extra_args:
                return fixture["sec_filings"]
            if "--concept" in extra_args:
                return {}
            if "narrative" in extra_args:
                accession = extra_args[extra_args.index("--accession") + 1]
                return narrative_by_accession.get(accession, {
                    "error": f"no fixture narrative entry for accession {accession!r}",
                })
            return fixture["sec_facts"]
        raise AssertionError(f"unexpected run_client script: {script}")

    return _side_effect


def test_us_migration_memo_fetch_section_keys():
    """pack_us.build_pack("memo-fetch", ...) top-level section keys match
    the data-us memo-fetch fixture (fixture-fed / mocked subprocess —
    offline, no network). Separate from the snapshot test above for
    F.I.R.S.T independence (one pack type's assertion failing must not
    hide the other's).

    Task 3 added two new top-level keys (`xval_source_a`/`xval_source_b`)
    not present in the pre-Task-3 fixture -- added to `expected_keys`
    directly rather than editing the fixture (out of this task's file
    scope). Their own producers (`_fetch_xval_source_a` /
    `build_companyfacts_pack`) are mocked here too, so this section-keys
    test never reaches the real edgartools/companyfacts network boundary
    those two producers touch."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402  (path-dependent import, must follow sys.path insert)
    import sec_edgar_client  # noqa: E402

    fixture = json.loads((FIXTURES / "data-us-memo-fetch-sample.json").read_text())
    expected_keys = set(fixture.keys()) | {"xval_source_a", "xval_source_b"}

    with mock.patch.object(pack_us, "run_client") as mock_run_client, mock.patch.object(
        pack_us, "_fetch_xval_source_a",
        return_value={
            "statements": [], "failed_items": [], "requested": 4,
            "succeeded": 4, "failed": 0, "_status": "ok",
        },
    ), mock.patch.object(
        sec_edgar_client, "build_companyfacts_pack",
        return_value={"cik": 320193, "facts": {}},
    ):
        mock_run_client.side_effect = _mock_run_client_for_memo_fetch(fixture)
        result = pack_us.build_pack("memo-fetch", ["AAPL"])

    assert set(result.keys()) == expected_keys, (
        f"pack_us memo-fetch section keys diverge from data-us fixture: "
        f"missing={expected_keys - set(result.keys())} "
        f"extra={set(result.keys()) - expected_keys}"
    )
    assert result["ticker"] == "AAPL"
    assert result["company_info"] == fixture["company_info"]
    assert result["sec_filings"] == fixture["sec_filings"]


# ---------------------------------------------------------------------------
# Task 3 — pack_memo_fetch wires the SEC narrative into a top-level
# `sec_narrative` key (brief §Decision memo-feed contract).
# ---------------------------------------------------------------------------

def _quarter_of(d: _dt.date) -> tuple[int, int]:
    return (d.year, (d.month - 1) // 3 + 1)


def _shift_quarter(year_quarter: tuple[int, int], n: int) -> tuple[int, int]:
    year, q = year_quarter
    total = year * 4 + (q - 1) - n
    return (total // 4, total % 4 + 1)


def _date_in_quarter(year_quarter: tuple[int, int]) -> str:
    year, q = year_quarter
    month = (q - 1) * 3 + 1
    return _dt.date(year, month, 15).isoformat()


def _synthetic_narrative_filings_rows() -> list[dict]:
    """Filings rows (Task 1 shape: `items` + `reportDate`) covering exactly
    what `select_narrative_filings` needs to pick 6/6 with zero gaps: a
    10-K, a 10-Q, and one item-2.02 earnings 8-K per quarter for the last 4
    quarters. Computed off *today* (mirroring `select_narrative_filings`'s
    own `as_of` default, which `pack_memo_fetch` does not override) so this
    test never goes stale."""
    today = _dt.date.today()
    rows = [
        {
            "form": "10-K", "filingDate": today.isoformat(),
            "accessionNumber": "0000320193-26-100001",
            "primaryDocument": "10k.htm", "primaryDocDescription": "10-K",
            "items": "", "reportDate": today.isoformat(),
        },
        {
            "form": "10-Q", "filingDate": today.isoformat(),
            "accessionNumber": "0000320193-26-100002",
            "primaryDocument": "10q.htm", "primaryDocDescription": "10-Q",
            "items": "", "reportDate": today.isoformat(),
        },
    ]
    anchor_yq = _quarter_of(today)
    for n in range(4):
        yq = _shift_quarter(anchor_yq, n)
        rows.append({
            "form": "8-K",
            "filingDate": _date_in_quarter(yq),
            "accessionNumber": f"0000320193-26-20000{n}",
            "primaryDocument": f"8k-{n}.htm",
            "primaryDocDescription": "8-K",
            "items": "2.02,9.01",
            "reportDate": _date_in_quarter(yq),
        })
    return rows


def _producer_narrative(accession: str, *, status: str = "ok", failed_item: str | None = None) -> dict:
    """A producer-shaped `--action narrative` result — mirrors
    sec_edgar_client.fetch_narrative_sections's real emission
    (sec_edgar_client.py:1417-1435): accession/cik/form/filingDate/
    sections/section_count/narrative_status/failed_items/_cache."""
    sections = [{
        "item": "Item 1",
        "text_path": f"/tmp/sections/{accession}/Item_1.txt",
        "disclosure_status": "filed",
        "accession": accession,
        "cik": 320193,
        "filingDate": "2026-05-01",
        "period_of_report": None,
        "url": f"https://www.sec.gov/Archives/edgar/data/320193/{accession}/10k.htm",
    }]
    failed_items: list[str] = []
    if status == "partial" and failed_item:
        sections.append({
            "item": failed_item,
            "error": f"section {failed_item!r} extraction failed for filing {accession!r}",
            "error_class": "extraction_error",
        })
        failed_items = [failed_item]
    return {
        "accession": accession, "cik": 320193, "form": "10-K",
        "filingDate": "2026-05-01", "sections": sections,
        "section_count": len(sections), "narrative_status": status,
        "failed_items": failed_items, "_cache": "miss", "action": "narrative",
    }


def _mock_run_client_for_narrative(filings_rows: list[dict], narrative_by_index: dict | None = None):
    """run_client side_effect for the sec_narrative tests: YF calls return
    `{}` (untested here), the filings call returns `filings_rows`, and each
    `--action narrative` call returns a producer-shaped result.
    `narrative_by_index` maps the Nth narrative call (0-indexed, in
    selection order — 10-K, 10-Q, then one 8-K per quarter n=0..3, per
    `select_narrative_filings`'s own construction order) to an
    `(status, failed_item)` pair; unlisted calls default to "ok"."""
    import pack_us  # noqa: E402  (module under test, already on sys.path)

    narrative_by_index = narrative_by_index or {}
    call_count = {"n": 0}

    def _side_effect(script, extra_args, timeout=pack_us.CLIENT_TIMEOUT_SECONDS):
        if script == pack_us.YF:
            return {}
        if script == pack_us.SEC:
            if "filings" in extra_args:
                return {"filings": filings_rows}
            if "--concept" in extra_args:
                return {}
            if "narrative" in extra_args:
                accession = extra_args[extra_args.index("--accession") + 1]
                idx = call_count["n"]
                call_count["n"] += 1
                status, failed_item = narrative_by_index.get(idx, ("ok", None))
                return _producer_narrative(accession, status=status, failed_item=failed_item)
            return {}
        raise AssertionError(f"unexpected run_client script: {script}")

    return _side_effect


def test_pack_memo_fetch_filings_call_uses_policy_derived_window_not_count_limit():
    """Task 8 (post-live-anchor defect fix): the live-observed false gap
    (2026-07-13, real AAPL run) traced to this exact call site fetching
    filings with `--limit 8` -- a row-COUNT window applied across ALL forms
    combined, so 8-K/10-Q volume could crowd the once-a-year 10-K out
    entirely. Fixed by switching to a policy-derived `--since-days` DATE
    window (`sec_edgar_client.narrative_filings_window_days`) -- a count
    argument must never reach this call again."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402
    import sec_edgar_client  # noqa: E402  (pure window function; no edgar/requests call)

    filings_rows = _synthetic_narrative_filings_rows()
    captured_args = {}

    def _side_effect(script, extra_args, timeout=pack_us.CLIENT_TIMEOUT_SECONDS):
        if script == pack_us.YF:
            return {}
        if script == pack_us.SEC:
            if "filings" in extra_args:
                captured_args["filings"] = list(extra_args)
                return {"filings": filings_rows}
            if "--concept" in extra_args:
                return {}
            if "narrative" in extra_args:
                accession = extra_args[extra_args.index("--accession") + 1]
                return _producer_narrative(accession)
            return {}
        raise AssertionError(f"unexpected run_client script: {script}")

    with mock.patch.object(pack_us, "run_client") as mock_run_client:
        mock_run_client.side_effect = _side_effect
        pack_us.build_pack("memo-fetch", ["AAPL"])

    args = captured_args["filings"]
    assert "--limit" not in args, f"filings fetch must not be a count window: {args}"
    assert "--since-days" in args, f"filings fetch must be a date window: {args}"
    since_days = int(args[args.index("--since-days") + 1])
    assert since_days == sec_edgar_client.narrative_filings_window_days(), (
        f"since-days must be the policy-derived window, got {since_days}"
    )


def test_memo_fetch_emits_sec_narrative_with_counts():
    """pack_memo_fetch wires Task 2's selection + one `--action narrative`
    subprocess per selected accession into a new top-level `sec_narrative`
    key: requested is fixed by the policy (2 + 4 quarters = 6), succeeded +
    failed reconciles to requested, failed_items is a top-level list, and
    _status is "ok" when every selected filing narrates cleanly."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402

    filings_rows = _synthetic_narrative_filings_rows()

    with mock.patch.object(pack_us, "run_client") as mock_run_client:
        mock_run_client.side_effect = _mock_run_client_for_narrative(filings_rows)
        result = pack_us.build_pack("memo-fetch", ["AAPL"])

    assert "sec_narrative" in result, "pack_memo_fetch did not emit sec_narrative"
    sec_narrative = result["sec_narrative"]
    assert sec_narrative["requested"] == 6
    assert sec_narrative["succeeded"] + sec_narrative["failed"] == sec_narrative["requested"]
    assert isinstance(sec_narrative["failed_items"], list)
    assert sec_narrative["failed_items"] == []
    assert sec_narrative["_status"] == "ok"
    assert len(sec_narrative["filings"]) == 6


def test_memo_fetch_sec_narrative_partial_status_visible_at_depth_1():
    """A selected filing's producer result carrying narrative_status=
    "partial" must (a) flip the wrapper's own _status to "partial" and
    (b) surface that filing's failed item ids in the wrapper's TOP-LEVEL
    failed_items — readable without walking into any nested `sections`
    list (brief Fork A: a status string alone is the documented
    ignored-by-structural-readers failure mode)."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402

    filings_rows = _synthetic_narrative_filings_rows()

    with mock.patch.object(pack_us, "run_client") as mock_run_client:
        mock_run_client.side_effect = _mock_run_client_for_narrative(
            filings_rows, narrative_by_index={2: ("partial", "Item 1A")}
        )
        result = pack_us.build_pack("memo-fetch", ["AAPL"])

    sec_narrative = result["sec_narrative"]
    assert sec_narrative["_status"] == "partial"
    assert any(entry.get("item") == "Item 1A" for entry in sec_narrative["failed_items"]), (
        f"failed item not hoisted to depth 1: {sec_narrative['failed_items']}"
    )


def test_memo_fetch_partial_sec_narrative_classifies_whole_pack_partial():
    """End-to-end proof the seam actually works: pack.py's own
    `_classify_result` (Task 4's self-declared-`_status` reader) reports
    the whole pack as partial when sec_narrative degrades — not just that
    the field exists, but that the real structural reader honors it.

    Also pins the depth-1 hoisting itself (not just the derived `_status`
    flag): `_status` alone can go "partial" via `any_partial` even if the
    hoisting loop that populates top-level `failed_items` is deleted, so a
    status-only assertion here would pass under that mutation and prove
    nothing about hoisting. Asserting the hoisted item is present makes
    that mutation fail this test.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack  # noqa: E402
    import pack_us  # noqa: E402

    filings_rows = _synthetic_narrative_filings_rows()

    with mock.patch.object(pack_us, "run_client") as mock_run_client:
        mock_run_client.side_effect = _mock_run_client_for_narrative(
            filings_rows, narrative_by_index={2: ("partial", "Item 1A")}
        )
        result = pack_us.build_pack("memo-fetch", ["AAPL"])

    status, failed_sections = pack._classify_result(result)
    assert status == "partial"
    assert "sec_narrative" in failed_sections

    sec_narrative = result["sec_narrative"]
    assert sec_narrative["failed_items"], (
        "top-level failed_items is empty — the depth-1 hoisting loop that "
        "populates it from a partial filing's own failed_items appears to "
        "have been removed"
    )
    assert any(entry.get("item") == "Item 1A" for entry in sec_narrative["failed_items"]), (
        f"expected the partial filing's failed item 'Item 1A' hoisted to "
        f"depth 1: {sec_narrative['failed_items']}"
    )


def test_us_specific_drops_stale_non_gaap_note():
    """Task 6: `us_specific.non_gaap_eps_note` claimed the non-GAAP EPS gap
    "lives in 8-K narratives" -- true only while the pack had no 8-K
    narrative. Task 3 wired sec_narrative in, so the note is now a stale
    pointer at a gap that no longer exists and must be removed.
    `segment_revenue_note` describes a genuinely still-open gap (XBRL
    segment revenue is NOT wired by this branch) and must survive --
    the guard that this removal did not overreach."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402

    filings_rows = _synthetic_narrative_filings_rows()

    with mock.patch.object(pack_us, "run_client") as mock_run_client:
        mock_run_client.side_effect = _mock_run_client_for_narrative(filings_rows)
        result = pack_us.build_pack("memo-fetch", ["AAPL"])

    us_specific = result["us_specific"]
    assert "non_gaap_eps_note" not in us_specific, (
        "non_gaap_eps_note is stale now that sec_narrative is wired in"
    )
    assert "segment_revenue_note" in us_specific, (
        "segment_revenue_note describes a still-open gap and must survive"
    )


def test_fetch_sec_narrative_empty_selection_is_not_vacuously_failed():
    """`failed == requested` is vacuously true when `requested == 0` (an
    empty selection: nothing requested, nothing failed) — that must NOT
    read as `_status: "failed"`. select_narrative_filings never actually
    returns requested=0 through today's fixed `2 + n_quarters` policy, but
    _fetch_sec_narrative must not rely on that invariant holding forever."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402
    import sec_edgar_client  # noqa: E402

    with mock.patch.object(
        sec_edgar_client, "select_narrative_filings",
        return_value={"selected": [], "gaps": [], "requested": 0},
    ):
        result = pack_us._fetch_sec_narrative([])

    assert result["requested"] == 0
    assert result["failed"] == 0
    assert result["_status"] == "ok", (
        f"empty selection (requested=0) must not read as failed: {result}"
    )


def test_fetch_xval_source_a_wraps_cells_envelope():
    """Task 2: `_fetch_xval_source_a` selects the latest 10-K accession from
    `sec_filings` rows, acquires it, and calls `extract_statement_cells` per
    primary statement. `extract_statement_cells` returns a BARE cell list on
    success -- this must be WRAPPED into the Source-A envelope
    {accession, statement_name, cells} per statement, never passed through
    bare. A statement whose extraction returns an error dict (StatementNotFound
    surfaces this way, sec_edgar_client.py:1645) is a loud per-statement skip
    recorded in the depth-1 status -- never a crash, never a fabricated
    cells entry."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402
    import sec_edgar_client  # noqa: E402

    filings_rows = _synthetic_narrative_filings_rows()
    latest_10k_accession = "0000320193-26-100001"  # the 10-K row above

    bare_cells = [{"concept": "Revenues", "numeric_value": 100.0}]
    stub_filing = mock.MagicMock(name="filing")

    def _extract_side_effect(filing, statement_name):
        assert filing is stub_filing, "extract_statement_cells must receive the acquired filing"
        if statement_name == "IncomeStatement":
            return {
                "statement_name": statement_name,
                "error": f"statement {statement_name!r} extraction failed: StatementNotFound",
                "error_class": "statement_not_found",
            }
        return list(bare_cells)

    with mock.patch.object(
        sec_edgar_client, "_acquire_raw_filing", return_value=stub_filing
    ) as mock_acquire, mock.patch.object(
        sec_edgar_client, "extract_statement_cells", side_effect=_extract_side_effect
    ):
        result = pack_us._fetch_xval_source_a(filings_rows)

    mock_acquire.assert_called_once_with(latest_10k_accession)

    balance_entry = next(
        s for s in result["statements"] if s["statement_name"] == "BalanceSheet"
    )
    assert balance_entry == {
        "accession": latest_10k_accession,
        "statement_name": "BalanceSheet",
        "cells": bare_cells,
    }, f"bare cell list must be WRAPPED into the envelope, not passed through: {balance_entry}"

    assert result["requested"] == len(pack_us.XVAL_PRIMARY_STATEMENTS)
    assert result["succeeded"] + result["failed"] == result["requested"]
    assert any(
        item.get("statement_name") == "IncomeStatement"
        and item.get("error_class") == "statement_not_found"
        for item in result["failed_items"]
    ), f"IncomeStatement failure not recorded as a loud per-statement skip: {result['failed_items']}"
    assert not any(s["statement_name"] == "IncomeStatement" for s in result["statements"]), (
        "a failed statement must never appear as a fabricated cells entry"
    )
    assert result["_status"] == "partial", (
        "one failed statement among several succeeding must read as partial, not ok/failed"
    )


def test_latest_10k_accession_multi_10k_tiebreak_by_filing_date():
    """`_latest_10k_accession` must select the LATEST-FILED 10-K's
    accession when `filings_rows` carries more than one 10-K (e.g. a
    restated/amended-year overlap) -- max by `filingDate`, not first- or
    last-in-list order."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402

    rows = [
        {"form": "10-K", "filingDate": "2024-10-25", "accessionNumber": "0000320193-24-000123"},
        {"form": "10-K", "filingDate": "2025-10-31", "accessionNumber": "0000320193-25-000079"},
        {"form": "10-K", "filingDate": "2023-10-27", "accessionNumber": "0000320193-23-000106"},
        {"form": "10-Q", "filingDate": "2026-01-30", "accessionNumber": "0000320193-26-000001"},
    ]

    assert pack_us._latest_10k_accession(rows) == "0000320193-25-000079", (
        "must pick the latest-filed 10-K by filingDate, not list order"
    )


def test_fetch_xval_source_a_no_10k_is_wholesale_failure_not_crash():
    """When `filings_rows` has NO 10-K row, `_latest_10k_accession` returns
    None, and `_fetch_xval_source_a` must read the failed acquisition that
    follows as a WHOLESALE failure (`_status: "failed"`, every statement
    recorded in `failed_items`) -- never a vacuous/silent success with an empty
    `statements` list passed off as `_status: "ok"`.

    WHAT IS PINNED HERE IS THE READING, NOT THE BOUNDARY. `_acquire_raw_filing`
    is mocked below with a resolution-error slot, so this test says nothing
    about what the real function does with a `None` accession. That real
    behaviour has now been restored to the loud slot it always used to be
    (the cache-key computation moved back inside `_acquire_raw_filing`'s own
    `try`, 2026-08-07) and is pinned where it belongs, in
    `test_raw_filing_cache.py::test_an_accession_of_none_comes_back_as_a_loud_slot_not_a_traceback`
    -- which also asserts the network was never reached. Two earlier versions
    of this docstring each asserted the contract of their own moment in the
    present tense, and each was falsified by the next change; state where the
    pin LIVES, not what the boundary currently does. Nothing in this file
    exercises that real path."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402
    import sec_edgar_client  # noqa: E402

    filings_rows = [
        {"form": "10-Q", "filingDate": "2026-01-30", "accessionNumber": "0000320193-26-000001"},
        {"form": "8-K", "filingDate": "2026-02-02", "accessionNumber": "0000320193-26-000002"},
    ]
    acquire_error = {
        "error": "SEC EDGAR filing acquisition failed: accession None did not resolve to a filing",
        "error_class": "resolution",
    }

    with mock.patch.object(
        sec_edgar_client, "_acquire_raw_filing", return_value=acquire_error
    ) as mock_acquire:
        result = pack_us._fetch_xval_source_a(filings_rows)

    mock_acquire.assert_called_once_with(None)
    assert result["statements"] == [], "no 10-K acquired must never fabricate a statements entry"
    assert result["requested"] == len(pack_us.XVAL_PRIMARY_STATEMENTS)
    assert result["succeeded"] == 0
    assert result["failed"] == result["requested"]
    assert len(result["failed_items"]) == result["requested"], (
        "every primary statement must be recorded as a failed_items entry, one per statement"
    )
    assert all(item.get("error_class") == "resolution" for item in result["failed_items"])
    assert result["_status"] == "failed", (
        "no 10-K resolved must read as a wholesale failure, not a vacuous ok/partial"
    )


# ---------------------------------------------------------------------------
# Task 3 — pack_memo_fetch wires xval_source_a (Task 2) + xval_source_b
# (Task 1's build_companyfacts_pack) into two new top-level keys, each
# carrying a depth-1 `_status` envelope.
# ---------------------------------------------------------------------------

def _run_client_for_xval_wiring(filings_rows: list[dict], *, cik: int = 320193):
    """run_client side_effect for the Task 3 wiring test: YF calls return
    `{}` (untested here), the filings call returns `filings_rows`, DCF
    `--concept` calls return `{}`, narrative calls return a producer-shaped
    result, and the plain `--action facts` call (no `--concept`) returns a
    CIK-bearing facts result -- `pack_memo_fetch` reuses this `cik` for
    `xval_source_b` rather than re-resolving it."""
    import pack_us  # noqa: E402  (module under test, already on sys.path)

    def _side_effect(script, extra_args, timeout=pack_us.CLIENT_TIMEOUT_SECONDS):
        if script == pack_us.YF:
            return {}
        if script == pack_us.SEC:
            if "filings" in extra_args:
                return {"filings": filings_rows}
            if "--concept" in extra_args:
                return {}
            if "narrative" in extra_args:
                accession = extra_args[extra_args.index("--accession") + 1]
                return _producer_narrative(accession)
            # plain `--action facts` (no --concept): the CIK-bearing result
            return {"ticker": "AAPL", "cik": cik, "action": "facts"}
        raise AssertionError(f"unexpected run_client script: {script}")

    return _side_effect


def test_pack_memo_fetch_emits_xval_packs_with_status():
    """Task 3: pack_memo_fetch wires `build_companyfacts_pack` (Task 1) +
    `_fetch_xval_source_a` (Task 2) into two new top-level keys,
    `xval_source_a` and `xval_source_b`, each carrying a depth-1 `_status`
    envelope with a `{requested, succeeded, failed}` count-triple --
    mirroring `_fetch_sec_narrative`'s own status discipline (never require
    walking into nested `cells`/`facts` to learn completeness). A mocked
    companyfacts fetch failure must surface as a depth-1 failed `_status`
    on `xval_source_b`, not a silent empty."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402
    import sec_edgar_client  # noqa: E402

    filings_rows = _synthetic_narrative_filings_rows()
    xval_source_a_stub = {
        "statements": [{
            "accession": "0000320193-26-100001",
            "statement_name": "BalanceSheet",
            "cells": [],
        }],
        "failed_items": [], "requested": 4, "succeeded": 4, "failed": 0,
        "_status": "ok",
    }
    run_client_side_effect = _run_client_for_xval_wiring(filings_rows)

    # -- success path --
    with mock.patch.object(
        pack_us, "run_client", side_effect=run_client_side_effect
    ), mock.patch.object(
        pack_us, "_fetch_xval_source_a", return_value=dict(xval_source_a_stub)
    ), mock.patch.object(
        sec_edgar_client, "build_companyfacts_pack",
        return_value={"cik": 320193, "facts": {"us-gaap": {"Revenues": []}}},
    ) as mock_build:
        result = pack_us.build_pack("memo-fetch", ["AAPL"])

    mock_build.assert_called_once_with(320193)  # reuse the already-resolved CIK, not re-resolve it

    assert "xval_source_a" in result, "pack_memo_fetch did not emit xval_source_a"
    assert "xval_source_b" in result, "pack_memo_fetch did not emit xval_source_b"

    for section, name in (
        (result["xval_source_a"], "xval_source_a"),
        (result["xval_source_b"], "xval_source_b"),
    ):
        assert "_status" in section, f"{name} missing depth-1 _status"
        assert {"requested", "succeeded", "failed"} <= section.keys(), (
            f"{name} missing depth-1 {{requested, succeeded, failed}} triple: {section}"
        )
        assert section["succeeded"] + section["failed"] == section["requested"]

    assert result["xval_source_b"]["_status"] == "ok"
    assert result["xval_source_b"]["facts"] == {"us-gaap": {"Revenues": []}}

    # -- failure path: companyfacts fetch fails --
    with mock.patch.object(
        pack_us, "run_client", side_effect=run_client_side_effect
    ), mock.patch.object(
        pack_us, "_fetch_xval_source_a", return_value=dict(xval_source_a_stub)
    ), mock.patch.object(
        sec_edgar_client, "build_companyfacts_pack",
        return_value={
            "error": "SEC EDGAR companyfacts fetch failed for CIK 320193: boom",
            "error_class": "companyfacts_fetch_failed",
            "identifier": "320193",
        },
    ):
        failed_result = pack_us.build_pack("memo-fetch", ["AAPL"])

    xval_source_b_failed = failed_result["xval_source_b"]
    assert xval_source_b_failed["_status"] == "failed", (
        f"a companyfacts fetch failure must surface as a depth-1 failed "
        f"_status on xval_source_b, not a silent empty: {xval_source_b_failed}"
    )
    assert xval_source_b_failed["failed"] == xval_source_b_failed["requested"] > 0
    assert "error" in xval_source_b_failed, (
        "depth-1 failed status must carry the error, not swallow it"
    )


def test_statement_backfill_envelope_declares_companyfacts_source_kind(monkeypatch):
    """Task 8, docs/loom/plans/2026-07-26-us-as-reported-statement-lane.md:
    `pack_statement_backfill` is pure I/O orchestration mirroring
    `pack_kpi_topline_backfill` (pack_us.py:1043) -- it calls the producer
    (`sec_edgar_client.build_statement_backfill`) and shapes the return into
    the standard envelope, carrying the mandatory top-level `source_kind`
    literal `"xbrl-companyfacts"` (plan's §PIN — statement pack envelope).
    `kpi_xbrl_ingest.ingest_pack` reads this exact literal to assign the
    correct durable provenance label; without it every point would inherit
    a wrong default. Stubs at the producer's own module boundary
    (`sec_edgar_client.build_statement_backfill`), not an intermediate
    projection -- this repo has a recorded incident where mocking one layer
    up let a green suite certify a crash."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402
    import sec_edgar_client  # noqa: E402

    fake_facts = [
        {
            "concept": "us-gaap:Revenues",
            "period_start": "2024-01-01",
            "period_end": "2024-12-31",
            "period_kind": "duration",
            "value": 1234000000.0,
            "unit": "USD",
            "accession": "0000320193-25-000079",
            "filed": "2025-10-31",
            "form": "10-K",
        }
    ]
    fake_coverage = {"skipped_rows": []}
    calls: list[str] = []

    def fake_backfill(ticker):
        calls.append(ticker)
        return {
            "pack": "statement-backfill",
            "ticker": ticker.upper(),
            "fetched_at": "2026-07-25T00:00:00+00:00",
            "source_kind": "xbrl-companyfacts",
            "company": "APPLE INC",
            "facts": fake_facts,
            "coverage": fake_coverage,
        }

    monkeypatch.setattr(sec_edgar_client, "build_statement_backfill", fake_backfill)

    payload = pack_us.pack_statement_backfill("aapl")

    assert payload["pack"] == "statement-backfill"
    assert payload["ticker"] == "AAPL"
    assert payload["source_kind"] == "xbrl-companyfacts"
    assert payload["company"] == "APPLE INC"
    assert payload["facts"] == fake_facts
    assert payload["coverage"] == fake_coverage
    assert "fetched_at" in payload
    assert calls == ["aapl"]


def test_statement_backfill_source_kind_overrides_producer_disagreement(monkeypatch):
    """The wrapper's docstring guarantees the envelope carries the
    top-level `source_kind` literal `"xbrl-companyfacts"` -- a promise the
    old wholesale `{**envelope, **result}` merge does NOT keep: the
    producer's own `source_kind` key, if present, wins over the envelope's
    (dict-merge semantics -- the right-hand operand's keys always
    override the left-hand's). Stubs a producer success payload with a
    DIFFERENT `source_kind` (a producer bug/regression -- `build_statement_
    backfill` has exactly one companyfacts code path and no legitimate
    reason to ever emit anything else) and asserts the WRAPPER's own
    literal wins. The wrapper, not the producer, is this lane's single
    source of truth for the provenance label -- matching
    `pack_kpi_topline_backfill`, whose producer (`build_top_line_backfill`)
    never even sets `source_kind`; the wrapper alone owns it there too."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402
    import sec_edgar_client  # noqa: E402

    fake_facts = [{"concept": "us-gaap:Revenues", "value": 1.0}]
    fake_coverage = {"skipped_rows": []}

    def fake_backfill_wrong_source_kind(ticker):
        return {
            "pack": "statement-backfill",
            "ticker": ticker.upper(),
            "fetched_at": "2026-07-25T00:00:00+00:00",
            "source_kind": "xbrl-dimensional",  # disagrees with the wrapper
            "company": "APPLE INC",
            "facts": fake_facts,
            "coverage": fake_coverage,
        }

    monkeypatch.setattr(
        sec_edgar_client, "build_statement_backfill", fake_backfill_wrong_source_kind
    )

    payload = pack_us.pack_statement_backfill("AAPL")

    assert payload["source_kind"] == "xbrl-companyfacts"


def test_statement_backfill_source_kind_survives_producer_omission(monkeypatch):
    """Companion to the disagreement test above: even a producer payload
    that OMITS `source_kind` entirely must still resolve to the wrapper's
    own `"xbrl-companyfacts"` literal, proving the docstring's guarantee
    is exercised independently of whatever the producer happens to emit
    (or not emit) -- not trusted as a coincidence between this module and
    `sec_edgar_client.build_statement_backfill`."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402
    import sec_edgar_client  # noqa: E402

    fake_facts = [{"concept": "us-gaap:Revenues", "value": 1.0}]
    fake_coverage = {"skipped_rows": []}

    def fake_backfill_no_source_kind(ticker):
        return {
            "pack": "statement-backfill",
            "ticker": ticker.upper(),
            "fetched_at": "2026-07-25T00:00:00+00:00",
            # deliberately no `source_kind` key
            "company": "APPLE INC",
            "facts": fake_facts,
            "coverage": fake_coverage,
        }

    monkeypatch.setattr(
        sec_edgar_client, "build_statement_backfill", fake_backfill_no_source_kind
    )

    payload = pack_us.pack_statement_backfill("AAPL")

    assert payload["source_kind"] == "xbrl-companyfacts"


def test_statement_backfill_pack_passes_through_any_producer_error_slot(monkeypatch):
    """A producer error slot rides through the envelope verbatim with no
    `facts` key -- structurally, not by enumerating known error classes.
    `build_statement_backfill` is being extended concurrently (a CIK-history
    guard adding one more error shape), so this stubs a NOVEL error shape
    (keys no current error class carries) to prove the wrapper doesn't
    special-case any particular error class."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402
    import sec_edgar_client  # noqa: E402

    def fake_backfill(ticker):
        return {
            "error": f"CIK history conflict for {ticker}",
            "error_class": "cik_history_conflict",
            "identifier": ticker,
            "prior_cik": "0000320193",
            "current_cik": "0000320194",
        }

    monkeypatch.setattr(sec_edgar_client, "build_statement_backfill", fake_backfill)

    payload = pack_us.pack_statement_backfill("AAPL")

    assert payload["error"] == "CIK history conflict for AAPL"
    assert payload["error_class"] == "cik_history_conflict"
    assert payload["prior_cik"] == "0000320193"
    assert payload["current_cik"] == "0000320194"
    assert "facts" not in payload


def test_build_pack_dispatches_statement_backfill(monkeypatch):
    """Registration gap: `pack_statement_backfill` (Task 8) was never wired
    into `build_pack`'s dispatch, mirroring `kpi-topline-backfill`'s branch
    (pack_us.py:1367). Without it `build_pack("statement-backfill", ...)`
    falls through to the generic `unknown pack` ValueError and the lane is
    unreachable from the CLI facade."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402

    calls: list[str] = []

    def fake_pack_statement_backfill(ticker):
        calls.append(ticker)
        return {"pack": "statement-backfill", "ticker": ticker}

    monkeypatch.setattr(
        pack_us, "pack_statement_backfill", fake_pack_statement_backfill
    )

    result = pack_us.build_pack("statement-backfill", ["AAPL"])

    assert calls == ["AAPL"]
    assert result == {"pack": "statement-backfill", "ticker": "AAPL"}


def test_reconstruct_pack_is_registered_and_us_only(monkeypatch, capsys):
    """Task 9, docs/loom/plans/2026-07-26-as-filed-statement-reconstruction.md:
    the as-filed reconstruction verb must be REACHABLE from the CLI facade, and
    reachable ONLY for US filers. Three claims, because two of them can hold
    while the third silently does not:

      1. `reconstruct` is in `pack_us.SUPPORTED_PACKS` — without it `build_pack`
         raises the generic `unknown pack` ValueError and the lane is dead.
      2. It DISPATCHES: `build_pack("reconstruct", ["KO"])` reaches
         `pack_reconstruct`. Registration alone is not dispatch — `statement-
         backfill` shipped registered-but-undispatched (see
         `test_build_pack_dispatches_statement_backfill`), so this is a
         measured failure mode in this exact module, not a hypothetical.
      3. It is REFUSED (exit 64) for a non-US market by the facade's
         `US_ONLY_PACKS` guard, which names the refusal as a market-
         availability problem rather than letting `pack_tw.build_pack`'s
         generic `unknown pack` ValueError misreport it as a pack-name typo.

    The US arm asserts the guard does NOT fire for a US ticker — a guard that
    rejects every market would satisfy claim 3 while making the verb
    unreachable everywhere, so the negative case is what proves the guard is
    market-scoped rather than blanket.

    Offline: the `.TW` arm returns before any market module is called, and the
    US arm's producer is stubbed, so neither reaches SEC EDGAR.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack  # noqa: E402
    import pack_us  # noqa: E402

    # --- 1. registered ---
    assert "reconstruct" in pack_us.SUPPORTED_PACKS, (
        f"reconstruct is not registered: {pack_us.SUPPORTED_PACKS}"
    )

    # --- 2. dispatches through build_pack ---
    calls: list[str] = []

    def fake_pack_reconstruct(ticker):
        calls.append(ticker)
        return {"pack": "reconstruct", "ticker": ticker}

    monkeypatch.setattr(pack_us, "pack_reconstruct", fake_pack_reconstruct)

    result = pack_us.build_pack("reconstruct", ["KO"])
    assert calls == ["KO"]
    assert result == {"pack": "reconstruct", "ticker": "KO"}

    # Ticker-count validation, mirroring every other single-heavy pack.
    with pytest.raises(ValueError, match=r"requires exactly one ticker \(single, heavy\)"):
        pack_us.build_pack("reconstruct", ["KO", "PEP"])

    # --- 3. refused for a non-US market, at the facade ---
    assert "reconstruct" in pack.US_ONLY_PACKS, (
        f"reconstruct is not declared US-only: {sorted(pack.US_ONLY_PACKS)}"
    )

    exit_code = pack.main(["--ticker", "2330.TW", "--pack", "reconstruct"])
    assert exit_code == pack.EXIT_USAGE_ERROR
    refusal = json.loads(capsys.readouterr().out)["_status"]
    assert refusal["status"] == "usage_error"
    assert "US-only" in refusal["message"], (
        f"refusal must name market availability, not a pack-name typo: {refusal}"
    )

    # ...and NOT refused for a US ticker (the guard is market-scoped, not blanket).
    calls.clear()
    us_exit = pack.main(["--ticker", "KO", "--pack", "reconstruct", "--quiet"])
    capsys.readouterr()
    assert calls == ["KO"], "the US arm must reach the producer, not be refused"
    assert us_exit != pack.EXIT_USAGE_ERROR


def _reconstruct_row(concept, label, **over):
    """One `get_statement` presentation row, shaped as the live surface
    carries it (verified key set, plan Task 3 Decision Log). Defaults are a
    real statement line: undimensioned, non-placeholder, non-abstract."""
    row = {
        "concept": concept, "label": label, "level": 0,
        "weight": 1.0, "calculation_parent": None,
        "values": {"FY2017": 1.0}, "is_abstract": False,
        "has_dimension_children": False,
    }
    row.update(over)
    return row


class _FakeXBRL:
    def __init__(self, rows):
        self.presentation_roles = ["http://ko.com/role/ConsolidatedStatementsOfIncome"]
        self._rows = rows

    def get_statement(self, role):
        return list(self._rows)


class _FakeFiling:
    """Answers exactly the two-call surface `statements_for` documents as its
    whole input contract (`.xbrl()` -> `presentation_roles` + `get_statement`)."""

    def __init__(self, rows):
        self._rows = rows

    def xbrl(self):
        return _FakeXBRL(self._rows)


def test_pack_reconstruct_emits_per_accession_statements_with_status(monkeypatch):
    """Task 9's producer body: one company, N accessions, the three statements
    per accession as the filer declared them.

    Stubs at the PRODUCERS' OWN boundaries (`resolve_cik` / `list_filings` /
    `_acquire_raw_filing`) and lets the REAL `statements_for` run over
    live-shaped rows -- this repo has a recorded incident where mocking one
    layer up let a green suite certify a crash, and mocking the reconstruction
    itself would leave the seam this task exists to build entirely unexercised.

    Four claims:
      1. the filer's OWN label and concept survive to the payload, in
         presentation order (labels are display-only but they are what the
         reader recognises; brief §Series identity);
      2. a failed acquisition is a LOUD per-accession skip in `failed_items`,
         never a fabricated statements entry -- mirroring
         `_fetch_xval_source_a`'s already-pinned discipline;
      3. the depth-1 `{requested, succeeded, failed}` triple reconciles and
         `_status` reads `partial`, so the facade's structural walk sees the
         degradation without descending into `filings`;
      4. the payload is JSON-SERIALIZABLE. `statements_for` returns frozen
         DATACLASSES (`Statements` / `Line`); `pack.py` ends in
         `json.dumps(...)`, which cannot serialize them. Without an explicit
         projection the verb crashes at the last line of a ~40s run, and no
         assertion on shape alone would catch it.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402
    import sec_edgar_client  # noqa: E402

    rows = [
        _reconstruct_row("us-gaap:IncomeStatementAbstract", "INCOME", is_abstract=True),
        _reconstruct_row("us-gaap:Revenues", "NET OPERATING REVENUES"),
        _reconstruct_row("ko:UnusualOrInfrequentItemOperating", "OTHER OPERATING CHARGES"),
        # A segment slice interleaved in the same role — must not leak through.
        _reconstruct_row("us-gaap:Revenues", "Asia Pacific", is_dimension=True),
    ]

    good = "0000021344-18-000008"
    bad = "0000021344-17-000009"
    acquire_error = {
        "error": f"SEC EDGAR filing acquisition failed: accession {bad!r} did not resolve",
        "error_class": "resolution",
    }

    monkeypatch.setattr(sec_edgar_client, "resolve_cik", lambda t: {"cik": 21344})
    monkeypatch.setattr(
        sec_edgar_client, "list_filings",
        lambda cik, forms, limit, min_filing_date=None: [
            {"form": "10-K", "filingDate": "2018-02-23", "accessionNumber": good},
            {"form": "10-K", "filingDate": "2017-02-24", "accessionNumber": bad},
        ],
    )
    monkeypatch.setattr(
        sec_edgar_client, "_acquire_raw_filing",
        lambda accession: _FakeFiling(rows) if accession == good else acquire_error,
    )

    envelope = pack_us.pack_reconstruct("ko")

    assert envelope["pack"] == "reconstruct"
    assert envelope["ticker"] == "KO"
    # Nested under one section so the facade's one-level walk honours the
    # self-declared `_status`; see
    # `test_reconstruct_clean_run_classifies_ok_through_the_facade`.
    payload = envelope["reconstruction"]

    # 1. the filer's own labels + concepts, in presentation order
    assert len(payload["filings"]) == 1
    filing = payload["filings"][0]
    assert filing["accession"] == good
    income = filing["statements"]["income"]
    assert [line["label"] for line in income] == [
        "NET OPERATING REVENUES", "OTHER OPERATING CHARGES"
    ], f"labels/order/segment-leak: {income}"
    assert income[1]["concept"] == "ko:UnusualOrInfrequentItemOperating", (
        "the filer's own custom concept must survive — no fixed concept list "
        "could contain it (brief §Decision)"
    )

    # 2. the failed acquisition is loud, and fabricates nothing
    assert [item["accession"] for item in payload["failed_items"]] == [bad]
    assert payload["failed_items"][0]["error_class"] == "resolution"
    assert all(f["accession"] != bad for f in payload["filings"]), (
        "a failed acquisition must never appear as a fabricated statements entry"
    )

    # 3. depth-1 triple reconciles; degradation visible without descending
    assert payload["requested"] == 2
    assert payload["succeeded"] == 1
    assert payload["failed"] == 1
    assert payload["succeeded"] + payload["failed"] == payload["requested"]
    assert payload["_status"] == "partial"

    # 4. the facade's final `json.dumps` must not crash on a dataclass
    json.dumps(envelope)


def _stub_reconstruct_producers(monkeypatch, accessions_to_rows):
    """Stub the three `sec_edgar_client` producers `pack_reconstruct` calls,
    from an {accession: rows-or-error-slot} map. Ordered as given."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import sec_edgar_client  # noqa: E402

    monkeypatch.setattr(
        sec_edgar_client, "resolve_cik",
        lambda t: {"cik": 21344, "title": "COCA COLA CO"},
    )
    monkeypatch.setattr(
        sec_edgar_client, "list_filings",
        lambda cik, forms, limit, min_filing_date=None: [
            {"form": "10-K", "filingDate": "2026-02-20", "accessionNumber": a}
            for a in accessions_to_rows
        ],
    )
    monkeypatch.setattr(
        sec_edgar_client, "_acquire_raw_filing",
        lambda accession: (
            accessions_to_rows[accession]
            if isinstance(accessions_to_rows[accession], dict)
            else _FakeFiling(accessions_to_rows[accession])
        ),
    )


def test_reconstruct_clean_run_classifies_ok_through_the_facade(monkeypatch):
    """A run in which EVERY filing reconstructed must classify `ok` through
    `pack._classify_result` -- the real structural reader, not just the
    producer's own opinion of itself.

    LIVE DOGFOOD DEFECT, 2026-07-26 (KO, real SEC fetch): 4 of 4 filings
    reconstructed, `failed_items == []`, the producer self-declared `_status:
    "ok"` -- and the facade still reported `partial`, exit 2. Two causes, both
    invisible to any test that only inspects the producer's own return:

      1. `_list_section_status` reads an EMPTY LIST as `"failed"` (deliberately
         -- for a ticker fan-out, zero rows means nothing came back). A
         top-level `failed_items: []` is the SUCCESS case, and it was being
         read as the failure case.
      2. `main()` assigns `output["_status"] = _status_block(...)`, so a
         producer's own TOP-LEVEL `_status` is overwritten before anyone reads
         it. Depth-1 status belongs on a named SECTION, which is where every
         other pack in this module puts it (`sec_narrative`, `xval_source_a`).

    The degraded arm is asserted in the same test on purpose: a "fix" that
    stops reporting partial at all would satisfy the ok arm while making real
    degradation invisible -- the strictly more dangerous direction, and the
    one this pack's whole failure-honesty contract exists to prevent.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack  # noqa: E402
    import pack_us  # noqa: E402

    rows = [_reconstruct_row("us-gaap:Revenues", "Net Operating Revenues")]

    # --- every filing reconstructed ---
    _stub_reconstruct_producers(monkeypatch, {"0001628280-26-010047": rows})
    clean = pack_us.pack_reconstruct("ko")

    status, failed_sections = pack._classify_result(clean)
    assert status == "ok", (
        f"a 1-for-1 clean reconstruction must not read as {status!r} "
        f"(failed_sections={failed_sections})"
    )

    # --- one filing failed to acquire: degradation must still be visible ---
    _stub_reconstruct_producers(monkeypatch, {
        "0001628280-26-010047": rows,
        "0000021344-25-000011": {"error": "did not resolve", "error_class": "resolution"},
    })
    degraded = pack_us.pack_reconstruct("ko")

    degraded_status, degraded_sections = pack._classify_result(degraded)
    assert degraded_status == "partial", (
        f"a failed acquisition must stay visible to the facade, got "
        f"{degraded_status!r}"
    )
    assert degraded_sections, "the degraded section must be named, not just counted"


def test_reconstruct_reads_enough_filings_for_the_briefs_ten_years():
    """`RECONSTRUCT_ANNUAL_FILINGS` must be enough to actually deliver the
    brief's Smallest End State: "the three statements as filed, for 10+ years".

    MEASURED 2026-07-26, live KO run: FOUR 10-Ks yielded SIX distinct annual
    periods (2020-2025), not ten. Consecutive 10-Ks overlap by their two
    comparative years, so N filings yield N+2 distinct years -- not 3N. The
    brief's own arithmetic ("Ten years is ~4 filings (each 10-K carries three
    comparative years)", §Users) multiplies where it should overlap, and the
    plan's cost note inherits it; both are refuted by the measurement rather
    than reinterpreted. This test is the guard that the constant tracks the
    REQUIREMENT (10+ years) instead of the refuted estimate (4 filings).
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402

    years_yielded = pack_us.RECONSTRUCT_ANNUAL_FILINGS + 2
    assert years_yielded >= 10, (
        f"{pack_us.RECONSTRUCT_ANNUAL_FILINGS} annual filings yield only "
        f"{years_yielded} distinct years (N+2, measured); the brief asks for 10+"
    )


# Money in the fixtures below is stated in DOLLARS, not millions, because the
# rounding interval is computed from the filer's declared `decimals` (-6 =
# reported to the nearest million) against the fact's own magnitude. A fixture
# stating 35410 with decimals -6 would give every group a tolerance 40x its own
# figures and collapse the four statuses into one.
_M = 1_000_000


def _sampled_era_rows():
    """One income statement whose four declared groups come out as four
    DIFFERENT sum-check statuses — the distinction this envelope must carry.

    Group by group, and the arithmetic is stated so a reader can argue with it
    rather than trust it:

      GrossProfit          35,410 - 13,256 = 22,154 against a reported 22,155.
                           1M off, inside the 1.5M its own declared precision
                           permits ((n+1)/2 units at decimals -6, n=2) ->
                           `within_rounding`. THIS IS THE ONE THAT MATTERS: an
                           exact comparison calls it broken, and 24 of the
                           committed capture's 27 disagreements are this shape
                           (plan Decision Log, Task 4 -> Task 8, "the raw count
                           overstates broken filer arithmetic ~8x").
      OperatingExpenses    12,000 + 1,000 = 13,000 against a reported 18,000.
                           5,000M off, nowhere near the interval -> `disagrees`.
      NonoperatingIncome   its only child carries no value for the period, so
                           no sum was computed at all -> `incomplete`. A
                           comparison that could not be made is not one that
                           failed.
      NetIncomeLoss        6,890 - 5,560 = 1,330 exactly -> `agrees`.
    """
    return [
        _reconstruct_row(
            "us-gaap:Revenues", "NET OPERATING REVENUES",
            values={"FY2017": 35410 * _M}, decimals={"FY2017": -6},
            calculation_parent="us-gaap:GrossProfit", weight=1.0,
            balance="credit",
        ),
        _reconstruct_row(
            "us-gaap:CostOfGoodsSold", "COST OF GOODS SOLD",
            values={"FY2017": 13256 * _M}, decimals={"FY2017": -6},
            calculation_parent="us-gaap:GrossProfit", weight=-1.0,
            balance="debit",
        ),
        _reconstruct_row(
            "us-gaap:GrossProfit", "GROSS PROFIT",
            values={"FY2017": 22155 * _M}, decimals={"FY2017": -6}, weight=None,
        ),
        _reconstruct_row(
            "us-gaap:SellingGeneralAndAdministrativeExpense",
            "SELLING, GENERAL AND ADMINISTRATIVE EXPENSES",
            values={"FY2017": 12000 * _M}, decimals={"FY2017": -6},
            calculation_parent="us-gaap:OperatingExpenses", weight=1.0,
        ),
        _reconstruct_row(
            "ko:UnusualOrInfrequentItemOperating", "OTHER OPERATING CHARGES",
            values={"FY2017": 1000 * _M}, decimals={"FY2017": -6},
            calculation_parent="us-gaap:OperatingExpenses", weight=1.0,
        ),
        _reconstruct_row(
            "us-gaap:OperatingExpenses", "TOTAL OPERATING EXPENSES",
            values={"FY2017": 18000 * _M}, decimals={"FY2017": -6}, weight=None,
        ),
        _reconstruct_row(
            "us-gaap:InterestExpense", "INTEREST EXPENSE",
            values={"FY2017": None}, decimals={"FY2017": -6},
            calculation_parent="us-gaap:NonoperatingIncomeExpense", weight=-1.0,
        ),
        _reconstruct_row(
            "us-gaap:NonoperatingIncomeExpense", "OTHER INCOME (LOSS) - NET",
            values={"FY2017": 500 * _M}, decimals={"FY2017": -6}, weight=None,
        ),
        _reconstruct_row(
            "us-gaap:IncomeLossBeforeIncomeTaxes", "INCOME BEFORE INCOME TAXES",
            values={"FY2017": 6890 * _M}, decimals={"FY2017": -6},
            calculation_parent="us-gaap:NetIncomeLoss", weight=1.0,
        ),
        _reconstruct_row(
            "us-gaap:IncomeTaxExpenseBenefit", "INCOME TAXES",
            values={"FY2017": 5560 * _M}, decimals={"FY2017": -6},
            calculation_parent="us-gaap:NetIncomeLoss", weight=-1.0,
        ),
        _reconstruct_row(
            "us-gaap:NetIncomeLoss", "CONSOLIDATED NET INCOME",
            values={"FY2017": 1330 * _M}, decimals={"FY2017": -6}, weight=None,
        ),
    ]


def _post_sample_era_rows():
    """A modern filing whose one declared group reconciles exactly, so the era
    breakdown has something OTHER than the failing era to report. A report
    showing one era says nothing about whether the rate varies by era, which is
    the whole question the brief says must be measured rather than assumed."""
    return [
        _reconstruct_row(
            "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "Net operating revenues",
            values={"FY2025": 47000 * _M}, decimals={"FY2025": -6},
            calculation_parent="us-gaap:GrossProfit", weight=1.0,
            balance="credit",
        ),
        _reconstruct_row(
            "us-gaap:CostOfGoodsAndServicesSold", "Cost of goods sold",
            values={"FY2025": 18000 * _M}, decimals={"FY2025": -6},
            calculation_parent="us-gaap:GrossProfit", weight=-1.0,
            balance="debit",
        ),
        _reconstruct_row(
            "us-gaap:GrossProfit", "Gross profit",
            values={"FY2025": 29000 * _M}, decimals={"FY2025": -6}, weight=None,
        ),
    ]


def _stub_reconstruct_filings(monkeypatch, dated_rows):
    """Stub the three `sec_edgar_client` producers from an ordered
    {accession: (filingDate, rows)} map, so a test can place each filing in a
    KNOWN era. `_stub_reconstruct_producers` dates every filing 2026-02-20,
    which puts a whole run in one era and cannot exercise the breakdown."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import sec_edgar_client  # noqa: E402

    monkeypatch.setattr(
        sec_edgar_client, "resolve_cik",
        lambda t: {"cik": 21344, "title": "COCA COLA CO"},
    )
    monkeypatch.setattr(
        sec_edgar_client, "list_filings",
        lambda cik, forms, limit, min_filing_date=None: [
            {"form": "10-K", "filingDate": date, "accessionNumber": accession}
            for accession, (date, _rows) in dated_rows.items()
        ],
    )
    monkeypatch.setattr(
        sec_edgar_client, "_acquire_raw_filing",
        lambda accession: _FakeFiling(dated_rows[accession][1]),
    )


def test_reconstruct_envelope_carries_the_resolution_report_and_sum_checks(monkeypatch):
    """The arc's central promise must reach the only surface that ships it.

    WHOLE-BRANCH REVIEW FINDING, 2026-07-26: "Inside the library the
    distinction is clean: `Cell.state` separates `not_presented` from
    `not_tagged`, `SumCheck.status` separates `within_rounding` from
    `disagrees`, `Unresolved` carries five distinct codes. NONE OF IT SHIPS."
    `pack_reconstruct` emitted raw `Line`s only, and `resolution_report` had
    zero references outside its own module and tests — so a reader holding this
    verb's output still could not tell a pipeline defect from an accounting
    fact, which is the brief's reason for existing (§Problem, "It cannot say
    WHY a cell is empty").

    Four claims, each the difference between a typed answer and a blank:

      1. THE PER-ERA COUNTS SHIP. The 63-of-65 resolution rate was measured on
         filings FILED 2016-2018 only and a 10-year run spans years nobody
         sampled (brief §"A limit this brief must not overclaim"), so a single
         run-wide rate is the overclaim the report exists to prevent. Both eras
         present here, with different outcomes.
      2. EVERY UNRESOLVED STATEMENT NAMES ITS REASON, and the detail names the
         group, so the reader can go argue with the filing rather than with a
         count.
      3. `within_rounding` IS DISTINCT FROM `disagrees` AND `incomplete`.
         Asserted as an exact four-way census rather than as "disagrees == 1",
         because collapsing the rounding residue into the disagreement is the
         measured ~8x overstatement (plan Decision Log, Task 4 -> Task 8) and a
         one-sided assertion passes right through it.
      4. THE PAYLOAD SERIALIZES WITHOUT `default=str`. Every figure on a
         `SumCheck` is a `Decimal` and `json.dumps` raises on one. The facade
         does pass `default=str`, which would paper over this at the last line
         of a ~85s run — and would also silently accept a float, the one
         representation this arc's arithmetic rules out. Pinned here on a bare
         `json.dumps`, so the projection has to be explicit.

    Plus the deliberate omission: `cell_state` is NOT in this envelope, and
    `pack_reconstruct` must SAY so. An undocumented absence leaves a reader
    assuming the four-way taxonomy is present — the same undifferentiated
    blank one layer up.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402

    _stub_reconstruct_filings(monkeypatch, {
        "0000021344-18-000008": ("2018-02-23", _sampled_era_rows()),
        "0000021344-26-000011": ("2026-02-20", _post_sample_era_rows()),
    })

    envelope = pack_us.pack_reconstruct("ko")
    verification = envelope["reconstruction"]["verification"]

    # 1. the per-era breakdown, both eras, different outcomes
    by_era = {tally["era"]: tally for tally in verification["by_era"]}
    assert sorted(by_era) == ["post_2018", "sampled_2016_2018"], (
        f"both eras in the run must be reported: {verification['by_era']}"
    )
    assert (by_era["sampled_2016_2018"]["resolved"],
            by_era["sampled_2016_2018"]["unresolved"]) == (0, 1)
    assert (by_era["post_2018"]["resolved"],
            by_era["post_2018"]["unresolved"]) == (1, 0)
    assert by_era["sampled_2016_2018"]["reasons"] == [
        {"reason": "sums_do_not_reconcile", "count": 1}
    ], f"the era's failure reasons must ride with its counts: {by_era}"

    # 2. the unresolved statement names its reason AND its group
    unresolved = [s for s in verification["statements"] if not s["resolved"]]
    assert len(unresolved) == 1, f"expected one unresolved statement: {unresolved}"
    assert unresolved[0]["filing_date"] == "2018-02-23"
    assert unresolved[0]["kind"] == "income"
    assert unresolved[0]["groups_checked"] == 4
    assert unresolved[0]["groups_incomplete"] == 1
    assert [r["reason"] for r in unresolved[0]["reasons"]] == ["sums_do_not_reconcile"]
    assert "us-gaap:OperatingExpenses" in unresolved[0]["reasons"][0]["detail"], (
        "a reason code with no group named sends the reader nowhere: "
        f"{unresolved[0]['reasons'][0]}"
    )

    # 3. the four-way census — within_rounding is its own answer
    assert verification["sum_checks"]["by_status"] == {
        "agrees": 2, "within_rounding": 1, "disagrees": 1, "incomplete": 1,
    }, f"the four statuses must stay four: {verification['sum_checks']}"

    disagreements = verification["sum_checks"]["disagreements"]
    assert [d["parent"] for d in disagreements] == ["us-gaap:OperatingExpenses"], (
        "only the genuine disagreement belongs here — a within_rounding group "
        f"listed as one rebuilds the ~8x overstatement: {disagreements}"
    )
    # Exact decimal TEXT, digit for digit. The trailing ".0" on the computed
    # figures is not noise and must not be normalised away: it is the scale
    # `Decimal` carried through Sigma(child x weight) at the filer's own
    # weight of 1.0, and `str` is the only projection that neither rounds it
    # nor routes it back through a binary float.
    assert disagreements[0]["reported"] == "18000000000"
    assert disagreements[0]["computed"] == "13000000000.0"
    assert disagreements[0]["difference"] == "-5000000000.0"
    assert disagreements[0]["tolerance"] == "1500000", (
        "the interval the filer's OWN declared precision permits must ride "
        "with the verdict, so a reader can argue with the interval too: "
        f"{disagreements[0]}"
    )
    for figure in ("reported", "computed", "difference", "tolerance"):
        assert isinstance(disagreements[0][figure], str), (
            f"{figure} must be exact decimal TEXT, never a float: "
            f"{disagreements[0][figure]!r}"
        )

    # 4. serializes with no `default=str` fallback
    json.dumps(envelope)

    # the omission is stated, not left to assumption
    doc = pack_us.pack_reconstruct.__doc__
    assert "cell_state" in doc and "derive_spine_as_filed" in doc, (
        "the envelope carries no per-cell typing; a reader must be TOLD that "
        "and told where it does live, rather than assuming the four-way "
        "taxonomy is present"
    )


def test_reconstruct_verification_failure_degrades_but_keeps_the_statements(monkeypatch):
    """Adding verification must not turn a working verb into a crashing one.

    `kpi_us_statement_check` REFUSES rather than guessing, deliberately and by
    its own docstring: a row presented twice under one calculation parent with
    disagreeing figures raises, and so does a filing date with no readable
    year. Both abort the whole run — "a caller running 56 filers should expect
    to lose the run and not one statement". That posture is right for an
    ORACLE, and wrong for this pack to inherit unexamined: the reconstruction
    of every other filing already succeeded, and letting the exception out
    would trade ~85s of good statements for a traceback, making the arc's
    benefit a REGRESSION in the verb that already worked.

    So the failure is contained to the section it belongs to, and made loud
    there:

      1. the statements still ship — the fidelity layer did its job and is not
         held hostage by the verification layer's refusal;
      2. `verification` carries the refusal's own message, not a bare flag; a
         reader must be able to see WHICH row the oracle refused;
      3. the degradation reaches the facade. This is the part that is not
         obvious: `_section_status` honours a section's self-declared
         `_status` and then NEVER descends, so a `verification._status` nested
         inside `reconstruction` is structurally invisible. The failure has to
         be folded into the `reconstruction` section's own `_status` or it is
         silent — asserted through `pack._classify_result`, the real reader,
         rather than through this pack's opinion of itself.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack  # noqa: E402
    import pack_us  # noqa: E402

    refused_rows = [
        _reconstruct_row(
            "us-gaap:Revenues", "NET OPERATING REVENUES",
            values={"FY2017": 35410 * _M},
            calculation_parent="us-gaap:GrossProfit", weight=1.0,
        ),
        # Same concept, same parent, a DIFFERENT figure. De-duplication keeps
        # the first row, so one of these numbers would vanish from the check —
        # the oracle refuses to pick.
        _reconstruct_row(
            "us-gaap:Revenues", "NET OPERATING REVENUES (RESTATED)",
            values={"FY2017": 41863 * _M},
            calculation_parent="us-gaap:GrossProfit", weight=1.0,
        ),
        _reconstruct_row(
            "us-gaap:GrossProfit", "GROSS PROFIT",
            values={"FY2017": 22155 * _M}, weight=None,
        ),
    ]

    _stub_reconstruct_filings(monkeypatch, {
        "0000021344-18-000008": ("2018-02-23", refused_rows),
    })

    envelope = pack_us.pack_reconstruct("ko")
    section = envelope["reconstruction"]

    # 1. the statements survived the verification failure
    assert [line["label"] for line in section["filings"][0]["statements"]["income"]] == [
        "NET OPERATING REVENUES", "NET OPERATING REVENUES (RESTATED)", "GROSS PROFIT"
    ], "the reconstruction must not be discarded because the check refused"

    # 2. the refusal is reported with its own message, under the `error` key
    #    this repo's `_has_error_marker` already treats as the failure signal —
    #    not a second private flag beside it
    verification = section["verification"]
    assert verification["error_class"] == "verification"
    assert "us-gaap:Revenues" in verification["error"], (
        f"the refused row must be nameable from the report: {verification}"
    )

    # 3. the degradation reaches the facade, which never descends past
    #    `reconstruction`'s own self-declared status
    assert section["_status"] == "partial", (
        "a nested `verification._status` is invisible to `_section_status`; "
        "the section's own status has to carry it"
    )
    status, failed_sections = pack._classify_result(envelope)
    assert status == "partial", (
        f"a run whose verification refused must not read as {status!r}"
    )
    assert "reconstruction" in failed_sections

    json.dumps(envelope)


def test_missing_client_dependency_names_what_to_pass(monkeypatch, capsys):
    """A dependency-free invocation must fail with a message naming what to
    pass -- never a bare `ModuleNotFoundError`.

    MEASURED, not hypothetical: the sibling as-reported lane's live dogfood
    died on `ModuleNotFoundError: No module named 'requests'` until both client
    deps were supplied on the `uv run` invocation (Gotcha trailer, PR #619,
    2026-07-26). `pack.py` is a ZERO-DEPENDENCY facade by design -- the market
    clients' deps are supplied per-invocation via `--with` and are deliberately
    never imported by the facade -- so this failure is reachable by every SEC
    pack, and the facade is the one place that knows the invocation contract.

    The raw traceback is KEPT alongside the message. A guidance string that
    replaced the cause would trade one opaque failure for another: the message
    says what to do, the traceback still says what actually happened.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack  # noqa: E402
    import pack_us  # noqa: E402

    def missing_requests(pack_name, tickers):
        # `name=` is what the IMPORT SYSTEM populates on a real failed import
        # (`sec_edgar_client`'s top-level `import requests`), so the stub sets
        # it too -- a hand-built exception missing `name` would let an
        # implementation that only reads `str(exc)` pass a test the real
        # failure shape would not exercise.
        raise ModuleNotFoundError("No module named 'requests'", name="requests")

    monkeypatch.setattr(pack_us, "build_pack", missing_requests)

    exit_code = pack.main(["--ticker", "KO", "--pack", "reconstruct", "--quiet"])
    status = json.loads(capsys.readouterr().out)["_status"]

    assert exit_code == pack.EXIT_FAILED
    assert status["status"] == "failed"

    message = status.get("message", "")
    assert "requests" in message, f"must name the MISSING module: {message}"
    assert "--with" in message, f"must name the fix, not just the symptom: {message}"
    assert "edgartools" in message, (
        f"must name the SEC lane's other client dep too — supplying only the "
        f"one named in the error just moves the failure one import later "
        f"(exactly how PR #619's dogfood went): {message}"
    )
    assert "ModuleNotFoundError" in status.get("traceback", ""), (
        "the real cause must survive alongside the guidance, not be replaced by it"
    )


def test_reconstruct_exit_code_matches_the_run_through_main(monkeypatch, capsys):
    """The nesting fix, pinned at the surface the live defect was SEEN at.

    `test_reconstruct_clean_run_classifies_ok_through_the_facade` pins
    `_classify_result`, which is the mechanism -- but the 2026-07-26 KO run
    reported the defect as **exit 2** on a clean 8-for-8 reconstruction, and no
    test crossed `main()` to reach an exit code. A future change to how
    `main()` maps status -> exit, or to which section carries `_status`, would
    reintroduce the observed symptom while the mechanism test stayed green.

    Both arms again, for the same reason as the classifier test: a change that
    made everything exit 0 would satisfy the clean arm while hiding real
    degradation, which is the more dangerous direction.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack  # noqa: E402

    rows = [_reconstruct_row("us-gaap:Revenues", "Net Operating Revenues")]

    _stub_reconstruct_producers(monkeypatch, {"0001628280-26-010047": rows})
    clean_exit = pack.main(["--ticker", "KO", "--pack", "reconstruct", "--quiet"])
    clean = json.loads(capsys.readouterr().out)
    assert clean_exit == pack.EXIT_OK, (
        f"a clean reconstruction must exit 0, got {clean_exit} "
        f"(failed_sections={clean['_status']['failed_sections']})"
    )
    assert clean["_status"]["status"] == "ok"

    _stub_reconstruct_producers(monkeypatch, {
        "0001628280-26-010047": rows,
        "0000021344-25-000011": {"error": "did not resolve", "error_class": "resolution"},
    })
    degraded_exit = pack.main(["--ticker", "KO", "--pack", "reconstruct", "--quiet"])
    degraded = json.loads(capsys.readouterr().out)
    assert degraded_exit == pack.EXIT_PARTIAL, (
        f"a failed acquisition must still exit 2, got {degraded_exit}"
    )
    assert "reconstruction" in degraded["_status"]["failed_sections"]


def _run_pack_raising(monkeypatch, capsys, exc):
    """Drive `pack.main` with a `build_pack` that raises `exc`; return
    (exit_code, _status block)."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack  # noqa: E402
    import pack_us  # noqa: E402

    def boom(pack_name, tickers):
        raise exc

    monkeypatch.setattr(pack_us, "build_pack", boom)
    exit_code = pack.main(["--ticker", "KO", "--pack", "reconstruct", "--quiet"])
    return exit_code, json.loads(capsys.readouterr().out)["_status"]


def test_internal_module_failure_is_not_dressed_as_a_client_dep_error(monkeypatch, capsys):
    """A missing INTERNAL module must not be answered with the client-deps
    message.

    The handler answers `ModuleNotFoundError` with "re-run with `--with ...`".
    That is right for a dependency the user supplies on the invocation, and
    WRONG for one of our own modules: `pack_us.pack_reconstruct` imports
    `kpi_us_statement_shape` ACROSS a skill boundary, so a move or rename
    there raises `ModuleNotFoundError` too -- and the user would be told to
    `--with` a package that does not exist, to fix a breakage that is not on
    their command line at all. An internal breakage wearing a user-error
    costume is the same "system disguises its own failure" mode this arc
    exists to remove, reproduced inside the error path meant to prevent it.

    Such a failure must fall through to the generic handler: a real traceback,
    and NO actionable-looking instruction that cannot work.
    """
    exit_code, status = _run_pack_raising(
        monkeypatch, capsys,
        ModuleNotFoundError(
            "No module named 'kpi_us_statement_shape'", name="kpi_us_statement_shape"
        ),
    )

    assert exit_code == 1
    assert status["status"] == "failed"
    assert "--with" not in status.get("message", ""), (
        f"an internal module must not be reported as a user-invocation error: "
        f"{status.get('message')!r}"
    )
    assert "kpi_us_statement_shape" in status.get("traceback", ""), (
        "the real cause must still be surfaced by the generic handler"
    )


def test_missing_edgartools_names_the_distribution_not_the_import_name(monkeypatch, capsys):
    """A missing edgartools must still be handled AND must name what the user
    can actually pass.

    IMPORT NAME != DISTRIBUTION NAME: `import edgar` (sec_edgar_client.py:853)
    raises `exc.name == "edgar"`, but the installable package is `edgartools`.
    Two consequences, and the first is why this test exists at all:

      1. a membership check written against the DISTRIBUTION names would not
         match `"edgar"`, so a genuinely missing client dep would be re-raised
         into the generic traceback handler -- silently reintroducing the bare
         `ModuleNotFoundError` this lane was built to remove;
      2. `--with edgar` installs the wrong project (or nothing), so the
         message must never tell the user to pass the import name.

    The `requests` arm cannot catch either: there the two names coincide.
    """
    exit_code, status = _run_pack_raising(
        monkeypatch, capsys,
        ModuleNotFoundError("No module named 'edgar'", name="edgar"),
    )

    assert exit_code == 1
    message = status.get("message", "")
    assert "--with" in message, (
        f"a genuinely missing client dep must still get the guidance: {message!r}"
    )
    assert "edgartools" in message, f"must name the installable package: {message!r}"
    assert "--with edgar " not in message and not message.endswith("--with edgar"), (
        f"must never tell the user to pass the IMPORT name: {message!r}"
    )
    assert "'edgar'" not in message.split("Pass the whole set")[-1], (
        f"the closing clause must name the distribution, not the import name: {message!r}"
    )


def _required_third_party_imports(path):
    """Top-level module names `path` REQUIRES that are neither stdlib nor a
    local sibling script — i.e. exactly what a caller must supply.

    Imports inside a `try:` with an except handler are EXCLUDED, because they
    are optional by construction. Observed case: `sec_edgar_client.py:1256`
    imports `httpx` under `try/except` to widen a timeout-exception tuple and
    falls back to the builtin `TimeoutError` when it is absent. Declaring it
    would tell the caller to pass a package the lane works fine without —
    a false instruction, which is the same defect class as the false promise
    this test exists to prevent, pointed the other way.
    """
    import ast  # noqa: E402

    local = {
        p.stem
        for scripts in (MARKETS_SCRIPTS, ROOT / "skills" / "analysis-kpi" / "scripts")
        for p in scripts.glob("*.py")
    }
    tree = ast.parse(path.read_text())

    optional: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and node.handlers:
            for stmt in node.body:
                for inner in ast.walk(stmt):
                    if isinstance(inner, (ast.Import, ast.ImportFrom)):
                        optional.add(id(inner))

    names: set[str] = set()
    for node in ast.walk(tree):
        if id(node) in optional:
            continue
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return {n for n in names if n not in sys.stdlib_module_names and n not in local}


def test_client_dependencies_covers_every_third_party_import_of_the_sec_lane():
    """`CLIENT_DEPENDENCIES` must be BOUND to the code, not to three copies of
    a sentence.

    The set is currently restated in `pack.py`'s constant, `pack.py`'s module
    docstring, and `SKILL.md` — and the message built from it promises the
    caller "the WHOLE set". Nothing derived that promise from the real imports,
    so adding a third client dependency would leave the message confidently
    false, which is precisely the PR #619 failure it was written to prevent
    (supply what you were told, fail on the next import anyway).

    Derived by parsing the real modules rather than listing names here: a test
    that hardcoded the same two names would be a fourth copy of the sentence,
    not a binding.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack  # noqa: E402

    # Keyed on IMPORT names — what `ModuleNotFoundError.name` actually carries.
    declared = set(pack.CLIENT_DEPENDENCIES)
    for module in ("sec_edgar_client.py", "pack_us.py"):
        found = _required_third_party_imports(MARKETS_SCRIPTS / module)
        assert found <= declared, (
            f"{module} imports {sorted(found - declared)}, which "
            f"`CLIENT_DEPENDENCIES` does not declare — the message's "
            f"\"pass the whole set\" promise is false for those"
        )


def test_build_pack_statement_backfill_requires_exactly_one_ticker():
    """Pins the ticker-count validation, mirroring `kpi-topline-backfill`'s
    branch (pack_us.py:1367-1372) and its exact error-message shape — a
    pack that dispatches but accepts two tickers is only half-wired."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402

    with pytest.raises(ValueError, match=r"requires exactly one ticker \(single, heavy\)"):
        pack_us.build_pack("statement-backfill", ["AAPL", "MSFT"])

    with pytest.raises(ValueError, match=r"requires exactly one ticker \(single, heavy\)"):
        pack_us.build_pack("statement-backfill", [])


# ---------------------------------------------------------------------------
# Task J (plan docs/loom/plans/2026-07-28-us-quarterly-statement-series.md) —
# the acquire loop that turns Task A's accession rows into the already-acquired
# filing objects Task D's stitching function takes. It lives HERE, on the
# data-markets side, because an `analysis-*` module reaching this I/O by import
# would cross the boundary this repo crosses by subprocess (Task D's
# Description; CLAUDE.md §Cross-Plugin Delegation Contract).
# ---------------------------------------------------------------------------

class _AcquiredFiling:
    """Stand-in for the raw edgartools ``Filing`` that `_acquire_raw_filing`
    returns on success.

    Deliberately NOT a `mock.MagicMock` and deliberately WITHOUT `__eq__`:

      - no `__eq__` means every comparison against one of these is IDENTITY,
        so an assertion can pin WHICH filing came back at each position rather
        than merely how many did (a loop that returned the first filing three
        times satisfies a count);
      - a bare object with only the attribute it was built with means a loop
        that reached INTO the filing — projecting it, re-wrapping it, reading
        `.form` — raises instead of quietly producing a passable shape. This
        loop's contract is pass-through, and pass-through is what that proves.
    """

    def __init__(self, accession: str) -> None:
        self.accession_number = accession

    def __repr__(self) -> str:  # pragma: no cover - failure messages only
        return f"<_AcquiredFiling {self.accession_number}>"


def test_partial_acquisition_failure_is_reported_not_silent(monkeypatch):
    """One accession in the span fails to acquire. The loop must record THAT
    accession as a failed item and still return the filings acquired from the
    rest -- and what it returns must be the raw filing objects themselves.

    Three ways this could go wrong, each pinned by its own assertion:

      1. **A silently shorter span.** A loop that drops the unacquirable
         accession without recording it returns a span that is shaped exactly
         like a complete one -- this arc's recurring defect. Pinned by asserting
         `failed_items` names the FAILED accession, not merely that it is
         non-empty: an entry carrying the wrong accession is as unusable as no
         entry, and points a reader at an innocent filing.
      2. **An aborted request.** One bad accession in seventy-seven must not
         cost the other seventy-six. Pinned by recording every accession the
         loop attempted, so a `break`/`raise` on the failure is visible as a
         short attempt list rather than only as a shorter result.
      3. **The wrong OUTPUT SHAPE.** Task D's function takes ALREADY-ACQUIRED
         filing objects; a loop yielding accession rows, or `_acquire_raw_filing`
         error dicts, or re-wrapped projections would satisfy every count above
         and fail at the seam. Pinned by identity against the exact objects the
         stub returned, in order.

    STUBBED AT `sec_edgar_client._acquire_raw_filing` -- this file's own
    boundary (the PRODUCER'S OWN boundary, as the autouse
    `_stub_xval_producers_for_memo_fetch` fixture's docstring puts it; that is
    the fixture this test overrides), NOT at `edgar.get_by_accession_number`. That is not stylistic here: Task B put a
    disk cache BEHIND the lower boundary, and this file pins no
    `INVESTING_TOOLKIT_CACHE` directory, so a lower stub would write fake
    filings into the developer's real cache. The second run would take a disk
    HIT instead of reaching the stub, and this test would stop exercising the
    failure it exists to pin -- without failing. (A lower stub, if one is ever
    needed, wants an autouse cache-dir fixture first; `test_sec_narrative.py`
    and `test_exhibit_fetch.py` are the pattern.)

    Follows the already-established shape of this exact loop in
    `pack_reconstruct` (`{"accession": accession, **filing}` appended to
    `failed_items`, then `continue`), rather than inventing a second one.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402
    import sec_edgar_client  # noqa: E402

    first = "0000789019-24-000023"
    bad = "0000789019-25-000010"
    last = "0000789019-25-000082"

    # The oldest-first row shape `assemble_quarterly_filing_span` returns.
    rows = [
        {"form": "10-Q", "filingDate": "2024-10-30", "accessionNumber": first},
        {"form": "10-Q", "filingDate": "2025-01-29", "accessionNumber": bad},
        {"form": "10-K", "filingDate": "2025-07-30", "accessionNumber": last},
    ]

    acquired_first = _AcquiredFiling(first)
    acquired_last = _AcquiredFiling(last)
    acquire_error = {
        "error": (
            f"SEC EDGAR filing acquisition failed: accession {bad!r} did not "
            f"resolve to a filing"
        ),
        "error_class": "resolution",
    }
    by_accession = {first: acquired_first, bad: acquire_error, last: acquired_last}

    attempted: list = []

    def _fake_acquire(accession):
        attempted.append(accession)
        return by_accession[accession]

    monkeypatch.setattr(sec_edgar_client, "_acquire_raw_filing", _fake_acquire)

    filings, failed_items = pack_us._acquire_filing_span(rows)

    # 2. the failure did not abort the request -- every accession was attempted
    assert attempted == [first, bad, last], (
        f"the loop must attempt every accession in the span; a failure at "
        f"{bad} must not stop it: {attempted}"
    )

    # 3. the OUTPUT CONTRACT. The no-dict check is FIRST deliberately: placed
    # after the identity assertion below it could never be the failing one --
    # every dict that reached `filings` fails identity first -- which is a test
    # line that cannot fail (docs/loom/memory/a-test-can-be-correct-and-still-
    # unable-to-fail.md). Here it is the line that catches an accession row or
    # an unrecognised error slot, and identity catches the rest.
    assert not any(isinstance(f, dict) for f in filings), (
        f"an accession row or an error slot must never be yielded as a "
        f"filing -- Task D's function calls into these objects: {filings}"
    )
    # Exactly the objects `_acquire_raw_filing` returned, in order.
    # `_AcquiredFiling` has no `__eq__`, so this is identity -- returning
    # `acquired_first` twice, or a re-wrapped projection, fails here while
    # satisfying any count-based assertion.
    assert filings == [acquired_first, acquired_last], (
        f"must yield the acquired filing objects themselves, in span order: "
        f"{filings}"
    )

    # 1. the failure is LOUD and names the accession that actually failed
    assert [item["accession"] for item in failed_items] == [bad], (
        f"the unacquirable accession must be recorded by NAME -- a shorter "
        f"span with nothing recorded, or an entry naming a filing that "
        f"succeeded, are both silent failures: {failed_items}"
    )
    assert failed_items[0]["error_class"] == "resolution", (
        f"the acquisition slot's own class must ride along, so a reader can "
        f"tell a resolution failure from a form-unavailable one: {failed_items}"
    )
    assert failed_items[0]["error"] == acquire_error["error"], (
        "the acquisition slot's own message must ride along verbatim, "
        "matching `pack_reconstruct`'s `{'accession': accession, **filing}`"
    )


def test_a_row_with_no_accession_is_recorded_never_attempted_never_dropped(monkeypatch):
    """A span row whose `accessionNumber` is `None` must be recorded as its own
    failed item -- neither handed to the acquisition boundary (which cannot NAME
    it) nor filtered out of the span (which loses it silently).

    THE ROW IS REAL. `sec_edgar_client.list_filings` builds each row by index
    across the submissions columns and pads a short column with `None`
    (`_append_submission_block`); it filters no row on that account, so a span
    assembled from its output can carry one.

    Both wrong answers are pinned, because both are one edit away:

      1. **Handing it to `_acquire_raw_filing`.** That function answers a
         `None` accession with its ordinary loud resolution slot, which reports
         `accession: None` and carries no form and no filing date -- so the row
         survives, but becomes unidentifiable, which for a row that HAS no
         accession is the whole of its identity. (It briefly raised
         `AttributeError` here instead, between the cache key being lifted out
         of its `try` and being moved back in on 2026-08-07; three docstrings
         across two files went on asserting that raise after it was gone, this
         one included. State the observable contract, not the mechanism.)
         The stub below reproduces the CURRENT boundary -- it returns the slot
         rather than raising -- so a loop that attempts the row fails here on
         the real loss instead of on a crash production no longer produces.
      2. **Filtering it out**, the way `pack_reconstruct` does. That is right
         THERE and silent HERE: `pack_reconstruct` counts `requested` over its
         own filtered list, while this function returns no count at all and
         leaves the caller to reconcile `len(rows)` against the two returned
         lists. A dropped row makes that arithmetic disagree with nothing
         recorded -- a span shaped exactly like a complete one, which is the
         defect this whole arc exists to remove. Pinned by asserting
         `failed_items` carries the `None`-accession entry, not merely that the
         good filing survived.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402
    import sec_edgar_client  # noqa: E402

    good = "0000789019-25-000082"
    rows = [
        {"form": "10-Q", "filingDate": "2025-01-29", "accessionNumber": None},
        {"form": "10-K", "filingDate": "2025-07-30", "accessionNumber": good},
    ]
    acquired = _AcquiredFiling(good)
    attempted: list = []

    def _fake_acquire(accession):
        # Faithful to the real boundary: a `None` accession comes back as a
        # loud resolution slot, NOT a raise. If the guard under test is ever
        # removed, this stub reproduces what production would actually do, so
        # the resulting failure reads true; a stub that raised instead would
        # fail this test with a crash production no longer produces.
        # THE LEDGER IS WRITTEN FIRST, BEFORE THE None BRANCH, and the order is
        # the point: `attempted` exists to record every call that REACHED this
        # boundary, so a `None` short-circuit placed above it would quietly
        # stop recording the one call the assertion below is looking for. That
        # is what an earlier version of this stub did — with the production
        # guard deleted, the boundary was reached, stderr showed the call, and
        # `attempted == [good]` still passed.
        attempted.append(accession)
        if accession is None:
            return {
                "error": "SEC EDGAR filing acquisition failed: accession None "
                "did not resolve to a filing",
                "error_class": "resolution",
            }
        return acquired

    monkeypatch.setattr(sec_edgar_client, "_acquire_raw_filing", _fake_acquire)

    filings, failed_items = pack_us._acquire_filing_span(rows)

    assert attempted == [good], (
        f"a row with no accession must never reach the acquisition boundary, "
        f"and the rows after it must still be attempted: {attempted}"
    )
    assert filings == [acquired], (
        f"the acquirable rows of the span must still come back, unaffected by "
        f"the unusable row before them: {filings}"
    )
    assert [item["accession"] for item in failed_items] == [None], (
        f"the row with no accession must be RECORDED as a failed item -- "
        f"filtering it out returns a short span with nothing to explain the "
        f"shortfall: {failed_items}"
    )
    assert failed_items[0]["error_class"] == "no_accession", (
        f"the missing accession is its own failure mode, distinct from an "
        f"accession that failed to resolve: {failed_items}"
    )
    assert "10-Q" in failed_items[0]["error"] and "2025-01-29" in failed_items[0]["error"], (
        f"with no accession to name it by, the entry must name the row some "
        f"other way or it points a reader at nothing: {failed_items}"
    )


def test_an_empty_span_returns_two_empty_lists_and_fabricates_no_failure():
    """Nothing was asked for, so nothing failed. An empty `rows` must not
    manufacture a `failed_items` entry to represent its own emptiness: an empty
    quarterly span is a real answer for a foreign private issuer that files
    20-F rather than 10-Q, and what it MEANS is the caller's to decide."""
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402

    assert pack_us._acquire_filing_span([]) == ([], []), (
        "an empty span is not a failure and must not be reported as one"
    )


# ---------------------------------------------------------------------------
# Task H — the quarterly-series pack verb
# (docs/loom/plans/2026-07-28-us-quarterly-statement-series.md)
# ---------------------------------------------------------------------------

# One fiscal year of a June-year-end filer, in the four cumulative columns the
# stitched result actually carries. Their day spans are what Task C's committed
# windows bucket into the four roles Task E pairs (measured, not assumed:
# `span_windows()` is q1 80-100 / ytd 175-190 + 260-285 / annual 350-380, and
# these keys span 91 / 183 / 273 / 364 days).
_SPAN_Q1 = "duration_2024-07-01_2024-09-30"
_SPAN_YTD6 = "duration_2024-07-01_2024-12-31"
_SPAN_YTD9 = "duration_2024-07-01_2025-03-31"
_SPAN_FY = "duration_2024-07-01_2025-06-30"
# ...and the three quarters no filing states, which Task E subtracts out of them.
_DERIVED_Q2 = "duration_2024-10-01_2024-12-31"
_DERIVED_Q3 = "duration_2025-01-01_2025-03-31"
_DERIVED_Q4 = "duration_2025-04-01_2025-06-30"


def _quarterly_series_stub_statements() -> dict:
    """The three statements as `XBRLS.get_statement` returns them, keyed by the
    library's own statement-type token.

    FLOAT-VALUED CELLS, because that is what the stitched surface really
    carries -- measured on this arc's own committed capture
    (`us_quarterly_stitched_msft.json`: all 255 income-statement cells are
    `float`). The figures are shaped after that filer's real FY2025 columns so
    the stub is recognisable, but nothing here is an oracle for them: every
    expectation below is recomputed from these literals.

    TWO LINES GUARD TWO DIFFERENT LANES, and neither one covers the other.
    Both were checked by running them, not reasoned about:

      * the DIVIDENDS line is the one that guards SERIALISATION -- the lane
        `_project_series_money_to_text` owns. Its cells carry a filed scale
        (`1.6600` / `2.4900`) that binary float cannot: `str(Decimal("0.8300"))`
        is `"0.8300"` and `str(float(Decimal("0.8300")))` is `"0.83"`. **It is
        the only line in this stub that can tell those two apart**, so trimming
        it silently disarms the assertion the money test exists for.
      * the DILUTED-EPS line guards the ARITHMETIC lane instead: a subtraction
        performed in binary float gives `13.64 - 9.99 == 3.6500000000000004`,
        which its assertion catches. It is TRANSPARENT to the serialisation
        lane -- `str(float(Decimal("3.65")))` is `"3.65"`, unchanged -- so it
        proves nothing about `_decimal_text`. (Total revenue is transparent to
        both: `76441000000.0` survives either route.)

    The EPS line carries only two of the four columns, which also exercises the
    per-line skip -- Q2 and Q4 need columns this line does not have.
    """
    duration_periods = [
        [_SPAN_Q1, "Q1 Sep 30, 2024"],
        [_SPAN_YTD6, "Q2 YTD Dec 31, 2024"],
        [_SPAN_YTD9, "Q3 YTD Mar 31, 2025"],
        [_SPAN_FY, "FY Jun 30, 2025"],
    ]
    return {
        "IncomeStatement": {
            "periods": duration_periods,
            "statement_data": [
                {
                    "concept": "us-gaap_Revenues",
                    "label": "Total revenue",
                    "values": {
                        _SPAN_Q1: 65585000000.0,
                        _SPAN_YTD6: 135190000000.0,
                        _SPAN_YTD9: 205283000000.0,
                        _SPAN_FY: 281724000000.0,
                    },
                },
                {
                    "concept": "us-gaap_EarningsPerShareDiluted",
                    "label": "Diluted earnings per share",
                    "values": {_SPAN_YTD6: 9.99, _SPAN_YTD9: 13.64},
                },
                {
                    # STRING-valued cells, which `_cell_decimal` documents as
                    # accepted ("a cell holding a numeric STRING is accepted:
                    # `Decimal('30')` is exactly 30"). They carry a SCALE that
                    # binary float cannot: `2.4900 - 1.6600` is `0.8300` in
                    # Decimal and `0.83` once it has been through a float, so
                    # this line is what separates `str(Decimal)` from
                    # `str(float(Decimal))` -- two conversions the arc's other
                    # figures agree on.
                    "concept": "us-gaap_CommonStockDividendsPerShareDeclared",
                    "label": "Dividends declared per share",
                    "values": {_SPAN_YTD6: "1.6600", _SPAN_YTD9: "2.4900"},
                },
            ],
        },
        "BalanceSheet": {
            "periods": [
                ["instant_2024-09-30", "Sep 30, 2024"],
                ["instant_2025-06-30", "Jun 30, 2025"],
            ],
            "statement_data": [
                {
                    "concept": "us-gaap_Assets",
                    "label": "Total assets",
                    "values": {
                        "instant_2024-09-30": 523013000000.0,
                        "instant_2025-06-30": 619003000000.0,
                    },
                },
            ],
        },
        "CashFlowStatement": {
            "periods": duration_periods,
            "statement_data": [
                {
                    "concept": "us-gaap_NetCashProvidedByUsedInOperatingActivities",
                    "label": "Net cash from operations",
                    "values": {
                        _SPAN_Q1: 34180000000.0,
                        _SPAN_YTD6: 56471000000.0,
                        _SPAN_YTD9: 93515000000.0,
                        _SPAN_FY: 136162000000.0,
                    },
                },
            ],
        },
    }


class _FakeXBRLS:
    """`XBRLS.from_filings`' return value, reduced to the one method
    `stitch_quarterly_statements` calls. Records every call so a test can see
    what the real stitching function derived from the filings it was handed."""

    def __init__(self, statements: dict) -> None:
        self._statements = statements
        self.calls: list[tuple] = []

    def get_statement(self, statement_type, **kwargs):
        self.calls.append((statement_type, kwargs))
        return self._statements[statement_type]


def _empty_stub_statements() -> dict:
    """What the stitcher returns for a filer whose filings carry no statement
    this projection can read: three well-formed EMPTY statements.

    Not a hypothetical shape -- `get_statement` answers with an empty
    `periods`/`statement_data` pair rather than raising, and
    `_projection_status` exists precisely because
    `{"lines": [], "periods": []}` is as well-formed as a complete statement
    and as easy to read straight past.
    """
    empty = {"periods": [], "statement_data": []}
    return {
        "IncomeStatement": dict(empty),
        "BalanceSheet": dict(empty),
        "CashFlowStatement": dict(empty),
    }


def _stub_quarterly_series_producers(
    monkeypatch, *, rows, failing=(), statements=None, resolved=None
):
    """Stub the verb's three producers and the stitcher's library boundary.

    STUBBED AT THE PRODUCERS, NOT AT THE COMPOSED FUNCTIONS. `_acquire_filing_span`
    (Task J), `stitch_quarterly_statements` (Task D), `derive_discrete_quarters`
    (Task E) and `project_quarterly_series` (Task F) all run for real, so what
    these tests exercise is the WIRING this task owns rather than a chain of
    doubles agreeing with each other. In particular `n_filings_used` is
    computed by the real `stitch_quarterly_statements` from the list the real
    acquire loop returned -- stubbing the stitcher would have made that
    assertion a statement about the stub.

    `sec_edgar_client._acquire_raw_filing` is the acquisition boundary this
    file already stubs everywhere (see `_stub_xval_producers_for_memo_fetch`
    and Task J's own test for why the LOWER `edgar.get_by_accession_number`
    boundary would let Task B's disk cache answer instead).

    `kpi_us_quarterly_series._build_xbrls` is that module's own declared
    monkeypatch seam ("the LOCAL import boundary a test monkeypatches"), which
    is what keeps `import edgar` out of an offline run.

    `statements` overrides what the stitcher's library boundary answers with
    (default: the four-column fiscal year below); `resolved` overrides what
    `resolve_cik` answers with, so a test can drive the resolver's own failure
    shape rather than only its success.

    Returns a record dict: `span_calls` (the `(cik, years)` the assembler saw),
    `attempted` (every accession the acquire loop reached), `filings` (the
    exact objects handed to the stitcher) and `xbrls` (the fake).
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402
    import sec_edgar_client  # noqa: E402

    pack_us._ensure_analysis_kpi_importable()
    import kpi_us_quarterly_series  # noqa: E402

    record: dict = {"span_calls": [], "attempted": [], "filings": []}

    monkeypatch.setattr(
        sec_edgar_client, "resolve_cik",
        lambda ticker: (
            {"cik": 789019, "title": "MICROSOFT CORP"} if resolved is None
            else resolved
        ),
    )

    def _fake_span(cik, years=None):
        record["span_calls"].append((cik, years))
        return rows

    monkeypatch.setattr(
        sec_edgar_client, "assemble_quarterly_filing_span", _fake_span
    )

    def _fake_acquire(accession):
        record["attempted"].append(accession)
        if accession in failing:
            return {
                "error": (
                    f"SEC EDGAR filing acquisition failed: accession "
                    f"{accession!r} did not resolve to a filing"
                ),
                "error_class": "resolution",
            }
        return _AcquiredFiling(accession)

    monkeypatch.setattr(sec_edgar_client, "_acquire_raw_filing", _fake_acquire)

    fake = _FakeXBRLS(
        _quarterly_series_stub_statements() if statements is None else statements
    )

    def _fake_build(filings):
        record["filings"] = list(filings)
        return fake

    monkeypatch.setattr(kpi_us_quarterly_series, "_build_xbrls", _fake_build)
    record["xbrls"] = fake
    return record


def _quarterly_series_rows(*accessions) -> list[dict]:
    """The oldest-first row shape `assemble_quarterly_filing_span` returns."""
    return [
        {"form": "10-Q", "filingDate": f"2024-10-{30 - i:02d}", "accessionNumber": a}
        for i, a in enumerate(accessions)
    ]


def _periods_of(payload: dict, kind: str) -> dict:
    """`{period_key: period_entry}` for one statement kind of a projection."""
    return {p["key"]: p for p in payload["statements"][kind]["periods"]}


def _cell(payload: dict, kind: str, concept: str, period_key: str):
    """One projected cell, or `KeyError`."""
    for line in payload["statements"][kind]["lines"]:
        if line["concept"] == concept:
            return line["values"][period_key]
    raise KeyError(f"{concept} is not a line of {kind}")


def test_quarterly_series_verb_is_registered_and_us_only(monkeypatch, capsys):
    """Plan Task H's first RED: the verb is REACHABLE from the pack CLI, is
    reachable ONLY for US filers, and answers with the LABELLED projection.

    Four claims, because each can hold while the next silently does not:

      1. `quarterly-series` is in `pack_us.SUPPORTED_PACKS` -- without it
         `build_pack` raises the generic `unknown pack` ValueError.
      2. It DISPATCHES. Registration is not dispatch: `statement-backfill`
         shipped registered-but-undispatched in this very module
         (`test_build_pack_dispatches_statement_backfill`).
      3. It is REFUSED (exit 64) for a non-US market by the facade's
         `US_ONLY_PACKS` guard -- and NOT refused for a US ticker, which is
         what proves the guard is market-scoped rather than blanket.
      4. The payload is the LABELLED projection: every period states its kind
         and its provenance, the balance sheet's instants come back
         `kind: "instant"`, and the three quarters no filing states are
         present and marked `derived`.

    Claim 4 also pins the CLEAN run's classification. `failed_items` is nested
    inside an `acquisition` section rather than sitting at the pack's top
    level, and that is not stylistic: `pack.py`'s `_list_section_status` reads
    an EMPTY top-level list as `"failed"` (right for a ticker fan-out, wrong
    for a `failed_items: []` that means success), which is the measured defect
    `pack_reconstruct`'s docstring records from a live KO run that
    reconstructed 4 of 4 filings and still reported partial. So a clean run
    classifying `ok` is a real assertion about placement, not a formality.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack  # noqa: E402
    import pack_us  # noqa: E402

    # --- 1. registered ---
    assert "quarterly-series" in pack_us.SUPPORTED_PACKS, (
        f"quarterly-series is not registered: {pack_us.SUPPORTED_PACKS}"
    )

    # The projection's own `pack` token and the registry name must read the
    # same -- `kpi_us_quarterly_series._PACK_NAME`'s own comment requires it,
    # and a payload naming a verb the CLI does not have is unreachable prose.
    pack_us._ensure_analysis_kpi_importable()
    import kpi_us_quarterly_series  # noqa: E402

    assert kpi_us_quarterly_series._PACK_NAME == "quarterly-series", (
        f"the projection's pack token and the CLI verb must read the same: "
        f"{kpi_us_quarterly_series._PACK_NAME!r}"
    )

    # --- 2. dispatches through build_pack ---
    calls: list = []

    def fake_pack_quarterly_series(ticker, years=None):
        calls.append((ticker, years))
        return {"pack": "quarterly-series", "ticker": ticker}

    # A SCOPED patch, not `monkeypatch.undo()`: this file's autouse fixtures
    # share the one function-scoped `monkeypatch`, so undoing would also drop
    # the `requests` stub every later import in this test depends on. Narrow
    # `mock.patch.object` is the override this file already documents.
    with mock.patch.object(
        pack_us, "pack_quarterly_series", fake_pack_quarterly_series
    ):
        result = pack_us.build_pack("quarterly-series", ["MSFT"])
        assert calls == [("MSFT", None)]
        assert result == {"pack": "quarterly-series", "ticker": "MSFT"}

        with pytest.raises(
            ValueError, match=r"requires exactly one ticker \(single, heavy\)"
        ):
            pack_us.build_pack("quarterly-series", ["MSFT", "AAPL"])

        # --- 3. refused for a non-US market, at the facade ---
        assert "quarterly-series" in pack.US_ONLY_PACKS, (
            f"quarterly-series is not declared US-only: "
            f"{sorted(pack.US_ONLY_PACKS)}"
        )
        exit_code = pack.main(["--ticker", "2330.TW", "--pack", "quarterly-series"])
        assert exit_code == pack.EXIT_USAGE_ERROR
        refusal = json.loads(capsys.readouterr().out)["_status"]
        assert refusal["status"] == "usage_error"
        assert "US-only" in refusal["message"], (
            f"refusal must name market availability, not a pack-name typo: "
            f"{refusal}"
        )

        calls.clear()
        us_exit = pack.main(
            ["--ticker", "MSFT", "--pack", "quarterly-series", "--quiet"]
        )
        capsys.readouterr()
        assert calls == [("MSFT", None)], "the US arm must reach the producer"
        assert us_exit != pack.EXIT_USAGE_ERROR

    # --- 4. the labelled projection, over a stubbed series ---
    rows = _quarterly_series_rows("0000789019-24-000023", "0000789019-25-000082")
    _stub_quarterly_series_producers(monkeypatch, rows=rows)

    payload = pack_us.pack_quarterly_series("msft")

    assert payload["pack"] == "quarterly-series"
    assert payload["ticker"] == "MSFT", "the ticker is normalised, as everywhere else"
    assert payload["_status"] == "ok"

    income = _periods_of(payload, "income")
    assert income[_SPAN_FY] == {
        "key": _SPAN_FY, "kind": "annual", "derived": False,
        "start": "2024-07-01", "end": "2025-06-30",
    }, f"a filed annual column must say so: {income[_SPAN_FY]}"
    assert income[_DERIVED_Q4] == {
        "key": _DERIVED_Q4, "kind": "discrete_quarter", "derived": True,
        "start": "2025-04-01", "end": "2025-06-30",
    }, f"the derived Q4 must be labelled as both: {income.get(_DERIVED_Q4)}"

    # The COUNT, not just the presence: a projection that dropped one derived
    # quarter satisfies every per-period assertion above.
    assert sorted(k for k, p in income.items() if p["derived"]) == [
        _DERIVED_Q2, _DERIVED_Q3, _DERIVED_Q4
    ], f"all three unstated quarters must be derived: {sorted(income)}"
    assert not any(p["derived"] for p in _periods_of(payload, "balance_sheet").values())
    assert all(
        p["kind"] == "instant" for p in _periods_of(payload, "balance_sheet").values()
    ), "the balance sheet is instant-based and must be labelled so"

    # ...and a clean run is not misreported as degraded by the facade.
    assert pack._classify_result(payload) == ("ok", []), (
        f"a run in which every filing acquired must classify ok -- an empty "
        f"`failed_items` at the pack's TOP level would read as failed: "
        f"{pack._classify_result(payload)}"
    )


def test_a_partial_span_reports_partial_and_counts_only_the_filings_it_used(
    monkeypatch,
):
    """Plan Task H's second RED, clause 1 -- the obligation Task J's return
    shape creates. `_acquire_filing_span` returns `(filings, failed_items)` and
    NO status; building `{requested, succeeded, failed}` is this verb's job.

    Three things, and the third is the one this arc keeps shipping wrong:

      1. `_status` is `"partial"`, never `"ok"`.
      2. The accession that failed is named in `failed_items`.
      3. **`n_filings_used` is `len(filings)`, never `len(rows)`.** A short
         answer must not be shaped like a complete one: a reader who sees the
         requested count there believes the series covers filings it never
         read. It is asserted against `requested` in the same breath, so a
         verb that reported either count for both fails.

    The classification is asserted too -- degradation the facade cannot see is
    degradation the caller never learns about, and `main()` OVERWRITES the
    payload's own top-level `_status` with its own block before anything is
    emitted (`pack.py` `main`), so the top-level string is invisible on the
    far side of the CLI. The `acquisition` section's own `_status` is what
    `_section_status` honours.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack  # noqa: E402
    import pack_us  # noqa: E402

    first = "0000789019-24-000023"
    bad = "0000789019-25-000010"
    last = "0000789019-25-000082"
    rows = _quarterly_series_rows(first, bad, last)
    record = _stub_quarterly_series_producers(monkeypatch, rows=rows, failing={bad})

    payload = pack_us.pack_quarterly_series("MSFT")

    assert record["attempted"] == [first, bad, last], (
        f"one unacquirable accession must not abort the span: "
        f"{record['attempted']}"
    )
    assert payload["_status"] == "partial", (
        f"a span that lost a filing is not an `ok` run: {payload['_status']}"
    )
    assert payload["acquisition"]["_status"] == "partial"
    assert [item["accession"] for item in payload["acquisition"]["failed_items"]] == [
        bad
    ], f"the failed accession must be named: {payload['acquisition']}"
    assert (payload["acquisition"]["requested"], payload["acquisition"]["succeeded"],
            payload["acquisition"]["failed"]) == (3, 2, 1), (
        f"the triple must reconcile against the span: {payload['acquisition']}"
    )
    # `requested` is pinned at 3 on the line above, so this pins the two counts
    # apart as well as pinning the value -- reporting `len(rows)` here fails.
    # (A separate `n_filings_used != requested` assertion would be one no
    # mutation could reach on its own, which this file's Task J neighbour
    # already had to fix once.)
    assert payload["n_filings_used"] == 2, (
        f"the series was built from 2 filings, not the 3 that were requested; "
        f"reporting the requested count makes a short answer look complete: "
        f"{payload.get('n_filings_used')}"
    )
    assert len(record["filings"]) == 2, (
        f"only the acquired filings may reach the stitcher: {record['filings']}"
    )

    assert pack._classify_result(payload) == ("partial", ["acquisition"]), (
        f"the degradation must be visible to the facade, which never reads "
        f"the payload's own top-level `_status`: {pack._classify_result(payload)}"
    )


def test_an_empty_span_is_a_named_failure_never_ok(monkeypatch):
    """Plan Task H's second RED, clause 2. An EMPTY span (`requested == 0`)
    must NOT report `ok`.

    `pack_reconstruct`'s status formula answers `requested == 0` with `"ok"`
    (`pack_us.pack_reconstruct`, the `status = ("failed" if requested and ...`
    expression) -- correct THERE, where zero means the caller asked for
    nothing, and a defect the brief records (§Error). Here zero filings is a
    real answer to a real request: a foreign private issuer files 20-F, not
    10-Q/10-K, and a well-formed empty series would tell its reader that
    company published no quarterly statements at all.

    So the verb names the refusal instead. The count is IN the message rather
    than only in the section, because the same door covers the other way to
    reach zero filings -- a span whose every accession failed to acquire --
    and the two are distinguishable only by those numbers.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack  # noqa: E402
    import pack_us  # noqa: E402

    _stub_quarterly_series_producers(monkeypatch, rows=[])

    payload = pack_us.pack_quarterly_series("BABA")

    assert payload["_status"] == "failed", (
        f"an empty span is not a successful run: {payload}"
    )
    assert payload["error_class"] == "empty_span"
    assert "0 filing(s) listed, 0 failed to acquire, 0 acquired" in payload[
        "error"
    ] and "20-F" in payload["error"], (
        f"the refusal must say what came back -- the whole reconciling clause, "
        f"since a bare `0` somewhere in the sentence is satisfied by a "
        f"hardcoded literal -- and name the ordinary reason a US-listed filer "
        f"has no 10-Q/10-K: {payload.get('error')}"
    )
    assert "statements" not in payload, (
        "a refusal must not also ship a well-formed empty series -- that is "
        "the shape it exists to avoid"
    )
    assert pack._classify_result(payload)[0] == "failed", (
        f"the facade must exit non-zero on it: {pack._classify_result(payload)}"
    )


def test_an_unresolvable_ticker_is_answered_by_the_resolver_not_by_an_empty_span(
    monkeypatch,
):
    """A ticker SEC EDGAR has never heard of -- a typo, a delisted symbol, a
    foreign listing -- is the likeliest thing a real caller does wrong, and the
    verb must stop at the resolver.

    Two failures this pins apart:

      1. **Carrying on regardless.** `resolve_cik`'s error dict has no `cik`
         key, so a verb that does not check it raises `KeyError: 'cik'` on the
         next line -- a bare traceback where the resolver had already written a
         usable sentence.
      2. **Answering in the wrong voice.** The refusal must still be a PACK
         envelope: `pack` / `ticker` / `fetched_at`, so a caller reading a
         directory of pack outputs can tell whose failure this is and when.
         The ticker is normalised here for the same reason it is everywhere
         else -- `msft` and `MSFT` must not file two different-looking answers.

    And the span assembler must never be reached: asking EDGAR for the filing
    history of a company that does not exist is a network round trip spent to
    learn what the resolver already said.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack  # noqa: E402
    import pack_us  # noqa: E402

    refusal = {
        "error": "ticker 'msftt' not found in SEC company_tickers.json",
        "error_class": "not_found",
    }
    record = _stub_quarterly_series_producers(
        monkeypatch, rows=_quarterly_series_rows("0000789019-25-000082"),
        resolved=refusal,
    )

    payload = pack_us.pack_quarterly_series("msftt")

    assert payload["pack"] == "quarterly-series"
    assert payload["ticker"] == "MSFTT", (
        f"a refusal is still attributed, and normalised as everywhere else: "
        f"{payload.get('ticker')!r}"
    )
    assert "fetched_at" in payload
    assert payload["error"] == refusal["error"], (
        f"the resolver's own sentence must survive, not be replaced by this "
        f"layer's guess at what went wrong: {payload.get('error')!r}"
    )
    assert payload["error_class"] == "not_found"

    assert record["span_calls"] == [], (
        f"the filing history of a company that does not exist must never be "
        f"requested: {record['span_calls']}"
    )
    assert record["attempted"] == []
    assert "statements" not in payload and "acquisition" not in payload, (
        f"an unresolvable ticker has no span to report on -- a well-formed "
        f"empty series or a 0/0/0 acquisition report would both invent one: "
        f"{sorted(payload)}"
    )
    assert pack._classify_result(payload)[0] == "failed", (
        f"the facade must exit non-zero on it: {pack._classify_result(payload)}"
    )


def test_a_partial_acquisition_never_promotes_a_projection_that_already_failed(
    monkeypatch,
):
    """The fold is one-directional: the acquisition's own degradation may DEMOTE
    an `ok` projection to `partial`, never PROMOTE a projection that already
    failed on its own terms.

    The state is reachable, not theoretical. `_projection_status` answers
    `"failed"` when NO statement kind came back with a period, and a filer whose
    filings stitch to three empty statements while part of the span failed to
    acquire is in exactly that state -- both conditions at once. Without the
    guard the fold overwrites `"failed"` with `"partial"`, and the run reports
    a partly-successful series when what it actually holds is no series at all.
    A short answer is bad news; an EMPTY answer wearing a short answer's status
    is worse.

    The `acquisition` section is asserted in the same breath, because it must
    NOT be demoted in sympathy: the acquisition really was partial (one filing
    of two came back), and flattening the two verdicts into one would lose the
    fact that the acquisition is not what went wrong here.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402

    good = "0000789019-25-000082"
    bad = "0000789019-94-000010"
    record = _stub_quarterly_series_producers(
        monkeypatch,
        rows=_quarterly_series_rows(bad, good),
        failing={bad},
        statements=_empty_stub_statements(),
    )

    payload = pack_us.pack_quarterly_series("MSFT")

    # The premise, checked rather than assumed: this really is the both-at-once
    # state, so the assertion below is about the fold and not about a projection
    # that was never `failed` to begin with.
    assert len(record["filings"]) == 1, (
        f"the premise needs a NON-empty span, or the zero-filing door answers "
        f"first and the fold is never reached: {record['filings']}"
    )
    assert payload["acquisition"]["failed"] == 1, (
        f"the premise needs a failed acquisition too: {payload['acquisition']}"
    )
    assert all(
        not view["periods"] for view in payload["statements"].values()
    ), f"the premise needs a projection with no periods at all: {payload}"

    assert payload["_status"] == "failed", (
        f"a projection that failed on its own terms must not be promoted to "
        f"`partial` by the acquisition fold: {payload['_status']}"
    )
    assert payload["acquisition"]["_status"] == "partial", (
        f"...and the acquisition keeps its own verdict, which is a different "
        f"question: {payload['acquisition']}"
    )


def test_a_span_whose_every_accession_failed_is_a_failure_naming_the_counts(
    monkeypatch,
):
    """The OTHER route to a zero-filing span, and the one the docstring claims
    the same door covers: the assembler listed filings, and not one of them
    could be acquired.

    Kept apart from the `rows == []` test above because the two are reached by
    different predicates and mean different things to a reader. A verb keyed on
    the REQUEST (`if not rows:`) sails past this state entirely and hands an
    empty list to `stitch_quarterly_statements`, which refuses it -- so what
    would reach the caller is a raw `ValueError` traceback about an empty
    filings list rather than the answer that three filings were listed and none
    of them could be read.

    The COUNTS are what tell the two routes apart -- that is the whole reason
    the message carries them, and asserting merely that a `0` appears in it is
    satisfied by the hardcoded `0 acquired` whatever the computed numbers say.
    So the reconciling clause is pinned whole, against a span where `requested`
    is 3 rather than 0.

    (`requested` and `failed` READ THE SAME on both routes and always will:
    `_acquire_filing_span` puts every row in exactly one of its two lists, so
    an empty `filings` forces `failed == requested`. Swapping the two in the
    message is an EQUIVALENT mutation, not a gap -- the pair is kept because a
    human reading the refusal should not have to know that invariant to trust
    the arithmetic.)
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack  # noqa: E402
    import pack_us  # noqa: E402

    accessions = (
        "0000789019-94-000010",
        "0000789019-94-000031",
        "0000789019-25-000082",
    )
    rows = _quarterly_series_rows(*accessions)
    record = _stub_quarterly_series_producers(
        monkeypatch, rows=rows, failing=set(accessions)
    )

    payload = pack_us.pack_quarterly_series("msft")

    assert list(record["attempted"]) == list(accessions), (
        f"every listed accession must still be attempted: {record['attempted']}"
    )
    assert payload["_status"] == "failed", (
        f"three filings listed and none acquired is not an `ok` run: {payload}"
    )
    assert payload["error_class"] == "empty_span"
    assert "3 filing(s) listed, 3 failed to acquire, 0 acquired" in payload["error"], (
        f"the refusal must reconcile against the span it was asked for -- "
        f"these counts are the only thing separating this route from a filer "
        f"that simply lists no 10-Q/10-K: {payload['error']}"
    )
    assert "MSFT" in payload["error"], (
        f"the ticker is normalised here as everywhere else: {payload['error']}"
    )
    assert payload["ticker"] == "MSFT"
    assert "statements" not in payload, (
        "a refusal must not also ship a well-formed empty series"
    )

    acquisition = payload["acquisition"]
    assert acquisition["_status"] == "failed", (
        f"the section's own status is the ONLY degradation signal that "
        f"survives `main()`, which overwrites the payload's top-level "
        f"`_status` with its own block: {acquisition}"
    )
    assert (
        acquisition["requested"], acquisition["succeeded"], acquisition["failed"]
    ) == (3, 0, 3), f"the triple must reconcile against the span: {acquisition}"
    assert [item["accession"] for item in acquisition["failed_items"]] == list(
        accessions
    ), f"every accession that failed must be named: {acquisition['failed_items']}"

    assert pack._classify_result(payload)[0] == "failed", (
        f"the facade must exit non-zero on it: {pack._classify_result(payload)}"
    )


def test_derived_money_is_exact_text_and_never_the_facade_fallback(monkeypatch):
    """Plan Task H's third RED -- this task's likeliest silent defect.

    Task F's projection returns derived line values as `Decimal`. `pack.py`'s
    `_emit` is `json.dumps(obj, indent=2, default=str)` (opened and read), so
    a `Decimal` left in the payload SERIALISES SILENTLY -- and so would a
    binary float, which is the whole point. The verb must therefore project
    money to exact text ITSELF, through `pack_us._decimal_text`, and this test
    pins that with a BARE `json.dumps` (no `default=`), which is the only form
    that can tell the two apart.

    THE PREMISE IS CHECKED, NOT ASSUMED. The first assertion runs the
    projection directly and asserts a `Decimal` is really there: without it,
    this whole test would go green on a stub that happens to carry none while
    the live run inherits the fallback -- a test correct in every line and
    incapable of failing
    (docs/loom/memory/a-test-can-be-correct-and-still-unable-to-fail.md).

    THE DISCRIMINATING ASSERTION IS `dividends_q3`, NOT `eps_q3`. Measured, by
    routing the projection through `float` and re-running: `eps_q3` still reads
    `"3.65"` -- `str(float(Decimal("3.65")))` is `"3.65"`, so an exact figure
    with no trailing scale is INVISIBLE to that mutation -- and `revenue` is
    invisible for the same reason. Only the dividends line fails, because it
    keeps the scale its filed inputs carried: `2.4900 - 1.6600` is `0.8300`
    through `Decimal` and `0.83` once it has been through a binary float.

    The `eps_q3` assertion is kept, and guards a DIFFERENT lane: an arithmetic
    performed in float rather than a serialisation performed in float
    (`13.64 - 9.99 == 3.6500000000000004`). Neither assertion substitutes for
    the other, and deleting the dividends line -- or the string-valued cells it
    is built from -- would leave this test unable to fail for the defect it is
    named after.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack_us  # noqa: E402

    rows = _quarterly_series_rows("0000789019-24-000023", "0000789019-25-000082")
    _stub_quarterly_series_producers(monkeypatch, rows=rows)

    pack_us._ensure_analysis_kpi_importable()
    import kpi_us_quarterly_series  # noqa: E402

    # --- the premise: the projection really does hand this verb a Decimal ---
    unprojected = kpi_us_quarterly_series.project_quarterly_series(
        kpi_us_quarterly_series.stitch_quarterly_statements(
            [_AcquiredFiling("0000789019-25-000082")]
        ),
        "MSFT",
    )
    assert isinstance(
        _cell(unprojected, "income", "us-gaap_EarningsPerShareDiluted", _DERIVED_Q3),
        Decimal,
    ), "premise broken: the projection no longer returns Decimal money"

    payload = pack_us.pack_quarterly_series("MSFT")

    eps_q3 = _cell(payload, "income", "us-gaap_EarningsPerShareDiluted", _DERIVED_Q3)
    assert eps_q3 == "3.65", (
        f"a derived cell must be EXACT TEXT: 13.64 - 9.99 is 3.65 in Decimal "
        f"and 3.6500000000000004 in binary float; got {eps_q3!r}"
    )
    assert _cell(payload, "income", "us-gaap_Revenues", _DERIVED_Q4) == "76441000000.0"

    # The SCALE the arithmetic produced, kept. This is the assertion that
    # separates `str(Decimal)` from `str(float(Decimal))`: the two agree on
    # every other figure in this stub, so without this line a conversion that
    # routes through float passes the whole test.
    dividends_q3 = _cell(
        payload, "income", "us-gaap_CommonStockDividendsPerShareDeclared", _DERIVED_Q3
    )
    assert dividends_q3 == "0.8300", (
        f"2.4900 - 1.6600 is 0.8300 in Decimal and 0.83 once it has been "
        f"through a binary float; got {dividends_q3!r}"
    )

    # A FILED cell is passed through as the library gave it, untouched. Only
    # OUR arithmetic is re-typed: converting the filer's own numbers to text
    # here would mask a non-serialisable value the bare dump below must catch.
    assert _cell(payload, "income", "us-gaap_Revenues", _SPAN_FY) == 281724000000.0

    # The bare dump: no `default=`, so a Decimal this verb failed to reach
    # raises here instead of being quietly stringified by the facade.
    json.dumps(payload)


def test_the_years_cap_is_optional_reaches_the_assembler_and_is_verb_scoped(
    monkeypatch, capsys
):
    """The verb takes a ticker and an OPTIONAL years cap, defaulting to ALL
    available history (plan Task H Description; Task A's
    `assemble_quarterly_filing_span(cik, years=None)` is what "all available"
    means, and ten years is the user's FLOOR rather than the target).

    Four claims:

      1. Called with no cap, the assembler is asked for `years=None` -- the
         default must not be a number this layer invented, which is the exact
         defect `assemble_quarterly_filing_span`'s own docstring records for a
         guessed `limit`.
      2. `--years N` reaches it, through the facade, as `N`.
      3. `--years` on any OTHER pack is a usage error rather than a silently
         ignored flag -- no other market module's `build_pack` accepts it, so
         a flag that looked accepted would be a lie on four of five markets.
      4. A non-positive cap is refused. Left through, it would resolve to a
         cutoff at or after today and come back as an EMPTY span, reported as
         a failure attributed to the FILER -- a usage error wearing a
         data-availability costume.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack  # noqa: E402
    import pack_us  # noqa: E402

    rows = _quarterly_series_rows("0000789019-24-000023", "0000789019-25-000082")
    record = _stub_quarterly_series_producers(monkeypatch, rows=rows)

    pack_us.pack_quarterly_series("MSFT")
    assert record["span_calls"] == [(789019, None)], (
        f"the uncapped default must ask for ALL available history: "
        f"{record['span_calls']}"
    )

    record["span_calls"].clear()
    rc = pack.main(
        ["--ticker", "MSFT", "--pack", "quarterly-series", "--years", "5", "--quiet"]
    )
    capsys.readouterr()
    assert record["span_calls"] == [(789019, 5)], (
        f"--years must reach the assembler, not be dropped by the facade: "
        f"{record['span_calls']}"
    )
    assert rc != pack.EXIT_USAGE_ERROR

    assert pack.main(["--ticker", "MSFT", "--pack", "snapshot", "--years", "5"]) == (
        pack.EXIT_USAGE_ERROR
    ), "--years is meaningless outside quarterly-series and must be refused"
    assert "--years" in json.loads(capsys.readouterr().out)["_status"]["message"]

    assert pack.main(
        ["--ticker", "MSFT", "--pack", "quarterly-series", "--years", "0"]
    ) == pack.EXIT_USAGE_ERROR, "a non-positive cap is a usage error, not an empty span"
    capsys.readouterr()


def test_a_client_printing_to_stdout_cannot_corrupt_the_emitted_json(
    monkeypatch, capsys
):
    """The facade's output contract is ONE JSON document on stdout, and a
    dependency that prints is what breaks it.

    MEASURED, NOT HYPOTHETICAL. On this branch's live `--pack
    quarterly-series` run against MSFT, edgartools' `get_filings` emitted
    `print_warning(...)` through a rich console -- which writes to STDOUT -- for
    two 1994 accessions it could not resolve, and the emitted document was no
    longer parseable JSON. The verb itself is innocent: `pack_us` logs through
    `_log` to stderr and contains no `print(` or `sys.stdout` at all. The noise
    comes from inside `build_pack`, from a library neither file owns.

    So the guard belongs at the facade's own boundary, around the ONE call that
    runs third-party code, and nowhere else: every `_emit` in `pack.py` sits
    strictly before or after that call, so redirecting for its duration cannot
    swallow the payload it is protecting. Any market module and any pack is
    covered by the same three lines -- `quarterly-series` is merely where it was
    measured.

    The noise must still be READABLE, on stderr next to the progress log, not
    discarded: a warning naming an accession that would not resolve is exactly
    what a reader needs when the span comes back short.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    import pack  # noqa: E402
    import pack_us  # noqa: E402

    noise = "WARNING: no XBRL data found for accession 0000789019-94-000010"

    def noisy_build_pack(pack_name, tickers, **kwargs):
        # What a rich console does inside the dependency: plain `print`.
        print(noise)
        return {"pack": pack_name, "ticker": tickers[0]}

    with mock.patch.object(pack_us, "build_pack", noisy_build_pack):
        rc = pack.main(["--ticker", "MSFT", "--pack", "quarterly-series", "--quiet"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)  # the whole point: this must not raise
    assert payload["_status"]["pack"] == "quarterly-series"
    assert payload["ticker"] == "MSFT"
    assert rc == pack.EXIT_OK

    assert noise not in captured.out, (
        f"library chatter must not reach the JSON channel: {captured.out!r}"
    )
    assert noise in captured.err, (
        f"...and must not be discarded either -- it belongs on stderr with the "
        f"progress log: {captured.err!r}"
    )

    # ...AND THE GUARD MUST NOT SWALLOW THE FAILURE ENVELOPE. A redirect placed
    # one level coarser -- around the whole `try`/`except` rather than around
    # the call -- passes every assertion above and sends the fail-loud JSON to
    # stderr with an EMPTY stdout, which is a worse failure than the one being
    # fixed: a caller piping to `jq` would see nothing at all on the runs that
    # most need explaining.
    def noisy_then_crash(pack_name, tickers, **kwargs):
        print(noise)
        raise RuntimeError("boom-after-the-noise")

    with mock.patch.object(pack_us, "build_pack", noisy_then_crash):
        rc = pack.main(["--ticker", "MSFT", "--pack", "quarterly-series", "--quiet"])

    captured = capsys.readouterr()
    failure = json.loads(captured.out)["_status"]
    assert rc == pack.EXIT_FAILED
    assert failure["status"] == "failed"
    assert "boom-after-the-noise" in failure["traceback"]
    assert noise not in captured.out
