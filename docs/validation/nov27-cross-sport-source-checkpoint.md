# November 27 slate research and cross-sport validation

Continues draft PR #12 from `2ba5337e9a851cf41058034ea055add0b3366150` and the private `ad642fdbec4d7fb8950c1f1fa8c9c72ee8e0e6ac` checkpoint. The November 27 NBA capture below was made Thursday night Eastern Time. This is research and staging work. Live scoring weights remain unchanged.

## Friday NBA preparation

Reproduced the saved 285-player NBA House preview and its 281 same-team history matches, 268 three-game minutes, 233 eight-game minutes and 161 eight-game production rates. The private role archive was verified at SHA-256 `4c1e115c5a803f64b7a99e7c1c386541a12004e2a00061c6b2b201336f308010` and contains 4,841 observations and 4,348 explicit starting/bench roles.

The refreshed early board has 290 NBA House minutes estimates across 11 scheduled games and 56 PropSims paired forecasts across 10. All 56 overlap, with an average absolute minutes gap of 2.07 and four gaps of at least five. Of the 290 preview players, 285 have matching same-team history, 272 have three-game minutes, 236 eight-game minutes and 162 eight-game rates. Seventeen have an eight-game workload gap of five minutes or more. Edgehalla supplied 100 dated-board conditional forecasts over 11 games. Of 96 exact player/team/game matches on the refreshed board, seven are at least five minutes apart from NBA House. Edgehalla uses season/recent history, so agreement with our history is shared evidence. Its source publication time was unavailable.

