# Install Dravux in the Codex or ChatGPT desktop app

Mostly clicking, with two short commands. About ten minutes.

## The file in this folder

`Dravux-OpenAI-Plugin-Source.zip` is the plugin source for Dravux. It is what you submit or share
when you want Dravux published to a workspace. It is **not** a one-click web installer: uploading it
to ordinary ChatGPT Chat does not install anything.

For your own desktop app, you do not need to unzip it. Install from this package directly.

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
