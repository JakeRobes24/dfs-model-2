# November 28 nine-player dependence and weekly stability
Predecessor 20627d6 verified: NFL 46137292250, NBA 46137292166, full 46137292191 successful. No live scoring or portfolio change. Recovered and checked archive member hashes for Live Performance Audit and NBA Multi Slate Roster Calibration Nov28. Verified official observations archive SHA256 2063db41a4a8332b0fb98bd2460449744ae07203e4f9cd2caac3e5d41cea74f9 and Nov24 contest file SHA256 d401c215c4db90be9ecefc949afb6f83ef25bce41f1bdf1f1b81873e1a25d9dc. Nov24 roster IDs from original exact app archive, Nov27 from final report. Retained the previously verified nine-player sets with complete played-scope outcomes, three Nov24 and 24 Nov27; projected and actual totals agree with earlier archived roster evaluation. Nov22 underlying roster files not restored for this batch; Nov25 timestamp unverified, excluded. No new legality or prospective claim.

## NBA fixed-marginal dependence
Local Python reconstructed 1,164 eight-game historical residual rows from official boxes (counting fields 0–150, 10–60 minutes, unique dates, positive historical and actual opportunity denominator). Prior training only: 1,003 rows for Nov24, 1,164 for Nov27. Fit centered standardized point errors by projected-minute band (18/28 cutoffs, at least 30 rows else overall); average same-team and opposing-team cross-products within game, equal date averaging, shrink by games/(games+50), cap ±.35. 79 and 91 supported training games. Estimated latent same-team/opponent parameters .006273/-.002183 and .007345/-.000506. These are exploratory copula parameters, not measured rank or marginal realized correlations. Sample 12,000 paired minute/rate residual draws per player (seed 137257, same band/fallback), centered residuals, minutes clipped 1/60–60. Reorder fixed draw columns by shared normal rank scores, compare zero, half and full estimated dependence; exactly preserve every player's sorted values, means and marginal ranges across methods. Same player draw across every candidate. Repair toward identity for nonpositive eigenvalues (not needed in these dates). Keep all nine-player candidates fixed; no outcome-driven roster construction, selection or parameter fitting. Verify actual and projected totals against archived range report.

| Date / method | Coverage | Width | Interval score | CRPS | Order Brier |
|---|---:|---:|---:|---:|---:|
| Nov24 independent | 66.7% | 93.000 | 134.078 | 31.499 | .218233 |
| Nov24 half | 66.7% | 93.198 | 134.061 | 31.479 | .218128 |
| Nov24 full | 66.7% | 93.356 | 134.057 | 31.460 | .218444 |
| Nov27 independent | 58.3% | 91.281 | 159.024 | 27.578 | .263176 |
| Nov27 half | 58.3% | 91.439 | 158.767 | 27.567 | .263159 |
| Nov27 full | 58.3% | 91.607 | 158.538 | 27.558 | .263144 |

3 and 275 non-tied comparisons respectively. All three methods share exact individual empirical distributions. The narrow change is consistent with near-zero fitted aggregate point-error correlation. No meaningful correction to undercoverage or candidate ordering; Friday still worse than neutral .25 order Brier. No seed-sensitivity claim or prospective validation; overlapping rosters, conditional played-only selection and retrospective historical fit. More specific role, rotation, pace, blowout and availability dependence remains open. Do not infer that actual player dependence is zero.

## NFL earlier-season learned role dependence stability
Recovered DFS_Model_2_Recovered_Outcomes_and_Role_Dependence.zip SHA256 ff40cc1b5aa5bb5be78e30cc4bef2e5aac0b622707109a8cd8332ade4cabd2cf (computed on recovery). Read archived nfl-role-dependence-weekly.csv: 112 aggregate rows, eight pair types, two policies, seven evaluation weeks. Verify matched pair counts for each week. Earlier Work fit 2025, evaluated 2026; this batch does not refit or create new holdouts. Calculate equal-week CRPS gain (independent minus learned), number of improved weeks, leave-one-week-out range and interval score gain.

| Pair | Pairs | CRPS gain | Improved weeks | Leave-one-week-out gain min/max | Interval score gain |
|---|---:|---:|---:|---:|---:|
| QB–QB opposite | 60 | .03372 | 5/7 | .02099/.04044 | .08265 |
| QB–WR opposite | 149 | .00101 | 5/7 | .00041/.00153 | .02428 |
| QB–RB same | 137 | .00326 | 5/7 | .00171/.00502 | -.01889 |
| QB–TE same | 140 | .03637 | 6/7 | .01712/.05617 | .53890 |
| QB–WR same | 151 | .02792 | 5/7 | .01862/.04809 | .54107 |
| RB–RB same | 101 | -.00012 | 2/7 | -.00097/.00051 | -.03419 |
| RB–WR same | 170 | .00276 | 6/7 | .00243/.00332 | .04953 |
| WR–WR same | 169 | .00365 | 4/7 | .00178/.00631 | .05932 |

All other types have small effects; QB-pass catcher and opposing QB-QB most encouraging. Positive gains for QB-WR and QB-TE survive removing any one evaluation week, but effect is small and does not establish a better legal lineup or payout. Pair samples overlap. Preserve existing research correlations, no new stacking requirement, no arbitrary exposure cap or changes to scoring. Final adjusted NFL prelock forecasts and exact simulation receipts still need recovery/forward capture. No NFL full-roster simulation newly evaluated.

## Checkpoint
Reusable fixed-marginal reorder and weekly robustness helpers added; both local tests passed (marginal preservation/matrix repair and exact common weekly support/leave-one-week-out). Local numerical NBA replay used same rank-coupling formula, independently from earlier simulator. Full replay runner is separately retained in the working research folder, not yet permanently archived; method and results above and code helper in repo. Latest full CI pending. Continue source expansion, role-conditional uncertainty, prospective freeze and actual slate evaluation. No MLB or production changes.
