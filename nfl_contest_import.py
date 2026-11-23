"""Strict FanDuel NFL classic contest CSV parser.

Contest data is authoritative for player IDs, roster eligibility, salary,
game, team, and status. Never infer missing projection or source timestamps.
"""
import csv
import io
import re

NFL_SLOTS = ("QB", "RB1", "RB2", "WR1", "WR2", "WR3", "TE", "FLEX", "DEF")
NFL_POSITIONS = {"QB", "RB", "WR", "TE", "DEF"}
OUT_FLAGS = {"O", "OUT", "IR", "INACTIVE", "SUSPENDED"}


def _read(raw):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")
    if not isinstance(raw, str) or len(raw) > 8 * 1024 * 1024:
        raise ValueError("NFL CSV must be text smaller than 8 MiB")
    lines = raw.splitlines()
    for start, line in enumerate(lines[:40]):
        columns = [x.strip().lower() for x in next(csv.reader([line]))]
        if {"id", "salary", "game"}.issubset(columns):
            reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
            if len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise ValueError("Ambiguous duplicate CSV headers")
            return list(reader)
    raise ValueError("Missing FanDuel player-list header")


def _field(row, *names):
    cols = {k.strip().lower(): v.strip() for k, v in row.items() if k is not None and v is not None}
    for name in names:
        if name.lower() in cols:
            return cols[name.lower()]
    return ""


def import_nfl_contest(raw, *, expected_contest_id=None):
    """Return full contest pool including out players; never silently drop rows."""
    rows = _read(raw)
    if not rows:
        raise ValueError("Empty contest")
    pool = []
    for row in rows:
        pid = _field(row, "Id")
        if not re.fullmatch(r"\d+-\d+", pid):
            raise ValueError("Invalid FanDuel player ID")
        contest_id = pid.split("-")[0]
        if expected_contest_id is not None and contest_id != str(expected_contest_id):
            raise ValueError("Wrong contest ID")
        pos = _field(row, "Position").upper()
        if pos == "D":
            pos = "DEF"
        if pos not in NFL_POSITIONS:
            raise ValueError(f"Invalid NFL position: {pos}")
        salary_text = _field(row, "Salary").replace("$", "").replace(",", "")
        if not salary_text.isdigit():
            raise ValueError("Invalid salary")
        salary = int(salary_text)
        if salary <= 0 or salary > 60000:
            raise ValueError("Salary out of range")
        name = _field(row, "Nickname", "Player Name") or (
            _field(row, "First Name") + " " + _field(row, "Last Name")).strip()
        team = _field(row, "Team").upper()
        game = _field(row, "Game")
        if not name or not team or not game or not re.search(r"\b" + re.escape(team) + r"\b", game, re.I):
            raise ValueError("Missing name/team or team not in matchup")
        roster = _field(row, "Roster Position", "Roster Eligibility").upper()
        tokens = {x.strip() for x in roster.split("/") if x.strip()}
        expected = {pos} | ({"FLEX"} if pos in {"RB", "WR", "TE"} else set())
        if not tokens or not tokens.issubset(expected) or pos not in tokens:
            raise ValueError("Incorrect NFL roster eligibility")
        flag = _field(row, "Injury Indicator", "Injury Flag").upper()
        pool.append({"player_id": pid, "contest_id": contest_id, "player": name,
                     "salary": salary, "positions": [pos], "roster_eligibility": sorted(tokens),
                     "team": team, "game": game, "status": "out" if flag in OUT_FLAGS else
                     "unknown" if not flag else flag.lower(), "injury_flag": flag})
    ids = [p["player_id"] for p in pool]
    if len(set(ids)) != len(ids) or len({p["contest_id"] for p in pool}) != 1:
        raise ValueError("Duplicate player IDs or mixed contest IDs")
    return pool


def attach_nfl_projections(contest_pool, projections, *, slate_date, source_version):
    """Exact player-ID match only; preserve missing projections as missing."""
    if not isinstance(projections, list):
        raise ValueError("Projections must be a list")
    by_id = {}
    for p in projections:
        pid = p.get("player_id")
        if not pid or pid in by_id:
            raise ValueError("Projection IDs must be present and unique")
        by_id[pid] = p
    if set(by_id) - {r["player_id"] for r in contest_pool}:
        raise ValueError("Projection contains out-of-contest IDs")
    output = []
    for player in contest_pool:
        projection = by_id.get(player["player_id"], {})
        output.append({**player, "slate_date": slate_date, "source_version": source_version,
                       "projection_fd": projection.get("projection_fd"),
                       "asof_utc": projection.get("asof_utc")})
    return output
