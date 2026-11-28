# November 28 matched provider component and coverage review

Previous c9b3039 verified NFL 46138801540, NBA 46138801560, full 46138801546 successful. Extend earlier paired-component audit; no source-weight change or new live scoring. Use only original archive data, no new public boards claimed. JS and local Python numerical comparisons executed.

## Archive and timing
Private history 8549d752ae253e972d09f160dfa6d5cee08be9a5. Nov24 137128 packets 3a6167f57f3de9a02ddf9aa64620ec69236b045546a0e3ef0566259b502ad984 and 6dbd4f73ea88976a39046e89e4679749ea902186c23a5629d225002ed11ac7be have byte-identical research_csv, so count once. First has actuals. Capture 11:14:51 UTC Nov24, archived cutoff 03:00 UTC Nov25; explicit before-full-slate-tip flag, do not reinterpret cutoff as earliest game time. Use positive verified NBA box minutes and eligible rows, exact contest IDs, valid source URL/family, exactly one provider record, six-hour observation window, exclude forecasts predating latest recorded official team news (five team/game keys with official news). This is a conservative retrospective observation-time filter, not proof of publication or incorporation of news. After-hours packet 137139 cbf58f7964a885564b2a1c7dc7cef470513d0c7922b41841cef37335f23f7fa7 has 70 rows but no independent provider fields/timed capture; do not count overlapping games as another independent day.

Nov25: recovered DFS-2026-11-25-137211-morning-recovery.zip, verify all four file digests against manifest. reviewed_pool(2).csv SHA256 ea3b8c7808336670aa65701deda27a095692fefea08496ff6a6698b5b0f143a2. Join 210 original pool rows to exact contest IDs in digest-verified Live Performance Audit Nov28 normalized CSV; require same team, game, eligible and played official box result. Provider URLs/families as above, exactly one per player; no verified full-slate timestamp or original complete independent minutes notes. 130 matched eligible played; 37 paired PropSims, 10 DFF. Sensitivity only, not a certified timed source comparison.

Nov27: full_pool_audit_v2.csv in 137257-full-pool, use 18:40 reviewed in_fd/in_min and props_fd/props_min, house_min,dff_fd. Strict played_box, status at 17:15 blank/P/A (exclude Q even if eventually played); 143 rows. No player-level timestamp provenance to confirm each board met freshness/news conditions. Sensitivity, not a new timed replay. No inferred zeros.

## Common support (same players per row)
All numbers MAE, smaller better. Separate comparison groups; n varies, do not compare scores across different supports.

| Date | N | DAILY minutes | Reviewed minutes | PropSims minutes | NBA House minutes | Equal Props/House |
|---|---:|---:|---:|---:|---:|---:|
| Nov24 |55|7.6480|4.0753|3.5473|3.9200|3.6290|
| Nov25 recovered |37|11.0423|4.9851|2.7295|unavailable|unavailable|
| Nov27 recovered |38|8.8732|3.8842|3.9496|4.0978|3.9031|

Nov24 bias DAILY/reviewed/Props/House -5.8659/-1.1459/+.5553/-1.3303. Nov25 -11.0423/-4.3110/-.7110; Nov27 -8.8638/+.5248/+1.1110/-.1311. Equal Props/House isn't best on either of the two matched dates. PropSims remains promising, not independently additive (already an input to reviewed forecasts).

| Date | N | DAILY FPPM | Reviewed FPPM | PropSims FPPM |
|---|---:|---:|---:|---:|
| Nov24 |46|.228651|.228651|.214932|
| Nov25 recovered |37|.242548|.242548|.224929|
| Nov27 recovered |38|.249658|.234351|.227746|

All four minute denominators (actual, DAILY, reviewed, provider) >=10. Identical DAILY/reviewed rate on first two dates reflects original model's preserved baseline rate in these rows. Point forecasts and minutes from same provider; never divide DFF points by another provider's minutes and call it DFF production rate.

| Date | N | DAILY FD | Reviewed FD | PropSims FD | DFF FD | Equal Props/DFF |
|---|---:|---:|---:|---:|---:|---:|
| Nov24 |4|8.8250|15.2237|12.7250|12.0000|12.3625|
| Nov25 recovered |10|15.4000|6.6827|7.3380|7.2800|7.2290|
| Nov27 recovered |20|14.5300|10.2872|10.1250|9.5700|9.5375|

Only 34 common point records across three dates, 4 in conservative timed group; do not rank providers from tiny selective cohorts, or fit weight on these dates. Nov24 played eligible coverage Props56, DFF4, House65 after news filter; Nov25 Props37/DFF10; Nov27 Props38/DFF20/House137. Missing provider evidence stays missing. Repeated players/date dependence, heterogeneous capture stages and conditional played sample. Earlier PropSims comparison had different inclusion rules (including some questionable players); counts are not interchangeable.

## Decision
No global source weights or scoring change. Continue separately recording minutes, production rate, points, opportunity components, same-source paired rates, explicit publication/observation and latest team news timestamps. Add common-support report helper with timing strata and duplicate contest checks; tests submitted, full CI pending. Preserve exposure challenge as additional operational requirement, not research replacement. NFL earlier component work remains active; this batch adds NBA provider comparison only, no new NFL results. Next priority: prospective current-slate capture and broader NFL source coverage, not another retrospective fit on same small samples. No MLB development.
