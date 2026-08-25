# What Dravux can do where

This page answers one question: **on the product you are actually using, what can Dravux do, and what will it refuse to do?**

You do not need to be technical to read it. Start with "The one thing to understand", then find your product in the tables.

## The one thing to understand

Installing or uploading Dravux does not give the assistant any new powers.

Dravux is a set of written instructions plus two small checking programs. It cannot give Claude, Codex, or any other assistant:

- internet access
- a web browser
- the live page a visitor would see, or the page's underlying structure
- screenshots
- keyboard or mouse control of a page
- your commit history, pull requests, or issues
- passwords, tokens, or logins
- permission to use a connector or integration

All of those come from **the product you are using and what you have turned on inside it** — never from a skill.

That is why Dravux runs a capability preflight at the start of every session, and why it sometimes stops before auditing. A stop is Dravux telling you the truth about the evidence available right now.

## Three separate layers, never mixed

Most confusion comes from treating these as one thing. They are three:

| Layer | Question | What it depends on |
|---|---|---|
| **A. Running Dravux** | Can this product find Dravux's instructions and run its checking programs? | How you installed it, and whether code execution is on |
| **B. Repository evidence** | Can it get files, commit history, pull requests, or issues from a code repository? | A GitHub integration you connected, a checkout on your own computer, or your own authorized command-line tool |
| **C. Live website evidence** | Can it open the real, rendered page, inspect its structure, click things, and take screenshots? | A browser capability such as Claude in Chrome, or a browser tool you connected |

Layer A never grants Layer B or Layer C. A product can be perfect at Layer A and have neither of the others.

## How to read the values

| Value | Meaning |
|---|---|
| **Works** | Available on that surface with the normal setup described in the install column. |
| **You connect it** | The surface can do it, but only after *you* enable or connect something. Until you do, Dravux treats it as absent. |
| **Unavailable -> `STATUS`** | Cannot happen on that surface. `STATUS` is the exact preflight result you will see. |

## Panel 1 — Running Dravux (Layer A)

**Before you upload anything to Claude Chat or Cowork:** some organization plans and admin settings turn custom skills or code execution off entirely. If yours does, the upload option may be missing or greyed out, and with code execution off Dravux stops at `UNSUPPORTED` instead of auditing. This is an account setting that Dravux cannot change — ask whoever administers your Claude account to enable custom skills and code execution.

| Surface | Install path | Code execution | Bundled validators |
|---|---|---|---|
| Claude Chat and Cowork | Upload `dravux.zip` under Settings > Capabilities > Skills (labeled Customize > Skills in some versions): "+ Create skill" then "Upload a skill" | **You connect it** — custom skills require code execution to be enabled | Works once code execution is on |
| Claude Code | Copy the skill folder to `.claude/skills/dravux/` in your project, or `~/.claude/skills/dravux/`, or install the plugin | Works | Works |
| Claude Code + connected browser | Same as Claude Code, plus a browser capability connected to the session | Works | Works |
| Claude in Chrome | Not a place skills live. The browser extension adds live-page ability to a Claude surface; that surface still hosts Dravux | Inherited from the host surface | Inherited from the host surface. If the host cannot run them: **Unavailable -> `UNSUPPORTED`** |
| Codex / ChatGPT desktop | Install the plugin from the release's local marketplace file, or copy the skill folder to `.agents/skills/dravux/`. Invoke `$dravux` | Works in Codex mode; varies in Work mode | Works wherever code execution works |
| Codex CLI | Copy the skill folder to `.agents/skills/dravux/` (repository) or `~/.agents/skills/dravux/` (personal) | Works | Works |

If code execution, the bundled files, or the validators are missing, preflight returns **`UNSUPPORTED`** (exit `4`) and Dravux produces no audit result at all. Ordinary ChatGPT Chat has no plugin route: attaching the folder supplies conversation context only, and any answer must be labeled `UNVALIDATED DRAFT — NOT A DRAVUX RESULT`.

## Panel 2 — Getting the website (Layer C)

An ordinary "audit this website" request needs `RENDERED_DOM`. Anything less is a reduced mode you have to accept in writing first.

| Surface | Converted text (`SOURCE_TEXT`) | Exact source (`RAW_SOURCE`) | Rendered page (`RENDERED_BROWSER`) | Structure and interaction (`RENDERED_DOM` / `INTERACTIVE`) | Screenshots |
|---|---|---|---|---|---|
| Claude Chat and Cowork | **You connect it** — depends on account and policy | **You connect it** — only if a session tool returns unconverted source | **You connect it** in Cowork with a browser capability; otherwise **Unavailable -> `LIMITATION_ACK_REQUIRED`** | Same as the previous column | **You connect it** with a browser capability; otherwise **Unavailable -> `LIMITATION_ACK_REQUIRED`** |
| Claude Code | **You connect it** — a fetch tool you permit | **You connect it** for remote pages; local files always work | **Unavailable -> `LIMITATION_ACK_REQUIRED`** | **Unavailable -> `LIMITATION_ACK_REQUIRED`** | **Unavailable -> `LIMITATION_ACK_REQUIRED`** |
| Claude Code + connected browser | Works | Works | Works | Works | Works |
| Claude in Chrome | Works | Works | Works | Works | Works |
| Codex / ChatGPT desktop | **You connect it** — sandbox network access is off by default | **You connect it** — same condition | **Unavailable -> `LIMITATION_ACK_REQUIRED`** | **Unavailable -> `LIMITATION_ACK_REQUIRED`** | **Unavailable -> `LIMITATION_ACK_REQUIRED`** |
| Codex CLI | **You connect it** — sandbox network access is off by default | **You connect it** — same condition | **Unavailable -> `LIMITATION_ACK_REQUIRED`** | **Unavailable -> `LIMITATION_ACK_REQUIRED`** | **Unavailable -> `LIMITATION_ACK_REQUIRED`** |

