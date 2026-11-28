# November 28 late forecast revision and ordering audit

Predecessor cd3bca5e49d2558afa82d1a0117477bd9f07067e passed NBA 46140205602, NFL 46140205607 and full 46140205614. Retain 47-source registry, original predictive accuracy roadmap and MLB deferral.

## NBA Nov27 contest 137257

Exact private archive 8549d752ae253e972d09f160dfa6d5cee08be9a5, daily-lineups/2026-11-27/137257-full-pool/full_pool_audit_v2.csv, blob f9d6d72a611c6e42777a4c4f6c19bfa9f67bfc24. Require unique contest IDs, played_box, finite original and revised minutes and FD and observed outcome, positive minutes for all three. 141 of 245 archived rows supported. Source-specific timing and recovered original review chronology retain previous limitations; this is retrospective, not a certified prospective holdout. Compare base_min/base_fd against in_min/in_fd. All outcomes use archived actual_fd, with prior display/box disagreements preserved. No new fitting or player-specific adjustments.

| Forecast cohort | N | Original FD MAE | Revised FD MAE | Closer/farther |
|---|---:|---:|---:|---:|
| All |141|7.37498|7.39724|68/73|
| FD increase >=2 |24|8.66850|8.48848|12/12|
| FD decrease >=2 |2|19.15727|21.28734|0/2|
| Absolute FD change <2 |115|6.90012|6.92793|56/59|
| Minutes increase >=2 |27|7.39342|7.35462|12/15|
| Minutes decrease >=2 |1|.39039|2.41091|0/1|
| 17:15 Q status, played subset |4|4.77620|6.04181|1/3|
| Other recorded statuses |137|7.45086|7.43681|67/70|

Cohorts overlap. Changes directionally toward actual on 71/141, but only 68/141 reduce absolute error. Mean revision +.75615 FD, mean signed error -.26858 -> +.48757. Not a claim that news updates are harmful, and cannot evaluate DNP avoidance on this conditional played sample.

| Forecast | MAE | Signed bias | Equal-game non-tied pair ordering |
|---|---:|---:|---:|
| Original |7.37498|-.26858|73.5063%|
| Revised |7.39724|+.48757|74.0987%|
| Revised minutes x original rate |7.39724|+.48757|74.0987%|
| Original minutes x revised rate |7.37498|-.26858|73.5063%|

Minutes MAE 5.05249 -> 4.61620; rate MAE .273748 -> .273748. Hybrid results coincide with original and revised totals at reported precision, i.e. rate is effectively unchanged by this particular late revision. Equal-game ranking over seven games and 1,352 non-tied pairs, forecasts tied within 1e-8 count .5; rank improved in four games, worsened in two, tied in one. These comparisons are dependent and rank is not a salary-adjusted lineup decision. Evidence specifically prioritizes independent late production-rate inputs and frozen component comparisons, not reversing the minutes work.

## NFL Thanksgiving 137123

Exact private archive f62950c8705df3afb47fc4745bcb4ed877cdd11d, manual-slates/2026-11-26/137123/postslate-user-evidence/prelock-4for4-reference.json (159139939d1609ce1561c1b57206b2e7d3c1d90a) and full-pool-official-reconstruction.json (34c6b00839e4cca97e46acc1110ab88043630cee). Exact input fingerprints, unique contest IDs, team, oriented game, position, played status, same DAILY projection and publication <= observation <= recorded decision cutoff. 14 matched reference players. This is provider comparison, not an actual late model revision.

| Position | N | DAILY MAE | Reference MAE | Closer/farther |
|---|---:|---:|---:|---:|
| QB |5|8.212|7.944|3/2|
| RB |4|15.75|12.95|3/1|
| WR |2|4.35|3.40|1/1|
| TE |3|5.1333|5.3667|1/2|
| Overall |14|9.1543|8.1729|8/6|

Four reference increases >=2 FD, MAE 7.525 -> 3.675; no decreases >=2. Overall bias -3.3971 -> -1.0614. Pair-weighted same-position ordering on 20 non-tied player comparisons fell 65% -> 57.5%, ties count .5. Different providers and tiny selective support; no statement of general source superiority. Preserve independent weekly workload, production and same-position player comparisons on upcoming prospective receipts.

## Reproducibility and next gate

Actual archive computations executed directly in JavaScript. Added offline forecast_revision_audit.py and synthetic regression cases; new CI pending, no local Python execution claimed. No live optimizer/scoring/website policy change, no new historical weight, no new archive player records published. Next substantive research: improve independent timestamped late rate evidence and compare matched original/revised component forecasts; continue prospective source capture, availability, calibration and alternatives. No need to repeat these same aggregate historical calculations without new evidence.