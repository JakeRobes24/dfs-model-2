# November 28 multi-slate NBA roster calibration

Replayed archived FanDuel forecasts on the exact saved lineups across three dated pre-tip forecast checkpoints. A fourth recovery with an unverified original timestamp is a sensitivity. This is a comparison of two fixed research simulators applied to the same forecasts. The prior [November 27 exact simulation recovery](nov28-reconstructed-candidate-ranges.md) separately reproduces the original deployed-in-session decisions and seeds.

## Matched sample

| Contest and archived forecast | Saved | Scored by both | Earlier training rows / dates |
| --- | ---: | ---: | ---: |
| Nov 22, 137037, 3:05 p.m. ET provisional scenario | 4 | 3 | 783 / 12 |
| Nov 24, 137128, 6:14 a.m. ET app run | 4 | 3 | 1,003 / 14 |
| Nov 27, 137257, 6:40 p.m. ET status-adjusted checkpoint | 28 | 24 | 1,164 / 16 |
| Nov 25, 137211, recovered morning export | 4 | 4, sensitivity only | 1,044 / 15 |

The Nov 22 scenario manifest's ten member hashes matched. Its four separate archived roster projections match the frozen scenario pool. Two of the scored rosters independently reproduce the entered FanDuel results of 387.1 and 419.9 using official NBA boxes. Candidate 2 is excluded. The original contest template makes Aaron Gordon eligible at PF, G/F, F/C and UTIL, and the saved candidate assigned him to C. His slot was left as archived. The evidence supports the forecast pool's 3:05 p.m. timestamp. The standalone roster export does not independently attest the later conversation time.

The Nov 24 app packet records capture before the first scheduled contest game and official outcomes. One candidate included a confirmed nonparticipant. Four Nov 27 candidate sets included a player projected for 6.79 minutes, outside the replay's forecast scope. The remaining 30 dated candidates had all nine players with verified outcomes and at least 10 actual minutes. Exact roster slots, cap, contest IDs and team composition passed for the scored sets. The primary Nov 27 comparison uses reconciled outcomes from its full-pool review. A separate box-only replay checks the six known box-versus-display differences.

## Calibration and ordering

Both policies sampled 8,000 draws per slate with shared player outcomes across overlapping lineups and a fixed seed. They used the same centers and strictly earlier official observations, with eight prior player games for each historical residual. One policy resampled the earlier fantasy-point errors directly. The paired policy sampled minutes and points-per-minute errors together. Both condition on playing and use independent draws between players. Compare scores across equal-weight dates because the rosters within each date overlap and Nov 27 has many more candidates than the earlier dates.

| Dated checkpoint | Point residual inside P10–P90 | Paired minute-rate inside P10–P90 | Point residual interval score | Paired minute-rate interval score |
| --- | ---: | ---: | ---: | ---: |
| Nov 22 | 1/3 | 1/3 | 238.50 | 220.44 |
| Nov 24 | 1/3 | 1/3 | 141.84 | 137.99 |
| Nov 27 | 13/24 | 14/24 | 162.45 | 161.07 |
| Equal date average | 40.28% | 41.67% | 180.93 | 173.17 |

The proper interval score penalizes width and misses, with lower scores better. Paired minutes and rate improved that score on each date, but average interval width grew from 86.81 to 91.94 points. Across 281 overlapping non-tied pair comparisons, equal-date order Brier was 0.2484 versus 0.2478. That is nearly unchanged. Both methods missed high on two Nov 22 candidates and low on two Nov 24 candidates. On Nov 27 all misses were below the lower bound. Three of four verified Nov 27 entries missed below P10 under both policies. Both Nov 22 entries exceeded P90 under both. The box-only sensitivity kept coverage identical and interval-score ordering unchanged (183.96 versus 176.22). Including four Nov 25 recovered rosters changed equal-date coverage to 48.96% and 50.00%. The original timestamp remains unverified, and their separate earlier comparison used a narrower training pool.

## Forecast bias and workload attribution

Signed errors are forecast minus actual. The minutes and rate terms use the existing midpoint decomposition and sum to the full lineup error. Every comparison uses the exact same nine players. Candidate overlap averaged 6.00, 6.67 and 5.62 shared players by date.

| Dated checkpoint | Mean minutes effect | Mean production-rate effect | Mean reviewed bias | DAILY roster MAE | Reviewed roster MAE |
| --- | ---: | ---: | ---: | ---: | ---: |
| Nov 22 | -34.06 | -20.87 | -54.93 | 51.60 | 54.93 |
| Nov 24 | +1.81 | +46.20 | +48.01 | 34.80 | 48.01 |
| Nov 27 | +31.82 | +7.25 | +39.07 | 69.55 | 40.03 |

The main driver changes by slate. Nov 24's positive bias was largely from points per minute despite the reviewed player forecasts leading DAILY on the broader played pool. Nov 27's candidate misses were largely from minutes, and its reviewed lineup totals improved substantially on DAILY. Nov 22 moved the other way on both terms. These are stage-specific, conditional roster results. The average fixed-center bias is +10.71 across the dated checkpoints and -0.40 with the recovered morning set, illustrating sensitivity to one slate. An overall correction would mask those differences.

Keep the paired challenger in shadow evaluation. There is no basis here for a global center shift, an unconditional range multiplier, or a scoring change. The next test needs exact comparable pre-tip and close-time forecasts, full availability coverage, and separately scored minutes and conversion at the player and roster levels. Record original candidate sets and unmatched slots before calculating any simulation metrics. Continue the [cross-sport audit](nov28-live-performance-audit.md) while the two NFL contests await original close-time forecasts and verified simulation receipts.
