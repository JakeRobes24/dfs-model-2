# Nov 28 full source inventory and lower-salary production coverage

Previous checkpoint cd8d1d2a0c38fcae4fa0697149aa4efae3f5ddee verified NBA 46140696722, NFL 46140696704 and full 46140696703 successful.

## Inventory
The user requested all 47 sources separated by use. The registry now exposes source_inventory() and source_inventory_counts(), with mutually exclusive highest-established-use classifications: 8 direct/conditional model support, 7 integrated advisory references, 14 manual/historical research, 18 candidates. Highest use is across sports and does not imply that both sports use a provider equally. The authoritative contest CSV and DAILY baseline are separate inputs, not part of the 47. See research_source_registry.py for the complete names, per-sport integration, purpose and acceptance-eligibility columns. New sources default to candidate, with no automatic scoring vote. Some manual/candidate providers have partial numeric evidence, limited access, or no verified numeric rows. Counts are not successful source fetches.

Reviewed main base 2d86b31e2b2dad505f91317377933bfbef2f5857 and development slate_research.py. Both recognize four point families (DFF, PropSims, RotoGrinders, conditionally verified LineupExperts) and four automated minutes providers (RotoWire, NBA House, PropSims, RotoGrinders). Separate official evidence and baseline. LineupExperts public board is reference only; do not conflate with a verified uploaded forecast. NFL staging has 4for4, PropSims and DailyFantasy.tips advisory comparisons and independent manual review; no automatic independent weighted scoring consensus certified. Repository code review does not certify hosted deployment or availability on a particular slate. No weights changed.

## NBA Nov27: lower salary and workload source coverage
Exact private 8549d752ae253e972d09f160dfa6d5cee08be9a5, daily-lineups/2026-11-27/137257-full-pool/full_pool_audit_v2.csv (blob f9d6d72a611c6e42777a4c4f6c19bfa9f67bfc24). Repeat the prior 141 exact-ID played positive-minutes common original/revised sample, finite salary, actual points and minutes, base and revised points/minutes. Count only archived positive PropSims minutes with finite same-provider points, positive House minutes, finite DFF points. These are recorded values, not certified fresh accepted estimates or proof of availability; retrospective source timing limits remain. FPPM uses actual_fd / actual_minutes and in_fd / in_min; include short actual appearances as earlier revision audit, so ratios can be volatile. Groups overlap.

| Cohort | N | PropSims paired | House minutes | DFF points | Revised FD MAE | Rate MAE | Signed rate bias | abs FD miss >=15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| All |141|39|141|21|7.3972|.27375|+.08864|16|
| PropSims paired |39|39|39|21|9.6256|.23059|+.07009|9|
| No PropSims pair |102|0|102|0|6.5452|.29025|+.09573|7|
| Salary below 5000 |93|0|93|0|6.3877|.29742|+.10752|5|
| Salary 5000–6999 |27|18|27|2|9.2649|.22223|+.03111|7|
| Salary 7000+ |21|21|21|19|9.4669|.23513|+.07899|4|
| Revised minutes >=30 |38|32|38|19|9.0304|.20070|+.06411|7|
| Revised minutes <30 |103|7|103|2|6.7947|.30070|+.09769|9|

This is a coverage and selection diagnostic, not a head-to-head provider accuracy comparison. Coverage is highly salary-dependent; none of 93 lower-salary players has a recovered paired independent rate forecast from PropSims, and no DFF point estimate. Do not infer these players lacked all research or that a provider failed live. DFF alone cannot provide a same-provider rate. Short-minute denominators may inflate rate error. Absolute point errors grow with opportunity, so compare providers on identical players. Examples: Dominick Barlow 14.22 projected vs 35.1 observed, actual minutes only about 4.03 above forecast but rate substantially underestimated. Elijah Harkless 8.80 vs 32.3, actual minutes about 16.72 above forecast. Neither had archived PropSims pairing. These are outcome diagnoses, not future player preferences. Prioritize broad lower-salary and bench/role-change paired components, not simply more top-player total projections; keep mandatory full-pool review.

Calculations executed directly on exact archived rows using JavaScript. New inventory helper and regression cases saved, new CI pending. No new NFL empirical results in this batch; NFL source classification and advisory path verified. Preserve previous NFL workload/efficiency research. No MLB, production merge or change to scoring. Next prospective work: exact timed full-pool coverage by salary and workload, source family and distinct minute/rate components; compare missing versus observed explicitly and preserve evidence before outcomes.