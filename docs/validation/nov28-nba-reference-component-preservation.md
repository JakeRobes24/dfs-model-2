# November 28 NBA-first partial component evidence and preservation

Previous checkpoint 1e611dfb98870ef36848c8659285001fa26b4a0f passed NBA 46150610221, NFL 46150610250, full 46150610237. Preserve all 50 research sources, NBA immediate focus, NFL work retained, MLB deferred.

## Numerical diagnostic
Reopened DFS_Model_2_NBA_Rotation_Replay.zip, original 2026-11-18.json member SHA-256 8ec493160d935b4b4faed6efb144077f8c52fb5e2529d0b9023de1846a474e12. Executed local Python on 2132 complete counting-stat played observations (21 dates), unique date/NBA ID/team, 10–60 actual minutes, counting stats in 0–150. Incomplete historical schedule coverage. Compute the error from comparing partial realized FD-weighted components with full realized FD, on identical rows. This is an omission diagnostic with actual counts, not a forecast accuracy or provider performance test. Group by ACTUAL minutes, not a pregame decision rule.

| Omission | All 2132: absolute FD difference | Actual 10–<25 min (1085) | Actual 25+ min (1047) |
|---|---:|---:|---:|
| PTS/REB/AST subtotal only |3.37664|2.68756|4.09074|
| Blocks absent |1.51970|1.16406|1.88825|
| Turnovers absent |1.44794|.97235|1.94078|

PRA-only signed difference -2.57927, absolute FD/min difference .139114, 27.955% of rows differ by at least five FD. Lower-minute subset PRA-only rate difference .148261; higher-minute .129634. Blocks-absent signed difference -1.51970, rate error .062000; turnovers-absent signed difference +1.44794, rate error .056465. These show why partial stats cannot be compared as complete FanDuel totals. Do not use observed mean omissions to impute a future player's missing fields. No new scoring weights.

## Fix forward evidence retention
Existing MatchWiz reference parser supplies minutes, PTS/REB/AST and a projected role, but generic reference archive previously retained mostly minutes and total points. Existing Edgehalla parser reads all six scoring components and constructs a conditional FD total, but its adapter discarded the components. Preserve all reported counts separately from FD total (reference_pts is real basketball points, reference_points remains existing FD total). Explicit zero retained; absent/invalid component omitted. MatchWiz remains partial only; its generic archive FD total is null, projected role is not official. Require actual dated, aware, within-six-hour retrieval timestamp for MatchWiz and Edgehalla records rather than substituting the archive time; publication remains unknown. Existing exact identity matching and reference-only semantics retained. No additional network requests.

Official outcome comparison now retains the complete six FanDuel counting fields, including previously discarded steals, blocks and turnovers, from the same verified played box as the official score. Replay export preserves optional official component columns, masks unverified and nonplayed observations rather than imputing zeros, remains compatible with prior results missing those fields. This creates a path to matched component and partial-rate evaluation with the original DAILY count projections; it does not yet implement or certify a new component evaluation dashboard. Four new regression cases cover partial/full component retention, real zeros, future observation rejection, and played-only official count export. Latest CI pending. No actual current contest coverage, deployment or changes to the scoring/optimizer. Prioritize evaluating exact prospective component records against verified official counts after outcomes.
