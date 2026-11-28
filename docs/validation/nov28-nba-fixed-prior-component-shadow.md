# November 28 NBA-first fixed prior component forecast

Previous checkpoint 33e0a992a4ba7adc19d802c239421491a851f96e passed NBA 46147097509, NFL 46147097495, full 46147097473. 

## Fixed-prior sensitivity on later observations

Recovered exact library archive DFS_Model_2_NBA_Rotation_Replay.zip, SHA-256 4f5ffe1b168a35f89c182bad3c5b13e66e089006b48a1c03fa76629660ec1509, original 2026-11-18.json member SHA-256 8ec493160d935b4b4faed6efb144077f8c52fb5e2529d0b9023de1846a474e12. Use the existing complete same-team four-game support and keep personal rebound production unchanged. Freeze pooled totals before Nov11 using 1617 complete records across 15 dates and 30 clubs (40216.5333333319 minutes, 18869 shot/FT/turnover opportunities, 16582 net scoring, 8760 weighted rebound FD, 6703.5 weighted assist FD, 6393 weighted stocks FD). The four-game personal history still updates before each target game; no target date enters forecasts. Fixed 40-opportunity efficiency and 100-minute assist/stock priors from previous experiment. No refitting. This is a reused archive and an outcome-informed research direction, not a pristine holdout.

| Nov11–17 evaluation | N | Dates | Personal FD MAE | Fixed-prior FD MAE | Improved dates |
|---|---:|---:|---:|---:|---:|
| All |353|6|8.976368|8.546683|6|
| Under 25 historical projected minutes |138|6|7.436200|7.094430|4|
| At least 25 minutes |215|6|9.703116|9.285267|6|

195 of 353 individual absolute errors improved. Equal-date channel MAE: net 5.353273 -> 5.192055, rebounds unchanged 2.674041, assists 2.538128 -> 2.389357, stocks 3.456065 -> 3.327510. Actual local Python calculations, no new target dates. Source acquisition incomplete (not a consecutive team-game schedule guarantee), conditional played sample. Fixed cohort prior does not need to be refreshed on every slate. This result compares history-only forecasts at historical mean minutes, not the current live incumbent or the new reviewed-minutes variant.

## Prospective draft path

The frozen prospective cohort uses all complete available original rows strictly before Nov18 (2132, 21 dates, 30 clubs; minutes 53297.6666666642, opportunities 24980.4, net 22214, weighted rebounds 11516.4, weighted assists 8913, weighted stocks 8586). No claim of current league representativeness. nba_pooled_history_shadow.py attaches exact last four observed same-team historical records, requires one stable official-source NBA ID and unambiguous player alias, rejects duplicates/incomplete/short/missing/uncertain-availability histories and dates outside previous 30 days. The old archive supplies only pooled priors; actual upcoming personal inputs come from the normal current rotation acquisition. Both personal and pooled history-based component alternatives are scaled to the SAME current reviewed minutes. Preserve rebound component; pool net conversion, assists and stocks. Neither is added to reviewed FD or replaces it; do not double-count baseline adjustments. Store exact personal and pooled component values separately alongside original DAILY and reviewed scores, in the verified pretip archive. No new network fetch. No new score weights or optimizer changes. Exact receipt recomputation, timestamps and hashes, paired played-only grading; multi-slate gate five dates/100 pairs before independent validation. Original 20% component-rate policy remains separate. No today contest inputs, actual prospective support or hosted roundtrip established. Three new synthetic tests saved. Latest CI pending. All 48 sources preserved, NFL work retained and discretionary NFL development paused. MLB deferred.
