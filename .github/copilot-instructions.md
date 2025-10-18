# Project overview

This repository contains a Telegram bot for playing Bridge. The guidance below
is written for automated contributors and reviewers who will make focused code
changes in this project.

## Core principles

- Keep changes small and focused. Prefer edits under ~100 lines and avoid
	sweeping refactors in a single PR.
- Favor clarity and reproducibility: log clearly, validate quickly, and record
	assumptions made by automated edits.

## Practical conventions (project-specific, assistant-friendly)

These are pragmatic rules that worked well in this repository. They are
intentionally concrete but avoid being prompt-specific.

- Command handlers
	- Declare an explicit mapping (command -> handler) in the handlers module and
		import that mapping into the bot entrypoint. This makes wiring and testing
		straightforward.

- Persistence and infra
	- Centralize persistence/infra checks in a single module (for example
		`api/store.py`) which constructs the client and exposes minimal helpers
		(create/save/load/exists). Expose a module-level client for convenience.
	- Fail fast on required services but support an env opt-out so CI/local runs
		can skip network checks (e.g., `DISABLE_REDIS_CHECK=1`).

- Serverless vs persistent runtimes
	- For per-invocation handlers, register only the CommandHandler needed for
		the incoming update instead of registering the whole command surface.
	- Provide a small utility to parse command tokens from message text.

- Edits and verification
	- Keep automated edits small (<100 lines) and split larger changes.
	- Verification checklist to run before finalizing changes:
		1. Create a short todo list and mark one item `in-progress`.
		2. Run static checks (syntax/import) with `get_errors` and fix up to three
			 targeted issues automatically. If more remain, stop and report.
		3. Add or update minimal unit tests for changed logic (happy path + one
			 edge case) where feasible.
		4. Re-run static checks and tests.

- Commits, logs, and tests
	- Keep commit messages concise and copyable using:

		<type>(<scope>): short summary

		- One-line: main actions (move/rename/extract/fix)
		- One-line: verification (get_errors/tests passed)

	- Log with contextual identifiers (chat id, request id) when helpful.
	- Prefer unit tests for parsing/handler logic; leave integrations for follow-ups.

## Operational rules for automated contributors

- Start with a short todo list (use repo task tool). Mark one todo as
	`in-progress` and update it as you work.
- Preface a batch of edits or tool calls with a one-sentence summary (why/what/outcome).
- After 3–5 tool calls or edits across multiple files, provide a concise progress
	update (what ran, key results, next steps).
- Avoid editing historical reference files (e.g., `old_bot.py`) except to read
	and port behavior into active code.
- Use `apply_patch` for edits and keep context lines minimal.

## Testing and verification checklist (summary)

- Run `get_errors` on edited files.
- Run unit tests or a short smoke test where relevant.
- If network integrations are required, provide manual test steps and an opt-out
	for CI if necessary.

## Communication

- Keep PR descriptions focused and include verification notes.
- Break larger changes into smaller PRs and include minimal usage notes when required.

These instructions are aimed at making automated edits safe, testable, and
easy to review in this project.
