# Copilot instructions
Keep edits small, testable, and owned by the module that needs them.

## Core architecture
- **Serverless-first**: Redis is canonical store; no in-memory global state (Game.games, Player.players removed).
- Load game via `load_game_from_redis(redis_client, chat_id)`, mutate it, then `save_game_to_redis(...)`.
- Pass Game objects through handler invocations; don't rely on process-level caches.
- Game.from_dict() ensures player.game is set; Player methods raise RuntimeError if player.game is None.

## Module organization
- `api/bridge.py`: core Game/Player logic; no persistence code. Define constants (Game.CLUBS, Game.SPADES, etc).
- `api/store.py`: Redis load/save helpers; centralize all persistence.
- `api/handlers.py`: command handlers exported as `COMMAND_HANDLERS = {}`.
- `api/lobby.py`: callback handlers exported as `CALLBACK_HANDLERS = [...]`.
- `api/inline_handlers.py`: inline query handlers exported as `INLINE_HANDLERS = [...]`.
- `api/game_utils.py`: reusable utilities (formatting, DM notifications, AI bidding loops).
- `api/bot.py`: webhook entry point; detect update types, register handlers conditionally.

## Workflow
1. Write short todo list; mark one item `in-progress`.
2. Make focused change with `replace_string_in_file` (<100 lines preferred).
3. Run `get_errors`; fix up to 3 issues.
4. Mark todo completed; give concise progress update after 3–5 tool calls.

## Operational rules
- Preface tool batches with one-line why/what/outcome.
- After edits/tool calls, report progress briefly (delta updates only).
- Avoid editing legacy/reference files (e.g., `old_bot.py`) unless explicitly porting behavior.
- Always run `get_errors` after file modifications to catch issues immediately.

## Code quality
- **DRY principle**: Extract duplicate code into helpers (e.g., `_get_suit_thumb_url()` for thumb URLs).
- **Use constants**: Replace magic strings with Game.CLUBS, Game.NO_TRUMP, etc.
- **Simplify naming**: Remove unnecessary wrapper functions (e.g., `_translate_bid` → `translate_bid`).
- **Single responsibility**: Break large functions into focused helpers (`_build_bid_results()`, `_handle_bid_selection()`).
- **Early returns**: Reduce nesting; validate and return early for error cases.

## Telegram bot patterns
- Extract `chat_id` from `message.chat` or `callback_query.message.chat`; return early if missing.
- **Update type detection**: Check for `message`, `callback_query`, `inline_query`, `chosen_inline_result`.
- **Conditional handler registration** (serverless):
  - `CommandHandler` when supported command present
  - `CALLBACK_HANDLERS` when `callback_query` detected
  - `INLINE_HANDLERS` when `inline_query` or `chosen_inline_result` detected
- Guard early for missing `TELEGRAM_TOKEN`.

## Game flow (auto-progression)
- On lobby full: start game, persist, remove join keyboard, DM hands, post bid prompt.
- AI turns processed automatically in loops; announce to chat.
- AI partner selection handled inline when declarer is AI.
- Bid phase: inline queries show valid bids → user selects → `player.make_bid()` → persist → continue loop.

## Refactoring principles
- Separation of concerns: extract utilities into appropriate modules.
- Defensive programming: raise explicit errors for missing references vs. silent fallback scans.
- Clear error messages guide correct usage (e.g., "Load game from Redis and ensure player.game is set").
- When user questions design, acknowledge concerns before implementing; verify assumptions with tests.

## Testing & verification
- Run `get_errors` on edited files after changes.
- Add comprehensive logging when investigating new Telegram update types.
- Surface unrelated errors without modifying historical files.

## Debugging serverless issues
- If player.game is None: ensure Game.from_dict() was called and sets player back-references.
- If state is stale: check Redis load/save calls; avoid relying on process-local state.
- Race conditions: acceptable under low concurrency; add optimistic locking (version field) if needed.
- For inline queries: log full JSON structure to understand context availability across chat types.

## Planning & documentation
- When planning large features, create concise TODO in `NEXT_STEPS.md` (<50 lines).
- Identify blockers clearly; list test scenarios needed before implementation.
- Provide decision trees: "If X test shows Y, do Z; otherwise do W."
- Keep summaries brief; focus on actionable items.

## Commit messages
- Format: `<type>(<scope>): short summary` (e.g., `refactor(bridge): remove in-memory registries`).

These rules keep edits small, serverless-safe, maintainable, and easy to review.

