# November 28 repeated-player portfolio opportunity cost
User-approved operational refinement: repetition across entries must be strongly supported by numerical evidence, not by optimizer reuse alone. Avoid unnecessarily closing alternative paths when comparable legal rosters exist. Equally, do not force diversity, use blanket exposure caps, blacklist players or sacrifice a clear edge merely for different names. Applies to NBA and NFL, all multi-entry workflows. Existing user-requested entry budget and contest constraints remain authoritative. Single-entry contests do not have portfolio exposure. No live optimizer or scoring change.

## Independent saved-candidate replay
Predecessor f1ca290 passed all three regression workflows. Private history 8549d752ae253e972d09f160dfa6d5cee08be9a5. Read Nov27 137257-full-pool/candidate_audit.csv and full_pool_audit_v2.csv, and 137257-post-slate-entries-audit.json. 28 previously reviewed legal candidate sets. Resolve every player name to unique contest ID; confirm nine unique players, frozen status in blank/P/A, salary <=60000 and sum of in_fd equals every saved projected total (including kat-out candidate labels: the archived audit totals are already rebased). Use prior certified legality, not new positional certification from name-only CSV. Enumerate distinct four-player-set portfolios from these candidates with exactly two Towns entries as originally requested. 6,885 portfolios; 232 within four aggregate projected FD points of the mean leader, the original archived selection guardrail, not a new universal tolerance. Select frontier and individual exposure alternatives using only frozen totals/identities, join archived realized scores for retrospective illustration afterward. Independent JavaScript calculations executed; Python helper is new and CI pending.

| Portfolio | Total projected | Loss vs mean leader | All-four shared | Distinct | Avg pair overlap | Best actual |
|---|---:|---:|---:|---:|---:|---:|
| Mean leader | 1306.0593 | 0 | 4 | 14 | 6.33 | 265.7 |
| Actually entered | 1302.2014 | 3.8580 | 3 | 17 | 5.17 | 308.1 |
| Best mean with <=3 shared | 1304.1968 | 1.8625 | 3 | 16 | 5.50 | 264.2 |
| Best mean with <=2 shared | 1302.8861 | 3.1732 | 2 | 16 | 5.17 | 310.9 |
| Best mean with <=1 shared | 1300.9883 | 5.0710 | 1 | 16 | 4.83 | 310.9 |

No zero-core portfolio in saved candidate universe. The <=2-shared portfolio retained Daniss Jenkins and Day'Ron Sharpe, candidates in_fd_True_3/new0_1/new0_Scottie Barnes/new1_0. It had +.6847 aggregate projected FD vs actually entered, one fewer all-four player, but fewer distinct players and the same average overlap. Lowest mean pair overlap among 232 near-leaders: 5.0 shared, two all-four players, 17 distinct, total 1302.7242, best actual 310.9 (in_fd_True_3/new0_1/new0_Scottie Barnes/new1_1). Retrospective examples only: not proof of superior simulated ceilings, scenario robustness or tournament results. Original simulation-selected method beat points-first on this date. Do not replace simulation selection with simple mean/core ranking.

## Individual challenge of actual entered exposure
Alternative is highest mean among all saved feasible portfolios with strictly less exposure to named player; all other exposures may change. Cost is relative to highest mean portfolio, not a one-for-one swap or actual entered score. This shows the limitation of the candidate search, not the player's true marginal value.

| Player | Actual portfolio count | Aggregate mean cost vs highest mean | Cost per entry |
|---|---:|---:|---:|
| Daniss Jenkins | 4 | 8.0663 | 2.0166 |
| Day'Ron Sharpe | 4 | 1.7358 | .4340 |
| Jaden McDaniels | 4 | .9402 | .2350 |
| Kevin Huerter | 3 | 3.0785 | .7696 |
| Tyrese Maxey | 3 | 3.8782 | .9695 |
| Isaiah Joe | 3 | .7795 | .1949 |

These are disparate opportunity costs. Jenkins had greater numerical support within the saved mean-forecast candidate universe than the other all-four players. This does not establish that his actual projection was correct, or that repetition of any player was optimal under simulation uncertainty. The existing candidate pool may miss strong alternatives; generate verified alternatives outside shared cores before judging the result. A lower count of all-entry players alone is not a sufficient objective.

## Mandatory prospective review
Before finalizing a multi-entry portfolio, record all player counts, all-entry core, pair overlap, distinct players, and shared game/team downside. Challenge repeated players, prioritizing those across all or most entries, using the full eligible pool and exact contest legality. Retain strongest original candidates. Compare feasible equal-budget alternatives on the same frozen projections and common player simulation draws: projected mean cost, uncertainty sensitivity, best-entry distribution, role/source agreement and adverse news scenarios. When a near-equivalent alternative improves opportunity coverage without giving up a meaningful evidence-backed edge, prefer it; if evidence is insufficient or candidate search incomplete, say so. Keep concentrated exposure when the numerical advantage is strong, and record why. No fixed numerical loss threshold or arbitrary cap added to production. Re-evaluate after material news. Use existing NBA core-expansion and stress comparison research paths where applicable; generic new mean diagnostic supplements rather than replaces these. NFL full-roster simulation validation remains incomplete. Preserve exact entry count, spend, user constraints and post-slate review. No MLB expansion. 
