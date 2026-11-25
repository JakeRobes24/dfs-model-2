# November 25 continuation checkpoint: paired production source audit

Verified branch head 9f4e9161200813039cd2b31d9aa116609799ea86. Full regression run 45588214504: 341 passed, one deselected, 134 warnings; all four workflows at this head succeeded. Public source probe run 45588214610: 830 exactly equal cold/warm official rotation rows, 38/38 final boxes and 7/7 schedule pages, 2.691s cold and 0.555s warm (79.4% reduction); not hosted UI timing.

## Paired forecast source decision
- RotoGrinders: public schema contains projected minutes and full relevant box-score stats; the existing adapter already derives FanDuel points from those same rows. No new source family.
- Daily Fantasy Fuel: 25 public FanDuel projection rows; inspected headers and row attributes omit projected minutes. Keep points-only; never combine with another provider's minutes to claim a paired source rate.
- LineupExperts: runner HTTP 403; keep reference/verified upload route.
- Fantasy Team Advisors (fantasyteamadvisors.com): provider guide https://fantasyteamadvisors.com/guides/nba-projections/ documents same-row minutes, site-specific points, update time and top-15 free preview. Accessible public article https://fantasyteamadvisors.com/nba-dfs-draftkings-projections/ displayed a Nov 24 5:17 PM CST update and a DraftKings points-only top-ten table, not eligible paired FanDuel rows; full board requires its tool. Keep reference/optional archive, no live weight, no claim of historical coverage. Inspect documented FanDuel preview through authorized access on a fresh slate before implementing any adapter.
- Fantasy Team Advice (fantasyteamadvice.com) is a separate domain, not verified as independent from any registered family; public board https://fantasyteamadvice.com/nba/dfs-projections showed Nov 24 projections and partial access, no verified same-row minutes. Do not silently substitute for Fantasy Team Advisors or the unresolved FantasyProjections name.
- FantasyProjections identity remains unresolved after search; no numeric use.

No additional paired source was admitted. All existing source rules and live scoring remain unchanged. This checkpoint records verified runner outcomes and public web findings, not new code or a new full-pool test.

Next: inspect remaining saved candidate providers for explicitly dated, pre-tip, same-provider paired forecasts; acquire prospective paired captures over multiple distinct dates, then evaluate equal-date error and fixed-minutes sensitivity before any shadow blend promotion. Keep all incomplete/access-restricted sources visible; never count provider aliases or unverifiable timestamps as independent evidence.

## Remaining saved source review (Nov 25)
- STAT-API NBA schema documents minutes_mean, pts, reb, ast, stl, blk, tov and inputs_as_of, plus game and player IDs and engine version. Source: https://stat-api.com/docs/data-dictionary/nba/ . Its DFS slate endpoint documents operator-specific points. Access requires a key; free list responses are capped at five records and full projections require the relevant tier (https://stat-api.com/faq/records/). The input timestamp is not necessarily the forecast publication timestamp; verify capture and pre-tip identity before use. RotoQL is powered by STAT-API; do not assume two independent votes. No API call, key, purchase or numerical coverage verified.
- DraftEdge public board https://draftedge.com/nba/nba-daily-projections/ exposed a dated projection table but masked projections and did not expose same-row projected minutes in the inspected preview. Retain manual research.
- FantasySportsEdge public board https://fantasysportsedge.com/nba/projections confirms FanDuel main-slate scoring but no paired minutes in the inspected table; retain reference-only provenance restrictions.
- TheCapper https://thecapper.io/nba/projections/ explicitly withholds blocks on Nov 25 and publishes conditional projections. Keep incomplete stat lines as manual reference only; never assume missing blocks are zero.
- Registry updated to retain these access limitations and two documented links; regression test added to ensure manual sources cannot be shown as verified based on claimed refresh status. No scoring changes.

## Archived coverage bottleneck review

Development checkpoint 8d43227185f70dcb5f705a6afd07bc2eef10bb34: four workflows passed, full regression run 45592501743 reported 345 passed, one deselected, 134 warnings.

Read-only examination of the private incoming-app directory found dates Nov 18, 20 and 24. Nov 18 contest 136886 contains 316 research rows (260 eligible) but no full frozen pre-tip replay or paired projection JSON. Nov 20 contest 136961 has a 1.51 MB packet; the connector returned incomplete JSON, so coverage remains unknown. Nov 24 contest 137139 has 70 rows and unknown replay timing; do not count as a verified capture. Nov 24 contest 137128 has 105 rows, 85 eligible, and capture 2026-11-24T11:14:51.162030Z marked before full slate tip. Its results packet has 105 recorded actual rows. The two packets have identical reported research lengths and capture versions; the calculation used the actuals-bearing packet 3a6167f57f3de9a02ddf9aa64620ec69236b045546a0e3ef0566259b502ad984.json.

