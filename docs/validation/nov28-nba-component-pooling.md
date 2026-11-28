# November 28 NBA-first scoring component pooling replay

Predecessor 1eda304b4a5e3a4c2ed09c9fe48307a3b3bcad12 passed NBA 46146212922, NFL 46146212906, full 46146212937. Continue NBA upgrades, retain 48 sources and original scoring. No NFL expansion or MLB.

## Numerical comparison

Recovered exact library archive DFS_Model_2_NBA_Rotation_Replay.zip, SHA-256 4f5ffe1b168a35f89c182bad3c5b13e66e089006b48a1c03fa76629660ec1509; 2026-11-18.json, 2591 recorded official-source observations. Same four earlier observed same-team played records, full FD and opportunity fields, 10–60 minutes, unique dates, within 30 days; 769 target player-games on 14 dates. Incomplete windows rejected. Incomplete original game acquisition means this is not a consecutive-team-game guarantee. Pooled totals include only earlier dates, never target-date counts. Preserve original four-game average minutes and personal FGA+.44*FTA+TO opportunity frequency. Compare net scoring efficiency (PTS-TO divided by opportunity proxy) with fixed 40-opportunity pooled prior; weighted REB, AST and stocks rates with fixed 100-minute pooled prior. Compare one changed channel at a time and all four together. These are exploratory fixed strengths, not tuned or independently validated. FD components include 1.2 per rebound, 1.5 per assist, 3 per steal/block, negative turnovers. All errors equal-date weighted.

| Cohort | N/dates | Baseline | Net only | Rebounds only | Assists only | Stocks only | All |
|---|---:|---:|---:|---:|---:|---:|---:|
| All |769/14|8.76418|8.63162|8.76320|8.67065|8.65193|8.38984|
| Through Nov10 |416/8|8.60505|8.44389|8.69586|8.56126|8.52216|8.34610|
| Nov11 onward |353/6|8.97637|8.88192|8.85299|8.81651|8.82496|8.44815|
| Later projected minutes <25 |138/6|7.43620|7.38678|7.06470|7.22427|7.35215|6.70145|

All-channel comparison improved 11/14 dates, including all six later dates. Channel-specific weighted FD component MAE baseline -> pooled:

| Channel | Entire sample | Later sample |
|---|---:|---:|
| Net scoring |5.43622 ->5.25049|5.35327 ->5.19148|
| Rebounds |2.47373 ->2.58565|2.67404 ->2.82290|
| Assists |2.42565 ->2.34725|2.53813 ->2.38983|
| Steals/blocks |3.39933 ->3.18842|3.45606 ->3.32883|

Rebound pooling worsens rebound prediction even when total FD improves in later sample; do not adopt generic rebound shrinkage on this evidence. Earlier tracked rebound-chance conversion results are a separate supported research candidate. Net scoring/assist/stocks retain further testing priority. Combined later FD gain .52822, low-minute later gain .73475. Not a comparison to current reviewed or DAILY forecasts, not calibrated to today's players, not an independent future holdout. No lineup simulation, promotion or fit. Existing archive second 2026-11-20.json contained zero rows dated Nov18 or later, so attempted extension did not supply independent later outcomes. Do not claim extra dates.

Local Python calculation actually executed on named archive; output component_pool_replay.csv retained in working evidence. New reusable nba_component_pool_replay.py and three synthetic tests saved; exact repository CI pending. Run component_pool_replay(records,date(2026,11,18)) and group absolute errors by date to reproduce. Keep candidate experimental until explicit baseline component forecasts and pregame frozen evidence permit same-support validation. No new website feature or production scoring change.
