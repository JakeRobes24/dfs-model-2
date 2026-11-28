# NBA production rates and NFL yardage distributions

Development checkpoint for draft PR #12, based on `2b17e07`. The NBA and NFL comparisons are advisory. Production scoring and lineup selection require separate validation and approval.

## NBA

The existing contest-scoped Edgehalla refresh now converts projected box components to conditional FanDuel points. Where both model and source have at least 10 projected minutes and positive points, the comparison shows each FD points-per-minute estimate and divides the FanDuel-point gap into a minutes effect and a production-rate effect. The effects sum to the gap before rounding. Each display and frozen reference retains conditional semantics. The source has no verified publication timestamp, so these rows remain outside the dated accuracy sample. Other qualifying dated references now get a matched FD points-per-minute accuracy metric alongside their existing point and minutes metrics. Both forecast and actual rate samples require at least 10 minutes.

Recomputed the Thursday evening preview using the saved, checksum-verified `friday-refreshed-advisory.json` (SHA-256 `1155df8925436e8ade4f0a77822382c7b25b847aa4ea6697254f3a86c4bf2130`). Among 96 exact name/team/game matches with the same-team eight-game minutes and rate baseline, average absolute differences were 1.74 composite FD points, 1.06 FD points attributable to minutes, and 1.68 attributable to production rate. The two effects pulled in opposite directions on 57 of 96 rows. Two players differed by at least five total FD points, with production rate the larger effect for one. The baseline and a history-derived board share historical information. These numbers measure disagreement before a contest is selected, with no realized outcomes or independent confirmation.

## NFL

Replayed the seven held-out weeks on the earlier verified NFL Weeks 1–11 workload file (3,412 exact final player-games, SHA-256 `255475bfa83fd49b5ee81b286fcdbc9d682590f60cf72d7ce394f946aec55dba`). Use `nfl_snap_workload_review.review_snap_workload` with the archived `nfl-final-matched-week-1-11.csv` in the [private evidence checkpoint](https://github.com/JakeRobes24/dfs-model-2-history/tree/af825d2362a9dc68ec310a47865f7db83d2312e0/research-evidence/2026-11-27). Each player uses four consecutive earlier completed team games and a strictly earlier position efficiency prior. The fixed- and variable-efficiency approaches share the same draws for snaps and opportunity rate. The variable approach independently samples the four game-level efficiency values with shrinkage and centers those values on the same efficiency mean. The older empirical baseline draws only from the four observed yardage results.

| Equal-week CRPS, lower is better | Played holdouts | Past game yardage | Snap/workload × fixed efficiency | Snap/workload × variable efficiency |
| --- | ---: | ---: | ---: | ---: |
| Rushing yards | 452 | 15.633 | 15.516 | 15.161 |
| Receiving yards | 967 | 17.332 | 17.005 | 16.622 |

Variable efficiency beat fixed efficiency and the past-game baseline in all seven weeks for both metrics. The four-game targets mean still leads the tested point forecasts (2.012 MAE versus 2.018 for the snap-based estimate). Holdouts are conditional on played and matched rows and sufficient prior opportunity. These results do not verify DNP risk, route or first-read coverage, FanDuel point-range calibration, cross-player correlation or contest performance. A new untouched slate remains the next validation step.

NFL staging now compares the market-informed [PropSims FanDuel board](https://propsims.com/dfs/fanduel/) to the uploaded Classic contest. It verifies exact games on the selected regular-season Sunday afternoon schedule, player identities, contest status, timing, and publication within 24 hours of observation. The receipt preserves the median and 85th percentile as separate metrics and uses the uploaded DAILY values for comparison. Live schedule and provider retrieval on Thursday at 9:55 p.m. ET returned 253 fresh rows across nine games using a synthetic contest scope built from the archived board. This exercises the provider and schedule, with real contest coverage still pending.

## Source expansion

| Source | Evidence and remaining gate |
| --- | --- |
| [FF Today weekly projections](https://www.fftoday.com/rankings/playerwkproj.php?Season=2026&GameWeek=12&PosID=30&LeagueID=1) | The 2026 Week 12 WR board exposes carries, yards, touchdowns and receptions, with no targets column. Displayed points use FF Today standard scoring. Publication time was not established, so use as a manual stat-line candidate. |
| [TheCapper NBA accuracy ledger](https://thecapper.io/nba/projections/accuracy/) | The provider reports 4.367-minute pregame MAE against 4.694 for its last-ten baseline on 1,437 played player-games. This is provider-reported. There was no November 26 game board, and a fresh, player-level slate export is still needed for an independent comparison. |
| [FantasyPros projection API](https://api.fantasypros.com/public/v2/docs) | The documented projections endpoint requires an API key. No numerical coverage or independent upstream weighting was established. |
| [NBA Stats usage definition](https://www.nba.com/stats/help/glossary) | Official usage requires on-court possessions and possession-ending free throws. The existing box-score opportunity-per-minute proxy is a different measure. Source coverage and exact play-by-play event joins must be established before testing official-style usage. |
| [nflverse refresh schedule](https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html) | PFR snaps and FTN charting have scheduled in-season updates. The consolidated participation feed is published after the postseason. Keep route and first-read coverage explicit until an exact, dated event-level join is verified. |

The hosted owner archive recovery is tracked separately in [issue #9](https://github.com/JakeRobes24/dfs-model-2/issues/9).
