"""test_raw_filing_cache.py — `_acquire_raw_filing` must serve a warm accession
from disk instead of re-scanning SEC's quarterly indexes.

Plan Task B (docs/loom/plans/2026-07-28-us-quarterly-statement-series.md).
Filings are immutable, so existence is validity: no TTL, no invalidation.
The cost this removes is measured in the brief's §Boundary — 15.9-29.1 s per
filing, re-paid in full by every fresh process, which at the ~77 filings of a
full history is 20-37 minutes EVERY run.

**What is actually cached, and why it is not a document.** `_acquire_raw_filing`
never fetches a filing document. `edgar.get_by_accession_number` resolves an
accession against SEC's quarterly INDEX files and builds a `Filing` from an
index row, so the cacheable thing is the filing's identity, not its bytes. The
on-disk format is the one the user ratified 2026-07-31 (Decision Log #3):

    {accession, fetched_at, sec_url,
     filing: {accession_number, cik, company, form, filing_date}}

`filing` carries edgartools' OWN `Filing.to_dict()` field names, so a future
field change in the dependency surfaces as a mismatch rather than as our own
silent drift.

**`sec_url` is the reconstructable archives URL**, built here from `cik` +
accession via `SEC_ARCHIVES_URL` / `_accession_nodash` — never
`Filing.filing_url`, which resolves the primary document OVER THE WIRE and
would therefore add a network round-trip on every cache MISS, on the one seam
whose whole purpose is removing network cost. `_FakeFiling` below enforces that
by omission: it has no `filing_url` attribute at all, so an implementation that
reached for one would raise rather than pass quietly.

**External-surface grounding — edgartools 5.42.0, verified 2026-07-31** by
running `uv run --with 'edgartools==5.42.0' --no-project python -c ...` against
the pinned version (introspection plus local object construction; no SEC calls).
`_FakeFiling` mirrors what those probes returned:

  - `Filing.__init__(self, cik: int, company: str, form: str, filing_date: str,
    accession_no: str, related_entities=None)` — the five values a cache hit
    must restore, and the reason the pre-ratification envelope could not work.
  - A live-acquired `Filing` carries `filing_date` as a `datetime.date`
    (the shape `sec_edgar_client.py`'s captured-shape comment above
    `_filing_date_iso` already records), and constructing one WITH a
    `datetime.date` preserves that type.
  - `Filing.to_dict()` -> `{accession_number, cik, company, form, filing_date}`;
    `Filing.from_dict` coerces `filing_date=str(...)`, which is why the
    implementation must NOT use it — see
    `test_a_cache_hit_carries_filing_date_as_a_date_not_a_string`.
  - `period_of_report` / `filing_url` / `homepage_url` are lazily-derived
    PROPERTIES on both an index-acquired and a reconstructed `Filing`, so a
    cache hit diverges from a live acquisition on none of them.

Offline: `edgar` and `requests` are injected as `sys.modules` stubs BEFORE
importing sec_edgar_client, the established pattern in test_sec_narrative.py.
The cache directory is pinned per-test at a pytest tmp dir, so nothing here
touches the developer's real cache.

No `@req` tags: this dispatch carries no registered loom-spec REQ-ids (the plan
binds no change-folder and tracks the work by named plan Tasks), so `@req` is
omitted per the implementer contract rather than invented.
"""
from __future__ import annotations

import contextlib
import datetime
import importlib
import json
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
MARKETS_SCRIPTS = ROOT / "skills" / "data-markets" / "scripts"

# MSFT's FY2025 Q3 10-Q. Values are a filing's real identity shape; no test here
# reaches SEC, so the accession only has to be well-formed and stable.
ACCESSION = "0000950170-25-060448"
# The SAME filing, spelled the other way SEC accessions circulate in — the
# spelling `_accession_nodash` exists to produce, and the one an archives URL
# carries. Written out rather than computed from the module under test.
ACCESSION_NODASH = "000095017025060448"
OTHER_ACCESSION = "0000950170-25-011699"
CIK = 789019
COMPANY = "MICROSOFT CORP"
FORM = "10-Q"
FILING_DATE = datetime.date(2025, 4, 30)

# The cache key family (`raw_filing_<accession-no-dashes>`), spelled out rather
# than computed from the module under test: an expectation derived from the code
# it is checking cannot fail. The key normalises away the dashes so that both
# spellings of one accession share one entry — see
# `test_the_two_spellings_of_one_accession_share_one_cache_entry`.
CACHE_FILENAME = f"raw_filing_{ACCESSION_NODASH}.json"
EXPECTED_SEC_URL = (
    "https://www.sec.gov/Archives/edgar/data/789019/000095017025060448/"
)


