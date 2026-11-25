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
