# Copilot instructions

Keep edits small, testable, and owned by the module that needs them.

## Core architecture

- **Serverless-first**: Redis is canonical store; no in-memory global state.
- Load game via `load_game_from_redis(redis_client, chat_id)`, mutate it, then `save_game_to_redis(...)`.
- Pass Game objects through handler invocations; don't rely on process-level caches.
- Game.from_dict() ensures player.game is set; Player methods raise RuntimeError if player.game is None.

## Module organization

- `api/bridge.py`: core Game/Player logic; no persistence code. Define constants.
- `api/store.py`: Redis load/save helpers; centralize all persistence.
- `api/handlers.py`: command handlers exported as `COMMAND_HANDLERS = {}`.
- `api/lobby.py`: callback handlers exported as `CALLBACK_HANDLERS = [...]`.
- `api/inline_handlers.py`: inline query handlers exported as `INLINE_HANDLERS = [...]`.
- `api/game_utils.py`: reusable utilities.
- `api/bot.py`: webhook entry point; detect update types, register handlers conditionally.

## Workflow

1. **Audit Phase**: Read `NEXT_STEPS.md` and relevant `api/` files before proposing changes.
2. **Implementation**: Mark task as `in-progress`. Make focused changes (`replace_string_in_file`, <100 lines).
3. **Verification**: Run `get_errors`. If dealing with new Telegram types, add `json.dumps()` logging to capture the raw payload.
4. **Documentation**: Mark task completed in `NEXT_STEPS.md`. Provide a concise audit summary (Task status, changes made, next steps).
5. **Commit**: Always provide a structured commit message at the end of the task.

## Operational rules

- Preface tool batches with a one-line intent (e.g., "Adding logging to debug inline query context").
- Avoid editing legacy files unless explicitly porting behavior.
- Run `get_errors` after every file modification.

## Code quality

- **DRY**: Extract duplicate code into helpers.
- **Constants**: Replace magic strings with defined constants (e.g., `Game.CLUBS`).
- **Single Responsibility**: Break large functions into focused helpers (e.g., `_build_bid_results`).
- **Defensive**: Raise explicit errors for missing references (e.g., when a Game object fails to load).

## Telegram bot patterns

- Extract `chat_id` from `message`, `callback_query`, or `inline_query`. Return early if missing.
- **Payload Logging**: For debugging ambiguous Telegram updates, log the full JSON payload using `json.dumps(obj, indent=2)`.
- Conditional registration: Register handlers in `bot.py` based on update types detected.

## Refactoring & Debugging

- If `player.game` is None: verify `Game.from_dict()` back-references.
- Stale state: Force `load_game_from_redis` to avoid process-local stale data.
- **JSON Context**: When debugging inline queries, log raw payloads to identify missing `chat_id` or `chat_type` fields.

## Planning & documentation

- Keep `NEXT_STEPS.md` (<50 lines) as the source of truth for current blockers and tasks.
- Use decision trees for logic: "If X observation → do Y; else do Z."

## Commit messages

- Format: `<type>(<scope>): short summary` (e.g., `feat(bot): add inline query JSON logging`).
- **Constraint**: Always provide a suggested commit message at the end of a completed task.