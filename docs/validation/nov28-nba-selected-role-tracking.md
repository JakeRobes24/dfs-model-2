# November 28 NBA-first opportunity and role evidence

Predecessor 0f1c2925b77f6ccf2f058aade95cac51cfa8267e: NBA 46145576548, NFL 46145576494, full 46145576435 all passed. Continue NBA-first development before today's exact contest inputs arrive.

## Actual data acquired

Six selected players from earlier large minutes-disagreement research; latest four visible played traditional logs and matched same-page tracking rows, manually transcribed from https://nbahouse.net/tristan-da-silva, /dominick-barlow, /nic-claxton, /zach-collins, /kentavious-caldwell-pope, /jordan-hawkins. Claxton, Collins, Hawkins CHI; Barlow and Caldwell-Pope PHI; da Silva ORL. Private archive a7060850fbbce805e583cba02079c58e4d15a7c5, research-evidence/2026-11-28/prospective-nba/selected-role-tracking-coverage.json, blob 7849193b3221c98157714fb30f029efd25519aae, exact readback verified. 24 counting rows, 22 tracking rows; two missing most recent tracking rows (Barlow and Caldwell-Pope Nov27); three disagree on counted rebounds and have missing rebound chances (da Silva, Claxton, Collins Nov20); Collins also has four assists against two potential assists; Hawkins has a four-minute prior appearance. 18 complete under joint screen of >=10 rounded minutes, counting agreement, nonmissing rebound chances, assists <= potential assists. No player has four fully supported rows under this joint screen. Per-channel independent official identity/game reconciliation and consecutive team-game schedule still required. No pooled conversion forecast authorized by this limited capture.

## Numerical description, not scoring changes

FD = PTS +1.2 REB +1.5 AST +3 STL +3 BLK -TO. Pooled recent four-game rate uses rounded displayed minutes; stocks share is observed weighted steals/blocks divided by FD. Opportunity proxy FGA+.44 FTA+TO, not official usage. Leave-one-game-out rate range is sample sensitivity, not prediction interval. Earlier discussion's House/Capper minutes differences are not newly verified live estimates; FD spread = absolute difference multiplied by four-game historical rate, illustrative only.

| Player | Min total | FD/min | Opp/min | Net pts/opp | Stocks share | Leave-one-out range | Illustrative minutes FD spread |
|---|---:|---:|---:|---:|---:|---:|---:|
| da Silva |111|.588|.350|1.286|0%|.532–.633|3.77|
| Barlow |61|1.498|.481|1.296|26.3%|1.309–1.644|10.34|
| Claxton |103|.891|.356|.983|32.7%|.846–.918|9.98|
| Collins |62|.865|.355|.773|33.6%|.643–1.031|8.21|
| Caldwell-Pope |101|.490|.218|1.091|18.2%|.463–.520|5.10|
| Hawkins |57|.860|.489|1.220|0%|.662–.937|6.62|

Small selected historical samples, no new contest eligibility, salaries or independent official confirmation. Barlow's observed non-stock rate 1.105, Claxton .600, Collins .574; do not simply remove steals/blocks from future projections, or infer a rate will persist. Earlier tested conversion policies remain unchanged. Actual calculated numerical evidence helps prioritize targeted research rather than fit new weights on the same retrospective cohorts.

## Data-acquisition correction

Existing nba_house_potential_assists parser required numeric rebound chances even though that field was discarded. This unnecessarily rejected otherwise usable potential-assist records. Require exactly the four fields actually used: minutes, assists, potential assists and counting rebounds. Preserve independent official cross-check of rounded minutes, assists, rebounds and oriented game; preserve >=10 minutes and assists <= potential. Real example: Hawkins Nov8 has 17 min, 1 assist, 2 potential assists, 0 rebounds, missing rebound chances; same-page traditional log agrees on minutes/assists/rebounds. It is outside the latest-four sample and not independently verified yet; now can enter the existing official matching gate rather than being dropped at parse time. Do not relax identity/cross-count or chronological requirements. Regression tests saved, latest CI pending. No claim of added validated observations without official join. No production deployment, scoring promotion, new NFL work or MLB. Preserve all 48 sources.