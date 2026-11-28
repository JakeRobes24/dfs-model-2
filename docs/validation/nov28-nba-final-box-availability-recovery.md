# November 28 NBA-first final-box participation recovery

Prior 16574d383f9c04974046b2275c8328e25e8ff528 passed NBA 46149829991, NFL 46149829944, full 46149830003. Continue original NBA predictive roadmap, preserve all 48 sources and NFL development, MLB deferred.

## Explicit source recovery
Reopened original Nov27 full_pool_audit_v2.csv, private archive 8549d752ae253e972d09f160dfa6d5cee08be9a5, blob f9d6d72a611c6e42777a4c4f6c19bfa9f67bfc24. 244 unique contest rows; 53 previously unresolved outcomes. Inspect official NBA dated schedule and final Miami–New York scorer's report (https://statsdmz.nba.com/pdfs/20261127/20261127_MIANYK_book.pdf), parsed first-page final box, Nov27, visiting/home clubs, regulation totals 240:00 each, final 108–105. Six exact full-name DNP matches (four Miami, two New York); normalized accents only, exact original contest ID/team/oriented game, no name-only cross-team match. Source lacks stable official NBA person IDs and screenshot request failed: textual verification only, no claim of visual inspection. Exclude abbreviated inactive surnames from this supplement rather than assuming identity. Six other contest final gamebook URLs inaccessible; NBA web box snapshots sometimes still in-progress, not suitable for final labels; team-hosted box attempts and Basketball Reference blocked. Search snippets alone not used as final outcome proof. Do not infer nonplay from absent rows.

Saved separate private supplemental packet research-evidence/2026-11-28/nov27-availability-final-box-supplement.json at db097ca1b3f98d5fd7b861ca41df302e33d7f615, blob 6ddadb9613b38f51790c90299330313761dbc893, exact readback verified. Original full pool untouched. Supplement explicitly marks render_verified=false. Six DNP rows reduce full-pool unknowns from 53 to 47 if applied; three of six have positive DAILY forecasts and qualify for previous 174-row availability sensitivity; other three had missing DAILY. No new played production outcomes.

## Recomputed fixed availability evaluation
Repeat exact prior Nov24 79-row training and Nov27 174-row support, same historical probability equations and status mapping. Only change: three newly supported DNP labels. JavaScript numerical replay executed. Now 142 played, 5 nonplayed, 27 unresolved, 147 known. Remaining possible DNP fraction 5/174 to 32/174, 2.8736% to 18.3908%. These are logical completion bounds, not uncertainty estimates or confidence intervals.

| Method | Original known Brier (144) | Updated known Brier (147) |
|---|---:|---:|
| Zero-risk reference | .013889 | .034014 |
| Flat earlier prior | .024692 | .040037 |
| Minute bands | .028889 | .042712 |
| Minutes and status | .028646 | .042475 |

Joint all-pool Brier difference minutes/status minus zero-risk changes from [-.038691,+.016659] to [-.038691,+.011156]; versus flat prior from [-.009115,+.005287] to [-.009115,+.003879]. Either can still reverse ordering under remaining unknown outcomes. Do not interpret the higher known Brier as forecast deterioration: only evaluation support changed. Original archive source/status and forecast-stage limitations remain. No new estimator, no score changes, no production deployment. Continue obtaining final gamebooks and exact participation evidence where available, prioritize live current-role and production inputs when actual contest files arrive. No need to rerun the same retrospective probability formulas until new evidence is recovered.