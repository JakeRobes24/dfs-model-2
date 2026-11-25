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
    ('RotoGrinders','Automatic','Manual required','Platform-specific projections and opportunity'),
    ('Courtside','Manual research','Not applicable','Prior minutes research; provider independence and fresh data require review'),
    ('PropSims','Automatic','Not established','Same-provider NBA points and minutes'),
    ('Daily Fantasy Fuel','Automatic','Manual research','Platform-specific fantasy projections'),
    ('LineupExperts','Reference + verified upload','Manual required','Projections, comparisons and matchup research'),
    ('Fantasy Team Advisors','Reference + optional archive','Manual research','Points, minutes, ownership and ceiling; partial preview'),
    ('FantasySportsEdge','Reference','Manual research','Projection comparison; upstream overlap unverified'),
    ('DraftEdge','Manual research','Manual research','Projection and lineup comparison; feed unverified'),
    ('RotoQL / stat-api','Manual research','Manual research','Projections, ownership; count shared provenance once'),
    ('Linemate','Manual research','Manual research','Player and matchup validation'),
    ('WalterPicks','Manual research','Manual research','Player and matchup validation'),
    ('FantasyProjections','Identity unresolved','Identity unresolved','Confirm exact provider before numerical use'),
    ('The Fantasy Footballers','Not applicable','Manual required','Weekly roles, matchup, injury and DFS research'),
    ('Fantasy Points','Not established','Manual research','Weekly projections, usage and efficiency'),
    ('4for4','Not applicable','Manual research','NFL projections and matchup research; exact access and provenance require verification'),
    ('FantasySharks','Not applicable','Manual research','Weekly platform-specific projections'),
    ('Upper Hand Fantasy','Not applicable','Manual required','Workload, role and matchup analysis'),
)
AUTOMATIC_NBA = {
    'Official NBA reports / NBA Stats': ('NBA injury report','NBA recent box scores'),
    'RotoWire': ('RotoWire starters and minutes',),
    'NBA House': ('NBA House projected minutes',),
    'RotoGrinders': ('RotoGrinders',),
    'PropSims': ('PropSims',),
    'Daily Fantasy Fuel': ('Daily Fantasy Fuel',),
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
        elif mode == 'Identity unresolved':
            current = 'Identity not verified'
        else:
            current = 'Not verified by automatic refresh; use applicable reference or manual check'
        rows.append({'Source':name,'Integration':mode,'Research purpose':purpose,'Refresh evidence':current})
    return pd.DataFrame(rows,columns=['Source','Integration','Research purpose','Refresh evidence'])
