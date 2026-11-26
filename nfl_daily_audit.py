"""Read-only FanDuel NFL DAILY coverage audit. No lock or scoring certification."""
import csv
import hashlib
import io
import math
import re
from collections import defaultdict
from nfl_contest_import import import_nfl_contest

TEAMS = dict(item.split(":") for item in (
    "ARI:Arizona Cardinals;ATL:Atlanta Falcons;BAL:Baltimore Ravens;BUF:Buffalo Bills;"
    "CAR:Carolina Panthers;CHI:Chicago Bears;CIN:Cincinnati Bengals;CLE:Cleveland Browns;"
    "DAL:Dallas Cowboys;DEN:Denver Broncos;DET:Detroit Lions;GB:Green Bay Packers;"
    "HOU:Houston Texans;IND:Indianapolis Colts;JAX:Jacksonville Jaguars;KC:Kansas City Chiefs;"
    "LAC:Los Angeles Chargers;LAR:Los Angeles Rams;LV:Las Vegas Raiders;MIA:Miami Dolphins;"
    "MIN:Minnesota Vikings;NE:New England Patriots;NO:New Orleans Saints;NYG:New York Giants;"
    "NYJ:New York Jets;PHI:Philadelphia Eagles;PIT:Pittsburgh Steelers;SEA:Seattle Seahawks;"
    "SF:San Francisco 49ers;TB:Tampa Bay Buccaneers;TEN:Tennessee Titans;WAS:Washington Commanders"
).split(";"))

def norm(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())

TEAM_KEYS = {norm(v): k for k, v in TEAMS.items()}
TEAM_KEYS.update({norm(k): k for k in TEAMS})
TEAM_KEYS.update({"la": "LAR", "jac": "JAX", "wsh": "WAS"})

# Verified against the original Nov 26 contest and DAILY files; never strip
# suffixes indiscriminately or apply NBA aliases to NFL names.
ALIASES = {"91626": ("jamescookiii", "jamescook", "BUF")}

def team(value):
    return TEAM_KEYS.get(norm(value), "")

def game(value):
    parts = [team(p) for p in str(value).split("@")]
    return "@".join(parts) if len(parts) == 2 and all(parts) and parts[0] != parts[1] else ""

def number(value):
    try:
        n = float(str(value).replace("$", "").replace(",", ""))
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None

def raw_bytes(raw):
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if not isinstance(raw, bytes) or len(raw) > 8 * 1024 * 1024:
        raise ValueError("Expected CSV below 8 MiB")
    return raw

def read_daily(raw):
    raw = raw_bytes(raw)
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    if not rows:
        raise ValueError("Empty DAILY export")
    header = [norm(x) for x in rows[0]]
    expected = ["player","team","gameinfo","salary","value","completionsattempts",
                "passingyards","passingtouchdowns","interceptionsthrown","rushingattempts",
                "rushingyards","rushingtouchdowns","receptions","targets","receivingyards",
                "receivingtouchdowns","fantasy","positionrank","overallrank","opponentdefensiverank"]
    if header != expected:
        raise ValueError("Unrecognized NFL DAILY export header")
    out = []
    for i, row in enumerate(rows[1:], 2):
        if not any(row):
            continue
        if len(row) < 5:
            raise ValueError(f"Malformed DAILY row {i}")
        name, raw_team, raw_game, sal, value = row[:5]
        t, g = team(raw_team), game(raw_game)
        if not name or not t or not g or t not in g.split("@"):
            raise ValueError(f"Invalid DAILY identity at row {i}")
        layout, points, candidate = "unrecognized", None, None
        # The original provider export uses a common offense header but
        # ragged 14-field DST / 17-field K rows. Preserve the candidate
        # value separately; no unlabeled field is silently certified.
        if len(row) == 20 and re.fullmatch(r"\d+(?:\.\d+)?/\d+(?:\.\d+)?", row[5]):
            layout = "offense_header"
            points = number(row[16])
        elif len(row) == 14 and norm(name).endswith("dst") and row[-2:] == ["", ""] and all(number(x) is not None for x in row[5:12]):
            layout, candidate = "dst_unlabeled", number(row[11])
        elif len(row) == 17 and row[-2:] == ["", ""] and all(number(x) is not None for x in row[5:15]):
            layout, candidate = "kicker_unlabeled", number(row[14])
        out.append({"row": i, "name": name, "team": t, "game": g,
                    "salary": number(sal), "layout": layout, "projection_fd": points,
                    "unlabeled_fd_candidate": candidate,
                    "rushing_attempts": number(row[9]) if layout == "offense_header" else None,
                    "targets": number(row[13]) if layout == "offense_header" else None})
    return out

