from datetime import date

from nba_edgehalla_reference import edgehalla_reference


def test_edgehalla_requires_exact_oriented_game_and_keeps_unknown_publication():
    header = '<h1>NBA Minutes Projections: Friday, November 27</h1>'
    fields = '# Player Game MIN PTS REB AST STL BLK TO'.split()
    columns = ''.join(f'<th>{field}</th>' for field in fields)
    good = ('<tr><td>1</td><th><a href="/nba/players/example">Example Player</a>'
            '<span>NYK · PG</span></th><td>@ BOS</td><td>21</td><td>14.3</td>'
            '<td>2</td><td>4</td><td>1</td><td>0.5</td><td>1</td></tr>')
    wrong = good.replace('Example Player', 'Wrong Home').replace('@ BOS', 'vs BOS')
    def board(rows):
        return f'{header}<table><thead><tr>{columns}</tr></thead><tbody>{rows}</tbody></table>'
    games = [dict(awayTeam={'teamTricode': 'NYK'}, homeTeam={'teamTricode': 'BOS'},
                  gameTimeUtc='2026-11-28T00:00:00Z')]
    args = (date(2026,11,27), '2026-11-27T17:00:00Z', games)
    other = good.replace('Example Player', 'Other Player')
    rows = edgehalla_reference(board(good+wrong+other+other), *args)
    assert len(rows) == 1
    assert rows[0]['game'] == 'NYK@BOS'
    assert rows[0]['points'] == 14.3
    assert rows[0]['minutes'] == 21 and rows[0]['as_of'] is None
    assert rows[0]['conditional_on_playing']