class _FakeFiling:
    """The edgartools 5.42.0 `Filing` surface `_acquire_raw_filing` contracts on.

    Deliberately NOT a `MagicMock`: a mock answers every attribute, so every
    assertion about a cache hit's shape would pass on a wrapper that returned
    the wrong filing entirely — this arc's recurring defect. This class answers
    only what the real object answers, and `obj()` returns a value keyed on the
    accession so a blanket-hit wrapper is distinguishable from a keyed one.

    It has no `filing_url`: reaching for one is a Decision Log #3 violation and
    must raise here rather than pass.
    """

    def __init__(self, cik, company, form, filing_date, accession_no,
                 related_entities=None):
        self.cik = cik
        self.company = company
        self.form = form
        self.filing_date = filing_date
        self.accession_no = accession_no

    def obj(self):
        return f"parsed-filing:{self.accession_no}"


def _filing_for(accession):
    return _FakeFiling(
        cik=CIK,
        company=COMPANY,
        form=FORM,
        filing_date=FILING_DATE,
        accession_no=accession,
    )


@contextlib.contextmanager
def _client_with_edgar(get_by_accession_number):
    """Import a FRESH `sec_edgar_client` whose lazy `import edgar` resolves to a
    stub with the given network path, restoring prior `sys.modules` on exit.

    A fresh import per context is what makes the cross-process clause
    executable: the reader below shares nothing in memory with the writer, so a
    hit can only have come off disk.
    """
    if str(MARKETS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(MARKETS_SCRIPTS))
    edgar_stub = mock.MagicMock(name="edgar")
    edgar_stub.Filing = _FakeFiling
    edgar_stub.get_by_accession_number = get_by_accession_number
    saved = {
        name: sys.modules.get(name)
        for name in ("edgar", "requests", "sec_edgar_client")
    }
    sys.modules["edgar"] = edgar_stub
    sys.modules["requests"] = mock.MagicMock(name="requests")
    sys.modules.pop("sec_edgar_client", None)
    try:
        yield importlib.import_module("sec_edgar_client")
    finally:
        for name, module in saved.items():
            if module is not None:
                sys.modules[name] = module
            else:
                sys.modules.pop(name, None)