def audit_nfl_daily(contest_raw, daily_raw, *, contest_id, single_game=False):
    contest_raw, daily_raw = raw_bytes(contest_raw), raw_bytes(daily_raw)
    pool = import_nfl_contest(contest_raw, expected_contest_id=contest_id, single_game=single_game)
    daily = read_daily(daily_raw)
    keyed = defaultdict(list)
    for d in daily:
        key = "DST" if d["layout"] == "dst_unlabeled" else norm(d["name"])
        keyed[(key, d["team"], d["game"])].append(d)
    contest_keys = []
    for p in pool:
        t, g = team(p["team"]), game(p["game"])
        if not t or not g:
            raise ValueError("Unrecognized contest team or game")
        k = "DST" if p["positions"] == ["DEF"] else norm(p["player"])
        alias = ALIASES.get(p["player_id"].split("-")[-1])
        if alias and (k, t) == (alias[0], alias[2]):
            k = alias[1]
        contest_keys.append((k, t, g))
    counts = {k: contest_keys.count(k) for k in set(contest_keys)}
    used = set()
    output = []
    for p, key in zip(pool, contest_keys):
        matches = keyed.get(key, [])
        issues = []
        d = None
        if len(matches) > 1 or counts[key] > 1:
            issues.append("ambiguous_identity")
        elif not matches:
            issues.append("missing_identity")
        else:
            d = matches[0]
            used.add(d["row"])
            position = p["positions"][0]
            expected = {"DEF": "dst_unlabeled", "K": "kicker_unlabeled"}.get(position, "offense_header")
            if d["layout"] != expected:
                issues.append("position_layout_mismatch")
            if d["salary"] is None:
                issues.append("daily_salary_missing")
            elif d["salary"] != p["salary"]:
                issues.append("daily_salary_mismatch")
            if d["layout"] in {"dst_unlabeled", "kicker_unlabeled"}:
                issues.append("unlabeled_score_requires_review")
            elif d["projection_fd"] is None:
                issues.append("invalid_or_missing_score")
        output.append({**p, "daily_name": d["name"] if d else None,
                       "daily_row": d["row"] if d else None,
                       "daily_salary": d["salary"] if d else None,
                       "projection_fd": d["projection_fd"] if d and "position_layout_mismatch" not in issues else None,
                       "unlabeled_fd_candidate": d["unlabeled_fd_candidate"] if d and "position_layout_mismatch" not in issues else None,
                       "rushing_attempts": d["rushing_attempts"] if d else None,
                       "targets": d["targets"] if d else None,
                       "issues": issues})
    active = [p for p in output if p["status"] != "out"]
    return {"contest_id": str(contest_id), "single_game": single_game,
            "contest_sha256": hashlib.sha256(contest_raw).hexdigest(),
            "daily_sha256": hashlib.sha256(daily_raw).hexdigest(),
            "contest_players": len(pool), "eligible_players": len(active),
            "daily_rows": len(daily), "matched": sum(p["daily_row"] is not None for p in output),
            "eligible_header_scores": sum(p["projection_fd"] is not None for p in active),
            "eligible_unlabeled_candidates": sum(p["unlabeled_fd_candidate"] is not None for p in active),
            "unused_daily_rows": [d["row"] for d in daily if d["row"] not in used],
            "certified": False, "players": output,
            "warning": "Coverage audit only. Capture time, official availability, independent research and unlabeled fields not certified."}
