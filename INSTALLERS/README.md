# Installers

Everything needed to install Dravux, in one place. Pick the folder that matches the app you use.

| Folder | Use it for | What is inside |
|---|---|---|
| `Claude-Chat-Cowork/` | Claude in a browser, or Cowork. No terminal needed. | `dravux.zip` plus instructions |
| `Codex-ChatGPT/` | The Codex or ChatGPT desktop app. | `Dravux-OpenAI-Plugin-Source.zip` plus instructions |

Using Claude Code or the Codex command line instead? You do not need this folder. Run
`sh install.sh` from the top of this package — see [Path 3 in START_HERE.md](../START_HERE.md).

## What these files are

Each folder holds one ready-made archive. They are exact copies of the archives published alongside
this release, byte for byte, so a checksum you were given for the standalone download also matches
the copy in here. `SHA256SUMS.txt` in the published release lists both.

Nothing in this folder needs to be built, unzipped, or edited before you use it. Upload or install
the archive as-is.

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
