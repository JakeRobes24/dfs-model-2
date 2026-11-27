"""Persistent research checklist, distinct from numerical source acceptance.

The saved project index and rolling readiness plan are the source of this registry.
An implemented adapter is not proof of current slate coverage.
"""
import pandas as pd

# name, NBA integration, NFL integration, research purpose
SOURCES = (
    ('Official NBA reports / NBA Stats','Automatic','Not applicable','Availability, official box scores, recent rotations and results'),
    ('Official NFL reports / statistics','Not applicable','Manual required','Availability, active/inactive, workload and verified results'),
    ('RotoWire','Automatic','Manual research','Minutes, lineups, roles and news'),
    ('NBA House','Automatic','Not applicable','Minutes and rotation estimates'),
    ('RotoGrinders','Automatic','Manual required','Platform-specific projections and opportunity; public sample only, full board subscription required'),
    ('Courtside','Manual research','Not applicable','Morning historical minutes/stat reference only; no injury, rest, starter or late trade updates; do not count as live consensus without verification'),
    ('PropSims','Automatic','Public weekly reference','NBA paired points and minutes. NFL market-informed FanDuel median and ceiling with exact schedule checks'),
    ('Edgehalla','Public minutes reference','Not applicable','Conditional minutes and box-score estimates derived from historical season and recent player logs. Publication time unverified'),
    ('Daily Fantasy Fuel','Automatic','Manual research','Platform-specific fantasy projections; public board does not expose projected minutes'),
    ('LineupExperts','Reference + verified upload','Manual required','Public projected stat lines; verified timestamp required for numerical use; licensed API documented'),
    ('Fantasy Team Advisors','Reference + optional archive','Manual research','Points, minutes, ownership, ceiling and teammate-absence splits; limited public preview'),
    ('FantasySportsEdge','Reference','Manual research','Dated FanDuel points including lower salaries; aggregates multiple undisclosed sources; reference only'),
    ('DraftEdge','Manual research','Manual research','Projection and lineup comparison; public board masks projections and does not show paired minutes; authorized feed unverified'),
    ('RotoQL / stat-api','Manual research','Manual research','Projections, ownership; STAT-API documents paired NBA minutes and full stat lines with input timestamp; API key and access tier required; count shared provenance once'),
    ('Linemate','Manual research','Manual research','App-based player trends and matchup checks; no verified public projection feed'),
    ('WalterPicks','Manual research','Manual research','App-based player projections and matchup validation; no verified public dated feed'),
    ('MatchWiz','Reference','Not established','Dated lineup minutes and partial PTS/REB/AST; FanDuel optimizer board separately available but exact current slate and timestamp unverified; provenance unverified'),
    ('TheCapper','Manual research','Not established','Dated conditional minutes and partial box-score projections; public table omits blocks; assumes player plays; exact slate date required; independent provenance unverified'),
    ('KeelStats','Reference','Not established','Public dated Tonight minutes and historical L10/starts/usage; returning players omitted from redistribution; reference only'),
    ('FantasyProjections','Identity unresolved','Identity unresolved','Confirm exact provider before numerical use'),
    ('The Fantasy Footballers','Not applicable','Manual required','Weekly roles, matchup, injury and DFS research'),
    ('Fantasy Points','Not established','Manual research','Weekly projections, usage and efficiency'),
    ('4for4','Not applicable','Public weekly reference','Visible FanDuel by-position points and component previews; full DFS coverage requires authorized subscription access'),
    ('FantasySharks','Not applicable','Manual research','Weekly platform-specific projections'),
    ('Upper Hand Fantasy','Not applicable','Manual required','Workload, role and matchup analysis'),
)
# Verified public access paths; links are not evidence of current coverage.
# Recovered historical reference paths are not proof of present-day availability.
HISTORICAL_RESEARCH_LINKS = {
    'MatchWiz': 'https://matchwiz.ai/nba/lineups',
    'TheCapper': 'https://thecapper.io/nba/projections/',
    'KeelStats': 'https://keelstats.com/nba/usage',
}
RESEARCH_LINKS = {
    'MatchWiz': 'https://matchwiz.ai/nba/lineups',
    'TheCapper': 'https://thecapper.io/nba/projections/',
    'KeelStats': 'https://keelstats.com/nba/usage',
    'LineupExperts': 'https://www.lineupexperts.com/basketball/projections?flt_pos=Utility&flt_proj_time_period=Today',
    'Fantasy Team Advisors': 'https://fantasyteamadvisors.com/guides/nba-usage-bump/',
    'FantasySportsEdge': 'https://fantasysportsedge.com/nba/projections',
    'DraftEdge': 'https://draftedge.com/nba/nba-daily-projections/',
    'RotoQL / stat-api': 'https://stat-api.com/docs/data-dictionary/nba/',
    'Linemate': 'https://linemate.io/',
    'WalterPicks': 'https://www.walterpicks.com/',
    'Courtside': 'https://courtside.higgsfield.app/projections',
    '4for4': 'https://www.4for4.com/dfs-legacy-generators',
    'Edgehalla': 'https://www.edgehalla.com/fantasy-basketball/projections/today/minutes',
}
AUTOMATIC_NBA = {
    'Official NBA reports / NBA Stats': ('NBA injury report','NBA recent box scores'),
    'RotoWire': ('RotoWire starters and minutes',),
    'NBA House': ('NBA House projected minutes',),
    'RotoGrinders': ('RotoGrinders',),
    'PropSims': ('PropSims',),
    'Daily Fantasy Fuel': ('Daily Fantasy Fuel',),
}

