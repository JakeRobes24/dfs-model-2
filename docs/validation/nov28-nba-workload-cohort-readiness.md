# November 28 NBA workload-cohort validation and readiness

Start from 2d345d46bf402a25ed58d48a1bee1e4e699e0a6b, whose NBA, NFL and full regression workflows completed successfully (46152282439, 46152282414, 46152282398). Preserve NBA-first priority, NFL progress, MLB deferral and established live scoring. The current registry includes 50 sources; the earlier rolling roadmap's 48 count predates TipoffLab and Statz.

## Retrospective comparison

Read exact private history commit 8549d752ae253e972d09f160dfa6d5cee08be9a5, research-evidence/2026-11-28/live-component-transfer/strict_history_shadow_results.csv, blob f7581828072c417d543d7b53baabc3e754731592. All 196 date/contest player keys unique, no missing comparator points. This is the same strictly matched retrospective sample, not a new independent date or prospectively frozen capture. Nov25 original capture timing remains unverified. Split by incumbent projected minutes, never actual minutes; the parent replay still conditions on verified actual playing time and complete history. Compute MAE within date, then equal weight per available date. JavaScript calculations executed directly on archive.

| Cohort | N (Nov24/25/27) | DAILY | Reviewed | 4-game rate | 8-game rate | 8-game minutes | Both |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 to <20 |49 (8/29/12)|6.8684|6.7400|6.6555|6.6927|6.5554|6.5003|
| 20 to <30 |72 (10/20/42)|9.0304|8.2012|8.0711|8.1019|8.2227|8.1163|
| 30 to 48 |75 (19/21/35)|13.0786|8.6385|8.5537|8.4793|8.6028|8.4376|

Both improves each date in 10–<20 and 30–48; 20–<30 Nov25 worsens from 7.9759 to 8.1613. Same rows, fixed 20% weights. In 31 rows with eight-game historical minutes differing by at least 5, equal-date reviewed/both MAE 8.6324/8.1906, but date counts 3/26/2 make this fragile. In 93 rows with historical rate above reviewed, 8.7135/8.5461; in 103 at or below, 7.4463/7.2581. These are descriptive slices, not a basis for new thresholds or selecting an optimal method. Do not infer a salary result from projected minutes. No new fit or live scoring promotion.

## Code upgrade

History-window freeze and evaluation now require both consistent, valid original input fingerprints, in addition to existing cutoff and exact-output checks. Validate the entire receipt before partitioning. Compare frozen coverage by incumbent projected minutes (10–<20, 20–<30, 30–48, outside window/missing), separating all eligible pre-tip rows, reproducible frozen forecasts and verified played matched rows. Missing inputs and outcomes are not zeros. Multi-slate experimental evaluation in the development UI displays/downloads per-date workload cohorts from existing archived replay data, with no new acquisition or automatic selection. Two synthetic regression cases added for mixed fingerprints, missing outcomes and support accounting. Source code, tests and UI committed as 6830d387, 1e4b1fd9, c7f8924e; all three workflow gates for latest code were running at documentation time. Hosted behavior not verified. No new scoring weights, optimizer changes, or production merge.

## Readiness

Freeze established live scoring; use experimental capture and comparisons as research, not automatic overrides. Today's actual contest and DAILY still required for full-pool match, current official statuses, independently supported minutes/production, legal alternatives, exposure challenge, and final close-time receipts. Do not delay these for speculative feature development. Continue NBA and NFL multi-slate audit after post-slate outcomes; preserve unresolved source timing, missing depth-player rate coverage, simulation calibration and archive verification issues.
