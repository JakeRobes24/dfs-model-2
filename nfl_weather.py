"""Timestamped game weather for NFL research. Does not adjust projections."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import json
import math
import re
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from nfl_daily_audit import game, team
from nfl_projection_review import stamp

ET = ZoneInfo('America/New_York')
SCOREBOARD = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard'
NWS = 'https://api.weather.gov'
MAX_JSON = 2_000_000
# Only venues reviewed against a venue/team source, keyed by exact schedule ID.
VENUES = {
    '11938': ('Highmark Stadium', False, 'outdoor', (42.7731, -78.7922),
              'https://www.buffalobills.com/news/how-to-watch-the-bills-ribbon-cutting-ceremony-at-highmark-stadium'),
    '3752': ('Acrisure Stadium', False, 'outdoor', (40.4467, -80.0158),
             'https://www.steelers.com/schedule/2026/'),
    '3727': ('Ford Field', True, 'fixed indoor', None, 'https://www.fordfield.com/about-ford-field'),
    '3687': ('AT&T Stadium', True, 'retractable roof unconfirmed', None,
             'https://static.www.nfl.com/league/apps/league-site/media-guides/2025/DAL.pdf'),
}


def fetch_json(url):
    request = Request(url, headers={'User-Agent': 'DFS Model 2.0 weather research',
                                    'Accept': 'application/geo+json, application/json'})
    with urlopen(request, timeout=6) as response:
        if response.geturl() != url:
            raise ValueError('Unexpected source redirect.')
        body = response.read(MAX_JSON + 1)
    if len(body) > MAX_JSON:
        raise ValueError('Weather response exceeds size limit.')
    result = json.loads(body)
    if not isinstance(result, dict):
        raise ValueError('Unexpected JSON response.')
    return result


def match_schedule(payload, slate_day, matchups):
    """Use the ordered away/home pair and Eastern slate date from the contest."""
    by_game = defaultdict(list)
    for event in payload['events']:
        for competition in event['competitions']:
            sides = {row['homeAway']: team(row['team']['abbreviation']) for row in competition['competitors']}
            if len(competition['competitors']) != 2 or set(sides) != {'away', 'home'}:
                continue
            matchup = game(f"{sides['away']}@{sides['home']}")
            kickoff = stamp(competition['date'])
            if matchup in matchups and kickoff.astimezone(ET).date() == slate_day:
                by_game[matchup].append(competition)
    return {matchup: records[0] for matchup, records in by_game.items() if len(records) == 1}


def forecast_timestamp(properties, observed, deadline):
    updated = stamp(properties['updateTime'])
    generated = stamp(properties.get('generatedAt', properties['updateTime']))
    if not observed - timedelta(hours=24) <= updated <= generated <= observed <= deadline:
        raise ValueError('Forecast is stale, later than the review, or outside the decision window.')
    return updated


def numeric(value, lower, upper):
    return value if type(value) in (int, float) and math.isfinite(value) and lower <= value <= upper else None


def gust_at(grid, start):
    """Read the unique NWS gust period covering the hourly timestamp."""
    gusts = grid['windGust']
    factors = {'wmoUnit:km_h-1': 0.621371, 'wmoUnit:m_s-1': 2.236936, 'wmoUnit:mi_h-1': 1}
    factor = factors.get(gusts['uom'])
    if factor is None:
        return None
    matches = []
    for period in gusts['values']:
        start_raw, _, duration = period['validTime'].partition('/')
        length = re.fullmatch(r'PT(\d+)H', duration)
        if length is None:
            continue
        left = stamp(start_raw)
        if left <= start < left + timedelta(hours=int(length[1])):
            matches.append(numeric(period['value'], 0, 300))
    return round(matches[0] * factor, 1) if len(matches) == 1 and matches[0] is not None else None


def parse_hourly(properties, kickoff, observed, deadline, grid=None):
    """Extract the hourly bins overlapping kickoff through three hours after."""
    updated = forecast_timestamp(properties, observed, deadline)
    if grid is not None and forecast_timestamp(grid, observed, deadline) != updated:
        grid = None
    end = kickoff + timedelta(hours=3)
    periods = []
    for source in properties['periods']:
        left, right = stamp(source['startTime']), stamp(source['endTime'])
        if right <= kickoff or left >= end:
            continue
        if right-left != timedelta(hours=1):
            raise ValueError('Expected one-hour forecast bins.')
        wind = re.fullmatch(r'(\d{1,3})(?:\s*(?:to|-)\s*(\d{1,3}))? mph', source.get('windSpeed') or '')
        pop = source.get('probabilityOfPrecipitation') or {}
        periods.append((left, right, {
            'start': left.isoformat(), 'end': right.isoformat(),
            'temperature_f': numeric(source.get('temperature'), -100, 150) if source.get('temperatureUnit') == 'F' else None,
            'precipitation_probability_pct': numeric(pop.get('value'), 0, 100) if pop.get('unitCode') == 'wmoUnit:percent' else None,
            'sustained_wind_mph': numeric(int(wind[2] or wind[1]), 0, 160) if wind else None,
            'wind_direction': source.get('windDirection') or None,
            'gust_mph': gust_at(grid, left) if grid is not None else None,
            'forecast': source.get('shortForecast') or None,
        }))
    periods.sort(key=lambda p: p[0])
    if (not periods or periods[0][0] > kickoff or periods[-1][1] < end
            or any(a[1] != b[0] for a, b in zip(periods, periods[1:]))):
        raise ValueError('Incomplete or conflicting kickoff weather coverage.')
    return updated, [item[2] for item in periods]


def outdoor_forecast(coords, kickoff, deadline, clock):
    point_url = f'{NWS}/points/{coords[0]:.4f},{coords[1]:.4f}'
    point = fetch_json(point_url)['properties']
    hourly_url, grid_url = point['forecastHourly'], point['forecastGridData']
    if (re.fullmatch(NWS.replace('.', r'\.') + r'/gridpoints/[A-Z]{3}/\d+,\d+', grid_url) is None
            or hourly_url != grid_url + '/forecast/hourly'):
        raise ValueError('Unexpected NWS grid URL.')
    forecast = fetch_json(hourly_url)['properties']
    observed = clock()
    grid_used = None
    try:
        grid = fetch_json(grid_url)['properties']
        grid_observed = clock()
        if forecast_timestamp(grid, grid_observed, deadline) == forecast_timestamp(forecast, observed, deadline):
            # Invalid/missing gust data should never hide a usable hourly forecast.
            if grid['windGust']['uom'] and isinstance(grid['windGust']['values'], list):
                grid_used = grid
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        updated, hours = parse_hourly(forecast, kickoff, observed, deadline, grid_used)
    except (ValueError, KeyError, TypeError):
        updated, hours = parse_hourly(forecast, kickoff, observed, deadline)
        grid_used = None
    flags = []
    if any((h['precipitation_probability_pct'] or 0) >= 50 for h in hours):
        flags.append('Precipitation')
    if any((h['sustained_wind_mph'] or 0) >= 15 or (h['gust_mph'] or 0) >= 25 for h in hours):
        flags.append('Wind')
    missing = [field for field in ('temperature_f', 'precipitation_probability_pct', 'sustained_wind_mph', 'gust_mph')
               if any(hour[field] is None for hour in hours)]
    return dict(status='Forecast captured' if not missing else 'Forecast captured with missing measurements',
                missing_measurements=missing, point_source=point_url, forecast_source=hourly_url,
                gust_source=grid_url if grid_used is not None else None,
                gust_observed_at=grid_observed.isoformat() if grid_used is not None else None,
                forecast_updated_at=updated.isoformat(), observed_at=observed.isoformat(),
                hours=hours, review_flags=flags)


def collect_nfl_weather(audit, slate_day, *, cutoff_utc=None, clock=None):
    slate_day = date.fromisoformat(slate_day)
    clock = clock or (lambda: datetime.now(timezone.utc))
    requested = stamp(cutoff_utc) if cutoff_utc else None
    matchups = sorted({game(row['game']) for row in audit['players']})
    if not matchups or not all(matchups):
        raise ValueError('Use a reconciled contest with exact matchups.')
    schedule_url = f'{SCOREBOARD}?dates={slate_day:%Y%m%d}'
    schedule = {}
    try:
        schedule = match_schedule(fetch_json(schedule_url), slate_day, matchups)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    schedule_observed = clock()
    first = min((stamp(row['date']) for row in schedule.values()), default=None)
    deadline = min(requested, first) if requested and first else requested or first

    def review(matchup):
        row = dict(game=matchup, status='Schedule matchup unavailable or ambiguous', hours=[])
        event = schedule.get(matchup)
        if not event:
            return row
        kickoff = stamp(event['date'])
        venue = event.get('venue') or {}
        status = event.get('status', {}).get('type', {})
        row.update(kickoff=kickoff.isoformat(), venue=venue.get('fullName'),
                   event_id=event.get('id'), status='Venue exposure unverified')
        verified = VENUES.get(venue.get('id'))
        if not verified or (venue.get('fullName'), venue.get('indoor')) != verified[:2]:
            return row
        _, _, exposure, coords, venue_source = verified
        row.update(exposure=exposure, venue_source=venue_source, status=exposure.capitalize())
        if exposure != 'outdoor':
            return row
        if len(schedule) != len(matchups) or deadline is None:
            row['status'] = 'Full contest schedule required for pre-lock weather'
        elif schedule_observed >= deadline or status.get('name') != 'STATUS_SCHEDULED':
            row['status'] = 'Pre-lock forecast unavailable after cutoff or schedule change'
        else:
            try:
                row.update(outdoor_forecast(coords, kickoff, deadline, clock))
            except (OSError, ValueError, KeyError, TypeError):
                row['status'] = 'No verified hourly forecast for the decision window'
        return row

    with ThreadPoolExecutor(max_workers=min(4, len(matchups))) as workers:
        rows = list(workers.map(review, matchups))
    return dict(contest_id=audit['contest_id'], contest_sha256=audit['contest_sha256'],
                slate_date=slate_day.isoformat(), decision_cutoff=deadline.isoformat() if deadline else None,
                schedule_source=schedule_url, schedule_observed_at=schedule_observed.isoformat(), games=rows)
