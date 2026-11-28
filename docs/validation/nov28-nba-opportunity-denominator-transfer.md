# November 28 NBA-first component and tracked denominator comparison

Previous checkpoint 55590bd530aad1165bee8b06ed71cf561412e99e passed NBA 46146470971, NFL 46146470927 and full regression 46146470920.

## Preserve rebound skill in component pooling
On the prior exact 769-row history-only component replay (see nov28-nba-component-pooling.md), combine net scoring, assists and stocks pooling while retaining personal rebound production. This is a post-review sensitivity, not a new independent holdout. Equal-date FD MAE baseline/all-four/no-rebound-pooling:

- All 769, 14 dates: 8.764184 / 8.389837 / 8.398473; no-rebound version improves 13 of 14 dates.
- Earlier 416, eight dates: 8.605046 / 8.346099 / 8.286053; no-rebound improves seven dates.
- Later 353, six dates: 8.976368 / 8.448154 / 8.548366; no-rebound improves six dates.
- Later under-25-minute 138, six dates: 7.436200 / 6.701451 / 7.087290; no-rebound improves four dates.

Retain no-rebound variant for further comparison without selecting the largest aggregate apparent gain; channel correctness matters. No production score adjustment.

## Later tracked chance comparison
Recovered the previously used library archive DFS_Model_2_Tracked_Opportunity_Validation.zip, SHA-256 ff64f55a7b2fbf4bb86c31babb76947265e2f0f0b849542bf0c917ca2cd09fc2. nba-tracking-joined.csv and nba-tracking-schedule.json: 1276 matched rows, 34 dates, 122 scheduled games. Restore leading zeros in numeric CSV game IDs before exact schedule join; no unmatched rows or duplicate player-game IDs. Require 10–60 minutes and counted outcome <= recorded chances <=70, four preceding consecutive observed team schedule entries, strictly earlier dates, at least four personal prior chances and 20 earlier cohort chances. Same tracked support across all forecasts, equal-date MAE. Compare personal four-game mean, fixed 100-minute raw-rate pooling and fixed 20-chance conversion pooling. No target opportunities in prediction. No new fit. Subsequent-date slice Nov18–25 occurs after the earlier rotation archive cutoff; this is a different later sample but not pristine (previously studied tracking archive).

| Channel/cohort | N/dates | Personal | Raw rate pool | Chance conversion pool |
|---|---:|---:|---:|---:|
| Rebounds all |629/27|2.032414|2.120041|1.985877|
| Rebounds Nov18 onward |179/8|2.015013|2.028927|1.957776|
| Rebounds later under 25 minutes |69/8|1.691584|1.568317|1.560454|
| Assists all |44/19|1.663952|1.655292|1.721569|
| Assists Nov18 onward |17/6|1.932870|1.945454|1.974027|

Tracked rebound conversion improved 20/27 dates and six of eight later dates. Raw rebound pooling worsened overall and later rebound count accuracy; low-minute cohort improved by either method. Assist coverage remains very limited and later raw pooling and chance conversion both worse than personal baseline. Counts, not FD points. Preserve tracked conversion challenger, keep assist baseline for this sample; do not transfer this to opaque total forecasts. Local Python replay executed directly on the archive, results retained in working evidence. Reusable compare_raw_and_tracked_pooling helper and synthetic regression saved. Latest CI pending; no production deployment or new scoring weights. All 48 sources retained, NFL development deferred, NBA first.