NBA_FORECAST_PROVIDERS = {
    'daily-fantasy-fuel': 'Daily Fantasy Fuel',
    'lineupexperts': 'LineupExperts',
    'nba-house': 'NBA House',
    'propsims': 'PropSims',
    'rotogrinders': 'RotoGrinders',
    'rotowire': 'RotoWire',
}


def research_checklist(sport, source_status=()):
    """Every saved source remains visible; unattempted sources never look checked."""
    if sport not in ('NBA','NFL'):
        raise ValueError('Registry currently covers NBA and NFL; MLB inventory is unfinished.')
    status = dict(source_status)
    rows = []
    for name,nba,nfl,purpose in SOURCES:
        mode = nba if sport == 'NBA' else nfl
        if mode in ('Not applicable','Not established'):
            continue
        labels = AUTOMATIC_NBA.get(name,()) if sport == 'NBA' else ()
        if labels:
            current = ' | '.join(f'{label}: {status.get(label,"Not checked this refresh")}' for label in labels)
        elif sport == 'NBA' and name in ('LineupExperts', 'FantasySportsEdge', 'Fantasy Team Advisors', 'KeelStats', 'MatchWiz') and name in status:
            current = status[name]
        elif mode == 'Identity unresolved':
            current = 'Identity not verified'
        else:
            current = 'Not verified by automatic refresh; use applicable reference or manual check'
        rows.append({'Source':name,'Integration':mode,'Research purpose':purpose,'Refresh evidence':current,
                     'Verified access link': RESEARCH_LINKS.get(name, ''),
                     'Historical reference link': HISTORICAL_RESEARCH_LINKS.get(name, '')})
    return pd.DataFrame(rows,columns=['Source','Integration','Research purpose','Refresh evidence','Verified access link','Historical reference link'])


def predictive_coverage(sport, *, matched=None, captured=None):
    """Label records in the selected archive independently of provider accessibility.

    Matched counts use (provider, metric) because one player can contribute to
    multiple metrics. Captured counts describe forecast rows awaiting outcomes.
    """
    matched = matched or {}
    captured = captured or {}
    checklist = research_checklist(sport)[['Source', 'Integration']]
    aliases = NBA_FORECAST_PROVIDERS if sport == 'NBA' else {}
    metrics = {}
    for (provider, metric), count in matched.items():
        if count > 0:
            metrics.setdefault(aliases.get(provider, provider), []).append(f'{metric} ({count})')
    checklist['Matched forecast rows by metric'] = checklist.Source.map(
        lambda source: ', '.join(sorted(metrics.get(source, ()))))
    checklist['Forecast rows awaiting outcomes'] = checklist.Source.map(captured).fillna(0).astype(int)
    return checklist.assign(Evidence=checklist.apply(
        lambda row: 'Matched outcomes' if row['Matched forecast rows by metric'] else
        'Captured forecasts' if row['Forecast rows awaiting outcomes'] else 'No comparable rows in this archive',
        axis=1))
