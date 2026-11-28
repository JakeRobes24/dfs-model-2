# Nov28 prospective roster verification and opportunity/production attribution

Predecessor 36379209314220928d41de9a497b238c2b193e98 passed NBA workflow 46141784968, NFL 46141784984 and full 46141784988. Continue the approved multi-slate predictive accuracy audit for NBA/NFL; MLB deferred. No live scoring policy or production merge.

## Official roster and schedule verification
Reopened original frozen reference captures at private archive ref 6fec2959708e6c9289d99f52deb721be31566446. NBA 36 names across ORL@WSH and BKN@CHA, NFL 14 names across NO@CIN, BAL@HOU, TEN@JAX. Manually reviewed official NBA team roster pages for four teams and NFL roster pages for six teams; matched normalized name/team and NFL position to each saved reference row, and independently confirmed scheduled game times on official league schedule pages. NBA accented names were normalized; previous Alex/Alexandre Sarr source alias remains recorded. All 36 NBA and 14 NFL rows matched official displayed roster names and schedule. This is roster membership/name corroboration, NOT stable official player ID resolution, official game participation, contest eligibility, or final injury/availability confirmation. No forecast edits.

New independent verification file: private archive commit d467d3edd0180ee33423f7982c747105a085a42d, research-evidence/2026-11-28/prospective-roster-schedule-verification.json, blob edf4752d2579edb2ac6cf12be326e78143869a67; readback matched written text. Source URLs, capture references and per-row results preserved; stable official IDs and game-day activity explicitly null. Original forecast archive blobs unchanged. Verify final outcomes and stable player identity independently after the games.

## Prospective error attribution
Added forward_component_attribution.py and integrated it into both existing reference evaluators. For positive matched opportunity quantities Vp, Va and explicit corresponding projected/actual production Yp, Ya, define Rp=Yp/Vp, Ra=Ya/Va. Signed opportunity effect=(Vp-Va)*(Rp+Ra)/2, signed rate effect=(Rp-Ra)*(Vp+Va)/2. Their sum is exactly Yp-Ya (up to floating-point arithmetic). Absolute component means are not additive MAE because signed errors can offset. Missing or invalid inputs and nonpositive opportunity counts are excluded, not imputed. No fitted correction, selection or policy change.

NBA: the Capper partial FD subtotal excludes blocks and is not a full FD total. Same existing matched played support with forecast and actual minutes >=10. Report opportunity and rate error attribution overall and by the frozen NBA House under-25/25+ minutes cohort.

NFL: provider-specific yardage attribution for carries, targets and catches, separate from head-to-head common support. Require positive actual and forecast opportunity and explicit same-provider yardage, with existing exact-match and final-outcome gates. Do not treat historical target/carry shares as projected opportunities or receptions as targets. Effects are in yards, not total fantasy points.

Added synthetic tests of exact decomposition and opposite-sign error cancellation, partial NBA points and NFL target-yardage attribution, and invalid/empty inputs. No actual final outcomes yet for these prospective games. New tests saved, regression not yet verified. Preserve the full 47-source registry and existing production freeze.
