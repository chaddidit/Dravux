# ChatGPT Adapter

## Work mode and Codex

Distribute Dravux as the included plugin. Plugins are supported in ChatGPT Work on the web and in Work or Codex in the desktop app. For local desktop testing, open the release's `.agents/plugins/marketplace.json`, install Dravux, start a new session, and run the capability preflight.

ChatGPT web Work can use Dravux only after the plugin is shared to that workspace or publicly published. The pre-publication plugin-source ZIP is not a one-click web installer and makes no availability promise for unrelated accounts.

## Ordinary Chat mode

Plugins are not available in ordinary Chat mode. Attaching `SKILL.md`, a ZIP, or the complete folder supplies conversation context only; it does not establish skill discovery, preserve executable paths, or prove that the bundled validators ran.

If the active surface cannot execute both `dravux_contract.py` and `dravux_run.py`, label any response:

**`UNVALIDATED DRAFT — NOT A DRAVUX RESULT`**

Do not display an automated result or final status as established Dravux output.

Official references:

- <https://learn.chatgpt.com/docs/build-skills>
- <https://learn.chatgpt.com/docs/build-plugins>
