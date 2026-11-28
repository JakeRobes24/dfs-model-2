# November 28 NBA-first availability forecast transfer and unresolved outcomes

Previous checkpoint be91bc4399cbf12fa3e78b8c1e86134b2a7cbdba: NBA 46149504252, NFL 46149504254, full 46149504245 all passed. Preserve all 48 research sources, NBA immediate priority, NFL retained, MLB deferred.

## Exact archived comparison
Private archive 8549d752ae253e972d09f160dfa6d5cee08be9a5. Nov24 original incoming-app/2026-11-24/137128/3a6167f57f3de9a02ddf9aa64620ec69236b045546a0e3ef0566259b502ad984.json (blob 97ad8103cee5606f1074cd18bfcdb964e2d592b3), exact unique contest-ID join research_csv and actuals_csv. Eligible, positive DAILY points and minutes <=48, not prelock hard out; use recorded prelock status with contest injury flag fallback. Actual played requires explicit NBA box-score calculation and positive minutes; DNP requires explicit NBA confirmed did not play and zero minutes/points. 79 known training rows, 9 DNP, minute bands <18/18–<28/28+ have 45/31/3 rows and 8/1/0 DNPs. Nov27 full_pool_audit_v2.csv (blob f9d6d72a611c6e42777a4c4f6c19bfa9f67bfc24), use original DAILY positive points and minutes <=48, exclude 17:15 O, recorded A/P/Q/D/blank. Outcomes as archived: played_box with positive actual minutes, explicit_final_out and zero FD, all others unknown. The Nov27 source labels include NBA House, not uniformly independently official outcome verification; stage differs from Nov24 morning, do not infer prospective calibration from this retrospective status mapping. 174 target rows, 142 played, two explicit DNPs, 30 unresolved (all projected <18 minutes). No unknowns treated as zero. No new model fit or today's slate inputs.

JavaScript executed existing nba_availability.py probability equations independently with fixed prior weight 20 and minute bands 18/28. Status group available/probable, questionable/doubtful, blank. Flat smoothed earlier DNP rate (9+.5)/(79+1)=.11875; minutes-only band shrinkage; minutes+status cohort with other-status backoff; zero-DNP reference. Compare Brier score (lower better) on 144 known outcomes. Zero-DNP reference is a diagnostic, not recommended forecast.

| Method | Known Brier | Full pool possible Brier lower/upper |
|---|---:|---:|
| Always plays |.013889|.011494/.183908|
| Flat prior |.024692|.022866/.154331|
| Minutes band |.028889|.028301/.145675|
| Minutes and status |.028646|.028153/.145217|

Observed DNP fraction 2/144; full-pool possible DNP fraction 2/174 to 32/174 (1.1494% to 18.3908%). These are logical bounds, NOT confidence intervals. For uncertain statuses seven targets, six known (four played/two DNP), one unknown. On known, zero/flat/band/cohort Brier .333333/.268268/.276514/.274251. Do not infer reliable Q/D probabilities from a seven-row mixed-status cohort.

## Joint missing-outcome sensitivity
For each missing outcome, calculate squared-error difference for both models under the SAME y=0 and y=1. Sum rowwise minima/maxima with known differences, divide by entire pool. Negative means challenger better. This avoids subtracting independent marginal bounds, which need not represent a shared completion.

| Cohort / comparison | Known difference | Entire-cohort possible difference |
|---|---:|---:|
| All: minutes/status vs always plays |+.014757|[-.038691,+.016659]|
| All: minutes/status vs flat |+.003954|[-.009115,+.005287]|
| All: minutes band vs flat |+.004197|[-.008657,+.005435]|
| Uncertain: minutes/status vs always plays |-.059082|[-.099105,-.045640]|
| Uncertain: minutes/status vs flat |+.005983|[-.011421,+.008116]|

Full-pool model ordering cannot be established from known-outcome Brier alone. The uncertain cohort beats zero risk for either possible completion, but is only seven players on a single date and does not establish superiority to a flat prior. Results depend on correctness of archived outcome labels and recovered pregame statuses. No statistical significance, causal claim, or deployment decision. Actual minutes and score never define a DNP except explicit outcome evidence.

## Implementation and decision
Added nba_availability_bounds.py and three synthetic regressions, including exhaustive enumeration of binary completions on a toy pool, invalid IDs/probabilities/outcomes, empty support, and robust direction check. Archive numerical replay actually executed in JavaScript. Module is read-only and requires caller-verified outcomes; not a new production participation estimator. Prioritize resolving missing outcomes where official evidence supports it, and capture exact timestamped pregame status and probability values before future evaluation. No changes to current scoring, player eligibility, simulation or portfolio rules. Latest regression pending; no hosted deployment.
