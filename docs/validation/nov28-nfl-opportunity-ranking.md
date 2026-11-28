# Nov28 NFL expected-opportunity player ranking

Prior 44ac9ad passed NFL 46139202014, NBA 46139202021, full 46139202017. Continue original predictive-accuracy roadmap. Recovered DFS_Model_2_Tracked_Opportunity_Validation.zip, whole archive SHA256 ff64f55a7b2fbf4bb86c31babb76947265e2f0f0b849542bf0c917ca2cd09fc2 verified. Exact nfl-expected-2026.csv: 3441 rows, 1147 player-game-channel keys with three matching policies, identical actuals, finite forecasts and exact half-blend arithmetic within tolerance. Data derived from ffopportunity and nflverse; earlier publication/model training lag unverified. Historical conditional played cohort; no current NFL contest forecasts, salaries, complete fantasy scores, availability or optimal roster results. Reused 2026 retrospective evaluation sample, not fresh holdout. Apply fixed prior season-selected overall channel weights from nov28-chronological-component-transfer.md (75% expected scoring receiving, 100% rushing); no new fitting. Compare rank discrimination, leader hit rate and leader regret within same position and channel among same-team or same-game matched players. Group must include at least two; actual ties omitted from pair ordering, tied predictions count .5; tied forecast leaders averaged rather than hindsight chosen. Average within groups then equal weeks (seven). Regret is actual best channel points minus forecast-selected leader's actual channel points, not lineup regret. Local Python executed, local regression passed.

| Scope/channel | Groups | Non-tied pairs | Actual-average order % | Expected-average order % | Prior blend order % | Actual-average regret | Prior blend regret |
|---|---:|---:|---:|---:|---:|---:|---:|
| Team RB receiving |58|63|58.31|68.10|64.11|1.6277|1.4079|
| Team TE receiving |52|63|60.60|62.09|62.92|2.3378|2.1262|
| Team WR receiving |143|292|67.58|70.18|72.01|2.8573|2.4698|
| Team RB rushing |89|103|75.73|76.05|76.05|1.0923|1.0304|
| Game RB receiving |72|194|54.22|61.14|58.53|2.9440|2.8926|
| Game TE receiving |82|196|57.05|58.95|59.31|3.2117|2.8745|
| Game WR receiving |93|713|67.61|70.72|71.47|4.7568|3.7849|
| Game RB rushing |84|286|69.50|69.14|69.14|2.6502|3.2828|

WR same-game leader hit .41832 -> .48438; same-team .60428 -> .64297. Raw expected receiving forecast often best for RBs and TEs; blend results differ by metric and scope. Rushing same-game ranking and leader regret deteriorated despite historical average error improvement in prior study. Samples overlap across team and game scopes and repeated weeks; no independent population claim. Do not use channel-specific leader as a DFS roster recommendation: full workload/production, passing, other scoring, salary, news and contest legality remain essential. No new weight promotion. Preserve exact per-group outputs in private evidence archive. Next prospective Sunday NFL source capture should include opportunity components and same-position alternative comparisons, not just full-score MAE. NBA and 42-source roadmap retained, MLB deferred.
