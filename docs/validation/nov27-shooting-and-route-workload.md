# November 27 shooting and route workload replay

Continues draft PR #12 from `b3e946c` with identical holdouts across competing forecasts in both sports. The new modules are historical research. They do not provide live projections or certify contest candidates.

## NBA shot mix and production per minute

Re-read 122 traditional NBA boxes for the previously selected eight-team schedule. All games passed the scheduled game ID and oriented club checks. The eight-team set supplied 1,286 player-games with at least 10 minutes and valid counting statistics. Reconciled official field goals, threes, free throws and final points. Two-pointers come from the difference between field goals and three-pointers. Take only players with eight consecutive earlier team appearances and a verified final outcome. That leaves 355 held-out player-games over 22 dates and 68 games.

Each shot-mix experiment separates per-minute volume and conversion for two-pointers, three-pointers and free throws. It uses the same four-game minutes and non-scoring FanDuel components. The pooled method adds 20 attempts per shot type at the eight-team conversion rate observed through the preceding date. Longer full-production controls vary overall FanDuel production and minutes on the same support.

| Forecast | FD points MAE | Basketball points MAE | FD per minute MAE | Minutes MAE |
| --- | ---: | ---: | ---: | ---: |
| Four-game baseline | 8.065 | 4.942 | 0.2544 | 4.152 |
| Four-game with pooled conversion | 7.964 | 4.851 | 0.2500 | 4.152 |
| Eight-game volume only | 7.897 | 4.830 | 0.2516 | 4.152 |
| Eight-game conversion only | 8.008 | 4.919 | 0.2548 | 4.152 |
| Eight-game shot rates | 7.831 | 4.743 | 0.2500 | 4.152 |
| Eight-game volume and pooled conversion | 7.819 | 4.707 | 0.2467 | 4.152 |
| Eight-game full rate and four-game minutes | 7.779 | 4.743 | 0.2450 | 4.152 |
| Eight-game minutes and full rate | 7.581 | 4.658 | 0.2450 | 4.073 |

Errors are averaged first by date. The per-shot conversion model improved on the short baseline in both date periods. The best shot-only method led the full-rate control slightly through November 17, then fell behind from November 18 through 25 (7.598 versus 6.929 FD MAE with eight-game minutes). The longer full-production baseline remains the stronger challenger overall. This sample excludes absences, fewer than ten minutes and incomplete windows. It offers no evidence that shot mix should override a verified role change or lineup confirmation. [NBA stats glossary](https://www.nba.com/stats/help/glossary) · [Previous tracked-opportunity checkpoint](nov27-tracked-opportunity-and-archive-recovery.md).

## NFL routes and expected receiving production

Verified both public RotoWire table schemas from Weeks 1–11. Recap rows carry oriented matchup, final score, team dropbacks, a named RB/WR/TE, route count and publication metadata. Require agreement with the regular-season schedule, a unique named position and GSIS identity in the existing snap/workload join, actual targets and receiving yards, and route counts bounded by offensive snaps. Duplicate display copies must agree. Blank targets and yards are accepted only when the independent actual is zero. This verifies the route record's identity and context. The route counts themselves come from RotoWire.

Of 3,231 numerically usable recap rows, 2,767 matched across 163 final games. The other 464 had an unmatched identity or inconsistent counts. Require four consecutive prior team appearances with source updates strictly before target kickoff, at least 20 earlier routes and four targets, and the same verified ffopportunity receiving components. The comparison retained 751 player-games over Weeks 5–11 (359 WR, 216 TE, 176 RB).

The routes challenger multiplies a four-game team dropback mean by two-game route share and pooled four-game targets per route. The score uses prior expected FanDuel points per target. An equal blend combines its target estimate with the direct four-game average. Receiving FD here includes yardage, catches, touchdowns and two-point conversions, without bonuses or fumbles. Each policy uses the same outcomes. Actual source publication lag and the original training dates for ffopportunity remain unverified.

| Forecast | Targets MAE | Receiving FD MAE |
| --- | ---: | ---: |
| Four-game actual | 2.0779 | 4.5183 |
| Four-game expected | 2.0779 | 4.2356 |
| Recent route share and expected | 2.0990 | 4.2587 |
| Equal route blend and expected | 2.0753 | 4.2410 |

Errors are averaged first by week. Expected scoring improved on recent actual scoring by about 6.3%. Adding recent routes did not improve the expected-scoring baseline overall. The equal blend cut WR target error from 2.358 to 2.345 with essentially the same WR fantasy error, while it worsened RB and TE fantasy error. Keep route coverage for role diagnosis and compare actual availability and frozen projections on future slates. Keep the direct target average as the research benchmark. [RotoWire Week 1 recap](https://www.rotowire.com/football/article/nfl-box-score-breakdown-week-1-recap-usage-stats-134247) · [RotoWire Week 11 recap](https://www.rotowire.com/football/article/nfl-box-score-breakdown-week-11-recap-usage-stats-147809) · [ffopportunity](https://ffopportunity.ffverse.com/).

The evidence archive includes input digests, joined rows, the replay recipe and paired forecast errors. The owner-authenticated hosted save and backup verification remains open in [issue #9](https://github.com/JakeRobes24/dfs-model-2/issues/9).
