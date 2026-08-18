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


def test_request_bid_in_chat_saves_game_and_prompts_human_after_ai_partner_call(monkeypatch):
    import asyncio

    import api.game_utils as game_utils
    from api.bridge import Game

    game = Game(1)
    game.add_human(10, "Human")
    for _ in range(3):
        game.add_AI()

    ai = game.players[1]
    human = game.players[0]
    game.players = [ai, human, game.players[2], game.players[3]]
    game.activePlayer = ai
    game.declarer = ai
    game.phase = Game.CALL_PHASE
    game.bid = "1S"
    game.trump = ""
    game.partnerCard = None

    human.hand = ["CA", "H2", "D2", "S2", "C2", "H3", "D3", "S3", "C3", "H4", "D4", "S4", "C4"]
    ai.hand = ["SA", "SK", "SQ", "SJ", "ST", "S9", "S8", "S7", "S6", "S5", "S4", "S3", "S2"]

    class FakeBot:
        def __init__(self):
            self.messages = []

        async def send_message(self, **kwargs):
            self.messages.append(kwargs)
            return None

    bot = FakeBot()
    save_calls = []
    prompt_messages = []

    def fake_partner(self, card='SA'):
        game.phase = Game.PLAY_PHASE
        game.partnerCard = 'CA'
        game.activePlayer = human
        return 'CA'

    def fake_save_game_to_redis(redis_client, chat_id, game_obj):
        save_calls.append((chat_id, game_obj.phase, game_obj.activePlayer.name if game_obj.activePlayer else None))
        return True

    monkeypatch.setattr(type(ai), 'call_partner', fake_partner)
    monkeypatch.setattr(game_utils, 'save_game_to_redis', fake_save_game_to_redis)

    asyncio.run(game_utils.request_bid_in_chat(bot, game, 123))

    assert save_calls, "expected game state to be saved after the AI partner call"
    assert game.phase == Game.PLAY_PHASE
    assert game.activePlayer is human
    assert any("your turn to play!" in message.get("text", "") for message in bot.messages)
