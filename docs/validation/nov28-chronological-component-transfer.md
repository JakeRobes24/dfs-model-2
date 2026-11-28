# November 28 chronological component transfer
Previous 74cfcbb: full regression 46134916965, NBA 46134916970, NFL 46134916986 succeeded. New offline research on restored original evidence ZIPs. The tracked-opportunity archive SHA-256 is ff64f55a7b2fbf4bb86c31babb76947265e2f0f0b849542bf0c917ca2cd09fc2 (computed on recovery; not an independently authenticated upstream manifest). Shooting-and-route archive SHA-256 83d73f04d82ecb914583c40e454fef90f64d3e4ecb7a9a1ea5bdb36a2764c0a4; all six member SHA-256 values in its included manifest verified. No private player rows copied to code repository.

Fit on earlier archived predictions only, fixed weight grid 0/.25/.5/.75/1, equal-date/week MAE, ties less change; evaluation strictly later. Minimum 40 training rows NBA, 100 NFL, four dates/weeks. Identical complete identities and outcomes required across all policies. These are new retrospective chronological splits on previously studied datasets, not pristine or prospective holdouts; no claims of performance against complete current live model. Python replay actually executed, three local tests passed. New full CI pending. Reproduce using run_temporal_component_transfer.py --archive-dir pointing to the two named original ZIPs.

## NBA tracking: train through Nov14, test Nov15 onward
| Component | Training/test rows | Earlier-selected pooled conversion weight | Later baseline / selected MAE |
|---|---:|---:|---:|
| Rebounds | 383/246 | 1 | 2.0404 / 1.9904 |
| Field goals made | 186/128 | 1 | 1.8361 / 1.7686 |
| Assists | 14/30 | insufficient | not fitted |
Fixed comparison of recent opportunity rate: rebounds earlier-selected .25 gives 2.0454, made shots earlier-selected 0 gives 1.8361. Recent opportunities plus pooled conversion earlier-selected .25 gives 2.0304 rebounds and 1.8319 made shots. Separate challenger fits, not a post-outcome winner selection. Retain pooled conversion for prospective shadow evaluation. Counts are not full FD outcomes. Potential-assist acquisition still thin. Earlier and later rows inherit source coverage and same-team historical lookback restrictions of the tracked-opportunity archive.

## NFL 2025 -> 2026
| Channel | Train/test rows | Earlier-selected expected scoring weight | Later baseline / selected MAE |
|---|---:|---:|---:|
| Receiving all | 1826/857 | .75 | 4.4074 / 4.1869 |
| Receiving RB | 559/223 | 1 | 3.1019 / 2.8409 |
| Receiving WR | 856/402 | .75 | 5.1243 / 4.9403 |
| Receiving TE | 411/232 | 1 | 4.4741 / 4.1210 |
| Rushing all | 728/290 | 1 | 4.4754 / 4.4032 |
| Rushing RB | 662/268 | 1 | 4.7633 / 4.6755 |
Rushing WR 57/21 and TE 9/1 insufficient. Pooled vs position comparisons overlap; no aggregation as independent tests. Entire 2025 regular season may extend into Jan 2026 but precedes 2026 season holdouts. Expected source publication/training chronology still unverified, conditioning on played games, prior scoring components only, not direct live workload projections. ffopportunity attribution: https://ffopportunity.ffverse.com/ CC BY-SA 4.0. Receiving includes catches, yards, TDs, conversions, excludes bonuses and fumbles. Rushing includes yards, TDs, conversions, excludes bonuses and fumbles. No new weights in production.

## NFL route blend weeks 5–8 -> weeks 9–11
| Target cohort | Train/test rows | Earlier-selected route weight | Later baseline/selected target MAE |
|---|---:|---:|---:|
| All | 442/309 | .25 | 2.1310/2.1266 |
| RB | 104/72 | 0 | 1.7498/1.7498 |
| WR | 218/141 | .5 | 2.3940/2.3691 |
| TE | 120/96 | .25 | 2.0770/2.0741 |
Fitting on receiving FD rather than targets selected zero route weight for every cohort. Later all-player receiving FD MAE 3.9932 unchanged (full route alternative 3.9747, not earlier-selected). Route counts sourced from archived RotoWire recaps and identity/workload reconciliation; archived source timestamp gates retained. Routes useful as role evidence; no proven point-forecast improvement from the route blend.

Next: prospective frozen paired component predictions and role-aware uncertainty, independent source component coverage, validated participation and candidate ranges. Keep incumbent and archive challengers separately. No production promotion, model weight, portfolio selection, UI or MLB changes.
