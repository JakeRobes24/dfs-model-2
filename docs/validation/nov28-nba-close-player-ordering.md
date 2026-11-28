# November 28 NBA-first close-player ordering and value audit

Predecessor 3e2a708637c10090f813d4bc1cecc2f8999f5ee7 passed NBA 46148308634, NFL 46148308569 and full regression 46148308572. Continue NBA predictive development, retain NFL work and all 48 research sources, defer MLB.

## Numerical test on archived live-forecast challengers
Exact private archive 8549d752ae253e972d09f160dfa6d5cee08be9a5, research-evidence/2026-11-28/live-component-transfer/strict_history_shadow_results.csv, blob f7581828072c417d543d7b53baabc3e754731592. 196 unique date/contest-player rows, history end strictly earlier than target date, complete finite forecasts and actuals. Original frozen/reconstructed history limitations remain: actual-playing support and earlier incomplete schedule acquisition, three reused dates, no new prospective receipt, Nov25 original timestamp unverified. Use the existing fixed four/eight-game 20% policies; no new fit. For each date form raw actual non-tied pairs, anchor closeness to incumbent projected FD difference <=5 or <=2. Score correct ranking as 1, tied prediction within 1e-8 as .5. Rank top ten by each forecast with deterministic ID tie break; evaluate actual mean and overlap with actual top ten on matched support only. No salary or positional constraints in this first comparison.

| Policy | Equal-date all-pair correct | Anchor gap <=5 | Anchor gap <=2 | Actual top-ten selection mean FD |
|---|---:|---:|---:|---:|
| DAILY |70.86%|53.10%|49.77%|41.8733|
| Reviewed |73.38%|57.72%|51.19%|42.5900|
| Four-game rate |74.11%|60.34%|56.79%|43.2933|
| Eight-game rate |74.08%|60.24%|57.47%|43.5867|
| Eight-game minutes |73.30%|57.38%|50.39%|43.5900|
| Eight-game both |74.07%|60.25%|57.17%|43.5867|

Pair counts by date Nov24/25/27: all 665/2410/3911, <=5 171/751/1245, <=2 66/336/502. Eight-game rate improves close <=2 ordering on every date (53.03->65.15%, 48.36->52.68%, 52.19->54.58%). Top-ten actual mean reviewed->eight-rate by date 44.20->43.65, 41.16->40.71, 42.41->46.40; aggregate gain driven by one date. Actual top-ten hits 7/4/6 reviewed versus 6/4/7 eight-rate; identical overall hits. Top raw scoring is not lineup value. Pairwise results depend on shared players, forecasts and games, no independent pair significance test.

## Salary sensitivity
Join exact contest IDs, incumbent point/minute fields agree within 1e-7 and positive salaries from Nov24 research_csv in incoming-app/2026-11-24/137128/3a6167f57f3de9a02ddf9aa64620ec69236b045546a0e3ef0566259b502ad984.json (blob 97ad8103cee5606f1074cd18bfcdb964e2d592b3) and Nov27 daily-lineups/2026-11-27/137257-full-pool/full_pool_audit_v2.csv (blob f9d6d72a611c6e42777a4c4f6c19bfa9f67bfc24). 37/89 matched exact rows, all verified against prior incumbent. Nov25 salary not recovered in this batch; exclude date from salary comparisons, not raw ranks.

| Date | Same-price (within $500) / also anchor <=5 pairs | Reviewed close same-price | Eight-rate | Combined |
|---|---:|---:|---:|---:|
| Nov24 |126/80|60.00%|67.50%|68.75%|
| Nov27 |909/697|54.52%|55.52%|55.09%|

All same-price pairs reviewed->eight-rate 58.73->63.49%, 56.11->56.88%. DAILY close same-price 50.63%,57.96% respectively; on Nov27 both incumbent and challengers trail DAILY. FD/$1000 ranking (same raw non-tied pair support; value ties half credit) reviewed->eight-rate 51.73->54.44%,54.49->53.67%. Top ten forecast FD/$1000 actual average reviewed/eight-rate unchanged 4.8041 on Nov24 and 4.2223 on Nov27; DAILY 4.6365/5.2052. These are matched played-support descriptive comparisons, not the entire slate, and similarly priced players may lack interchangeable roster positions. No optimizer re-run, no claim of GPP improvement, no price-only selection recommendation.

## Implementation and decision
New nba_player_choice_audit.py and three synthetic regressions record common-support ordering, fixed anchor-gap cohorts, same-price comparisons, top-k realized output and salary-value diagnostics; missing salary disables salary comparison for that date rather than guessing; duplicate identities and missing forecasts rejected. JavaScript archive calculations actually executed; new Python regression pending. This is a complementary evaluation target, not a new forecast model. Retain validated incumbent, compare existing history challengers on genuine prospective captures, include both numerical accuracy and candidate/portfolio outcomes in evaluation. No automatic scoring changes or new website features. All 48 sources remain, NFL development paused, MLB deferred.