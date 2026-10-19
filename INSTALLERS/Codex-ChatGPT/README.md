# Install Dravux in the Codex or ChatGPT desktop app

Mostly clicking, with two short commands. About ten minutes.

## Integrity gate — before upload or installation

For a downloaded artifact, do not extract, upload, install, or run it until its SHA-256 digest matches
the exact entry in the accompanying `SHA256SUMS.txt`. After a matching release-archive digest,
extract it and run `sh verify-release.sh` before the plugin commands below. A same-channel checksum,
the embedded manifest, and the internal release record detect corruption or inconsistency only; they
do not authenticate the publisher. Dravux 1.0.2 has no cryptographic publisher signature.
**Publisher authenticity was not independently verified.**
Details: [SECURITY.md](../../SECURITY.md).

For a source checkout, there is no installer ZIP to verify: run `sh verify-release.sh` on the checkout
before adding it as a local plugin source. If the plugin-source ZIP will be submitted or shared,
verify that separately published archive before uploading it.

## The file in this folder

`Dravux-OpenAI-Plugin-Source.zip` is the plugin source for Dravux. It is what you submit or share
when you want Dravux published to a workspace. It is **not** a one-click web installer: uploading it
to ordinary ChatGPT Chat does not install anything.

For your own desktop app, you do not need to unzip it. Install from this package directly. In a
downloaded engineering release the archive sits in this folder; in a source checkout it is
intentionally absent, and you still do not need it to install from the verified package.

## Install from this package

From the top folder of this package:

```bash
codex plugin marketplace add "$(pwd)"
codex plugin add dravux@dravux
```

Then start a new task in the app so it notices the new plugin.

## Check that it worked

Type `$dravux` in the app. Dravux should be offered. Ask for the bundled self-test before any real
website:

```text
$dravux:dravux Validate fixtures/passing/known-pass.json in read-only mode. Report the contract result, automated result, final status, and manual-check state. Do not edit files.
```

Use `$dravux` instead of `$dravux:dravux` if you installed the plain skill rather than the plugin.
Keep one route only: do not install both the plain skill and the plugin in the same app.

## Where your reports go

Not into this package. Dravux writes audit output into a `dravux-audits` folder outside its own
files, so a verified package stays verified. Ask for the exact path with:

```bash
python3 <skill-root>/scripts/dravux_run.py output-dir
```

## What you have, and what you do not

Installing the plugin gives the app the Dravux method and its validators. It does not grant a
browser, page rendering, clicking, screenshots, or repository history. Dravux reports which of those
are genuinely present before each audit. See [docs/capabilities.md](../../docs/capabilities.md) for
the full surface-by-surface picture.

## If it will not install

- **Plugin commands are not recognised.** Use the plain installer instead: `sh install.sh --codex
  --project-dir <your project folder>` from the top of this package.
- **The app still shows an old copy.** Remove the old plugin and the old local source, then add this
  package's folder again. The commands are in
  [the README's update section](../../README.md#update-or-remove).
- **You are in ordinary ChatGPT Chat.** There is no plugin route there. Anything produced that way
  is an unvalidated draft, not a Dravux result.
