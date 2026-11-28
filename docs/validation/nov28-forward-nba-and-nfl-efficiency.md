# Nov28 forward NBA reference and NFL efficiency coverage

Predecessor 8b8a0d16f1b9ddc9d80871f8d118e3a096f1954a: NBA 46141386208, NFL 46141386235 and full 46141386226 completed successfully. Continue predictive accuracy and prospective evidence, not discretionary classification. NBA and NFL only.

## NBA pregame reference

Inspected explicitly dated NBA House https://nbahouse.net/minutes/2026-11-28 and TheCapper https://thecapper.io/nba/projections/ on Nov28. Both showed ORL@WSH and BKN@CHA, with House scheduled tips 22:00 and 23:00 UTC. Capper displayed overnight run 02:31 ET, conditional on playing and nominal 80% minutes range; House publication time unknown, expected lineup and minutes. Edgehalla and PropSims minutes direct pages displayed Nov27 despite Nov28 search snippets; rejected as fresh. No independent confirmation of provider publication or official player identities yet.

Preserved all 36 displayed Capper players from these two games matched to House minutes (16 ORL/WSH, 20 BKN/CHA) at review clock 2026-11-28T06:49:25-05:00, private history commit 6fec2959708e6c9289d99f52deb721be31566446, research-evidence/2026-11-28/prospective-nba/early-two-game-component-capture.json, blob f9716770e60ee38c7b27f223d8f4450ac3738ac5. Exact text readback verified. Manually transcribed numbers, Alex/Alexandre Sarr alias explicitly retained, official identity and schedule verification still required. No contest salary or eligibility, no outcome-informed choice, no authenticated acquisition timestamp. No inference that absent players have zero forecasts.

| Group by House projected minutes | N | Mean absolute Capper-House gap | Signed gap | Abs gap >=5 |
|---|---:|---:|---:|---:|
| All |36|2.1472|+2.0194|3|
| Under 25 |19|3.0737|+2.9789|3|
| 25+ |17|1.1118|+.9471|0|

Largest gaps Grant Williams 10 vs 19, Christian Anderson 16 vs 23.1, Tristan da Silva 22 vs 28.4 (House then Capper). These are disagreements, not errors. House projects returning players and uses 240-minute team fitting, whereas Capper runs overnight and assumes participation. No attribution of exact gaps to news without timed evidence. This is selected two-game public support, not whole slate and not a causal effect of playing time. No scoring changes.

New nba_forward_component_reference.py evaluates the exact saved rows only against independently verified, final, played outcomes with same oriented game, tip and stable official identity; missing outcomes and nonparticipation excluded and counted separately. Compares paired minutes by frozen House band, nominal 80% range coverage and interval score, individual count stats, and the explicit FD-weighted subtotal without blocks. Partial subtotal rate and House-minutes/Capper-rate sensitivity require forecast and actual minutes >=10. No claims about full FD score; conditional versus unconditional semantics remain separate. New tests cover missing fields, range scoring, duplicate outcomes and post-tip review rejection.

## NFL forward evaluation extension

Previous Nov29 three-game reference 9b871619fa241bcfd7c1d18542604aa775643492 remains unchanged. Added separate provider-specific component errors and same-provider yardage efficiency (yards per carry, target, or reception), requiring positive matched opportunity counts and explicit yardage. This prevents losing Volt-only targets/carries in the common-support report. It does not treat Malter historical shares as projected counts. Common-support metrics remain unchanged; do not compare provider-specific sample errors as if they used identical players. Added regression for missing other-provider targets and rate error. No new NFL actual outcomes yet.

Both manual references can now be graded following actual games. Current research is before contest reconciliation, not a final slate build or complete model forecast. Numerical disagreement calculation executed in JavaScript; Python tests saved, not locally executed in this turn. Latest CI pending. Preserve all 47 sources and unchanged scoring policy; MLB deferred.
