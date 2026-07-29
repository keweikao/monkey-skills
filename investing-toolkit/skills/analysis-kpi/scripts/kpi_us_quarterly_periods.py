#!/usr/bin/env python3
"""kpi_us_quarterly_periods.py — classify one period key into an explicit
kind (plan Task C, docs/loom/plans/2026-07-28-us-quarterly-statement-series.md).

`period_kind(period_key)` answers, for ONE period key, which of
`discrete_quarter | ytd | annual | instant | unknown` it is, by bucketing the
duration's day span. `derived` (a Q4 = FY - Q3-YTD period, plan Task E) is a
SEPARATE boolean flag a later task adds — NOT a sixth kind value here (plan
Decision Log, one-way door #1) — because a derived Q4 is both a discrete
quarter AND derived, and collapsing the two axes makes "every discrete
quarter regardless of provenance" unaskable.

`unknown` IS AN ANSWER, NOT A FAILURE — this module's own load-bearing case.
A span that fits no window must stay VISIBLE as `unknown` rather than round to
the nearest bucket: a 52/53-week filer's quarters vary year to year and can
fall outside a naive window (plan Task G), and a transition-year filing can
produce a stub period the three ordinary kinds do not describe. Rounding
either into "the nearest kind" would silently mislabel it.

DAY-SPAN WINDOWS ALIGN WITH THE DEPENDENCY, NOT INVENTED HERE (plan Decision
Log, two-way door): `discrete_quarter` 80-100, `ytd` 175-190 OR 260-285,
`annual` 350-380. An `instant_<date>` key is always `instant`, regardless of
whether its date parses — the shape of the key (not the validity of its
date) is what `instant_` answers; a duration key's DATES have to parse
because the day span is computed from them, but an instant key carries no
span to compute.

PURE, STDLIB ONLY: no network, no `edgartools` import, no I/O, no logging, no
caching, no module-level state — deliberately, so a sibling task (Task G,
Task D) can import this module without pulling in the dependency this arc's
other modules need. `date.fromisoformat` is the only parsing this module
does.

A MALFORMED KEY MUST NOT RAISE — the caller is projecting a whole filing's
period keys at once, and one bad key must not abort the rest. A key that is
not shaped like `duration_<start>_<end>` or `instant_<date>` at all, or whose
dates do not parse, returns `unknown` exactly the same as an out-of-window
span: both mean "do not read a span from this key."

No `@req` tags: this dispatch carries no registered loom-spec REQ-ids (the
work is tracked by named plan Task C), so `@req` is omitted per the
implementer contract.
"""
from __future__ import annotations

from datetime import date

_DURATION_PREFIX = "duration_"
_INSTANT_PREFIX = "instant_"

# Inclusive day-span windows, aligned with the dependency's own boundaries
# (plan Decision Log) rather than invented here.
_DISCRETE_QUARTER_SPAN = (80, 100)
_YTD_SPANS = ((175, 190), (260, 285))
_ANNUAL_SPAN = (350, 380)


def period_kind(period_key: str) -> str:
    """Classify `period_key` as `"discrete_quarter"`, `"ytd"`, `"annual"`,
    `"instant"`, or `"unknown"`.

    `"unknown"` covers three different cases and deliberately does not
    distinguish them: a key not shaped like either prefix, a duration key
    whose dates do not parse, and a duration key whose span fits no window.
    All three mean the same thing to a caller — do not read a kind from this
    key.

    A Q1 discrete quarter and a Q1-YTD span are day-count identical (both
    land in the 80-100 window) and both classify as `"discrete_quarter"` —
    intentional, since a fiscal Q1 IS its own YTD; Task F, which consumes
    this label, should know the two are indistinguishable by span alone.
    """
    if period_key.startswith(_INSTANT_PREFIX):
        return "instant"
    if period_key.startswith(_DURATION_PREFIX):
        span = _duration_span_days(period_key)
        if span is None:
            return "unknown"
        return _kind_for_span(span)
    return "unknown"


def _duration_span_days(period_key: str) -> int | None:
    """The day span of a `duration_<start>_<end>` key, or `None` when the
    key does not carry exactly two ISO dates after the prefix."""
    rest = period_key[len(_DURATION_PREFIX):]
    parts = rest.split("_")
    if len(parts) != 2:
        return None
    start_str, end_str = parts
    try:
        start = date.fromisoformat(start_str)
        end = date.fromisoformat(end_str)
    except ValueError:
        return None
    return (end - start).days


def _kind_for_span(span: int) -> str:
    """Bucket one day span into a kind, or `"unknown"` when it fits none of
    the three windows."""
    if _DISCRETE_QUARTER_SPAN[0] <= span <= _DISCRETE_QUARTER_SPAN[1]:
        return "discrete_quarter"
    if any(low <= span <= high for low, high in _YTD_SPANS):
        return "ytd"
    if _ANNUAL_SPAN[0] <= span <= _ANNUAL_SPAN[1]:
        return "annual"
    return "unknown"
