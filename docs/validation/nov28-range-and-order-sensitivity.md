# November 28 chronological NBA range and order sensitivity

Prior development checkpoint 37a81f9 passed all three workflows. Recover DFS_Model_2_NBA_Multi_Slate_Roster_Calibration_Nov28.zip, SHA256 b5e38f92420186ff5f12192d1b5f83f1c35d377da8c6326dd494fbb38e4b8e41 (computed on recovery). Verify three output members against included manifest, including multi-slate.json SHA256 b484ef342288d4532e8c648c1a16d5bf53da7c655372f3932d062eaafd1b6d1e. Use dated Nov22 (3), Nov24 (3), Nov27 (24) legal, played-scope candidates; exclude Nov25 unverified capture. Same rosters, centers, outcomes and head-to-head pairs as original archive. No new simulations or reoptimization. Script range_diagnostic.py ran locally against archive; three local tests passed. Run python range_diagnostic.py <archive.zip> to reproduce. New CI pending.

## Interval scale sensitivity

Fixed width factors 1, 1.25, 1.5, 2 around unchanged median, scale both sides separately. Proper 80% interval score = width + 10 times miss distance. Select lowest equal-date earlier score (ties prefer smaller factor). Only one earlier slate for Nov24, two for Nov27: exploratory training, not reliable calibration.

| Date | Method | Earlier chosen factor | Original coverage | Scaled coverage | Original interval score | Scaled interval score |
|---|---|---:|---:|---:|---:|---:|
| Nov24 | Point residual | 2 | 33.3% | 100% | 141.84 | 172.65 |
| Nov24 | Paired minutes/rate | 1.5 | 33.3% | 100% | 137.99 | 137.12 |
| Nov27 | Point residual | 1.5 | 54.2% | 79.2% | 162.45 | 134.35 |
| Nov27 | Paired minutes/rate | 1.5 | 58.3% | 91.7% | 161.07 | 140.61 |

For Nov27 widths grow 85.17 to 127.75 and 91.83 to 137.75. No universal scaling justified: Nov24 point score deteriorates. Range coverage alone is not evidence of better predictive distributions or stronger lineup selection.

## Candidate-order discrimination

Use simulated lead share plus half tie share as pair probability; actual ties omitted. Fixed shrinkage toward 50% with raw probability weight 0, .5, 1. Earlier-date equal-weight Brier chooses weight, ties prefer less confidence. Compare raw against neutral probability Brier .25 and hard projected-score order as descriptive comparator (not probability). 281 pair observations per policy across dates; overlapping lineups and repeated players, not independent.

| Date | Non-tied pairs | Point residual raw | Paired minute-rate raw | Neutral |
|---|---:|---:|---:|---:|
| Nov22 | 3 | .25169 | .25222 | .25000 |
| Nov24 | 3 | .22573 | .22445 | .25000 |
| Nov27 | 275 | .26782 | .26662 | .25000 |

Nov24 earlier-selected weight zero for both (Brier .25). Nov27 earlier-selected weight one for both, worse than neutral on the evaluation day. Half shrink on Nov27 .25850/.25795, also worse than neutral. Hard projected ordering wrong on 66.18% of Nov27 non-tied pairs (ties handled .5), but this is a one-day overlapping sample, not a reason to invert predictions. Earlier chosen methods fail to reliably transfer; no probability or range scaling promotion. Preserve original range predictions, compare against neutral order benchmark on future dates. Separately evaluate roster centers, availability, dependence, portfolio selection, and realized best score. Do not infer contest win probability. NFL simulation/role-dependence evidence remains separately scoped; no new NFL range replay in this batch. No changes to scoring, optimizer, website, or MLB.
