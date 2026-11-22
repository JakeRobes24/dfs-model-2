"""Point-in-time NBA market evidence for an uploaded contest."""
from collections import defaultdict
from datetime import timedelta
from statistics import median
import math

import pandas as pd

from slate_import import matchup_key, player_key, team_code


def fair_over_probability(over, under):
    """Remove the two-way overround from decimal odds at the same line."""
    if not all(math.isfinite(value) and value > 1 for value in (over, under)):
        raise ValueError('Expected decimal odds above one.')
    return (1 / over) / (1 / over + 1 / under)


def upcoming_markets(events, slate, as_of, games):
    expected = {matchup_key(game) for game in games}
    by_game = defaultdict(list)
    for event in events:
        away, home = map(team_code, (event.get('away_team', ''), event.get('home_team', '')))
        game = f'{away}@{home}'
        tip = pd.to_datetime(event.get('commence_time'), utc=True, errors='coerce')
        if (not away or not home or away == home or matchup_key(game) not in expected
                or pd.isna(tip) or tip <= as_of or tip.tz_convert('America/New_York').date() != slate):
            continue
        by_game[matchup_key(game)].append((game, event))
    return [entries[0] for entries in by_game.values() if len(entries) == 1]


def fresh_stamp(market, book, as_of):
    stamp = pd.to_datetime(market.get('last_update') or book.get('last_update'),
                           utc=True, errors='coerce')
    return stamp if pd.notna(stamp) and as_of - timedelta(hours=2) <= stamp <= as_of else None


def game_market_evidence(events, slate, as_of, games):
    """Summarize fresh same-book totals and spreads for upcoming contest games."""
    result = []
    for game, event in upcoming_markets(events, slate, as_of, games):
        home = game.split('@')[1]
        books = {}
        for book in event.get('bookmakers', []):
            quotes = {}
            for market in book.get('markets', []):
                stamp = fresh_stamp(market, book, as_of)
                if stamp is None:
                    continue
                quotes[market.get('key')] = (market.get('outcomes', []), stamp)
            if not book.get('key') or not {'totals', 'spreads'} <= quotes.keys():
                continue
            totals, totals_at = quotes['totals']
            spreads, spreads_at = quotes['spreads']
            total = {item.get('name'): item.get('point') for item in totals}
            spread = {team_code(item.get('name', '')): item.get('point') for item in spreads}
            if len(totals) != 2 or len(spreads) != 2 or set(total) != {'Over', 'Under'} or set(spread) != set(game.split('@')):
                continue
            values = [*total.values(), *spread.values()]
            if not all(type(value) in (int, float) and math.isfinite(value) for value in values):
                continue
            if total['Over'] != total['Under'] or abs(sum(spread.values())) > .001 or not 100 <= total['Over'] <= 350:
                continue
            game_total, home_spread = total['Over'], spread[home]
            if abs(home_spread) >= game_total:
                continue
            prices = {item['name']: item.get('price') for item in totals}
            fair_over = (fair_over_probability(prices['Over'], prices['Under'])
                         if all(type(price) in (int, float) and math.isfinite(price) and price > 1
                                for price in prices.values()) else None)
            quotes_at = min(totals_at, spreads_at)
            previous = books.get(book['key'])
            if previous is None or quotes_at > previous[0]:
                books[book['key']] = (quotes_at, game_total, home_spread, fair_over)
        if books:
            total = median(quote[1] for quote in books.values())
            home_spread = median(quote[2] for quote in books.values())
            fair = [quote[3] for quote in books.values() if quote[1] == total and quote[3] is not None]
            result.append(dict(game=game, total=total, home_spread=home_spread,
                               implied_home=(total - home_spread) / 2,
                               implied_away=(total + home_spread) / 2,
                               fair_over_pct=100 * median(fair) if fair else None, bookmakers=len(books), oldest_quote=min(q[0] for q in books.values()).isoformat()))
    return pd.DataFrame(result)


PROP_MARKETS = {'player_points': 'Points', 'player_rebounds': 'Rebounds', 'player_assists': 'Assists'}


def player_market_evidence(events, slate, as_of, pool):
    """Return same-line two-way prop quotes keyed to unambiguous contest players."""
    identities = defaultdict(list)
    for player in pool.itertuples():
        identities[matchup_key(player.game), player_key(player.fanduel_name)].append(player)
    rows = defaultdict(list)
    for game, event in upcoming_markets(events, slate, as_of, set(pool.game)):
        for book in event.get('bookmakers', []):
            if not book.get('key'):
                continue
            for market in book.get('markets', []):
                key = market.get('key')
                if key not in PROP_MARKETS:
                    continue
                stamp = fresh_stamp(market, book, as_of)
                if stamp is None:
                    continue
                pairs = defaultdict(list)
                for quote in market.get('outcomes', []):
                    name = quote.get('description')
                    side, line, price = (quote.get(k) for k in ('name', 'point', 'price'))
                    if (isinstance(name, str) and name.strip() and side in ('Over', 'Under')
                            and type(line) in (int, float) and 0 <= line <= 150
                            and type(price) in (int, float) and math.isfinite(price) and price > 1):
                        pairs[player_key(name), line].append((side, price))
                for (name, line), outcomes in pairs.items():
                    player = identities[matchup_key(game), name]
                    prices = dict(outcomes)
                    if len(player) == 1 and len(outcomes) == 2 and set(prices) == {'Over', 'Under'}:
                        person = player[0]
                        rows[person.fanduel_id, key, book['key']].append(dict(
                            fanduel_id=person.fanduel_id, player=person.fanduel_name, game=game,
                            stat=PROP_MARKETS[key], line=line, bookmaker=book['key'],
                            quoted_at=stamp.isoformat(),
                            fair_over_pct=100 * fair_over_probability(prices['Over'], prices['Under'])))
    # Multiple main lines for the same player and book are ambiguous.
    return pd.DataFrame([quotes[0] for quotes in rows.values() if len(quotes) == 1])
