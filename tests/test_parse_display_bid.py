import os

import redis


class FakeRedis:
    def ping(self):
        return True

    def set(self, *args, **kwargs):
        return True

    def get(self, *args, **kwargs):
        return None

    def delete(self, *args, **kwargs):
        return True

    def exists(self, *args, **kwargs):
        return 0

    def scan_iter(self, *args, **kwargs):
        return []


os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
redis.StrictRedis.from_url = staticmethod(lambda url: FakeRedis())

from api.game_utils import parse_display_bid, parse_display_card


def test_parse_display_bid_club():
    assert parse_display_bid('1♣️') == '1C'


def test_parse_display_bid_pass():
    assert parse_display_bid('PASS') == 'PASS'


def test_parse_display_bid_no_trump():
    # Some clients may render no-trump with a 🚫 emoji
    assert parse_display_bid('1🚫') == '1N'


def test_parse_display_bid_card_display():
    # Telegram may send the inline selection back as a plain message like '6♦️'
    # which must be converted to the canonical card code 'D6'.
    assert parse_display_card('6♦️') == 'D6'
    assert parse_display_bid('6♦️') == 'D6'
