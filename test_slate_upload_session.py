from slate_upload_session import SlateUpload, select_upload_pair


def test_exact_retained_pair_can_recover_missing_widget_values():
    contest = SlateUpload('contest.csv', b'contest')
    daily = SlateUpload('daily.csv', b'daily')
    pair = (contest, daily)
    assert select_upload_pair(contest, daily, None) == (pair, False)
    assert select_upload_pair(None, daily, pair) == (pair, True)
    assert select_upload_pair(contest, None, pair) == (pair, True)
    assert select_upload_pair(None, None, pair) == (pair, True)
    assert select_upload_pair(None, None, None) == (None, False)


def test_new_or_empty_upload_is_not_silently_mixed_with_previous_pair():
    contest = SlateUpload('contest.csv', b'contest')
    daily = SlateUpload('daily.csv', b'daily')
    changed = SlateUpload('daily.csv', b'changed')
    pair = (contest, daily)
    assert select_upload_pair(None, changed, pair) == (None, False)
    assert select_upload_pair(contest, changed, pair) == ((contest, changed), False)
    assert select_upload_pair(contest, SlateUpload('daily.csv', b''), pair) == (None, False)
