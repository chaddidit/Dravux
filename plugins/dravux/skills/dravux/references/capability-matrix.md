# Capability Matrix

Operational copy of the surface capability truth, carried inside the skill so a standalone upload stays self-contained. The expanded human-facing version lives in the project at `docs/capabilities.md`; do not depend on it at run time.

## The rule that generates every row

Installing, uploading, or invoking this skill establishes **instruction discovery only**. A skill cannot grant network egress, a browser, a rendered page, DOM or accessibility-tree access, computed styles, screenshots, keyboard or pointer control, GitHub commit/PR/issue metadata, credentials, or connector authorization. Those come from the host product and from what the user has enabled. Declare capabilities from what the session actually demonstrates, never from what the surface is usually able to do.

Keep three layers separate in every statement:

- **A. Skill installation and invocation** — discovery, bundled files, code execution, validator execution.
- **B. Repository evidence acquisition** — files, history, pull requests, issues.
- **C. Live rendered website acquisition and interaction** — rendered page, DOM, styles, screenshots, scripted interaction.

Layer A never implies B or C. Never answer a Layer B or C question with a Layer A fact.

## Values

- **Works** — available with the normal setup for that surface.
- **Connect** — the user must enable or connect something first; until then, declare it absent.
- **No -> `STATUS`** — unavailable on that surface; `STATUS` is the preflight result the user will see.

## Layer A — running the skill

**Before you upload anything to Claude Chat or Cowork:** some organization plans and admin settings turn custom skills or code execution off entirely. If yours does, the upload option may be missing or greyed out, and with code execution off Dravux stops at `UNSUPPORTED` instead of auditing. This is an account setting that Dravux cannot change — ask whoever administers your Claude account to enable custom skills and code execution. Tell the user this plainly rather than letting them retry a blocked upload, and do not treat it as a Dravux fault.

| Surface | Install path | Code execution | Bundled validators |
|---|---|---|---|
| Claude Chat / Cowork | Upload `dravux.zip` in the skills settings screen (Settings > Capabilities > Skills, labeled Customize > Skills in some versions) | Connect — custom skills require code execution enabled | Works once code execution is on |
| Claude Code | `.claude/skills/dravux/`, `~/.claude/skills/dravux/`, or plugin | Works | Works |
| Claude Code + connected browser | As Claude Code, plus a connected browser capability | Works | Works |
| Claude in Chrome | Not a skill host; adds live-page capability to a host Claude surface | Inherited from host | Inherited; if the host cannot run them, No -> `UNSUPPORTED` |
| Codex / ChatGPT desktop | Local plugin marketplace, or `.agents/skills/dravux/` | Works in Codex mode; varies in Work mode | Works wherever code execution works |
| Codex CLI | `.agents/skills/dravux/` or `~/.agents/skills/dravux/` | Works | Works |

Ordinary ChatGPT Chat has no plugin route. An attached folder is conversation context only; if the bundled validators cannot execute, return `UNVALIDATED DRAFT — NOT A DRAVUX RESULT`.

## Layer C — live website acquisition

| Surface | `SOURCE_TEXT` | `RAW_SOURCE` | `RENDERED_BROWSER` | `RENDERED_DOM` / `INTERACTIVE` | Screenshots |
|---|---|---|---|---|---|
| Claude Chat / Cowork | Connect (account and policy dependent) | Connect (only if a session tool returns unconverted source) | Connect in Cowork with a browser capability; else No -> `LIMITATION_ACK_REQUIRED` | As previous column | Connect with a browser capability; else No -> `LIMITATION_ACK_REQUIRED` |
| Claude Code | Connect (permitted fetch tool) | Connect for remote; local files always | No -> `LIMITATION_ACK_REQUIRED` | No -> `LIMITATION_ACK_REQUIRED` | No -> `LIMITATION_ACK_REQUIRED` |
| Claude Code + connected browser | Works | Works | Works | Works | Works |
| Claude in Chrome | Works | Works | Works | Works | Works |
| Codex / ChatGPT desktop | Connect (sandbox network off by default) | Connect (same condition) | No -> `LIMITATION_ACK_REQUIRED` | No -> `LIMITATION_ACK_REQUIRED` | No -> `LIMITATION_ACK_REQUIRED` |
| Codex CLI | Connect (sandbox network off by default) | Connect (same condition) | No -> `LIMITATION_ACK_REQUIRED` | No -> `LIMITATION_ACK_REQUIRED` | No -> `LIMITATION_ACK_REQUIRED` |

## Layer B — repository evidence

| Surface | Selected repository files | Commit history / PRs / issues |
|---|---|---|
| Claude Chat / Cowork | Connect — GitHub integration (file names and contents only) | No -> `LIMITATION_ACK_REQUIRED` |
| Claude Code | Works from a local checkout | Connect — the user's own clone, authorized CLI, or connector |
| Claude Code + connected browser | Works | Connect — as above, or read the pages as rendered-page evidence |
| Claude in Chrome | Works as rendered pages | Connect — readable as rendered pages, never as repository metadata |
| Codex / ChatGPT desktop | Works from a local checkout | Connect — as Claude Code |
| Codex CLI | Works from a local checkout | Connect — as Claude Code |

Read [github-evidence.md](github-evidence.md) before promising any repository evidence.

## Deterministic mode routing

Route to the strongest mode the session can actually supply. Do not deliberate; apply in order.

1. Set `requested_mode` from the request. A website audit request is at least `RENDERED_DOM`; the preflight contract rejects a lower `requested_mode` for a `WEBSITE` target.
2. Set the ceiling from the demonstrated acquisition capability: `NONE` -> `CONTRACT_ONLY`, `FILES_ONLY` -> `FILE_STATIC`, `CONVERTED_TEXT` -> `SOURCE_TEXT`, `RAW_SOURCE` -> `RAW_SOURCE`, `RENDERED_BROWSER` -> `RENDERED_BROWSER`, `RENDERED_DOM` -> `RENDERED_DOM`, `INTERACTIVE_BROWSER` -> `INTERACTIVE`.
3. Set `selected_mode` to the strongest mode at or below both the ceiling and `requested_mode`. Never select a weaker mode when a stronger one is genuinely available, and never select above the ceiling — that is a contract violation returning `INVALID` (exit `1`), not a shortcut.
4. Missing code execution, missing bundled files, unavailable validator execution, or a failed bundle self-test returns `UNSUPPORTED` (exit `4`) regardless of acquisition.
5. `selected_mode` weaker than `requested_mode` without `limitation_acknowledged` returns `LIMITATION_ACK_REQUIRED` (exit `3`).
6. Otherwise `READY` (exit `0`).

## Preflight stop copy

When preflight returns `LIMITATION_ACK_REQUIRED`, tell the user, in plain language:

- what strength of evidence the request needs, and what this session can actually get;
- what the reduced mode would still allow, and what it leaves unproven;
- the two next actions: accept the reduced mode and its limits, or move the audit to a surface that has the missing capability;
- that **a correct capability stop is not a failed audit** — no accessibility conclusion has been made, and nothing has been claimed about the target.

Do not acquire the target, do not produce a report, and do not continue automatically. When preflight returns `UNSUPPORTED`, return `UNVALIDATED DRAFT — NOT A DRAVUX RESULT` and the exact next action.
