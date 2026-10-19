# Start here

Dravux checks websites and web content for accessibility problems — the barriers that stop people
who use screen readers, keyboards, magnification, captions, or reduced motion from using a page.

It works as an add-on for an AI assistant. You describe what you want checked, and Dravux keeps the
assistant honest: it states up front what it can and cannot see, it separates "the automated check
passed" from "a person verified this", and it refuses to invent evidence.

**Dravux is not a scanner you point at a URL and walk away from.** It is a discipline for an
assistant you already use. If the assistant cannot reach a page, Dravux says so instead of guessing.

## Pick the description that sounds like you

| You are... | Go to | Time |
|---|---|---|
| Using Claude in a browser or in Cowork, and you never want to open a terminal | [Path 1](#path-1--claude-chat-or-cowork-no-terminal) | 10 minutes |
| Using the Codex or ChatGPT desktop app, mostly clicking, plus two short commands to paste | [Path 2](#path-2--codex-or-chatgpt-desktop-app-mostly-clicking) | 10 minutes |
| Comfortable in Terminal, using Claude Code or the Codex command line | [Path 3](#path-3--claude-code-or-codex-command-line) | 5 minutes |
| Maintaining, packaging, or reviewing Dravux itself | [Path 4](#path-4--maintainer-or-developer) | 15 minutes |

Everything below is offline. Nothing in this package sends data anywhere, installs software, or
asks for a password, a card, or an API key.

## Verify the artifact before any route

Do not extract, upload, install, or run a downloaded archive first. Keep it unopened, calculate its
SHA-256 digest with `shasum -a 256 <archive-name>`, and compare the result with that archive's exact
line in the accompanying `SHA256SUMS.txt`. Only after it matches should you extract or use it. From an
extracted engineering release, run `sh verify-release.sh` before uploading an embedded installer,
installing, or running Dravux.

That fingerprint check catches corruption in transit; it does **not** prove who published the file.
Dravux 1.0.2 has no cryptographic publisher signature.
**Publisher authenticity was not independently verified.**
Details: [SECURITY.md](SECURITY.md).

A source checkout intentionally contains no installer ZIPs. Run `sh verify-release.sh` before local
use, and obtain the separately published `dravux.zip` or OpenAI plugin-source ZIP for a route that
needs an archive. Maintainers can generate release candidates outside the source tree with
`python3 -B scripts/build_release.py --output-dir <outside folder>`.

---

## Path 1 — Claude Chat or Cowork (no terminal)

**What you need:** a Claude account where you can turn on code execution.

**What to open:** the folder `INSTALLERS/Claude-Chat-Cowork/` inside this package. It contains one
file to upload, `dravux.zip`, and a short page of instructions in an extracted published release.
In a source checkout the folder intentionally contains only the guide; obtain the separately
published `dravux.zip` instead.

**Before you start:** some organization plans and admin settings turn custom skills or code execution
off entirely, and if yours does the upload option may be missing or greyed out — this is an account
setting Dravux cannot change, so ask whoever administers your Claude account to enable custom skills
and code execution.

**What to do:**

1. In Claude, open **Customize > Skills** — the screen where skills are uploaded. Depending on your
   version it may sit under Settings and be labelled Capabilities; look for the skills screen.
2. Make sure code execution is turned on for your account. Dravux checks its own work by running a
   small bundled program, so without it there is nothing to upload into.
3. Choose **+ > Create skill > Upload a skill**.
4. Upload `dravux.zip`, switch Dravux on, and start a new conversation.
5. In that new conversation, type: `Run your bundled contract-only self-test and show me the result.`

**What success looks like:** Dravux replies with a short receipt naming the contract result, the
automated result, and the final status. The final status will say `INCOMPLETE` — that is correct.
A self-test proves the machinery works; it does not certify a website.

**Where reports go:** into the conversation, and into files you download yourself. Dravux never
writes into its own installed folder.

**Honest limit:** uploading the skill gives Claude the Dravux method. It does not give Claude a web
browser, a screen reader, screenshots, or the ability to click things on a live page. Dravux checks
what the session can actually do before every audit and tells you what it found.

---

## Path 2 — Codex or ChatGPT desktop app (mostly clicking)

**What you need:** the Codex or ChatGPT desktop app with plugin support.

**What to open:** the folder `INSTALLERS/Codex-ChatGPT/` inside this package.

**What to do:** follow the short page in that folder. It walks you through adding this package as a
local plugin source and installing Dravux from it — two short commands to copy into a terminal —
then starting a fresh session so the app notices the new plugin.

**What success looks like:** typing `$dravux` in the app offers Dravux. Ask it for the bundled
self-test first, before any real website.

**Where reports go:** into the conversation, and into a folder you choose. See
[Where did my report go?](README.md#where-did-my-report-go) if you cannot find one.

**Honest limit:** ordinary ChatGPT Chat has no plugin route at all. Attaching these files to a chat
gives the assistant reading material, not a working Dravux installation, and any answer produced
that way is an unvalidated draft.

---

## Path 3 — Claude Code or Codex command line

**What you need:** macOS, Python 3.8 or newer, and Terminal.

**What to do:**

```bash
sh verify-release.sh
sh install.sh --claude --project-dir "$HOME/Desktop/Dravux-Test"
sh verify-install.sh --claude --project-dir "$HOME/Desktop/Dravux-Test"
```

Swap `--claude` for `--codex` for the Codex command line. Create the project folder first; the
installer refuses to guess it, and it refuses to overwrite anything that already exists.

**What success looks like:** the first command ends with
`VERIFIED: Dravux 1.0.2 release tree passed all offline checks`, and the third confirms the installed
copy matches the shipped copy byte for byte.

**Where reports go:** a `dravux-audits` folder outside the installed skill and outside this package.
Ask for the exact location with:

```bash
python3 <skill-root>/scripts/dravux_run.py output-dir
```

**Read next:** [README.md](README.md) for the 60-second self-test and the first website test.

---

## Path 4 — Maintainer or developer

Run the full offline suite, then the distribution verifier:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_*.py'
python3 -B scripts/verify_distribution.py
```

Then read, in order: [README.md](README.md) (architecture and reference sections at the end),
[docs/quickstart.md](docs/quickstart.md), [docs/portability.md](docs/portability.md),
[docs/release-checklist.md](docs/release-checklist.md), [SECURITY.md](SECURITY.md), and
[docs/capabilities.md](docs/capabilities.md) for exactly which surface can do which kind of
acquisition.

Release archives are built with `scripts/build_release.py`. Builds are deterministic: the same tree
produces byte-identical archives every time.

---

## If something stops you

Go to [Troubleshooting](README.md#troubleshooting) in the README. It is organised by what you saw on
screen, not by what the internals are called. The most common surprise —
`LIMITATION_ACK_REQUIRED`, where Dravux stops and asks before auditing — is Dravux working
correctly, not an error.
