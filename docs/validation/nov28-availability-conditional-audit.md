# November 28 availability and conditional-outcome audit

Predecessor bac89453: NFL 46134659855, NBA 46134659866, full 46134659851 all succeeded. Read-only live-performance continuation. Archive main f62950c8705df3afb47fc4745bcb4ed877cdd11d. Use exact IDs in Nov24 original app packet 3a6167f57f3de9a02ddf9aa64620ec69236b045546a0e3ef0566259b502ad984.json, Nov27 137257-full-pool/full_pool_audit_v2.csv, Thanksgiving 137123/postslate-user-evidence/full-pool-official-reconstruction.json. JS replay calculated results independently; Python helper is committed for subsequent use, CI not yet verified.

## NBA: availability error versus production error

Nov24 105 pool: 70 played, 35 explicitly confirmed did not play. Nov27 244: 147 played, 44 explicitly out, 53 absent from played tables remain unknown for strict scoring. Nov24 morning and Nov27 18:40 snapshots differ. For identical complete forecast rows:

| Date / outcome | N | DAILY MAE | Reviewed MAE |
|---|---:|---:|---:|
| Nov24 played | 70 | 8.527 | 7.386 |
| Nov24 confirmed nonplay | 23 | 10.543 | 4.311 |
| Nov24 both | 93 | 9.026 | 6.625 |
| Nov27 played | 142 | 8.735 | 7.439 |
| Nov27 confirmed nonplay | 38 | 15.995 | 1.281 |
| Nov27 both | 180 | 10.267 | 6.139 |

The raw positive point forecast mass on confirmed nonparticipants fell from 242.50 to 99.15 (Nov24), and 607.80 to 48.69 (Nov27). The nonplay share of total absolute improvement on common rows was 143.35/223.23 (64.2%) and 559.11/743.13 (75.2%), respectively. Thus much of the unconditional gain is availability review, not better played-player production forecasting. Keep both metrics in future audits. This is not a profitability or causal claim.

Nov24 remaining positive reviewed forecasts on confirmed DNPs: nine, two >=10 (Cade Cunningham 48.50 with P label, Julian Strawther 13.8 blank). Nov27 two (Kyrie Irving 34.66 and Isaiah Stewart 14.03, both Q at 17:15). They are scenario-conditional reviewed in forecasts, not certified final playable picks. No inference that the status at the snapshot was wrong. Nov27 19 positive forecasts totalling 96.95 on unknown outcomes, not counted as errors. Four played players with zero reviewed FD: Tacko Fall 4.2 actual, Chaney Johnson 12.4, Jericho Sims 0, Tim Hardaway 4.5. Zero score does not mean did not play. Small late-rotation omissions are distinct from production misses. Nov27 Q status 4 played/2 confirmed out; Nov24 Q 1 played. Do not estimate a reliable Q participation probability from these small stage-dependent samples. Nov27 doubtful and 16 out-labeled rows absent from tables are unknown for strict outcome grading.

## NFL: availability scope

Thanksgiving original pool 153: 77 played skill players, 16 explicit inactive/DNP, 54 not listed in gamebook (unknown), six team units (exclude from player availability). Exact matched DAILY: 66 played MAE 5.134, 15 explicit nonplay MAE 2.220, combined 81 MAE 4.595. No final adjusted forecasts recovered. Five confirmed nonplayers had positive DAILY total 33.30; Kenneth Walker III 18.1 (Q) and Tanner McKee 13.1 (blank) were the only >=10. Five Q rows: two played/three confirmed nonplay. Four positive forecasts on unknown outcomes total 7.5. Nine played zero-projection rows include nonzero actual Elijah Moore 7.2, Tyler Conklin 1.4, Camden Brown 2.4. Do not count IR rows absent from gamebook as independently verified inactive outcomes. No NFL adjusted accuracy or probability calibration claim.

## Next steps

Capture status and eligibility timestamps, confirmed inactives, each scenario-specific forecast, actual participation independent of FD score, unknowns, and exact entered roster identity. Preserve conditional and unconditional calibration separately; do not convert positive projections into participation probabilities or treat Q/D/P labels as numeric probabilities without chronological validation. Test uncertainty and status updates on future untouched dates. No live scoring, lineup ranking, source weighting or website changes. NBA and NFL remain active; MLB deferred.
