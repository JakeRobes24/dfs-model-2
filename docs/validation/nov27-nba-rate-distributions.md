# November 27 NBA rate distribution and interval calibration

Executed the new Python module locally against 4,841 archived official played observations. Archive SHA-256 independently verified: 2063db41a4a8332b0fb98bd2460449744ae07203e4f9cd2caac3e5d41cea74f9. Same observed-game completeness and nonzero opportunity gates as the existing component benchmark, cutoff 2026-11-26. Equal-date averages. Paired empirical game draws vs Cartesian product of minutes and FPPM vs the independent draws recentered on the paired mean. Centering controls for differences in mean predictions; this is univariate, not a teammate or lineup dependence test.

| Prior games | Policy | Holdouts | Dates | CRPS | Coverage | Width | Interval score |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 8 | paired | 1164 | 16 | 6.51962 | .59767 | 19.25037 | 44.56520 |
| 8 | independent | 1164 | 16 | 6.41469 | .66525 | 22.03648 | 42.86014 |
| 8 | independent centered | 1164 | 16 | 6.37448 | .66195 | 22.03648 | 42.54197 |
| 12 | paired | 322 | 8 | 6.23472 | .68924 | 21.09347 | 41.35642 |
| 12 | independent | 322 | 8 | 6.14378 | .70731 | 22.83895 | 41.30301 |
| 12 | independent centered | 322 | 8 | 6.14764 | .71757 | 22.83895 | 41.40125 |

Calibration uses only strictly earlier dates after 100 prior holdouts, nominal 80% interval. Equal-date means, identical holdouts across methods within each cohort.

| Prior games | Policy | Holdouts | Dates | Raw coverage | Calibrated coverage | Raw interval score | Calibrated score |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 8 | paired | 1052 | 12 | .64994 | .82456 | 41.00494 | 38.76935 |
| 8 | independent | 1052 | 12 | .70602 | .82470 | 39.49108 | 38.67690 |
| 8 | independent centered | 1052 | 12 | .70163 | .82291 | 39.33851 | 38.51943 |
| 12 | paired | 203 | 3 | .69964 | .81671 | 37.50566 | 36.56790 |
| 12 | independent | 203 | 3 | .75558 | .82983 | 36.60903 | 36.54999 |
| 12 | independent centered | 203 | 3 | .75950 | .83376 | 36.60659 | 36.54310 |

Eight-game centered challenger improves CRPS and interval score without changing mean forecasts. All calibration methods improve interval score on the matched historical samples; 12-game sample only has 3 evaluation dates, not independent of eight-game cohort. Preserve as research only. No evidence for DNP, role changes, contest ceiling or lineup correlations. No live scoring change.

## Acquisition verification
Documented NBA Stats tracking endpoint https://stats.nba.com/stats/leaguedashptstats (passing, rebounding, possessions and other tracking categories; https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/leaguedashptstats.md); BALLDONTLIE alternative per-game tracking documented at https://nba.balldontlie.io/; authorization and identity crosswalk still needed. NFL expected opportunity reference confirmed at https://nflreadr.nflverse.com/reference/load_ff_opportunity.html and https://ffopportunity.ffverse.com/. These are realized-play-conditioned model outputs, not independently timestamped pregame forecasts. Local container DNS could not access the NBA Stats and GitHub external download hosts. No actual tracking or expected-points data rows collected in this batch. Next: acquire authorized dated rows, verify exact game/player joins, and evaluate conversion separately from opportunity. No MLB or Friday contest inputs.
