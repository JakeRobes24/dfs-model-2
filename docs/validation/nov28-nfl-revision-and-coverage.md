# November 28 NFL revision integrity and salary coverage

Predecessor 6faa881f364513bc3e0d6efbed53b6210a465668 passed NBA 46142496528, NFL 46142496532, full 46142496723. Continue approved NBA/NFL accuracy audit; MLB deferred. No automatic promotion or deployment.

## Thanksgiving exact-pool coverage
Private archive f62950c8705df3afb47fc4745bcb4ed877cdd11d, manual-slates/2026-11-26/137123/postslate-user-evidence/prelock-4for4-reference.json (blob 159139939d1609ce1561c1b57206b2e7d3c1d90a) and full-pool-official-reconstruction.json (blob 34c6b00839e4cca97e46acc1110ab88043630cee). Verify both input fingerprints, unique IDs, same team, oriented matchup and position, publication <= observation <= recorded cutoff. 77 confirmed participating QB/RB/WR/TE with recorded non-OUT status; exclude DST, unknown participation and nonplay. DAILY numeric coverage and reference presence counted independently. Paired error requires exact matching DAILY value and finite source score; played-only conditional comparison, no future availability inference.

| Cohort | Played | Numeric DAILY | Archived 4for4 | Paired DAILY/4for4 MAE |
|---|---:|---:|---:|---:|
| All |77|66|14|9.1543/8.1729|
| Salary below 6000 |54|44|3|5.1333/5.3667|
| Salary 6000–7999 |15|14|4|6.2800/3.5200|
| Salary 8000+ |8|8|7|12.5200/12.0343|
| QB |6|5|5|8.2120/7.9440|
| RB |18|14|4|15.7500/12.9500|
| WR |31|29|2|4.3500/3.4000|
| TE |22|18|3|5.1333/5.3667|

All 14 archived provider rows have matching DAILY projections; none of the 11 played players lacking DAILY has this reference. Of those 11, ten cost below 6000. Four recorded nonzero actual scores (Joe Milton III 34.74, Jashaun Corbin 2.1, Salvon Ahmed 7.7, Stephen Carlson 4); the remaining seven have zero recorded points. These are postgame observations, not pregame selection evidence, and a zero actual does not imply nonparticipation. Public source coverage is very selective, not an evaluation of full provider coverage or causal proof of salary-related accuracy. All 66 matched DAILY players MAE 5.1342; reference subset DAILY MAE 9.1543. Never compare the latter provider error to the former all-player baseline as though samples match. JS calculations executed on archived records.

## Advisory NFL revision handling
nfl_projection_review.py previously treated distinct valid versions from a source as family disagreement regardless of publication order. Preserve strict identity, scoring, independence attestation and cutoff gates; reject conflicting reuse of a record ID before considering revisions. Within each normalized source and family, use only newest valid publication time with distinct record IDs, retaining earlier valid records in superseded_source_records. Simultaneous newest contradictions, disagreements across different sources in a shared family, and contradictory reused IDs remain blocked; no additional vote for a new version. Post-cutoff estimates cannot supersede a valid earlier estimate. Keep DAILY and official-status gates unchanged; this is advisory only.

Five regression cases cover permutations of legitimate revisions, shared-family affiliates, cutoff exclusion, latest simultaneous conflicts, and reused record conflicts followed by newer versions. Synthetic test fixtures, not a measured historical revision advantage. No actual new pregame source data or NBA empirical comparison in this batch. All 47 sources retained; no scoring weight changes. Latest CI pending. Next actual contest inputs and game outcomes remain necessary for full prospective validation.
