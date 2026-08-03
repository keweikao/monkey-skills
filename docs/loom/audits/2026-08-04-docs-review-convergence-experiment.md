# Why a docs-review round never returns empty — a controlled measurement

**Date**: 2026-08-04
**Subject**: `loom-code:requesting-docs-review`'s convergence contract
**Method**: four fresh `docs-reviewer` dispatches over one already-passed branch

## What prompted it

PR #643 closed with the docs arm converging at round 4 — two independent
arms returning PASS and PASS_WITH_NOTES, zero instruction-class findings.
Hours later the question was whether the arm had converged because the
artifacts were clean, or because the round cap had run out.

A proposal was on the table at the time: add a **harm gate** to the
docs-reviewer contract, requiring a finding to name the concrete harm a
reader would suffer before it could gate. The stated theory was that the
loop is driven by findings that are technically true but consequence-free.

## Design

Twelve merged `.md` artifacts from PR #643 — the exact tree that had
passed round 4 — were handed to four fresh `docs-reviewer` dispatches
with no knowledge of each other or of the prior rounds.

| Arm | Contract |
|---|---|
| Control A, Control B | the shipped contract, unchanged |
| Treatment A, Treatment B | the shipped contract plus the harm gate |

Predictions were registered before dispatch. The one that mattered:
**if the treatment arms return the same gating-finding count as the
controls, the harm gate does not address the mechanism and the proposal
is dropped.**

## Result

| Arm | Gating findings (`class: instruction`) | Verdict |
|---|---|---|
| Control A | 1 | PASS_WITH_NOTES |
| Control B | 2 | NEEDS_REVISION |
| Treatment A | 2 | NEEDS_REVISION |
| Treatment B | 2 | NEEDS_REVISION |

**The harm gate did not reduce gating findings.** The criterion actually
applied was the weaker, one-sided form: *no reduction* — the treatment
counts (2, 2) sit at the top of the controls' range (1, 2), so the gate
removed nothing. The registered wording said "the same count", which the
literal reading (1 vs 2) does not satisfy; the one-sided form is what was
used and what the conclusion rests on. Either way the proposal was
dropped, unbuilt.

The result that was not predicted is the load-bearing one:

> **The four arms' gating findings did not overlap at all.** Seven
> distinct findings; no two reviewers raised the same one.

## Were they real?

All seven were checked, but not to the same depth, and the difference
matters to what this audit may be cited for. Each of the seven was read
against the text it cited and found to describe that text accurately —
no finding pointed at a passage that did not say what it claimed. Two
were additionally confirmed by running the command that decides them,
both against artifacts that had passed round 4 that same day:

