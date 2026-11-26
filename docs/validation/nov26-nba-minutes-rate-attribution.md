# NBA provider minutes and scoring-rate comparison

The NBA evaluation now compares five forecasts on the same played players with complete minutes, point forecasts and official outcome provenance. The forecasts are DAILY, reviewed, provider minutes with reviewed scoring rate, reviewed minutes with provider scoring rate, and the provider's original minutes and rate. A paired source forecast must have points and minutes in the same record. All comparisons require at least ten actual and forecast minutes. Report mean absolute minutes, fantasy points per minute and fantasy-point error, alongside signed bias and player-level improvement counts. Give each date equal weight within the same provider.

| Evidence | Matched players | DAILY FD MAE | Reviewed FD MAE | Replace minutes | Replace rate | Replace both |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Nov 24 verified pre-tip contest 137128 | 46 | 10.38 | 8.62 | 7.74 | 8.22 | 7.24 |
| Nov 25 retrospective morning export, contest 137211 | 37 | 12.45 | 7.79 | 7.91 | 7.97 | 7.47 |

PropSims is the sole qualifying provider on these matched samples. November 24 starts with 48 already-accepted paired source forecasts. The common sample retains 46 after applying complete positive baseline point and minutes requirements. The exact archived packet has SHA-256 `3a6167f57f3de9a02ddf9aa64620ec69236b045546a0e3ef0566259b502ad984` and Git blob `97ad8103cee5606f1074cd18bfcdb964e2d592b3`. Outcomes were joined by exact IDs using the existing reconciled official box-score fixture.

November 25 uses the preserved morning export and the verified six-game outcome file, joined by contest player ID, team and game. The historical audit's assumed 6:36:42 a.m. ET cutoff was reused to select timestamped paired provider evidence. The export lacks a certified capture, so it is descriptive only and stays outside the strict replay and calibration sample.

Replacing scoring rate alone improved November 24 point MAE by 0.39 and worsened November 25 point MAE by 0.18. Its scoring rate was closer to actual scoring rate on both dates. Fantasy-point error may move differently when combined with an inaccurate minutes estimate. The archived sample supports collecting same-provider minutes and points together and comparing the components prospectively. It gives no basis for adding a production scoring weight. The new table is part of the existing historical evaluation and requires no extra provider request.
