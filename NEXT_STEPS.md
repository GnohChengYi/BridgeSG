# Next Steps for BridgeSG Bot

## ✅ Completed 

### Phase 1: Inline handlers infrastructure (Nov 20, 2025)
- `inline_handlers.py`, helpers in `store.py`, `game_utils.py`

### Phase 2: Webhook integration in `bot.py` (Nov 20, 2025)
- Detects & routes inline queries and chosen_inline_results

### Phase 3: Inline Query JSON Logging (Mar 14, 2026)
- Added `json.dumps()` logging in `bot.py` for:
  - `inline_query` full payload (line 96)
  - `chosen_inline_result` full payload (line 99)
- Captures these objects whenever they appear in webhook pipeline
- Ready for testing in group chat to determine chat context availability

## 🔴 Blocked: Inline Query Context

**Problem:** Inline queries may not have chat context → can't route to correct game when user is in multiple games.

**Current log (DM context):**
```json
{"inline_query": {"chat_type": "sender", "from": {"id": 12345}}}  // ← No chat_id!
```

### 🧪 Next Action: RUN LOGGING TEST IN GROUP CHAT

Start game in group → type `@BotName` → check logs for:
```
inline_query payload: {...}
chosen_inline_result payload: {...}
```

Verify if `inline_query.chat` or `inline_query.from.id` contains group context.

### Solutions (depends on test results):

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
- `api/bot.py` - Webhook routing (logging completed ✅)
- `api/inline_handlers.py` - Bid/card selection
- `api/bridge.py` - Game logic
- `api/store.py` - Redis helpers

