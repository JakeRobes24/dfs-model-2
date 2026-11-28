# NBA and NFL predictive evidence, November 26

Base is PR 12 at `6c83e04ca5419bca6b32fa403f052b6955dbfa3b`. This batch is isolated from production and preserves the existing projection and lineup inputs.

## NFL public numerical reference

4for4's public QB, RB, WR and TE FanDuel tables exposed 38 parseable Week 12 rows. The Thanksgiving contest 137123 matched 14 of 131 eligible players using name, team, game orientation and roster position. The provider showed a November 25 7:40 p.m. ET publication time. The actual retrieval was around 5:13 a.m. ET on November 26, before the 12:30 p.m. ET cutoff used for this capture. The adapter records both times, excludes post-cutoff or stale results, collapses ambiguous identities, and reports coverage by position. Partial access and editorial independence limit this to advisory use. It is excluded from automatic consensus and does not cover targets, routes, kickers, defenses, or the full field. The exact capture and import hashes are preserved with private research.

The largest matched source disagreement was Emmett Johnson at 19.8 versus DAILY 4.1. This is a workload and availability review flag. It carries no automatic adjustment.

## NFL historical receiving opportunity

Retrieved 41 completed ESPN regular-season game summaries for LAR Corum/Williams, DET Gibbs/Montgomery and CHI Swift/Monangai. Exact provider identities and carries matched the previously saved official logs. Team volume sums all credited individual targets. Four games lack a target row for one back. Missing rows block windows instead of filling zero. These cohorts are conditional on the earlier paired-carry inventory. Seventeen held-out game dates had usable four-game history and both actual targets. All three policies use the same rows.

| Targets policy | Equal-cohort MAE | LAR games | DET games | CHI games |
|---|---:|---:|---:|---:|
| Last available game in window | 1.400 | 5 | 10 | 2 |
| Four-game target mean | 1.767 | 5 | 10 | 2 |
| Four-game team volume with recent player shares | 1.699 | 5 | 10 | 2 |

On the same two Rams backs in contest 137104 on November 25, DAILY target MAE was 5.175. The three historical estimates had 0.50, 1.50 and 0.985 target MAE, respectively. DAILY carry MAE was 13.715 versus 7.50 for last game, 10.375 for equal-four and 10.05 for recent-weighted-four. The historical windows predate the game, but the policies were chosen retrospectively. One archived DAILY game and three historical backfields do not establish a general change to NFL scoring. Preserve routes, snaps and pre-lock source captures before testing further.

## NBA opportunity versus production rate

Joined the recovered 210-player November 25 morning contest export to official outcomes across all six games. The morning export has no certified capture time. On 120 eligible players with complete paired forecasts and played outcomes, point MAE was 8.805 DAILY and 7.233 reviewed. Mean absolute minutes contribution fell from 7.763 to 5.449 FD points. Mean absolute production-rate contribution was 6.024 for both. These contributions can offset and do not sum to total MAE.

The narrower time/rate experiment requires an exact reviewed player, one fresh source with paired minutes and points, at least three recent official games and agreement within three minutes between source and historical estimates. Large disagreements of five or more minutes surface a midpoint, a four-minute capped change and a midpoint with 25% provider rate. The advisory view and archive capture are restricted to a schedule-verified pre-tip session. It does not change optimizer inputs.

Five November 25 players qualify in the retrospective snapshot using the historical audit's conservative 6:36:42 a.m. ET timestamp assumption. On those exact five observed outcomes, reviewed minutes MAE was 11.419 and midpoint minutes MAE was 3.507. Point MAE was 6.780 for DAILY and reviewed, 6.545 with the time-only midpoint, 6.355 with the midpoint and 25% provider rate, and 6.317 with the capped change. The selected sample is small and retrospectively defined. Start with frozen pre-lock rows before any accuracy or superiority claim. Current simulation calibration remains limited by the number of strictly timed historical slates. There is no change to correlation weights, ownership, or contest win probabilities.

## Archive and release

New remote submissions require byte-for-byte readback at the returned commit before the app shows confirmation. Duplicate immutable submissions retain their exact-byte check. Receipt confirms research-packet durability separately from backup publication. The Streamlit app's download-before-submit and independent recovery lookup remain available. Hosted owner-authenticated workflow verification is still pending.

Rollback before release consists of leaving the development changes off main. Any future release needs the hosted two-CSV and private archive verification, independent prospective prediction results and owner approval. Keep the exact approval scoped to the tested commit and preserve the previous production revision and history pointer.

The local Streamlit NFL entry point accepted both original Thanksgiving CSVs, retrieved all four public pages and displayed the 14 matches. The official schedule lists zero NBA games on November 26, so the NBA check uses the historical six-game file, focused tests and the local Streamlit regression suite. Protected source and contest-specific recovery records remain on the private research branch.
