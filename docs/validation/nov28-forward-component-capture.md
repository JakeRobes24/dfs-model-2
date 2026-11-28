# November 28 forward component capture and NBA denominator sensitivity

Predecessor ca182e367c31ece47f9addb4768bc104b16d4705: NBA 46140956931, NFL 46140956909, full 46140956952 all succeeded. User clarified source classifications are informational; no further discretionary classification development. Return to predictive accuracy, source acquisition and performance audit for NBA/NFL. MLB deferred.

## NFL prospective advisory reference

Public boards inspected Nov28 for future Nov29 games: https://voltfantasy.com/nfl/projections and https://www.malteranalytics.com/fantasy-football/2026/week-12. Official revised schedule https://www.nfl.com/news/week-12-schedule-change confirms oriented NO@CIN, TEN@JAX and BAL@HOU all scheduled 18:00 UTC Nov29. Manual sample of 14 overlapping public rows (6 QB, 4 RB, 4 WR) saved before kickoff at reviewed-at 2026-11-28T06:44:26-05:00, private history commit 9b871619fa241bcfd7c1d18542604aa775643492, research-evidence/2026-11-28/prospective-nfl-week12/early-three-game-component-capture.json, blob 949e10dea47888ddc6f381148bc364ed0c3ea2bc. Exact text readback verified. Review clock after inspection, not authenticated provider fetch receipt. Volt relative update label, absolute publication unknown; Malter displayed Saturday 6:17 ET, not independently authenticated. No provider stable IDs or official roster reconciliation yet. Scope deliberately limited to visible overlapping rows, not the selected contest or complete slate. Historical trailing-three-game shares preserved separately from forecast components. Missing fields omitted, no postgame values or synthesized FD totals.

| Common component | Pairs | Mean absolute difference |
|---|---:|---:|
| Passing yards |6|3.8333|
| Passing TD |6|.1500|
| Rushing yards (QB/RB combined)|9|4.5556|
| Receptions |8|.4375|
| Receiving yards |4|3.5000|
| Receiving TD |4|.1000|

Disagreement, not actual error; no source independence inferred. Carry/target estimates from one provider remain available for separate future absolute evaluation, not the two-provider common comparison. A new read-only evaluator nfl_forward_component_reference.py requires exact name/team/oriented-game/position, caller-verified stable official identity, final played result after kickoff and matching kickoff. Compares explicit shared components only; unknowns never zero. No automatic scoring or claims of authenticated provenance. Wait for official actuals after games for evaluation; do not refetch and substitute these forecasts. Tests added, full CI pending. No contest CSV needed for this reference capture; actual contest pool still required for any lineup workflow.

## NBA short-appearance denominator sensitivity

Exact archive 8549d752ae253e972d09f160dfa6d5cee08be9a5, daily-lineups/2026-11-27/137257-full-pool/full_pool_audit_v2.csv, blob f9d6d72a611c6e42777a4c4f6c19bfa9f67bfc24. Strict positive played sample narrowed to finite DAILY, original and revised minutes and actual minutes all >=10, finite corresponding FD and salary. 108 matched rows from prior 141. Compute rate from paired points/minutes, no fitting, compare equal-player MAE. Recorded PropSims positive pair with source minutes >=10, not verified fresh scoring acceptance.

| Cohort | N | DAILY rate MAE | Revised rate MAE | Revised rate bias | DAILY/revised FD MAE | PropSims pairs |
|---|---:|---:|---:|---:|---:|---:|
| All |108|.26936|.25676|+.04904|9.6861/8.0549|39|
| Salary below 5000 |60|.29201|.27986|+.04663|8.1000/7.0163|0|
| Salary 5000+ |48|.24104|.22787|+.05206|11.6688/9.3533|39|
| Revised minutes below 30 |70|.29290|.28719|+.04086|8.8157/7.5254|7|
| Revised minutes >=30 |38|.22598|.20070|+.06411|11.2895/9.0304|32|

Lower-salary rate gap persists under stricter denominator (23% higher revised rate MAE, not prior 50% minute-group comparison). Conditional played-only retrospective support and one date; no causal conclusion. Vektor Labs date-specific Nov28 page unavailable on recheck; Parlae still displayed Nov27, so no new NBA pregame board captured. Need broader timestamped low-salary role/production evidence and prospective matched outcomes.

Numerical calculations executed directly in JavaScript. No production score changes, no new weight, no MLB. Private reference capture verified; development code and tests pending regression.