"""Verify the six Nov 22 contest games against official NBA final boxes."""
from datetime import date
from slate_results import collect_final_boxes, nba_outcomes
from slate_import import game_code, matchup_key

codes = ["BOS@GSW", "DAL@UTA", "DEN@CHI", "IND@NYK", "OKC@MIA", "ORL@WAS"]
games = {matchup_key(game_code(c)) for c in codes}
boxes = collect_final_boxes(date(2026, 11, 22), games)
outcomes, finals = nba_outcomes(boxes)
print("OFFICIAL_FINALS", len(finals), len(games))
if finals != games:
    raise SystemExit("NBA official final coverage incomplete")
count = {"Played": 0, "Did not play": 0, "Needs review": 0}
for (game, team, name), identities in sorted(outcomes.items()):
    if len(identities) != 1:
        print("OFFICIAL_AMBIGUOUS", game, team, name, len(identities), sep="|")
        continue
    outcome, minutes, points, source, *_ = next(iter(identities.values()))
    count[outcome] += 1
    print("OFFICIAL|" + "|".join(map(str, (game, team, name, outcome,
                                            "" if minutes is None else minutes,
                                            "" if points is None else points))))
print("OFFICIAL_COUNTS", count)
