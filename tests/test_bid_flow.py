import asyncio
import types

from api.bridge import Game
from api import inline_handlers


def test_chosen_inline_result_handler_continues_into_ai_call_phase_after_human_pass(monkeypatch):
    game = Game(1)
    game.add_human(100, "Human")
    game.add_AI()
    game.add_AI()
    game.add_AI()
    game.start()

    human = game.players[0]
    ai = game.players[1]
    game.activePlayer = human
    game.phase = Game.BID_PHASE
    game.bid = Game.PASS

    requests = []

    class FakeBot:
        pass

    class FakeResult:
        result_id = Game.PASS
        from_user = types.SimpleNamespace(id=human.id)

    class FakeUpdate:
        chosen_inline_result = FakeResult()

    async def fake_request_bid_in_chat(bot, game_obj, chat_id):
        requests.append((chat_id, game_obj.phase, game_obj.activePlayer.name if game_obj.activePlayer else None))
        game_obj.phase = Game.CALL_PHASE
        game_obj.activePlayer = ai
        game_obj.declarer = ai
        game_obj.bid = "1C"

    monkeypatch.setattr(inline_handlers, "_get_game_for_user", lambda user_id: (123, game))
    monkeypatch.setattr(inline_handlers, "save_game_to_redis", lambda *args, **kwargs: True)
    monkeypatch.setattr(inline_handlers, "set_user_active_game", lambda *args, **kwargs: True)
    monkeypatch.setattr(inline_handlers, "request_bid_in_chat", fake_request_bid_in_chat)

    asyncio.run(
        inline_handlers.chosen_inline_result_handler(FakeUpdate(), types.SimpleNamespace(bot=FakeBot()))
    )

    assert requests == [(123, Game.CALL_PHASE, ai.name)]
    assert game.phase == Game.CALL_PHASE
    assert game.activePlayer is ai
    assert game.declarer is ai
