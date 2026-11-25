# Live research acquisition benchmark — November 25, 2026

GitHub Actions run 45582846344, commit 54b6a482b998a8c108c484c4219f1f69e1ba83b4. Official slate schedule: 9 games, common decision cutoff 04:10:58 ET. Sequential and concurrent paths called the same three uncached public loaders in that order.

| Batch | Sequential (s) | Concurrent (s) |
|---|---:|---:|
| Official and independent projections | 1.188 | 1.784 |
| Recent official rotations | 4.939 | 2.689 |
| Reference boards | 0.619 | 1.153 |
| Total wall time | 6.746 | 2.689 |

Reduction 60.1%. Equal aggregate coverage and provider status strings: 476 notes, 91 independent projection rows, 830 historical player rows, 38/38 final boxes, 7/7 schedule days, 202 MatchWiz rows. The comparison did not hash individual row content. NBA injury report 69 entries, RotoWire 105 minutes/zero confirmed starters, DFF 25 points, PropSims 60 points/minutes, RotoGrinders 6 pre-tip estimates, NBA House 236 minutes. LineupExperts, FantasySportsEdge, Fantasy Team Advisors, KeelStats unavailable from this runner. Not full contest reconciliation, not hosted UI timing, not a provider accuracy result. Sequential-first order may favor the second pass; repeat with reversed ordering before generalizing.

At benchmark commit all four workflows passed; 333 tests, one private historical fixture deselected, 134 warnings.

## Next implementation

Recent final box retrieval is the longest measured batch. Added opt-in bounded 512-entry 30-minute public final-box cache keyed by exact day/game/away/home, with copy isolation, expiry and no caching empty or one-sided results. Dated official schedule checks remain in place, and cache only accepts the expected teams and date. Normal and extended UI rotation windows share the cache. The cache does not certify complete official statistics or avoid corrections beyond its TTL; existing outer Streamlit rotation TTL remains 30 minutes. New tests and live cache timing verification still required. No scoring or production change.


## Reverse-order and final-box reuse check

Run 45583600402, cutoff November 25 04:15:26 ET. Concurrent first: 4.609s; sequential second: 3.857s. Both retrieved 476 notes, 91 point projections, 830 historical rows and 202 MatchWiz records. Exact rotation rows equal. Provider status strings differed because DFF reported a newer update during the sequential pass; aggregate row counts are equal, not evidence of identical live numerical forecasts. The two runs do not establish a guaranteed concurrency speed gain.

In the same workflow, uncached final-box load took 2.087s and the immediate warm-cache load 0.470s (77.5% lower elapsed time). Both returned 830 identical rows and all 38 final boxes across seven dated schedule pages; warm pass reused 38 boxes. This is a runner-local immediate-repeat test, not a hosted UI timing or evidence of unchanged boxes throughout the TTL.

At commit 050e031e8a99e1f14ad23bc06f0fe641124f61a0 all four workflows succeeded, with 337 passed, one deselected, 134 warnings. New production-rate diagnostics are separately pending verification.
