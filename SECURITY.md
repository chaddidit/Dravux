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

A source checkout intentionally has no installer ZIPs under `INSTALLERS/`. Verify the checkout
with `sh verify-release.sh` before local use, or obtain the separately published installer
artifact for an upload route.

## What the integrity checks prove — and what they do not

A same-channel `SHA256SUMS.txt`, the embedded `RELEASE_MANIFEST.json`, and the internal release
record detect corruption or internal inconsistency only. They do **not** authenticate the
publisher.

Dravux 1.0.2 has no cryptographic publisher signature.
**Publisher authenticity was not independently verified.**

Do not describe `verify-release.sh`, the manifest, or the checksum file as proof that a download
came from a trusted publisher. They prove the tree is self-consistent with what the package claims
to ship.

## What the offline validators enforce

- Bounded JSON ingress (byte, depth, container, aggregate-item, string/key, numeric-token, and
  structural-token limits) with duplicate-key and non-finite-number rejection. Schemas do not
  publish `maxLength`; loader limits live in the Python validators.
- Contract string fields reject ASCII control characters, `DEL`, `NEL`, and Unicode line/paragraph
  separators so free text cannot forge extra lines in a run receipt.
- Validator diagnostics quote untrusted keys and values as escaped single-line ASCII literals.
  Text receipts escape C1 controls and Unicode formatting characters, including bidi overrides;
  `--json` preserves the authoritative contract values.
- Website preflight and acquisition records are checked against literal special-address and metadata-host rules
  for the requested URL, redirect hops, and final location.
- Installers refuse symlink and group-/world-writable parents, refuse overwrite, and do not call
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
  A/AAAA address is global. See `plugins/dravux/skills/dravux/SKILL.md` and
  `plugins/dravux/skills/dravux/references/input-capabilities.md`.
- **Skill-in-assistant architecture.** Hostile page or fixture text is inert data to the validators.
  An assistant that ignores the skill policy could still follow embedded instructions. That is a
  host/model risk, not something the offline validator can eliminate.

## Platform notes

Python validators and contracts are meant to stay OS-agnostic (standard library only). POSIX shell
installers (`install.sh`, `verify-install.sh`, `verify-release.sh`) are the supported operator path
on macOS and Linux today. Native Windows shell entry points are a separate portability task; see
[docs/portability.md](docs/portability.md). CI defines full offline gates on Ubuntu/macOS and a scoped contract-validation job on Windows.
The `output-dir` helper refuses systems without POSIX directory-descriptor support.
A passing check on the exact release commit is required before claiming platform verification.
