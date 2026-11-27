# NBA historical production-rate challenger replay

Recovered the authorized private workflow artifact 15111472254 from dfs-model-2-history, verified SHA-256 2063db41a4a8332b0fb98bd2460449744ae07203e4f9cd2caac3e5d41cea74f9, and read 4,841 official played observations. An independent Python implementation of the current history-window equations reproduced the existing baseline MAEs and exact cohort sizes; no target stats used to form predictions. Cutoff 2026-11-26. Equal-date averages; eight-game and twelve-game cohorts overlap and must not be treated as independent. Each policy within a cohort uses identical targets. The new repository CLI wraps the original Python model; its execution against the full archive is pending, rather than claiming the independent reproduction executed repository code.

| Prior games | Policy | Played holdouts | Dates | FD MAE | FD/minute MAE | Minutes MAE |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 8 | Equal 8 | 1164 | 16 | 8.58417 | 0.25438 | 4.34058 |
| 8 | 8 min / 4 rate | 1164 | 16 | 8.96259 | 0.27326 | 4.34058 |
| 8 | 8 min / 50:50 4+8 rate | 1164 | 16 | 8.70668 | 0.26106 | 4.34058 |
| 12 | Equal 12 | 322 | 8 | 8.34562 | 0.24938 | 3.83169 |
| 12 | 12 min / 4 rate | 322 | 8 | 8.24458 | 0.25808 | 3.83169 |
| 12 | 8 min / 4 rate | 322 | 8 | 8.23771 | 0.25808 | 3.71750 |
| 12 | 12 min / 50:50 4+12 rate | 322 | 8 | 8.20513 | 0.24941 | 3.83169 |

The new blend worsens the larger eight-game sample versus equal eight and modestly improves total points MAE on the twelve-game cohort without improving standalone FD/minute MAE. Retain equal eight as the larger-cohort history-only benchmark and the 12-minute/4+12 rate blend as an experimental challenger, not an automatic scoring policy. Equal-eight mean signed point error -1.716 FD decomposes into -1.276 minutes effect and -0.439 rate effect; mean absolute effects 4.104 and 7.009 FD respectively, not additive absolute errors. The production-rate component is substantial. Both cohorts condition on played games with at least ten minutes and complete earlier observed games; do not infer availability, missing scheduled games, full-pool DFS error or future performance from these results.

Reproduce with `python nba_archive_replay.py official-box-observations.zip` using the authorized private artifact. No private rows copied into model repo, no Friday inputs, no MLB or production changes.
