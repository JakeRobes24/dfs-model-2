# November 28 NBA component and roster validation

The component accuracy regression failed during test collection. A trailing quote after the 64-character DAILY fingerprint in the fixture caused a syntax error. Removing it restored the existing tests, including the checks for partial component totals, genuine zeros, timing and short appearances.

## First outcome comparison for the saved Drop Coverage preview

The November 27 capture preserved 25 Brooklyn–Toronto players before tip, with minutes and all six FanDuel components. The provider's latest run was 12:17 a.m. ET, the observation was 3:26 a.m. ET, and the game started at 7:30 p.m. ET. All 25 matched unique original FanDuel contest IDs. The final ESPN box independently corroborated the scoring arithmetic for all 22 verified played rows. Three players had unknown outcomes in the contest audit. Three of the six players forecast for zero minutes played. The test retains those misses. One played row lacked a complete DAILY comparison. The reviewed estimates are from the 6:40 p.m. ET checkpoint and had access to later news.

| Mean absolute error | Matched players | Drop Coverage | DAILY | Late review |
| --- | ---: | ---: | ---: | ---: |
| Minutes | 21 | 6.02 | 6.65 | 4.82 |
| FanDuel points | 21 | 8.91 | 9.21 | 8.54 |
| Minutes, salary below $5,000 | 14 | 6.80 | 5.38 | 4.93 |
| FanDuel points, salary below $5,000 | 14 | 8.37 | 6.38 | 7.15 |

Across all 21 matches the source beat DAILY for points (4.44 versus 5.13 MAE), assists (1.34 versus 1.45) and turnovers (0.78 versus 0.85). DAILY led on rebounds (1.91 versus 2.29), steals (0.81 versus 0.82) and blocks (0.49 versus 0.50). In the 14 lower-salary matches, DAILY led on scoring points and rebounds, while the source led on assists and turnovers.

On the 16 matches meeting the established minutes criteria, six-component production-rate MAE was 0.227 FD/min for the source and 0.253 for DAILY. The nine qualifying lower-salary players were nearly tied at 0.265 and 0.268. Multiplying both rates by the same late reviewed minutes produced lower-salary errors of 8.11 and 8.14 FD points. The rate sample excludes short and zero-minute forecasts. Displayed DAILY FD and the six-component subtotal can differ slightly through rounding.

## Fixed historical roster check

Checked the 28 previously saved candidate sets against the original contest, including exact slots, salary and team composition. Each had two to five players from the preview. Replacing only their late projected scores with their early Drop Coverage values increased mean absolute lineup error from 38.73 to 43.79 FD. The other roster spots retained the archived late forecasts. Candidate sets overlap and share the same preview game. This measures the effect on saved roster totals. It cannot establish a change in ceiling, correlation or optimal exposure.

Keep the provider as an advisory source. This adds a previously unscored source-outcome pairing on a historical game already used in the project. One selective preview game and different forecast times limit transfer to later slates. The evidence supports keeping rate comparisons and role checks separate, especially for cheaper players.

## Reproduction

From the repository root, run `PYTHONPATH=. python scripts/replay_nov27_drop_coverage.py` with the four archived inputs in this order.

1. `DFS_Model_2_NFL_Roster_Recovery_and_Timed_References.zip`, which contains the original NBA preview, raw responses and schedule.
2. `NBA_137257_1840_checkpoint.zip`, which contains the original contest and DAILY exports and saved candidates.
3. `espn-401909329.json`, the final game box from the November 28 rotation audit.
4. `full_pool_audit_v2.csv` for contest 137257, which contains seconds-based minutes and reconciled FanDuel outcomes.

The command verifies all four SHA-256 digests and the underlying preview response digests. The experiment uses the same matched-component evaluator as the staging accuracy panel. Original production archive receipt verification remains tracked in issue 9.
