# Installers

Everything needed to install Dravux, in one place. Pick the folder that matches the app you use.

## Integrity gate — before extraction, upload, or installation

For a downloaded artifact, keep the archive unopened, calculate its digest with
`shasum -a 256 <archive-name>`, and compare it with the exact matching line in the accompanying
`SHA256SUMS.txt`. Do not extract, upload, install, or run it unless the digest matches. A same-channel
checksum, the embedded manifest, and the internal release record detect corruption or inconsistency
only; they do not authenticate the publisher. Dravux 1.0.2 has no cryptographic publisher signature.
**Publisher authenticity was not independently verified.**

After the outer engineering archive matches, extract it and run `sh verify-release.sh` before using
either embedded installer. A source checkout contains these guides but intentionally contains no
installer ZIPs; verify the checkout before local use, or obtain the separately published installer
archive for an upload route.

| Folder | Use it for | What is inside |
|---|---|---|
| `Claude-Chat-Cowork/` | Claude in a browser, or Cowork. No terminal needed. | Guide; a published engineering release also injects `dravux.zip` |
| `Codex-ChatGPT/` | The Codex or ChatGPT desktop app. | Guide; a published engineering release also injects `Dravux-OpenAI-Plugin-Source.zip` |

Using Claude Code or the Codex command line instead? You do not need this folder. Run
`sh install.sh` from the top of this package — see [Path 3 in START_HERE.md](../START_HERE.md).

## What these files are

In an extracted published engineering release, each folder holds one ready-made archive. They are
exact copies of the archives published alongside the release, byte for byte, and the accompanying
`SHA256SUMS.txt` records both. In a source checkout, each folder holds its guide only.

After completing the integrity gate, do not rebuild, unzip, or edit an embedded installer before
use. Upload or install the verified archive as-is.

## What installing does and does not do

Installing Dravux teaches your assistant the Dravux method: preflight the session, state what
evidence is genuinely available, keep automated results separate from human-verified ones, and
refuse to certify what it did not observe.

Installing Dravux does **not** give an assistant a web browser, page rendering, keyboard control,
screenshots, or access to a repository's history. Those come from the app you are using, not from
this package. Dravux checks what is actually available at the start of every audit and says so in
plain language before it does anything.

## Before you audit a real site

Ask for the bundled self-test first. It runs against files shipped inside the skill, needs no
network, and proves the installation works. Details are in
[the README's 60-second self-test](../README.md#the-60-second-self-test).
