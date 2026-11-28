# November 28: team minutes budget and rotation allocation diagnostic

Preceding verified development e213d3a; three workflows success (NFL 46133382443, NBA 46133382434, full 46133382488). Private history f62950c8705df3afb47fc4745bcb4ed877cdd11d. Read the Nov24 app packet (incoming-app/2026-11-24/137128/3a6167f57f3de9a02ddf9aa64620ec69236b045546a0e3ef0566259b502ad984.json, exact-ID join of research_csv and actuals_csv) and Nov27 full_pool_audit_v2.csv. Use reviewed morning minutes/points on Nov24, adjusted in_min/in_fd on Nov27. This is a new team-budget diagnostic, not a repeat of the prior individual minutes-shrink experiment.

## Team-level budget evidence

| Nov24 team | Known projected minutes | Forecast coverage |
|---|---:|---|
| DEN | 274.055 | 3 missing |
| ORL | 253.585 | complete |
| DET | 239.460 | complete |
| WAS | 247.700 | 2 missing |
| DAL | 238.030 | complete |
| BOS | 241.830 | 1 missing |

All 14 Nov27 teams already sum to 240 projected minutes (floating-point tolerance). MEM's contest IDs cover only 219.75 observed minutes because a played player was outside the original pool; other 13 teams cover 240 to within a second. Do not force unknown players to zero or claim that raw source estimates themselves sum to 240. The archived Nov27 reviewed values were already normalized.

## Fixed exploratory alternatives

Use the five largest positive forecast minutes per team (not assumed starters). Preserve the forecast FD/min rate. Compare unchanged forecast, proportional normalization to 240, then transfer 5% of normalized top-five minutes to other positive forecasts proportionally, or the reverse. Zero forecasts stay zero, no future actuals in candidate construction. Skip missing/invalid forecast minutes, infeasible transfers and teams without reconciled 240 observed contest minutes (retrospective coverage gate). Score only positive projected and actual minutes with known points across identical samples. These formulas are arbitrary fixed sensitivities, not optimized policies. Independent JavaScript replay of the archived rows produced:

| Method | Nov24 minutes MAE (33) | Nov24 FD MAE | Nov27 minutes MAE (133) | Nov27 FD MAE |
|---|---:|---:|---:|---:|
| Raw | 5.2030 | 7.8082 | 4.6789 | 7.2064 |
| Normalized | 5.3078 | 7.7080 | 4.6789 | 7.2064 |
| Top five down | 5.6142 | 8.0048 | 4.6753 | 7.1099 |
| Top five up | 5.2930 | 7.4735 | 5.0154 | 7.5453 |

Nov24 supports three teams (ORL/DET/DAL); Nov27 thirteen. Team projected top-five minute allocation minus observed after normalization averages +0.47 and +6.42, respectively, but differences vary substantially by club. On Nov27 DET +27.61, DAL +34.87, PHI +34.51, IND +31.61 and BKN +24.95, while BOS -20.48 and NY -15.50. Nov27 matched top five mean signed minute error +0.82 (64), other players -2.35 (69). Negative differences do not establish bench roles or cause. Outcome-only team reconciliation is not a live feature, and conditional sample excludes zero forecasts and unknown outcomes. All rates fixed; no lineup reoptimization.

## Decision

Normalization alone cannot fix within-team misallocation. Neither uniform transfer reliably improves both dates; retain existing scoring. Focus further evidence collection on timestamped depth-chart roles, substitution patterns, rotation size, availability and minutes source disagreements, not blanket reductions of selected players. The new offline helper refuses incomplete forecasts, checks per-player 48-minute bounds and leaves missing points unknown. The calculation above was executed in JavaScript; Python implementation/regression cases are committed, CI not yet verified at creation. No new NBA or NFL live scoring policy, website behavior or model weights. NFL workload/efficiency remains active priority from the preceding component audit. 