class _CountingNetwork:
    """The spy on the network path: records every accession it was asked for."""

    def __init__(self):
        self.calls = []

    def __call__(self, accession):
        self.calls.append(accession)
        return _filing_for(accession)


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Pin the toolkit cache dir at a per-test tmp dir so no test can read or
    write the developer's real cache. Exercises the real
    `cache_util.resolve_cache_dir` precedence (INVESTING_TOOLKIT_CACHE wins)."""
    monkeypatch.setenv("INVESTING_TOOLKIT_CACHE", str(tmp_path))
    yield


@pytest.fixture(scope="module")
def warm_cache(tmp_path_factory):
    """Warm one accession ONCE, through the real writer, in a module-scoped dir.

    The two clauses that need a pre-existing cache depend on THIS fixture rather
    than on each other, so every node id in this file passes alone as well as
    in-file — the mechanical check
    `docs/loom/memory/a-no-mutation-test-cannot-baseline-off-shared-fixture-state.md`
    prescribes for order-dependent suites.
    """
    cache_dir = tmp_path_factory.mktemp("raw_filing_cache")
    network = _CountingNetwork()
    with mock.patch.dict(os.environ, {"INVESTING_TOOLKIT_CACHE": str(cache_dir)}):
        with _client_with_edgar(network) as sec:
            written = sec._acquire_raw_filing(ACCESSION)
    assert not isinstance(written, dict), (
        f"warming the cache must yield a Filing, got an error slot: {written!r}"
    )
    assert network.calls == [ACCESSION]
    return {
        "cache_dir": cache_dir,
        "path": cache_dir / "sec_edgar" / CACHE_FILENAME,
    }


def test_second_acquire_of_same_accession_does_not_refetch():
    """Plan Task B RED + GREEN clause 1."""
    network = _CountingNetwork()
    with _client_with_edgar(network) as sec:
        first = sec._acquire_raw_filing(ACCESSION)
        second = sec._acquire_raw_filing(ACCESSION)

    assert network.calls == [ACCESSION], (
        "the second acquire of the same accession must not reach the network; "
        f"the spy recorded {network.calls!r}"
    )
    # The other required half: a hit of the WRONG shape would satisfy the count
    # alone. Compare the ANSWER, not merely the presence of the attributes.
    assert (second.cik, second.company, second.form, second.accession_no) == (
        first.cik, first.company, first.form, first.accession_no
    )
    assert second.filing_date == first.filing_date
    assert second.obj() == first.obj() == f"parsed-filing:{ACCESSION}"


def test_a_different_accession_is_still_fetched():
    """Plan Task B GREEN clause 3 — the cache is keyed, not blanket-hit."""
    network = _CountingNetwork()
    with _client_with_edgar(network) as sec:
        first = sec._acquire_raw_filing(ACCESSION)
        other = sec._acquire_raw_filing(OTHER_ACCESSION)
        again = sec._acquire_raw_filing(ACCESSION)

    assert network.calls == [ACCESSION, OTHER_ACCESSION], (
        "a DIFFERENT accession must still be fetched, and the first one must "
        f"still be a hit afterwards; the spy recorded {network.calls!r}"
    )
    # A wrapper that returned the first filing for every accession would pass a
    # call-count assertion; these pin that each accession got its own answer.
    assert other.accession_no == OTHER_ACCESSION
    assert other.obj() == f"parsed-filing:{OTHER_ACCESSION}"
    assert again.accession_no == ACCESSION
    assert again.obj() == f"parsed-filing:{ACCESSION}"


@pytest.mark.parametrize(
    "first, second",
    [
        pytest.param(ACCESSION, ACCESSION_NODASH, id="dashed-warms-nodash-hits"),
        pytest.param(ACCESSION_NODASH, ACCESSION, id="nodash-warms-dashed-hits"),
    ],
)
def test_the_two_spellings_of_one_accession_share_one_cache_entry(
    tmp_path, first, second,
):
    """One filing, one entry — whichever way the accession is spelled.

    SEC accessions circulate in this module in BOTH spellings; that is why
    `_accession_nodash` exists at all, and `--accession` on this client's CLI
    accepts whatever a user types. Keyed on the raw string, the two spellings of
    the SAME filing are two files and two index scans — never a wrong answer,
    but a second 15.9-29.1 s miss on the one seam built to remove exactly that,
    and (no TTL) two entries that then diverge nowhere and expire never.
    """
    network = _CountingNetwork()
    with _client_with_edgar(network) as sec:
        warm = sec._acquire_raw_filing(first)
        hit = sec._acquire_raw_filing(second)

    assert network.calls == [first], (
        "the second spelling of an accession that is already warm must not "
        f"reach the network; the spy recorded {network.calls!r}"
    )
    assert [p.name for p in sorted((tmp_path / "sec_edgar").iterdir())] == [
        CACHE_FILENAME
    ], "both spellings must land on ONE cache file"
    # The hit is the warmed filing itself, not a same-shaped stand-in.
    assert hit.accession_no == warm.accession_no
    assert hit.obj() == warm.obj() == f"parsed-filing:{first}"


def test_a_cache_hit_carries_filing_date_as_a_date_not_a_string():
    """Plan Task B GREEN clause 4 — assert the TYPE, not the value.

    `Filing.from_dict` coerces `filing_date=str(...)`, so reading the cache back
    through it yields a `str` where a live acquisition yields a `datetime.date`.
    No count-based or value-based assertion sees that: `str(date)` renders
    exactly `"2025-04-30"`, which compares equal to the string.
    """
    network = _CountingNetwork()
    with _client_with_edgar(network) as sec:
        sec._acquire_raw_filing(ACCESSION)
        hit = sec._acquire_raw_filing(ACCESSION)

    assert network.calls == [ACCESSION]
    assert type(hit.filing_date) is datetime.date, (
        "a cache hit must restore `filing_date` as a datetime.date, the type a "
        "live acquisition carries; got "
        f"{type(hit.filing_date).__name__} ({hit.filing_date!r}) — "
        "`Filing.from_dict` is the likely cause, use date.fromisoformat"
    )
    assert hit.filing_date == FILING_DATE


def test_a_failed_acquisition_is_surfaced_and_never_cached(tmp_path):
    """Beyond the four ratified clauses, and deliberately so: the cache has NO
    TTL, so an error slot written to disk would be a PERMANENT wrong answer that
    never self-heals — a transient 429/403 poisoning a filing for good. The
    module docstring claims this property; an unpinned claim in a docstring is
    how the same defect ships twice.
    """
    calls = []

    def _fails_then_succeeds(accession):
        calls.append(accession)
        if len(calls) == 1:
            raise RuntimeError("transient 429 from SEC")
        return _filing_for(accession)

    with _client_with_edgar(_fails_then_succeeds) as sec:
        failed = sec._acquire_raw_filing(ACCESSION)
        assert isinstance(failed, dict) and "error" in failed, (
            f"a failed acquisition must be a loud error slot, got {failed!r}"
        )
        assert not (tmp_path / "sec_edgar" / CACHE_FILENAME).exists(), (
            "an acquisition failure was written to a cache that has no TTL — "
            "it would never self-heal"
        )
        # The retry must actually reach the network, and must then succeed.
        recovered = sec._acquire_raw_filing(ACCESSION)

    assert calls == [ACCESSION, ACCESSION]
    assert recovered.accession_no == ACCESSION
    assert recovered.obj() == f"parsed-filing:{ACCESSION}"


_ABSENT = object()


def _ratified_payload():
    """A well-formed on-disk payload — the shape every corrupt row below is a
    single mutation away from."""
    return {
        "accession": ACCESSION,
        "fetched_at": "2026-07-31T00:00:00Z",
        "sec_url": EXPECTED_SEC_URL,
        "filing": {
            "accession_number": ACCESSION,
            "cik": CIK,
            "company": COMPANY,
            "form": FORM,
            "filing_date": "2025-04-30",
        },
    }


def _payload_whose_filing_is(value):
    payload = _ratified_payload()
    if value is _ABSENT:
        payload.pop("filing")
    else:
        payload["filing"] = value
    return payload


def _filing_minus(key):
    stored = _ratified_payload()["filing"]
    stored.pop(key)
    return stored


def _filing_with(key, value):
    stored = _ratified_payload()["filing"]
    stored[key] = value
    return stored


@pytest.mark.parametrize(
    "corrupt_payload, raw_text",
    [
        pytest.param(_payload_whose_filing_is(_ABSENT), None,
                     id="filing-key-absent"),
        pytest.param(_payload_whose_filing_is("MICROSOFT CORP 10-Q"), None,
                     id="filing-is-a-json-string"),
        pytest.param(_payload_whose_filing_is(_filing_minus("cik")), None,
                     id="cik-key-missing"),
        pytest.param(_payload_whose_filing_is(_filing_with("cik", None)), None,
                     id="cik-is-null"),
        pytest.param(
            _payload_whose_filing_is(_filing_with("filing_date", "30 April 2025")),
            None, id="filing-date-is-not-iso"),
        pytest.param(None, '{"_cache_meta": {"version"', id="file-is-not-json"),
    ],
)
def test_a_corrupt_cache_entry_refetches_and_self_heals(
    tmp_path, corrupt_payload, raw_text,
):
    """The recovery path, pinned by the same argument that justifies
    `test_a_failed_acquisition_is_surfaced_and_never_cached`.

    That test holds that a FAILURE must never be written, because a cache with
    no TTL makes a bad entry permanent. This one holds the other half: an entry
    that IS on disk but malformed — a truncated write, a hand-edited file, an
    envelope written by an older shape of this code — must ALSO not be
    permanent. Nothing expires it, so the only escape is that a malformed entry
    reads as a miss, refetches, and overwrites itself. If any of these rows
    raised, or returned the unusable `None` the rebuild yields, the filing would
    be dead on that machine until someone deleted the file by hand.

    The rows are chosen to reach DIFFERENT branches of the rebuild, because a
    single corrupt shape exercises only one of them:

      - `filing-key-absent` / `filing-is-a-json-string` stop at the non-dict
        early-out and never enter the try block;
      - `cik-key-missing` raises KeyError, `cik-is-null` raises TypeError (from
        `int(None)`), `filing-date-is-not-iso` raises ValueError (from
        `date.fromisoformat`) — one row per member of the caught tuple, so
        narrowing that tuple to any two of the three fails here;
      - `file-is-not-json` never reaches this module's rebuild at all; it pins
        that `cache_util.load_cache`'s own fail-open still reads as a miss here
        rather than as an empty hit.
    """
    path = tmp_path / "sec_edgar" / CACHE_FILENAME
    network = _CountingNetwork()

    with _client_with_edgar(network) as sec:
        if raw_text is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(raw_text)
        else:
            sec.cache_util.save_cache(path, corrupt_payload)
        assert path.exists(), "the corrupt entry must be on disk before the read"

        healed = sec._acquire_raw_filing(ACCESSION)
        # Same accession again: a self-heal that did not OVERWRITE the corrupt
        # entry would refetch forever, which is the permanence this pins.
        second = sec._acquire_raw_filing(ACCESSION)

    assert network.calls == [ACCESSION], (
        "a malformed cache entry must read as a MISS (refetch, exactly once) "
        f"and then heal itself; the spy recorded {network.calls!r}"
    )
    assert not isinstance(healed, dict), (
        f"expected a refetched Filing, got {healed!r}"
    )
    assert (healed.accession_no, healed.cik, healed.company, healed.form) == (
        ACCESSION, CIK, COMPANY, FORM
    )
    assert healed.obj() == f"parsed-filing:{ACCESSION}"
    assert second.accession_no == ACCESSION
    assert second.obj() == f"parsed-filing:{ACCESSION}"
    assert type(second.filing_date) is datetime.date

    # The corrupt bytes are gone: what is on disk is the ratified payload.
    stored = json.loads(path.read_text())["data"]
    assert stored["filing"] == _ratified_payload()["filing"]


def test_the_identity_guard_precedes_even_a_warm_cache_hit(
    warm_cache, monkeypatch,
):
    """The SEC fair-access identity is a precondition of this client, not a
    pre-send optimization — so it is enforced on the cache-hit path too.

    A cache hit sends nothing, which is exactly why the ordering is invisible to
    every other test here: move the identity guard BELOW the cache read and the
    whole suite still passes, while a caller with no compliant `<name> <email>`
    identity silently starts getting served. The claim in `_acquire_raw_filing`
    that the guard stays FIRST is a decision about this seam's contract
    (`_acquire_raw_filing` returns a loud error slot when the identity is
    unset — full stop, warm or cold), and a decision with nothing checking it is
    the kind that gets refactored away by accident.
    """
    monkeypatch.setenv("INVESTING_TOOLKIT_CACHE", str(warm_cache["cache_dir"]))

    def _network_must_not_be_reached(accession):
        raise RuntimeError(f"the network path was reached for {accession}")

    with _client_with_edgar(_network_must_not_be_reached) as sec:
        # A non-compliant User-Agent: one token, no email — `_is_compliant_identity`
        # requires at least one name token BEFORE an email-shaped one.
        monkeypatch.setattr(sec, "USER_AGENT", "anonymous")
        result = sec._acquire_raw_filing(ACCESSION)

    assert isinstance(result, dict) and "error" in result, (
        "a warm cache must not serve a caller whose SEC identity is unset; got "
        f"{result!r}"
    )
    assert "identity not configured" in result["error"]


def test_the_cache_file_on_disk_is_the_ratified_envelope(warm_cache):
    """Plan Decision Log #3 — the on-disk format is a ratified one-way door.

    Key sets are asserted EXACTLY at both levels: adding a field later
    invalidates every cached filing on every user's machine, at 20-37 minutes
    per filer to rebuild, so a quiet widening has to fail here.
    """
    stored = json.loads(warm_cache["path"].read_text())
    payload = stored["data"]  # cache_util wraps the payload under `data`

    assert set(payload) == {"accession", "fetched_at", "sec_url", "filing"}
    assert set(payload["filing"]) == {
        "accession_number", "cik", "company", "form", "filing_date",
    }
    assert payload["accession"] == ACCESSION
    assert payload["filing"] == {
        "accession_number": ACCESSION,
        "cik": CIK,
        "company": COMPANY,
        "form": FORM,
        "filing_date": "2025-04-30",
    }
    # The reconstructable archives URL, never `Filing.filing_url` (which costs a
    # network round-trip to resolve the primary document).
    assert payload["sec_url"] == EXPECTED_SEC_URL
    assert payload["fetched_at"].endswith("Z")


def test_a_fresh_import_reads_the_warm_cache_with_the_network_made_to_raise(
    warm_cache, monkeypatch,
):
    """Plan Task B GREEN clause 2 — the executable form of "a fresh process gets
    a disk hit".

    The network path RAISES rather than returning a filing: a stub that answered
    would let this clause pass on a cache that silently refetched every time.
    """
    monkeypatch.setenv("INVESTING_TOOLKIT_CACHE", str(warm_cache["cache_dir"]))

    def _network_must_not_be_reached(accession):
        raise RuntimeError(
            "the network path was reached for an accession that is warm on "
            f"disk: {accession}"
        )

    with _client_with_edgar(_network_must_not_be_reached) as sec:
        hit = sec._acquire_raw_filing(ACCESSION)

    assert not isinstance(hit, dict), (
        "expected a Filing reconstructed from disk; got an error slot, which "
        "means the network path WAS reached and its failure was swallowed into "
        f"an acquisition error: {hit!r}"
    )
    assert hit.accession_no == ACCESSION
    assert (hit.cik, hit.company, hit.form) == (CIK, COMPANY, FORM)
    assert type(hit.filing_date) is datetime.date
    assert hit.obj() == f"parsed-filing:{ACCESSION}"
