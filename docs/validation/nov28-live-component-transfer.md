# November 28 live-forecast component transfer
Verified predecessor d2bfcc4: NFL 46135390955, NBA 46135390989, full 46135390948 all passed. Private archive checkpoint fa2512e9c1e0d7e00bebd85e39d0e97e2aed79c1, research-evidence/2026-11-28/live-component-transfer. Saved 223 paired NBA player rows, replay recipe, and NFL component summary with readback. No code or production scoring changes.

## NBA: longer-history sensitivities against archived live forecasts

Recovered the original live audit normalized CSV (all member digests verified), the official observations ZIP (SHA-256 2063db41a4a8332b0fb98bd2460449744ae07203e4f9cd2caac3e5d41cea74f9) and Nov24 original contest CSV (SHA-256 d401c215c4db90be9ecefc949afb6f83ef25bce41f1bdf1f1b81873e1a25d9dc). Nov24 teams restored by exact contest player ID. Match historical names (Unicode normalization and punctuation removal) and team with a unique earlier NBA ID and no duplicate dates. Last eight recorded same-team appearances of at least ten minutes, strictly before target date; pooled FD/minute, last four as short comparator. Score identical eligible played rows with finite DAILY, reviewed and actual points/minutes, at least ten reviewed/actual minutes. Apply fixed 20% historical weight separately to rate and minutes and together. Earlier historical short appearances are filtered before selecting the window; the sensitivity is not a byte-exact execution of the stricter frozen nba_window_shadow.py policy, and no new prospectively frozen predictions are claimed. Nov25 recovered morning timestamp remains unverified. No outcomes used to construct forecasts; actual participation and completeness gate retrospective comparison only.

| Method | Nov24 morning (41) | Nov25 morning (82) | Nov27 18:40 (100) | Equal-date MAE |
|---|---:|---:|---:|---:|
| DAILY | 10.4610 | 9.5780 | 9.3470 | 9.7953 |
| Reviewed | 8.5277 | 7.0407 | 8.0756 | 7.8813 |
| Four-game rate | 8.3229 | 6.9382 | 8.1220 | 7.7943 |
| Eight-game rate | 8.2225 | 7.0106 | 8.0824 | 7.7718 |
| Eight-game minutes | 8.3464 | 7.0419 | 8.0014 | 7.7966 |
| Eight-game both | 8.0458 | 7.0003 | 8.0072 | 7.6844 |

Combined challenger lowered equal-date MAE about 2.5%, but is not best on each date. Matched exposure-positive players: Nov24 n14, incumbent/combined 10.5975/10.3583; Nov25 n11 5.3661/5.3795; Nov27 n16 9.5240/9.5885. Selection stages differ; no lineup reoptimization. Minutes MAE incumbent/eight-game blend 3.6342/3.3962, 5.1801/4.6486, 4.4496/4.3911. This is encouraging but small retrospective improvement, not a held-out live decision or full-pool gain. Earlier history archive may be incomplete for individual team games; selected last eight qualifying appearances, not guaranteed consecutive appearances. Retain established prospective policy and require untouched paired future packets; no weight promotion.

## NFL: directly paired DAILY versus independent component forecasts

Thanksgiving 137123. Verified original DAILY bytes SHA-256 f2f84bd3ffcf86f4ea5a6f9aa443cb2a00f9edbddf04815592a658462c661f6c; match exact archived DAILY player name, team, oriented game and fantasy total with the official reconstruction. Exact contest ID and timed prelock 4for4 capture, publication <= observation <= cutoff. All 14 source players matched, 74 component pairs; only played, explicit gamebook component tuples, no unknown imputation.

| Component | N | DAILY MAE | 4for4 MAE |
|---|---:|---:|---:|
| Pass attempts | 5 | 5.212 | 6.220 |
| Passing yards | 5 | 72.318 | 69.120 |
| Passing TD | 5 | .712 | .920 |
| Interceptions | 5 | .656 | .720 |
| Rush attempts | 9 | 4.371 | 4.022 |
| Rush yards | 9 | 23.806 | 22.500 |
| Rush TD | 9 | .672 | .656 |
| Receptions | 9 | 1.256 | .800 |
| Receiving yards | 9 | 20.452 | 17.456 |
| Receiving TD | 9 | .400 | .478 |

Yardage-only FD decomposition (positive projected and actual volume for both providers) using same symmetric formula. Passing n5 DAILY volume/rate 1.554/2.411, 4for4 1.817/1.912; rushing n9 DAILY 1.898/2.010, 4for4 1.815/2.345; receiving n9 DAILY 1.086/1.175, 4for4 .705/1.196. Absolute effects may offset, not additive MAE. Receiving volume = catches, not targets: 4for4 reference lacks targets. Small public source cohort, one slate, no general provider ranking. The earlier NFL final adjusted projection gap remains.

## Decision
No global weight change. Next prospective slates should save raw DAILY, independent component forecasts (including targets/routes when supported), incumbent and frozen shadow outputs, timestamped status/role, simulation intervals and actuals. Continue existing rolling roadmap, preserve NBA/NFL work and defer MLB. Private evidence and prior regression results verified; this commit adds documentation only.
