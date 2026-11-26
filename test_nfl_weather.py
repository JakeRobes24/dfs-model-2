import unittest
from datetime import date, timedelta
from unittest.mock import patch

from nfl_weather import collect_nfl_weather, match_schedule, parse_hourly, stamp

DAY = '2026-11-26'
KICK = stamp('2026-11-27T01:20:00Z')
OBSERVED = stamp('2026-11-26T10:00:00Z')
FIRST = stamp('2026-11-26T18:00:00Z')
UPDATE = '2026-11-26T09:00:00Z'


def event(away='KC', home='BUF', kickoff=KICK, venue=None):
    return dict(id='event', date=kickoff.isoformat(), venue=venue or
                dict(id='11938', fullName='Highmark Stadium', indoor=False),
                status={'type': {'name': 'STATUS_SCHEDULED'}},
                competitors=[dict(homeAway=side, team={'abbreviation': club})
                             for side, club in [('home', home), ('away', away)]])


def payload(*competitions):
    return {'events': [{'competitions': competitions}]}


def forecast():
    first = KICK.replace(minute=0)
    periods = []
    for i in range(4):
        start = first + timedelta(hours=i)
        periods.append(dict(startTime=start.isoformat(), endTime=(start + timedelta(hours=1)).isoformat(),
                            temperature=37, temperatureUnit='F', windSpeed='9 to 13 mph',
                            windDirection='NE', shortForecast='Rain',
                            probabilityOfPrecipitation={'unitCode': 'wmoUnit:percent', 'value': 100-i}))
    return {'updateTime': UPDATE, 'periods': periods}


class NFLWeatherTests(unittest.TestCase):
    def test_exact_order_slate_day_and_ambiguous_games(self):
        tomorrow = KICK + timedelta(days=1)
        source = payload(event('BUF', 'KC'), event(kickoff=tomorrow), event())
        self.assertEqual(set(match_schedule(source, date.fromisoformat(DAY), {'KC@BUF'})), {'KC@BUF'})
        self.assertFalse(match_schedule(payload(event(), event()), date.fromisoformat(DAY), {'KC@BUF'}))

    def test_midnight_kickoff_window_and_gust_conversion(self):
        gust = {'updateTime': UPDATE,
                'windGust': {'uom': 'wmoUnit:km_h-1', 'values': [
                    {'validTime': '2026-11-27T01:00:00Z/PT4H', 'value': 55.5}]}}
        updated, hours = parse_hourly(forecast(), KICK, OBSERVED, FIRST, gust)
        self.assertEqual(updated.isoformat(), '2026-11-26T09:00:00+00:00')
        self.assertEqual(len(hours), 4)
        self.assertEqual(len(parse_hourly(forecast(), KICK, OBSERVED, KICK+timedelta(days=1))[1]), 4)
        self.assertEqual(hours[0]['gust_mph'], 34.5)
        self.assertEqual(hours[0]['sustained_wind_mph'], 13)
        mismatched_grid = dict(gust, updateTime='2026-11-26T08:00:00Z')
        self.assertIsNone(parse_hourly(forecast(), KICK, OBSERVED, FIRST, mismatched_grid)[1][0]['gust_mph'])

    def test_stale_future_and_missing_hour_rejected(self):
        sources = [dict(forecast(), updateTime='2026-11-25T09:00:00Z'),
                   dict(forecast(), updateTime='2026-11-26T11:00:00Z'),
                   dict(forecast(), generatedAt='2026-11-26T16:00:00Z'),
                   dict(forecast(), periods=forecast()['periods'][1:])]
        for source in sources:
            with self.subTest(source=source), self.assertRaises(ValueError):
                parse_hourly(source, KICK, OBSERVED, FIRST)

    def test_dome_retractable_outdoor_and_exact_decision_cutoff(self):
        detroit = event('CHI', 'DET', FIRST, dict(id='3727', fullName='Ford Field', indoor=True))
        dallas = event('PHI', 'DAL', FIRST+timedelta(hours=3), dict(id='3687', fullName='AT&T Stadium', indoor=True))
        audit = {'contest_id': '137123', 'contest_sha256': 'abc',
                 'players': [{'game': matchup} for matchup in ('CHI@DET', 'PHI@DAL', 'KC@BUF')]}
        with patch('nfl_weather.fetch_json', return_value=payload(detroit, dallas, event())), \
             patch('nfl_weather.outdoor_forecast', return_value={'status': 'Forecast captured'}) as outdoor:
            receipt = collect_nfl_weather(audit, DAY, cutoff_utc=KICK.isoformat(), clock=lambda: OBSERVED)
            self.assertEqual(receipt['decision_cutoff'], FIRST.isoformat())
            self.assertEqual([x['status'] for x in receipt['games']],
                             ['Fixed indoor', 'Forecast captured', 'Retractable roof unconfirmed'])
            outdoor.assert_called_once()
            self.assertEqual(outdoor.call_args.args[2], FIRST)
            outdoor.reset_mock()
            earlier = collect_nfl_weather(audit, DAY, cutoff_utc=OBSERVED.isoformat(), clock=lambda: OBSERVED)
            self.assertIn('after cutoff', earlier['games'][1]['status'])
            outdoor.assert_not_called()
        with patch('nfl_weather.fetch_json', return_value=payload(detroit, event())), \
             patch('nfl_weather.outdoor_forecast') as outdoor:
            incomplete = collect_nfl_weather(audit, DAY, clock=lambda: OBSERVED)
            self.assertIn('Full contest schedule required', incomplete['games'][1]['status'])
            outdoor.assert_not_called()
