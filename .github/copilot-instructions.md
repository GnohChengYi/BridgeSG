# Copilot instructions
Keep edits small, testable, and owned by the module that needs them.

## Core architecture
- **Serverless-first**: Redis is the canonical store; no in-memory global state (Game.games, Player.players removed).
- Load game via `load_game_from_redis(redis_client, chat_id)`, mutate it, then `save_game_to_redis(...)`.
- Pass Game objects through handler invocations; don't rely on process-level caches.
- Game.from_dict() ensures player.game is set; Player methods raise RuntimeError if player.game is None.

## Module organization
- `api/bridge.py`: core Game/Player logic; no persistence code.
- `api/store.py`: Redis load/save helpers; centralize all persistence.
- `api/handlers.py`: command handlers exported as `COMMAND_HANDLERS = {}`.
- `api/lobby.py`: callback handlers exported as `CALLBACK_HANDLERS = [...]`.
- `api/game_utils.py`: reusable game utilities (hand formatting, DM notifications, AI bidding loops).

## Workflow
1. Write short todo list; mark one item `in-progress`.
2. Make focused change with `apply_patch` (<100 lines preferred).
3. Run `get_errors`; fix up to 3 issues.
4. Mark todo completed; give concise progress update after 3–5 tool calls.

## Operational rules
- Preface tool batches with one-line why/what/outcome.
- After edits/tool calls, report progress briefly (delta updates only).
- Avoid editing legacy/reference files (e.g., `old_bot.py`) unless explicitly porting behavior.
- Use `apply_patch`; keep context minimal (3–5 lines before/after target).

## Telegram bot patterns
- Extract `chat_id` from `message.chat` or `callback_query.message.chat`; return early if missing.
- Detect `callback_query` explicitly; treat as separate routing case.
- Register handlers conditionally per invocation (serverless):
  - Add `CommandHandler` only when supported command present.
  - Add `CALLBACK_HANDLERS` only when update contains `callback_query`.
- Guard early for missing `TELEGRAM_TOKEN`.

## Game flow (auto-progression)
- On lobby full: start game, persist, remove join keyboard, DM hands, post bid prompt.
- AI turns processed automatically in loops; announce to chat.
- AI partner selection handled inline when declarer is AI.

## Refactoring principles
- Separation of concerns: extract utilities (e.g., hand formatting → game_utils).
- Defensive programming: raise explicit errors for missing references vs. silent fallback scans.
- Clear error messages guide correct usage (e.g., "Load game from Redis and ensure player.game is set").

## Testing & verification
- Run `get_errors` on edited files after changes.
- Add minimal unit/integration tests when changing routing or core logic.
- Surface unrelated errors without modifying historical files.

## Debugging serverless issues
- If player.game is None: ensure Game.from_dict() was called and sets player back-references.
- If state is stale: check Redis load/save calls; avoid relying on process-local state.
- Race conditions: acceptable under low concurrency; add optimistic locking (version field) if needed.

## Commit messages
- Format: `<type>(<scope>): short summary` (e.g., `refactor(bridge): remove in-memory registries`).

These rules keep edits small, serverless-safe, and easy to review.

