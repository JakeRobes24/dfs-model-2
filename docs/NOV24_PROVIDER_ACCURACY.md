# November 24 provider accuracy — archived morning capture

Read-only calculation on 2026-11-25 using the genuine processed archive for contest 137128. Source packet: [immutable research and actuals packet](https://github.com/JakeRobes24/dfs-model-2-history/blob/7cf0fad511caf68f6ac65dd25b2c7bdf536e189d/incoming-app/2026-11-24/137128/3a6167f57f3de9a02ddf9aa64620ec69236b045546a0e3ef0566259b502ad984.json); [processed receipt](https://github.com/JakeRobes24/dfs-model-2-history/blob/7cf0fad511caf68f6ac65dd25b2c7bdf536e189d/processed/app/2026-11-24/137128/3a6167f57f3de9a02ddf9aa64620ec69236b045546a0e3ef0566259b502ad984).

105 research rows and 105 recorded outcome rows; 85 eligible, 70 played, 15 verified DNP, no unresolved eligible outcomes. All frozen rows mark before_scheduled_tip, captured 2026-11-24T11:14:51.162030Z. This is the morning capture, not final pre-lock evidence. Actuals are the archived NBA box-score calculation or NBA confirmed DNP rows; boxes were not freshly fetched for this calculation. Independent read-only calculation follows nba_source_accuracy.py filters: exact source/family, six-hour freshness, official status cutoff, latest nonconflicting value, played-only minutes, verified DNP zero for points, paired comparison on common observations. 234 provider/metric/player observations. Historical database and original packet were not modified.

| Metric | Provider | Observations | Source MAE | Bias | DAILY paired MAE | Reviewed paired MAE |
|---|---|---:|---:|---:|---:|---:|
| FD points | Daily Fantasy Fuel | 24 | 9.15 | +0.07 | 12.93 | 10.98 |
| FD points | PropSims | 59 | 7.77 | +0.86 | 9.93 | 8.83 |
| Minutes | NBA House | 65 | 4.01 | -0.91 | 7.27 | 4.22 |
| Minutes | PropSims | 56 | 3.55 | +0.61 | 7.57 | 4.06 |
| Minutes | RotoWire | 30 | 3.38 | -0.58 | 7.29 | 4.09 |

All observations had both baseline forecasts. Positive bias means overprojection. Source errors on different coverage cannot rank providers.

| Metric | Source A | Source B | Common players | MAE A | MAE B |
|---|---|---|---:|---:|---:|
| FD points | Daily Fantasy Fuel | PropSims | 24 | 9.15 | 9.29 |
| Minutes | NBA House | PropSims | 55 | 3.92 | 3.55 |
| Minutes | NBA House | RotoWire | 28 | 3.63 | 3.57 |
| Minutes | PropSims | RotoWire | 28 | 3.24 | 3.51 |

The broad-sample apparent ranking reverses on several common samples. No RotoGrinders or verified LineupExperts forecast qualified in this capture; do not infer performance. No frozen PropSims uncertainty fields exist in this older packet. One date, exploratory only; no scoring-policy or provider-weight change. Do not call this a final-lock or independent fresh-box audit. Continue using prior archive loader and official outcomes for prospective repeatable source evaluation. Prior fixture-independent gate at 6502be15668b24da841152610bf617100fdba529: 320 passed, one private history fixture deselected, three workflows successful.
