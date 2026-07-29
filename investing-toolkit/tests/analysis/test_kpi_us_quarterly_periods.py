"""Tests for analysis-kpi/scripts/kpi_us_quarterly_periods.py — classify one
period key into an explicit kind (plan Task C,
docs/loom/plans/2026-07-28-us-quarterly-statement-series.md).

`period_kind(period_key)` maps a `duration_<start>_<end>` / `instant_<date>`
key to one of `discrete_quarter | ytd | annual | instant | unknown` by
day-span bucketing. `unknown` is load-bearing: a span outside every window
must say so rather than round to the nearest bucket — a 52/53-week filer
(plan Task G) or a transition year can produce exactly such a span.

FIXTURE PROVENANCE, stated per row and never in bulk. Six of the
`duration_` / `instant_` keys below are copied verbatim from a period key
already committed to disk in this repo, not invented for this test — these
are labelled OBSERVED:

  - `duration_2024-07-01_2024-09-30`, `duration_2024-01-01_2024-12-31`, and
    `duration_2024-08-31_2024-08-31` (the same-day, 0-day-span duration) all
    appear in `tests/data/fixtures/us_statement_reconstruction_2026-07-26.json`.
  - `duration_2025-01-27_2025-07-27` appears in
    `tests/data/fixtures/xbrl_quarterly_nvda_range.json`.
  - `duration_2016-09-25_2017-09-30` and `instant_2025-12-31` also appear in
    this suite's own `test_kpi_us_statement_series.py` /
    `test_kpi_us_statement_cells.py`.

The two required examples from the task brief — an 89-day discrete quarter
and a 273-day Q3-YTD — are `duration_2026-01-01_2026-03-31` and
`duration_2025-07-01_2026-03-31`. These are REAL MSFT fiscal-Q3-FY2026
values — one discrete-quarter, one YTD-cumulative, both ending 2026-03-31 —
MEASURED from a live 10-Q during a 2026-07-28 feasibility probe. (MSFT's
fiscal year ends June 30, so the quarter ending 2026-03-31 is fiscal Q3, not
Q1 — confirmed by this same repo's `duration_2024-07-01_2025-06-30`, a
364-day FY2025 annual anchor in
`tests/data/fixtures/us_quarterly_stitched_msft.json`.)

That probe's output was session-scoped and no longer exists, so these two
values cannot currently be re-derived from the probe itself. They ARE,
however, verbatim-present in
`tests/data/fixtures/us_quarterly_stitched_msft.json` (spans of exactly 89
and 273 days) — Task D's fixture, which landed in this working tree while
this task was in flight, and which `git ls-files` does not list (untracked
as of this writing). This file deliberately does NOT cite that fixture as
this test's source: Task C is `Independent: true` (plan:82-83), and citing
into a sibling task's not-yet-landed artifact would create exactly the
undeclared cross-task dependency that flag exists to forbid. So: absent
from every TRACKED fixture and every other test file in this repo — not
"absent from every fixture" — and these two rows stay labelled MEASURED,
distinct from both OBSERVED (repo-verifiable, tracked) and CONSTRUCTED
(invented, no real-world referent).

The task brief's day-counts do appear in the plan text itself:
`docs/loom/plans/2026-07-28-us-quarterly-statement-series.md:80` reads
"...a 273-day Q3-YTD and an 89-day quarter" in prose. The period-key
STRINGS above, though, do not appear anywhere in the plan or brief text.

`not_a_period_key` is the one CONSTRUCTED row in the main table: no real key
of this shape exists anywhere; it exists only to pin the parse-failure path.
The 16 window-edge rows in `test_period_key_classifies_window_edges` below
are also CONSTRUCTED — built from a fixed start date to land exactly on each
window boundary — and are labelled as such at that test.

No `@req` tags: this dispatch carries no registered loom-spec REQ-ids (the
work is tracked by named plan Task C), so `@req` is omitted per the
implementer contract.
"""
from __future__ import annotations

import importlib.util
import sys

import pytest
from conftest import SKILLS

PERIODS_SCRIPT = SKILLS / "analysis-kpi" / "scripts" / "kpi_us_quarterly_periods.py"


