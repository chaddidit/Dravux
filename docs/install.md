# Install, use, and maintain Dravux

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
supported POSIX installers today. CI defines a Windows job for contract, preflight, and run
validation; full release verification and safe `output-dir` creation require macOS/Linux. Native Windows shell installers are still a separate portability task — see
[docs/portability.md](portability.md). A standalone GUI or browser extension is a separate
product layer; both can reuse the same contracts and validators.

## Downloads

Get packaged assets from [GitHub Releases](https://github.com/chaddidit/Dravux/releases).
Use the assets attached to the published version tag. If there is no published version with these
assets, a packaged release is not yet available.

| Asset | Use it for |
|---|---|
| `dravux.zip` | Claude Chat/Cowork custom-skill upload, where enabled |
| `Dravux-OpenAI-Plugin-Source.zip` | Codex/ChatGPT local plugin source, where the host supports local plugins |
| `Dravux-1.0.4.zip` | Full engineering release, local installers, offline tests, and both embedded installer ZIPs |
| `dravux-1.0.4.tgz` | Packaged npm launcher; 1.0.4 is also published to the npm registry |
| `SHA256SUMS.txt` | Compare the matching archive digest before extraction, upload, or execution |

GitHub's automatically generated **Source code** archives are source snapshots, not the packaged
release. They do not contain the built installer ZIPs. Download `SHA256SUMS.txt` alongside your
chosen asset and follow the integrity steps below. Checksums detect corruption and inconsistency;
1.0.4 has no publisher signature and does not independently authenticate its publisher.

## Choose your path

New here? **[START_HERE.md](../START_HERE.md)** walks through all four routes step by step.

| You are... | Route | Start with |
|---|---|---|
| Using Claude in a browser or Cowork | Check the file's integrity, then upload it in the app | [INSTALLERS/Claude-Chat-Cowork/](../INSTALLERS/Claude-Chat-Cowork) |
| Using the Codex or ChatGPT desktop app | Install as a local plugin | [INSTALLERS/Codex-ChatGPT/](../INSTALLERS/Codex-ChatGPT) |
| Comfortable in Terminal (Claude Code, Codex CLI) | Run the installer | [Installation options](#installation-options) below |
| Maintaining or reviewing Dravux itself | Run the test suite | [Reference and architecture](#reference-and-architecture) |

## Verify a downloaded artifact before using it

Do not extract, upload, install, or run a downloaded Dravux archive until its digest has been checked.
Keep the archive unopened, calculate its SHA-256 digest, and compare it with the exact matching line in
the accompanying `SHA256SUMS.txt`:

```bash
shasum -a 256 Dravux-1.0.4.zip
shasum -a 256 dravux.zip
shasum -a 256 Dravux-OpenAI-Plugin-Source.zip
```

Check only the archive you actually received. That fingerprint check catches corruption in transit; it
does **not** prove who published the file. Dravux 1.0.4 has no cryptographic publisher signature.
**Publisher authenticity was not independently verified.**
Full detail: [SECURITY.md](../SECURITY.md).

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

**[docs/capabilities.md](capabilities.md) is the full matrix** — every surface against every
kind of evidence, and exactly which preflight stop you should expect when something is missing.

If neither bundled validator can run, the only honest label is
`UNVALIDATED DRAFT — NOT A DRAVUX RESULT`.

## The 60-second self-test

This self-test is offline: no network, no accounts, no installs, no keys.

In Terminal, from the engineering release or source-checkout root:

```bash
sh verify-release.sh
```

Expected last line:

```text
VERIFIED: Dravux 1.0.4 release tree passed all offline checks
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
evidence mode it will use. See [demos/live-site/README.md](../demos/live-site/README.md).


---

# Installation and reference

Everything above is the beginner path. Everything below is the full detail.
This page uses the full engineering ZIP or a source checkout; the npm launcher does not include
the fixtures, demos, tests, adapters, or release/build scripts referenced below.

## Requirements

- macOS or Linux for shell installers, full release verification, and `output-dir`
- Windows: portable Python contract validation only; native installers are not shipped
- Python 3.8 or newer (`python3 --version`)
- Claude Chat/Cowork with custom skills enabled, Claude Code, Codex, or ChatGPT Work with the Dravux
  plugin
- No package installation, network access, API key, or external scanner is required for Dravux's
  validator and offline tests

## Verify before installing

1. For a downloaded archive, complete the pre-extraction digest check above.
2. Only after it matches, unzip the release.
3. Open Terminal and change into the `Dravux-1.0.4` folder.
4. Run the internal consistency verifier before installing or running anything:

```bash
sh verify-release.sh
```

Expected last line:

```text
VERIFIED: Dravux 1.0.4 release tree passed all offline checks
```

## Create a disposable acceptance project

Run this from the extracted `Dravux-1.0.4` engineering folder. It creates a uniquely named Desktop project and
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

### Via npx (npm registry; GitHub-tag alternative)

Requires Node.js 18 or newer, macOS or Linux with `sh`, and Python 3.8 or newer.
Dravux 1.0.4 is published to npm and installs with `npx --yes dravux@1.0.4`.
Dravux 1.0.3 is also on npm. The GitHub-tag route is the alternative; it downloads
the tagged package without using npm registry publication.
Review the tagged source and the [integrity limits](../SECURITY.md) before running it.

```bash
npx --yes dravux@1.0.4 --help
npx --yes dravux@1.0.4 --codex --project-dir "$DRAVUX_TEST_PROJECT"
npx --yes dravux@1.0.4 verify --codex --project-dir "$DRAVUX_TEST_PROJECT"

# Alternative: published GitHub tag
npx --yes github:chaddidit/Dravux#v1.0.4 --help
npx --yes github:chaddidit/Dravux#v1.0.4 --codex --project-dir "$DRAVUX_TEST_PROJECT"
npx --yes github:chaddidit/Dravux#v1.0.4 verify --codex --project-dir "$DRAVUX_TEST_PROJECT"
```

Use `--claude` for Claude, or replace `--project-dir` and its path with `--personal`
to install under `HOME`. The project must already exist. Existing installs are never overwritten.
Both published routes accept the same arguments.
The launcher uses the bundled shell installers and adds no runtime dependencies.

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

Use the dedicated `dravux.zip` supplied under `INSTALLERS/Claude-Chat-Cowork/`. The upload itself uses
the app interface, but the integrity checks above use command-line steps and come first. In Claude:

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

- Package version: `1.0.4`
- Report-contract version: `0.2.0`
- Preflight-contract version: `1.0.0`
- Operational-run-contract version: recorded as `operational_contract_version` in
  `RELEASE_MANIFEST.json` and declared by the bundled operational validator
- Normative accessibility standard: WCAG `2.2`

### Package map

```text
Dravux-1.0.4/
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
├── docs/                           Install, troubleshooting, CLI reference, quickstart, checklists
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
See [docs/quickstart.md](quickstart.md), [docs/portability.md](portability.md),
[docs/release-checklist.md](release-checklist.md),
[docs/manual-verification-checklist.md](manual-verification-checklist.md), and
[SECURITY.md](../SECURITY.md).

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

### Historical packaging limits in 1.0.3

These two limits were tracked for 1.0.4; the published 1.0.3 downloads are unchanged:

- `dravux-1.0.3.tgz` is a slim launcher package, not the engineering tree. Its bundled README and
  security guide mention files and commands that only the engineering tree has, such as
  `START_HERE.md` and `sh verify-release.sh`. For those, use this guide at the
  [tagged commit](https://github.com/chaddidit/Dravux/tree/8166a35db883c77c88f55dc2d9f27caaf1ed34ff)
  or the full `Dravux-1.0.3.zip`.
- The standalone Claude upload `dravux.zip` and plain installed skill copies do not include
  `LICENSE` or `THIRD_PARTY_NOTICES.md`. The tagged copies are
  [LICENSE](https://github.com/chaddidit/Dravux/blob/8166a35db883c77c88f55dc2d9f27caaf1ed34ff/LICENSE) and
  [THIRD_PARTY_NOTICES.md](https://github.com/chaddidit/Dravux/blob/8166a35db883c77c88f55dc2d9f27caaf1ed34ff/THIRD_PARTY_NOTICES.md). The published
  1.0.3 archives are unchanged; this note does not fix them.

## License

Original Dravux content is available under the MIT License. Third-party standards and specifications
retain their own terms; see `THIRD_PARTY_NOTICES.md`. Dravux is not legal advice, a certification, or
a W3C endorsement.
