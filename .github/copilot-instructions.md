# Copilot instructions (condensed)
Keep edits small, testable, and owned by the module that needs them.

Core rules
- Keep changes <100 lines when possible.
- Export command handlers as `COMMAND_HANDLERS = {}` and callbacks as `CALLBACK_HANDLERS = [...]`.
- For serverless per-invocation entrypoints, register only the command needed and any callbacks required for that invocation.
- Centralize persistence/infra in `api/store.py` and expose simple helpers.

Minimal workflow
1. Write a short todo list and mark one item `in-progress`.
2. Make a focused change with `apply_patch` (<100 lines preferred).
3. Run `get_errors` and fix up to 3 issues; add minimal tests when reasonable.
4. Re-run `get_errors` and tests; include verification notes in the PR.

Quick operational rules
- Preface a batch of edits/tool calls with a one-line why/what/outcome.
- After 3–5 tool calls or edits, give a concise progress update.
- Avoid editing historical/reference files (e.g., `old_bot.py`) unless porting behavior.
- Use `apply_patch` and keep context minimal.

Quick session learnings
- Detect `callback_query` explicitly and treat it as a separate routing case.
- Extract `chat_id` from `message.chat` or `callback_query.message.chat` and return `"no chat id"` if missing.
- Register handlers conditionally:
  - Add `CommandHandler` only when a supported command is present.
  - Add `CALLBACK_HANDLERS` only when update contains `callback_query`.
- Guard early for missing `TELEGRAM_TOKEN` and return a clear status.
- Run `get_errors` after edits and fix up to 3 issues; surface unrelated errors without changing historical files.

Testing & verification
- Run `get_errors` on edited files.
- Include a minimal smoke/unit test for parsing/handler logic when changing routing.

Commit messages
- Use: `<type>(<scope>): short summary` (e.g. `feat(lobby): add lobby callbacks`)

These condensed rules keep automated edits small, safe, and easy to review.

