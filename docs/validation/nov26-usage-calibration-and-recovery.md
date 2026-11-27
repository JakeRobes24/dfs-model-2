# NBA usage, NFL range calibration and archive recovery

Draft PR #12 continuation from `bde3782`. November 26 Eastern Time. All experiments use archived evidence or publicly available historical sources. Live scoring changes require prospective verification.

## NBA opportunity and production

Joined the NBA's public advanced and traditional V3 boxes by exact scheduled game ID, team and NBA player ID. The official schedule provided all 60 final games involving Boston, Chicago, New York or Toronto from Oct 21 through Nov 25. Both box types were retrieved and matched for all 60 games. Require the same positive minutes in both boxes and at least ten minutes in each game observation. The four-game model and target require consecutive completed team games. The provider's possessions and usage percentage are distinct from the box-score opportunity-per-minute proxy.

| Comparison | Equal-date error |
| --- | ---: |
| FanDuel points from four-game production per minute | 7.869 FD |
| Same rate per possession with pace blended halfway toward the last two games | 7.884 FD |
| NBA usage percentage from the prior four games | 4.090 percentage points |
| NBA usage percentage from the prior two games | 4.697 percentage points |

There were 320 matched holdouts across 25 dates. The shorter usage window and tested pace adjustment both increased error. Retain the existing model. This was a history-only cohort conditional on playing ten minutes and four complete prior games. PBP Stats returned 44 usable responses over a wider 122-game request set. Its strict sample produced only seven holdouts on one date. Use the NBA boxes for this comparison and keep the PBP Stats counts separate.

## NFL yardage interval calibration

The prior batch lowered distribution error using separate draws of snap workload, opportunity and efficiency. A new check compared the original nominal 80% intervals with an additive correction calculated only from earlier weeks. For each metric and method, the correction estimates the required extra yards beyond the earlier interval's boundaries. Report equal-week averages on the same six matched evaluation weeks after the 50-player warmup.

| Variable-efficiency draws | Played holdouts | Original coverage | Calibrated coverage | Original interval score | Calibrated interval score |
| --- | ---: | ---: | ---: | ---: | ---: |
| Rushing yards | 381 | 52.9% | 79.7% | 107.90 | 94.24 |
| Receiving yards | 822 | 46.5% | 79.5% | 120.79 | 101.34 |

Lower interval scores are better and penalize wide intervals and large misses. The calibration widened the rushing intervals from 38.1 to 62.6 yards and receiving intervals from 39.7 to 64.7 yards. Results are conditional on played rows and four verified prior games. Game script, teammate dependence, availability and full FanDuel lineup ranges still require separate validation. This calibration is available for historical replay.

### First-read audit

Joined FTN Data via nflverse (CC BY-SA 4.0) to nflverse play-by-play by game and play ID. Restrict to actual receiver-directed passes, excluding two-point attempts and no-play rows. All 10,258 such plays across the 163 verified final games matched documented read codes, but only 15 were labeled code `0`. The published codebook identifies `0` as the primary read. There were zero complete four-game windows with usable primary-read data, even before excluding rows where `date_pulled` was too late. The source did not support a first-read predictor in this sample. No codes were relabeled. Routes and first-read targets remain distinct. [FTN codebook](https://nflreadr.nflverse.com/articles/dictionary_ftn_charting.html).

## Numerical source expansion

DailyFantasy.tips published a FanDuel-specific board for archived Thanksgiving contest 137123. The new Classic staging comparison matched **all 153 original IDs, salaries, teams, opponents and positions** against the recovered contest export. There was one extra provider ID and 22 contest players marked unavailable. Among the 86 eligible players with a labeled DAILY score, the average absolute difference was 1.270 FD points, with three gaps of at least five. This is forecast disagreement. The provider page was retrieved after the slate and its displayed time lacked a verified timezone. Its methodology blends two unnamed sources. The new UI scopes results to both uploaded file hashes and retains advisory-only numbers. [Provider board and methodology](https://dailyfantasy.tips/nfl/).

The direct access pass covered all 26 saved entries and ten related endpoints. It found visible tables for NBA House, Courtside, PropSims, Edgehalla, a small RotoGrinders preview, and NFL Daily Fantasy Fuel. The FanDuel Research page returned 403 on direct access. The DraftEdge NFL homepage exposed sample tables, while its NBA board did not return usable direct content on this pass. Razzball's NBA page responded with a lineup title but no public projection rows in the HTML. SaberSim and Stokastic pages responded without table rows. LineupExperts, FantasySportsEdge, MatchWiz, KeelStats, Fantasy Team Advisors, TheCapper, RotoWire, Linemate, WalterPicks, Fantasy Points, FantasySharks, Upper Hand Fantasy and The Fantasy Footballers returned pages requiring a source-specific verification step for numbers. The 4for4 registry link is a legacy notice; the existing dated position-page adapter is separate. STAT-API documentation exposes schemas and the feed still requires authorization. FantasyProjections provider identity is unresolved. HTTP access, schema rows and page previews do not establish admissible pre-lock estimates.

## Website archive recovery

The owner-only receipt panel accepts a previously downloaded packet after a fresh session. It shows the contest and digest, checks for an existing exact-byte receipt, and permits an explicitly reviewed retry when intake access is configured. A successful readback prevents a repeat write. Missing packets can be submitted using their original bytes after full slate payload validation. Missing or mismatched remote bytes never become a success receipt. Automatic preservation retains a downloadable packet when the write fails and the session survives. Recovery still requires a previously downloaded packet or an existing remote copy after a full reset.

Controlled tests cover fresh-session retry, immutable readback and contest mismatch. Hosted production save, publication and recovery are still tracked by [issue #9](https://github.com/JakeRobes24/dfs-model-2/issues/9).
