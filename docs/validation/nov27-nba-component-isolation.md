# NBA production component isolation

Using the SHA-256 verified official-box-observations.zip (2063db41a4a8332b0fb98bd2460449744ae07203e4f9cd2caac3e5d41cea74f9), 4841 observations through November 25, an independent local Python replay reproduced both prior cohort sizes and baseline errors. Six predeclared single-component challengers replace one long-window rate with either the four-game rate or its equal blend with the long rate, retaining the same long-window minutes and other rates. Opportunity is FGA + 0.44 FTA + turnovers per minute, not official usage; efficiency is net points per opportunity; peripherals are weighted rebounds, assists, steals and blocks per minute. No tracking fields in the archive.

| Method | 8-history FD MAE | 8-history FPPM MAE | 12-history FD MAE | 12-history FPPM MAE |
| --- | ---: | ---: | ---: | ---: |
| Long baseline | 8.58417 | .25438 | 8.34562 | .24938 |
| Blend opportunity | 8.63064 | .25729 | 8.30765 | .24828 |
| Blend efficiency | 8.58663 | .25562 | 8.29639 | .24995 |
| Blend peripherals | 8.67112 | .25719 | 8.30654 | .24966 |
| Recent opportunity | 8.70178 | .26101 | 8.29430 | .24871 |
| Recent efficiency | 8.64370 | .25921 | 8.32019 | .25366 |
| Recent peripherals | 8.81184 | .26271 | 8.36813 | .25364 |
| Blend full rate | 8.70668 | .26106 | 8.20513 | .24941 |

Eight-game cohort 1164 held-out played observations over 16 dates; twelve-game cohort 322 over 8 dates, overlapping cohorts. Equal-date means. None of the single-component challengers improves larger-cohort FPPM MAE. On the smaller cohort the opportunity blend modestly improves FPPM MAE, and full-rate blend leads point MAE, but neither warrants production promotion. All results conditional on played complete observations, not full contest forecasts; no prospective holdout. Repository replay now includes the six methods; new tests assert identical support, fixed minutes, one-component changes and no target leakage. The independent local replay actually ran; repository CI pending. No private player-level rows copied, no MLB or Friday slate files.
