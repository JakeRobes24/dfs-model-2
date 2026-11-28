# November 28 strict-window replay and prospective readiness

Recovered after interrupted conversation. Previous checkpoint 5cc3d4d3357d3b785c3d0055edb71c891f145738 remained unchanged. All three regression workflows completed successfully: NBA 46135691886, NFL 46135691897, full 46135691893.

## Stricter retrospective replay

Private archive 8549d752ae253e972d09f160dfa6d5cee08be9a5, research-evidence/2026-11-28/live-component-transfer/strict_history_shadow_results.csv, 196 rows verified by exact readback. Use same archived live normalized outcomes and official played observations as prior 223-row replay (see nov28-live-component-transfer.md). Retain most recent eight same-team observed played records within 30 days BEFORE target day, including short appearances in window selection; reject a window containing any incomplete or sub-10-minute record, rather than skipping that record. Require unique historical normalized name/team and NBA ID, no duplicated dates, official NBA game URL and matching oriented club, finite counting fields within 0–150, minutes 10–60, positive four/eight-game opportunity denominator. Require incumbent minutes 10–48, score 0<FD<=150, positive rates <=5, finite DAILY and recorded outcomes, actual minutes 10–60. Use 20% weight for each historical rate/minutes alternative, cap historical mean minutes at 48. Exclude out/questionable/doubtful/GTD/suspended/inactive as applicable using Nov24 frozen injury_flag/prelock_status, Nov25 recovered injury_flag/prelock_status, Nov27 status_1715 in archived 18:40 manual checkpoint. No later actual status used for candidate construction. Exact Nov24 blocked IDs recorded in prior research packet; Nov25 and Nov27 status mappings use original contest-specific IDs. Exact same played matched support across all methods. Independent local Python replay actually executed. This is closer to existing history-window rules but not byte-exact invocation of nba_window_shadow.py: conservative name matching instead of complete alias registry, manually mapped Nov27 statuses, archived observations may be incomplete, no frozen prospective prediction record and Nov25 timestamp unverified.

| Date | Eligible played complete baseline | Paired | Rejected uncertain | Rejected identity/duplicate | Rejected under 8 | Rejected incomplete last 8 |
|---|---:|---:|---:|---:|---:|---:|
| Nov24 | 50 | 37 | 1 | 5 | 4 | 3 |
| Nov25 | 95 | 70 | 2 | 6 | 6 | 11 |
| Nov27 | 119 | 89 | 3 | 8 | 6 | 13 |

| Forecast MAE | Nov24 | Nov25 | Nov27 | Equal-date |
|---|---:|---:|---:|---:|
| DAILY | 10.9703 | 9.9029 | 9.6910 | 10.1880 |
| Reviewed | 8.8407 | 7.1181 | 8.1931 | 8.0507 |
| 4-game rate | 8.6186 | 7.0112 | 8.2359 | 7.9553 |
| 8-game rate | 8.5210 | 7.0834 | 8.2065 | 7.9370 |
| 8-game minutes | 8.7052 | 7.1580 | 8.1217 | 7.9950 |
| 8-game both | 8.3914 | 7.0904 | 8.1341 | 7.8720 |

Player-weighted incumbent/combined MAE 7.9315/7.8099. Improvements/worsenings 25/12, 38/32, 50/39; no ties. Selected-player matches 14,9,16 with MAE incumbent/combined 10.5975/10.3583, 4.4500/4.3412, 9.5240/9.5885. RMSE 11.4951/11.0789, 9.3824/9.1261, 10.6435/10.5909. Minutes MAE 3.5200/3.3296, 5.4727/4.8693, 4.5539/4.5213. FPPM MAE .23643/.22849, .26412/.25950, .24773/.24872. No lineup reoptimization or claim of tournament gain. Three retrospective dates, repeated players, selected and nonselected stage differences; support 196/264 eligible played complete baseline rows, not the entire contest population. Keep research challenger unpromoted.

## Prospective readiness and next slate gate

- NBA existing nba_window_shadow.py already has versioned freeze and exact-input recomputation checks. nba_shadow_multislate.py distinguishes earlier exploratory from prospective dates; requires five supported dates and 100 paired rows before independent validation, not automatic promotion. Use the established 20% history-window challenger unchanged. Record eligible coverage, supported rows, exact source history, source times, incumbent and four challenger values in each pretip receipt. Existing capture is only verified in code/regression, not new owner-authenticated hosted roundtrip. Manual Nov27 data and new retrospective sensitivity do not count as prospective receipts.
- NBA tracked conversion alternatives (rebound chances, field goals made) showed historical transfer benefits; no full live component inputs verified for upcoming contest. Capture exact dated chances, shots and potential assists where accessible. Do not derive made-shot FD totals without shot mix/free throws and other components. No new policy promoted.
- NFL existing app_nfl_staging.py supports exact contest/DAILY coverage, timed 4for4 and Sunday PropSims captures, weather receipts, independent review and fixed-candidate research comparison. It is not a certified live optimizer or an implemented prospective expected-scoring forecast generator. Preserve source receipts, original and fully reviewed player forecasts, exact entry IDs, all eligible candidates and scenario forecasts with cutoff times. Preserve expected-opportunity challenger separately only when exact prior history and published-before-kickoff evidence support it; do not reconstruct a missing forecast as prospective. Provider publication/training lag remains unverified for historical ffopportunity. Route and first-read availability remains a research evidence task. Do not claim verified upcoming contest inputs until supplied.
- Capture actual participation separately from score, both conditional and unconditional outcome intervals, plus exact outcome reconciliation and all entry results. Maintain free legal source access and the existing mandatory full-pool review; no MLB expansion. Do not delay contest execution for a research experiment. No live scoring, optimizer or website change in this documentation checkpoint.

Next: complete prospective receipts on the next actual NBA/NFL slates when inputs arrive; continue the rolling multi-slate audit and independent source coverage. The next live outcome is essential for prospective evidence; historical exploration cannot substitute.
