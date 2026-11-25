# November 24 same-provider production-rate review

Source: immutable morning capture for contest 137128, private history packet incoming-app/2026-11-24/137128/3a6167f57f3de9a02ddf9aa64620ec69236b045546a0e3ef0566259b502ad984.json. Capture 2026-11-24T11:14:51.162030Z, first scheduled tip 2026-11-25T03:00:00Z. 105 research rows and 105 recorded official box-score outcomes; 85 eligible, 70 played, 15 DNP. Read-only JS calculation mirrors the current source and rate eligibility algorithms using archived actuals, not a fresh download of official box scores or an execution of the Python module. Reject estimates after capture, older than six hours, before the latest official status/starter evidence, or with conflicting latest values. Require accepted points and minutes from the same source record and timestamp, actual and projected minutes at least ten, played outcomes only. Baselines on identical complete paired observations.

Only PropSims qualified: 48 rate forecasts, 46 with both baselines. Mean absolute FD points/minute error: all source observations 0.216363, source bias -0.033809; matched source MAE 0.214932, DAILY 0.228651, adjusted 0.228651. Relative matched rate MAE reduction 6.0%. No other provider had qualifying paired rate observations.

## Fixed reviewed minutes experiment (46 matched players)

| Rate applied to reviewed minutes | FD point MAE |
|---|---:|
| DAILY rate | 8.615307 |
| Existing reviewed projection | 8.615307 |
| PropSims rate | 8.224173 |

Absolute reduction 0.391134 FD points (4.54%). Holding minutes fixed isolates the offline impact of rate substitution; it does not establish that the provider forecast is independent of DAILY or that the substitution improves lineup selection or contest returns. The equal DAILY-rate/reviewed result shows that the selected matched subset used the same production rate in its reviewed forecast. This is one historical date and one provider, not a basis for changing live scoring. The ten-minute threshold excludes short appearances and cannot measure unconditional injury/DNP risk.

Implemented fixed-reviewed-minutes sensitivity alongside existing historical provider rate reports, with per-date and equal-date summaries. No additional archive fetch or live scoring change. New regression pending. Previous commit 4908c760398505055c1abb790089652528d3ba55 passed all four workflows (340 tests, one private history fixture deselected, 134 warnings; run 45586063933).

Next: accumulate earlier verified dates with paired independent production-rate estimates, assess stability by date and role, then evaluate a predeclared shadow blend prospectively before considering promotion. No tuning on this single retrospective sample.
