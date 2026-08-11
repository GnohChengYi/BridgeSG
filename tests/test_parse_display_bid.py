from api.game_utils import parse_display_bid


def test_parse_display_bid_club():
    assert parse_display_bid('1♣️') == '1C'


def test_parse_display_bid_pass():
    assert parse_display_bid('PASS') == 'PASS'


def test_parse_display_bid_no_trump():
    # Some clients may render no-trump with a 🚫 emoji
    assert parse_display_bid('1🚫') == '1N'
