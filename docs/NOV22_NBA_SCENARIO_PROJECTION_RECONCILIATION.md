# November 22 NBA — recovered scenario vs entered lineup retrospective

**Source:** ChatGPT Library `Nov22_137037_research_scenario_pool.csv` (210 player rows, 24 fields). Matched exact player names to the two user-provided FanDuel screenshots preserved in `docs/NOV22_NBA_TWO_ENTERED_LINEUPS_SCREENSHOT_AUDIT.md`. The scenario file is an archived research scenario, **not independently certified as the final frozen pre-lock submission**. No user results have been inserted into this scenario's original projections.

## Nine-player salary and projection comparison

| | Entered lineup 1 | Entered lineup 2 |
| --- | ---: | ---: |
| Exact player-name matches in archived scenario | 9/9 | 9/9 |
| Distinct rostered players | 9 | 9 |
| Archived salaries | $60,000 | $59,800 |
| Archived DAILY FD points | 342.4 | 337.9 |
| Archived `model_fd` | 342.4 | 337.9 |
| Archived `consensus_scenario_fd` | 335.557 | 336.799 |
| Screenshot FD points | 419.9 | 387.1 |
| Screenshot actual minus DAILY | +77.5 | +49.2 |
| Screenshot actual minus scenario | +84.343 | +50.301 |

The archived model_fd values are identical to DAILY for these eighteen lineup appearances. The scenario columns represent an alternate research what-if, not proven final model weights. Screenshot results were taken with BOS–GS at fourth-quarter 0:00; verify official final settlement before certifying errors.

### Direct substitution test

Seven players were shared. Only two differed:
- Lineup 1: Klay Thompson (DAILY **25.3**, scenario **25.3**, screenshot **27.2**) and Matas Buzelis (DAILY **37.9**, scenario **32.158**, screenshot **36.5**). Combined DAILY **63.2**, scenario **57.458**, actual **63.7**.
- Lineup 2: Mikal Bridges (DAILY **26.4**, scenario **26.4**, screenshot **14.1**) and Jalen Suggs (DAILY **32.3**, scenario **32.3**, screenshot **16.8**). Combined DAILY **58.7**, scenario **58.7**, actual **30.9**.
- DAILY favored lineup 1 by **4.5**; scenario favored lineup 2 by **1.242**; screenshot result favored lineup 1 by **32.8**.
- Buzelis scenario expected minutes **28** vs DAILY **33**, with independent research evidence text `NBA House 29; StatIQ 27`. The scenario reduction was **5.742 FD points**, flipping the ranking. We must verify the observation times, independence, actual minutes, and whether the late status/role changed before treating this as a calibration lesson.
- Giddey scenario **39.013** vs DAILY **41.8** affects both lineups equally, so it cannot explain their ranking difference.

### Important controls

1. Scenario pool contains **210** rows, not necessarily a fully verified final eligible player population; verify exact contest ID, original contest CSV hashes, player IDs, status and salary before certifying legality beyond the displayed salaries and slot patterns.
2. These two screenshot rosters are confirmed user-entered; the other two proposed builds were **not submitted**. Do not fabricate their contest placements or scores.
3. This is **not** a full-slate paired MAE study; only two lineups and their overlapping nine-player subsets are available from screenshots. Repeated players are not independent observations.
4. Do not claim the `consensus_scenario_fd` column was the live optimizer's selected projection. No production weight adjustment is justified by these results alone.
5. The original screenshot scores and provisional contest ranks/prizes require final verification. Original full-pool actual results and the immutable pre-tip capture should be recovered before comprehensive calibration.
6. Once the official final NBA box scores are joined, compare DAILY, actual selected adjusted projections, and alternative scenario on **the same unique eligible player IDs**, and assess role/minutes deviations and uncertainty. Preserve original snapshot hashes and source timestamps.

## Follow-up

- Check saved pre-tip `137037` capture for exact `replay_captured_at_utc`, original FanDuel IDs, eligible statuses, DAILY hashes, model version, and selected projection.
- Use the existing `run_frozen_replay.py` only with a valid complete saved pre-tip pool and verified final boxes; never substitute the scenario CSV for its required replay fields.
- Compare the full pool and investigate Buzelis minutes assumption and Bridges/Suggs downside, with an explicit distinction between prelock decision quality and realized variance.

**No production merge, weight change, or database mutation.**

## Additional recovered pre-tip archive evidence (project index)

The saved `DFS_Model_2_Project_Index.md` contains a November 22 **3:10 p.m. ET** development validation entry for contest **137037**, linking an archived full pool/source audit/script/manifest at [development validation archive](https://chatgpt.com/library?file_id=libfile_e3e86fe52b4081918ff022eedb9096a8&account_id=personal). Its recorded scope: **210 contest IDs**, **six games**, **180 DAILY point matches**, **19 eligible players lacking usable point projections**, **377 reviewed source rows**, **31 rotation boxes**, **15 public ownership estimates**, and **zero officially confirmed starters matched at capture**. The index says all **66 tests passed** for that earlier development revision. These are historical project-index statements, **not a new execution or verification of the archive's raw contents**.

The index separately documents a **3:17 p.m. ET** research alias check with 155 independent projection matches and a preserved 210-player pool, and later development work on the frozen replay runner. The 3:10 capture is pre-tip, but **not independently certified as the final lineup version recalled by the user at approximately 5:58 p.m. ET**. The user corrected the approximate lineup discussion time from 6:58 p.m. to **5:58 p.m. ET**, two minutes before the first scheduled 6 p.m. game. This makes a full-slate pre-tip candidate comparison plausible, but the original message timestamp and immutable projection version still need verification.

The user's subsequently provided original four-lineup screenshots establish the model scenario rankings **336.8, 336.6, 335.6, 335.3 FD**. Original **model Lineup 1** is the entered **387.1** result, while original **model Lineup 3** is the entered **419.9** result. These are descriptive scenario comparisons, not certified full-pool GPP simulation results.

**Next evidence action:** retrieve the linked archive bytes, verify manifest/hashes and capture times against the exact source files, compare the 3:10 frozen pool to the approximately 5:58 p.m. model-scenario candidates, and use official final boxes for complete-slate actuals only after provenance validation. The project index and screenshots do not authorize inventing the missing 19 player forecasts or asserting full-slate prelock certification.
