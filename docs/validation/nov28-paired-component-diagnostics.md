# November 28 continuation: paired component source diagnostics

Base 07c67bf (all three regression workflows passed). Continue the live-performance audit without changing forecast, optimizer or simulation weights. Private evidence archive main f62950c8705df3afb47fc4745bcb4ed877cdd11d. Results below were independently calculated in JavaScript from the exact archived records; the new pure-Python diagnostic implements the same fixed formulas, with regression cases. Python full regression pending until CI completes.

## NBA: isolate independent source minutes from production rate

Nov 24 packet: incoming-app/2026-11-24/137128/3a6167f57f3de9a02ddf9aa64620ec69236b045546a0e3ef0566259b502ad984.json. Join research and actuals by exact FanDuel ID, eligible true, positive actual/reviewed/source minutes, finite FD, exactly one PropSims paired forecast observed no later than captured time and before scheduled tip. Nov 27: daily-lineups/2026-11-27/137257-full-pool/full_pool_audit_v2.csv, played statuses, positive minutes, complete paired in_min/in_fd and props_min/props_fd; exact archived 18:40 stage. Source-specific publication timestamps not independently preserved for the latter sample. Use displayed reconciled actual FD where available. 56 and 39 matched player rows, not independent contests or representative entire pools. PropSims was an input to the original review; comparisons do not establish incremental independence.

For M minutes and F points, rate=F/M. Fixed hybrids swap or average the components separately. No optimization, tuning or selection on outcomes.

| FD MAE | Nov 24 | Nov 27 |
|---|---:|---:|
| Reviewed | 8.1576 | 9.6256 |
| PropSims | 6.9568 | 9.2769 |
| Source minutes only | 7.6353 | 9.4947 |
| Source rate only | 7.5939 | 9.4257 |
| Half minutes only | 7.8426 | 9.4749 |
| Half rate only | 7.8435 | 9.4798 |
| Half both | 7.4921 | 9.3269 |

Minutes MAE reviewed/source: Nov 24 4.0605/3.5507, Nov 27 3.9331/3.9175. Rate MAE (FD/min) reviewed/source: Nov 24 .25265/.23338, Nov 27 .23059/.22295. Both components improved on each paired sample, but the Nov 27 minutes gain was almost nil. Equal date mean FD MAE 8.8916 reviewed, 8.1169 source, 8.4095 half both. On Nov 24 six players had >=6-minute disagreement, minutes MAE 9.315/6.1739; Nov 27 zero such rows. For 3–<6-minute disagreement Nov 24 n=3 (6.2078/4.6011), Nov 27 n=2 (5.1049/1.8917). Small descriptive groups, no threshold or weight promotion. All policies evaluated on the same rows. These are fixed retrospective hypotheses, not held-out confirmation. Keep free-source capture and source timing; next prospective slates must grade paired rates, minutes, exact player identity and conditional availability independently.

## NFL: 4for4 Thanksgiving component check

Use manual-slates/2026-11-26/137123/postslate-user-evidence/prelock-4for4-reference.json and full-pool-official-reconstruction.json. Match exact ID, oriented game/team, played status, published <= observed <= 17:30 UTC cutoff. 14 matched players, 74 component pairs with explicit gamebook tuple entries. Gamebook pass tuples are attempts/completions/yards/TD/interceptions; do not misread completion as yards. Rush attempts/yards/TD; receiving targets/catches/yards/TD. Source lacks targets, so do not treat receptions as targets. Missing component tuples stay unknown.

| Component | n | MAE | Signed bias (forecast minus actual) |
|---|---:|---:|---:|
| Pass attempts | 5 | 6.22 | +1.62 |
| Passing yards | 5 | 69.12 | +11.96 |
| Passing TD | 5 | 0.92 | +0.92 |
| Interceptions | 5 | 0.72 | -0.20 |
| Rush attempts | 9 | 4.02 | -2.11 |
| Rush yards | 9 | 22.50 | -13.99 |
| Rush TD | 9 | 0.66 | -0.41 |
| Receptions | 9 | 0.80 | +0.42 |
| Receiving yards | 9 | 17.46 | +1.26 |
| Receiving TD | 9 | 0.48 | +0.17 |

Positive-volume yardage-only FD midpoint decomposition, mean absolute component contributions (not additive MAE): passing n=5 volume 1.82, rate 1.91; rushing n=9 volume 1.82, rate 2.34; receiving n=9 catches 0.71, yards/catch 1.20. Passing factor .04, rush/receive .1; no TDs, catches points, bonuses or turnovers in this attribution. James Cook projected 16.8 carries and 94.5 yards vs actual 32 and 117; opposing volume (-7.05 FD) and rate (+4.80 FD) errors offset. Gibbs projected 20.3 carries/96.1 yards vs 21/205, mainly conversion error. This extends the earlier DAILY-only workload decomposition, not a matched DAILY component comparison. One slate, public provider subset, no generalization or automatic weight changes. The Loveland injury remains an outcome observation, not a pre-lock signal.

## Decision and next gates

Retain source components as research-only diagnostic; no promotion. Need prospective identical-sample evaluation, earlier source timestamps, more NFL workload/target forecasts and calibrated rate distributions. Keep free legitimate access including public portions of paid providers; no purchase required. Do not invent missing forecasts or replace existing research sources. Preserve rolling priorities and production freeze. Code and tests are offline utilities, no runtime wiring. 
