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

## Mandatory NFL research source: The Fantasy Footballers

Check https://www.thefantasyfootballers.com/ for every NFL slate, including main and single-game contests and relevant pre-lock refreshes. Consult accessible weekly rankings, matchup and start/sit analysis, injury and role/opportunity commentary, player news, public podcast recaps or transcripts, weather and accessible DFS analysis. Season-long opinions can inform player research but must be translated to the exact contest's scoring, salary, opportunity, ceiling and slate context; do not equate ordinal rankings with projected DFS points. Prioritize official availability and corroborate factual claims; distinguish analyst opinions from data and trace syndicated news to its original source to avoid false independent consensus. Use public or legitimately authorized content only, flag unavailable/paywalled coverage, never invent estimates or require a subscription. Preserve dated source URLs, relevant findings and their decision impact in pre-lock evidence when available. This is a mandatory research check, not an automatic scoring weight or a completed website integration.

## MLB 2027 preseason readiness (approved priority)

Have the MLB architecture operational and validated before the 2027 regular-season Opening Day, rather than beginning development midseason. Target milestones: November–December shared infrastructure and active NBA/NFL priorities; January MLB schema, identity, scoring and contest rule adapters; February historical ingestion and chronological backtests; spring training live pipeline rehearsal and readiness gates; Opening Day verified regular-season operation. These are planning targets, not completion guarantees.

Use legally accessible historical official results, Statcast and reputable projection sources; separate observed outcomes from contemporaneous archived forecasts and do not fabricate historical DFS salaries, eligibility, ownership or pre-lock projections. Keep spring-training workload and outcome distributions separate from regular-season calibration. Include pitcher workload, strikeouts, walks, opposing lineup, handedness, hitter plate appearances, batting order, park/weather, bullpen, postponement and confirmed lineup evidence. Reuse the shared provenance, archive, calibration, evaluation, versioning and rollback infrastructure; validate MLB rules and learned parameters independently. Before regular-season use, verify full-pool reconciliation, scoring, legal roster constraints, timestamped research, lock-aware updates, archival roundtrip and historical evaluation without leakage. Preserve ongoing NBA/NFL slate readiness while reserving time for MLB preseason preparation. Reprioritize after each slate.

## Mandatory year-round three-sport development cycle

Maintain NBA, NFL and MLB as persistent, versioned sport-specific models sharing learning and validation infrastructure. No model or historical database resets at the end of a season. In season, prioritize reliable slate execution, complete pre-lock captures, verified actuals, post-slate evaluation and evidence-driven incremental improvements. In each sport's offseason, conduct a comprehensive season review (projection accuracy, source reliability, lineup decision quality, contest outcomes and profitability where actual entry/payout data are available), chronological backtesting, calibration experiments, and larger architecture upgrades without disrupting active sports. Preserve prior seasons' evidence and model versions; account for aging data, trades, roster turnover, coaching/scheme changes, rookies, rule changes and distribution shifts. Keep sport-specific seasons, preseason samples and scoring regimes distinct. Require held-out validation and rollback safeguards before promoting changes. Prepare and rehearse each sport's pipeline before its next season, especially MLB 2027; do not wait for Opening Day or midseason. Allocate work across the annual calendar according to active slate deadlines and the rolling highest-impact backlog; reuse shared improvements without assuming cross-sport parameter transfer. Offseason learning uses available verified historical data and updated preseason evidence, not invented new game outcomes. Scheduled unattended retraining is a future capability, not currently implemented.

## Mandatory performance, risk and operational standards (approved)

These requirements apply across NBA, NFL and MLB and remain in the rolling backlog until implemented and verified. Do not silently drop them to accelerate feature development or slate execution.

- Immediate: projection accuracy, independent research reliability, explicit missing/stale/conflicting-data flags, contest legality and operational failure detection. Fail closed on invalid inputs; disclose incomplete coverage.
- High: compare each scoring policy against raw baseline projections, independently sourced forecasts and prior model versions on identical chronological held-out samples. Build guarded self-calibration and tournament evaluation. Track actual entered lineups, entry fees, payouts, placement, contest size/format and net return separately from hypothetical candidates; do not infer missing financial data or promise profitability.
- Ongoing: user-approved bankroll and exposure limits, no chasing losses or automatically increasing stakes, contest suitability evaluation using actual results and payout structures, overfitting prevention, model/source drift detection and research cost-versus-value measurement. Evaluate learning at player/role, source, strategy and contest levels, with sample-size safeguards and uncertainty disclosure.
- Longer term: scalable shared storage, reproducible efficient calculations and simulations, centralized three-sport accuracy/risk/performance dashboard, and reliable end-to-end automation with human review of material decisions.
- At each slate checkpoint and after verified outcomes, review and reorder unfinished work by expected decision-quality impact, strength of evidence, urgency and reuse across sports. Preserve readiness for the next slate and preseason commitments. No promotion without validation, no unapproved production merge, and no completion claim without evidence.

This is an operating requirement, not a claim that all capabilities exist today. Prioritize execution over further roadmap expansion; record blockers and defer lower-priority work explicitly rather than forgetting it.

## Mandatory slate checkpoints and operational safeguards

Use distinct, purposeful research checkpoints rather than repeated identical optimization: initial morning baseline (NFL may begin the prior day), major refresh approximately 90 minutes before lock (MLB approximately two hours), final optimization around 30 minutes before lock, and final injury/availability/starting-role verification approximately 15 minutes before lock. Account for actual contest deadlines, source publication timing, and solver runtime. Regenerate when material inputs change; preserve distinct dated snapshots and final candidates. After lock, respect contest-specific lock and swap rules, monitor relevant later games, and evaluate verified actuals after completion. Automated material-change alerts and scheduled refreshes are development objectives, not a claim of current unattended operation.

Across all three sports, maintain an emergency fallback to the last verified snapshot with explicit age, coverage and limitations; never present stale research as current or bypass eligibility and lock safeguards. Record exact model versions, source timestamps, input hashes, scoring settings and manual overrides with their rationale; preserve reproducibility and rollback. Verify actual user-entered FanDuel/DraftKings rosters against approved candidates when entry evidence is available, including late swaps, without assuming that candidates were entered. Compare manual decisions against model recommendations using matched pre-decision alternatives and verified outcomes, separating decision quality from variance. Maintain secure, access-controlled backups and test recovery. Complete end-to-end preseason readiness rehearsals for every sport. Track these safeguards in the rolling backlog until verified; prioritize reliability and decision impact over unnecessary features.
