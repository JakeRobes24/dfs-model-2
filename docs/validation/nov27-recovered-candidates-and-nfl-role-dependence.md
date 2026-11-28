# Recovered NBA candidate outcomes and NFL role dependence

Continues draft PR #12 from `f8c00de`. This checkpoint scores four archived legal NBA candidates and tests whether position-specific NFL correlations transfer from an earlier season.

## NBA contest 137211

The reproducible read-only audit verifies the four file SHA-256 values and compares the recovered reviewed pool with the original contest. It validates all nine slots, salaries, team counts, saved eligibility and the two-decimal candidate export before accessing NBA results. Reproduce with `python nba_recovered_contest_review.py DFS-2026-11-25-137211-morning-recovery.zip`.

Verified all six final NBA boxes on November 25. All 210 contest IDs were resolved: 130 played and 80 were confirmed did not play. Among 120 played players with both projections, the recovered DAILY and reviewed mean absolute errors were 8.855 and 7.283 FD points, respectively.

| Candidate | DAILY | Recovered reviewed projection | Final NBA box-score FD |
| --- | ---: | ---: | ---: |
| 1 | 223.70 | 324.00 | 352.50 |
| 2 | 221.20 | 321.12 | 350.80 |
| 3 | 227.80 | 320.96 | 347.10 |
| 4 | 222.10 | 320.83 | 371.50 |

The outcome comparison uses the values preserved in the recovery ZIP. All four candidates have nine verified played outcomes. The review does not establish verified pre-tip timing, official FanDuel settlement or which candidates were entered. One slate's comparison does not establish a prospective scoring gain.

### Retrospective legal-roster simulations

Used the existing archived-roster simulator with 8,000 draws and identical shared player draws across overlapping rosters. Trained from 446 eight-game forecast residuals over 21 prior dates, ending November 24, within the previously acquired eight-team NBA box-score cohort. The reviewed values set roster centers. The November 25 actuals were used only after draws to measure the forecast intervals. Both methods covered candidates 1–3 and missed candidate 4 above their upper boundary.

| Historical residual representation | Covered | Mean 80% interval score | Pair-order Brier score |
| --- | ---: | ---: | ---: |
| Point residual | 3 of 4 | 104.17 | 0.24492 |
| Paired minutes and production rate | 3 of 4 | 99.50 | 0.24477 |

The lower paired-model interval score mainly reflects the smaller upper-tail miss on one candidate. The four candidates share just 13 players, and the six pair comparisons overlap. These results support preserving the challenger for additional dates and do not establish full-contest calibration or justify a lineup-selection change.

## NFL position pairing

Joined original weekly player statistics to the previously verified final-game snap/workload dataset. Required exact game, player, club, opponent, position, target, carry and yardage agreement. The 2025 training season retained 5,656 player-games across all 272 regular-season games and 2,516 forecasts after a complete four-game played lookback. The 2026 evaluation sample retained 3,403 player-games from 163 games, with 1,212 eligible forecasts across 99 games. None of the 2026 rows were used to fit the respective position-pair scales or correlations.

Both methods use the same forecast mean, residual scale and players. The challenger freezes 2025 pair-specific residual correlations, shrunk by the number of earlier unique games and capped at ±0.50. Select the highest baseline forecasts per position among the verified played rows. The FD offensive scoring reconstruction includes passing, rushing, receiving, half-PPR, conversion scoring and the yardage bonuses. Defensive, return, fumble and recovery scoring are outside this comparison. [FanDuel scoring](https://www.fanduel.com/rules).

| NFL pair | 2026 pairs | Frozen correlation | Independent CRPS | Role-dependence CRPS | Independent / role interval score |
| --- | ---: | ---: | ---: | ---: | ---: |
| Same-team QB–WR | 151 | +0.249 | 7.814 | 7.786 | 50.82 / 50.27 |
| Same-team QB–TE | 140 | +0.229 | 6.896 | 6.860 | 40.18 / 39.64 |
| Same-team QB–RB | 137 | +0.031 | 8.019 | 8.016 | 50.48 / 50.50 |
| Same-team WR–WR | 169 | +0.087 | 5.794 | 5.791 | 35.53 / 35.47 |
| Same-team RB–WR | 170 | +0.020 | 7.451 | 7.448 | 45.69 / 45.64 |
| Same-team RB–RB | 101 | +0.015 | 6.296 | 6.296 | 38.60 / 38.63 |
| Opposing QB–WR | 149 | +0.008 | 7.141 | 7.140 | 45.56 / 45.54 |
| Opposing QB–QB | 60 | +0.137 | 7.969 | 7.936 | 46.79 / 46.70 |

Equal-week averages across seven 2026 weeks. Lower scores are better. QB–WR 80% coverage increased from 74.1% to 78.1%, and QB–TE from 72.0% to 78.3%. The effect on other pair types was small, and interval scores slightly worsened in the same-team QB–RB and RB–RB comparisons. This supports testing QB/pass-catcher correlations in future complete contests. Overlapping pairs, played-only support and baseline historical means limit inference. Availability, field ownership and full legal NFL lineup calibration remain unverified.

The owner-authenticated hosted save and backup sequence remains open in [issue #9](https://github.com/JakeRobes24/dfs-model-2/issues/9). The recovered contest review is read-only.
