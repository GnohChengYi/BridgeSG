# Project Overview

This repository contains a Telegram bot for playing Bridge. The instructions below are intended for automated contributors and reviewers who will make focused code changes.

## Principles

- Keep changes small and focused. Prefer edits <100 lines and avoid sweeping refactors.
- Prefer clarity and reproducibility: log clearly, validate quickly, and document assumptions.

## Practical rules for automated contributors

- Start with a short todo list (use the repository's task tool when available). Mark one item as "in-progress" and update the list as you work.

- Preface any batch of tool calls or file edits with a one-sentence why/what/outcome summary so reviewers understand intent.

- After several tool calls or when editing multiple files (3-5 calls or >~3 files), provide a concise progress update: what ran, key results, and next steps.

- Enforce required external services at startup: if a dependency is essential (for example Redis is the authoritative state store), fail fast and log a clear error. If you add an early connectivity check (e.g. `ping()`), document an opt-out env var (for CI/dev) so tests can run without external services.

- Treat serverless vs persistent runtimes differently: when the deployment is serverless prefer authoritative external state (Redis) and avoid relying on long-lived in-memory registries; still perform best-effort in-memory cleanup for warm invocations.

- Keep key formats consistent (string vs int). If you change a convention, update usages and state that assumption in the edit note.

- Do not edit reference or historical files (for example `old_bot.py`) except to read them. Port behavior into the active code instead.

- Validate every change quickly: run syntax/import checks (use `get_errors`), and any relevant unit or smoke tests. If failures occur, try up to three targeted fixes; if still failing, report the failing output clearly.

- Avoid leaving unused imports or dead code. Use a quick grep/search or `get_errors` to spot leftovers.

- When adding startup checks or configuration changes, document behavior and provide opt-outs where appropriate for CI/local dev.

- Log actions and exceptions with actionable messages including contextual identifiers (chat id, request id) when helpful for debugging.

- Use `apply_patch` for edits when possible and keep context lines minimal.

These rules are meant to make automated edits safer, easier to review, and reproducible by developers.

## Testing and verification checklist

- Run a syntax/import check on edited files (`get_errors`).
- Run unit tests or a short smoke test if available and relevant.
- If network integrations are required, provide manual test steps and an opt-out for CI if necessary.

## Communication

- Keep commit messages and PR descriptions concise and focused on behavior and validation steps.
- Break larger changes into smaller PRs and include minimal usage notes when required.
