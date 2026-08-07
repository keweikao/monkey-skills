# Changelog

All notable changes to the `loom-discovery` plugin will be documented in this
file.

Format: [Keep a Changelog](https://keepachangelog.com/).
Versioning: [Semantic Versioning](https://semver.org/).

## [0.4.1] — 2026-08-07 — plugin description back inside the listing's range

### Changed

- **Plugin description** cut from 1005 to 104 characters across
  `marketplace.json`, `.claude-plugin/plugin.json`, and
  `.codex-plugin/plugin.json`. The old string enumerated both skills with
  their gate vocabularies, the artifact directory layout, and the delegation
  rules — README content on a browse surface, and a 4.6x outlier against the
  next-longest plugin (216) in a listing whose median is 97. The detail is
  not lost: `.codex-plugin`'s `longDescription` and `README.md` both retain
  it. Finishes the sweep of #437 (all 25 descriptions to one-line taglines)
  and #494 (seven more), which `loom-discovery` missed by landing later
  in #523.
- **This is a patch RELEASE, not a metadata-only edit.** Claude Code CLI
  reads the installed `plugin.json` when listing plugins (see
  `scripts/check-marketplace-description-sync.py`'s docstring); without a
  version bump, existing CLI installs would keep displaying the 1005-char
  string until the next release — the exact surface this change fixes.
  Claude Desktop and fresh installs read `marketplace.json` and would have
  refreshed either way.

### Unchanged — deliberately

- The `user-insights` SKILL frontmatter description stays at its measured
  899-character pin. `docs/skill-dogfood/2026-07-30-description-diet-firing-ab/`
  found that string regresses at three separate diet bands (170 / 217 / 493)
  against the `loom-pipeline:loom-memory` guard pair, and requires a same-day
  two-leg A/B before any future attempt. That pin is a skill-routing surface;
  the plugin manifest edited here is a browse blurb that no experiment has
  ever varied. The two strings sit one directory apart and are not the same
  decision.

## [0.4.0] — 2026-07-25 — bba imperative in entry router

### Added

- **`using-loom-discovery`**: §Intake's family-routing step gains a
  one-line `dev-workflow:brief-before-asking` imperative for non-trivial
  discovery forks (value commitment, on-ramp choice) — carries the
  trigger triple (≥3 trade-offs, ≥2 implementation paths, or
  architectural blast radius) verbatim, mirroring
  `using-loom-pipeline`'s gate (b) pattern.

## [0.3.0] — 2026-07-18 — mandatory bounded validator step

### Added

- **`user-insights`** and **`business-value`**: both SKILL.md files gain a
  mandatory validate step before declaring done — run
  `scripts/validate_discovery_artifacts.py` on the produced artifact dir;
  non-zero result → fix and re-run, bounded at 2 attempts, then surface to
  the user. Mirrors `loom-product-principles`'s Step 8 wiring pattern;
  tolerates greenfield/first-run artifact creation.

Design SSOT: `docs/loom/audits/2026-07-18-agent-loop-convergence-audit.md` §4
rec 5.

## [0.2.0] — 2026-07-18 — evidence source-type column

### Added

- **`user-insights` evidence template**: the evidence table gains a
  `Source type` column (`craft` / `domain-convention` / `project-local`) +
  a compact legend — evidence is typed at intake so downstream stations
  know which authority owns each claim.

## [0.1.2] — 2026-07-14

### Fixed

- **`user-insights` description reverted to the full pre-sweep 899-char
  version** (byte-identical to the 0.1.0 text). The post-merge A/B B-leg
  (plan Task 8) measured combined firing 100%→33%: two records were
  cross-family-attracted by loom-pipeline:loom-memory's pre-existing
  "check prior experience before loom work" clause once the slimmed
  170-char description lost its needs-research lexical thickness. A
  targeted 217-char restore was cache-experimented and ALSO failed
  (1/3 — the ja record newly flipped), demonstrating that mid-band
  lexical tuning near a sibling attractor is unstable — pin-literal
  revert per the plan's A/B bar. Evidence:
  `docs/skill-dogfood/2026-07-14-description-token-economy/ab-results.md`
  §remedy-experiment. Net sweep for this plugin stands at
  using-loom-discovery −566 / business-value −386 chars.

## [0.1.1] — 2026-07-14

### Changed

- Description token-economy sweep (two-tier standard,
  `skill-dev-toolkit/skills/skill-creator-advance/references/description-design.md`
  Principle 5 + cutting rules): frontmatter descriptions rewritten —
  `using-loom-discovery` 1,065→499 rendered chars (router exception band
  ≤500, firing-evidence YAML comment added above `description:` citing the
  2026-07-14 baseline 3/3 EXACT), `user-insights` 899→170, `business-value`
  616→230 (normal band, 250 soft lint). Bodies untouched; multilingual belt
  triggers preserved (需求研究 / 值不值得做 / ユーザーインサイト /
  時間の使い方 / ビジネスバリュー).

## [0.1.0] — 2026-07-10

### Added

- Initial plugin: dual manifest (`.claude-plugin/` + `.codex-plugin/`, Claude
  SSOT synced via `scripts/sync_codex_manifests.py`), `README.md`, this
  changelog; three skills — `using-loom-discovery` (family-entry router),
  `business-value` (adversarial worth-it check, GO / NO-GO /
  NEEDS-MORE-RESEARCH, skippable + re-entrant), `user-insights` (two-mode
  needs research with user-ratified value commitment) — plus
  `scripts/validate_discovery_artifacts.py` (assess-first intermediate state
  honored) and the behavioral-dogfood fix round
  (`docs/skill-dogfood/2026-07-10-loom-discovery/report.md`).
  Test count at close-out: 64 (loom-discovery suite; family suites green).
