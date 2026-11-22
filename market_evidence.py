"""Point-in-time NBA market evidence for an uploaded contest."""
from collections import defaultdict
from datetime import timedelta
from statistics import median
import math

import pandas as pd

from slate_import import matchup_key, team_code


def fair_over_probability(over, under):
    """Remove the two-way overround from decimal odds at the same line."""
    if not all(math.isfinite(value) and value > 1 for value in (over, under)):
        raise ValueError('Expected decimal odds above one.')
    return (1 / over) / (1 / over + 1 / under)


def game_market_evidence(events, slate, as_of, games):
    """Summarize fresh same-book totals and spreads for upcoming contest games."""
    expected = {matchup_key(game) for game in games}
    by_game = defaultdict(list)
    for event in events:
        away, home = map(team_code, (event.get('away_team', ''), event.get('home_team', '')))
        game = f'{away}@{home}'
        tip = pd.to_datetime(event.get('commence_time'), utc=True, errors='coerce')
        if (not away or not home or away == home or matchup_key(game) not in expected
                or pd.isna(tip) or tip <= as_of or tip.tz_convert('America/New_York').date() != slate):
            continue
        by_game[game].append((event, home))

    result = []
    for game, candidates in by_game.items():
        if len(candidates) != 1:
            continue
        event, home = candidates[0]
        books = {}
        for book in event.get('bookmakers', []):
            quotes = {}
            for market in book.get('markets', []):
                stamp = pd.to_datetime(market.get('last_update') or book.get('last_update'),
                                       utc=True, errors='coerce')
                if pd.isna(stamp) or not as_of - timedelta(hours=2) <= stamp <= as_of:
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
