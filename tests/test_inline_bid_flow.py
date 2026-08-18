import importlib
import types


def _install_fake_redis(monkeypatch):
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

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(redis.StrictRedis, "from_url", staticmethod(lambda url: FakeRedis()))


def test_chosen_inline_result_handler_requests_ai_partner_call_after_human_pass(monkeypatch):
    _install_fake_redis(monkeypatch)

    import api.inline_handlers as inline_handlers
    import api.handlers as handlers
    from api.bridge import Game

    def fake_request_bid_in_chat(bot, game, chat_id):
        calls.append((bot, game, chat_id))

    calls = []
    monkeypatch.setattr(inline_handlers, "request_bid_in_chat", fake_request_bid_in_chat)
    monkeypatch.setattr(inline_handlers, "save_game_to_redis", lambda *args, **kwargs: True)
    monkeypatch.setattr(inline_handlers, "set_user_active_game", lambda *args, **kwargs: True)
    monkeypatch.setattr(inline_handlers, "_get_game_for_user", lambda user_id: (123, game))

    game = Game(1)
    game.add_human(10, "Human")
    for _ in range(3):
        game.add_AI()

    game.phase = Game.BID_PHASE
    game.activePlayer = game.players[0]
    game.declarer = game.players[1]
    game.bid = "1C"

    class FakeResult:
        result_id = "PASS"
        from_user = types.SimpleNamespace(id=10)

    class FakeUpdate:
        chosen_inline_result = FakeResult()

    bot = object()
    context = types.SimpleNamespace(bot=bot)
    update = FakeUpdate()

    # This is the real regression: human passes, auction advances to the declarer's call phase.
    # The handler should continue the flow by asking the AI declarer to choose a partner.
    import asyncio
    asyncio.run(inline_handlers.chosen_inline_result_handler(update, context))

    assert calls, "expected the bot to continue into the AI call phase after a human pass"
    assert game.phase == Game.CALL_PHASE
    assert game.activePlayer is game.declarer
