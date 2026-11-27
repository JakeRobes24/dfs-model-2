# Verified NBA tracking, NFL expected opportunity and archive recovery

Continues the verified draft at `6c36582`. This checkpoint measures new historical opportunity inputs and implements owner-only recovery of archived packet bytes.

## NBA tracking

Acquired all 122 requested official player-tracking boxes covering eight selected teams in the October 21 to November 25 schedule. Joined exact game ID, oriented clubs, official NBA player ID and counting-box minutes. Quarantined one game whose tracking team metadata disagreed with the traditional box, Denver at Indiana (November 7). The eight-team subset retained 1,276 played rows with at least ten minutes. There were 1,275 valid tracked rebound-chance observations and 1,116 rows where contested and uncontested attempts and makes reconciled to official field-goal totals. Missing or conflicting shooting classifications stayed blank.

The official tracking boxes supplied rebound chances and shot splits but no potential-assist count. The individual [NBA House player tracking](https://nbahouse.net/tracking) pages supplied 156 dated potential-assist observations from 17 players on the selected teams. All 156 agreed with the traditional box on unique normalized name, exact game orientation and date, rounded minutes, assists and rebounds. The cohort is top-passers weighted and has no reason to represent the league's assist or DNP distribution. The separate NBA Stats league passing request timed out. No authorized BALLDONTLIE tracking feed was used.

On identical consecutive played holdouts, compare the four-game outcome mean, a recency change to opportunities per minute with minutes fixed, and a conversion estimate shrunk toward the matched cohort on strictly earlier dates. The pooled conversion uses 20 opportunities of shrinkage. Equal-date errors:

| Forecast | Player-games | Dates | Four-game outcome MAE | Pooled conversion MAE | Recent opportunities MAE |
| --- | ---: | ---: | ---: | ---: | ---: |
| Rebounds | 629 | 27 | 2.032 | 1.986 | 2.133 |
| Field goals made | 314 | 26 | 1.916 | 1.863 | 2.011 |
| Assists | 44 | 19 | 1.664 | 1.722 | 1.892 |

Shrinkage improved historical rebound and field-goal conversion forecasts modestly. Reweighting recent opportunities increased error across all three channels. These are stat-count comparisons, and made field goals are not scoring-weighted points. Preserve the rebound and shooting conversion methods for prospective validation and keep the four-game assist baseline.

## NFL expected opportunity

Downloaded both documented [ffopportunity releases](https://ffopportunity.ffverse.com/) with weekly historical fantasy scoring components (CC BY-SA 4.0). Match the season, final regular-season game, team, GSIS ID and position to the existing workload history. Require exact agreement on independently reconciled attempts or targets and yardage for every prior and target row. Then compare an average of four earlier scoring outcomes, a four-game average using realized-play-conditioned expected components, and their equal blend. Use FanDuel receiving and rushing components, excluding fumbles. These tests do not use any expected target-game values to forecast scoring. Publication lag and the source model's own training history are unverified.

| Season and channel | Player-games | Actual scoring MAE | Expected components MAE | Equal blend MAE |
| --- | ---: | ---: | ---: | ---: |
| 2025 receiving | 1,826 | 4.057 | 3.907 | 3.918 |
| 2026 receiving | 857 | 4.407 | 4.163 | 4.239 |
| 2025 rushing | 728 | 4.564 | 4.279 | 4.372 |
| 2026 rushing | 290 | 4.475 | 4.403 | 4.366 |

Equal-week errors on the same player-games. The expected receiving average improved on actual scoring in both seasons. The equal blend did better for 2025 wide receivers by raw player-game MAE and rushing results were dominated by running backs. This is sufficient to keep an expected-component receiving challenger for prospective testing. It does not replace the sources for routes, pregame workload, status or original DAILY forecasts. No numerical player routes were acquired.

## Archive repair and legal roster check

The repository's NFL archive command ran on all three private parts. It independently verified the archive SHA-256 `71a020b29e51fcf53ca7e2db68e4e048981a73409c1d1546a7d6c233c237375f` and the workload member SHA-256 `255475bfa83fd49b5ee81b286fcdbc9d682590f60cf72d7ce394f946aec55dba`. The 3,412-row replay reproduced the published asymmetric-tail summary without extracting private rows into the repository.

The prior Work comparison tables are preserved in the evidence packet. The official eight-team minutes/rate replay found mean FD error of 7.581 for eight-game minutes and rate versus 8.065 for four on 355 matched targets. The NFL test fixed 2025 calibration before evaluating 2026. It covered 79.8% of rushing and 79.1% of receiving outcomes across seven weeks versus 52.2% and 47.1% for the original intervals. These are retrospective sensitivity results. The consolidated branch already has separate NBA window challengers and NFL interval calibration.

Owner-only recovery now accepts an Eastern slate date and FanDuel contest ID. It lists remote immutable versions at a pinned revision and permits download after checking both the bytes and contest metadata. This addresses a lost browser download when the packet actually reached the archive. The original November 25 submission path still returns 404. Production save/recovery and snapshot publication still need their own hosted verification. [Issue #9](https://github.com/JakeRobes24/dfs-model-2/issues/9).

Verified all four file digests in the independently retained November 25 recovery ZIP. The candidate roster CSV is byte-matched to the private repository's Git blob `5ddf5c80433107cd4fd64d85c42b300f0f296044`. Reconciled it with the original 210-player contest pool and recovered reviewed file. All four candidates have exactly nine unique IDs, correct slot eligibility including both UTILs, matching salaries within the cap, legal team composition and no recorded ineligible or OUT player. Salaries are $59,800, $59,900, $59,900 and $60,000. One player in each export was questionable in that input. The source projections agree at the export's two-decimal precision. This certifies legality against that archived input. It cannot certify actual entries, final pre-lock status, or full-lineup simulation accuracy.
