# November 28 full-pool exposure challenge and shared-draw comparison

Predecessor d3ef3a3 verified: NFL 46137931059, NBA 46137931051, full 46137931041 success. User's mandatory evidence-backed repetition review remains active for NBA and NFL. No live scoring or optimizer policy changes.

## Actual replay
Executed local Python on NBA_137257_1840_checkpoint.zip SHA256 0545c34e12387efa4094ee359d54b272f8c3725f115c17152b2a6e0a82b1418f. Original contest template and closing pool match all 244 IDs, of which 158 have positive reviewed score and status blank/P/A. Preserve original exact slot eligibility including composite slots, $60,000 salary cap, nine distinct players, max four from team, and archived status exclusions. Reuse archived 18:00 slot MILP and 18:40 reviewed points; remove tiny late-slot objective tie term for pure mean, set two-second limit and zero relative gap request. Test no omission, six individual omitted players with at least three actual entries, and the three pairwise omissions among the actual all-four core, each with Towns in and out (20 single-roster solves). All 20 reported optimal and passed independent roster count, slot, salary, club, omission and Towns inclusion checks. 13 new distinct sets; original 28 retained, union 41. This is bounded candidate expansion, not a proof of global portfolio optimum. All union sets have historical simulation support.

| Omitted player | Best without Towns | Best with Towns |
|---|---:|---:|
| None | 326.2819 | 326.9002 |
| Jaden McDaniels | 325.7828 | 325.7981 |
| Daniss Jenkins | 321.2691 | 321.3651 |
| Day'Ron Sharpe | 323.6965 | 325.0024 |
| Tyrese Maxey | 325.0540 | 325.7802 |
| Kevin Huerter | 326.1390 | 325.2893 |
| Isaiah Joe | 326.2819 | 326.3240 |
| Sharpe/Jenkins | 318.8254 | 319.0593 |
| Sharpe/McDaniels | 322.8904 | 323.9347 |
| Jenkins/McDaniels | 320.5068 | 320.9377 |

## Shared-draw portfolio comparison
Use archived residual construction (four-eight earlier recorded same-team played games, Cartesian minute/rate residuals centered), official history archive SHA256 2063db41a4a8332b0fb98bd2460449744ae07203e4f9cd2caac3e5d41cea74f9. Same per-player outcomes across union; sorted player indices for deterministic draw allocation, hence not byte-exact original replay. Preserve two Towns entries and four distinct lineups, aggregate mean within four points of highest-mean portfolio (original archived guardrail, not general cap). Evaluate 892 expanded portfolios, 232 original. Use original seeds 1840137257 (2500 selection draws) and 1841137257 (30000 evaluation draws); maximize minimum expected best across frozen in and all-Q-out scenarios on selection draws, evaluate separately. Actual outcomes joined only after selection via digest-verified live audit normalized CSV, no missing value imputation.

| Portfolio | Mean total | Held-out robust expected best | Best P90 (in scenario) | All-four core | Realized best |
|---|---:|---:|---:|---:|---:|
| Highest mean | 1306.0593 | 342.2070 | 378.7734 | 4 | 265.7 |
| Actually entered / original universe winner | 1302.2014 | 345.3461 | 382.2978 | 3 | 308.1 |
| Expanded universe winner | 1302.2014 | 345.3461 | 382.2978 | 3 | 308.1 |
| Best lower McDaniels exposure | 1302.2344 | 345.1864 | 381.8164 | 2 | 308.1 |
| Best lower Sharpe exposure | 1302.3144 | 344.4189 | 379.7360 | 3 | 294.7 |
| Best lower Maxey exposure | 1302.3039 | 343.8316 | 381.4392 | 4 | 284.3 |
| Best lower Huerter exposure | 1302.4046 | 344.5491 | 381.6398 | 3 | 308.1 |
| Best lower Joe exposure | 1302.0828 | 344.8852 | 381.5617 | 3 | 298.0 |

No reduced-Jenkins portfolio passed original four-point aggregate guardrail among generated sets. This is not a mandate to retain Jenkins, nor proof of strong true production forecast. Lower McDaniels candidate set new1_1/new1_2/in_fd_False_3/expanded_2 preserved realized best, +.0330 aggregate mean, -.1597 robust expected best, -.4814 P90, one fewer all-four player but one fewer distinct player (16 vs17) and greater mean pair overlap (5.33 vs5.17). It is nearly tied under this uncertain simulator; lower all-entry core alone is not a sufficient decision. No calibrated tournament win probability or proof of portfolio improvement. In-scenario quantiles remain conditional played-only. This single retrospective NBA slate cannot validate NFL portfolio scoring; NFL remains active with separate rules. Local replay script and detailed results saved in working research folder; permanent archive of full runner/results remains open, summary committed here. No current slate files used, no paid source, no MLB.

## Operational decision
Require explicit exposure challenge before finalization, preserving original full pool and exact legal candidate evidence. Near-identical simulated scores warrant comparing genuinely different opportunities, source/role agreement and shared downside rather than simply maximizing a noisy simulation objective. Do not force exposure caps, change spending, promote scoring weights or automatically select a different portfolio. 
