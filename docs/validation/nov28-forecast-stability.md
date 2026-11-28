# Nov28 paired forecast stability and exposure cohorts

Resumed exact checkpoint 833f7a8f712ad734c479acb9755f4bada2cbd48e after conversation limit. Prior NFL 46139505803, NBA 46139505789 and full 46139505831 regression workflows all succeeded. Continue approved multi-slate live-performance audit; MLB deferred.

## NBA
Read exact 196-row private archived strict history replay at 8549d752ae253e972d09f160dfa6d5cee08be9a5, research-evidence/2026-11-28/live-component-transfer/strict_history_shadow_results.csv, blob f7581828072c417d543d7b53baabc3e754731592. Verified unique date/contest player keys, finite paired rows, historical end strictly prior to target date. No new fit: incumbent and previously fixed eight-game combined 20% challenger. Pooled row-weighted values; selected means archive candidate exposure, not necessarily actual entry. Cohorts overlap.

| Cohort | N | Incumbent/challenger MAE | Incumbent/challenger signed bias | Improved/worse | >=15 FD absolute misses before/after |
|---|---:|---:|---:|---:|---:|
| All |196|7.9315/7.8099|-0.6193/-0.3183|113/83|29/28|
| Unselected |157|7.7310/7.6002|-1.4418/-1.0274|94/63|22/21|
| Selected |39|8.7384/8.6540|2.6918/2.5360|19/20|7/7|
| Exposure >=3 |16|9.2000/8.9314|7.6135/7.1010|10/6|3/3|
| Base minutes >=30 |75|8.7335/8.5641|-0.0825/-0.0004|40/35|13/13|
| Base minutes <30 |121|7.4344/7.3424|-0.9521/-0.5154|73/48|16/15|

Mean absolute forecast change .6579 FD overall; directional agreement 115/196. Repeated exposure signed incumbent bias by date Nov24 +10.1380 (6), Nov25 -.0013 (5), Nov27 +12.1988 (5). Selected-player challenger worsened Nov27 MAE 9.5240 -> 9.5885. Small improvement, large misses almost unchanged, no causality or blanket fade. Selection on high forecasts may itself induce positive conditional bias. No new weights or caps.

## NFL
Read private exact 4524dbaaee3a6e24adb300d53c5b989be7388b60 rank archives: nfl_rank_team.csv (1026 records, 342 groups; blob eb829bccd32f92298a8a448d4cc27b3f97b02498) and nfl_rank_game.csv (993 records, 331 groups; blob fbfebda1028497206303852d2f04f4dc64d98f78), under research-evidence/2026-11-28/nfl-opportunity-ranking/. Verified all three policies per key with equal player/pair counts and paired finite metrics where defined. No new fitting. Compare fixed prior blend vs actual scoring average, equal group weighting within each week and equal week weighting across seven weeks. Positive deltas favorable (regret reversed). Leave-one-week-out ranges are sensitivity, not confidence intervals.

| Scope/channel | Order improved/worse/tied weeks | Mean order delta pp | Leave-one-week-out range pp | Mean regret benefit | Regret improved/worse/tied |
|---|---:|---:|---:|---:|---:|
| Game WR receiving |7/0/0|3.8615|3.2596 to 4.4257|.9719|7/0/0|
| Game RB receiving |3/2/2|4.3092|1.9024 to 6.3005|.0514|3/2/2|
| Game TE receiving |3/1/3|2.2619|.6944 to 2.8704|.3371|3/0/4|
| Game RB rushing |2/5/0|-.3632|-3.4330 to 1.0072|-.6325|0/5/2|
| Team WR receiving |6/1/0|4.4312|3.2253 to 5.4621|.3875|4/2/1|
| Team RB receiving |4/1/2|5.7993|3.5913 to 8.4325|.2197|4/1/2|
| Team TE receiving |1/1/5|2.3280|-.6173 to 3.3333|.2116|1/1/5|
| Team RB rushing |3/2/2|.3175|-1.0185 to 2.6852|.0619|4/0/3|

Game WR leader-regret benefit remains positive excluding any one week (.7479 to 1.0594 component points); game RB rushing remains unfavorable (-.7379 to -.4076). Receiving and rushing are scoring channels, not complete player projections; earlier publication/training timing unverified, historical played-only cohort and reused sample. No lineup edge or promotion claim.

## Reproducibility and next priorities
Numerical summaries executed directly on exact archived CSV contents using JS. Added forecast_stability.py with corresponding NBA cohort and NFL weekly summary helpers and two locally executed synthetic pytest cases (passed); full new CI pending. Python helper not yet replayed on full private rows locally. Raw evidence remains in original private archive, no player-level data copied into code repository. Next: freeze prospective paired live forecasts and source-specific numerical opportunities when contest files arrive, especially WR receiving, NBA production per minute and high exposure alternatives. Continue source expansion, complete availability and independent forecast comparison, and archive exact full-pool records; do not fit again to these same small samples. No live scoring or website changes.
