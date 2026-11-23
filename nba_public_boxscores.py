"""Export dated ESPN NBA final box scores for an explicitly scoped set of games.

Official NBA box scores remain the preferred verification source. ESPN data is
an independently retrieved secondary source, not FanDuel contest scoring.
"""
import csv
import json
import sys
from urllib.request import Request, urlopen

GAMES = {"BOS@GSW", "DAL@UTA", "DEN@CHI", "IND@NYK", "OKC@MIA", "ORL@WAS"}


def fetch(url):
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0 DFS-research-audit"}), timeout=25) as response:
        return json.load(response)


def minutes(value):
    if ":" in str(value):
        m, s = value.split(":", 1)
        return round(float(m) + float(s) / 60, 3)
    return float(value)


def export():
    schedule = fetch("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20261122")
    writer = csv.writer(sys.stdout)
    writer.writerow(["game", "name", "team", "minutes", "points", "rebounds", "assists", "steals", "blocks", "turnovers", "fd_points", "source"])
    covered = set()
    for event in schedule.get("events", []):
        comp = event["competitions"][0]
        teams = {c["homeAway"]: c["team"]["abbreviation"] for c in comp["competitors"]}
        code = teams["away"] + "@" + teams["home"]
        aliases = {"UTAH": "UTA", "NY": "NYK", "GS": "GSW", "WSH": "WAS"}
        code = aliases.get(teams["away"], teams["away"]) + "@" + aliases.get(teams["home"], teams["home"])
        if code not in GAMES:
            continue
        if comp.get("status", {}).get("type", {}).get("completed") is not True:
            raise ValueError("Game not final: " + code)
        summary_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=" + str(event["id"])
        data = fetch(summary_url)
        covered.add(code)
        for side in data["boxscore"]["players"]:
            team = side["team"]["abbreviation"]
            for group in side["statistics"]:
                labels = group.get("labels", [])
                for item in group.get("athletes", []):
                    vals = dict(zip(labels, item.get("stats", [])))
                    if not item.get("didPlay", True) or "MIN" not in vals or "PTS" not in vals:
                        print("DNP|" + code + "|" + item["athlete"]["displayName"] + "|" + team, file=sys.stderr)
                        continue
                    try:
                        fields = {key: float(vals.get(label, 0)) for key, label in
                                  [("points", "PTS"), ("rebounds", "REB"), ("assists", "AST"),
                                   ("steals", "STL"), ("blocks", "BLK"), ("turnovers", "TO")]}
                        mins = minutes(vals["MIN"])
                    except (ValueError, TypeError):
                        continue
                    fd = fields["points"] + 1.2 * fields["rebounds"] + 1.5 * fields["assists"] + 3 * fields["steals"] + 3 * fields["blocks"] - fields["turnovers"]
                    writer.writerow([code, item["athlete"]["displayName"], team, mins,
                                     *(fields[k] for k in ("points", "rebounds", "assists", "steals", "blocks", "turnovers")),
                                     round(fd, 2), summary_url])
    if covered != GAMES:
        raise ValueError("Missing contest games: " + repr(sorted(GAMES - covered)))


if __name__ == "__main__":
    export()
