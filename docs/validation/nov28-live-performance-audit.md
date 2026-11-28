# November 28 live-performance audit

The November 28 rolling priority governs this replay. It uses development parent `62e3a059` and archive head `f62950c8`. Five contest pools supply 1,213 original IDs. Three NBA slates support played-player DAILY versus morning comparisons, and two NFL slates support narrower live evidence. Forecast stage, attribution scope and missing outcomes are preserved. This is a historical diagnostic with no live scoring or portfolio-policy changes.

## Forecast evidence

| NBA contest | Played paired rows | DAILY MAE | Morning review MAE | Late evidence |
| --- | ---: | ---: | ---: | --- |
| Nov 24, 137128 | 70 | 8.53 | 7.39 | 18:30 candidates, entry status and full final forecast unavailable |
| Nov 25, 137211 | 120 | 8.85 | 7.28 | Evening export covers candidate rosters, one entered roster differs |
| Nov 27, 137257 | 142 | 8.73 | 7.43 | 18:40 adjusted MAE 7.44, all four archived model rosters match entries |

Each comparison uses the same exact IDs, played outcomes and available forecasts. Morning means the saved pretip review on Nov 24, recovered morning production export on Nov 25, and the initial archived preliminary review on Nov 27. The Nov 27 post-slate archive's separate morning scenario scored 7.428 on the same 142 IDs. These stages and model versions differ. The replay shows the historical review workflow improved on DAILY across three slates. It does not isolate whether a specific new development change improved live performance.

The combined independent forecast on the overlapping Nov 24 (56 players) and Nov 25 (37) samples scored 6.93 and 7.44 MAE, versus morning 8.16 and 7.79. The combined field can mix providers and the recovered Nov 25 source timing is incomplete. On Nov 27, timed source columns each use their own common comparison sample.

| Nov 27 source sample | Players | DAILY | Initial morning | 18:40 adjusted | Source |
| --- | ---: | ---: | ---: | ---: | ---: |
| PropSims | 39 | 11.64 | 9.32 | 9.63 | 9.28 |
| Daily Fantasy Fuel | 21 | 14.39 | 9.39 | 10.05 | 9.12 |

The source cohorts differ, so their column values cannot rank the providers directly. All outcomes known only by missing played-box listings stay null in the strict Nov 27 comparison. The audit preserves the six known display-versus-box differences. Using box-only outcomes on the played sample kept the main result materially unchanged (final MAE 7.44).

## Optimizer selection, role and concentration

Bias is forecast minus actual in FanDuel points. Selections use the Nov 24 saved morning candidates, Nov 25 entered model rosters against the morning forecast, and Nov 27 entered model rosters against 18:40 estimates. These are different decision checkpoints.

| NBA date | Selected / unselected matched players | Selected bias | Unselected bias | Exposure-weighted selected bias | Same-salary-and-forecast comparison |
| --- | ---: | ---: | ---: | ---: | --- |
| Nov 24 morning | 15 / 55 | +2.35 | -0.93 | +5.88 | -3.29, 7 selected players |
| Nov 25 morning | 14 / 106 | -2.00 | -2.19 | -3.28 | +3.55, 12 selected players |
| Nov 27 adjusted | 17 / 125 | +4.42 | -0.25 | +5.57 | -1.77, 9 selected players |

The adjusted comparison uses same-slate $1,000 salary and five-point forecast bands, comparing each selected player with the average nonselected error in that band. It controls two obvious differences without claiming a causal effect or independent observations. The direction changes across dates and sometimes reverses within those comparable bands. There is no support for a blanket selected-player reduction.

Across the common 141 played records with positive minutes at both Nov 27 stages, the late review reduced minutes MAE from 5.05 to 4.62 and FD RMSE from 9.82 to 9.74. FD MAE moved from 7.37 to 7.40. The 17 selected players averaged a +3.34 minute miss at 18:40. Their average signed FD contributions were +3.23 from minutes and +1.19 from rate. Mean absolute contributions (5.35 and 5.86) can offset each other and do not add to total MAE.

For Kevin Huerter, the Nov 24 morning forecast was 28.14 FD in 30.83 minutes against 29.70 FD in 32.45 minutes (four morning rosters). On Nov 27, it was 28.52 in 34.44 minutes against 17.90 in 23.80 minutes (three model entries). About 8.41 of the 10.62-point miss came from minutes and 2.22 from per-minute production. The independent box reconstruction credited 14.90, which leaves the minutes contribution larger than the rate contribution. These two observations support reviewing rotation confidence, not a player-specific adjustment. Final margins were 18 and 15 points. Final margin is an outcome-only grouping. On Nov 27 18:40 minute MAE was 5.22 in games ending at least 15 points apart versus 4.08 otherwise. This cannot determine when a game became noncompetitive or how rotations redistributed usage. Verified substitution stints, past role signals and contemporaneous projections for those opportunities are needed to test those mechanisms.

