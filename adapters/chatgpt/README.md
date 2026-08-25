# ChatGPT Adapter

## Work mode and Codex

Distribute Dravux as the included plugin. Plugins are supported in ChatGPT Work on the web and in Work or Codex in the desktop app. For local desktop testing, open the release's `.agents/plugins/marketplace.json`, install Dravux, start a new session, and run the capability preflight.

ChatGPT web Work can use Dravux only after the plugin is shared to that workspace or publicly published. The pre-publication plugin-source ZIP is not a one-click web installer and makes no availability promise for unrelated accounts.

## Ordinary Chat mode

Plugins are not available in ordinary Chat mode. Attaching `SKILL.md`, a ZIP, or the complete folder supplies conversation context only; it does not establish skill discovery, preserve executable paths, or prove that the bundled validators ran.

## Capability boundary

Plugin or skill installation establishes instruction discovery only. It grants no network access, browser, rendered page, DOM, screenshots, keyboard control, repository metadata, or credentials. Declare capabilities from what the session demonstrates and run the preflight every time. `docs/capabilities.md` holds the per-surface matrix; the skill carries `references/capability-matrix.md` and `references/github-evidence.md`. Write audit artifacts outside the skill folder and any extracted release tree by taking the destination from `python3 <skill-root>/scripts/dravux_run.py output-dir`.

If the active surface cannot execute both `dravux_contract.py` and `dravux_run.py`, label any response:

**`UNVALIDATED DRAFT — NOT A DRAVUX RESULT`**

Do not display an automated result or final status as established Dravux output.

Official references:

- <https://learn.chatgpt.com/docs/build-skills>
- <https://learn.chatgpt.com/docs/build-plugins>
