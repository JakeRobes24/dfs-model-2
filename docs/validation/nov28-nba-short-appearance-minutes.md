# November 28 NBA-first minutes sensitivity including short appearances

Previous checkpoint b5020da7df11e4d4736c7f56e8e6f883d1bc4525 passed NBA 46147713893, NFL 46147713912, full 46147713892. No new NFL development, MLB deferred, all 48 research sources retained.

## Broader numerical support
Recovered exact DFS_Model_2_NBA_Rotation_Replay.zip, member 2026-11-18.json SHA-256 8ec493160d935b4b4faed6efb144077f8c52fb5e2529d0b9023de1846a474e12. 2591 rows, 21 dates Oct26–Nov17, 30 teams. All starter flags missing, so this is not a confirmed starter/bench role comparison. Archive reports 115/127 final games acquired; observed windows not necessarily consecutive team games. Same NBA ID/team, unique dates, four earlier played complete FD observations with minutes strictly positive and <=60, oldest within 30 days, latest within seven days. Unlike prior >=10-minute filter, retain short observed appearances in both prior and target, not DNPs. Rate fixed across all methods at minutes-weighted four-game historical FD/min. No target-day minutes or scoring used for forecast. Eight-game comparison keeps the four-game rate fixed and adds eight prior valid minute observations on same support. Equal-date error means. Actual local Python replay; results saved in working evidence. Reused archive, no new prospective sample.

| Cohort | N/dates | Mean4 min / FD MAE | Median4 min / FD | Half median min / FD | Weighted4 min / FD | Mean2 min / FD |
|---|---:|---:|---:|---:|---:|---:|
| All |1011/14|4.73912/8.44982|4.71972/8.42022|4.70622/8.42736|4.71629/8.41366|4.97591/8.49799|
| Through Nov10 |526/8|4.36224/8.18601|4.40449/8.11260|4.35450/8.14126|4.31335/8.18255|4.55428/8.28750|
| Nov11 onward |485/6|5.24164/8.80156|5.14003/8.83037|5.17519/8.80884|5.25355/8.72180|5.53807/8.77864|
| Prior short appearance, all |221/14|5.81201/6.71232|5.95131/6.77088|5.85952/6.72921|5.59554/6.43886|5.95617/6.63760|
| Prior short appearance, later |124/6|6.46478/7.82206|6.47159/7.71978|6.44434/7.75867|6.15467/7.61485|6.20310/7.66061|
| Later no prior short |361/6|4.83788/9.14474|4.75283/9.23111|4.78359/9.18305|4.92077/9.10079|5.22370/9.15132|
| Explicit prior observed absence |54/9|4.90616/5.89212|5.08848/6.12393|4.97457/5.99590|4.81153/5.70525|5.59608/6.21068|

Weighted4 uses chronological 1/2/3/4 weights, fixed sensitivity not optimized. All target played <10 min:104; later:63; later short-prior:50; explicit prior absence:20. Weighted4 improves minutes MAE 8/14 dates (4/6 later), FD MAE 8/14 (4/6 later), short-prior later FD 5/6. Prior short cohort later minutes bias -1.87542 mean vs -2.00162 weighted, so lower MAE does not eliminate systematic underprojection. Explicit prior observed absence requires latest observed team game strictly after prior last personal appearance and unanimous explicit absent/not played from available teammate lists, using prior personal name; this is not proof of medical injury or consecutive schedule coverage. Small 54-row cohort; not a verified returning injury sample. No blanket decrease in projected minutes on return.

On 149 eight-game matched observations across six dates, mean4 minutes/FD MAE 4.83820/9.49859, mean8 4.63411/9.16944, median8 4.67381/9.37538, half mean4/8 4.70944/9.30281. Same four-game production rate, no target information. This is additional common-support evidence for longer windows, not validation over existing reviewed model. No simple weighting wins consistently; retain current live scoring, preserve short minutes as descriptive risk rather than dropping them or imputing zero. New offline helper nba_minutes_window_replay.py and three synthetic tests saved. Exact repository CI pending. No additional website feature or live weighting change.