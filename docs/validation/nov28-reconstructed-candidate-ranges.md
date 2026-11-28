# November 28 reconstructed NBA candidate ranges

Follows the [five-contest live audit](nov28-live-performance-audit.md) and [rotation reconciliation](nov28-rotation-evidence.md). The earlier audit identified that individual simulation quantiles were absent from the Nov 27 18:40 export. The original data and deterministic sampling settings survived.

## Recovering the original simulation

Used FanDuel contest 137257's closing report, the embedded byte-matched 18:00 checkpoint and the SHA-256-verified official observation archive. Validated exact player IDs, order, eligibility, roster size, salary and team limits. Recreated the original residual inputs using four to eight earlier same-team appearances, the archived name normalization, minute-by-rate sample construction and the original player-set iteration order. Held the archived candidate sets fixed, so no optimization rerun or outcome-driven roster construction was required. Shared draws preserve overlapping players across candidates. The archived model samples player residuals independently and conditions on playing.

Replayed 2,500 selection draws, then the original 30,000 held-out draws. Both reported portfolio summary values reproduced to stored precision, as did the choice among 232 archived portfolios and the full set of 28 candidates. The paired comparison preserves the archived requirement to include Karl-Anthony Towns in two of four entries. The historical outputs below are reconstructed from the frozen inputs, with verified actuals joined only after the receipt matched.

| November 27 four-lineup group | Original robust expected best | Reconstructed best-lineup P10 / P50 / P90 | Best realized score | Sum of realized scores |
| --- | ---: | ---: | ---: | ---: |
| Points-first, same constraint | 342.08 | 306.58 / 341.40 / 378.51 | 265.7 | 1054.3 |
| Simulation-selected, actually entered | 345.30 | 309.89 / 344.44 / 381.78 | 308.1 | 1101.7 |

The original robust expected best takes the lower expectation across the saved in and all-questionable-out scenarios. The quantiles use only the saved in scenario for comparison with realized scores. The selected portfolio gained 42.4 realized points on the best lineup and 47.4 in aggregate over points-first. Both maxima were below their own 10th percentiles. The best unentered candidate from the wider saved set scored 335.8. This single slate with heavily overlapping players leaves any selection edge, population calibration and variance cause unresolved.

| Candidate ranges | Graded | Inside P10–P90 | Below P10 | Above P90 | Mean range width | Median forecast bias |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| All saved | 28 | 15 | 13 | 0 | 76.85 | +36.79 |
| Entered | 4 | 1 | 3 | 0 | 78.20 | +48.90 |

Bias is simulated median minus actual FanDuel points. All misses went below the ranges despite the wide intervals. The sample leaves the individual effects of projection centering, uncertainty scale and correlation unresolved. Repeat on additional independently frozen slates before using ranges for live ranking or changing the model.

## Archive for the next comparison

The experimental candidate simulation now offers a timestamped JSON download. It carries exact candidate IDs, adjusted minutes and fantasy points, draw and seed settings, played-only scope, schedule timing and P10/P50/P90. It checks roster identity, ordered quantiles and agreement between the recorded means and the displayed candidate totals. A missing schedule stays marked unverified. The download itself does not certify close-time news or candidate entry. No change to optimizer scoring or simulation parameters.

The private historical search, Library and recovered November 22 NFL integration package yielded no additional final individual forecast artifact for contests 136799 or 137123. The November 22 package is explicitly preliminary. Thanksgiving retains the original DAILY and timed auxiliary records. Keep both final forecast gaps open. [Prior NFL evidence](nov28-live-performance-audit.md#nfl-scope-and-workload).
