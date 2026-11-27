# NFL receiving opportunity share challenger

Independent JavaScript replay of repository evidence docs/validation/nfl-yardage-evidence.json (Git blob e154aeb2a85acc88489be72187503297fee8cb11). Same four earlier complete recorded paired-backfield games and target outcomes for all methods. No missing targets imputed. New optional challenger averages the direct four-game targets forecast and the existing team-volume times recent share forecast.

| Team | Held-out paired games | Last-game MAE | Four-game MAE | Team volume + recent shares MAE | 50:50 blend MAE |
| --- | ---: | ---: | ---: | ---: | ---: |
| LAR | 5 | 1.400 | 2.350 | 2.240 | 2.270 |
| DET | 10 | 1.550 | 1.700 | 1.706 | 1.703 |
| CHI | 2 | 1.250 | 1.250 | 1.151 | 1.200 |

Only 17 paired games, not representative of all receivers or team roles. Last-game forecast wins two cohorts and the existing recent share model wins the third. No reason to promote the new blend. This is retrospective conditional on both recorded players and verified team targets; no prospective validation or full contest scoring. Code adds the blend as opt-in and preserves defaults, with tests against all three actual archived cohorts. No Friday file, MLB, or production scoring changes.
