# Troubleshooting

## Artifact integrity gate

Before extracting, uploading, installing, or running a downloaded archive, keep it unopened,
calculate `shasum -a 256 <archive-name>`, and compare its exact entry in `SHA256SUMS.txt`.
Continue only when it matches. Same-channel checksums establish consistency, not publisher identity.
Dravux 1.0.4 has no cryptographic publisher signature.
**Publisher authenticity was not independently verified.** See [SECURITY.md](../SECURITY.md).
From an extracted engineering ZIP or source checkout, run its `sh verify-release.sh` before use;
that file is absent from the npm launcher.

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
  [docs/capabilities.md](capabilities.md) says which those are.

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
- `Dravux-1.0.4.zip` is the complete package for people installing from Terminal. It will be
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

[docs/capabilities.md](capabilities.md) maps each evidence need to the routes that can supply
it and to what the preflight should declare when they cannot.

### Other symptoms

- **`verify-release.sh` or a checksum fails.** Stop. Do not install. Get a fresh copy and retry.
- **A Python error appears.** Run `python3 --version`. Dravux needs 3.8 or newer. No Python packages
  are required.
- **"Destination already exists".** The installer refuses to overwrite. Use a new folder, or move the
  existing one aside — see [Update or remove](install.md#update-or-remove).
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


## Installer refused an owner or writable parent

The installer checks ownership of `.claude`/`.agents`, `skills`, and the destination parent:
each must belong to your current user or root. It refuses unsafe paths with exit `4` and installs
nothing. Do not use `sudo` to bypass a refusal.

A group-writable directory (such as mode `0775`) is accepted only if you own it, its group is your
primary group, and `getgrgid().gr_mem` lists no other account. World-writable directories and all
other group-writable directories are refused. On macOS, `staff` normally fails the membership
condition, so a `0775` folder in `staff` is still refused. Remove group write permission with
`chmod g-w <path>` on the exact folder named by the error, then retry; do not change a folder
you do not own. The installed-copy verifier also refuses any file or folder not owned by you,
or carrying setuid, setgid, or sticky bits.

## Linux cannot finalize the install safely

Linux uses `renameat2` with `RENAME_NOREPLACE` so a raced destination cannot be replaced.
If libc lacks the wrapper (for example glibc before 2.28), the installer tries the direct system
call on the supported architectures listed in [Portability](portability.md#linux-exclusive-rename).
Unsupported architectures, `ENOSYS`, `EINVAL`, or an unavailable call cause a safe refusal, with
nothing installed. Use a supported OS/filesystem; Dravux never substitutes an overwriting rename.

## The validator named a field and a code point

Fix the named JSON field rather than removing validation. Contract strings reject all C0 controls (including TAB, LF and CR), DEL, and all C1
controls; Unicode line/paragraph separators; bidi embedding, override
and isolate controls U+202A–U+202E and U+2066–U+2069; and U+061C, U+200E and U+200F.
ZWJ, ZWNJ and soft hyphen remain allowed when the field otherwise contains visible text.
A preflight error in `validate` names the JSON path, expected value/type, and found value
as an escaped representation cut to 80 characters.

For every command, flag and exit code, see [CLI reference](cli-reference.md).