The [NBA's 9 p.m. ET report](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-26_09_00PM.pdf) yielded 89 Friday rows, 29 exact preview matches. The report listed Austin Reaves, Dylan Harper, Joel Embiid and LaMelo Ball as questionable, and Giannis Antetokounmpo as probable. An unmatched report row leaves availability unknown. These are report-time statuses, and previous starter or bench roles are historical.

| Review item | NBA House min | PropSims min | Edgehalla min | Last 3 / last 8 min |
| --- | ---: | ---: | ---: | ---: |
| Austin Reaves | 26 | — | 34.3 | 33.28 / 34.75 |
| Dylan Harper | 24 | — | 31.6 | 31.34 / 31.04 |
| Dean Wade | 21 | — | 27.7 | 28.76 / 26.98 |
| Jeremiah Fears | 29 | 33.73 | 34.9 | 37.54 / 33.35 |
| Mo Bamba | 16 | — | — | 23.83 / 24.81 |
| Victor Wembanyama | 28 | 33.48 | 31.8 | 33.04 / 30.79 |

Reaves and Harper require a status and role recheck before using the higher conditional workload. Wade and Bamba need current rotation context. Fears and Wembanyama have overlapping evidence for meaningful upside relative to the lower minutes board, subject to news and the exact contest. The packet has all remaining flags and production-rate rows. Friday contest CSV and DAILY were unavailable in the inspected checkpoint. These are 11-game advisory comparisons. Contest eligibility, salaries, final starter confirmation, reconciliation and lineup certification remain pending.

## Matched predictive evidence

NBA history-only estimates held the longer-window production rate fixed and changed minutes to the average of prior three games or a 50/50 blend with the longer window. On 1,164 matched played rows and 16 dates, eight-game baseline minutes and FD MAE were 4.341 and 8.584. The blend yielded 4.387 and 8.581. On the 12-game cohort (322 rows and eight dates), the blend improved minutes 3.832 to 3.713 and FD MAE 8.346 to 8.325, still behind the earlier 8-minutes/4-rate model's 8.238. The three-game-only minutes estimate worsened point MAE in both cohorts. A separate same-row historical probe using only strictly earlier three-game team pace/defense inputs moved FD MAE from 8.584 to 8.576 for a half-size pace adjustment, to 8.591 for opposing defense alone and to 8.574 for both. These differences are small and retrospective. Keep prospective challenger comparisons.

NFL exact joins used nflverse weekly GSIS statistics, PFR offensive snaps, an unambiguous published player-ID crosswalk, and final season/game/team/opponent keys. The completed Weeks 1–11 dataset contains 3,412 matched player-games across 163 games and all 32 teams. The holdout requires four consecutive completed team games with exact matches and sufficient prior carries or targets. A missing match breaks the window. Position-level yardage shrinkage learns only from earlier calendar dates. All methods use the same targets within each metric; errors weight each of seven test weeks equally.

| Measure | Matched player-games | Baseline | Best tested comparison |
| --- | ---: | ---: | ---: |
| Carries MAE | 452 | 3.266 four-game mean | 3.224 snaps × workload rate |
| Targets MAE | 967 | 2.012 four-game mean | 2.018 snaps × workload rate |
| Rushing yards MAE | 452 | 20.389 four-game mean | 19.896 with shrunk efficiency |
| Receiving yards MAE | 967 | 22.700 four-game mean | 22.204 with shrunk efficiency |
| Carries CRPS | 452 | 2.565 empirical game draws | 2.491 separate snap/rate draws |
| Targets CRPS | 967 | 1.548 empirical game draws | 1.488 separate snap/rate draws |

NFL snap/yardage work is conditional on the matched played sample. It lacks original pre-lock DAILY across those weeks, route/first-read completeness, and lineup/contest outcome calibration. Separating snaps and rates is a marginal workload experiment. It implies no particular teammate, receiver/QB or lineup correlation.

## Source discovery and readiness

| Source | Verified result this session | Permitted evidence use |
| --- | --- | --- |
| Edgehalla NBA | 100 game-matched Friday minutes and component rows; publication time absent | Conditional advisory reference. History-derived overlap cannot count as a second vote for the same history. |
| PropSims NFL | 253 Week 12 Sunday rows with FanDuel medians and reported ceilings across nine scheduled games. Captured Thursday at about 9:06 p.m. ET, publication 1:36 p.m. ET. | Match exact contest IDs when files exist. Market-informed methodology overlaps sportsbook evidence. Refresh near lock. |
| PBP Stats | Public schema and completed NYK–TOR game `0022600241` checked, dated Nov 15 with oriented clubs and numerical team/player-stat sections. | Official-play-by-play-derived feature candidate. Validate IDs, possession definitions and data completeness before modeling. |
| nflverse / FTN | Verified snapped weekly outcomes and ID crosswalk above. FTN documentation distinguishes charting updates and delayed participation availability. | Reuse verified snaps and box components now. Maintain unknown for routes without verified charting. |
| BankrollSZN | Reachable public landing shell. No dated player forecast table verified. | Candidate for authorized export, no forecast weight. |
| FanDuel Research NBA and NFL | Public page describes CSV; runtime returned access denial. No dated rows collected. | Verify CSV and upstream provenance before any weight. |
| Basketball Monster | Public page exposes historical leaderboard headers; no dated projection rows verified. | Candidate for dated and scoring-matched export. |
| FantasyPros NBA | Cheat-sheet shell accessible, no dated player table verified in the response. | Aggregate only after underlying research-source overlap is known. |
| TipoffLab | Public examples exposed numeric sample rows; no exact Friday FanDuel board verified. | Sample only. |
| Dimers | Discoverable points/stat and line view. Direct response was a generic shell and dated search preview was locked. | Candidate for raw stat or matchup benchmark, no paired FanDuel pts/minutes evidence. |
| Daily Fantasy Fuel, LineupExperts, RotoWire and older references | Public pages or shells were reachable in this run. The existing same-day adapters retain their date gates. | Perform Friday date/timestamp and contest checks when appropriate. Existing accepted integrations and advisory roles are preserved. |
| Razzball, SaberSim, Stokastic, Establish The Run | Carried forward from earlier access review as candidates. | Recheck public or authorized exports. No subscription assumed. |
| MLB Stats API and Baseball Savant | Official Stats API returned all 30 teams' 2026 records and 277 scheduled spring games for Feb 20–Mar 10, 2027. Statcast search describes pitch/game-level inputs. | Separate historical, spring and regular-season data. No MLB projections trained. |
| FanGraphs/RosterResource | Public roster and candidate depth-chart source identified. | Audit preseason lineup/probable starter provenance and timestamps before joins. |

The validation code includes strict, schedule-matched parsers for Edgehalla and the NFL PropSims board. Their rows are advisory. Only the two documented source roles were added to the registry. References remain separate from consensus. The LineupExperts archive now explicitly uses its FanDuel field when generic points also appear, avoiding duplicate columns and ambiguous persistence.

The private restart folder is `research-evidence/2026-11-27/` on branch `research-evidence/2026-11-27-cross-sport`. It contains the numerical packet, test inputs and digests. The hosted owner-authenticated production reset and backup roundtrip remain open in issue #9. No hosted owner operations or production changes were performed in this checkpoint.
