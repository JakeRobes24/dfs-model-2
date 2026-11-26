# NFL opportunity diagnostics — retrospective only

## November 25 backfield attribution
Exact archived Corum/Williams pair: 26.29 projected versus 44 actual carries. The symmetric decomposition of Corum's +22.57 actual-minus-projected error is +9.6162 carries from pair-volume error and +12.9538 from within-pair allocation error. Williams' -4.86 error is +8.0938 volume and -12.9538 allocation. The sum of allocation errors is zero. After the historical prior, Corum still has +9.5110 volume and +11.3067 allocation error. These are pair totals, NOT full team rushing volume; observed actuals are for attribution, never a forecast input.

## Original DAILY offensive rows
Read-only independent arithmetic check of original Library exports: 42 labeled offensive rows from Nov25 and 108 from Nov26, all finite complete scoring fields in those rows. Standard visible passing/rushing/receiving subtotal minus labeled fantasy score is within 1 FD point on all 150; maximum absolute residual 0.327 and 0.417 respectively. This checks raw export arithmetic, not full contest identity/status coverage or provider scoring certification. Kicker/DST layouts are excluded. The subtotal omits events such as fumbles and conversions; the original DAILY score remains authoritative. Python diagnostics preserve all labeled offensive components, require valid opportunities before creating team-budget records, retain missing players, and report numeric completeness rather than certify a team's actual play volume.

The 1-point residual flag is diagnostic only, not a calibrated decision rule. No changes to player scoring, candidate ranking, production deployment, or automatic projection selection.
