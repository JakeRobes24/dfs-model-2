# November 28 NBA independent paired candidate sensitivity

The previous checkpoint e11c3705032e40294d047d10c9736ffad9c3090c passed all three GitHub workflows: NFL 46153779567, NBA 46153779411 and full 46153779407. Continue NBA-first work; NFL preserved, MLB deferred. No live weight or optimizer change.

## Archived numerical replay

Read exact private history 8549d752ae253e972d09f160dfa6d5cee08be9a5, daily-lineups/2026-11-27/137257-full-pool/full_pool_audit_v2.csv (f9d6d72a611c6e42777a4c4f6c19bfa9f67bfc24) and candidate_audit.csv (3878cf464c5de68bee0de4c54e0ba33c3ff306dd). Verified 244 unique player IDs/names and 28 distinct archived nine-player candidate totals, each matching original reviewed and actual sum within .001, no inferred outcomes. Exact slot legality was previously independently checked in the drop coverage outcome report for these same 28 sets. No new slot verification claimed here. All calculations executed in JavaScript on archive.

Use only archived predecision fields to define paired support: status at 17:15 blank/A/P, incumbent and PropSims minutes 10–48, positive points <=150, rates <=5. No actual minutes or scores used for support selection. Source observation and publication timing remain incomplete in archive; not a certified fresh forecast replay. 38 of 244 rows supported, 6–8 per roster (mean 7.36); no supported row under $5000, mean 1.64 such players per roster. Retain incumbent for unsupported rows. Compare source rate at incumbent minutes, half rate, source minutes at incumbent rate, and source paired total. No reoptimization. All same rosters, same outcomes.

| Policy | Lineup MAE | Signed bias | Mean abs change | Correct non-tied pair order |
| --- | ---: | ---: | ---: | ---: |
| Reviewed |38.7319|37.9094|0|40.32%|
| Rate only |40.3104|39.8869|2.8630|44.83%|
| Half rate |39.5211|38.8982|1.4315|42.71%|
| Minutes only |40.0606|39.4481|2.0990|52.79%|
| Source paired |41.5465|41.3338|3.6874|50.93%|

377 non-tied actual pairs; rate-only changed 61 comparisons (39 toward actual ordering, 22 away), half-rate 45 (27/18), minutes-only 113 (80/33), both 88 (64/24). These comparisons are strongly dependent; the candidates overlap substantially and come from one reused slate with incumbent positive bias. Better rank agreement does not establish profitability, calibrated ceiling, or a better prospective scoring policy. All substitutions worsened total error; do not increase automatic source weight based on this sample. The cheap-player coverage gap remains the priority, rather than assigning more weight to supported higher-salary players.

## Operational upgrade

nba_candidate_paired_sensitivity.py reuses the exact roster validator and registered, fresh same-provider paired coverage. Source observation cutoff is six hours and after any valid recorded team confirmation; later observation is not proof of news incorporation. Require stable pre-tip availability and 10–48 minutes, retain valid reviewed points if minutes are missing. Compute fixed-roster source-specific rate-only, half-rate, minutes-only and paired totals; disclose unsupported fallback and sub-$5000 coverage separately. Never mix source families, change eligibility, use actual outcomes, or overwrite a projection. Existing pre-tip UI offers the optional comparison and download; no new network calls. Three synthetic regressions added. Commits 526c19ce, 4a408a60, 5be4b4c8, 24018e2d. Latest CI pending at documentation time; hosted UI unverified.

## Decision

Keep reviewed scores as live incumbent. Compare alternative lineups with actual current research, not by mechanically choosing the most favorable sensitivity. Today's prospectively captured component and source outcomes are more valuable than further reuse of the same retrospective set. Preserve mandatory full-pool research, exact contest validation, independent rate and workload checks, shared-core challenges, final status verification and pre-tip receipt; do not delay slate preparation for experimental development. Continue NBA and NFL work after post-slate. No production deployment or stake change.
