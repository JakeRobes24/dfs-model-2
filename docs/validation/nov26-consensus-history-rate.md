# Nov26 independent minutes + historical rate factorial review

Archive: private history packet `incoming-app/2026-11-24/137128/3a6167f57f3de9a02ddf9aa64620ec69236b045546a0e3ef0566259b502ad984.json`, blob `97ad8103cee5606f1074cd18bfcdb964e2d592b3`. Read all 105 research and 105 outcome rows; joined exact contest IDs. Independent arithmetic over the archived rows, not new provider retrieval. Require verified played outcomes (at least ten minutes), positive reviewed score, supported historical role/recent rate, two distinct fresh minute families, no pre-confirmation team estimates, six-minute maximum provider spread, and projected minutes 10–48. Historical rate shrinkage unchanged (240-minute prior, max 40% weight). Evaluate time-only, rate-only and combined on identical players.

| Forecast | Common players | FD MAE | Signed bias |
|---|---:|---:|---:|
| DAILY | 33 | 11.06061 | -7.96364 |
| Reviewed | 33 | 9.24518 | -1.30563 |
| Consensus minutes with reviewed rate | 33 | 8.41239 | -0.47283 |
| Historical rate with reviewed minutes | 33 | 8.81445 | -1.20314 |
| Consensus minutes with historical rate | 33 | 7.98235 | -0.37104 |

Reviewed minute MAE 4.32232, consensus 3.53843. Combined improved 20 of 33 player absolute errors versus reviewed; time-only improved five, historical rate alone sixteen (ties not improvements). Combined lowered matched MAE 13.66%. Single earlier slate, chosen policy declared after outcomes: exploratory. Provider acquisition and archive timestamps unchanged. No new source claims. The module constructs candidates without actuals, and the multi-slate review labels Nov26 and earlier as exploratory. Future dates require the existing full-slate chronology gate. Seven synthetic regression methods verify mechanics and leakage guards; direct Python reproduction against the private packet remains to be checked. No production promotion. The six-minute spread is an uncalibrated diagnostic gate.
