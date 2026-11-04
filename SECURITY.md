# Security and integrity

Dravux is free and open under the MIT License. This file is the single place for how to
check a download, what that check actually proves, what residual risks remain, and how to
report a vulnerability. Operator guides link here instead of repeating a long essay.

## Reporting a vulnerability

Open a [GitHub issue](https://github.com/chaddidit/Dravux/issues) for ordinary bugs and
documentation problems. Do **not** put secrets, private data, or sensitive exploit detail in a
public issue.

For a security vulnerability you believe is sensitive, open an issue titled
`Security: private disclosure requested` with **no** technical details in the body, and ask for a
private channel. If GitHub Security Advisories are enabled on the repository, prefer that private
advisory flow instead.

## Before you extract, upload, install, or run a download

1. Keep the archive unopened.
2. Calculate its SHA-256 digest (`shasum -a 256 <archive-name>` on macOS/Linux;
   `Get-FileHash -Algorithm SHA256 <archive-name>` in PowerShell on Windows).
3. Compare that digest with the exact matching line in the accompanying `SHA256SUMS.txt`.
4. Only after it matches, extract. From an extracted engineering release, run
   `sh verify-release.sh` on macOS/Linux before uploading an embedded installer,
   installing, or running Dravux.

The npm launcher package does not contain `verify-release.sh`: that command and the full offline
suite require the engineering ZIP or source checkout.

A source checkout intentionally has no installer ZIPs under `INSTALLERS/`. Verify the checkout
with `sh verify-release.sh` before local use, or obtain the separately published installer
artifact for an upload route.

## What the integrity checks prove — and what they do not

A same-channel `SHA256SUMS.txt`, the embedded `RELEASE_MANIFEST.json`, and the internal release
record detect corruption or internal inconsistency only. They do **not** authenticate the
publisher. Same-channel checksums establish consistency, not publisher identity.

Dravux 1.0.4 has no cryptographic publisher signature.
**Publisher authenticity was not independently verified.**

Do not describe `verify-release.sh`, the manifest, or the checksum file as proof that a download
came from a trusted publisher. They prove the tree is self-consistent with what the package claims
to ship.

## What the offline validators enforce

- Bounded JSON ingress (byte, depth, container, aggregate-item, string/key, numeric-token, and
  structural-token limits) with duplicate-key and non-finite-number rejection. Schemas do not
  publish `maxLength`; loader limits live in the Python validators.
- Contract string fields reject all C0 controls (including TAB, LF and CR), DEL, and all C1 controls; Unicode line/paragraph
  separators; bidi embedding, override and isolate controls U+202A–U+202E and U+2066–U+2069;
  and U+061C, U+200E and U+200F, even alongside visible text. ZWJ, ZWNJ and soft hyphen
  remain allowed. Diagnostics identify the field and code point.
- Validator diagnostics quote untrusted keys and values as escaped single-line ASCII literals.
  Text receipts escape C1 controls and Unicode formatting characters, including bidi overrides;
  `--json` preserves the authoritative contract values.
- Website preflight and acquisition records are checked against literal special-address and metadata-host rules
  for the requested URL, redirect hops, and final location.
- Installers refuse symlink parents and unsafe ownership or permissions. Group-writable directories
  are accepted only when owned by the user, in their primary group, with no other account in
  `getgrgid().gr_mem` and no other account using that group as its primary group; world-writable
  directories are always refused. On macOS, `staff` normally
  fails that membership check. Installed files/folders must be user-owned and have no setuid, setgid
  or sticky bits. Installers refuse overwrite and do not call
  `curl`, `wget`, `sudo`, or `eval`. Source and staging trees reject symlinks and special files
  before staged validation; exclusive finalization refuses a destination that appears during installation.
- Audit output is redirected outside skill, checkout, and release trees so a verified tree stays
  verified.
- Release archives reject unsafe paths, symlink members, OS metadata inside the archive, and
  expansion that exceeds fixed budgets.

## Residual risks (honest limits)

- **No publisher signature.** Same-channel digests are consistency checks only.
- **No DNS in the offline validator.** Recorded URLs are checked as literals. The validator cannot
  prove a redirect chain is complete and cannot eliminate DNS rebinding. Acquisition tooling must
  resolve DNS before the initial request and every redirect hop, and must fail closed unless every
  A/AAAA address is global. A hostname resolving to an internal IP can pass the literal offline
  check: DNS-to-internal-IP detection is permanently outside this validator because it requires
  network resolution. See `plugins/dravux/skills/dravux/SKILL.md` and
  `plugins/dravux/skills/dravux/references/input-capabilities.md`.
- **Skill-in-assistant architecture.** Hostile page or fixture text is inert data to the validators.
  An assistant that ignores the skill policy could still follow embedded instructions. That is a
  host/model risk, not something the offline validator can eliminate.
- **Folder creation is not atomic with its identity check.** `output-dir` records the identity of
  a new `dravux-audits` folder and a new audit folder right after `mkdir`. A process that can
  already write to the parent folder could swap in an empty folder in that instant; a refusal then
  removes only that empty folder, never a folder with contents. POSIX offers no way to close this
  window.
- **"Filled in" follows the running Python's Unicode tables.** A text field made only of
  characters newer than that Python's Unicode version (for example a new emoji on Python 3.8)
  is treated as unassigned and refused; newer Pythons accept it.

## Platform notes

Python validators and contracts are meant to stay OS-agnostic (standard library only). POSIX shell
installers (`install.sh`, `verify-install.sh`, `verify-release.sh`) are the supported operator path
on macOS and Linux today. Native Windows shell entry points are a separate portability task; see
[docs/portability.md](https://github.com/chaddidit/Dravux/blob/v1.0.4/docs/portability.md). CI defines full offline gates on Ubuntu/macOS and a scoped contract-validation job on Windows.
The `output-dir` helper refuses systems without POSIX directory-descriptor support.
A passing check on the exact release commit is required before claiming platform verification.
