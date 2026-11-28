# November 28 rotation-confidence audit

Continues the live-performance priority at `c9f8727`. This is a read-only audit of the three archived NBA contests, with outcomes kept separate from forecast inputs. The known November 22 and Thanksgiving NFL final-projection gaps remain in the prior audit. [Five-contest live audit](nov28-live-performance-audit.md).

## Reconstructed rotations

Checked all 16 games in contests 137128, 137211 and 137257. Matched each final ESPN event by Eastern date, exact oriented clubs and score. Each complete-game rotation starts from the explicit five starters, applies ordered substitutions by athlete ID, and verifies the reconstructed minutes against the final ESPN box. A second match requires unique contest player name and club plus agreement within 1.05 seconds of the saved independent outcome time.

Thirteen play feeds passed the complete-game check. Houston–Phoenix on Nov 25, Milwaukee–Detroit and Atlanta–Boston on Nov 27 contained substitutions inconsistent with the active lineup. Their individual traces were scored only where the player's changes reconciled to both boxes. Overall 308 of 347 played contest rows verified, with results from all 16 games. Missing or inconsistent clocks are absent from the verified outcomes CSV.

| Kevin Huerter | Q1 | Q2 | Q3 | Q4 | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Nov. 24 at Orlando | 8:57 | 9:09 | 7:30 | 6:51 | 32:27 |
| Nov. 27 vs. Milwaukee | 6:16 | 4:45 | 7:53 | 4:54 | 23:48 |

Huerter started both games. His total fell 8:39 and his first-half time fell 7:05. Fourth-quarter time fell 1:57. Time on court with a fourth-quarter score margin of at least 15 fell from 4:21 to 2:35.5. The observed shortfall was already well underway before the final period. This does not establish what caused the coaching decisions or predict a recurring player-specific change. The Milwaukee game supports his individually reconciled trace. [Nov 24 event log](https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401909314) · [Nov 27 event log](https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401909327).

## Pre-tip warnings

Scored archived morning forecasts of at least 24 minutes with positive verified playing time and four earlier same-team official box entries within 21 days. Names must map to one NBA ID in that interval, with unique earlier dates. The same historical eligibility and tests also run on the available Nov 27 18:40 snapshot. The two exploratory flags used a six-minute threshold for projected expansion above the four-game mean, or a six-minute standard deviation in those prior minutes. The archived Nov 27 column named `history_sd` is fantasy-point volatility. This audit independently computes minutes volatility.

| Snapshot | Eligible | Misses of at least 6 min | Overprojections of at least 6 min | Expansion flag caught | Volatility flag caught |
| --- | ---: | ---: | ---: | ---: | ---: |
| Three mornings | 129 | 22 | 10 | 0 of 1 flags | 0 of 8 flags |
| Nov. 27 18:40 | 64 | 19 | 13 | 0 flags | 2 of 5 flags, 1 downside |

The morning flags missed all ten sizable downside events. The late volatility flag caught one of 13. Huerter's four earlier same-team boxes averaged 33.63 minutes with a 2.55-minute standard deviation. The saved late forecast was 34.44. Both flags missed his actual 23.80 minutes. The samples are conditional on playing and having exact histories. They do not measure DNP prediction or imply that each player-game was independent.

No fit met the two-earlier-date minimum for the original six-minute expansion rule. A separately labeled sensitivity lowering the gate to any positive gap had 20 training observations across Nov 24 and 25. Earlier outcomes selected zero shrinkage under bounded least squares with equal date weights. The Nov 27 morning holdout tied at 4.04 minutes MAE and 7.93 FD MAE across 70 players. Forecast production per minute was held fixed. This is a chronological historical sensitivity considered after the strict rule had sparse support.

Both tested flags remain research-only. Capture timestamped rotation and role evidence by forecast stage before testing a richer confidence rule. Use the verified substitution outcomes to separate early and late playing time instead of assigning the entire miss to final scoring margin. No change to live forecast weights, roster construction or candidate ranking.