Claude in Chrome can read, click, navigate, type, take screenshots, and read console output, network requests, and page structure. It requires a browser extension with a broad permission grant that is **not** per-site, so treat it as a deliberate decision rather than a default. It is available on paid plans and is generally available in Claude Cowork and Claude Code, and in beta in the Chrome browser itself.

## Panel 3 — Repository evidence (Layer B)

| Surface | Selected repository files | Commit history, pull requests, issues |
|---|---|---|
| Claude Chat and Cowork | **You connect it** — the GitHub integration, added from the "+" button in a chat or in project knowledge | **Unavailable -> `LIMITATION_ACK_REQUIRED`** — the integration syncs file names and contents only |
| Claude Code | Works from a checkout on your computer | **You connect it** — your own clone supplies commit history; pull requests and issues need your own authorized command-line tool or connector |
| Claude Code + connected browser | Works | **You connect it** — either as above, or by reading the pages in the browser, recorded as rendered-page evidence |
| Claude in Chrome | Works — as rendered pages | **You connect it** — readable as rendered pages, never as repository metadata |
| Codex / ChatGPT desktop | Works from a checkout | **You connect it** — same conditions as Claude Code |
| Codex CLI | Works from a checkout | **You connect it** — same conditions as Claude Code |

The Claude GitHub integration is a **file** integration. Its own documentation states that only file names and contents on a specific branch are synced, and that commit history, pull requests, and other metadata are not retrieved. Dravux never presents it as a general GitHub layer. For the full mapping of evidence need to route, see the skill's `references/github-evidence.md`.

## What the stop messages mean

| Result | Exit code | Plain meaning | What to do next |
|---|---|---|---|
| `READY` | `0` | The evidence Dravux needs is actually available. | Nothing. The audit proceeds. |
| `LIMITATION_ACK_REQUIRED` | `3` | Dravux can run, but only with weaker evidence than the request needs. | Either say you accept the named reduced mode and its limits, or move the audit to a surface that has the missing capability. **This is not a failed audit** — it is a correct capability stop, and no accessibility conclusion has been claimed yet. |
| `UNSUPPORTED` | `4` | Dravux cannot establish a run here at all — usually no code execution, missing bundled files, or the validators cannot run. | Move to a surface that can run the bundled programs. |
| `INVALID` | `1` | The preflight claimed a stronger evidence mode than the session's declared capabilities allow. | Lower the selected mode to what the session can genuinely acquire. Never raise it to make the stop go away. |
| load or execution error | `2` | The preflight file could not be read or the program could not run. | Fix the file path or the runtime, then re-run. |

## How Dravux picks the mode (deterministic, not a judgement call)

1. The requested mode comes from the request. Any ordinary website audit requests at least `RENDERED_DOM`.
2. The declared session capability sets a **ceiling**: no acquisition means `CONTRACT_ONLY`, files only means `FILE_STATIC`, converted text means `SOURCE_TEXT`, exact source means `RAW_SOURCE`, and so on up to interactive browsing.
3. The selected mode is the **strongest mode that is at or below both the ceiling and the requested mode**. Nothing weaker is chosen when something stronger is genuinely available.
4. If the selected mode is weaker than the requested mode and you have not accepted that reduction, preflight stops at `LIMITATION_ACK_REQUIRED`.
5. Declaring a selected mode above the ceiling is a contract violation, not a shortcut: preflight returns `INVALID`.

## Where reports are written

Dravux never writes audit artifacts into the skill folder, a source checkout, or an extracted release tree — that contaminates a tree whose contents are verified against a manifest. Ask the skill for a safe directory instead:

```bash
python3 <skill-root>/scripts/dravux_run.py output-dir
```

It prints an absolute path as its last line and creates the directory. Add `--audit-id <slug>` for a per-audit subfolder, `--base <path>` to choose where it starts looking, and `--strict` to refuse instead of redirecting when the starting point is inside a protected tree.

## Verified against published documentation

These statements were checked against Anthropic's published support articles while this page was written:

- Custom skills in Claude Chat and Cowork are uploaded as a ZIP through the skills settings screen, and the feature requires code execution to be enabled. **Verified.**
- The Claude GitHub integration syncs only file names and contents for a repository branch, and does not retrieve commit history, pull requests, or other metadata. **Verified.**
- Claude in Chrome reads, clicks, navigates, types, takes screenshots, and can read console output, network requests, and page state; it requires a broad, non-per-site permission grant; it is offered on paid plans, generally available in Claude Cowork and Claude Code, and in beta in the Chrome browser. **Verified.**

The exact wording of a settings menu label, every "you connect it" value, and the note about organization plans and admin settings switching custom skills or code execution off are **assumed, not verified against a published article**. So can every value change with product updates and with your organization's policy. Treat all of it as assumed until your own preflight proves it. That is the entire point of running the preflight every session rather than trusting this table.

## Related reading

- `plugins/dravux/skills/dravux/references/capability-matrix.md` — the copy that travels inside the skill
- `plugins/dravux/skills/dravux/references/surface-modes.md` — evidence modes and the required downgrade prompt
- `plugins/dravux/skills/dravux/references/github-evidence.md` — evidence need to route mapping
- `plugins/dravux/skills/dravux/references/input-capabilities.md` — what each input type can and cannot establish