## Lineup and ceiling comparisons

- Nov 24's saved 18:30 candidates reached 299.4 at best versus 286.1 for the archived morning rosters. Original entry matching is incomplete.
- Nov 25's four original morning rosters reconstructed to 352.5, 350.8, 347.1 and 371.5. Actual model entries scored 341.0, 330.9, 322.8 and 321.0. Only three evening-export rosters matched an entered roster exactly. Four players were shared by all four entered rosters.
- Nov 27's original preliminary rosters scored 298.8, 297.7, 291.5 and 284.8 using verified outcomes. The four 18:40 model entries scored 308.1, 264.2, 263.7 and 265.7. The best revised entry beat the best preliminary roster, while the preliminary four had a higher average. Three players were shared across all four entries and pairwise overlap averaged 5.17. All 28 saved candidate records had full strict outcomes after the full-pool review. The best unentered saved candidate scored 335.8 (27.7 above the highest entered model lineup). This is observed opportunity cost, not a forecastable ordering or a reason to force diversity.
- The Nov 27 saved simulation compared 232 portfolios with 30,000 draws and reported selected versus point-first summaries. The archive has no per-candidate forecast quantiles sufficient for lineup calibration. PropSims' published ceiling was exceeded on four of 39 matched played rows. The exact percentile meaning needs independent confirmation before treating that as calibration. Ten user-supplied high-finisher screenshots contain seven distinct rosters. Their exposure does not establish field ownership.

## NFL scope and workload

Nov 22 contest 136799 has 501 original IDs and 16 supported outcome identities from four saved rosters. The entered roster scored 161.6 versus a preliminary 137.1 aggregate. Only three entered player-level DAILY estimates survive. Their mean signed error was -11.60 and they cannot identify a recurring selected-player bias.

Thanksgiving contest 137123 has 153 original IDs, 83 played or D/ST records, and 72 eligible with DAILY forecasts in the strict comparison. The entered nine scored 117.42. Their DAILY mean error was -2.10 (MAE 6.28) versus -0.46 (MAE 4.71) for 63 other eligible played or D/ST rows. The paired 14-player 4for4 sample improved from 9.15 DAILY MAE to 8.17. This is the archived prelock capture. The post-slate publication remains excluded. No final adjusted full pool or ceiling archive was recovered for either NFL slate. The separate Nov 25 NFL single-game settlement is preserved in the historical repo, with no verified prelock forecasts for comparison.

The Thanksgiving original DAILY attempts and targets link by contest ID to final gamebook components. For 42 positive-workload receiving rows, the mean absolute contributions were 2.08 FD from targets and 3.07 from receiving production per target. For 12 positive-workload rushing rows they were 3.23 from carries and 4.65 from output per carry. Among seven entered receivers, the magnitude was 3.63 from targets and 3.20 from rate. Subtotals exclude yardage bonuses, fumbles and conversions so the workload-times-rate identity holds. Zero workload, missing components and other event types are outside this conditional comparison.

## Chronological correction and evidence priorities

Fit a bounded two-input blend between DAILY and the saved morning forecast using the 190 paired played results from Nov 24 and 25, with equal date weights. Test on the 142 Nov 27 played matches. The fit reached 100% morning review, so the challenger exactly tied the incumbent at 7.43 MAE. No score change is supported. This is a post-slate replay of a fixed rule across heterogeneous historical checkpoints, not a prospective trial.

1. Recover and preserve more exact close-time NBA and NFL full-pool forecasts, revisions, entered rosters and timestamped simulation quantiles. Candidate and entered IDs are necessary to distinguish scoring misses from execution.
2. Compare a confidence-aware minutes challenger with the incumbent on untouched future slates. Score production rate separately, report comparable salary cells, and retain role and availability uncertainty.
3. Gate rotation and blowout-effect studies on dated pregame role evidence and verified substitutions. Do not learn a live adjustment from final margins alone. Preserve the public SumerSports workflow as advisory context. [SumerSports validation](nov28-sumersports-reference.md).

The code supplies exact join guards, paired bias/MAE/RMSE, selection strata, workload attribution, archived roster scoring and the chronological blend. The evidence archive retains the normalized data, source SHA-256 inventory and replay recipe. The inherited SumerSports registry test exposed a missing access URL. The registry now links directly to the verified public receiving board. [Rolling roadmap](../ROLLING_SLATE_READINESS.md).
