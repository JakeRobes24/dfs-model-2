# Nov 28 public numerical-source review

Continues 61aebadd2e6417f8b5dec9353003541ee54261c7. Previous regression runs NBA 46139795781, NFL 46139795789 and full 46139795868 all completed successfully. Maintain the existing NBA/NFL live-performance audit and mandatory workflow; no MLB expansion, production score change or new automatic scoring vote.

## NBA: recovered Vektor Labs minutes

Public source https://www.vektorlabs.app/nba?date=2026-11-27, historical Miami at New York game table, retrieved November 28. Source labels rows frozen but neither an original pre-tip capture nor per-player publication time independently established. Current-day page had no projections in the inspected response; later-day injury timeline entries are not usable as contemporaneous morning information. Partial box-score stat projections, minutes and separate conditional availability, including censored 78%+ display. Do not equate a conditional minutes forecast to unconditional minutes or treat displayed 78%+ as exact probability.

Compare entire displayed first-game minutes table, 32 source rows, to private archive 8549d752ae253e972d09f160dfa6d5cee08be9a5, daily-lineups/2026-11-27/137257-full-pool/full_pool_audit_v2.csv, blob f9d6d72a611c6e42777a4c4f6c19bfa9f67bfc24. Exact normalized names (Unicode accent/punctuation normalization), team and oriented game, NYK mapped to NY. 30 unique matches, two unmatched. Require played_box, positive actual and reviewed minutes, complete finite DAILY, base and revised minutes. 18 matched rows also have NBA House estimates. Of 12 excluded matched rows, seven not listed in played table, four explicit final OUT and one played row with incomplete/nonpositive comparator. No inference of zero. Count statistics not evaluated in this batch. Exact retrospective common-support numerical calculation executed in JavaScript.

| Forecast | N | Minutes MAE | Signed error |
|---|---:|---:|---:|
| DAILY |18|7.6846|-6.2039|
| Original review |18|4.2180|-2.3764|
| Revised review |18|3.3770|-1.0103|
| NBA House |18|4.3185|-2.5222|
| Vektor Labs |18|3.0704|-0.8833|

Only one game, conditional played cohort, manually transcribed source minutes, recovered source timing unverified. Existing frozen review uses different stages and inputs. No proof of independent incremental benefit or new weight. Priority candidate for timestamped acquisition and prospective component comparison, including separate availability.

## NFL: numerical component overlap

Public https://voltfantasy.com/nfl/projections and https://www.malteranalytics.com/fantasy-football/2026/week-12. Inspected November 28. Volt default half-PPR with relative update label, claimed kickoff freeze, projected target/carry counts, yards, catches and ranges. Malter page reports Saturday 5:17 AM ET update, half-PPR, projected yards/catches and historical trailing-three-game snap/target/carry shares. Exclude already played and Monday games from sample. Match names, teams and oriented games for six overlapping Sunday WRs and nine overlapping Sunday RBs selected from displayed public rows, not a complete contest or a randomly sampled universe. No external official schedule or contest-ID verification yet. Comparison is source disagreement, not actual error or evidence of true independence. Calculations executed in JavaScript.

| Metric | N | Mean absolute difference | Mean Volt minus Malter | Maximum absolute difference |
|---|---:|---:|---:|---:|
| WR receptions |6|0.3333|-0.2667|0.7|
| WR receiving yards |6|2.6667|0.3333|4|
| RB receptions |9|0.7000|0.3000|1.8|
| RB rushing yards |9|5.2222|3.6667|18|

Do not equate Malter historical target shares to a target forecast. Do not convert incomplete half-PPR scores to complete FD scores by assuming missing bonus/turnover events. Neither source has a certified pre-lock capture or accepted model weight in this review. Capture exact dated component rows and compare with official post-game outcomes on the next applicable slate.

## Other candidate access

- Parlae https://parlae.io/fantasy/nba/projections: numerical minutes, FD-equivalent stated scoring and partial stat ranges, but direct response displayed November 27 with 4:23 PM ET update while search snippet advertised November 28. Do not treat search snippet as current board validation. Need exact dated numerical capture and source lineage.
- Dimers https://www.dimers.com/nba/player-projections and https://www.dimers.com/nfl/player-projections: partial visible stat projections, majority locked, full board and CSV access not established. No subscription acquired, no claim of full coverage or paired minutes.
- PredictEdge https://predictedge.bet/fantasy/: inspected direct response returned no populated numerical board despite search snippet; defer registration until actual access established.

Add Vektor Labs, Parlae, Volt Fantasy, Malter Analytics and Dimers as five manual reference candidates in the existing registry (47 total). Preserve all 42 prior sources and their existing mode. Regression case added to ensure no automatic coverage claims, no duplicate source names, and sport-correct links. New CI pending at documentation time. No numerical data added to production scoring and no player-level external data published to repository. Source availability remains separate from comparable forecast evidence.