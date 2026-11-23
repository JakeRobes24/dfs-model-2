# November 22, 2026 NBA FanDuel — user-entered two-lineup screenshot audit

## Provenance and scope

Two user-supplied FanDuel lineup screenshots and one contest standings screenshot, captured near the end of the Boston–Golden State game. The user confirms **only two of the four intended lineups were entered**; the other two are unsubmitted test candidates, not contest results. Contest screenshot title begins `$2K Sun NBA Piggy Bank Shot...`; do not infer complete contest ID or full title.

This is a **screenshot transcription and arithmetic check**, not independently certified official finals or a complete projection-error audit. Boston–Golden State shows fourth quarter **0:00** and Neemias Queta **21.0 FD** in both screenshots; standings show **1 minute left**. The standing scores are provisional until independently finalized.

## Entered lineup 1

| Slot | Player | Screenshot FD |
| --- | --- | ---: |
| PG | Josh Giddey | 70.8 |
| SG | Klay Thompson | 27.2 |
| SF | Matas Buzelis | 36.5 |
| PF | Josh Hart | 38.2 |
| C | Neemias Queta | 21.0 |
| G/F | Aaron Gordon | 43.1 |
| F/C | Nikola Jokić | 78.1 |
| UTIL | Jamal Murray | 74.5 |
| UTIL | Keyonte George | 30.5 |
| **Total** | | **419.9** |

## Entered lineup 2

| Slot | Player | Screenshot FD |
| --- | --- | ---: |
| PG | Josh Giddey | 70.8 |
| SG | Mikal Bridges | 14.1 |
| SF | Josh Hart | 38.2 |
| PF | Aaron Gordon | 43.1 |
| C | Neemias Queta | 21.0 |
| G/F | Jalen Suggs | 16.8 |
| F/C | Nikola Jokić | 78.1 |
| UTIL | Jamal Murray | 74.5 |
| UTIL | Keyonte George | 30.5 |
| **Total** | | **387.1** |

The six common players are Giddey, Hart, Queta, Gordon, Jokić, Murray and George — **seven** common players. Differences: Lineup 1 has Klay Thompson **27.2** and Matas Buzelis **36.5**; Lineup 2 has Mikal Bridges **14.1** and Jalen Suggs **16.8**. The changed players produce **63.7 vs 30.9**, a **32.8 FD** difference. All nine scores in each screenshot sum to the displayed contest standings totals.

## Contest standings (provisional screenshot)

- Username `panambi98`, shown rank **174**, score **419.9**, displayed prize **$0.30**.
- Same username, shown rank **1512**, score **387.1**, displayed prize **$0.15**.
- The contest was not marked fully final in the screenshot; **do not certify ranks or prizes as final**.
- Two other planned lineups **not entered**; do not invent entries, contest returns or lineup scores.

## Research hypotheses, not proven errors

1. **Ceiling/correlation:** Jokić (78.1), Murray (74.5), and Gordon (43.1) combined for **195.7 FD**, with Giddey adding **70.8**. Determine whether the archived prelock simulation captured high-ceiling Denver stack outcomes and ownership/duplication risks.
2. **Challenger swap:** Compare original **timestamped prelock** projections, minutes, usage, roles and positional eligibility for Klay Thompson + Buzelis vs Mikal Bridges + Suggs. The actual **32.8** difference alone is not proof the first construction was the better prelock decision.
3. **Roster legality:** Screenshots establish nine distinct players per lineup and visible slots; cannot verify salary cap or contest-CSV eligibility without original slate CSV.
4. **Projection accuracy:** Do not calculate expected-vs-actual deltas until matching archived prelock DAILY and adjusted projections to exact FanDuel IDs and cutoff timestamps.
5. **Final confirmation:** Reconcile official final player box scores/FD scoring and contest settlement; preserve differences if they emerge.

## Resume actions

- Load the archived November 22 NBA contest `137037` snapshot (separate from NFL `136799`); check whether these exact entered rosters belong to that contest before joining.
- Match the two screenshot lineups to the authoritative NBA contest pool and stored prelock forecast version; preserve the original two unsubmitted builds as candidates only.
- Retrieve verified final actuals for the full eligible pool, compare paired DAILY/adjusted projections, investigate minutes/role misses and ceiling calibration.
- Do not modify production weights based on one slate or these screenshots alone.

**Engineering:** This note records user evidence and hypotheses; no model tuning, live deployment, or private history database changes.
