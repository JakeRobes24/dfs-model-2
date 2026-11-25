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
