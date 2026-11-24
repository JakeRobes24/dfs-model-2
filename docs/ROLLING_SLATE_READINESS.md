# Rolling slate readiness and development priorities

## Operating standard

Develop, test, validate, freeze the scoring policy, execute the normal full-pool slate workflow, evaluate actuals, and reprioritize. Do not promote a new forecast merely because it yields different lineups or higher projected totals. Complete live availability and role checks near lock; never describe an earlier snapshot as final. Keep missing evidence visible. Preserve original and final verified snapshots and compare actual outcomes on identical samples. Production merges remain approval-gated.

## November 24 checkpoint (NBA contest 137128)

- Hosted archive submission and backup publication observed. Four pre-tip candidates and 105 contest rows preserved; manifest reports 668 historical research rows.
- Fragility audit rounding correction passed three regression workflows.
- Independent re-solve of the uploaded reviewed export: 105 rows, 20 ineligible, 79 usable, six eligible without defensible DAILY scores. All four saved candidate player sets reproduced; all four solves certified optimal under sequential max-overlap-seven constraints.
- Missing rows: NBA House expects no rotation for three Denver players and Felix Okpara, and 2/4 minutes for Anthony Gill/Devin Carter. These are source estimates, not official absences. Do not assign invented scores. Individual forced-roster tests require roughly 20.61–20.80 FD points to equal the best reviewed candidate, conditional on other scores fixed and one missing player introduced at a time. Revisit on news.
- Experimental 60/40 blend of reviewed total and independent total, without scaling points a second time, supported 20 players in the saved morning snapshot. At least two agreeing independent point sources and a paired minutes estimate within two minutes of reviewed consensus required. Experimental alternate optimization retained candidate sets 1 and 3 and changed sets 2 and 4. Leading roster remained unchanged. This is sensitivity evidence only; no demonstrated accuracy advantage.
- Keep established live scoring for this slate. Experimental policy must remain separate; compare verified post-slate actuals on common supported played-player rows. Do not treat missing actual results as zero.
- User-authenticated staging read/write and published backup verified; production unchanged. Recheck current hosted model, independent source coverage, lineup legality and all news before final entry.

## Prioritized work queue

1. Slate critical: refresh authoritative injury, starting-role, minutes and opportunity evidence, especially uncertain or missing players; full pool and legal alternatives, final lock verification, preserve final pre-tip snapshot.
2. Post-slate: retrieve verified final box scores, compare original versus final forecasts and candidate decisions, evaluate experimental combined scoring using archived evidence; record remaining coverage gaps.
3. Improve minutes/rate model and provider calibration only with prospective paired evidence. Investigate source timestamps, role changes, missing scoring and uncertainty; retain conservative fallback.
4. Tournament candidate selection, ownership and dependence validation; do not promote untested policies.
5. Reduce manual uploads, improve lock-aware workflow and archive reliability; then extend NFL integration using its own contest rules and evidence.

Review priorities after every slate. This checkpoint is not a final injury check, proof of a tournament edge, or deployment approval.

## Approved three-sport architecture

The long-term goal is one shared self-calibrating DFS platform for NBA, NFL and MLB, not three independent infrastructure implementations.

- Reuse contest reconciliation interfaces, source provenance, versioned immutable pre-lock captures, verified outcome ingestion, paired error measurement, chronological validation, calibration registries, promotion gates, rollback and audit tooling.
- Keep scoring rules, player identity, opportunity features, eligibility, roster constraints, uncertainty, game correlation and tournament objectives sport- and contest-specific. Do not pool incomparable raw errors or transfer learned weights across sports without separate validation.
- Begin with NBA, then extend NFL, then MLB as the shared foundation becomes reliable. NBA need not be perfect before extension.
- Use prospective, chronological held-out evaluation with adequate samples, compare against the current policy on matched observations, and retain the incumbent if improvement is unsupported. Automatic recalibration is a development goal, not a currently validated capability. Preserve model versions and rollback; do not silently promote experiments.
- Prioritize work by likely decision-quality impact, strength of evidence, and reuse across sports. Freeze stable scoring before each slate and resume development after verified outcomes, without delaying normal pre-lock checks.
