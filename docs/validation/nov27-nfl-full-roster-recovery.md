# November 22 NFL roster recovery and calibration

Continues draft PR #12 from `2a725db`. NBA contest 137211 and the earlier NFL role-pair study are preserved in [the preceding checkpoint](nov27-recovered-candidates-and-nfl-role-dependence.md).

## Original contest and lineup outcomes

Recovered the original FanDuel Classic CSV for contest 136799. The strict import contains 501 distinct player IDs across ten games, with 440 rows free of the importer's out flag. Every saved slot for all four archived candidates resolves to one original contest ID. All 16 distinct members pass the original salary, eligibility and recorded availability checks. The audit also verifies nine unique players, the original salary cap and legal team counts. Recorded CSV status is the only availability evidence in this recovery. [FanDuel NFL roster guide](https://www.fanduel.com/research/fantasy-football-strategy).

The skill-position calculation reconciles the original weekly player stats with the matched final workload history. It scores FanDuel offense, bonuses, lost fumbles, returns and own-fumble touchdowns when these categories have verified counts. The D/ST calculation builds team events from the final play-by-play, verifies the game date, week, clubs and final scoreboard, and applies the platform's offensive points-allowed formula. All 13 distinct skill-player outcomes and all three D/ST outcomes resolved on the exact slate and matchup. Buffalo 8.0, Denver 13.0 and Kansas City 7.0 FD points came from the play-by-play. The reconstructed Buffalo score and all eight entered skill outcomes independently match the user's settled lineup, totaling 161.6. [FanDuel scoring](https://www.fanduel.com/rules) · [nflverse field definitions](https://nflreadr.nflverse.com/articles/dictionary_pbp.html).

| Candidate | Salary | Saved preliminary FD | Reconstructed final FD |
| --- | ---: | ---: | ---: |
| 1, entered | $60,000 | 137.1 | 161.60 |
| 2 | $60,000 | 135.9 | 128.64 |
| 3 | $60,000 | 135.6 | 171.54 |
| 4 | $59,800 | 135.4 | 121.54 |

Candidates 2–4 are reconstructed alternatives. Their final totals describe what those saved rosters scored in hindsight. The original NFL DAILY, individual alternative projections, verified pre-lock availability, field scores and ownership are still missing. The only similarly dated DAILY found in the saved archive contained NBA rows. A full-slate optimizer replay and a contest-wide predictive or payout comparison remain unverified.

## Full-roster distribution comparison

The historical point forecast is the average of the four latest verified same-team appearances before the slate. All 16 members had four earlier verified scores. These are retrospectively reconstructed history estimates with no injury, original DAILY, weather or ownership inputs. D/ST may skip a game screened out for unresolved scoring. The 2025 scale fits use 2,516 skill residuals with complete consecutive four-game histories and 196 D/ST residuals with four preceding consecutive verified team games. The screen resolved 231 of 272 final 2025 games and 143 of 166 final 2026 schedule games present at extraction. Its exclusions cover blocked kicks with ambiguous platform scoring, ambiguous multi-fumble recoveries, missing play-by-play and scoring events that failed the final-score check. All three target D/ST games passed.

On the same four legal rosters, the challenger adds frozen 2025 residual dependence for same-team QB–WR (+0.255) and QB–TE (+0.230). The joint normal model uses equal individual means and variances for both policies. Pair-order probabilities use the same outcomes for shared players, so five or six common roster spots cancel per comparison.

| Policy | 80% coverage | Mean 80% width | Mean 80% interval score | Mean CRPS | Pair-order Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| Independent | 2 of 4 | 55.45 | 88.61 | 14.345 | 0.12925 |
| QB/pass-catcher covariance | 2 of 4 | 57.09 | 85.92 | 14.303 | 0.13055 |

Both methods miss candidates 1 and 3 above their upper interval. The challenger reduces those misses by widening the ranges, with a slightly worse pair-order score. The effective sample is one slate with extensively overlapping rosters. Keep the dependence challenger in research until it can be tested against frozen projections over multiple slates. Live scoring and lineup selection continue under the current policy.

## Numerical source coverage and staging

The existing 4for4 reference now parses the FanDuel D/ST board alongside its offense tables. It checks the exact format and week, verifies the defense's team link and matchup orientation, preserves publication and observation timestamps, and joins only to one eligible original contest ID. The comparison retains points allowed, yards allowed, sacks and forced turnovers alongside the source's fantasy projection. It remains advisory.

The public Week 12 board showed ten defenses. A capture on November 27 at about 3:24 a.m. ET retained nine projections across eight future games after verifying the scheduled kickoff. It excluded Dallas, whose game started before the provider's displayed publication time of November 26 at 7:12 p.m. ET. The saved sample is schedule-matched and awaits outcomes and exact contest-file comparison. The direct historical Week 11 FanDuel URL redirected to Week 12, the indexed Week 11 FanDuel publication was Monday afternoon, and the visible Week 11 standard ranking showed a Sunday 3:08 p.m. ET update. Neither the redirect nor the stale search timestamp supplies a pre-lock FanDuel input. [Live FanDuel defense board](https://www.4for4.com/fantasy-football-projections/fanduel/def/2026/week12) · [Standard ranking archive](https://www.4for4.com/fantasy-football-rankings/standard-6pt-patd/def/2026/week11).

## Newly verified NBA minutes and rate source

Drop Coverage joins the saved research registry as a public, timed reference. Its November 27 3:26 a.m. ET JSON capture carried a latest run timestamp of 12:17 a.m. ET. All 11 games matched the ESPN schedule on event ID, oriented clubs and tip time. The public player file contained 3,366 market rows. Complete numeric projections were public for 25 Brooklyn–Toronto players. Nineteen had positive minutes, and six had zero minutes with zero components. Twenty-three of 25 minute estimates were labeled model and two were labeled fallback. The active status of the zero-minute players is a separate outcome check.

The audit groups the six FanDuel scoring inputs and divides their weighted sum by projected minutes where positive. The result is a derived component score and production rate. It is unsuitable as a distribution percentile without the joint draws. On uniquely matched positive-minute rows, average absolute source disagreement was 2.53 minutes versus NBA House (19 players), 1.11 versus PropSims (five), and 1.34 versus Edgehalla (seven). The captures occurred at different times before the game. Those are disagreements, and final box-score outcomes are pending. The source remains advisory, with exact FanDuel contest matching pending. [Drop Coverage open data](https://thedropcoverage.com/api).

Run `python -m nfl_archived_lineups --help` for the original contest, archive, entered result, schedule and two seasons of matched stats and play-by-play inputs. The report records SHA-256 for each input. The hosted owner-authenticated save and backup verification remains open in [issue #9](https://github.com/JakeRobes24/dfs-model-2/issues/9).
