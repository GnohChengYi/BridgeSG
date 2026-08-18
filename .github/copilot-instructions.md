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
2. **Session Memory (for multi-step debugging)**: Create `/memories/session/debug_<issue>.md` immediately. Record hypotheses with confidence levels, evidence gathered, and what was tested. Update it as you progress.
3. **Implementation**: Mark task as `in-progress`. Make focused changes (`replace_string_in_file`, <100 lines). After EACH file edit, run `get_errors` to verify no breakage.
   - Use the configured system interpreter from `configure_python_environment`. Do not create or rely on a `venv` unless the user explicitly requests it.
   - If dealing with new Telegram types, add `json.dumps()` logging to capture the raw payload.
4. **Verification**: 
   - Run targeted regression tests to confirm the fix works.
   - Then run the FULL test suite (`pytest tests/`) to catch unintended regressions before marking complete.
5. **Documentation**: **MANDATORY** — Update `NEXT_STEPS.md` with task completion status, what was fixed, and remaining work. This is the single source of truth for task state.
6. **Commit**: Always provide a structured commit message matching the actual changes made.

## Operational rules

- Preface tool batches with a one-line intent (e.g., "Adding logging to debug inline query context").
- Avoid editing legacy files unless explicitly porting behavior.
- Run `get_errors` after every file modification.
- When issuing terminal commands, confirm the shell state first. If the terminal is in a Python REPL, exit with `exit()` or `quit()` before sending shell commands.

### Terminal execution best practices
- **PowerShell vs bash syntax**: Windows PowerShell does NOT support bash heredocs (`<<EOF`) or the same pipe semantics. If terminal command fails with syntax errors, immediately try `mcp_pylance_mcp_s_pylanceRunCodeSnippet` instead.
- **When to use direct Python snippets**: For any one-off reproduction, verification, or diagnostic checks, prefer the Python snippet tool over terminal commands. It avoids shell quoting and syntax issues entirely.
- **Terminal for side effects only**: Reserve terminal commands for operations that require actual shell state (git, build steps, package installs) or when explicitly building infrastructure.

## Code quality

- **DRY**: Extract duplicate code into helpers. When multiple functions share identical mappings or transformations (e.g., suit symbol normalization), consolidate into a shared constant or utility function.
- **Constants**: Replace magic strings with defined constants (e.g., `Game.CLUBS`).
- **Single Responsibility**: Break large functions into focused helpers (e.g., `_build_bid_results`).
- **Defensive**: Raise explicit errors for missing references (e.g., when a Game object fails to load).
- **Refactoring Opportunities**: During implementation, if you notice duplicated logic between functions, document it in your session memory for the next refactoring pass (don't refactor mid-fix unless it's in the same module).

## Telegram bot patterns

- Extract `chat_id` from `message`, `callback_query`, or `inline_query`. Return early if missing.
- **Payload Logging**: For debugging ambiguous Telegram updates, log the full JSON payload using `json.dumps(obj, indent=2)`.
- Conditional registration: Register handlers in `bot.py` based on update types detected.

## Refactoring & Debugging

### Root-cause diagnosis strategy
1. **Static code analysis first**: Read the relevant code paths end-to-end before running anything. State transitions, guard conditions, and control flow are often visible without execution.
2. **Form hypotheses with confidence levels**: Before building any test or reproduction, write out 2-3 hypotheses about the root cause and assign confidence (0-100%). This focuses investigation.
3. **Session memory (MANDATORY for multi-step debugging)**: Create `/memories/session/debug_<issue>.md` upfront. Record hypotheses with confidence levels, evidence gathered, what was tested, and what was ruled out. Update it as progress is made. This prevents redundant exploration and clarifies the reasoning trail.
4. **Minimal reproduction before full test suite**: Verify the hypothesis with the simplest possible script (mocked dependencies, direct method calls). Do NOT build pytest harness until the fix is confirmed to work.

### When to build tests vs. when to skip
- **Build tests (full pytest)**: After confirming the fix works, only if the fix involves code paths that will be modified again or need regression coverage.
- **Skip full tests**: For one-off bug fixes in stable code. A focused unit-level check is sufficient to verify the fix doesn't regress.
- **Environment constraints**: If Redis or other infrastructure is not available in the test environment, mock it at the import level rather than trying to work around it.
- **Full Test Suite (MANDATORY)**: Before completing a task, always run `pytest tests/` to verify no unintended regressions in other modules. Only targeted tests can miss broader issues.

- If `player.game` is None: verify `Game.from_dict()` back-references.
- Stale state: Force `load_game_from_redis` to avoid process-local stale data.
- **JSON Context**: When debugging inline queries, log raw payloads to identify missing `chat_id` or `chat_type` fields.

## Planning & documentation

- Keep `NEXT_STEPS.md` (<50 lines) as the source of truth for current blockers and tasks.
- Use decision trees for logic: "If X observation → do Y; else do Z."
- **Session memory for debugging**: When investigating a bug with multiple hypotheses, use `/memories/session/` to:
  - Record the initial symptom and hypotheses with confidence levels
  - Log evidence as it's gathered (code paths reviewed, test results, state transitions observed)
  - Track what was tried and ruled out
  - This prevents redundant exploration and provides clarity on the reasoning chain

## Commit messages

- Format: `<type>(<scope>): short summary` (e.g., `feat(bot): add inline query JSON logging`).
- **Constraint**: Always provide a suggested commit message at the end of a completed task.