# November 27 group dependence challengers

NBA: independently reconstructed the existing eight-game historical forecast equations from SHA-256-verified official archive 2063db41a4a8332b0fb98bd2460449744ae07203e4f9cd2caac3e5d41cea74f9, producing 1,164 forecast rows. Ran the new group comparison locally. Strictly earlier dates fit minute-band residual scale and shrunk teammate/opponent standardized cross-products; covariance matrices are repaired toward identity when needed. Identical mean, marginal scale and held-out players for each method. Two highest forecast-minute players per side in the already observed played cohort; no actual-performance ranking. Normal total CRPS is analytic. Equal-date averages after warmup.

| Group | Dates | Groups | Independent CRPS | Dependence CRPS | Independent interval score | Dependence interval score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Four same-game players | 9 | 65 | 15.87501 | 15.87883 | 103.47011 | 103.55024 |
| Two teammates | 9 | 130 | 10.18298 | 10.18334 | 67.37024 | 67.39140 |

Coverage unchanged at 68.22% and 78.35%, respectively. No improvement from this learned dependence challenger. Group observations overlap; not nine-player legal lineup or prospective accuracy evidence. Keep independent reference; no claim that real teammate dependence is zero.

NFL: independent JavaScript numerical replay of existing historical yardage evidence, Git blob e154aeb2a85acc88489be72187503297fee8cb11. New optional method mixes equal probability mass from paired and independent draws while preserving marginal distributions and total mean.

| Team | Metric | Holdouts | Paired CRPS | Independent CRPS | Half-mixed CRPS |
| --- | --- | ---: | ---: | ---: | ---: |
| LAR | Rush | 5 | 44.73750 | 40.24844 | 42.00430 |
| LAR | Receive | 5 | 19.66250 | 17.50938 | 18.36016 |
| DET | Rush | 13 | 42.51923 | 38.98678 | 40.31701 |
| DET | Receive | 10 | 25.48750 | 23.70000 | 24.36875 |
| CHI | Rush | 11 | 44.71591 | 43.90270 | 43.62979 |
| CHI | Receive | 2 | 9.28125 | 8.19531 | 8.63477 |

Independent wins five of six small cohorts; mixed slightly wins Chicago rushing. No scoring promotion. Archive replay integration and regression tests submitted. Future research should validate real archived legal rosters, availability and position-specific opportunity dependencies. No Friday inputs or MLB changes.
