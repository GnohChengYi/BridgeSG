# Next Steps for BridgeSG Bot

## ✅ Completed (Nov 20, 2025)
- Phase 1: Inline handlers infrastructure (`inline_handlers.py`, helpers in `store.py`, `game_utils.py`)
- Phase 2: Webhook integration in `bot.py` (detects & routes inline queries)

## 🔴 Blocked: Inline Query Context

**Problem:** Inline queries may not have chat context → can't route to correct game when user is in multiple games.

**Current log (DM context):**
```json
{"inline_query": {"chat_type": "sender", "from": {"id": 12345}}}  // ← No chat_id!
```

### 🧪 Next Action: TEST IN GROUP CHAT

Add to `bot.py`:
```python
logger.info("inline_query: %s", json.dumps(inline_query, indent=2))
logger.info("chosen_inline_result: %s", json.dumps(chosen_inline_result, indent=2))
```

Start game in group → type `@BotName` → check if `inline_query` contains chat_id.

### Solutions (depends on test):

**A) Group queries have chat_id** → Extract chat_id from `inline_query`, fix `inline_handlers.py`

**B) No chat_id available** → Implement query parsing:
- `@BotName -123456` → Parse chat_id from query text
- `@BotName` → Show game selector if multiple games

**C) Simplest** → Enforce one-game-per-user rule in `Game.add_human()`

## 📋 After Unblocking

1. Test full bid flow: join → bid → AI auto-bid → partner selection
2. Implement card play phase completion
3. Add trick completion & game conclusion logic

## 📁 Key Files
- `api/bot.py` - Webhook routing
- `api/inline_handlers.py` - Bid/card selection
- `api/bridge.py` - Game logic
- `api/store.py` - Redis helpers
