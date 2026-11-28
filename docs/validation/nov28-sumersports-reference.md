# SumerSports public research assessment — 2026-11-28

Registry addition 38; NFL advisory historical and matchup context only. Inspected public numeric season-to-date tables: [QB](https://sumersports.com/players/quarterback/), [RB](https://sumersports.com/players/running-back/), [WR](https://sumersports.com/players/wide-receiver/), [TE](https://sumersports.com/players/tight-end/), [offense](https://sumersports.com/teams/offensive/), [defense](https://sumersports.com/teams/defensive/). QB board displayed Nov 27 18:33 ET; RB Nov 27 12:21 ET; team boards Nov 27 18:29 EST. Dates differ; never assume synchronized cutoffs. WR/TE route counts, target share conditional on active games, targets per route and yards per route; RB carries, EPA/rush, success rate, yards after contact; QB scramble rate, EPA/play, time to throw; team pass/rush EPA. The public [Gibbs profile](https://sumersports.com/players/cea1ef5/jahmyr-gibbs/) shows season-level rows for 2023–2026, not a verified dated game-level archive. Example public WR board reports DeVonta Smith 193 routes, 38.07% target share, 0.35 targets/route and 2.85 yards/route; this capture is AFTER Thanksgiving and cannot establish pre-lock knowledge. No historical forecast accuracy claimed. Verify provider identifiers, team aliases, game windows, denominator definitions, raw counts and cutoff versus official statistics and existing RotoWire/nflverse/ffopportunity records. Do not use rounded rates to manufacture exact target counts. Premium [SumerPass](https://sumersports.com/features/stats/) includes situational filtering and play-level data; no subscription needed for public reference; no authorized bulk feed or dated weekly exports established. [Fantasy edition announcement](https://sumersports.com/the-zone/sumerbrain-open-beta-fantasy-edition/) describes third-party consensus, not independent platform-specific forecasts. No consensus vote, weight change, automated integration or forecast validation. Next: following the November 27 post-slate review, keep multi-slate live performance audit first; evaluate incremental opportunity/efficiency features only with strictly earlier dated game-level observations and chronological matched holdouts. No retrospective use of current cumulative season rows for prior games.


## Deeper access investigation and bounded numerical diagnostic (Nov 28)

Public historical player profiles: https://sumersports.com/players/c32ba12/george-kittle/ explicitly labels 2022–2026 rows. Current profile shows 256 routes vs 255 on https://sumersports.com/players/tight-end/ with the same 591 yards; do not assume synchronized captures. Historical board URL probes https://sumersports.com/players/wide-receiver/?plays=50&season=2025 and https://sumersports.com/players/wide-receiver/?plays=250&season=2024 returned the same October 17 2026 04:42 ET table, despite requested season and threshold differences. Week=11 probe unavailable. Team filter also returned multiple teams. Neither historical filters nor public weekly game-level data verified. Stop repeated probes; no paid access or API authorization.

https://sumersports.com/football-analytics-definitions/ documents route participation excluding pass blocking and target share denominator restricted to active games. https://sumersports.com/the-zone/inside-the-data-how-smerbrain-sees-the-game/ describes in-house tracking classification, licensed inputs and historical backfills; distinct charting is not evidence of independent fantasy projections. https://sumersports.com/features/stats/ advertises premium situational filters and updates within two hours of last game; advertised timing not independently validated. https://sumersports.com/the-zone/sumersports-big-data-bowl-2026/ and https://github.com/SumerSports/SportsTrackingTransformer/releases describe supplemental coverage/alignment and a historical competition tracking release; no downloaded or joined rows, not a complete current season archive. Do not count raw tracking competition data as independent current fantasy forecasts.

Exploratory snapshot-difference diagnostic, fixed cohort top ten receiving-yard rows in October 17 table above, matched name/team against https://sumersports.com/players/wide-receiver/ November 27 18:33 ET displayed snapshot. Other captures of the same page display different update times; archive source values and retain ambiguity. Exact transcribed inputs (routes, receiving yards), early then late:
```csv
player,early_routes,early_yards,late_routes,late_yards
Smith-Njigba,202,717,317,1207
Olave,205,537,404,866
Lamb,169,507,425,1242
London,132,488,296,801
Watson,166,474,345,981
Adams,203,441,232,480
Higgins,170,423,363,867
Flowers,91,405,296,785
Golden,169,397,380,892
McMillan,164,385,371,731
```
All ten have positive route increments. Compute early rate = early yards / early routes; implied incremental rate = delta yards / delta routes. Early pooled benchmark 2.8569718731 (sum yards / sum routes). Equal player weights; compare own early rate, pooled early rate, fixed 50/50 blend. MAE/RMSE/signed bias (predicted minus implied incremental):
- own 0.790937 / 1.121444 / +0.648664
- pooled 0.836312 / 0.979260 / +0.552708
- blend 0.812212 / 0.992575 / +0.600686

This is a descriptive conditional calculation, NOT a historical replay or model validation: early season identity unverified by broken filter, snapshot revisions and date conflicts possible, leaders selected by earlier yards, only ten players, no independent outcomes or DAILY/model pairing, no predicted workload. Do not promote any method or weight. Useful hypotheses: compare prior route/target rates versus shrunk rates, and forecast receiving conversion conditional on opportunity, only with dated game-level matched data and held-out outcomes. Current role, active games and schedule must be reconciled separately. SumerSports remains advisory public historical/matchup reference; initial and bounded deeper research complete, full predictive validation blocked by game-level/cutoff evidence. Next task: Nov 27 post-slate, then multi-slate live performance audit. No additional subscription or feature work necessary before those tasks.
