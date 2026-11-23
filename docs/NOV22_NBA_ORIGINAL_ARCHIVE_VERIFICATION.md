# November 22 NBA — original archive recovery and hash validation

**Recovered from user's ChatGPT Library and directly inspected (2026-11-22):**
- `Nov22_137037_provisional_prelock_freeze.zip`
- `Nov22_137037_DFS_Model_2_Development_Validation.zip`
- `Nov22_137037_four_reconstructed_scenario_lineups.csv`

## Cryptographic validation

The provisional ZIP contains the original FanDuel contest template, `DAILY(3).csv`, reconciliation v2, baseline and research scenario pools, lineup CSVs, scenario manifests, and provisional notes. **All 10 files with SHA-256 entries in `Nov22_137037_prelock_provisional_manifest.json` matched their recorded hashes** when verified directly against ZIP member bytes. This establishes internal archive integrity; it does not independently attest the 5:52–5:58 PM final message timestamp or external source validity.

Manifest `snapshot_created_utc=2026-11-22T20:05:11.355408+00:00` = **3:05:11 PM ET**. Baseline manifest created at 2:55:31 PM ET, research scenario manifest at 3:00:59 PM ET. These all precede the first scheduled 6 PM tip.

Separate development validation archive's `app_validation_manifest.json` says `captured_at_utc=2026-11-22T20:10:29.923261+00:00` = **3:10:29 PM ET**, 210 players, 180 DAILY matches, 19 eligible without usable projection, 377 research rows, 0 official starters matched at capture. This is a different model development run; its lineup projections (334.75, 333.94, 333.79, 332.84) must not be conflated with the four final presented research scenario lineups.

## Four original model scenarios, now verified against player-ID CSV

The standalone archived `Nov22_137037_four_reconstructed_scenario_lineups.csv` contains exactly **36 roster rows**, 9 per lineup, with exact FanDuel player IDs, roster slots, salary, and scenario FD projections.

| Original model lineup | Sum of nine archived individual projections | Salary | User entry |
| --- | ---: | ---: | --- |
| 1 | 336.799 | $59,800 | Entered; screenshot 387.1 |
| 2 | 336.607 | $59,800 | Not entered |
| 3 | 335.557 | $60,000 | Entered; screenshot 419.9 |
| 4 | 335.249 | $60,000 | Not entered |

All four totals reconcile to screenshot-displayed rounded values. Original model Lineup 3 (Klay Thompson and Matas Buzelis) outscored original model Lineup 1 (Mikal Bridges and Jalen Suggs) by **32.8 FD** in the user-provided contest screenshot; their original scenario forecast ordering was reversed by **1.242 FD**. Seven shared players make the direct two-player substitution comparison informative, but actual results do not by themselves establish prelock decision superiority.

## Chronology and certification

The user confirms the planned 5:40 PM check-in was late, and the four original model scenarios were **the final lineups presented approximately 5:52–5:58 PM ET before the first 6 PM scheduled game**. Only original Lineups 1 and 3 were submitted, even though the builds were considered tests. The screenshots corroborate roster and projections but lack a machine-verifiable original message timestamp.

The original archive explicitly labels itself `PROVISIONAL_NOT_CERTIFIED`, and warns of incomplete research, mutable status, incomplete independent full-pool verification, and missing lock attestation. **Final presented does not equal research-certified.** The archive contains 210 contest players, 180 DAILY matches, 30 unmatched; later development research reports 19 eligible players without usable projection. Do not treat these as equivalent denominators.

## Next validated engineering step

1. Compare each exact player-ID lineup against the frozen contest CSV, reconcile slot eligibility, and verify the archived status fields and player-specific projection provenance.
2. Obtain verified final full-pool FanDuel points from official final box scores and preserve verified DNP vs missing result. Run paired DAILY vs selected adjusted projection calibration on the exact same eligible player IDs, with no hindsight input leakage.
3. Distinguish the 3:05 research scenario and 3:10 development run from any late 5:52–5:58 source changes. Keep candidate scoring and contest entry outcomes separate; do not claim unsubmitted entries or payouts.
4. Require reproducible replay outputs, evidence audit, and tests before recommending any NBA production projection weight change.

**No production merge/deployment or model-weight adjustment performed.**

## Direct raw-file coverage and ranking audit

Reopened the original provisional ZIP's exact `Nov22_137037_research_scenario_pool.csv` and standalone `Nov22_137037_four_reconstructed_scenario_lineups.csv` (not screenshots). The frozen scenario pool has **210 distinct rows**, **180 nonblank DAILY FD projections**, **180 nonblank consensus scenario FD projections**, and **30 rows without either**. Frozen status distribution: **159 blank**, **36 O**, **10 Q**, **4 P**, **1 D**. Of 30 rows missing projections, **24 have blank status and 6 have O**. Blank status is not proof of eligibility or availability. Of 180 rows with projections, 30 were marked O at capture; model-wide coverage metrics must therefore filter the contest's status and eligibility appropriately, and cannot equate 180 projections to 180 usable entrants.