def _load(name: str, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def periods():
    return _load("kpi_us_quarterly_periods_test", PERIODS_SCRIPT)


@pytest.mark.parametrize(
    "period_key,expected_kind,provenance",
    [
        # Required example — an 89-day discrete quarter. MEASURED: real MSFT
        # fiscal-Q3 FY2026 value from a live 10-Q probe (2026-07-28), NOT
        # re-derivable from this repo — see module docstring provenance note.
        ("duration_2026-01-01_2026-03-31", "discrete_quarter", "MEASURED-not-repo fiscal-Q3 89d"),
        # A second discrete-quarter shape (91 days), OBSERVED in
        # us_statement_reconstruction_2026-07-26.json.
        ("duration_2024-07-01_2024-09-30", "discrete_quarter", "OBSERVED Q3 91d"),
        # Required example — a 273-day Q3 YTD (the 260-285 YTD window).
        # MEASURED: real MSFT Q3-YTD FY2026 value from the same live 10-Q
        # probe, NOT re-derivable from this repo — see module docstring.
        ("duration_2025-07-01_2026-03-31", "ytd", "MEASURED-not-repo Q3-YTD 273d"),
        # A 181-day H1 YTD, exercising the OTHER YTD window (175-190),
        # OBSERVED in xbrl_quarterly_nvda_range.json.
        ("duration_2025-01-27_2025-07-27", "ytd", "OBSERVED H1-YTD 181d"),
        # A 365-day calendar-year annual duration, OBSERVED in
        # us_statement_reconstruction_2026-07-26.json.
        ("duration_2024-01-01_2024-12-31", "annual", "OBSERVED calendar-year FY"),
        # A 370-day 52/53-week-shaped annual duration (still inside 350-380),
        # OBSERVED in test_kpi_us_statement_series.py.
        ("duration_2016-09-25_2017-09-30", "annual", "OBSERVED 52/53wk FY"),
        # An instant key.
        ("instant_2025-12-31", "instant", "OBSERVED instant"),
        # OBSERVED same-day duration (0-day span) — genuinely out of every
        # window, must be visible as `unknown`, not rounded to the nearest
        # bucket.
        ("duration_2024-08-31_2024-08-31", "unknown", "OBSERVED 0-day span"),
        # CONSTRUCTED: not shaped like either prefix at all — the parse-
        # failure path must return `unknown`, never raise.
        ("not_a_period_key", "unknown", "CONSTRUCTED malformed key"),
    ],
)
def test_period_key_classifies_by_span(periods, period_key, expected_kind, provenance):
    assert periods.period_kind(period_key) == expected_kind, (
        f"{provenance}: {period_key!r} expected {expected_kind!r}"
    )


def test_malformed_duration_key_returns_unknown_not_raise(periods):
    """A duration-shaped key whose dates don't parse must not raise — the
    caller is projecting a whole filing and one bad key must not abort it."""
    assert periods.period_kind("duration_not-a-date_2026-03-31") == "unknown"


# All 16 rows below are CONSTRUCTED: built from a fixed 2024-01-01 start
# date with the end date chosen to land the day span exactly on (or one day
# outside) each of the module's eight window edges — no real filing needs
# to exhibit these exact spans for the test to matter; the module's whole
# behaviour IS these eight constants, and a table that cannot fail on any of
# them (a mutant narrowing every window AND flipping every `<=` to `<` left
# the previous table's non-edge spans all green) tests nothing that
# matters about them. Do not read these as OBSERVED filing data.
@pytest.mark.parametrize(
    "period_key,expected_kind,edge_description",
    [
        # discrete_quarter window (80, 100)
        ("duration_2024-01-01_2024-03-21", "discrete_quarter", "quarter low edge 80 (inside)"),
        ("duration_2024-01-01_2024-03-20", "unknown", "quarter low edge 79 (just outside)"),
        ("duration_2024-01-01_2024-04-10", "discrete_quarter", "quarter high edge 100 (inside)"),
        ("duration_2024-01-01_2024-04-11", "unknown", "quarter high edge 101 (just outside)"),
        # ytd window 1 (175, 190) — H1
        ("duration_2024-01-01_2024-06-24", "ytd", "ytd-H1 low edge 175 (inside)"),
        ("duration_2024-01-01_2024-06-23", "unknown", "ytd-H1 low edge 174 (just outside)"),
        ("duration_2024-01-01_2024-07-09", "ytd", "ytd-H1 high edge 190 (inside)"),
        ("duration_2024-01-01_2024-07-10", "unknown", "ytd-H1 high edge 191 (just outside)"),
        # ytd window 2 (260, 285) — Q3
        ("duration_2024-01-01_2024-09-17", "ytd", "ytd-Q3 low edge 260 (inside)"),
        ("duration_2024-01-01_2024-09-16", "unknown", "ytd-Q3 low edge 259 (just outside)"),
        ("duration_2024-01-01_2024-10-12", "ytd", "ytd-Q3 high edge 285 (inside)"),
        ("duration_2024-01-01_2024-10-13", "unknown", "ytd-Q3 high edge 286 (just outside)"),
        # annual window (350, 380)
        ("duration_2024-01-01_2024-12-16", "annual", "annual low edge 350 (inside)"),
        ("duration_2024-01-01_2024-12-15", "unknown", "annual low edge 349 (just outside)"),
        ("duration_2024-01-01_2025-01-15", "annual", "annual high edge 380 (inside)"),
        ("duration_2024-01-01_2025-01-16", "unknown", "annual high edge 381 (just outside)"),
    ],
)
def test_period_key_classifies_window_edges(periods, period_key, expected_kind, edge_description):
    """Pin every one of the module's 8 window-edge constants: the inside
    value must classify and the just-outside neighbour must fall to
    `unknown`. Without these, a mutant narrowing all four windows AND
    flipping all eight `<=` to `<` leaves the (deliberately non-edge)
    rows above all green — this module's whole behaviour IS these 8
    constants, so a table that can't fail on them tests nothing load-bearing."""
    assert periods.period_kind(period_key) == expected_kind, (
        f"{edge_description}: {period_key!r} expected {expected_kind!r}"
    )
