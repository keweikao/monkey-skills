---
name: 2026-08-05-cache-key-made-acquire-raw-filing-none-crash-instead-of-fail-loudly
description: Task B's cache key made _acquire_raw_filing(None) crash where it used to fail loudly — a live regression with four untraced call sites
status: OPEN
origin: found by Task J's implementer, independently reproduced by both Task J reviewers, branch feat-us-quarterly-statement-series (2026-08-05)
start: before any live multi-filing run reaches a filer with a missing form, or on the next touch of pack_us._fetch_xval_source_a
---

- Start: before any live multi-filing run reaches a filer with a missing form
  (Task H's one-off live run is the first that would), or on the next touch of
  `pack_us._fetch_xval_source_a`. It is a live regression in shipped behaviour,
  not a latent risk.
- Origin: found by Task J's implementer while fixing the same root cause in its
  own loop; independently reproduced by both of Task J's reviewers
  (branch `feat-us-quarterly-statement-series`, 2026-08-05).
- **The root cause**: `_acquire_raw_filing` used to go straight from its identity
  guard into `try: edgar.get_by_accession_number(accession)`, so a `None`
  accession raised INSIDE the try and came back as a loud `{"error": ...}` slot.
  Task B inserted the cache-key computation AHEAD of that `try`, and
  `_accession_nodash` is not defensive:
  `AttributeError: 'NoneType' object has no attribute 'replace'`.
  **Verified 2026-08-05 by executing it** (faked `edgar`, temp cache dir); the
  identity guard does not intercept, because `USER_AGENT` is a compliant constant.
- **The confirmed live site**: `pack_us._fetch_xval_source_a` takes
  `accession = _latest_10k_accession(filings_rows)`, whose signature is
  `str | None` and which returns `None` when no 10-K row exists, then hands it
  straight to `_acquire_raw_filing`. **So a filer with no 10-K in the window now
  aborts memo-fetch with a traceback instead of reporting a wholesale failure.**
  Its own docstring still asserts the expired premise — "which already returns a
  loud resolution error slot ... no separate guard is needed here to avoid a
  crash". Verified 2026-08-05 by opening both.
  Its test cannot see it: the test mocks the boundary, so nothing exercises the
  real `None` path.
- **What is NOT known**: `_acquire_raw_filing` has six call sites (three in
  `sec_edgar_client.py`, three in `pack_us.py`). Only two have been traced —
  Task J's loop (fixed in that task) and `_fetch_xval_source_a` (this entry).
  **The other four have not been checked for whether their accession can be
  `None`**, and a grep does not answer that; each needs its producer traced.
  Do not treat this entry as a complete inventory.
- Fix shape: make `_acquire_raw_filing` `None`-safe at its own head — return the
  same loud resolution slot it used to, restoring the contract every caller and
  several docstrings still assume. That is one guard against six unaudited
  callers, versus a guard at each call site. Then correct the two docstrings that
  still state the expired premise.
- A pre-existing test also asserts the expired premise in prose and cites a line
  range Task B invalidated (`test_data_markets_us.py`, the no-10-K wholesale
  failure test). Task J's round 2 corrected that prose; the underlying test still
  mocks the boundary and so still does not exercise the real path.