| Original lineup | Frozen DAILY FD | Frozen scenario FD | Adjustment | Salary | Archived O status in lineup |
| --- | ---: | ---: | ---: | ---: | --- |
| 1 | 337.9 | 336.799 | -1.101 | 59800 | None |
| 2 | 344.4 | 336.607 | -7.793 | 59800 | None |
| 3 | 342.4 | 335.557 | -6.843 | 60000 | None |
| 4 | 337.3 | 335.249 | -2.051 | 60000 | None |

**Ranking sensitivity:** DAILY ranks 2 > 3 > 1 > 4, while scenario ranks 1 > 2 > 3 > 4. The final presented ranking is therefore sensitive to uncertain research-adjusted minutes/projections. The observed entered outcomes (model 3 419.9, model 1 387.1) are not sufficient to conclude which methodology predicts better across the slate. Investigate each player-level adjustment with contemporaneous source evidence and paired final actuals; do not retune based solely on the two entered results.

## Exact per-player adjustment attribution (original frozen research pool)

Computed by joining all 36 original scenario lineup rows to the 210-player `Nov22_137037_research_scenario_pool.csv` using `player_id`. Only four unique players in these final four candidates had nonzero DAILY-to-research adjustments:

| Player | DAILY FD | Research FD | Delta | DAILY minutes | Research minutes | Archived evidence |
|---|---:|---:|---:|---:|---:|---|
| Nikola Jokic | 60.7 | 62.386 | +1.686 | 36 | 37 | NBA House 37 |
| Josh Giddey | 41.8 | 39.013 | -2.787 | 30 | 28 | NBA House 28 |
| Matas Buzelis | 37.9 | 32.158 | -5.742 | 33 | 28 | NBA House 29; StatIQ 27 |
| Desmond Bane | 34.2 | 33.25 | -0.950 | 36 | 35 | NBA House 35 |

All other original-lineup player projections were unchanged from DAILY in this frozen scenario; many explicitly say `No additional research; retained previous scenario`. The Buzelis adjustment appears in original Lineups 2 and 3 and accounts for **5.742 of the 6.843-point** DAILY-to-scenario reduction in original Lineup 3. Original Lineup 1 has no Buzelis and its net change is **-1.101** (Jokic +1.686 and Giddey -2.787). Therefore the projected ranking flip between entered model Lineups 1 and 3 is predominantly explained by the Buzelis minutes reduction, not broad nine-player independent consensus.

**Decision audit:** Model 3's two differential players Klay Thompson (27.2 actual) and Buzelis (36.5 actual) totaled 63.7, versus model 1's Bridges (14.1 actual) and Suggs (16.8 actual) totaling 30.9; seven shared players cancel, yielding +32.8 actual. This is an outcome comparison, not proof that prelock ceiling, minutes, or ownership inputs should be reweighted. The archived NBA House/StatIQ labels are provenance notes, not independently verified live source captures. Next replay should sweep Buzelis minutes at 27–33 while preserving all other frozen inputs and calculate ranking stability; obtain full-pool verified actuals before fitting adjustments.

## Implemented candidate-ranking robustness guard

Development-only implementation: `nba_prelock_robustness.py`, with regression test source `test_nba_prelock_robustness.py`. Given a frozen scenario pool, the exact lineup player-ID CSV, one target player, and lower/upper plausible minutes, the module validates IDs, nine-player candidate membership, finite projections, and source projection equality; it then reports both endpoint lineup rankings and pairwise crossover minutes. It intentionally does **not** optimize new lineups, assert independent research source validity, or certify news at lock. The regression tests are committed, but this commit does not assert a CI run.

**Directly recomputed from original archived CSVs:** Buzelis ID `137037-203761`, scenario 28.0 minutes / 32.158 FD. Holding all other frozen player projections fixed and linearly scaling his points per minute, the original candidate totals are:

| Buzelis minutes | L1 | L2 | L3 | L4 | Leader |
|---|---:|---:|---:|---:|---|
|27|336.799|335.459|334.409|335.249|L1|
|28|336.799|336.607|335.557|335.249|L1|
|29|336.799|337.755|336.706|335.249|L2|
|30|336.799|338.904|337.854|335.249|L2|
|31|336.799|340.053|339.002|335.249|L2|
|32|336.799|341.201|340.151|335.249|L2|
|33|336.799|342.349|341.300|335.249|L2|

The crossover L2/L1 is approximately 28.167 minutes, and L3/L1 is approximately 29.081 minutes. These are deterministic *what-if* computations, not calibrated conditional forecasts. Before integrating into the production lineup optimizer, the guard needs real CI verification and integration into the existing prelock candidate selection path, plus independent source confidence and multi-player joint scenario treatment.
