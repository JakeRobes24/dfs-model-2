# November 28 NBA-first defensive production replay

Previous checkpoint 711d4f72b925f4685c036795150ed0c185a640d3 passed NBA 46145890221, NFL 46145890223 and full 46145890210. Maintain immediate NBA development priority, all 48 sources, no MLB or production promotion.

## Fixed defensive component comparison
Recovered library archive DFS_Model_2_NBA_Rotation_Replay.zip, SHA-256 4f5ffe1b168a35f89c182bad3c5b13e66e089006b48a1c03fa76629660ec1509 (computed on recovery; no independent archive signature). Use only 2026-11-18.json: 2,591 recorded official-source box observations, October 26–November 17, 21 dates, 30 teams, 446 player-team histories. Verified no duplicate NBA ID/date. Original README reports 115/127 final boxes acquired; not a complete official schedule. No target-date values in predictions. Last 4 or 8 observed played records, all complete and 10–60 minutes, same player/team, unique dates, within 30 days. Do not skip incomplete observations; observed played windows are not necessarily consecutive team games. Compare recent four-game average FD against identical minutes and non-stock production, changing only the weighted steals/blocks rate (3 FD each). Fixed 100-minute pooled prior: (personal historical stocks FD + 100 * earlier-date pooled stocks FD/min) / (personal minutes + 100). This is a predefined sensitivity for this replay, not fitted from outcomes; cohort is the available earlier complete played rows, not necessarily all league minutes. Strong defenders retain their personal contribution. Longer-rate policies use eight earlier appearances on common support.

Executed local Python on exact archive; duplicate and chronology checks. All errors equal-date weighted, not per-row pooled.

| Four-game support | N | Dates | Baseline FD MAE | Pooled FD MAE | Baseline stocks FD MAE | Pooled stocks FD MAE |
|---|---:|---:|---:|---:|---:|---:|
| All |769|14|8.76418|8.65193|3.39933|3.18842|
| Through Nov10 |416|8|8.60505|8.52216|3.35678|3.08311|
| Nov11 onward |353|6|8.97637|8.82496|3.45606|3.32883|
| Later stocks share >=25% |58|6|8.30782|8.19756|3.89677|3.65905|
| Later projected minutes <25 |138|6|7.43620|7.35215|3.42789|3.16721|

Later six dates: five FD MAE improvements, one worsening; 208/353 individual FD absolute errors improve, 145 worsen. Equal-date mean daily RMSE 11.04658 ->10.87684. Stock-rate MAE .13730 ->.13111. Overall FD gain modest, .11225 equal-date FD points. The later cohort is a chronological sensitivity on the same reconstructed archive, not an untouched prospective holdout. Fixed shrinkage not fit on earlier target errors.

Eight-game support: 117 rows, six dates, overlapping subset of four-game sample. Baseline FD MAE 9.67506; eight-game stocks alone 9.38950; half long rate 9.52791; four-game pooled 9.31652; long pooled 9.24913. Stocks-only MAE 3.79539, 3.89368, 3.83151, 3.66102, 3.76716 respectively. Longer history not uniformly better for the channel itself. Do not select a policy solely on total FD because other component errors can offset it. Both rate and minutes remain conditional on playing; no contest DAILY component reconciliation, live lineup edge, or upside-distribution improvement demonstrated.

## Reusable implementation and next step
Added nba_stock_replay.py and three synthetic regression tests. Local calculations ran separately before repository submission; exact repository helper full CI pending. Reproduce by reading the named JSON member from original ZIP and calling stock_replay(records, date(2026,11,18), window=4 or 8); group absolute errors by target date before averaging. No private player rows copied to code repo. Prospective comparison should preserve explicit baseline defensive components, source dates and matched earlier history, not subtract a historical defensive rate from an opaque total. Keep fixed 100-minute challenger for further evidence; no change to production scores, simulation distributions or optimizer. No new NFL features.