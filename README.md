# Dravux

**Accessibility checks that tell you what they actually looked at.**

Dravux is an add-on for an AI assistant. You ask it to check a page, a design export, or a code
snippet for accessibility barriers — the things that stop people using screen readers, keyboards,
magnification, captions, or reduced motion. Dravux makes the assistant declare, before it starts,
what it can genuinely see in your current session. It keeps "the automated check passed" separate
from "a person confirmed this", it requires evidence anyone can reproduce, and it never claims that
software alone proves a site is accessible or legally compliant.

It is not a scanner and not a certification. It is a way to stop an assistant from guessing.

## Support and issue reporting

For bugs, documentation problems, and feature requests, open a
[GitHub issue](https://github.com/chaddidit/Dravux/issues). Do not include secrets, private data, or
sensitive vulnerability details in a public issue.

## Portable core and adapters

Dravux's standard-library Python validators, JSON contracts, fixtures, and offline CLI are
agent-neutral. Claude, Codex, ChatGPT, and GitHub Copilot support are thin adapters around that
same core. Any new host must declare its capabilities and return `UNSUPPORTED` or `INCOMPLETE`
instead of inferring browser, DOM, screenshot, keyboard, or screen-reader evidence it cannot
actually obtain.

Validators and contracts are OS-agnostic (Python standard library). macOS and Linux have the
supported POSIX installers today; Windows is exercised in CI so failures show up without a local
Windows machine. Native Windows shell installers are still a separate portability task — see
[docs/portability.md](docs/portability.md). A standalone GUI or browser extension is a separate
product layer; both can reuse the same contracts and validators.

## Choose your path

New here? **[START_HERE.md](START_HERE.md)** walks through all four routes step by step.

| You are... | Route | Start with |
|---|---|---|
| Using Claude in a browser or Cowork, no terminal | Upload one small file | [INSTALLERS/Claude-Chat-Cowork/](INSTALLERS/Claude-Chat-Cowork/) |
| Using the Codex or ChatGPT desktop app | Install as a local plugin | [INSTALLERS/Codex-ChatGPT/](INSTALLERS/Codex-ChatGPT/) |
| Comfortable in Terminal (Claude Code, Codex CLI) | Run the installer | [Installation options](#installation-options) below |
| Maintaining or reviewing Dravux itself | Run the test suite | [Reference and architecture](#reference-and-architecture) |

## Verify a downloaded artifact before using it

Do not extract, upload, install, or run a downloaded Dravux archive until its digest has been checked.
Keep the archive unopened, calculate its SHA-256 digest, and compare it with the exact matching line in
the accompanying `SHA256SUMS.txt`:

```bash
shasum -a 256 Dravux-1.0.2.zip
shasum -a 256 dravux.zip
shasum -a 256 Dravux-OpenAI-Plugin-Source.zip
```

Check only the archive you actually received. That fingerprint check catches corruption in transit; it
does **not** prove who published the file. Dravux 1.0.2 has no cryptographic publisher signature.
**Publisher authenticity was not independently verified.**
Full detail: [SECURITY.md](SECURITY.md).

Only after the downloaded digest matches should you extract an archive. From an extracted engineering
release, run `sh verify-release.sh` before uploading an embedded installer, installing, or running
Dravux. A source checkout intentionally has no installer ZIPs under `INSTALLERS/`; run the same
release verifier on the checkout before local use, or obtain the separately published installer
artifact for an upload route.

## What Dravux can and cannot do here

Three separate questions, often confused with each other:

1. **Is the skill installed?** Can your assistant follow the Dravux method at all.
2. **Can it read the thing you want checked?** Source text, raw source, a rendered page, a repository
   file.
3. **Can it interact?** Keyboard, focus order, screenshots, clicking, live browser behaviour.

Installing a skill answers only the first. It never grants a browser, network access, a rendered
page, screenshots, keyboard control, or a repository's commit and pull-request history. Those come
from the app you are using.

| Surface | Route in | Typical limit |
|---|---|---|
| Claude Chat / Cowork | Upload `dravux.zip` | Code execution must be on; page acquisition varies |
| Claude Code (desktop or CLI) | Installer or plugin | Browser and page-inspection tooling stay optional |
| Codex (desktop or CLI) | Installer or plugin | Browser and page-inspection tooling stay optional |
| ChatGPT desktop Work / Codex | Local plugin source in this package | Start a new session after installing |
| Ordinary ChatGPT Chat | No plugin route | Attachments are reading material, not an installation |

**[docs/capabilities.md](docs/capabilities.md) is the full matrix** — every surface against every
kind of evidence, and exactly which preflight stop you should expect when something is missing.

If neither bundled validator can run, the only honest label is
`UNVALIDATED DRAFT — NOT A DRAVUX RESULT`.

## The 60-second self-test

Everything below is offline: no network, no accounts, no installs, no keys.

In Terminal, from this folder:

```bash
sh verify-release.sh
```

Expected last line:

```text
VERIFIED: Dravux 1.0.2 release tree passed all offline checks
```

Any other ending means the package did not verify. Stop; do not install it.

Inside an assistant, ask for the equivalent in words:

```text
Run your bundled contract-only self-test and show me the receipt.
```

Expected: a short receipt naming the contract result, the automated result, and a final status of
`INCOMPLETE`. `INCOMPLETE` is the right answer here — the self-test proves the machinery, and no
website has been examined yet.

## Your first real check, on a page you already have

This package ships a small deliberately broken web page and its repaired twin, so you can see a
`FAIL`, apply a fix, and see the difference — with no live site and no network.

```bash
python3 scripts/audit_demo_html.py demos/github/broken/index.html --state broken --output ~/Desktop/broken-report.json
python3 scripts/audit_demo_html.py demos/github/repaired/index.html --state repaired --output ~/Desktop/repaired-report.json
python3 scripts/validate_report.py ~/Desktop/broken-report.json
```

Expected output, in order:

```text
Wrote ~/Desktop/broken-report.json: FAIL | VERIFIED FAIL
Wrote ~/Desktop/repaired-report.json: PASS | INCOMPLETE
VALID Dravux report: DRV-DEMO-BROKEN-001 | FAIL | VERIFIED FAIL
```

How to read that:

- The broken page produces **five findings** and `FAIL | VERIFIED FAIL`. A machine-detectable
  failure with reproducible evidence is enough to establish a failure.
- The repaired page produces **zero findings** and `PASS | INCOMPLETE` — not `VERIFIED PASS`.
  Automation cleared what automation can see. Keyboard behaviour, meaning, and real user experience
  still need a person. Dravux will not upgrade that verdict on its own.
- The third line is the validator agreeing that the report itself is well formed. Without that, a
  report is a draft, whatever it says inside.

That asymmetry — failures can be proven, passes cannot be assumed — is the whole idea.

Ready for a live site? Run it inside your assistant, and expect Dravux to ask first about the
evidence mode it will use. See [demos/live-site/README.md](demos/live-site/README.md).

## Troubleshooting

Organised by what you saw, not by what the internals are called.

### Claude stopped before the audit and said `LIMITATION_ACK_REQUIRED`

**This is Dravux working correctly.** It is not an error, and it is not a failed audit.

It means Dravux asked the session for the strongest evidence it wanted — usually a fully rendered
page — could not get it, and found a weaker option instead, such as the page's source text. Rather
than quietly downgrading and handing you a weaker result dressed up as a full one, it stopped to
ask.

**Your next action:** reply with a plain yes or no.

- To continue with less: say so explicitly, for example
  `Yes, proceed with source text only, and mark the limits in the report.` Dravux will then audit
  within that reduced mode, use "potential" wording for anything it could not confirm, and finish at
  `INCOMPLETE`.
- To get the full check instead: move to a surface that can open and render pages, then ask again.
  [docs/capabilities.md](docs/capabilities.md) says which those are.

Dravux must not choose for you. That is deliberate.

### I only got source text, not the real page

Your session could read the page's underlying markup but could not render it — no layout, no colours
as displayed, no keyboard behaviour, no scripts. Contrast, focus order, motion, and anything that
appears only after a script runs cannot be judged from that.

What to do: accept the reduced mode if source-level findings are useful to you, and read the result
as partial. Or switch to a surface with a real browser and re-run.

What not to do: treat a source-only `PASS` as evidence the page works. It is not.

### Where did my report go?

Dravux never writes audit files inside its own installed folder, inside this package, or inside an
extracted release. Doing so would make the manifest and internal consistency checks fail. Instead it
writes to a folder named `dravux-audits`, outside those trees.

To see the exact location:

```bash
python3 <skill-root>/scripts/dravux_run.py output-dir
```

Replace `<skill-root>` with where the skill was installed. The last line printed is the absolute
path where reports go. Add `--audit-id my-first-audit` to keep separate runs apart. If you run it
from inside the package or an installed skill, it tells you it redirected and where to; add
`--strict` if you would rather it refuse than redirect.

If you asked an assistant for a report and got only text on screen, no file was written. Ask it for
the file, or copy the text out yourself.

### The ZIP will not install

Only one of the archives is a Claude skill upload, and it is not the big one.

- `dravux.zip` (in `INSTALLERS/Claude-Chat-Cowork/`) is the Claude upload. Unzipping it gives a
  single folder named `dravux` containing `SKILL.md`. That shape is what the upload requires.
- `Dravux-1.0.2.zip` is the complete package for people installing from Terminal. It will be
  rejected as a skill upload.
- `Dravux-OpenAI-Plugin-Source.zip` (in `INSTALLERS/Codex-ChatGPT/`) is plugin source for
  submission or workspace sharing, not a one-click installer.

Also check that code execution is on in Claude, and start a new conversation after enabling the
skill. Do not unzip and re-zip an archive — that adds a wrapper folder and hidden operating-system
files, and the upload will fail.

### I need evidence from GitHub — files, commit history, pull requests

These are three different things and only some are obtainable.

A repository connection typically supplies **files you select**. It does not supply commit history,
pull-request diffs, review threads, or repository metadata, and no skill can add them. If your
audit's evidence depends on history or a pull request, that has to come from a surface that provides
it, or from you pasting it in.

[docs/capabilities.md](docs/capabilities.md) maps each evidence need to the routes that can supply
it and to what the preflight should declare when they cannot.

### Other symptoms

- **`verify-release.sh` or a checksum fails.** Stop. Do not install. Get a fresh copy and retry.
- **A Python error appears.** Run `python3 --version`. Dravux needs 3.8 or newer. No Python packages
  are required.
- **"Destination already exists".** The installer refuses to overwrite. Use a new folder, or move the
  existing one aside — see [Update or remove](#update-or-remove).
- **Dravux does not appear in the app.** Confirm the right project is open, run `verify-install.sh`
  (plain install) or the app's plugin list (plugin install), then start a new session.
- **The command name is unknown.** Plain installs answer to `/dravux` or `$dravux`. Plugin installs
  answer to `/dravux:dravux` or `$dravux:dravux`.
- **Two copies, or a shadowed skill.** Do not keep a plain install and a plugin install active in the
  same app. Remove one and start a new session.
- **A local plugin source points at an older extracted folder.** Remove that entry, change into the
  current verified folder, add it again, reinstall.
- **`UNSUPPORTED` in preflight.** The current surface cannot run the bundled validators. Move to one
  that can. An attachment-only answer is not a Dravux result.
- **A live URL ends `INCOMPLETE`, or reports a tooling `ERROR`.** That can be the correct bounded
  outcome when the session lacks browser access or manual evidence. It does not mean the contract
  failed.
- **Loose `.DS_Store` files appear after extracting.** Harmless. macOS creates them. They are
  excluded from every Dravux archive, and the verifier warns about them rather than failing.

---

# Installation and reference

Everything above is the beginner path. Everything below is the full detail.

## Requirements

- macOS
- Python 3.8 or newer (`python3 --version`)
- Claude Chat/Cowork with custom skills enabled, Claude Code, Codex, or ChatGPT Work with the Dravux
  plugin
- No package installation, network access, API key, or external scanner is required for Dravux's
  validator and offline tests

## Verify before installing

1. For a downloaded archive, complete the pre-extraction digest check above.
2. Only after it matches, unzip the release.
3. Open Terminal and change into the `Dravux-1.0.2` folder.
4. Run the internal consistency verifier before installing or running anything:

```bash
sh verify-release.sh
```

Expected last line:

```text
VERIFIED: Dravux 1.0.2 release tree passed all offline checks
```

## Create a disposable acceptance project

Run this from the extracted `Dravux-1.0.2` folder. It creates a uniquely named Desktop project and
copies the acceptance fixtures into it:

```bash
DRAVUX_TEST_PROJECT="$HOME/Desktop/Dravux-Test-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DRAVUX_TEST_PROJECT"
cp -R fixtures "$DRAVUX_TEST_PROJECT/fixtures"
printf 'Test project: %s\n' "$DRAVUX_TEST_PROJECT"
```

Keep this Terminal window open while installing. Open the printed project path in the desktop app
when instructed below.

## Installation options

Choose exactly one. Do not install both a plain skill copy and a plugin copy for the same app;
duplicate copies cause confusing discovery or shadowing.

### Option A — project-only install (recommended for first testing)

Claude Code/Desktop:

```bash
sh install.sh --claude --project-dir "$DRAVUX_TEST_PROJECT"
sh verify-install.sh --claude --project-dir "$DRAVUX_TEST_PROJECT"
```

Codex CLI/Desktop:

```bash
sh install.sh --codex --project-dir "$DRAVUX_TEST_PROJECT"
sh verify-install.sh --codex --project-dir "$DRAVUX_TEST_PROJECT"
```

Project destinations:

- Claude: `<project>/.claude/skills/dravux`
- Codex: `<project>/.agents/skills/dravux`

The project directory must already exist. The installer never guesses it from the current directory.

### Option B — personal install

Use this only when Dravux should be available in every project for that app.

Claude Code/Desktop:

```bash
sh install.sh --claude --personal
sh verify-install.sh --claude --personal
```

Codex CLI/Desktop:

```bash
sh install.sh --codex --personal
sh verify-install.sh --codex --personal
```

Personal destinations:

- Claude: `$HOME/.claude/skills/dravux`
- Codex: `$HOME/.agents/skills/dravux`

The installer refuses to merge with, replace, or rename an existing destination. That is intentional.

### Option C — native local plugin marketplace

The repository also includes local marketplace metadata for both products. Use this route instead of
the plain installer if plugin management is preferred.

Claude Code:

```bash
claude plugin marketplace add "$(pwd)"
claude plugin install dravux@dravux
```

In Claude Code Desktop, configured marketplaces are available from the Code tab through `+` →
`Plugins`. Claude documents project and personal skills in
[Extend Claude with skills](https://code.claude.com/docs/en/slash-commands), desktop behavior in
[Claude Code Desktop](https://code.claude.com/docs/en/desktop), and local marketplaces in
[Plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces).

Codex:

```bash
codex plugin marketplace add "$(pwd)"
codex plugin add dravux@dravux
```

Codex documents project/user skill discovery and plugin distribution in
[Build skills](https://learn.chatgpt.com/docs/build-skills).

Plugin commands modify the app's plugin configuration and cache. The plain installer does not.

### Option D — Claude Chat or Cowork custom-skill upload

Use the dedicated `dravux.zip` supplied under `INSTALLERS/Claude-Chat-Cowork/`. In Claude:

1. Open Customize > Skills — the screen where skills are uploaded. Some versions place it under
   Settings and label it Capabilities.
2. Enable code execution for the account if it is not already enabled.
3. Select `+` > Create skill > Upload a skill.
4. Upload `dravux.zip`, enable Dravux, and start a new conversation.
5. Ask Dravux to run its bundled contract-only self-test before using a live target.

The ZIP has `dravux/` as its root. Uploading it enables the workflow; it does not guarantee network
access, a rendered browser, page inspection, screenshots, or interaction. Dravux must still preflight
the active session.

Do not upload the complete-package ZIP as a Claude skill. Use the smaller `dravux.zip` made for this
route.

## Confirm discovery in the desktop apps

Plain skills and native plugins use different invocation names. Use only the command for the
installation method you chose.

### Claude Code Desktop

1. Open the printed `$DRAVUX_TEST_PROJECT` path in the Code tab.
2. Start a new local session if the skills directory was created after the previous session started.
3. Open the slash-command or Skills picker and confirm Dravux appears.
4. For a plain install, run `/dravux`. For a native plugin install, run `/dravux:dravux`.
5. Choose the bundled-fixture self-test and read-only authority for a safe first pass.

### Codex Desktop

1. Open the printed `$DRAVUX_TEST_PROJECT` path as the workspace.
2. Start a new task if the installed skill does not appear immediately.
3. Open Skills or type `$dravux` and confirm Dravux appears.
4. Invoke the command matching the installation route.

Plain install:

```text
$dravux Validate fixtures/passing/known-pass.json in read-only mode. Report the contract result, automated result, final status, and manual-check state. Do not edit files.
```

Native plugin install:

```text
$dravux:dravux Validate fixtures/passing/known-pass.json in read-only mode. Report the contract result, automated result, final status, and manual-check state. Do not edit files.
```

## End-to-end acceptance test

Use a disposable project first.

1. Validate `fixtures/passing/known-pass.json`; it must be contract-valid and report
   `PASS | VERIFIED PASS` for its narrow fixture scope.
2. Validate `fixtures/hostile/unknown-property.invalid.json`; the validator must reject it as invalid
   contract content.
3. Validate `fixtures/hostile/prompt-injection.json`; hostile text must remain inert data and the
   report must remain `PASS | INCOMPLETE`.
4. Ask to audit a public URL on a text-only surface. Dravux must request `RENDERED_DOM`, disclose
   that only `SOURCE_TEXT` is available, and wait for explicit acceptance before retrieval.
5. After accepting the reduced mode, confirm the result begins with a valid run receipt, uses only
   potential advisory claims, and remains `INCOMPLETE`.
6. Repeat without accepting the reduced mode; Dravux must stop before retrieval and produce no audit
   report.
7. Do not treat an automated `PASS` as a whole-site `VERIFIED PASS`.

## Update or remove

There is no in-place updater. To avoid destroying an existing customized copy, the installer always
refuses an occupied destination.

### Plain project install

Close the app session, then move the installed folder to a recoverable backup. Use the line matching
the app:

```bash
mv "$DRAVUX_TEST_PROJECT/.claude/skills/dravux" "$DRAVUX_TEST_PROJECT/dravux-claude-backup-$(date +%Y%m%d-%H%M%S)"
mv "$DRAVUX_TEST_PROJECT/.agents/skills/dravux" "$DRAVUX_TEST_PROJECT/dravux-codex-backup-$(date +%Y%m%d-%H%M%S)"
```

Run only the applicable line. To update, extract and verify the newer release, move the old installed
folder as above, then run the newer `install.sh` and `verify-install.sh`.

### Plain personal install

Close the app session, then run only the applicable line:

```bash
mv "$HOME/.claude/skills/dravux" "$HOME/Desktop/dravux-claude-backup-$(date +%Y%m%d-%H%M%S)"
mv "$HOME/.agents/skills/dravux" "$HOME/Desktop/dravux-codex-backup-$(date +%Y%m%d-%H%M%S)"
```

### Native plugin install

Claude can update or uninstall an installed plugin:

```bash
claude plugin update dravux@dravux
claude plugin uninstall dravux@dravux
```

Codex local plugins update by removing the installed copy, replacing the local marketplace source
with the newly extracted release, and adding the plugin again:

```bash
codex plugin remove dravux@dravux
codex plugin marketplace remove dravux
codex plugin marketplace add "$(pwd)"
codex plugin add dravux@dravux
```

Start a new app session after any install, update, or removal.

## Reference and architecture

- Package version: `1.0.2`
- Report-contract version: `0.2.0`
- Preflight-contract version: `1.0.0`
- Operational-run-contract version: recorded as `operational_contract_version` in
  `RELEASE_MANIFEST.json` and declared by the bundled operational validator
- Normative accessibility standard: WCAG `2.2`

### Package map

```text
Dravux-1.0.2/
├── START_HERE.md                   Plain-language entry point
├── SECURITY.md                     Integrity gate, residual risks, vulnerability reporting
├── INSTALLERS/                     Guides; built release includes ready-made archives
├── plugins/dravux/skills/dravux/   One canonical shipped skill
├── .claude-plugin/                 Claude local marketplace
├── .agents/plugins/                Codex local marketplace
├── fixtures/                       Valid, invalid, ambiguous, and hostile reports
├── tests/                          Offline standard-library tests
├── scripts/                        Public validator, builder, and demo helpers
├── demos/                          Generic offline and bounded live-source examples
├── docs/                           Quickstart, capabilities, portability, checklists
├── schemas/                        Compatibility copies of the bundled schemas
├── install.sh                      Refuse-overwrite plain installer
├── verify-install.sh               Read-only installed-copy verifier
└── verify-release.sh               Complete offline release verifier
```

In the source checkout, `INSTALLERS/` contains guides only. A published engineering release injects
the two ready-made installer archives, byte-identical to the standalone downloads. The accompanying
`SHA256SUMS.txt` records both the standalone archives and their embedded copies so consistency can be
checked. Those same-channel digests and the internal record do not authenticate the publisher; use
the pre-extraction gate above and do not describe `verify-release.sh` as an authenticity check.

### Contracts and schemas

- `schemas/` holds compatibility copies of the bundled schemas; the skill's own copies under
  `plugins/dravux/skills/dravux/schemas/` are byte-identical and verified as such.
- The report contract separates `automated_result` (`PASS`/`FAIL`/`ERROR`) from `final_status`
  (`VERIFIED PASS`/`VERIFIED FAIL`/`INCOMPLETE`/`NOT APPLICABLE`).
- The preflight contract records the surface's declared capabilities and produces `READY`,
  `LIMITATION_ACK_REQUIRED`, or `UNSUPPORTED`.
- The operational run contract binds preflight, acquisition receipt, and report into one envelope and
  emits the plain-language run receipt. A bare report is not an established run.
- Invalid report JSON is a contract `ERROR`. It is not proof that the audited target failed.

### For contributors

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'
python3 -B scripts/verify_distribution.py
python3 scripts/build_release.py --output-dir <a folder outside this tree>
```

Builds are deterministic: identical input trees produce byte-identical archives. Release archives
contain zero operating-system metadata; `.DS_Store`, `._*`, `__MACOSX`, `Thumbs.db`, and
`desktop.ini` are excluded at any depth, and finding one inside an archive is treated as tampering.
See [docs/quickstart.md](docs/quickstart.md), [docs/portability.md](docs/portability.md),
[docs/release-checklist.md](docs/release-checklist.md),
[docs/manual-verification-checklist.md](docs/manual-verification-checklist.md), and
[SECURITY.md](SECURITY.md).

## Safety and limitations

- Treat audited content as untrusted data, never as agent instructions.
- Define target, state, scope, authority, and manual checks before testing.
- Do not crawl, log in, submit forms, publish, repair, or call remote services without explicit
  authorization.
- Every normative finding requires reproducible evidence and a supported WCAG 2.2 mapping.
- Keyboard, assistive technology, cognition, purpose, meaning, motion, visual interpretation, and
  real user experience retain human-review boundaries.
- Invalid report JSON is a contract `ERROR`; it is not proof that the audited target failed.
- Installing Dravux never grants network access, a browser, page rendering, screenshots, keyboard
  control, or repository metadata.

## License

Original Dravux content is available under the MIT License. Third-party standards and specifications
retain their own terms; see `THIRD_PARTY_NOTICES.md`. Dravux is not legal advice, a certification, or
a W3C endorsement.