- `docs/loom/memory/enumerate-every-copy-before-editing-a-claim-and-name-the-leaks.md`
  — the frontmatter `description` presented the hard-wrap leak as open
  ("hard-wrapped so a quote split across two lines matches nothing")
  while the body stated the opposite ("The unwrapping half is now
  mechanised"). **The quoted description no longer exists**: the same
  commit that added this audit rewrote it, so a reader checking the file
  today finds the corrected text, not the contradiction.
  `scripts/check_loom_memory_integrity.py` exited 0 on it throughout:
  the checker compares the index line against the frontmatter
  byte-for-byte and never compares either against the body.
- `docs/loom/specs/2026-08-03-claim-copy-sweep.md:82` — states the tool
  accepts a claim via `--claim` **or stdin**. `grep -c stdin
  scripts/claim_copy_sweep.py` returns 0. PR #643 (`9960b202`) was a
  mixed branch: the spec is `.md` and went to the docs arm, the script
  is `.py` and went to the code arm. Under the per-file split then in
  force, the reviewer that read the claim was not given the file that
  falsifies it. What the code arm did or did not read is not recorded —
  the observable fact is the scope split, not the other arm's attention.

None was manufactured — meaning none cited a passage that did not exist
or did not say what the finding said. That is the claim this audit
supports; it is not a claim that all seven were worth fixing.

## What this means

The mechanism behind the non-converging loop is not that reviewers
invent findings. It is arithmetic:

> **A document carrying many small real defects, reviewed by a sampler,
> yields new findings on every pass. A stop rule keyed on "did the
> reviewer find anything" can never terminate.**

The hard 2-round cap is therefore correct — but not for the reason the
skill stated. It is not that extra rounds manufacture defects; it is
that no round count reaches an empty round. The cap exists because
"reviewer found nothing" is not a reachable state, so it cannot be the
termination condition.

The two framings prescribe opposite reader behaviour, which is why the
distinction is worth the edit:

| Framing | What a reader does with round-2 findings |
|---|---|
| *extra rounds manufacture defects* | discount them — they are probably artifacts |
| *the pool is large and sampled* | treat them as real; decide on severity, not on exhaustion |

The second also yields the operative consequence: **a deterministic
check outranks another review round.** A checker returns the same
finding on every run; a reviewer returns a different subset each time.
Both of the hand-verified findings above are of a kind a mechanism
could have held, and each fed one follow-up: the description-vs-body
contradiction produced the `description` rule now in
`docs/loom/memory/README.md` §Format (a format contract, not a detector
— `docs/loom/memory/measure-a-checks-fire-rate-before-building-it.md`
records why), and the stdin claim produced the `read-context` field in
`requesting-code-review` Step 1 / `requesting-docs-review` Step 3.

## Limits — stated, not buried

- Four arms over **one** branch's artifacts. This measures that the pool
  is large and disjointly sampled on this corpus; it does not
  generalize a rate.
- Severity was not controlled. All seven findings were `🟡`-class; the
  experiment says nothing about whether `🔴` findings overlap more.
- The harm gate was refuted **as a lever on finding count**. It was not
  tested as a lever on relay quality, which is a different claim.
- **Zero overlap characterises the tail, not review in general.** The
  four-arm review of the branch that shipped this audit overlapped on
  three locations out of its seven distinct findings — the opposite
  result. The difference is what the tree carried: the measurement above
  ran against an already-passed corpus holding only small residual
  defects, while that branch carried a structural gap (a mechanism
  written into the skill layer but not into the agent contract that
  executes it). Both arms found the structural gap; neither found the
  other's residual nits. So a panel does converge on structural defects,
  and the disjoint sampling above is a property of the residual tail.

## Corrections this arc's research pass produced

The session that led here ran a deep-research pass whose first-round
output was checked against primary sources. The corrections are recorded
because each would have changed a decision. **Citation status, stated
rather than implied**: only the κ bullet carries a document identifier.
The others name an author, venue, or literature by description, and the
primary documents were not re-opened while writing this audit. Treat
every bullet below as a pointer to re-verify before reuse, not as a
citation that has been checked here:

- **The κ≈0.3 figure for LLM-as-judge agreement** was misattributed
  (arXiv 2505.12201, not the number first cited) and mis-scoped: it
  measures one judge's cross-language self-consistency, not inter-judge
  agreement. English-language benchmarks report κ spanning 0.271–0.898.
- **"Anthropic models have the worst false-positive rate on clean
  prose"** inverted the finding. Models scoring zero false positives do
  so with d′ = −0.17 and 100% orchestrated false negatives — a hit rate
  pinned to the floor, not accuracy. Acting on the inverted reading would
  have swapped in a model that detects nothing.
- **"No published practice keys a review stop rule on findings"** was a
  universal negative asserted from two examples, both of which key on
  findings.
- **"Seeded defects are easier to find than real ones"** had the
  direction and the attribution wrong. Andrews/Briand/Labiche (ICSE
  2005) find generated mutants resemble real faults, while hand-seeded
  defects are *harder*.
- **"Prose admits no cheap ground-truth generator"** is false; error
  seeding for documents dates to the Basili/NASA inspection work.

## Consumers

Every place that cites this audit, so an editor revising a claim above
knows what depends on it:

- `loom-code/skills/requesting-docs-review/SKILL.md` — Directive 1's
  rationale, the matching red-flag row, and Step 3's `read-context`
  rationale (the stdin miss).
- `loom-code/CHANGELOG.md` — the 0.47.0 entry.
- `docs/loom/memory/README.md` §Format — the description-vs-body
  contradiction above is the recorded instance behind its rule.

Re-run the list with `python3 scripts/claim_copy_sweep.py --claim
"2026-08-04-docs-review-convergence-experiment"` rather than trusting
this enumeration after either document moves.
