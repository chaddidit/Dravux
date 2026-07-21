# Surface and Evidence Modes

Separate four questions before every run:

1. Can this product discover the Dravux instructions?
2. Can it execute the bundled standard-library validator?
3. What target evidence can it acquire in this session?
4. Which human checks remain outside automation?

Installing a skill answers only the first question.

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
| Claude Chat and Cowork | Upload the dedicated custom-skill ZIP in Customize > Skills | Skills require code execution. Network and page acquisition vary by account policy. Run preflight every session. |
| Claude Code desktop/CLI | Project `.claude/skills/dravux` or plugin | Local validation is supported; browser/DOM tools remain optional capabilities. |
| Codex desktop/CLI | Project `.agents/skills/dravux` or plugin | Local validation is supported; browser/DOM tools remain optional capabilities. |
| ChatGPT desktop Work/Codex | Install from the included local plugin marketplace | Start a new session after install and run preflight. |
| ChatGPT web Work | Install after the plugin is shared to the workspace or publicly published | The pre-publication plugin-source ZIP is not a one-click web installer. |
| Ordinary ChatGPT Chat | No Dravux plugin installation route | Attachment supplies context only. Return `UNVALIDATED DRAFT — NOT A DRAVUX RESULT` if the bundled validator cannot execute. |

Official product references:

- OpenAI: <https://learn.chatgpt.com/docs/build-skills>
- OpenAI: <https://learn.chatgpt.com/docs/build-plugins>
- Anthropic custom skills: <https://support.claude.com/en/articles/12512180-use-skills-in-claude>
- Claude Code skills: <https://code.claude.com/docs/en/slash-commands>

## Required downgrade prompt

State all four items before asking for acceptance:

- Requested mode
- Available and selected mode
- Claims the selected mode permits
- Claims and manual checks it leaves open

If the user does not accept the reduction, stop before target acquisition and produce no audit report.