Read-only JavaScript calculation on archived rows mirrors current paired coverage and rate policy logic; not a Python execution, independent checksum validation, or fresh official result retrieval. No outcome data was used to choose the coverage classifications.

| Eligible players | Count |
|---|---:|
| No fresh paired provider | 26 |
| One fresh paired provider | 59 |
| Two or more fresh paired providers | 0 |
| Reviewed minutes policy not met | 44 |
| Insufficient paired sources after policy gates | 38 |
| Uncertain availability | 3 |
| Supported experimental rate forecasts | 0 |

PropSims: 59 eligible fresh paired rows; Daily Fantasy Fuel: 24 eligible fresh points-only rows; RotoGrinders: no accepted fresh point rows in this archive. Coverage is limited to one assessable date; no cross-date accuracy claim. Acquiring genuinely overlapping independent paired estimates is the immediate bottleneck for the paired-rate experiment; do not relax the minutes policy or count points-only sources as paired. Continue regular capture and the existing prospective evidence gates (five dates / 100 matched observations) before independent validation. No live scoring changes.


## RotoGrinders/PropSims paired-board diagnostic and resilience batch

Run 45593456274 on commit 76bb29c42038de9de5746c4ae45ddb1fc6bd4f28: public RotoGrinders board contained only six actual stat rows, all numeric, all MIA@PHI, and all six were accepted by the adapter. The public schedule menu listed additional games but did not supply their stat rows. PropSims returned 60 records and the positive paired player/name/team/matchup intersection was four. These are public board counts, not contest-matched or post-news coverage. All four workflows passed; run 45593456343: 345 tests passed, one deselected.

The previously unavailable PropSims board recovered in the later check. Added one bounded retry for temporary transport and selected 5xx failures, never for 403/429 or stale/invalid data; isolate malformed PropSims numerical rows instead of discarding valid pairs. RotoGrinders now requires an explicit offset and allows a fresh previous-evening forecast only with the exact current dated pre-tip schedule. No new provider family, no altered consensus weights, no bypass of public limits. Valid newly recovered records may affect the existing pipeline normally. Added synthetic regression cases for these changes. Full CI verification pending.


## Additional provider feasibility review (November 25)

Candidate inventory only; not added to the live automatic research stack or counted as independent scoring votes. Prioritize based on documented ability to supply a complete, dated paired row and accessible coverage rather than marketing claims.

| Candidate | Observed evidence | Decision |
|---|---|---|
| Three7 DFS (https://three7dfs.com/nba/) | Public board on retrieval labeled Monday Nov 23, updated 8:22 PM ET, after its 7 PM first lock. Displayed DraftKings table has Min, Pts, Reb, Ast, Stl, Blk, TO and player matchup, plus a FanDuel switch. | High-priority fresh pre-tip inspection. Complete stat rows could be converted to FD without using the DK median; verify date, publication time, exact matchup and same-provider provenance. Do not use this stale board. |
| Daily Fantasy Tips (https://dailyfantasy.tips/nba-projections-for-the-preaseason-and-the-regular-season/) | Public FanDuel table exposes player, team, opponent, salary, projection, value, and FD ID. Nov 25 04:31 timestamp nevertheless accompanied Nov 24 contest 137128 and its three matchups; actual visible FD table lacks minutes. | Points-only candidate for current contest-matched reference. Reject stale contest and unverified timezone; never infer paired minutes from the documentation. |
| BankrollSZN (https://bankrollszn.com/nba-projections) | Advertises FD-specific scores, engine minutes and production inputs. Public preview shows limited players from the prior slate; full board requires a free account. | Authorized manual research candidate; no account creation or claims of coverage. |
| FanDuel Research (https://www.fanduel.com/research/nba/fantasy/dfs-projections/pg) | Public projection page offers CSV download but inspection did not expose player rows, paired minutes, or publication time. | Manual CSV evaluation if available, identity/provenance still unverified. |
| TipoffLab (https://dfs.tipofflab.com/) | Public sample shows same-row points and minutes, but a Nov 4 DraftKings example and private beta access. | No established current FD feed; defer. |
| Dimers (https://www.dimers.com/nba/player-projections) | Documents full projected stat lines and minutes as a model input; public access limited to three players and full export requires Pro. Same-row projected minutes not established. | Low-priority reference; no purchase. |
| SpreadModel (https://spreadmodel.com/dfs-projections-api/) | Search listing describes site-specific projections and minutes; direct documentation returned HTTP 502. | Unverified candidate; defer until documented access is available. |

Next: inspect Three7's *current* pre-tip board and verify the dated schema before deciding whether to build a reference-only adapter. Consider the other authorized sources only if they add unique, contest-matched evidence. Continue existing full-pool research, preserve all prior registry entries, and avoid repeated searches of unavailable pages. Provider coverage and numerical accuracy remain separate.
