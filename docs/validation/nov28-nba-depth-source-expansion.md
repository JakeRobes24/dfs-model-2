# November 28 NBA-first depth-source numerical comparison

Previous 5dc0bde54e053851f8341e5e9711d2fb9238d896 passed NBA 46150316610, NFL 46150316630, full 46150316601. NBA immediate focus; NFL preserved; MLB deferred.

## TipoffLab public historical minutes
https://dfs.tipofflab.com/nba-dfs-projections/2026-11-27 retrieved Nov28. Page reports Nov27 17:43 ET update, DraftKings main slate, seven matching oriented games. Ten displayed player rows plus six additional numerical minutes estimates in news/update sections. No original pre-tip observation or source-lineage certificate; retrospective recovery only. Exact normalized names/team/oriented game (PHX=PHO, NYK=NY) matched 16/16 to private full_pool_audit_v2.csv, blob f9d6d72a611c6e42777a4c4f6c19bfa9f67bfc24, all played_box with positive actual/DAILY/reviewed/House minutes, status at 17:15 blank/A/P. Use authoritative FanDuel salary, not DK salary. Compare minutes only, not DK totals or DK rate. JS executed numerical calculations on exact archived common rows.

| Cohort | N | DAILY MAE | Reviewed MAE | NBA House MAE | TipoffLab MAE |
|---|---:|---:|---:|---:|---:|
| All |16|10.5100|4.9382|6.4385|3.8823|
| FD salary <5000 |8|12.8663|3.7798|6.7375|2.1250|
| Table |10|8.8203|5.7140|5.8417|5.0417|
| News/update |6|13.3261|3.6453|7.4333|1.9500|

All-sample signed minutes error DAILY -10.4875, reviewed -2.1544, House -3.9344, TipoffLab +.1906. All eight lower-salary matches lack archived PropSims paired minutes. TipoffLab is useful specifically as a depth-role minutes reference, not yet independent FD production evidence. Selective published cohort, stage/timestamp mismatch with final reviewed pool, one reused date, no new weights. Exact matched evidence saved to private research-evidence/2026-11-28/nov27-tipofflab-minutes-reference.json, commit f48e893df92532b9d8651c53eaa7efb94ac77492, blob f9175f9ae736b0874a675d35b159659f2d2ef1b6, readback verified.

## Additional source checks
- Statz https://statz.ai/nba/projections/players: public sample 10 populated current-date rows with six counting-stat projections and ranges, remaining visible rows masked; projected minutes and turnovers absent. Account required for broader access. No full FD or paired rate calculation. Current-day sample inspected for schema only, no today's lineup or contest claims.
- StatRankings https://statrankings.com/nba/players/daily-projections: existing registry source now notes NBA limited access. Direct page showed stale Nov27 board and just three DK fantasy-point rows, despite documentation of minutes and platform-specific points. No added independent votes.
- BTB Data https://btbhardwood.com/: member-only numerical board, displayed older refresh date; no numerical depth coverage verified. HoopVantage https://hoopvantage.com/props returned 403. Splash Play search result dated Nov27 20:51 ET, after first lock; not admitted as prelock evidence. No subscriptions or accounts created; these access checks do not imply a verified feed.

Add TipoffLab and Statz as candidates; preserve all prior 48 sources. Total 50 (8 direct/conditional, 7 advisory, 14 manual/historical, 21 candidates). Existing accepted point/minutes families unchanged; no new acquisition calls in live flow. New registry regression pending. No scoring or simulation change; do not claim lower-salary paired FD production coverage solved. Next prioritize exact contemporaneous full components and minutes from accessible sources, with official status, lineup and contest identity checks. Do not delay today's contest preparation for paywalled/blocked boards.
