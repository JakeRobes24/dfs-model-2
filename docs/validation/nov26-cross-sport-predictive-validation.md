# November 26 cross-sport predictive validation

This experimental checkpoint continues PR #12 from `c936e6cf620c1ce885e6aa2da9b184adf8e432b1`. It adds matched provider coverage, an NBA minutes challenger, an NBA simulator comparison, and a reproducible NFL workload and yardage benchmark. No scoring weights were changed.

## NBA provider evidence

Replayed the frozen November 24 FanDuel slate 137128 against the existing 105-row verified official outcome fixture. The frozen packet SHA-256 is `3a6167f57f3de9a02ddf9aa64620ec69236b045546a0e3ef0566259b502ad984`. Each comparison uses the same players for the named provider, DAILY and the reviewed model. Coverage differs across providers.

| Provider | Measure | Matched players | DAILY MAE | Reviewed MAE | Provider MAE |
| --- | --- | ---: | ---: | ---: | ---: |
| NBA House | Minutes | 65 | 7.27 | 4.22 | 4.01 |
| RotoWire | Minutes | 30 | 7.29 | 4.09 | 3.38 |
| PropSims | Minutes | 56 | 7.57 | 4.06 | 3.55 |
| PropSims | FanDuel points | 59 | 9.93 | 8.83 | 7.77 |
| Daily Fantasy Fuel | FanDuel points | 24 | 12.93 | 10.98 | 9.15 |

On the 57 players with forecasts from at least two accepted providers, minutes MAE was **7.49** for DAILY, **4.01** for reviewed, **3.49** for the provider median, and **3.68** for a 50/50 blend with reviewed minutes. Each player has one vote per provider family and only one contribution to the error. This single date supports testing the challenger on additional exact replay dates. The [previous paired attribution](nov26-nba-minutes-rate-attribution.md) explains the same-source PropSims rate and minutes results. Rate-only improvements were inconsistent when measured in FanDuel points.

RotoGrinders and LineupExperts had no qualifying forecast in this packet. The NBA and NFL evidence tables use the entire applicable source registry and distinguish scored outcomes, captured forecasts, and archive gaps. A missing comparison does not establish that a source is unavailable. Official sources are primarily outcome and availability evidence. Reference-only, app-only, subscriber, and unresolved-identity providers retain their prior roles. See the [public access review](nov26-provider-access-review.md) for source-specific constraints. The private Week 12 public 4for4 archive matched 14 pregame forecast rows after original contest/DAILY hash, player, team, game and position checks. The contest CSV contains 153 player rows. Accuracy is pending matching final outcomes.

## NBA simulation

An opt-in simulator estimates errors in FanDuel points per minute on played training rows with at least ten actual minutes, then scales the sampled error by the simulated playing time. The comparator keeps additive point errors. Both share the same chronological training players, minute draws, reviewed target projections, and random seed. The standard in-app comparison requires verified pre-tip captures.

A descriptive replay trained on 51 November 24 players and used 120 November 25 official played outcomes. The November 25 morning export lacks a certified capture, so these figures are excluded from the strict calibration gate. Seed 42, 4,000 draws per player.

| Error model | FD median MAE | 80% interval score ↓ | Mean interval width | Observed coverage |
| --- | ---: | ---: | ---: | ---: |
| Additive points | 7.25 | 35.82 | 29.00 | 85.8% |
| Rate × sampled minutes | 7.30 | 35.08 | 22.40 | 73.3% |

The rate approach narrowed the intervals and improved the proper interval score slightly. It missed the nominal coverage and increased median MAE. Additional frozen slates are needed to estimate repeatability and player-band calibration. Neither policy models DNP risk or certifies tournament-winning probabilities.

## NFL workload, efficiency and teammate dependence

Recovered 41 final regular-season team-game records across 39 distinct ESPN summaries, preserving exact game/athlete IDs and the existing cross-checked carry and target counts. The [recorded evidence](nfl-yardage-evidence.json) includes per-game source links and corresponds to SHA-256 `b6eb8e9cbca893014bb17dd4b171931e6c97fb4925b7c92fea30dfc8eace505d`. Missing target and yardage rows invalidate affected windows. The comparison holds out a game and uses exactly the preceding four cohort games. Recency weights are 1:2:3:4. Efficiency shrinkage adds the equivalent of 12 carries or six targets at the pair's observed rate. These are fixed research assumptions.

| Cohort | Yardage | Held-out games | Last game MAE | Four-game yards MAE | Recent workload × pooled efficiency MAE | Recent workload × shrunk efficiency MAE | Paired / independent CRPS ↓ |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| LAR | Rushing | 5 | 36.00 | 35.28 | 35.05 | 35.66 | 44.74 / 40.25 |
| DET | Rushing | 13 | 47.73 | 37.04 | 38.19 | 37.79 | 42.52 / 38.99 |
| CHI | Rushing | 11 | 39.32 | 30.00 | 30.81 | 30.92 | 44.72 / 43.90 |
| LAR | Receiving | 5 | 9.30 | 14.63 | 12.43 | 11.77 | 19.66 / 17.51 |
| DET | Receiving | 10 | 32.10 | 20.53 | 21.68 | 21.47 | 25.49 / 23.70 |
| CHI | Receiving | 2 | 17.50 | 5.94 | 6.08 | 5.93 | 9.28 / 8.20 |

Four-game mean rushing yardage performed best on average across cohorts. Receiving gains from efficiency shrinkage were uneven. The simulation kept the same marginal player distributions and changed only whether two same-game samples stayed paired. Same-game sampling had worse continuous ranked probability scores (CRPS) in all six cohort/metric comparisons. The four-game windows and selected backfields limit how far that result can generalize. The records lack comparable historical DAILY forecasts and complete snaps, routes, passing, field ownership and real contest outcomes. Neither forecast MAE nor pair-total CRPS establishes a FanDuel lineup edge.

Reproduce the NFL result with `python nfl_yardage_validation.py docs/validation/nfl-yardage-evidence.json`. It emits held-out rows, training dates, predictions and distribution scores. In NBA staging, the same-player minutes and simulation comparisons appear in the historical evaluation. NFL staging displays captured 4for4 coverage after exact contest matching.

The next evidence gate is more verified pre-lock NBA captures and exact contest-paired historical NFL forecasts and final workload. Use those for a prospective comparison against DAILY and the reviewed policy before promoting anything. Experimental code and evidence can be reverted as a single development change.
