# DFS Model 2.0 — November 22 NFL historical reconciliation checkpoint

The [November 27 recovery update](validation/nov27-nfl-full-roster-recovery.md) supersedes the contest-file and saved-candidate outcome gaps below. The original player-level pre-lock export remains outstanding.

**Status:** Evidence reconciliation complete for accessible records; full-slate historical replay **BLOCKED** by missing original contest and prelock data. This is a safe pause point, not a certified retrospective optimizer result.

## Sources actually inspected

- `tests/fixtures/nov22_2026_nfl_fd_preliminary.json` — transcribed user-provided original entered lineup, salary, partial preliminary DAILY projections and actual FanDuel results.
- `tests/fixtures/nov22_2026_nfl_four_preliminary_candidates.json` — four preliminary candidate rosters and aggregate projected totals.
- ChatGPT Library `Nov22_2026_NFL_historical_challenger_fixture.json`, `Nov22_2026_NFL_audit_findings.md`, and `Nov22_2026_FD_NFL_postslate_lineup.csv` — corroborate the fixture and its provenance caveats.
- GitHub repository tree on the isolated NFL branch and `JakeRobes24/dfs-model-2-history` HEAD — inspected for historical contest/player-level data. The latter contained November 18/20 NBA checkpoints and no identified November 22 NFL contest import.
- No original FanDuel 136799 full contest CSV, complete DAILY player-level prelock export, or verified official prelock status archive was located in the inspected sources.

## Verified scope and calculations

- FanDuel contest `136799`, November 22, 2026, 10 games, salary cap **$60,000**.
- Four **preliminary** candidate lineups preserved, with aggregate projected totals **137.1, 135.9, 135.6, 135.4 FD** and salaries **$60,000, $60,000, $60,000, $59,800**. These are not certified final projections.
- Entered lineup: **nine players**, salary **$60,000**, actual **161.6 FD**, preliminary aggregate **137.1 FD**; observed difference **+24.5 FD**. Do not interpret the aggregate difference as a fully traceable player-level forecast error.
- Individual preliminary projections recovered for **3 of 9** entered players: Dak Prescott **20.8**, Emmett Johnson **19.3**, CeeDee Lamb **17.0**; sum **57.1**. Their actuals sum **91.9**.
- Remaining **6 of 9** individual preliminary projections unavailable. Their **80.0 FD** is an aggregate residual, **not** six recovered player forecasts. All nine entered-player actuals are documented, totaling **161.6**.
- Across the four candidate lineups, **16 distinct named players** can be enumerated from the archived roster list. These are **not** the full contest pool. The fixture does not provide verified contest-scoped FanDuel IDs for these players.
- Ownership, original final prelock statuses and timestamps, field/payout distributions, and final alternative-player projections remain unavailable.

## Reconciliation outcome and hard stop

| Gate | Status | Evidence |
| --- | --- | --- |
| Four preliminary candidate rosters | Recovered | Archived preliminary fixture |
| Entered lineup salary and nine actual scores | Recovered | Fixture and Library CSV |
| Entered lineup individual preliminary projections | **3/9** | Six are null |
| Exact original contest player IDs, salary/position/status for entire eligible pool | **Unavailable** | No original contest CSV found |
| Complete individually timestamped prelock projections | **Unavailable** | No complete DAILY export found |
| Independent official active/inactive source records at cutoff | **Unavailable** | No verifiable prelock source archive |
| All-contest actual FanDuel scores | **Unavailable** | Entered lineup only |
| Full-slate prelock optimization/replay | **BLOCKED** | Contest IDs and full projection coverage absent |
| Full-slate postslate calibration | **BLOCKED** | Missing full-slate actuals and matched prelock forecasts |

**Do not** run `audit_nfl_replay_coverage` on a fabricated nine- or sixteen-player contest CSV: its full-pool percentages would be misleading. The automated audit requires the authentic contest export and exact IDs. Do not infer missing individual projections from the aggregate 80.0. Do not backfill historical prelock research with post-game results.

## Engineering and validation

The isolated branch `test/nfl-nov22-historical-fixture` contains the NFL contest importer, timestamped prelock challenger, evidence-certification safeguards, and explicit historical coverage audit. The latest **64-test** GitHub Actions run at commit `ab6466fcfc5c52532b0de214e9c26bcbcbb2bdbb` passed: https://github.com/JakeRobes24/dfs-model-2/actions/runs/45108265379 .

This document is an evidence-coverage checkpoint, **not** a completed authentic historical replay. No changes to production, no merges, and no alteration of the private history database.

## Safe resume handoff

1. **NBA post-slate review:** Return to the NBA-first roadmap; use the preserved November 22 NBA prelock snapshot and official box scores, with exact player-ID joins, timestamp/cutoff discipline, verified DNP handling, and paired DAILY vs adjusted forecast comparisons. Do not confuse NFL contest 136799 with NBA contest 137037.
2. **NFL replay only if authentic missing archives become available:** Import full original FanDuel contest 136799 CSV; reconcile exact IDs and game/position/salary/status; join individually timestamped original prelock projections and verified official statuses; compute actuals across the eligible pool; run coverage audit and challenger; archive input hashes, candidate results, test outputs.
3. Preserve the four preliminary NFL candidates as descriptive baselines, not as evidence of tournament-optimality or a model improvement.

**Pause decision:** Reconciliation and blocker documentation are complete; an authentic full-slate replay cannot proceed with the available sources. Safe to pause NFL work here and switch to NBA post-slate analysis.
