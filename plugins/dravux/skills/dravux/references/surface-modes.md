# Surface and Evidence Modes

Separate five questions before every run:

1. Can this product discover the Dravux instructions?
2. Can it execute the bundled standard-library validator?
3. What live website evidence can it acquire in this session?
4. What repository evidence can it acquire in this session?
5. Which human checks remain outside automation?

Installing a skill answers only the first question. Questions 3 and 4 are separate capabilities with separate routes; never infer one from the other. [capability-matrix.md](capability-matrix.md) holds the per-surface answers and the deterministic routing rules; [github-evidence.md](github-evidence.md) holds the repository routes.

## Evidence modes

| Mode | Minimum evidence | Allowed conclusion |
|---|---|---|
| `CONTRACT_ONLY` | Bundled validator and a supplied report | Report structure only; no target accessibility claim |
| `FILE_STATIC` | Supplied portable file plus a capable parser | Static artifact observations within declared parser limits |
| `SOURCE_TEXT` | Converted text or Markdown retrieval | Potential advisory hypotheses only; always `INCOMPLETE` |
| `RAW_SOURCE` | Exact HTML/source with a reproducible acquisition receipt | Static markup/source findings; no rendered or interaction claim |
| `RENDERED_BROWSER` | Rendered page and recorded screenshots | Visual-state observations; no unrecorded DOM semantics |
| `RENDERED_DOM` | Rendered DOM/accessibility tree/computed-style evidence | Tool-supported rendered checks; manual checks remain |
| `INTERACTIVE` | Rendered DOM plus scripted interaction evidence | Scripted behavior only; still not human AT or conformance proof |

An ordinary request to “audit this website” requests at least `RENDERED_DOM`. Selecting a lower mode requires explicit user acknowledgement before acquisition.

## Product surfaces

| Surface | Distribution | Operational boundary |
|---|---|---|
| Claude Chat and Cowork | Upload the dedicated custom-skill ZIP in the skills settings screen (Settings > Capabilities > Skills, labeled Customize > Skills in some versions) | Skills require code execution to be enabled. Network and page acquisition vary by account policy. Rendered-page capability exists only where a browser capability is connected. Run preflight every session. |
| Claude Code desktop/CLI | Project `.claude/skills/dravux` or plugin | Local validation is supported; browser/DOM tools remain optional capabilities. |
| Claude Code with a connected browser | As Claude Code, plus a browser capability connected to the session | Rendered browser, DOM, interaction, and screenshots become available. Confirm per session; a connection that existed yesterday is not evidence today. |
| Claude in Chrome | Not a skill host. The extension adds live-page capability to a host Claude surface | Reads, clicks, navigates, types, screenshots, and reads console/network/page state. Requires a broad, non-per-site permission grant. Validator execution is inherited from the host surface; if the host cannot run it, the run is `UNSUPPORTED`. |
| Codex desktop/CLI | Project `.agents/skills/dravux` or plugin | Local validation is supported; sandbox network access is off by default; browser/DOM tools remain optional capabilities. |
| ChatGPT desktop Work/Codex | Install from the included local plugin marketplace | Start a new session after install and run preflight. |
| ChatGPT web Work | Install after the plugin is shared to the workspace or publicly published | The pre-publication plugin-source ZIP is not a one-click web installer. |
| Ordinary ChatGPT Chat | No Dravux plugin installation route | Attachment supplies context only. Return `UNVALIDATED DRAFT — NOT A DRAVUX RESULT` if the bundled validator cannot execute. |

Official product references:

- OpenAI: <https://learn.chatgpt.com/docs/build-skills>
- OpenAI: <https://learn.chatgpt.com/docs/build-plugins>
- Anthropic custom skills: <https://support.claude.com/en/articles/12512180-use-skills-in-claude>
- Claude Code skills: <https://code.claude.com/docs/en/slash-commands>
- Claude GitHub integration (files only): <https://support.claude.com/en/articles/10167454-use-the-github-integration>
- Claude in Chrome (live rendered pages): <https://support.claude.com/en/articles/12012173-get-started-with-claude-in-chrome>

## Required downgrade prompt

State all five items before asking for acceptance:

- Requested mode
- Available and selected mode, and the specific capability that is missing
- Claims the selected mode permits
- Claims and manual checks it leaves open
- That this stop is a correct capability result, not a failed audit, and that nothing has yet been claimed about the target

Offer both next actions: accept the reduced mode and its limits, or move the audit to a surface that has the missing capability. If the user does not accept the reduction, stop before target acquisition and produce no audit report. Never set the acknowledgement on the user's behalf.
